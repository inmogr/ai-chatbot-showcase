# PRD — Mini RAG Chatbot Backend (Acme policy assistant)

This document defines what will be built for the take-home: the problem and goals as the brief states them, the users and their document access, scope and non-goals, every assumption tied to the brief line it interprets, the functional requirements FR-01…FR-34 with acceptance criteria and test names, the non-functional requirements NFR-01…NFR-15, a risk summary, the round-10 resolution of every former open item, and every claim that is still unverified. Precedence used throughout: the decision register wins over K-file corrections, and corrections win over K-file bodies. Version 1.1 applied the round-10 resolutions appended to the register: every item that was OPEN in §8 is RESOLVED (round 10), with its ID kept for traceability. Version 2 applies the round-11 accuracy changes (wording of assumptions, consolidated error catalog, test mechanics, optional conversation memory, Origin verified).

Sources: `inputs/00-brief.md`; `inputs/attach/DECISIONS-REGISTER.md`; `knowledge/K01`–`K09` (each file's corrections section applied), `knowledge/K10-consolidation.md` (round-10 resolutions), `knowledge/K11-accuracy.md` (round-11 changes); evidence E01–E15, E17; round state records `inputs/attach/C05`–`C08-STATE.md` where cited. "Brief README §N" means requirement section N of the assignment README; "brief §6" / "brief §7" mean sections of `inputs/00-brief.md` (PDF text / measured facts on the candidate's machine).

Companion documents: [REQUIREMENTS-TRACEABILITY.md](REQUIREMENTS-TRACEABILITY.md), [DECISIONS.md](DECISIONS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [TEST-PLAN.md](TEST-PLAN.md), [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md), [README_SUBMISSION-OUTLINE.md](README_SUBMISSION-OUTLINE.md), [RISKS-ASSUMPTIONS.md](RISKS-ASSUMPTIONS.md).

---

## 1. Problem and goals

### 1.1 Problem (brief, verbatim)

> "Build a FastAPI backend that exposes a chatbot over WebSocket. The chatbot answers questions about company policy documents using Retrieval-Augmented Generation (RAG) and enforces role-based access control (RBAC) so users only see documents they are authorised to access."

### 1.2 What the evaluator values (brief, verbatim)

> "We want to see **production-quality code at small scale**, not a prototype. Clear decisions, reasonable error handling, and honest documentation of tradeoffs matter more than a long feature list."

> "What we care about is whether **you understand what you produced**. Do not paste output you cannot explain."

> "**Time budget:** ~4–6 hours of focused work. You have 3 days to submit."

> "Your server must accept the protocol exactly as specified — the provided client is what we will use to evaluate your submission."

### 1.3 Goals

| #   | Goal                                                                                                                                          | Brief basis                | Delivered by         |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | -------------------- |
| 1   | Ingest the 7 department PDFs (6 text-layer, 1 scanned) automatically, with `department`, `access_level`, `source_file`, `page` on every chunk | §1 Document ingestion      | FR-04…FR-11          |
| 2   | Chat over `/ws/chat` with in-band auth first and real token-by-token streaming                                                                | §2 WebSocket chat endpoint | FR-12…FR-18, FR-30   |
| 3   | RBAC filter at the vector-DB query layer, with the single `hr` exception                                                                      | §3 RBAC at retrieval time  | FR-03, FR-19, FR-20  |
| 4   | One LLM tool whose three mock fetches run in parallel (~1 s, not ~3 s)                                                                        | §5 Parallel tool call      | FR-22…FR-27          |
| 5   | Free-tier LLM and local embeddings behind a thin, swappable interface                                                                         | §6 LLM and embeddings      | FR-28, FR-33         |
| 6   | `auth_failed` + close on bad auth; user-facing error with the socket kept open on LLM/tool failure; no blocking calls in `async def`          | §7 Error handling          | FR-15, FR-29, NFR-04 |
| 7   | Work end-to-end with the provided `test_client.html`, which we treat as read-only (our assumption, A-26)                                      | How to test your server    | FR-30                |
| 8   | `README_SUBMISSION.md` with the 8 mandated sections and the provider choice                                                                   | What to submit             | FR-32, FR-33         |
| 9   | Commit history that shows iteration                                                                                                           | Ground rules               | FR-34                |

### 1.4 Success criteria (the brief's rubric)

| Rubric area                      | What the brief looks for                                          | How this plan proves it                                                                        |
| -------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| WebSocket + streaming            | Correct protocol, real token-by-token streaming                   | FR-12…FR-18; progressive-streaming test; live cadence test (U-01)                              |
| Parallel APIs                    | Correctly parallel, ~1 s total not ~3 s                           | FR-27, NFR-01 (< 1.35 s; E06)                                                                  |
| No blocking calls in `async def` | —                                                                 | NFR-04 (unit test: `encode` dispatched through `asyncio.to_thread`)                            |
| RBAC at the DB layer             | Vector DB filter applied at query time, not post-filter in Python | FR-03, FR-19, FR-20, NFR-05 (counts 12/18/24/30)                                               |
| Chunk strategy                   | Defensible choice; not a magic number copied from a tutorial      | D-22; README §4 backed by E01/E02                                                              |
| Scanned PDF handling             | Works without manual intervention                                 | FR-04 (RapidOCR, bundled models)                                                               |
| Error handling                   | Reasonable, not over-engineered                                   | FR-15, FR-29, consolidated catalog (10 turn-error strings + 4 `auth_failed` texts), no retries |
| Code quality                     | Type hints, Pydantic models, no dead code, small functions        | NFR-14 (ruff incl. C90 complexity ≤ 10 + mypy strict)                                          |
| README thinking                  | Shows judgment and tradeoffs                                      | FR-32, FR-33                                                                                   |

---

## 2. Users and roles

### 2.1 Test users

The three users come from the provided `mint_tokens.py` (HS256, signed with `JWT_SECRET` from `.env`, 7-day tokens). `fin-001` is a test-only user, minted with the same secret by the test-token helper (the pytest fixture `make_user_token`, plus the optional `scripts/generate_test_tokens.py` used for the manual finance check), because `mint_tokens.py` has no finance user and we treat the provided files as read-only — our assumption (A-26); the brief does not forbid editing them.

| `sub` (user_id)       | `department` | `level` | Source                             |
| --------------------- | ------------ | ------- | ---------------------------------- |
| `emp-001`             | `hr`         | 1       | brief README §4 / `mint_tokens.py` |
| `mgr-002`             | `hr`         | 2       | brief README §4 / `mint_tokens.py` |
| `exec-003`            | `exec`       | 3       | brief README §4 / `mint_tokens.py` |
| `fin-001` (test-only) | `finance`    | 1       | test-token helper (K04, K08)       |

### 2.2 Document access table (brief README §1) and source reality (brief §6–7, E01)

| File                               | `department` | `access_level` | Format                                                  | Chunks |
| ---------------------------------- | ------------ | -------------- | ------------------------------------------------------- | ------ |
| `hr/leave_policy.pdf`              | hr           | 1              | text layer, 1 page, title + 6 numbered sections         | 6      |
| `hr/code_of_conduct.pdf`           | hr           | 1              | text layer, 1 page, title + 6 sections                  | 6      |
| `hr/performance_review.pdf`        | hr           | 2              | text layer, 1 page, title "(Manager Only)" + 6 sections | 6      |
| `finance/expense_policy.pdf`       | finance      | 1              | text layer, 1 page, title + 6 sections                  | 6      |
| `finance/travel_reimbursement.pdf` | finance      | 1              | text layer, 1 page, title + 6 sections                  | 6      |
| `exec/compensation_committee.pdf`  | exec         | 3              | text layer, 1 page, title + 6 sections                  | 6      |
| `exec/strategic_plan.pdf`          | exec         | 3              | one embedded image, 0 text-layer characters (OCR)       | 6      |
| **Total**                          |              |                |                                                         | **42** |

### 2.3 RBAC rule and visible-chunk matrix

Rule (filter inside the Qdrant query): `department ∈ {user.department, "hr"}` AND `access_level ≤ user.level`.

| Document (level)           | emp-001 (hr, 1) | mgr-002 (hr, 2) | fin-001 (finance, 1) | exec-003 (exec, 3)        |
| -------------------------- | --------------- | --------------- | -------------------- | ------------------------- |
| leave_policy (1)           | yes             | yes             | yes (hr exception)   | yes (hr exception)        |
| code_of_conduct (1)        | yes             | yes             | yes (hr exception)   | yes (hr exception)        |
| performance_review (2)     | no (level)      | yes             | no (level)           | yes (hr exception)        |
| expense_policy (1)         | no              | no              | yes                  | no (no finance exception) |
| travel_reimbursement (1)   | no              | no              | yes                  | no (no finance exception) |
| compensation_committee (3) | no              | no              | no                   | yes                       |
| strategic_plan (3)         | no              | no              | no                   | yes                       |
| **Visible chunks (of 42)** | **12**          | **18**          | **24**               | **30**                    |

### 2.4 Role boundaries and edge cases

- **HR exception keeps the level check (Reading A).** It waives only the department condition; `emp-001` (level 1) cannot see `performance_review.pdf` (level 2) although both are `hr` (A-01).
- **Executives cannot read finance.** This is the consequence of the brief's formula plus its single `hr` exception, not a rule the brief states; `exec-003` sees 30 chunks, none from `finance/` (A-02). This is the README's "one thing to improve".
- **Unknown departments** (any non-empty string, e.g. a department with no folder) are accepted and see only `hr` content within their level (A-23).
- **`level`** is a strict integer ≥ 1 with no upper bound; `"1"`, `true` and `1.0` are rejected (A-12, A-23).
- **Claims given to the LLM:** only `sub` (needed for the tool's IDOR check); `department` and `level` are withheld (A-19).

---

## 3. Scope and non-goals

### 3.1 In scope

- **Ingestion CLI** `python -m scripts.ingest --docs-dir ./docs`: pypdfium2 text layer; RapidOCR 3.9.2 only for pages with `len(text.strip()) == 0`; structural chunks (numbered headings / geometric paragraph gaps) with the title prefixed; 150-token sentence-packing fallback; 42 chunks written to Qdrant.
- **Vector DB with DB-layer RBAC:** Qdrant server in Docker (`qdrant/qdrant:v1.19.1`, `http://localhost:6333`) with payload indexes on `department` (keyword) and `access_level` (integer).
- **Embeddings:** local `BAAI/bge-small-en-v1.5` (384 dimensions) on CPU; model load and encode through `asyncio.to_thread`.
- **WebSocket endpoint** `/ws/chat`: in-band auth gate, then a sequential message loop.
- **Parallel tool** `get_employee_context(user_id)`: three mock fetches in an `asyncio.TaskGroup` (< 1.35 s), behind an IDOR check in the orchestrator against the JWT `sub` (a mismatch sends a denial result to pass 2).
- **LLM streaming** through one OpenAI-compatible adapter; default Groq `openai/gpt-oss-120b`; other providers selectable by configuration (a configuration swap, not failover).
- **Conversation memory (stretch S-03) — optional:** implemented last, only if time remains (IMPLEMENTATION-PLAN commit 8); the core pipeline is stateless. If built: the last 3 question/answer pairs go to the LLM only; retrieval always uses the current question.
- **Error handling:** auth failures close with 1008; a turn failure sends one of 10 consolidated turn-error strings and keeps the socket open.
- **Tests and quality:** offline default suite with fakes in flat `tests/test_*.py` files; `model` / `qdrant` / `live_llm` markers; ruff + mypy strict; branch coverage ≥ 80 % on `app/`, measured on the full local suite `uv run pytest -m "not live_llm"`.
- **Documentation:** `README_SUBMISSION.md` with the 8 mandated sections, provider choice and swap, assumptions, test notice and known limitations.

### 3.2 Non-goals

| Non-goal                                                | Reason                                                                                                                                               |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Post-retrieval filtering in Python                      | Forbidden by the brief (R-01); the filter runs inside `query_points`                                                                                 |
| Login endpoints, user tables, token storage or refresh  | Tokens are minted offline by `mint_tokens.py`                                                                                                        |
| Modifying `test_client.html` or `mint_tokens.py`        | Our assumption (A-26): we treat them as read-only — the brief does not forbid editing them; finance tokens come from a test helper (R-17)            |
| Hosted OCR / vision APIs                                | D-05: local OCR is reproducible (no account, key, cost or network for OCR; bundled models) and minimises data (whole documents never leave the host) |
| OCR needing system packages (tesseract, poppler)        | D-05; neither is installed on the candidate's machine (brief §7); the evaluator's machine is unknown                                                 |
| HTTP-handshake auth (401/403, headers)                  | The protocol authenticates in-band on the first frame (R-09)                                                                                         |
| History in the retrieval query; LLM query rewriter      | E04: concatenation broke topic switches; a rewriter is a "with more time" item                                                                       |
| Reranker, hybrid BM25 search                            | Optional stretch items S-01, S-02                                                                                                                    |
| Interleaved or cancelled concurrent turns on one socket | The client renders one streaming bubble at a time (R-12); turns queue                                                                                |
| Runtime citation verification during streaming          | Would require buffering the stream; citations are spot-checked by the manual checklist (D-80)                                                                         |
| Persistent chat sessions                                | History is a local variable of the connection handler                                                                                                |
| `/health` endpoint, connection manager, global state    | YAGNI; evaluation is `test_client.html` over `/ws/chat` (R-19)                                                                                       |
| Automatic retries of LLM or tool calls                  | Interactive turn; partial text cannot be replayed without duplicate output                                                                           |
| Startup "pre-flight" model ping                         | Burns free-tier quota and can block startup when rate-limited                                                                                        |
| Retrieval score threshold                               | Answerable and unanswerable top-1 scores overlap (E03)                                                                                               |

---

## 4. Assumptions

Each assumption names the exact brief line it interprets. These are the README's "Assumptions" list (C-11).

**A-01 — The `hr` exception keeps the level check (Reading A).**
Brief: "There is one exception: any user can access `hr` content regardless of their primary department. Think about the cleanest way to express this."
The exception waives the department condition only; `access_level <= user.level` still applies, otherwise `emp-001` would read "Performance Review Process (Manager Only)". Expressed as `department MatchAny [user.department, "hr"]`. Decision D-27.

**A-02 — No exception for executives on finance.**
Brief: "`department == user.department  AND  access_level <= user.level`" and "There is one exception".
`exec-003` (level 3) does not see finance policies. This follows from the brief's formula plus its single `hr` exception — the brief states no such rule itself; it is kept as is and raised as the improvement idea. Decision D-27.

**A-03 — The LLM explains the grade mismatch instead of inventing a mapping.**
Brief: "The LLM should be able to invoke this tool when the user asks something personal like "how much leave do I have given my grade" or "who is my manager"."
The tool returns `"grade": "Senior"`; the travel policy uses numeric grades ("Grade 4 and above"). No mapping is hard-coded. Decision D-01.

**A-04 — Grounding overrides a false premise; leave does not depend on grade.**
Brief: same line as A-03.
`leave_policy.pdf` gives 22 working days to all full-time employees; the canonical prompt's rule 6 instructs the model to state that the entitlement does not depend on grade (prompt-driven, U-09). Decisions D-02, D-34.

**A-05 — Pages are 1-based and taken from the PDF.**
Brief: "`page` — page number if applicable".
All 7 PDFs are 1 page (brief §7 measured facts), so every chunk has `page == 1`, but the value is extracted, not hard-coded. Decision D-03.

**A-06 — Ingestion is a CLI script, not an endpoint.**
Brief: "Write a script or endpoint that:".
Keeps CPU-heavy OCR and embedding work out of the async server and needs no ingestion auth. Decision D-04.

**A-07 — OCR runs locally with RapidOCR.**
Brief: "Extracts text from each PDF (handle both text-based and scanned PDFs — your choice of approach)" and rubric "Scanned PDF handling | Works without manual intervention".
Justification: reproducible (no account, key, cost or network call for OCR; models bundled in the wheel) and data minimisation (whole documents never leave the host; at query time only up to 4 role-filtered chunks reach the hosted LLM, which the README discloses). Decision D-05.

**A-08 — OCR triggers only on an empty text layer.**
Brief: "`exec/strategic_plan.pdf` (scanned/image — OCR required)".
Trigger `len(text.strip()) == 0`: the six text PDFs have 1,433–1,619 text-layer characters (E01), the scan has 0; no arbitrary threshold, no double ingestion of mixed pages. Decision D-06.

**A-09 — Turns are sequential per connection.**
Brief: "Client then sends messages: `{"type": "message", "text": "How many leave days do I get?"}`" (and the client keeps a single `currentBotMsg`).
Messages sent during a turn wait in uvicorn's per-connection queue (`ws_max_queue` = 32, then TCP backpressure; nothing dropped, E11). Decisions D-08, D-41.

**A-10 — The tool's `user_id` is checked against the JWT, deny on mismatch.**
Brief: "Give the LLM one tool: `get_employee_context(user_id)`."
The model's argument is untrusted; the orchestrator compares it with the JWT `sub` before calling the tool, and on mismatch does not call the tool and sends the denial result to pass 2 so the model refuses in conversation (round 10, O-01). Decisions D-09, D-52.

**A-11 — Retrieval always precedes generation.**
Brief: "When the user sends a message, retrieve relevant chunks **filtered at the vector DB query layer**" and "Give the LLM one tool".
The LLM gets no search tool; every message is retrieved for first. Decision D-10.

**A-12 — Integers stay integers.**
Brief: "`access_level` — integer, see mapping below".
Chunk `access_level` is stored as `int` (a float `1.0` passes Qdrant's numeric range, E03); the JWT `level` uses `StrictInt` because lax parsing turns `true`, `"2"`, `2.0` into ints (K02 verified). Decisions D-11, D-24.

**A-13 — Strict JWT validation.**
Brief: "Invalid / expired / missing JWT → send `auth_failed` and close the connection".
PyJWT does not require `exp` by default (K02 verified), so `algorithms=["HS256"]` is pinned and `sub`, `exp`, `department`, `level` are required (leeway 10 s). Decisions D-12, D-13, D-39.

**A-14 — The first frame must be a valid auth frame.**
Brief: "Client sends first: `{"type": "auth", "token": "<jwt>"}`".
Anything else (non-JSON, another frame type, a bad token, no frame in time) gets `auth_failed`, then close with code 1008. Decisions D-14, D-39.

**A-15 — Message text is 1–2,000 characters after stripping.**
Brief: "Client then sends messages: `{"type": "message", "text": "How many leave days do I get?"}`".
Uvicorn accepts 16 MiB messages by default (K02 verified) and the embedder silently truncates beyond 512 tokens (verified by running code, K02); leading/trailing whitespace is stripped before the length check (E12). Decisions D-16, D-40.

**A-16 — Unauthorised documents are treated as non-existent.**
Brief: "…so users only see documents they are authorised to access."
The filter keeps them out of the prompt; the prompt instructs the model to answer with the fixed refusal "I cannot find that information in the authorised company policies." (U-09). Decision D-17.

**A-17 — Every message goes through retrieval; no intent classifier.**
Brief: "The chatbot answers questions about company policy documents using Retrieval-Augmented Generation (RAG)".
Greetings are handled by the prompt's rule 1. Decision D-18.

**A-18 — The model cites inline; the server appends no sources block.**
Brief: "**Metadata on each chunk must include:** … `source_file` … `page`".
Excerpts carry `source` and `page`; the model cites `[file.pdf, page N]`. A server-built block would need stream buffering (D-19, reversed).

**A-19 — Only `sub` reaches the LLM.**
Brief: "The JWT payload looks like: `{"sub": "emp-001", "email": "emp@test.com", "department": "hr", "level": 1, …}`".
`department` and `level` are withheld so the model cannot confuse clearance level with HR grade; `sub` is needed for the tool. Decision D-20.

**A-20 — Memory is optional; retrieval always uses the current question.**
Brief (stretch): "Conversation memory across turns".
The core pipeline is stateless; conversation memory is optional and built last, only if time remains (round 11). Retrieval uses the current question only (E04); if memory is built, the last 3 question/answer pairs go to the LLM only. Decisions D-21 (reversed concatenation), D-36, D-73.

**A-21 — The automatic first-run model download is not manual intervention.**
Brief: "Downloads a small model once (~100MB) and runs on CPU." and rubric "Works without manual intervention".
No human step is needed, but the first run needs network (~130 MB, 21.7 s measured; E01, K03); an air-gapped run needs a pre-warmed Hugging Face cache. Decision D-23.

**A-22 — Pluggability is one OpenAI-compatible adapter behind a port.**
Brief: "keep it pluggable behind a thin interface so we can swap in our own provider/key without rewriting your code."
Groq, Gemini, OpenRouter, Ollama, OpenAI and Anthropic are selected by `LLM_PROVIDER` plus that provider's variables. Decision D-29.
Embeddings (post-review): only the local `sentence-transformers` adapter is implemented, behind the embedder ports. Another embedding provider — for example the template's commented `EMBEDDING_PROVIDER=openai` — means one new adapter class plus re-running ingestion; until then any other value stops startup and ingestion with a configuration error (O-18). The README states this under Known limitations.

**A-23 — JWT claim shapes.**
Brief: "The JWT payload looks like: `{"sub": "emp-001", … "department": "hr", "level": 1, "iat": …, "exp": …}`" and "any user can access `hr` content regardless of their primary department".
`sub` is a non-empty string; `department` is a non-empty free string (unknown departments see only `hr` content); `level` is `StrictInt` ≥ 1 with no upper bound. Decisions D-11, D-39.

**A-24 — The auth window is 10 seconds.**
Brief: "Client sends first: `{"type": "auth", …}`" and "You are free to also support other clients (curl/wscat/Postman)".
10 s allows pasting a token into wscat or Postman; the earlier 3 s (D-15) was a planning assumption, not a brief rule. Decision D-39.

**A-25 — Server and token script share `miniragchatbot/.env`.**
Brief: "Use the signing key in `.env` (`JWT_SECRET`)." `mint_tokens.py` calls `load_dotenv()` with no path; python-dotenv then searches for `.env` starting in the script's own folder (`miniragchatbot/`) and walking up — not the working directory (corrected post-review; verified with python-dotenv 1.2.4).
The server's settings (`pydantic-settings`, `env_file=".env"`) read `.env` from the working directory, so the server must start in `miniragchatbot/`; then both read `miniragchatbot/.env` and tokens verify. Decisions D-47, D-76.

**A-26 — The provided files are treated as read-only.**
Brief: "A helper script `mint_tokens.py` is provided" and "A browser-based test client is provided at `test_client.html`… the provided client is what we will use to evaluate your submission."
Our assumption, not a brief rule: the brief does not forbid editing them. We leave both as delivered and mint the test-only `fin-001` token with a separate helper (round 11). Decision D-74.

---

## 5. Functional requirements

Format: statement, acceptance criteria (Given / When / Then), the K01 rows satisfied, the test name, its level and its pytest marker. FR-n satisfies MUST row M-n. Test names are canonical (K09; round 10, O-03); K08 names survive only as aliases in the traceability matrix.

### FR-01 — FastAPI application (M-01)

- **Statement:** The backend is a FastAPI application in the `app/` package; setup and teardown run in the lifespan, which also loads the settings (importing `app.main` has no side effects).
- **Given** a valid `.env` and an ingested collection, **when** `uv run uvicorn app.main:app --reload` starts, **then** the lifespan loads the settings, loads the embedding model via `asyncio.to_thread`, verifies the collection, serves `/ws/chat`, and closes the Qdrant and OpenAI clients on shutdown.
- **Test:** `test_fastapi_app_lifespan_and_startup` — unit, marker none.

### FR-02 — Retrieval-augmented answers (M-02)

- **Statement:** Every message is answered with RAG: retrieval runs before the LLM.
- **Given** an authenticated user and a message, **when** the turn runs, **then** the query is embedded and the RBAC-filtered Qdrant query (k = 4, no score threshold) completes before pass 1, and the chunks reach the LLM as excerpts labelled with source file and page so the model can cite `[file.pdf, page N]`.
- **Test:** `test_rag_pipeline_retrieval_and_inline_citations` — unit (fakes), marker none. Whether the live model actually cites correctly is U-09.

### FR-03 — RBAC inside the database (M-03)

- **Statement:** Access control is enforced by the vector database at query time.
- **Given** validated claims, **when** `query_points` runs, **then** its filter is `department MatchAny [user.department, "hr"] AND access_level Range(lte=user.level)` and no Python code removes returned chunks.
- **Test:** `test_rbac_database_layer_filter_enforcement` — integration, marker `qdrant`.

### FR-04 — Text-layer and scanned PDFs (M-04)

- **Statement:** Ingestion extracts text from text-based and scanned PDFs without manual steps.
- **Given** the PDFs under `./docs`, **when** text is extracted, **then** pages with a text layer use pypdfium2 and a page with `len(text.strip()) == 0` is rendered at 300 dpi and read by RapidOCR 3.9.2 with its bundled models (no system packages).
- **Test:** `test_pdfium_and_rapidocr_text_extraction` — integration, marker `model`.

### FR-05 — Ingestion CLI (M-05)

- **Statement:** Ingestion is a CLI module.
- **Given** `./docs` and a running Qdrant, **when** `uv run python -m scripts.ingest --docs-dir ./docs` runs, **then** it processes every file, prints a summary (files, chunks, time) and exits 0; library code raises domain errors (Qdrant unreachable, access-table mismatch, missing or unmapped file) and only the CLI maps them to exit code 1.
- **Test:** `test_ingest_cli_execution_and_exit_code` — integration, markers `model` + `qdrant`.

### FR-06 — Chunk persistence (M-06)

- **Statement:** Ingestion stores chunks and metadata in a Qdrant collection through the synchronous `QdrantClient` (`VectorWriterPort`).
- **Given** the extracted chunks, **when** they are written, **then** the collection is recreated and holds 42 points (36 text-layer + 6 from the scan) with deterministic UUIDv5 ids, 384-dimension cosine vectors and payload indexes keyword(`department`) and integer(`access_level`). The counts 42 and 6 live only in tests, never in product code.
- **Test:** `test_qdrant_collection_recreation_and_chunk_count` — integration, markers `model` + `qdrant`.

### FR-07 — Department from the folder (M-07)

- **Statement:** `department` is derived from the parent folder.
- **Given** a file at `./docs/<dept>/<file>.pdf`, **when** its chunks are built, **then** payload `department` equals the folder name (`hr`, `finance` or `exec`) and agrees with the access table.
- **Test:** `test_metadata_department_extracted_from_folder` — unit, marker none.

### FR-08 — Integer access level (M-08)

- **Statement:** `access_level` is stored as an integer.
- **Given** the access table, **when** payloads are written, **then** `access_level` is a Python `int` (never float or str) with an integer payload index. Reason: Qdrant's range filter returned a float `1.0` probe and never a string `"1"` (E03).
- **Test:** `test_metadata_access_level_integer_type` — unit, marker none.

### FR-09 — Canonical access mapping (M-09)

- **Statement:** Levels follow the brief's 7-row table exactly.
- **Given** the files on disk, **when** ingestion maps them, **then** each file gets the table's department and level; a mapped file missing from disk, an unmapped `*.pdf`, or a path/casing mismatch (e.g. `HR/leave_policy.pdf`) raises a domain error (fail fast).
- **Test:** `test_access_level_canonical_mapping_and_fail_fast` — unit, marker none.

### FR-10 — Source file name (M-10)

- **Given** an input file `leave_policy.pdf`, **when** its chunks are stored, **then** every payload has `source_file == "leave_policy.pdf"`.
- **Test:** `test_metadata_source_file_persisted` — unit, marker none.

### FR-11 — Page number (M-11)

- **Given** parsed pages, **when** payloads are written, **then** `page` is a 1-based `int` (1 for every chunk of this corpus).
- **Test:** `test_metadata_page_number_1_based` — unit, marker none.

### FR-12 — `/ws/chat` route (M-12)

- **Given** the running app, **when** a client opens `ws://localhost:8000/ws/chat` without auth headers, **then** the server accepts the upgrade and waits for the first in-band frame.
- **Test:** `test_ws_chat_endpoint_accepts_connection` — transport, marker none.

### FR-13 — Auth frame first (M-13)

- **Given** a new connection, **when** the client sends `{"type": "auth", "token": "<jwt>"}` within 10 s, **then** the token's signature and claims are verified.
- **Test:** `test_first_frame_auth_payload_received` — transport, marker none.

### FR-14 — Auth success (M-14)

- **Given** a valid token with `sub="emp-001"`, `department="hr"`, `level=1`, **when** authentication succeeds, **then** the server sends `{"type": "auth_success", "user_id": "emp-001", "department": "hr", "level": 1}`.
- **Test:** `test_auth_success_payload_emission` — transport, marker none.

### FR-15 — Auth failure and close (M-15)

- **Statement:** Every first-frame failure sends one `auth_failed` frame, then closes with code 1008.
- **Given** an unauthenticated connection, **when** (a) no frame arrives within 10 s, (b) the frame is not JSON, (c) the frame is JSON but not a valid auth frame, or (d) the token is invalid, expired or has missing/ill-typed claims, **then** the server sends `{"type": "auth_failed", "message": …}` with respectively "Authentication timed out", "Invalid JSON frame", "Authentication required as first frame", "Invalid or expired token", and closes with 1008.
- **Test:** `test_auth_failure_emits_frame_and_closes_1008` — transport (sync `def`; a small auth timeout passed as a parameter), marker none.

### FR-16 — Message frames (M-16)

- **Given** an authenticated session, **when** the client sends `{"type": "message", "text": "What is the policy?"}`, **then** leading/trailing whitespace is stripped and a turn starts if 1–2,000 characters remain; whitespace-only text or more than 2,000 characters after stripping gets the error "Message text must be between 1 and 2000 characters" with the socket open; unknown extra fields are ignored.
- **Test:** `test_chat_message_frame_validated` — transport, marker none.

### FR-17 — Token streaming (M-17)

- **Given** a running turn, **when** the adapter yields text deltas, **then** each delta is sent at once as its own `{"type": "stream", "text": "…"}` frame (no buffering), so frames arrive progressively.
- **Test:** `test_stream_tokens_progressive_frames` — transport (fake LLM, 7 deltas 0.03 s apart), marker none.

### FR-18 — Completion signal (M-18)

- **Given** a turn that finishes successfully, **when** the last delta has been sent, **then** the server sends `{"type": "done"}` and keeps the socket open for the next message.
- **Test:** `test_stream_finishes_with_done_frame` — transport, marker none.

### FR-19 — Exact filter (M-19)

- **Given** `fin-001` (`department="finance"`, `level=1`), **when** retrieval runs, **then** `query_points` receives `department MatchAny ["finance", "hr"]` AND `access_level Range(lte=1)` with a limit of 4.
- **Test:** `test_qdrant_rbac_department_and_level_filter` — unit (spy on `query_points`), marker none.

### FR-20 — HR exception (M-20)

- **Given** `exec-003` (`department="exec"`, `level=3`), **when** Qdrant is searched, **then** `hr` chunks with `access_level ≤ 3` are candidates and `finance` chunks are not.
- **Test:** `test_hr_exception_allows_cross_department_access` — integration, marker `qdrant`.

### FR-21 — JWT verification with the environment secret (M-21)

- **Given** `JWT_SECRET` from the environment (required and non-empty; no literal default; missing or empty stops startup), **when** a token is decoded, **then** PyJWT uses `algorithms=["HS256"]`, requires `sub`, `exp`, `department`, `level`, applies leeway 10 s, and only `jwt.PyJWTError` and pydantic `ValidationError` are caught.
- **Test:** `test_jwt_validation_strict_hs256_env_secret` — unit, marker none (plus the 10-case transport matrix `test_jwt_matrix_ten_cases`, NFR-07).

### FR-22 — Employee tool and IDOR check (M-22, R-10)

- **Statement:** The LLM gets exactly one tool, `get_employee_context(user_id)`; the orchestrator checks the `user_id` it supplies against the JWT `sub` before calling the tool (round 10, O-01).
- **Given** a session authenticated as `sub="emp-001"`, **when** pass 1 returns a `get_employee_context` call, **then** the tool is called only if `user_id == "emp-001"`; on mismatch the tool is not called (none of the three fetches runs), pass 2 receives the tool result "Access denied: caller may only query their own context.", and the client gets the model's in-dialogue refusal followed by `done` — no error frame.
- **Test:** `test_tool_idor_validation_against_jwt_sub` — unit, marker none.

### FR-23 — Tool invocation loop (M-23)

- **Given** `{"type": "message", "text": "who is my manager"}`, **when** pass 1 runs with `tools=[get_employee_context]`, `tool_choice="auto"` and returns a tool call, **then** the tool runs and pass 2 runs with the same tools and `tool_choice="none"`, streaming plain text, followed by `done`; at most one tool round per turn. If pass 1 returns several tool calls, only the first is executed and echoed in the pass-2 assistant message, and a warning is logged (round 10, O-14).
- **Test:** `test_turn_invokes_employee_context_on_personal_query` — unit (fake LLM), marker none. The real model choosing the tool is live-only: `test_live_llm_invokes_employee_tool` (marker `live_llm`).

### FR-24 — Mock profile (M-24)

- **Given** an authorised `user_id="emp-001"`, **when** the profile fetch runs, **then** it returns `{"name": "Jane Doe", "grade": "Senior"}` (after `asyncio.sleep(1)`); the combined tool result nests it under `"profile"`.
- **Test:** `test_employee_tool_returns_profile_payload` — unit, marker none.

### FR-25 — Mock manager (M-25)

- **Given** an authorised `user_id="emp-001"`, **when** the manager fetch runs, **then** it returns `{"manager": "John Smith"}`; the combined result nests it under `"manager"`.
- **Test:** `test_employee_tool_returns_manager_payload` — unit, marker none.

### FR-26 — Mock team (M-26)

- **Given** an authorised `user_id="emp-001"`, **when** the team fetch runs, **then** it returns `{"team_size": 8, "team_name": "Platform"}`; the combined result nests it under `"team"`. Combined tool result: `{"profile": {"name": "Jane Doe", "grade": "Senior"}, "manager": {"manager": "John Smith"}, "team": {"team_size": 8, "team_name": "Platform"}}`.
- **Test:** `test_employee_tool_returns_team_payload` — unit, marker none.

### FR-27 — Parallel execution under a timeout (M-27, R-04, C-03)

- **Given** three fetches that each await `asyncio.sleep(1)`, **when** `get_employee_context` runs, **then** they run concurrently in an `asyncio.TaskGroup` inside `asyncio.timeout(2.0)` and the call completes in < 1.35 s (sequential is ≥ 3 s); a failing or timed-out fetch cancels its siblings and raises `ToolExecutionError`.
- **Test:** `test_employee_tool_executes_parallel_under_1_35s` — unit, marker none. Evidence E06.

### FR-28 — Pluggable providers (M-28)

- **Given** `LLM_PROVIDER=groq` and `GROQ_API_KEY` in `.env`, **when** the app starts, **then** an `AsyncOpenAI`-backed adapter that satisfies the `stream_chat` Protocol is built with `GROQ_MODEL=openai/gpt-oss-120b`; switching provider means changing `LLM_PROVIDER` and that provider's variables with no code change; a selected provider without its key (except Ollama) or model stops startup. The embedder sits behind its own ports; the four Protocols live in `app/domain/ports.py`.
- **Test:** `test_openai_adapter_satisfies_stream_chat_protocol` — unit (mypy-checked assignment to the Protocol), marker none.

### FR-29 — Failures keep the socket open (M-29, C-06, I-05)

- **Given** an active connection, **when** a tool fetch fails (`ToolExecutionError`) or the LLM fails (e.g. HTTP 429), **then** exactly one `{"type": "error", "message": …}` frame with one of the 10 consolidated turn-error strings (ARCHITECTURE §10) is sent ("Failed to execute employee lookup." / "System is busy due to high demand. Please try again shortly."), no `done` follows, nothing is retried, and the next message is processed normally.
- **Test:** `test_downstream_failure_emits_error_frame_and_keeps_socket_open` — transport, marker none.

### FR-30 — `test_client.html` compatibility (M-30, I-01, I-06)

- **Given** `test_client.html` opened from `file://` (Origin `null`), **when** it connects, authenticates and sends `{"type": "message", "text": "…"}`, **then** it receives `auth_success`, progressive `stream` frames and `done` with no client change; the server adds no Origin check — none is needed because auth is an in-band JWT, not cookies, and an allow-list rejecting `null` would break this client (verified live, E17: Origin `null` and foreign origins are accepted by default); every server frame is a JSON object.
- **Test:** `test_client_html_exact_protocol_flow` — transport, marker none; plus the manual checklist (TEST-PLAN §9).

### FR-31 — Packaging and environment template (M-31, R-02, R-16)

- **Given** a fresh clone, **when** `uv sync --python 3.12` runs, **then** all pinned dependencies install; `.env.example` lists every key (e.g. `JWT_SECRET`, `GROQ_API_KEY`) with placeholders only; no real secret exists in any commit.
- **Test:** `test_submission_files_and_env_template_present` — unit (file presence), marker none; plus the scripted git-history secrets scan (NFR-08).

### FR-32 — Submission README (M-32, C-08, C-11)

- **Given** the repository, **when** `README_SUBMISSION.md` is read, **then** it covers the brief's 8 numbered sections, the provider choice and swap, the assumptions, test instructions and known limitations.
- **Test:** `test_readme_submission_contains_required_sections` — README check, marker none.

### FR-33 — Provider choice documented (M-33, G-01)

- **Given** the default `LLM_PROVIDER=groq`, **when** `README_SUBMISSION.md` is read, **then** it states the choice (Groq, `openai/gpt-oss-120b`) and the reasons — free plan, documented tool support, deliberation documented to arrive in a separate field (E09; not live-verified, U-02), that Groq does not retain customer data for inference by default (up to 30 days for reliability/abuse monitoring) — and discloses that up to 4 role-filtered excerpts per turn reach the hosted provider while OCR and embeddings stay local (`LLM_PROVIDER=ollama` keeps inference local). Training use is not stated in the Groq docs read and is not claimed (U-08, UNVERIFIED; round 10, O-07).
- **Test:** `test_readme_documents_provider_selection_rationale` — README check, marker none.

### FR-34 — Vertical-slice commit history (M-34)

- **Given** the `.git` history, **when** it is inspected, **then** commits 1–7 match the vertical slices from the skeleton (auth + stub stream) to the final README, each with its tests.
- **Test:** `test_git_history_reflects_vertical_slices` — manual, marker none.

### 5.1 How the rubric criteria (C-01…C-11) are proven

| K01 row | Rubric focus                      | Proving requirements                                                               |
| ------- | --------------------------------- | ---------------------------------------------------------------------------------- |
| C-01    | Defensible chunking               | FR-32 (README defence with E01/E02 data), FR-04, FR-06 (structural chunks, 42 / 6) |
| C-02    | Real token-by-token streaming     | FR-17, FR-30; live cadence test (U-01)                                             |
| C-03    | No blocking calls                 | NFR-04, FR-27                                                                      |
| C-04    | RBAC at the DB layer              | FR-03, FR-19, FR-20, NFR-05                                                        |
| C-05    | Scanned PDF handled automatically | FR-04                                                                              |
| C-06    | Clean error handling              | FR-29, NFR-09, NFR-11                                                              |
| C-07    | Code quality                      | NFR-14                                                                             |
| C-08    | README judgment                   | FR-32, FR-33                                                                       |
| C-09    | Production quality                | FR-28, FR-31, NFR-14                                                               |
| C-10    | Understanding of the code         | FR-32, FR-34                                                                       |
| C-11    | Assumptions documented            | FR-32 (§4 of this PRD)                                                             |

---

## 6. Non-functional requirements

| ID     | Requirement                   | Threshold                                                                                                                                                                                                                             | Verification                                                                                                                                                                                                                                                                                                                                                           | Evidence                  |
| ------ | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| NFR-01 | Tool latency                  | Three 1.0 s fetches complete in < 1.35 s total                                                                                                                                                                                        | Unit test with spies on the three fetchers; fails at ≥ 1.35 s (sequential ≥ 3.0 s); no lower bound (it proves nothing about overlap)                                                                                                                                                                                                                                   | E06                       |
| NFR-02 | First-token latency           | From request start (`create`) to the first chunk of any kind — text, deliberation-only or tool-call — within 8.0 s, else the timeout error; no separate connect timeout; the 30 s turn timeout bounds the rest (round 10, O-09, O-21) | Unit tests passing a sub-second timer value to the adapter's constructor (round 11): a hanging `create()` and a late first chunk each give "Response generation timed out. Please try again."; a non-text first chunk stops the timer                                                                                                                                  | —                         |
| NFR-03 | Retrieval                     | Filtered query returns at most k = 4 chunks through `AsyncQdrantClient` on the event loop                                                                                                                                             | `qdrant` test (isolated collection `acme_policies_test`) asserts ≤ 4 chunks and < 200 ms (test ceiling; measured median 1.7 ms, p95 2.3 ms)                                                                                                                                                                                                                            | E03                       |
| NFR-04 | Non-blocking event loop       | Model load and `encode` run via `asyncio.to_thread`; no other blocking call in `async def`                                                                                                                                            | One unit test patches `asyncio.to_thread` in the embedder module and asserts `encode` is dispatched through it (round 11; the heartbeat and mutation thresholds were dropped)                                                                                                                                                                                          | E01                       |
| NFR-05 | DB-layer RBAC                 | Filter only inside `query_points`; zero post-retrieval filtering                                                                                                                                                                      | `qdrant` test on 42 seeded payloads in `acme_policies_test`: filtered count = 12 / 18 / 24 / 30 per user; filtered scroll contains no forbidden `source_file`                                                                                                                                                                                                          | E03                       |
| NFR-06 | IDOR prevention               | Every tool call whose `user_id` ≠ JWT `sub` is denied by the orchestrator before the tool is called; no lookup ever runs for another user                                                                                             | Adversarial unit test injects a mismatched `user_id`; asserts the tool is not called and pass 2 receives the denial result "Access denied: caller may only query their own context." (round 10, O-01)                                                                                                                                                                  | —                         |
| NFR-07 | JWT pinning                   | HS256 only; `sub`, `exp`, `department`, `level` required; leeway 10 s                                                                                                                                                                 | 10-case transport matrix (`test_jwt_matrix_ten_cases`), each → `auth_failed` "Invalid or expired token" + close 1008: expired; wrong secret; `alg: none`; missing `sub`; missing `department`; missing `level`; `level` `"1"`; `level` `true`; `level` `1.0`; missing `exp` (round 10, O-15). Missing/empty `JWT_SECRET` is covered by the startup-config test (FR-21) | K02 verified              |
| NFR-08 | Credential hygiene            | No real key, secret or token in any commit                                                                                                                                                                                            | Scripted/manual git-history scan before submission (no CI exists); `.env` is git-ignored                                                                                                                                                                                                                                                                               | —                         |
| NFR-09 | Sanitised errors              | Every client-facing error text is one of the 10 consolidated turn-error strings or the 4 `auth_failed` texts (round 11); no traceback or internal path                                                                                | Error-injection tests (Qdrant failure, LLM exceptions, malformed frames) compare frames verbatim                                                                                                                                                                                                                                                                       | —                         |
| NFR-10 | Auth and turn timeouts        | First frame within 10.0 s; whole turn within 30.0 s                                                                                                                                                                                   | Sync transport tests passing small timeout values as parameters (round 11): auth silence → "Authentication timed out" + close 1008; slow turn → one "Response generation timed out. Please try again." frame                                                                                                                                                           | E15                       |
| NFR-11 | Reliability                   | No automatic retries; socket stays open after any turn error                                                                                                                                                                          | Provider-failure test asserts one error frame, one upstream call, and that the next message is accepted                                                                                                                                                                                                                                                                | —                         |
| NFR-12 | Logging and data minimisation | Connection and turn metadata only; never message text, streamed tokens, excerpts or raw JWTs                                                                                                                                          | Log-capture test inspects the records                                                                                                                                                                                                                                                                                                                                  | —                         |
| NFR-13 | Portability                   | Python ≥ 3.11 via uv (not the system 3.9.6); Qdrant `qdrant/qdrant:v1.19.1`; no OCR system packages                                                                                                                                   | Clean bootstrap with `uv sync --python 3.12` (manual)                                                                                                                                                                                                                                                                                                                  | brief §7 (measured facts) |
| NFR-14 | Static quality                | ruff (E, W, F, I, UP, B, ASYNC, SIM, C90 with `max-complexity = 10`) clean; mypy strict clean; no dead code                                                                                                                                                           | Commit gates `uv run ruff check .` and `uv run mypy app scripts` (strict via `pyproject.toml`; round 10, O-06)                                                                                                                                                                                                                                                         | —                         |
| NFR-15 | Offline suite and coverage    | `uv run pytest` passes with no Docker, model download or key (no coverage gate); branch coverage ≥ 80 % on `app/` measured on the full local suite `uv run pytest -m "not live_llm"` (Docker Qdrant + model; round 11)                | Default run; the gate command; the RapidOCR boxes of `strategic_plan.pdf` are stored as a JSON fixture so geometric grouping is unit-tested without OCR; tokenizer-dependent chunker tests carry `model`                                                                                                                                                               | E02                       |

---

## 7. Risk register (summary)

Full mitigations and early-detection signals are in [RISKS-ASSUMPTIONS.md](RISKS-ASSUMPTIONS.md) §1.

| ID    | Risk                                                          | Likelihood | Impact   | Core mitigation                                                                                                                                                                                |
| ----- | ------------------------------------------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RR-01 | Groq free-tier model deprecation or rate-limit changes        | High       | High     | Provider swap by configuration; 429 → busy message; detection by the live smoke test (no startup model ping)                                                                                   |
| RR-02 | Deliberation-model latency, token exhaustion, empty responses | Medium     | High     | `reasoning_effort` low via `GROQ_EXTRA_PARAMS` (sent only when `LLM_PROVIDER=groq`); `max_tokens` 1500; 8 s timer to the first chunk and 30 s turn timeout (the latter bounds long deliberation, O-21); empty output → catalog error |
| RR-03 | OCR paragraph-threshold drift across environments             | Medium     | Medium   | RapidOCR 3.9.2 pinned, bundled models, 300 dpi, 2.0× gap threshold; `model`-marked integrity test (6 / 42)                                                                                     |
| RR-04 | First-run embedding-model download fails                      | Medium     | High     | Documented network need; domain error → CLI exit 1                                                                                                                                             |
| RR-05 | Evaluator has no Docker for Qdrant                            | Medium     | Critical | Embedded mode rejected; lifespan check fails fast (uvicorn exit 3)                                                                                                                             |
| RR-06 | Default macOS Python too old                                  | High       | High     | `requires-python >= 3.11`; `uv sync --python 3.12`                                                                                                                                             |
| RR-07 | RBAC bypass or leakage                                        | Low        | Critical | Filter in code at the DB layer; counts 12/18/24/30 tested                                                                                                                                      |
| RR-08 | Event-loop starvation                                         | Medium     | High     | `asyncio.to_thread` for model work; a unit test asserts `encode` is dispatched through it                                                                                                      |

---

## 8. Former open items (resolved) and unverified claims

All 23 consolidation items are **RESOLVED (round 10)**; round 11 amended O-13 and superseded O-17 (rows below, DECISIONS D-67, D-70); the final decisions are appended to the register and recorded in K10. IDs are kept so that references elsewhere still resolve. Decision entries with the rejected alternatives: DECISIONS D-52…D-66.

### 8.1 Former conflicts — all RESOLVED (round 10)

| ID   | Topic                                     | Status                        | Decision                                                                                                                                                                                                                                                                                                                            |
| ---- | ----------------------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| O-01 | IDOR denial                               | RESOLVED (round 10)           | The orchestrator compares the tool call's `user_id` with the JWT `sub` before calling the tool; on mismatch it does not call the tool and sends the denial result "Access denied: caller may only query their own context." to pass 2, so the model explains in conversation. Port: `get_employee_context(user_id)`, no `caller_id` |
| O-02 | Test file layout                          | RESOLVED (round 10)           | Flat `tests/test_*.py` files; markers separate unit / `qdrant` / `model` / `live_llm`                                                                                                                                                                                                                                               |
| O-03 | Test names                                | RESOLVED (round 10)           | K09 names (PRD FRs + implementation plan) are canonical; K08 names are aliases                                                                                                                                                                                                                                                      |
| O-04 | Ports module path                         | RESOLVED (round 10)           | One module, `app/domain/ports.py`, holding the four Protocols                                                                                                                                                                                                                                                                       |
| O-05 | Qdrant command                            | RESOLVED (round 10)           | `docker run -d --name qdrant -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1`                                                                                                                                                                                                                              |
| O-06 | mypy invocation                           | RESOLVED (round 10)           | `uv run mypy app scripts` (strict via `pyproject.toml`)                                                                                                                                                                                                                                                                             |
| O-07 | Groq training use                         | RESOLVED (round 10, evidence) | Training use is not stated in the docs read; say only "does not retain customer data for inference by default (up to 30 days for reliability/abuse monitoring)"; U-08 stays UNVERIFIED                                                                                                                                              |
| O-08 | RR-01 likelihood                          | RESOLVED (round 10, evidence) | High                                                                                                                                                                                                                                                                                                                                |
| O-09 | Connect timeout                           | RESOLVED (round 10)           | No separate connect timeout; the 8 s timer covers request start (`create`) through the first chunk, so a hung connection is caught; the 30 s turn timeout bounds the rest                                                                                                                                                           |
| O-10 | Pydantic in the domain                    | RESOLVED (round 10)           | Pydantic models are allowed in the domain (schemas only); I/O, network and database libraries are not                                                                                                                                                                                                                               |
| O-11 | Tests that trail their code               | RESOLVED (round 10)           | Every test ships in the commit that introduces the code it guards (JWT matrix in commit 1, blocking-detector test in commit 4)                                                                                                                                                                                                      |
| O-21 | What the 8 s "first-token" timer measures | RESOLVED (round 10)           | It stops at the first chunk of any kind, including deliberation-only or tool-call chunks; the 30 s turn timeout bounds the total                                                                                                                                                                                                    |
| O-22 | Anthropic token-limit fields              | RESOLVED (round 10, evidence) | Anthropic lists both `max_tokens` and `max_completion_tokens` as fully supported (E10 corrected); the adapter sends `max_tokens`                                                                                                                                                                                                    |
| O-23 | Wiring outside `app/main.py`              | RESOLVED (round 10)           | `scripts/ingest.py` is the second, CLI-only composition root; the dependency-rule test allows exactly `app/main.py` and `scripts/ingest.py`                                                                                                                                                                                         |

### 8.2 Former gaps — all RESOLVED (round 10)

| ID   | Gap                                                | Status                                     | Decision                                                                                                                                                                                        |
| ---- | -------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| O-12 | HTTP 400 from the provider                         | RESOLVED (round 10)                        | `BadRequestError` (HTTP 400) → "System configuration error. Please contact support."                                                                                                            |
| O-13 | `finish_reason="content_filter"`                   | RESOLVED (round 10), AMENDED (round 11)    | → "AI service temporarily unavailable. Please try again." (round 11 replaces the round-10 last-resort mapping)                                                                                  |
| O-14 | Several tool calls in pass 1                       | RESOLVED (round 10)                        | Execute only the first, echo only that call in the pass-2 assistant message, log a warning                                                                                                      |
| O-15 | Missing-`exp` JWT case                             | RESOLVED (round 10)                        | The JWT matrix has 10 cases (adds missing `exp`)                                                                                                                                                |
| O-16 | `aclosing` and timeouts inside the generator chain | RESOLVED (round 10)                        | Every streaming async generator (the adapter stream inside `run_turn`, `run_turn` inside the consumer) is consumed inside `contextlib.aclosing`; no timeout context stays open across a `yield` |
| O-17 | Offline token counting for chunker tests           | RESOLVED (round 10), SUPERSEDED (round 11) | The injectable token counter was cut; tokenizer-dependent chunker tests carry the `model` marker                                                                                                |
| O-18 | Other `EMBEDDING_PROVIDER` values                  | RESOLVED (round 10)                        | Anything other than `sentence-transformers` fails fast at startup or ingestion with a configuration error                                                                                       |
| O-19 | `--docs-dir` vs `DOCS_DIR`                         | RESOLVED (round 10)                        | The CLI's `--docs-dir` overrides `IngestConfig.DOCS_DIR`                                                                                                                                        |
| O-20 | OpenRouter and OpenAI base URLs                    | RESOLVED (round 10)                        | OpenRouter `https://openrouter.ai/api/v1`; OpenAI `https://api.openai.com/v1`                                                                                                                   |

### 8.3 Unverified claims

Each is detailed with how and when it gets verified in [RISKS-ASSUMPTIONS.md](RISKS-ASSUMPTIONS.md) §3. Verified since v1 (no longer open): WebSocket Origin handling (E17, live); sentence-transformers truncation beyond `max_seq_length` (K02) and bge unit-norm output (K03), both measured by running code.

| ID   | Claim (UNVERIFIED)                                                                                                                                                                                                                          |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| U-01 | Groq supports tool calling together with `stream=true` (docs list both, not the combination; E05)                                                                                                                                           |
| U-02 | Groq's streamed tool-call deltas follow the SDK shape and no raw deliberation reaches `content` (E07, K05)                                                                                                                                  |
| U-03 | `max_tokens` bounds deliberation (reasoning) tokens, on Groq and other providers                                                                                                                                                            |
| U-04 | Deliberation tokens count toward Groq rate limits / usage (not stated, E09)                                                                                                                                                                 |
| U-05 | `tool_choice="none"` is honoured by every provider; Anthropic's compatibility layer does not list top-level `tool_choice` (E10)                                                                                                             |
| U-06 | Tools and streaming together work on Gemini's OpenAI-compatible endpoint (beta), Ollama and OpenRouter (E05)                                                                                                                                |
| U-07 | Narrowed post-review: `GROQ_EXTRA_PARAMS` `{"reasoning_effort":"low"}` is never sent to other providers, so only a Groq model outside E09's list (GPT-OSS, Qwen 3.8 27B) could reject it (UNVERIFIED); clear `GROQ_EXTRA_PARAMS` when changing `GROQ_MODEL` to such a model |
| U-08 | Groq does not use API data for training (not stated in the docs read, E05; O-07)                                                                                                                                                            |
| U-09 | Prompt-driven behaviour of the live model: exact refusal wording, inline citation format, grade-independence statement, tool use only for personal questions, plain text, and an in-dialogue explanation after an IDOR denial result (O-01) |
| U-10 | The 2.0× OCR paragraph threshold holds on other machines (measured once, E02)                                                                                                                                                               |
| U-11 | A browser's close handshake behaves like the Python client in the close-race test (E13 limits)                                                                                                                                              |
| U-12 | Qdrant has collection-level metadata (the design does not depend on it: `model_name` is in every payload)                                                                                                                                   |
| U-13 | `opencv-python` can be swapped for the headless build via uv `override-dependencies` (not planned)                                                                                                                                          |
| U-14 | The default offline suite runs in < 2 s (K08 estimate)                                                                                                                                                                                      |
| U-15 | The revised implementation estimate: 305 minutes best case, up to 360 minutes for commits 1–7, plus an estimated 20–30 minutes of SIGN-OFF day-1 checks that no commit already covers — about 6–6.5 hours in total (IMPLEMENTATION-PLAN §5); for this build the 2-hour run replaces it (pre-build, D-78) |
| U-16 | Model availability and free-plan limits recorded on 2026-10-04 (E05) still hold at evaluation time                                                                                                                                          |
