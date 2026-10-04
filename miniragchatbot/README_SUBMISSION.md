# Mini RAG Chatbot Backend — Submission

A FastAPI WebSocket chatbot that answers questions about the Acme policy PDFs with retrieval-augmented generation, and enforces role-based access inside the Qdrant query. Stack: Python 3.12 (uv), FastAPI + uvicorn, Qdrant 1.19 in Docker, `BAAI/bge-small-en-v1.5` embeddings and RapidOCR (both local), and Groq `openai/gpt-oss-120b` through the OpenAI-compatible SDK.

Every command below runs from `miniragchatbot/` — the folder that holds `docs/`, `mint_tokens.py` and `.env.example`.

### Quick start

```bash
docker run -d --name qdrant -p 127.0.0.1:6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1
cp .env.example .env                      # set JWT_SECRET and GROQ_API_KEY
uv sync --python 3.12
uv run python -m scripts.ingest --docs-dir ./docs
uv run uvicorn app.main:app --reload
uv run python mint_tokens.py              # paste a token into test_client.html
```

Without uv: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt` (the exact, hash-pinned versions of `uv.lock`; pip verifies every download), then use `.venv/bin/python` and `.venv/bin/uvicorn` in place of `uv run`. uv is the path that was tested.

## 1. How to run the ingestion script

1. Start Qdrant: `docker run -d --name qdrant -p 127.0.0.1:6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1`. It runs in the background, keeps the index in `./qdrant_data` (git-ignored) and listens on localhost only — this Qdrant has no authentication, so it must not be reachable from the network.
2. `cp .env.example .env` and set `JWT_SECRET`. Ingestion itself needs neither the secret nor an LLM key.
3. `uv sync --python 3.12` — Python ≥ 3.11 is required; the macOS system `python3` is 3.9.
4. `uv run python -m scripts.ingest --docs-dir ./docs`

It prints `ingested 7 files, 42 chunks into 'acme_policies' in 3.1 s` (measured with the model already cached) and exits with code 0.

What it does:

- Checks that Qdrant is reachable before loading any model, and checks the files on disk against the brief's 7-row access table: a missing, unmapped or misplaced PDF stops it with a clear message and exit code 1. Non-PDF files such as `.DS_Store` are ignored.
- Extracts text with pypdfium2. A page with no text layer (`exec/strategic_plan.pdf`) is rendered at 300 dpi and read with RapidOCR, whose ONNX models ship inside the wheel — no tesseract, no poppler, no manual step.
- Chunks by document structure (section 4), embeds with `BAAI/bge-small-en-v1.5`, recreates the collection and writes 42 points. Point ids are deterministic (uuid5 of file, page and chunk index); the payload holds `department`, `access_level` (int), `source_file`, `page` (1-based), `chunk_index`, `text` and `model_name`. Keyword and integer payload indexes are created on `department` and `access_level`.
- `--docs-dir` overrides `DOCS_DIR` from `.env`. An `EMBEDDING_PROVIDER` other than `sentence-transformers` exits with code 1 and a configuration error.
- Re-running is safe: the collection is recreated, so no stale chunks remain.
- The first run downloads the embedding model (~130 MB) automatically; that needs network once.
- RapidOCR prints about nine INFO lines naming its bundled model files while it starts. They are harmless.

## 2. How to run the server

1. Qdrant is running and ingestion is done (section 1).
2. In `.env`, set `JWT_SECRET` (required: the server refuses to start without it) and `GROQ_API_KEY` (a free key from https://console.groq.com). Shipped defaults: `LLM_PROVIDER=groq`, `GROQ_MODEL=openai/gpt-oss-120b`, `GROQ_EXTRA_PARAMS={"reasoning_effort":"low"}`, `MAX_TOKENS=1500`.
3. `uv run uvicorn app.main:app --reload`
4. The endpoint is `ws://localhost:8000/ws/chat` — the only route. The OpenAPI and docs pages are disabled because there is no HTTP API.

Notes:

- Start the server in `miniragchatbot/`. It reads `.env` from its working directory, and `mint_tokens.py` reads the `.env` next to itself, so both use the same `JWT_SECRET`; otherwise tokens will not verify.
- Port 8000 taken? Run `uv run uvicorn app.main:app --port 8001` and type `ws://localhost:8001/ws/chat` into the client's URL box (no file change).
- At startup the settings are validated (a missing secret or provider key stops the server, and the error never echoes a value), the embedding model loads in a worker thread, and the collection is checked: it exists, holds 384-dimension vectors and was built with `EMBEDDING_MODEL`. Any failure aborts startup with a clear log line, for example `StartupCheckError: collection 'acme_policies' not found: run uv run python -m scripts.ingest --docs-dir ./docs`. Plain uvicorn then exits with code 3; under `--reload` the reloader process stays up with nothing listening (it waits for a file change), so read the log. There is no startup call to the LLM.
- Logs carry metadata only — user id, error class, upstream status and request id, timings — never message text, answer text, excerpts or tokens.
- Beyond localhost, start it as `uv run uvicorn app.main:app --ws-max-size 65536 --ws-per-message-deflate false`. uvicorn's defaults accept 16 MiB compressed frames and do not bound how many frames queue on a connection, so a client could make the server buffer a lot of memory before it has even authenticated; the largest legitimate frame here is about 24 KB.
- `mint_tokens.py` (as delivered) prints `JWT_SECRET` along with the tokens — do not share its output.
- A `JWT_SECRET` shorter than 32 bytes works, but PyJWT then logs `InsecureKeyLengthWarning`; use a long random string. The startup line "You are sending unauthenticated requests to the HF Hub" comes from the model loader checking for updates and is harmless.

## 3. How to test

**Browser (the evaluation client).**

1. `uv run python mint_tokens.py` prints three tokens (`emp-001`, `mgr-002`, `exec-003`).
2. Double-click `test_client.html`, paste a token, keep `ws://localhost:8000/ws/chat`, click Connect and ask a question. Tokens appear progressively, and the cursor clears on `done`. Groq generates several hundred tokens per second, so a short answer can arrive within milliseconds as dozens of `stream` frames — `scripts.ws_probe` (below) shows each frame and its time.
3. `mint_tokens.py` has no finance user. `uv run python -m scripts.generate_test_tokens` prints a token for the test-only user `fin-001` (finance, level 1), signed with the same secret; unlike `mint_tokens.py` it never prints the secret.

**Command line.** `uv run python -m scripts.ws_probe --token <jwt> "How many leave days do I get?" "Who is my manager?"` prints every frame with a timestamp, so the streaming cadence is visible. `--url` selects another port; `--origin null` mimics the `file://` client.

**Example exchange** (`emp-001`; the split into frames is illustrative — real deltas are smaller and the wording is the model's):

```text
→ {"type": "auth", "token": "<emp-001 token>"}
← {"type": "auth_success", "user_id": "emp-001", "department": "hr", "level": 1}
→ {"type": "message", "text": "How many leave days do I get?"}
← {"type": "stream", "text": "You are entitled to "}
← {"type": "stream", "text": "22 working days of paid annual leave per calendar year "}
← {"type": "stream", "text": "[leave_policy.pdf, page 1]."}
← {"type": "done"}
```

**Failures.**

- An invalid or expired token → `{"type": "auth_failed", "message": "Invalid or expired token"}`, then close code 1008.
- A whitespace-only message (e.g. from wscat) → `{"type": "error", "message": "Message text must be between 1 and 2000 characters"}`; the connection stays open.
- An LLM or tool failure → one `error` frame with a fixed message (see Limits and timeouts), no `done`, and the connection stays open.

**What to expect per user.** The fixed refusal is "I cannot find that information in the authorised company policies." Every row below, plus the behaviour checks (whitespace sends nothing, an invalid token closes with 1008, a second message sent mid-answer gets its own answer in order), passed live on 2026-10-04 with Groq and the provided client. Questions about your own profile, manager, team or grade — and often about your own leave — make the model call the employee lookup first, a ~1 s pause.

| User | Question | Expected |
|---|---|---|
| `emp-001` | How many leave days do I get? | 22 working days, citing `[leave_policy.pdf, page 1]` |
| `emp-001` | What are the rating distributions for performance reviews? | the fixed refusal (a manager-only document) |
| `emp-001` | Who is my manager? | a ~1 s pause (the tool), then John Smith |
| `emp-001` | How much leave do I have given my grade? | a ~1 s pause, "You are a Senior employee", 22 working days, which do not depend on grade |
| `mgr-002` | What is the expected distribution across ratings in performance reviews? | 10 / 20 / 50 / 15 / 5 |
| `exec-003` | What are the strategic priorities for APAC expansion? | doubling APAC revenue by the end of 2027, a Singapore hub, about USD 45 million — read from the scanned PDF |
| `exec-003` | How many days of paid sick leave do employees get? | 10 days (the hr exception) |
| `exec-003` | What expenses require Finance Partner pre-approval? | the fixed refusal (no finance access) |
| `fin-001` | What is the nightly rate cap for hotels? | USD 250 in high-cost cities, USD 180 elsewhere |

**Automated tests:** see the Test notice below.

## 4. Chunking strategy — size, overlap, why

- **Structural chunks, not fixed windows.** One chunk per numbered section in the six text PDFs (a line matching `^\d+\.\s+[A-Z]` starts a section) and one chunk per paragraph in the scanned plan. The document title is prefixed to every chunk, so each chunk names its policy.
- **Size comes from the documents.** Measured on the stored index, each chunk is 39–83 bge tokens with its title, a whole document is 308–417 tokens and the corpus is about 2,440 — far below the model's 512-token window, so nothing is truncated.
- **Overlap: 0.** Each section is a self-contained rule. Overlap would repeat text across the 4 retrieval slots without adding context a section lacks.
- **Fallback.** Only a body over 150 bge tokens is split into sentences and packed evenly. 150 sits above every section here and well inside 512: it never triggers on this corpus but protects a longer document.
- **Why not a tutorial number.** A fixed 500/50 window would not come from this corpus; it would cut rules mid-sentence and mix neighbouring sections in one vector.
- **The scanned PDF.** At 300 dpi RapidOCR reads 18 lines (minimum confidence 0.984, mean 0.993, matching a manual transcription). Lines are grouped by vertical gaps: the median line gap is 14.1 px; paragraph gaps are 2.9–3.9× the median and in-paragraph gaps 0.8–1.4×, so a 2.0× threshold separates them. The title line is prefixed to the six paragraphs (intro, four priorities, board approval) → 6 chunks.
- **Result:** 42 chunks, 6 per document.
- **Details.** Wrapped lines are joined. The heading pattern needs "number, dot, space, capital" because wrapped lines in three files start with digits. The fallback's sentence regex would split initials ("John D. Doe"); none occur here, and a test documents it.

## 5. RBAC approach — how, and why at the DB layer

- **The filter runs inside the Qdrant query** (`query_points`) as one `must` clause: `department MatchAny [user.department, "hr"]` AND `access_level Range(lte=user.level)`, backed by a keyword index on `department` and an integer index on `access_level`.
- **The hr exception** is "hr" added to the allowed departments. It waives only the department condition — the level check still applies, so `emp-001` (hr, level 1) never sees the manager-only performance review.
- **Why at the DB layer.** The brief requires it, and post-filtering is wrong twice over: Qdrant would return the top 4 first and Python would then drop some, leaving fewer than 4 relevant chunks; and restricted text would sit in process memory, one bug away from the hosted LLM. With the filter in the query, restricted chunks never leave Qdrant. The reader never drops points in Python.
- **Claims come only from the verified JWT:** HS256 pinned; `sub`, `exp`, `department` and `level` required; `level` a strict integer ≥ 1 (`"1"`, `true` and `1.0` are rejected); `exp` checked with a 10 s leeway. The LLM never sees `department` or `level` — only the user id.
- **Measured on the real index:** `emp-001` sees 12 chunks, `mgr-002` 18, `fin-001` 24 and `exec-003` 30 (the same counts are asserted by tests on a seeded collection), and a 4-user × 4-question retrieval run returned no restricted file.
- **Stored types matter.** During design an `access_level` stored as the string `"1"` never matched `Range`, while a float `1.0` did (numeric comparison); ingestion writes ints and a test enforces it.
- **Qdrant runs as a server:** its embedded local mode evaluates filters in Python and would block the event loop.
- **No Origin check.** Auth is an in-band JWT, not a cookie, so a foreign page gains nothing without a token — and an allow-list that rejects `null` would break the provided `file://` client.

## 6. Async / parallel approach

- `get_employee_context(user_id)` runs the three mock fetches — profile, manager, team, each `asyncio.sleep(1)` — concurrently in an `asyncio.TaskGroup` inside `asyncio.timeout(2.0)`.
- **Measured** with the real service: 1.001–1.002 s per call, against 3.004 s when the fetches are awaited one after another. The unit test spies on the three fetches, asserts that all of them started, and asserts that the call took under 1.35 s.
- **Why TaskGroup, not `gather`.** When one fetch fails, plain `gather` raises but leaves the other fetches running, and `gather(return_exceptions=True)` hands back partial results. TaskGroup cancels the siblings and raises, which becomes one error frame: "Failed to execute employee lookup." A test proves the siblings were cancelled.
- **Tool security.** Before calling the tool, the orchestrator compares the model's `user_id` argument with the JWT `sub`. On a mismatch the tool is not called; the model receives "Access denied: caller may only query their own context." and explains the refusal (tradeoff below). Only the first tool call of a turn runs, its arguments are validated by a Pydantic model, and a turn has at most one tool round (two LLM passes).
- **No blocking calls elsewhere.** The embedding model load and every `encode` run in `asyncio.to_thread`; Qdrant and the LLM use async clients; JWT decoding takes microseconds, and tokens over 4,096 characters are rejected before decoding. A unit test patches `asyncio.to_thread` in the embedder and asserts `encode` goes through it.
- **Streaming.** Each text delta from the LLM is forwarded as a `stream` frame the moment it arrives; nothing is buffered.
- **Turn timeout.** 30 s, owned by the WebSocket handler, which consumes the turn inside `contextlib.aclosing`: a timed-out or abandoned turn closes the upstream LLM stream before the error frame is sent. No deadline is held inside a generator across `yield`s — during design that caused spurious cancellations.

## 7. One thing I would improve

Department inheritance — an access policy with more than one department per role, so executives can read finance. Today `exec-003` sees 30 chunks (hr + exec) and none from finance, because the brief's formula plus its single hr exception leaves finance out. I kept that consequence rather than change the rule silently. With more time I would move the allowed departments per role into configuration, so the filter stays one `MatchAny` and a test pins each role's visible count.

## 8. One tradeoff and why

**k = 4 with no similarity threshold.** Top-1 similarity scores overlap: during design, answerable questions scored 0.556–0.869 and questions with no allowed answer 0.412–0.590, so any threshold would either refuse valid questions or pass invalid ones. Instead the model always gets the 4 best authorised chunks and the prompt enforces the fixed refusal. The cost: an off-topic question still sends 4 authorised excerpts to the hosted LLM, and the refusal depends on the model following the prompt (checked by a live test).

## LLM provider — choice and why

- **Default:** Groq with `openai/gpt-oss-120b`, `GROQ_EXTRA_PARAMS={"reasoning_effort":"low"}` and `max_tokens` 1500.
- **Why.** The model is on Groq's free plan (30 requests per minute, 1,000 per day, 8,000 tokens per minute, 200,000 per day); tool use is documented for it; and its deliberation is documented to arrive in a separate `reasoning` field, so the content-only stream does not show it. The template's alternatives fell away: `llama-3.3-70b-versatile` is not in Groq's free-plan table, `gemini-2.0-flash` has been shut down, and OpenRouter's `meta-llama/llama-3.3-70b-instruct:free` is no longer listed.
- **Data.** Groq says it "does not retain customer data for inference by default (up to 30 days for reliability/abuse monitoring)". The Groq documentation read for this project says nothing either way about training use, so this README makes no claim about it.
- **Confidentiality.** OCR and embeddings run locally, so whole documents never leave the machine. Each turn sends up to 4 role-filtered excerpts to the hosted provider — for an executive this can include strategic-plan text. `LLM_PROVIDER=ollama` keeps inference local.
- **Verification status.** Verified live on 2026-10-04 with a free Groq key: real token streaming (79 deltas for a 40-line answer; a policy answer arrives as 30–90 `stream` frames), the model calling the tool on its own (~1 s pause, then John Smith or the grade Senior), the exact refusal for restricted and off-topic questions, and the full browser checklist with `test_client.html`. The error path was also exercised against the real endpoint (an invalid key gives "System configuration error. Please contact support." and the connection stays open).

## How to swap the provider

One OpenAI-compatible adapter sits behind a small `LLMPort` interface, so swapping needs no code change: set `LLM_PROVIDER` and that provider's variables (all listed in `.env.example`). Startup fails fast if the chosen provider lacks its key (Ollama needs none) or its model.

| `LLM_PROVIDER` | Variables | Base URL | Caveat |
|---|---|---|---|
| `groq` (default) | `GROQ_API_KEY`, `GROQ_MODEL` | `https://api.groq.com/openai/v1` | — |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | the OpenAI-compatible endpoint is beta; free-tier content may be used to improve Google's products |
| `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | `https://openrouter.ai/api/v1` | pick a tool-capable model |
| `ollama` | `OLLAMA_BASE_URL` (`/v1` is appended), `OLLAMA_MODEL` | `${OLLAMA_BASE_URL}/v1` | fully local |
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` | `https://api.openai.com/v1` | paid |
| `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | `https://api.anthropic.com/v1/` | Anthropic describes its OpenAI-compatibility layer as not meant for long-term production use; `tool_choice` support there was not verified |

- `GROQ_EXTRA_PARAMS` is sent only when `LLM_PROVIDER=groq`, so switching providers never sends `reasoning_effort` elsewhere. If `GROQ_MODEL` is changed to a Groq model without documented `reasoning_effort` support, clear `GROQ_EXTRA_PARAMS`.
- Tools combined with streaming were not verified for Gemini, Ollama or OpenRouter.
- Embeddings: changing `EMBEDDING_MODEL` requires re-running ingestion; the server refuses to start if the stored `model_name` differs. Only the local sentence-transformers provider is implemented (see Known limitations).

## Assumptions

Each one interprets a line of the brief.

- The hr exception ("any user can access hr content") waives the department check only; the level check still applies.
- Executives get no finance access — the consequence of the brief's formula plus its single hr exception, not a rule the brief states.
- The tool's `"grade": "Senior"` does not map to the travel policy's numeric grades; the model says so instead of inventing a mapping. Annual leave is 22 working days regardless of grade.
- Pages are 1-based and read from the PDF (every document has one page).
- Ingestion is a CLI script (the brief allows "a script or endpoint"). OCR runs locally with RapidOCR, and only on pages without a text layer.
- A connection runs one turn at a time; messages sent meanwhile queue and are answered in order.
- The tool's `user_id` is checked against the JWT `sub` before the tool runs; a mismatch gets an in-dialogue refusal. Retrieval always runs before generation.
- `access_level` is stored as an int; the JWT `level` is a strict integer ≥ 1; `sub`, `exp`, `department` and `level` are required and HS256 is pinned. Any department string is accepted — an unknown department sees hr content only.
- The first frame must be a valid auth frame and arrive within 10 s.
- Message text is 1–2,000 characters after trimming.
- Restricted documents are treated as non-existent: the user gets the same fixed refusal as for a question no policy covers, so hidden documents cannot be probed.
- No conversation memory (an optional stretch): every question is answered on its own, and retrieval uses the current question only.
- The automatic first-run model download is not a manual step, but it needs network.
- The server starts in `miniragchatbot/`, so it and `mint_tokens.py` share `miniragchatbot/.env`.
- `mint_tokens.py` and `test_client.html` are left as delivered (the brief does not forbid editing them); the `fin-001` token comes from a separate helper.
- `generate_pdfs.py` is listed in the brief but absent from the repository; the brief says to ignore it.

## Limits and timeouts

- Auth: the first frame must arrive within 10 s, otherwise `auth_failed` and close 1008. Tokens longer than 4,096 characters are rejected before decoding; `exp` is checked with a 10 s leeway.
- LLM: the first chunk of any kind must arrive within 8 s of the request (this deadline covers connecting; the OpenAI SDK's own 5 s connect timeout also applies); `max_tokens` 1500; no retries (the SDK's own retries are disabled), so a failure surfaces once.
- Tool: 2 s for the three parallel fetches. Whole turn: 30 s.
- Retrieval: k = 4. Message text: 1–2,000 characters.
- Errors are fixed messages: 4 `auth_failed` texts (each followed by close 1008) and 10 turn-error texts (one `error` frame, no `done`, connection kept open):

| Message | When |
|---|---|
| Invalid message structure | a frame after auth that is not JSON, has a wrong or missing field, or is a second auth frame |
| Message text must be between 1 and 2000 characters | empty after trimming, or too long |
| Knowledge base search temporarily unavailable | the embedding or the Qdrant query failed |
| Failed to execute employee lookup. | the tool failed or timed out, or the model requested it with bad arguments |
| System is busy due to high demand. Please try again shortly. | HTTP 429 |
| System configuration error. Please contact support. | HTTP 400, 401, 402, 403 or 404 — a bad request, a bad key, no credits, no access or an unknown model; retrying cannot help |
| Response generation timed out. Please try again. | no first chunk within 8 s, or the turn exceeded 30 s |
| The answer was cut short. Please ask a narrower question. | the model hit `max_tokens` |
| AI service temporarily unavailable. Please try again. | HTTP 5xx or another unexpected HTTP status, connection error, a stream that drops or ends without a finish reason, an empty answer (including a second pass that returns a tool call instead of text), a content filter |
| Something went wrong. Please try again. | anything else (the traceback is logged; the detail is never sent) |

## Test notice

- `uv run pytest` runs the offline suite — unit and protocol tests, the JWT matrix, the RBAC filter counts on an in-memory Qdrant, progressive streaming with a delayed fake LLM, the error catalog, the turn timeout, disconnect cleanup, the `asyncio.to_thread` dispatch test, adapter parsing of synthetic stream chunks — with no Docker, no model download and no API key. One test proves this by re-running the suite with an empty model cache, the Hugging Face offline switches and a dead network proxy.
- `uv run pytest -m "not live_llm"` adds the integration tests: RBAC counts on a seeded Qdrant collection, OCR and the 42-chunk integrity check on the real PDFs, and the ingestion CLI end to end. It needs Docker Qdrant and downloads the embedding model once.
- `uv run pytest -m live_llm` (with `GROQ_API_KEY` in `.env`) runs the real-model checks: streaming cadence, the model calling the tool, and the exact refusal wording.
- Coverage: `uv run pytest -m "not live_llm" --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80`.
- Static checks: `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy app scripts` (strict).
- Secrets: `uv run python -m scripts.scan_secrets` scans every commit on every branch and the staged changes for keys, tokens, private keys, committed `.env` files (any `.env.*` except the template) and the exact values in the local `.env`.

## Known limitations

- Embeddings are swappable at the interface, not yet by configuration: only the local sentence-transformers adapter exists behind the embedder ports. Another provider (for example the template's commented `EMBEDDING_PROVIDER=openai`) means one new adapter class plus re-running ingestion; until then any other value stops startup and ingestion with a configuration error.
- Executives cannot see finance documents (section 7).
- No similarity threshold: off-topic questions still send 4 authorised excerpts to the hosted LLM, and the refusal is prompt-driven (section 8).
- At most one tool round per turn, and only the first tool call of a turn runs.
- No conversation memory: each question is answered on its own.
- Citations come from the model and are not verified at runtime; the live checklist (section 3) checked the expected citation for each answer.
- Prompt injection is mitigated, not solved: excerpt text and questions are escaped so they cannot forge excerpt blocks, and the prompt treats excerpts as data, but text inside a retrieved document can still steer the model.
- Questions about your own leave may trigger the employee lookup although leave does not depend on grade (about 1 s extra).
- The OCR paragraph threshold (2.0×) was measured on one machine; drift would show in the ingestion integrity test (42 chunks, 6 from the scan).
- The token is checked once, at connect: a connection opened before `exp` stays authorised until it closes (the protocol has no re-auth frame).
- Any `JWT_SECRET` is accepted, as the brief allows "any string you like"; PyJWT warns below 32 bytes.
- No per-user rate or connection limit; an authenticated idle connection stays open until either side closes it (uvicorn's 20 s pings detect dead peers).
- A client that stops reading while frames are pending can hold its own connection's handler — including the error reply after the 30 s deadline — until uvicorn's keepalive closes the connection. Other connections are unaffected.
- On shutdown (Ctrl+C) uvicorn waits for open connections: a turn in progress ends at its next send or at the 30 s deadline, then the lifespan closes the Qdrant and LLM clients.
- A client disconnect during retrieval or the tool is noticed at the next send.
- RapidOCR's INFO lines during ingestion and the Hugging Face notice at server start are noise, not errors.
- The embedding model and tokenizer are downloaded by name from Hugging Face; the startup check compares the model name, not the weights (pinning a revision would make this reproducible).
- With `--log-level debug`, the websockets library logs raw frames, message text included — keep the default log level.

## Project layout

```text
app/
  domain/      models, events, errors, prompt, orchestrator, ports — no I/O libraries
  adapters/    llm (OpenAI-compatible), embedder, vector_store (Qdrant reader/writer), employee_tool
  transport/   websocket: frames, auth, routes
  ingestion/   extractor (pypdfium2 + RapidOCR), chunker, pipeline
  main.py      the server's composition root
scripts/       ingest, ws_probe, generate_test_tokens, scan_secrets
tests/         offline, integration (qdrant, model) and live suites
```

Ports and adapters: the domain imports no I/O library, and only `app/main.py` and `scripts/ingest.py` construct concrete adapters — a test enforces both. The commit history has one commit per vertical slice (skeleton, LLM streaming, ingestion, RBAC retrieval, tool, resilience, docs) plus review-fix commits.

**Packaging.** Hand in tracked files only: `git archive --format=zip -o submission.zip HEAD` from the repository root. Never zip the working folder — it holds `.env` (secrets), `.venv` (~1.3 GB) and `qdrant_data/`. The design documents (requirements, architecture, decisions, test plan, and a build tracker with every review finding) are in `deliverables/` next to this folder; code comments cite their decision and review numbers.
