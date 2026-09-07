# HandbookIQ — Case Study

**A retrieval-augmented Q&A app over university student handbooks, built so that a wrong answer is structurally harder to produce than an honest "I don't know."**

---

## 1. The problem

Every semester, a registrar's office answers the same twenty questions. *What is the attendance minimum? How do I appeal a final grade? When is the last day to withdraw without academic penalty? What happens if I'm caught using AI on an assessment?* All of the answers are already written down, in a 120-page handbook PDF that every student was emailed and none of them read.

The naive fix — paste the handbook into a chatbot — fails in a specific and dangerous way. Ask a general-purpose model about attendance requirements and it will answer, fluently and immediately, with something like *"most institutions require 75–80% attendance."* That is a reasonable statement about universities in general. It is not a statement about *this* handbook, and the student cannot tell the difference, because the model's confidence is identical either way.

In a policy domain, that asymmetry is the whole problem:

- A **correct** answer saves a student a trip to the registrar.
- A **missing** answer costs them that trip. Annoying, recoverable.
- A **plausible wrong** answer makes them miss a withdrawal deadline, or assume a grade appeal window that does not exist. Unrecoverable, and now it is the institution's problem.

So the product requirement is not "answer as many questions as possible." It is **"never produce category three."** Everything else in this project follows from that.

## 2. The approach

### Scope: one document set, not "chat with any PDF"

Constraining the app to student handbooks was a deliberate early decision. It buys three concrete things a generic tool cannot have:

- **A tuned prompt.** The system prompt can state flatly that the model has no other knowledge of the institution — a claim that would be wrong for a general document tool but is exactly right here.
- **Meaningful structure.** Handbooks are heavily sectioned (`4.2 Attendance Policy`, `Appendix B — Fee Schedule`), so heading detection is worth building and citations get much better: *"page 12, section 4.2"* beats *"page 12."*
- **Honest evaluation.** "Does this answer the twenty questions a real student asks?" is a test you can actually run. "Does this work on any PDF?" is not.

### The grounding architecture

Three independent gates stand between a question and a fabricated answer. They are independent on purpose: no single failure should be able to produce a confident lie.

**Gate 1 — the retrieval floor.** The question is embedded and matched against chunks from the selected document only, with a cosine-similarity floor of 0.20. If nothing clears it, the API returns *not found* **without ever calling the LLM**. This gate is the strongest one available, because a model that is never invoked cannot hallucinate. It is also the cheapest and the fastest.

**Gate 2 — the prompt contract.** When passages do clear the floor, they are rendered as numbered, page-labelled excerpts, and the model is told in priority order: answer only from these; if they are insufficient, say so; saying "not in this document" is a correct and valuable answer. That last clause matters more than it looks — without explicit permission to fail, a model will reach for general knowledge to fill the gap. `temperature=0` and JSON mode keep the output deterministic and parseable.

**Gate 3 — citation validation.** The model returns which excerpt numbers it relied on. Any index outside the range actually supplied is discarded. A citation can therefore never point at a passage that does not exist, no matter what the model claims.

The UI reflects all of this: a *not found* response renders as a distinct amber card, visually separated from a real answer, and near-miss passages are still shown but explicitly labelled *"retrieved, but not used."* The user always sees what the search found, not just what the model said about it.

### Chunking for citation accuracy

The page number *is* the product. If it drifts, the app becomes confidently wrong — the exact failure it exists to prevent. So the chunker does not concatenate the document and split the blob, which loses page provenance the moment a chunk crosses a boundary. Instead every word is tagged with its page number and its enclosing heading, and a ~600-token window slides over the *tagged* stream with ~90 tokens of overlap. A chunk that spans pages 12–13 is cited to page 12, where its text begins.

The overlap is not decoration. Without it, a sentence split across a chunk boundary is retrievable from neither side — the single most common silent failure in a naive RAG pipeline.

## 3. Three trade-offs

### The headline: estimated tokens instead of `tiktoken`

**The decision.** Chunk sizes are computed with a four-characters-per-token estimate rather than OpenAI's exact `tiktoken` tokenizer.

**Why.** `tiktoken` downloads its BPE vocabulary from the network on first use and caches it to a temp directory. In a serverless function, that means the first request after a cold start makes an extra network call to a third-party host, into a filesystem that may or may not persist — a failure mode that is intermittent, environment-dependent, and miserable to debug at 2am before a demo.

**What it costs.** The estimate runs about 10% off on English prose, so a "600-token" chunk is really 540–660 tokens.

**Why that is acceptable.** Nothing in this pipeline needs an exact token count. Chunk sizing needs a *consistent* count — the goal is chunks of roughly uniform semantic size, and a consistent 10% bias produces exactly that. The precision would have been real, and entirely unused.

**When I would revisit it.** If chunks were being packed against a hard context-window limit, where a 10% underestimate means a truncated request, exactness would stop being optional.

### Direct-to-storage upload instead of proxying through the API

Vercel Functions reject request bodies over 4.5 MB at the platform edge, before any application code runs. A 20 MB handbook cannot reach the backend as a POST body, full stop. The upload therefore became a three-step handshake: the backend mints a Supabase Storage signed URL, the browser PUTs the bytes directly to Storage, and the backend pulls the file *outbound* (where no limit applies) to index it.

This started as a platform workaround and ended up the better design regardless: bytes take one hop instead of two, the API never buffers a 20 MB body in a 2 GB-memory function, and an abandoned upload leaves a visible `pending` row rather than a half-written request. The cost is a more complex client flow and a `pending` state that has to be modelled honestly. A single-call `POST /upload` was kept for local development and curl, capped at 4 MB with an error message that points at the signed-URL route.

### `pypdf` instead of `pdfplumber`

`pdfplumber` gives per-glyph coordinates and table extraction, and pulls in Pillow and pdfminer.six to do it. Handbooks are prose; the pipeline needs page-scoped text and nothing else. `pypdf` is pure Python, has no native wheels, and keeps the function bundle small. The cost is real: text extracted from multi-column layouts and tables is messier, and fee schedules in particular come out as run-on text. If handbook tables turn out to matter, the extraction layer is one module ([`pdf.py`](../backend/nichedocs/pdf.py)) behind a stable interface, so swapping it is a contained change rather than a rewrite.

## 4. What I would do next

- **Hybrid retrieval.** Pure vector search is weak on exact-term queries — a student searching for "clause 7.3.1" wants lexical matching, not semantic similarity. Postgres full-text search alongside the vector index, fused by reciprocal rank, is the standard fix.
- **An evaluation set.** Twenty real student questions with hand-labelled correct pages, run on every change. Right now "does it work?" is a judgement call; it should be a number, and specifically a number that tracks the false-confident-answer rate, not just accuracy.
- **Background indexing.** A 500-page handbook holds the `/process` request open for minutes. A job queue with UI progress is the right answer at real scale.
- **Citations that open the PDF.** Clicking "page 12" should render page 12 of the source, not just name it. It closes the verification loop the whole product is built around.

## 5. What I learned

The engineering that mattered was not the retrieval — a similarity search over pgvector is a solved problem and took an afternoon. It was **designing for the failure case**: deciding that "not found" is a first-class result with its own visual treatment rather than an error state, that a citation the model invents must be dropped rather than rendered, and that a chunk which crosses a page boundary needs a defensible answer to *which page it belongs to* before any of the rest is trustworthy.

A RAG app is easy to make work on the questions the document answers. The hard part — and the part worth building — is making it behave well on the questions it does not.
