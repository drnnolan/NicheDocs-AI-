"""Split extracted pages into overlapping, page-attributed chunks.

The design constraint that drives this module: every chunk must know which page
it came from, because the page number *is* the citation the UI shows. So rather
than concatenating the document and splitting the blob, we tag each word with
its page and its enclosing heading, then slide a window over the tagged stream.
A chunk that straddles a page boundary is cited to the page where it starts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .pdf import PageText

# --- Heading detection ------------------------------------------------------
# Policy documents are heavily sectioned, and "Section 4.2 — Attendance" is a far more
# useful citation than "page 37" alone. These heuristics are intentionally
# conservative: a missed heading costs nothing (section is nullable), while a
# false positive mislabels every chunk beneath it.

# "4", "4.2", "4.2.1" followed by a title.
_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*\.?\s+\S.*$")
# "Section 4", "Chapter II", "Appendix B", "Article 3".
_NAMED_HEADING = re.compile(
    r"^(?:section|chapter|article|part|appendix|annex)\b\s*[\w.\-]*\s*[:.—-]?\s*\S?.*$",
    re.IGNORECASE,
)
_HAS_LETTER = re.compile(r"[A-Za-z]")
_WORD_SPLIT = re.compile(r"\s+")


def estimate_tokens(text: str) -> int:
    """Approximate the BPE token count of `text`.

    Four characters per token is OpenAI's own rule of thumb for English prose
    and is accurate to within ~10% on the handbooks this app targets. We use it
    instead of `tiktoken` because tiktoken downloads its BPE vocabulary from the
    network on first use, which is a cold-start failure mode we do not want in a
    serverless function. Chunk sizing tolerates the error fine — nothing here
    needs an exact count, only a consistent one.
    """
    return max(1, round(len(text) / 4))


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not (3 <= len(stripped) <= 90):
        return False
    if not _HAS_LETTER.search(stripped):
        return False
    # Real headings rarely end in sentence punctuation.
    if stripped.endswith((".", ",", ";", ":")) and not _NUMBERED_HEADING.match(stripped):
        return False
    if _NUMBERED_HEADING.match(stripped) or _NAMED_HEADING.match(stripped):
        return True
    # ALL-CAPS lines, e.g. "STUDENT CONDUCT". Require >1 word so we don't catch
    # stray acronyms sitting on their own line.
    letters = [ch for ch in stripped if ch.isalpha()]
    return bool(letters) and all(ch.isupper() for ch in letters) and len(stripped.split()) > 1


@dataclass(frozen=True)
class _Token:
    """One whitespace-delimited word, plus where it came from."""

    word: str
    page_number: int
    section: str | None


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    page_number: int
    section: str | None
    content: str
    token_count: int


def _tokenize(pages: list[PageText]) -> list[_Token]:
    tokens: list[_Token] = []
    current_section: str | None = None

    for page in pages:
        for line in page.text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if _is_heading(stripped):
                current_section = stripped
                # The heading itself is kept in the text so the embedding sees
                # it — it is often the most topical phrase in the chunk.
            for word in _WORD_SPLIT.split(stripped):
                if word:
                    tokens.append(
                        _Token(
                            word=word,
                            page_number=page.page_number,
                            section=current_section,
                        )
                    )
    return tokens


def _overlap_start(window: list[_Token], overlap_tokens: int) -> int:
    """Index into `window` at which the next chunk should begin.

    Walks backwards accumulating characters until we have roughly
    `overlap_tokens` worth of trailing context, so consecutive chunks share a
    tail. Without this, a sentence split across a chunk boundary is retrievable
    from neither side.
    """
    if overlap_tokens <= 0:
        return len(window)

    budget_chars = overlap_tokens * 4
    chars = 0
    for index in range(len(window) - 1, -1, -1):
        chars += len(window[index].word) + 1
        if chars >= budget_chars:
            # Never return 0: that would re-emit the same window forever.
            return max(1, index)
    # Overlap would swallow the whole window; advance by at least one token so
    # the loop in chunk_pages() cannot stall.
    return max(1, len(window) - 1)


def chunk_pages(
    pages: list[PageText],
    *,
    target_tokens: int = 600,
    overlap_tokens: int = 90,
    min_tokens: int = 24,
) -> list[Chunk]:
    """Slide a ~`target_tokens` window over the document with overlap.

    `min_tokens` drops trailing scraps — a 6-word final chunk is noise in the
    similarity index and would only ever surface as a bad citation.
    """
    if overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be smaller than target_tokens")

    tokens = _tokenize(pages)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0
    budget_chars = target_tokens * 4
    # Index one past the last token already covered by an emitted chunk. Used to
    # append only genuinely new words when folding in a tail, so the shared
    # overlap is not duplicated into the text.
    covered_to = 0

    while start < len(tokens):
        chars = 0
        end = start
        while end < len(tokens) and chars < budget_chars:
            chars += len(tokens[end].word) + 1
            end += 1

        window = tokens[start:end]
        content = " ".join(token.word for token in window).strip()
        token_count = estimate_tokens(content)
        is_last = end >= len(tokens)

        if content:
            # Only the *trailing* window can be an undersized scrap — every
            # other window is a full budget's worth by construction. Folding on
            # size alone would collapse the whole document into one chunk
            # whenever target_tokens happened to sit below min_tokens.
            if is_last and chunks and token_count < min_tokens:
                tail = tokens[max(covered_to, start) : end]
                extra = " ".join(token.word for token in tail).strip()
                previous = chunks[-1]
                merged = f"{previous.content} {extra}".strip() if extra else previous.content
                chunks[-1] = Chunk(
                    chunk_index=previous.chunk_index,
                    page_number=previous.page_number,
                    section=previous.section,
                    content=merged,
                    token_count=estimate_tokens(merged),
                )
            else:
                head = window[0]
                chunks.append(
                    Chunk(
                        chunk_index=len(chunks),
                        # Cite where the passage starts, not where it ends.
                        page_number=head.page_number,
                        section=head.section,
                        content=content,
                        token_count=token_count,
                    )
                )
            covered_to = max(covered_to, end)

        if is_last:
            break
        start += _overlap_start(window, overlap_tokens)

    return chunks
