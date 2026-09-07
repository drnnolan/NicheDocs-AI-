"""Prompt construction and grounded answer generation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAIError

from .clients import get_openai
from .config import get_settings
from .errors import UpstreamError

logger = logging.getLogger(__name__)

# Trim very long chunks before they reach the prompt. 600-token chunks are the
# norm, but merged tail chunks can run longer and there is no value in paying
# for 3 KB of a single passage.
MAX_EXCERPT_CHARS = 2400

NOT_FOUND_ANSWER = (
    "I could not find an answer to that in this document. "
    "Try rephrasing your question, or check whether this handbook covers the topic."
)

SYSTEM_PROMPT = """\
You are NicheDocs, an assistant that answers questions about a single \
university student handbook. You are given numbered excerpts from that \
handbook and one question.

Rules, in priority order:

1. Answer ONLY from the excerpts provided. You have no other knowledge of this \
institution. Do not use general knowledge about how universities usually work, \
and do not infer policies that are not written in the excerpts.
2. If the excerpts do not contain enough information to answer, set "found" to \
false and say plainly that the handbook does not cover it. Do not guess, do not \
hedge with a general answer, and do not pad the response with what is typical \
elsewhere. Saying "not in this document" is a correct and valuable answer.
3. If the excerpts DO answer the question, set "found" to true, answer in 1-4 \
sentences of plain language, and list the numbers of every excerpt you actually \
relied on in "citations". Never cite an excerpt you did not use.
4. If the excerpts partially answer the question, answer the part they cover, \
set "found" to true, and state explicitly what the handbook does not say.
5. Quote exact figures, deadlines, and thresholds verbatim from the excerpts. \
Never round or approximate a number that carries a policy meaning.

Respond with a JSON object and nothing else:
{"found": boolean, "answer": string, "citations": [integer, ...]}\
"""


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    found: bool
    cited_indices: set[int]  # 1-based, indexing into the excerpts we supplied


def build_context(matches: list[dict[str, Any]]) -> str:
    """Render retrieved chunks as numbered, page-labelled excerpts."""
    blocks: list[str] = []
    for position, match in enumerate(matches, start=1):
        content = (match.get("content") or "").strip()
        if len(content) > MAX_EXCERPT_CHARS:
            content = content[:MAX_EXCERPT_CHARS].rstrip() + "…"

        label = f"page {match.get('page_number')}"
        section = match.get("section")
        if section:
            label += f", section “{section}”"

        blocks.append(f"[{position}] ({label})\n{content}")
    return "\n\n".join(blocks)


def _parse(raw: str, *, excerpt_count: int) -> GroundedAnswer:
    """Parse the model's JSON, tolerating the ways it can drift."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # JSON mode makes this very unlikely, but a malformed reply should
        # degrade to showing the text rather than 500-ing the request.
        logger.warning("Answer was not valid JSON; falling back to raw text")
        text = raw.strip()
        return GroundedAnswer(
            answer=text or NOT_FOUND_ANSWER, found=bool(text), cited_indices=set()
        )

    if not isinstance(payload, dict):
        return GroundedAnswer(answer=NOT_FOUND_ANSWER, found=False, cited_indices=set())

    answer = str(payload.get("answer") or "").strip()
    found = bool(payload.get("found")) and bool(answer)

    cited: set[int] = set()
    for value in payload.get("citations") or []:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        # Drop hallucinated citation numbers that point outside what we sent.
        if 1 <= index <= excerpt_count:
            cited.add(index)

    if not found:
        return GroundedAnswer(
            answer=answer or NOT_FOUND_ANSWER, found=False, cited_indices=set()
        )
    return GroundedAnswer(answer=answer, found=True, cited_indices=cited)


def generate_answer(*, question: str, matches: list[dict[str, Any]]) -> GroundedAnswer:
    """Ask the model to answer `question` using only `matches`.

    Callers should short-circuit before getting here when retrieval returned
    nothing — there is no point paying for a completion to be told the obvious.
    """
    if not matches:
        return GroundedAnswer(answer=NOT_FOUND_ANSWER, found=False, cited_indices=set())

    settings = get_settings()
    context = build_context(matches)
    user_prompt = (
        f"Handbook excerpts:\n\n{context}\n\n"
        f"---\n\nQuestion: {question.strip()}"
    )

    try:
        completion = get_openai().chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            # Grounded extraction, not creative writing: keep it deterministic.
            temperature=0,
            response_format={"type": "json_object"},
            max_tokens=700,
        )
    except OpenAIError as exc:
        logger.exception("Answer generation failed")
        raise UpstreamError(f"Could not generate an answer: {exc}") from exc

    raw = (completion.choices[0].message.content or "").strip()
    return _parse(raw, excerpt_count=len(matches))
