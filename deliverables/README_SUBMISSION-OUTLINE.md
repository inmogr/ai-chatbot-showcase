# README_SUBMISSION Outline

This outline is the skeleton of the `README_SUBMISSION.md` that ships in commit 7: the eight sections the brief mandates, in its order, followed by the provider choice and how to swap it, the assumptions, timeouts, the test notice and known limitations. Every bullet uses decided values or measured numbers; examples use only the real corpus. Items marked UNVERIFIED must be worded as such in the final README. Version 2 applies the round-10 resolutions and the round-11 accuracy changes; the post-review corrections (2026-10-04) are applied in place.

Rules for the final README (post-review):
- It lives at `miniragchatbot/README_SUBMISSION.md`, and every command in it runs from `miniragchatbot/`, the project root (D-76).
- It shows no internal planning labels. The IDs in this outline (E01–E17, U-xx, A-xx, K01–K12, D-xx, O-xx, S-xx, RR-xx) are for traceability only; the README states the number and how it was measured instead (for example "measured: 20 runs, median 1.0014 s" rather than "(E06)").
- §7 and §8 contain exactly one improvement and one tradeoff, as the brief asks.

Sources: `inputs/00-brief.md` ("What to submit"); `knowledge/K09-prd-plan.md` README parts A and B with corrections; `inputs/attach/DECISIONS-REGISTER.md`; `knowledge/K01`, `K03`, `K04`, `K05`, `K08`; `inputs/attach/C07-STATE.md`; `knowledge/K10-consolidation.md` (round-10 resolutions); `knowledge/K11-accuracy.md` (round-11 changes); evidence E01–E06, E09, E10, E15, E17.

---

## 1. How to run the ingestion script

- Run every command from `miniragchatbot/` (the project root: `docs/`, `mint_tokens.py`, `.env.example` and the provided `.gitignore` live there).
- Start Qdrant: `docker run -d --name qdrant -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1` — runs in the background and keeps the index in `./qdrant_data` (already in `.gitignore`).
- `cp .env.example .env` and set `JWT_SECRET` (used by the server and `mint_tokens.py`; ingestion needs neither it nor an LLM key).
- `uv sync --python 3.12` — the project needs Python ≥ 3.11; macOS system `python3` is 3.9.6.
- `uv run python -m scripts.ingest --docs-dir ./docs`
- What it does:
  - checks that Qdrant is reachable before loading any model, and validates the files on disk against the brief's 7-row access table (mismatch, missing or unmapped file → clear error, exit 1);
  - extracts text with pypdfium2; a page whose text layer is empty (`exec/strategic_plan.pdf`) is rendered at 300 dpi and read with RapidOCR 3.9.2 using models bundled in the wheel — no tesseract, no poppler, no manual step;
  - chunks by document structure (§4), embeds with `BAAI/bge-small-en-v1.5`, recreates the collection and writes 42 chunks with deterministic ids and the metadata `department`, `access_level` (int), `source_file`, `page`;
  - prints a summary (files, chunks, time) and exits 0.
- `--docs-dir` overrides `DOCS_DIR` from `.env`; an `EMBEDDING_PROVIDER` other than `sentence-transformers` stops ingestion with a configuration error.
- First run downloads the embedding model automatically (~130 MB; 21.7 s measured) — no manual step, but it needs network; an air-gapped machine needs a pre-warmed Hugging Face cache.
- Re-running is safe: the collection is recreated, so no stale chunks remain.

## 2. How to run the server

- Qdrant running and ingestion done (§1).
- In `.env`: `JWT_SECRET` (required — the server refuses to start without it; no default) and `GROQ_API_KEY`. Shipped defaults: `LLM_PROVIDER=groq`, `GROQ_MODEL=openai/gpt-oss-120b`, `GROQ_EXTRA_PARAMS={"reasoning_effort":"low"}`, `MAX_TOKENS=1500`.
- `uv run python mint_tokens.py` — it always reads the `.env` next to it (`load_dotenv()` searches from the script's own folder upward, not from the working directory); the server reads `.env` from the directory it starts in, so start the server in `miniragchatbot/` and both use the same `JWT_SECRET` (otherwise tokens will not verify).
- `uv run uvicorn app.main:app --reload`
- If port 8000 is taken: `uv run uvicorn app.main:app --port 8001` and type `ws://localhost:8001/ws/chat` into the client's WebSocket URL box (no file change).
- A `JWT_SECRET` shorter than 32 bytes works but makes PyJWT log `InsecureKeyLengthWarning` (measured with PyJWT 2.15.1); use a long random string.
- At startup the server loads its settings, loads the embedding model in a worker thread and checks the collection (exists, 384-dimension vectors, `model_name` equals `EMBEDDING_MODEL`); any failure aborts startup (uvicorn exit code 3). There is no startup call to the LLM.
- Endpoint: `ws://localhost:8000/ws/chat` (the only endpoint).

## 3. How to test

- **Browser:** open `test_client.html` (double-click), paste a token from `mint_tokens.py`, keep `ws://localhost:8000/ws/chat`, click Connect, type a question; tokens appear progressively.
- **Command line:** `uv run python -m scripts.ws_probe --token <jwt> "How many leave days do I get?"` prints every frame with a timestamp, so the streaming cadence is visible (pre-build, D-84).
- **Example exchange** (`emp-001`, department `hr`, level 1):

```text
→ {"type": "auth", "token": "<emp-001 token from mint_tokens.py>"}
← {"type": "auth_success", "user_id": "emp-001", "department": "hr", "level": 1}
→ {"type": "message", "text": "How many leave days do I get?"}
← {"type": "stream", "text": "You are entitled to "}
← {"type": "stream", "text": "22 working days of paid annual leave per calendar year "}
← {"type": "stream", "text": "[leave_policy.pdf, page 1]."}
← {"type": "done"}
```

  The split into frames is illustrative — real deltas are smaller and vary; the answer text comes from the model.
- **Failure examples:** an invalid token → `{"type": "auth_failed", "message": "Invalid or expired token"}`, then close code 1008; a whitespace-only message sent with wscat → `{"type": "error", "message": "Message text must be between 1 and 2000 characters"}` with the connection kept open.
- **Automated tests:** see the test notice below.
- **Manual checklist per user:** `emp-001` gets 22 working days and refusals for performance-review, finance and exec topics; `mgr-002` gets the 10/20/50/15/5 rating distribution; `exec-003` gets the APAC priorities from the scanned plan (USD 45 million, Singapore hub), the 18-company peer group and 10 days of sick leave (hr exception), and a refusal for finance questions; "Who is my manager?" answers John Smith after a ~1 s pause.

## 4. Chunking strategy — size, overlap, why

- **Structural chunks, not fixed windows:** one chunk per numbered section in the six text PDFs (a line matching `^\d+\.\s+[A-Z]` starts a section), one chunk per paragraph in the scanned plan; the document title is prefixed to every chunk.
- **Size:** set by the documents — every section is 35–74 tokens with the bge tokenizer; whole documents are 279–364 tokens; the corpus is ~2,157 tokens; all far below the model's 512-token window (E01).
- **Overlap: 0** — each section is a self-contained rule; overlap would repeat text across the 4 retrieval slots.
- **Fallback:** only a body over 150 bge tokens is split into sentences and packed evenly; 150 sits above every measured section and well inside 512; it never triggers on this corpus.
- **Why not a tutorial number:** a fixed window size and overlap would not come from this corpus and would cut rules mid-sentence.
- **Scanned PDF:** at 300 dpi RapidOCR returned 18 lines, minimum confidence 0.984, matching the transcription word for word (E01). Paragraph gaps are 41–55 px (2.9×–3.9× the 14 px median line gap) while in-paragraph gaps are 0.7×–1.4×, so a 2.0× threshold separates them (E02): title, intro, four priorities, board approval → 6 chunks.
- **Result:** 42 chunks — 6 per document (36 from text, 6 from the scan).
- **Details worth a line:** wrapped lines are joined; the heading pattern needs "number, dot, capital" because wrapped lines start with digits in three files; the fallback's sentence regex would split initials ("John D. Doe") — none occur here, and a test documents it.

## 5. RBAC approach — how, and why at the DB layer

- **Filter inside the Qdrant query** (`query_points`): `department MatchAny [user.department, "hr"]` AND `access_level Range(lte=user.level)`, one `must` clause; payload indexes keyword(`department`) and integer(`access_level`).
- **The `hr` exception** is "hr" added to the allowed departments — the cleanest expression; it keeps the level check, so the manager-only performance review stays hidden from `emp-001`.
- **Why at the DB layer:** the brief requires it; post-filtering would take the top 4 first and then drop chunks (fewer than 4 left), and would hold restricted text in process memory with the risk of it reaching the hosted LLM; with the filter in the query, restricted chunks never leave Qdrant.
- **Claims come only from a verified JWT** (HS256 pinned, required claims, strict integer `level`); the LLM never sees `department` or `level`.
- **Visible chunks:** `emp-001` 12, `mgr-002` 18, `fin-001` (test-only finance user) 24, `exec-003` 30 — tested by counting with the same filter on a seeded collection.
- **Measured (E03):** 0 restricted-file leaks across 24 filtered queries; points with no `department`, no `access_level`, or `access_level "1"` were never returned; a float `1.0` was (numeric comparison), so ingestion stores ints and a test enforces it; filtered query median 1.7 ms.
- **Qdrant runs as a server:** embedded/local mode evaluates filters in Python and blocks the event loop.
- **Executives do not see finance documents** — the consequence of the brief's formula plus its single `hr` exception, not a rule the brief states (§7).
- **Origin:** no Origin check is needed — auth is an in-band JWT, not cookies, so a foreign page gains nothing without a token, and an allow-list rejecting `null` would break the provided `file://` client (verified live, E17).

## 6. Async / parallel approach

- `get_employee_context(user_id)` runs three mock fetches — profile, manager, team, each `asyncio.sleep(1)` — concurrently in an `asyncio.TaskGroup` inside `asyncio.timeout(2.0)`.
- **Measured (E06):** sequential 3.003 s; TaskGroup 1.001 s (20 runs: median 1.0014 s, max 1.0016 s). The test wraps the three fetches in spies and asserts all ran and the call took < 1.35 s.
- **Why TaskGroup, not `gather`:** on a failure plain `gather` raises but leaves the other fetches running; `gather(return_exceptions=True)` returns partial results; TaskGroup cancels the siblings and raises, which becomes one error frame "Failed to execute employee lookup."
- **Tool security:** before calling the tool, the orchestrator checks the model's `user_id` against the JWT `sub`. On a mismatch the tool is not called; the model receives the result "Access denied: caller may only query their own context." and explains the refusal in its answer (tradeoff in §8).
- **No blocking elsewhere:** the embedding model load and each `encode` run in `asyncio.to_thread`; Qdrant and the LLM use async clients; JWT decoding and logging take microseconds. A unit test patches `asyncio.to_thread` in the embedder module and asserts `encode` is dispatched through it.
- **Turn timeout:** 30 s, owned by the WebSocket consumer, which iterates the turn generator inside `contextlib.aclosing` (a deadline held inside a generator across yields caused spurious cancellations — E15).

## 7. One thing I would improve

- Department inheritance / a multi-department access policy so executives can read finance. Today `exec-003` sees 30 chunks (hr + exec) and none from finance, because the brief's formula plus its single `hr` exception leaves finance out; that consequence was kept rather than changed silently.

## 8. One tradeoff and why

- **k = 4 with no similarity threshold.** Top-1 scores overlap: answerable questions scored 0.556–0.869, questions with no allowed answer 0.412–0.590 (E03), so any threshold would refuse some valid questions or pass some invalid ones. Instead the model always gets 4 authorised chunks and the prompt enforces the fixed refusal "I cannot find that information in the authorised company policies."
- **Cost:** off-topic questions still send 4 authorised chunks to the hosted LLM, and refusal depends on the model following the prompt (checked by a live test).

## LLM provider — choice and why

- **Default:** Groq with `openai/gpt-oss-120b`, `GROQ_EXTRA_PARAMS={"reasoning_effort":"low"}`, `max_tokens` 1500.
- **Why:** on Groq's free plan (30 RPM, 1K RPD, 8K TPM, 200K TPD); tool use documented; the model's deliberation is documented to arrive in a separate `reasoning` field, so the content-only stream should not show it — not live-verified (U-02) (E05, E09).
- **Data:** say only that Groq "does not retain customer data for inference by default (up to 30 days for reliability/abuse monitoring)" (E05). Its docs do not state training use, so make no claim about it (U-08, UNVERIFIED). Do not claim zero retention.
- **Why not the template defaults:** `llama-3.3-70b-versatile` is tagged Enterprise and is not in the free-plan table; `gemini-2.0-flash` is shut down; OpenRouter's `meta-llama/llama-3.3-70b-instruct:free` is not listed (E05).
- **Not live-verified:** Groq documents tool calling and streaming, but not their combination (E05); it was not run with a real key during planning (UNVERIFIED, U-01).
- **Confidentiality:** OCR and embeddings run locally; whole documents never leave the machine. Each turn sends up to 4 role-filtered excerpts to the hosted provider — for executives this can include "Executive Restricted" strategic-plan text. `LLM_PROVIDER=ollama` keeps inference local.

## How to swap the provider

- One OpenAI-compatible adapter behind a small port; no code change. Set `LLM_PROVIDER` and that provider's variables from `.env.example`; startup fails fast if the selected provider lacks its key (Ollama needs none) or model.

| `LLM_PROVIDER` | Variables | Base URL | Caveat |
|---|---|---|---|
| `groq` (default) | `GROQ_API_KEY`, `GROQ_MODEL` | `https://api.groq.com/openai/v1` | — |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | OpenAI-compatible endpoint is beta; free-tier content is used to improve Google's products (E05) |
| `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | `https://openrouter.ai/api/v1` | pick a tool-capable model |
| `ollama` | `OLLAMA_BASE_URL` (`/v1` appended), `OLLAMA_MODEL` | `${OLLAMA_BASE_URL}/v1` | fully local |
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` | `https://api.openai.com/v1` | paid |
| `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | `https://api.anthropic.com/v1/` | Anthropic: the layer "is not considered a long-term or production-ready solution for most use cases"; `tool_choice` support there is UNVERIFIED (E10) |

- `GROQ_EXTRA_PARAMS` is read only when `LLM_PROVIDER=groq`, so switching provider never sends `reasoning_effort` elsewhere and needs no cleanup. If `GROQ_MODEL` is changed to a Groq model without documented `reasoning_effort` support, clear `GROQ_EXTRA_PARAMS` (UNVERIFIED, U-07).
- Tools together with streaming are UNVERIFIED for Gemini, Ollama and OpenRouter (E05).
- Changing `EMBEDDING_MODEL` requires re-running ingestion; the server refuses to start if the stored `model_name` differs. Other embedding providers: see Known limitations.

## Assumptions (each tied to a brief line — PRD §4)

- The `hr` exception waives the department check only; the level still applies (A-01).
- Executives get no finance access — a consequence of the brief's formula plus its single `hr` exception, not a rule the brief states (A-02).
- The tool's `"grade": "Senior"` does not map to the travel policy's numeric grades; the model says so instead of inventing a mapping (A-03); leave is 22 working days regardless of grade (A-04).
- Pages are 1-based and read from the PDF (A-05).
- Ingestion is a CLI script (A-06); OCR runs locally with RapidOCR (A-07) and only when a page has no text layer (A-08).
- Turns on one connection run one at a time; extra messages queue (A-09).
- The tool's `user_id` is checked against the JWT `sub` before the tool is called; a mismatch gets an in-dialogue refusal (A-10); retrieval always runs before generation (A-11).
- `access_level` is stored as an int; JWT `level` is a strict integer ≥ 1 (A-12, A-23); `sub`, `exp`, `department`, `level` are required and HS256 is pinned (A-13); any department string is accepted — unknown departments see only hr content (A-23).
- The first frame must be a valid auth frame, within 10 s (A-14, A-24).
- Messages are 1–2,000 characters after trimming (A-15).
- Restricted documents are treated as non-existent (A-16); every message goes through retrieval (A-17); the model cites inline (A-18); the LLM sees only `sub` (A-19).
- Memory is optional (stretch S-03, built last only if time remains); the core pipeline is stateless; retrieval always uses the current question only; if memory is built, the last 3 question/answer pairs go to the LLM (A-20).
- The automatic first-run model download is not a manual step but needs network (A-21).
- Pluggability is one OpenAI-compatible adapter selected by configuration (A-22).
- The server starts in `miniragchatbot/`, so it and `mint_tokens.py` share `miniragchatbot/.env` (A-25).
- `mint_tokens.py` and `test_client.html` are treated as read-only — our assumption; the brief does not forbid editing them (A-26).
- `generate_pdfs.py` is listed in the brief but absent from the repository; the brief says to ignore it.

## Limits and timeouts

- Auth window 10 s (then `auth_failed`, close 1008); first response chunk within 8 s of sending the request (no separate connect timeout); tool 2 s; whole turn 30 s.
- Message text 1–2,000 characters; k = 4 chunks; `max_tokens` 1500; history 3 question/answer pairs only if the optional memory commit is built.
- Errors are fixed user-facing messages from a consolidated catalog — 10 turn-error strings plus the 4 `auth_failed` texts; the connection stays open after a turn error; nothing is retried.

## Test notice

- `uv run pytest` runs the whole offline suite — unit and protocol tests, the JWT matrix (10 cases), progressive streaming with a delayed fake LLM, the `asyncio.to_thread` dispatch test, adapter parsing of synthetic stream chunks, `aclosing` cleanup — with no Docker, no model download and no API key (markers `model`, `qdrant`, `live_llm` are excluded by default).
- `uv run pytest -m qdrant` — RBAC counts 12 / 18 / 24 / 30 on a seeded collection (needs Docker Qdrant).
- `uv run pytest -m model` — ingestion integrity: 42 chunks, 6 from the scan (downloads the embedding model on first run).
- `uv run pytest -m "qdrant and model"` — semantic differential pairs and end-to-end ingestion.
- `GROQ_API_KEY=… uv run pytest -m live_llm` — the real model calls the tool, real streaming cadence, exact refusal wording.
- Coverage: `uv run pytest -m "not live_llm" --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80` (≥ 80 % branch on `app/`; needs Docker Qdrant and the model). The offline default suite has no coverage gate.

## Known limitations

- Groq documents tool calling and streaming separately; using them together was not live-verified during planning (U-01).
- Embeddings are swappable at the interface, not yet by configuration. The brief asks to keep the LLM and embeddings "pluggable behind a thin interface"; only the local `sentence-transformers` adapter is implemented behind the embedder ports. Another provider — for example the template's commented `EMBEDDING_PROVIDER=openai` — means one new adapter class plus re-running ingestion; until then any other value stops startup and ingestion with a configuration error.
- Executives cannot see finance documents — the consequence of the brief's formula plus its single `hr` exception (§7).
- No similarity threshold: off-topic questions still send 4 authorised chunks to the hosted LLM; refusal is prompt-driven.
- At most one tool round (two LLM passes) per turn.
- Conversation memory is optional (stretch S-03, built last only if time remains); without it every question is answered on its own; with it, history goes to the LLM only, never to retrieval.
- Citations come from the model; the manual checklist checks the expected citation for each answer row. They are not verified at runtime, and there is no automated citation eval (pre-build, D-80).
- The OCR paragraph threshold (2.0×) was measured on one machine; drift is caught by the ingestion integrity test.
- The first run needs network to download the embedding model.
- Up to 4 role-filtered excerpts per turn reach the hosted provider (use `LLM_PROVIDER=ollama` to keep inference local).
- A client disconnect during retrieval or the tool is noticed at the next send.
- If any core item is still unverified at submission (e.g. U-01), state what was tried and the next step (brief ground rule).
