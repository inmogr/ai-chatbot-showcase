# Decision Log

This log records every planning decision: what was decided, which alternatives were rejected, the reason for the choice, the reason against each alternative, the evidence, and whether the decision was later reversed, superseded or restated. D-01…D-21 keep the IDs they were given when first decided; D-22…D-51 are IDs assigned here to the later decisions (the K files did not number them) so the other deliverables can reference them; D-52…D-66 record the round-10 resolutions of the consolidation items O-01…O-23 (version 1.1); D-67…D-75 record the round-11 accuracy changes (version 2); D-76…D-77 and the in-place notes marked "post-review" record the corrections made after the deliverables were checked against the repository on 2026-10-04; D-78…D-85 and the notes marked "pre-build" record the corrections made before the 2-hour build. The appendix lists superseded statements that must not be reused.

Sources: `inputs/attach/DECISIONS-REGISTER.md` (canonical), `knowledge/K02-decisions.md` (D-01…D-21), `K03`–`K08` (later decisions), `K09` corrections; round state records `inputs/attach/C05-STATE.md`–`C08-STATE.md` (for recorded reasons); evidence E01–E15; `knowledge/K10-consolidation.md` (round-10 resolutions; its reviewer note overrides the raw replies); `knowledge/K11-accuracy.md` (round-11 changes); evidence E17; `inputs/00-brief.md`. "Brief README §N" = requirement section N of the assignment README; "brief §7" = the measured facts in `inputs/00-brief.md`.

## Changed decisions at a glance

| ID | Change | Replacement |
|---|---|---|
| D-02 | REFINED | Canonical prompt rule 6 states grade-independence explicitly |
| D-05 | RESTATED justification | Reproducibility + data minimisation (hosted LLM still sees ≤ 4 role-filtered excerpts, disclosed) |
| D-06 | CONFIRMED (earlier "< 50 characters" wording void) | `len(text.strip()) == 0` |
| D-09 | Wording replaced ("simulated 403" → deny on mismatch); mechanism RESOLVED in round 10 | Orchestrator check before the tool; denial result to pass 2 (D-52) |
| D-11 | CORRECTED (filter operator is `<=`) | Unchanged otherwise |
| D-14 | CORRECTED | `auth_failed` first, then close 1008 |
| D-15 | SUPERSEDED | 10 s auth timeout (D-39) |
| D-19 | REVERSED | Inline model citations; checked by the manual checklist (the offline eval was cut with D-72; corrected pre-build, D-80) |
| D-20 | CORRECTED | `department` and `level` withheld; `sub` still given to the LLM for the IDOR check |
| D-21 | REVERSED | Current-question retrieval; bounded history to the LLM only (D-36) |

### Corrected before the 2-hour build (2026-10-04, pre-build)

| Decision | Change |
|---|---|
| D-78 | NEW: two-hour execution layer — pre-flight before the clock, time boxes, tripwires, native execution with background ECC reviews, tracker |
| D-79 | NEW: one function per test (twenty names fold into fourteen tests) |
| D-80 | NEW: citations checked by the manual checklist; the "offline eval" wording is removed (D-19 corrected) |
| D-81 | NEW: commit 6 ends with three real-run failure drills |
| D-82 | NEW: the live cadence test asserts the frame count, not a 0.1 s spread |
| D-83 | NEW: `uvicorn[standard]`, dev `httpx`, mypy override policy (D-49 amended) |
| D-84 | NEW: `scripts/ws_probe.py` and `scripts/scan_secrets.py` named |
| D-85 | NEW: five review-focus test cases |

### Corrected after the 2026-10-04 review (post-review)

| Decision | Change |
|---|---|
| D-26 | The reason for Qdrant over Chroma is stated; no head-to-head comparison was run |
| D-35, D-47, D-59 | `LLM_EXTRA_PARAMS` → `GROQ_EXTRA_PARAMS`, sent only when `LLM_PROVIDER=groq` |
| D-49 | ruff gains `C90` (max-complexity 10), so the rubric's "small functions" has a check |
| D-76 | NEW: the project root is `miniragchatbot/` |
| D-77 | NEW: submission is a push to the CodeSubmit `origin`; whether `deliverables/` ships is OPEN (owner decision) |

### Changed by the round-11 accuracy changes

| Decision | Change |
|---|---|
| D-42 | SUPERSEDED by the consolidated catalog (D-67) |
| D-37, D-40, D-59 | Error strings consolidated; `content_filter` → "AI service temporarily unavailable. Please try again." (D-67) |
| D-63 | SUPERSEDED: injectable token counter cut (D-70) |
| D-36 | OPTIONAL: conversation memory built last, only if time remains; the core is stateless (D-73) |
| D-46, D-51 | Sync transport tests, timeouts as parameters, isolated collection (D-68); one-test blocking proof (D-69); coverage gate (D-71); golden-set eval cut (D-72) |
| D-27 | Exec/finance worded as a consequence of the formula, not a brief rule (D-74) |
| D-16, D-23 | Truncation and unit-norm marked as verified by running code (D-75) |

### Amended by the round-10 resolutions

| Decision | Amendment |
|---|---|
| D-12 | The JWT matrix gains a missing-`exp` case (D-61) |
| D-22 | The chunker takes an injectable token counter (D-63) |
| D-23, D-47 | `EMBEDDING_PROVIDER` other than `sentence-transformers` fails fast; `--docs-dir` overrides `DOCS_DIR` (D-64) |
| D-29 | OpenRouter and OpenAI base URLs recorded (D-65) |
| D-30, D-35 | Groq data wording and Anthropic token-limit fields follow the evidence (D-55) |
| D-31, D-37 | The 8 s timer runs to the first chunk of any kind, no connect timeout (D-56); HTTP 400 and `content_filter` mappings (D-59) |
| D-32 | Only the first of several tool calls is executed (D-60) |
| D-45 | One `app/domain/ports.py` (D-53); pydantic schemas allowed in the domain (D-57); `scripts/ingest.py` as the second composition root (D-66) |
| D-48 | `aclosing` around the adapter stream inside `run_turn` as well (D-62) |
| D-49 | mypy runs as `uv run mypy app scripts` (D-54) |
| D-50, D-51 | Tests ship with the code they guard (D-58); flat files and K09 names (D-53); 10-case JWT matrix (D-61) |

---

## Product and protocol decisions (D-01…D-21)

### D-01 — The LLM handles the "Senior" vs numeric-grade gap · KEPT
- **Decision:** No grade mapping in code; the model explains that the tool's qualitative grade ("Senior") does not map to the numeric grades some policies use.
- **Rejected:** hard-coding a Senior→number mapping; overriding the tool data.
- **Why:** keeps the architecture clean; strict grounding lets the model point out the data gap.
- **Why not the alternatives:** any mapping would be data that exists neither in the brief nor in the corpus.
- **Evidence:** brief README §5 (`"grade": "Senior"`); `travel_reimbursement.pdf` ("Grade 4 and above", "Grade 5 and above").
- **Status:** kept (A-03).

### D-02 — Strict grounding for false-premise questions · KEPT, refined
- **Decision:** answers come from the policy text regardless of the user's premise ("given my grade").
- **Rejected:** general prompt guards against false premises.
- **Why:** grounding outputs the flat 22-day entitlement regardless of the premise.
- **Why not the alternatives:** not needed — grounding already outputs the flat entitlement whatever the premise.
- **Evidence:** brief README §5 example question; `leave_policy.pdf` ("Full-time employees are entitled to 22 working days").
- **Status:** kept; the canonical prompt (register) adds rule 6, a targeted instruction to state when an entitlement does not depend on grade (A-04).

### D-03 — 1-based page numbers read from the PDF · KEPT
- **Decision:** `page` is the 1-based page index taken during extraction.
- **Rejected:** hard-coding `page=1`.
- **Why:** correct for multi-page documents without failing silently.
- **Why not the alternatives:** a constant mislabels any multi-page document.
- **Evidence:** brief README §1 ("page number if applicable"); brief §7 measured facts (all PDFs are 1 page).
- **Status:** kept (A-05, FR-11).

### D-04 — CLI ingestion script · KEPT
- **Decision:** `python -m scripts.ingest --docs-dir ./docs`, separate from the server.
- **Rejected:** a FastAPI ingestion route.
- **Why:** isolates CPU-heavy OCR and embedding from the async server; no auth needed.
- **Why not the alternatives:** a route runs heavy work in the server process and needs its own protection.
- **Evidence:** brief README §1 ("Write a script or endpoint").
- **Status:** kept (A-06, FR-05).

### D-05 — Local OCR with RapidOCR · RESTATED
- **Decision:** RapidOCR 3.9.2 + onnxruntime (added explicitly) with the ONNX models bundled in the wheel; the page is rendered by pypdfium2 at 300 dpi.
- **Rejected:** hosted OCR/vision APIs; tesseract + poppler; DocTR and EasyOCR (download weights at runtime, per the pre-verification comparison, which marks DocTR's download UNVERIFIED); ocrmac (macOS only); `rapidocr-onnxruntime` 1.4.4 (legacy, Python < 3.13).
- **Why (restated):** reproducible — no account, key, cost or network call for OCR, models bundled; data minimisation — whole documents never leave the host, and at query time only up to k = 4 role-filtered chunks reach the hosted LLM, which the README discloses.
- **Why not the alternatives:** hosted OCR needs an account and key and sends whole documents off-host; tesseract/poppler add a system-install step (neither is installed on the candidate's machine, brief §7); runtime weight downloads need network at ingestion time; ocrmac does not run on Linux.
- **Evidence:** E01 (300 dpi: 18 lines, min confidence 0.984, mean 0.993, OCR 1.90 s, engine init 0.88 s, bundled models used; 150 dpi min confidence 0.655); K02 verified (rapidocr 3.9.2 Apache-2.0 bundles PP-OCRv6 det/rec small + cls ONNX models, ~32 MB, and does not declare onnxruntime).
- **Status:** RESTATED. The earlier "cloud APIs would leak confidential data" rationale is not used: the hosted LLM still receives role-filtered excerpts (E05 consequence), so the honest claim is minimisation, not secrecy.

### D-06 — OCR trigger `len(text.strip()) == 0` · CONFIRMED
- **Decision:** OCR a page only when its text layer is empty after stripping.
- **Rejected:** a character threshold such as "< 50".
- **Why:** targets the image-only page without duplicating text on mixed pages.
- **Why not the alternatives:** an arbitrary limit is a magic number and risks OCR-ing pages that already have a short text layer, ingesting their text twice.
- **Evidence:** E01 (text-layer characters 1,433–1,619 for the six text PDFs; 0 for the scan).
- **Status:** CONFIRMED; every "< 50 characters" statement is void.

### D-07 — pypdfium2 for text extraction · KEPT
- **Decision:** pypdfium2 (BSD-3 / Apache-2.0).
- **Rejected:** PyMuPDF.
- **Why:** permissive licence for a corporate backend.
- **Why not the alternatives:** PyMuPDF 1.28.2 is AGPL / commercial dual-licensed.
- **Evidence:** K02 verified on PyPI (pypdfium2 5.13.0).
- **Status:** kept.

### D-08 — Sequential turns with uvicorn's queue · KEPT
- **Decision:** one turn at a time per connection; frames sent meanwhile wait in uvicorn's queue.
- **Rejected:** discarding inputs; cancelling the running turn; replying `error` while streaming; concurrent turns.
- **Why:** safe and simple; matches the client's single `currentBotMsg`.
- **Why not the alternatives:** dropping loses user input; an `error` mid-stream splits one answer into two bubbles around a red error; interleaved streams cannot render in the client; cancellation adds event logic.
- **Evidence:** E11 (`ws_max_queue` = 32 buffered messages, then TCP backpressure; nothing dropped).
- **Status:** kept (A-09, D-41).

### D-09 — Check the tool's `user_id` against the JWT · KEPT (mechanism resolved in round 10, D-52)
- **Decision:** keep the brief's `get_employee_context(user_id)` signature; compare the model-supplied `user_id` with the JWT `sub`; deny on mismatch.
- **Rejected:** a zero-parameter schema; silently overwriting the argument with `sub`.
- **Why:** matches the required signature and stops IDOR at the execution boundary.
- **Why not the alternatives:** a zero-parameter tool does not match the brief's `get_employee_context(user_id)` signature; no separate reason is recorded against the silent overwrite (K01 had first proposed it).
- **Evidence:** brief README §5.
- **Status:** kept as deny-on-mismatch (register); the "simulated 403" wording is dropped; round 10 (D-52): the orchestrator checks before calling the tool and sends the denial result to pass 2.

### D-10 — Retrieval before generation · KEPT
- **Decision:** deterministic retrieval precedes the LLM on every turn.
- **Rejected:** giving the LLM a search tool.
- **Why:** the model should not decide when to search; the brief allows one tool only.
- **Evidence:** brief README §3 and §5.
- **Status:** kept (A-11).

### D-11 — Strict claim types · KEPT (corrected)
- **Decision:** `sub` non-empty string; `department` non-empty free string (unknown departments see only `hr` content); `level: Annotated[StrictInt, Field(ge=1)]` with no upper bound.
- **Rejected:** rejecting unknown departments; lax integer parsing.
- **Why:** upholds the `hr` exception for any department and protects the `<=` filter from type tricks.
- **Why not the alternatives:** lax `int` turns JSON `true` → 1, `"2"` → 2, `2.0` → 2.
- **Evidence:** K02 verified (pydantic 2.13.5; `StrictInt` rejects all three).
- **Status:** kept (A-12, A-23).

### D-12 — `exp` is required · KEPT
- **Decision:** `options={"require": ["sub", "exp", "department", "level"]}`.
- **Rejected:** PyJWT defaults.
- **Why:** no immortal tokens; the brief requires expired tokens to fail.
- **Why not the alternatives:** PyJWT decodes a token without `exp` by default.
- **Evidence:** K02 verified (PyJWT 2.15.1 raises `MissingRequiredClaimError`).
- **Status:** kept; the JWT matrix now has a missing-`exp` case (D-61).

### D-13 — `sub` is required · KEPT
- **Decision:** `sub` is required and becomes `user_id`.
- **Rejected:** using `email`.
- **Why:** `sub` feeds the IDOR check and `auth_success.user_id`; `email` is unused.
- **Evidence:** brief README §4 payload; the client shows `user.user_id || user.sub`.
- **Status:** kept.

### D-14 — The first frame must be auth · KEPT (corrected)
- **Decision:** anything but a valid auth frame first → `auth_failed`, then close.
- **Rejected:** ignoring non-auth frames; closing silently.
- **Why:** enforces the handshake and returns the mandated failure ("missing JWT → send `auth_failed` and close").
- **Evidence:** brief README §2 and §7; E13.
- **Status:** kept, corrected to send `auth_failed` before closing; close code 1008 (D-39).

### D-15 — 3-second auth timeout · SUPERSEDED
- **Decision (original):** 3 s for the first frame.
- **Rejected (original):** infinite idle sockets.
- **Why (original):** protect against idle-socket exhaustion; the client sends auth immediately on open.
- **Status:** SUPERSEDED by 10 s (D-39): 3 s was a planning assumption, not a brief rule, and the brief allows wscat/Postman clients where a person pastes the token.

### D-16 — 2,000-character message cap · KEPT
- **Decision:** strip leading/trailing whitespace, then require 1–2,000 characters (`StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)`).
- **Rejected:** uvicorn's default limit.
- **Why:** avoids silent truncation in the embedder and protects LLM rate limits.
- **Why not the alternatives:** uvicorn's default `ws_max_size` is 16 MiB; sentence-transformers silently truncates beyond `max_seq_length` (512).
- **Evidence:** K02 (truncation beyond `max_seq_length` verified by running code); E12 (`Field(min_length=1)` accepts `" "`).
- **Status:** kept (A-15).

### D-17 — Unauthorised documents are treated as non-existent · KEPT
- **Decision:** never confirm that a restricted document exists; uniform refusal.
- **Rejected:** telling the user a document exists but is restricted.
- **Why:** users "only see documents they are authorised to access".
- **Status:** kept (A-16); the filter keeps restricted chunks out of the prompt; refusal wording is prompt-driven (U-09).

### D-18 — Every message goes through RAG · KEPT
- **Decision:** no intent classifier; greetings are handled by the prompt.
- **Rejected:** an intent classifier for greetings.
- **Why:** linear, simple pipeline at small scale.
- **Status:** kept (A-17; prompt rule 1).

### D-19 — Server-built citations · REVERSED
- **Decision (original):** after the model's stream, the server sent a plain-text "Sources Consulted" block built from chunk metadata as `stream` frames before `done`.
- **Replacement:** the model cites inline from the excerpt labels, e.g. `[leave_policy.pdf, page 1]`; the manual checklist checks each answer row's expected citation (the offline eval planned here was cut with the golden set, D-72; corrected pre-build, D-80).
- **Why the replacement:** a server block must know whether the answer is a refusal, which needs the stream buffered (breaks token-by-token streaming); restricted chunks never reach the model, so a wrong citation is a hallucination, not a leak.
- **Why not a runtime guard:** tokens are already sent before any check over buffered text completes; it cannot work without buffering.
- **Evidence:** K04 corrections.
- **Status:** REVERSED.

### D-20 — Withhold security claims from the LLM · KEPT (corrected)
- **Decision:** `department` and `level` are withheld from the LLM; `sub` goes into the system prompt.
- **Rejected:** giving the LLM all claims.
- **Why:** stops the model confusing security `level` with HR grade or reasoning about access; `sub` is needed for the tool.
- **Status:** kept (A-19).

### D-21 — Query concatenation for memory · REVERSED
- **Decision (original):** embed `Q(t-1) + Q(t)` for retrieval.
- **Replacement:** retrieval uses the current question only; a bounded history goes to the LLM only (D-36); an LLM query rewriter is a "with more time" item.
- **Why the replacement:** measured — concatenation kept follow-ups at 4/4 but dropped topic switches to 1/3 at hit@1 (one lost the right document from the top 4), against 3/3 for current-only.
- **Why not a rewriter:** a second LLM call per turn adds latency, quota use and a failure point without fixing a measured problem.
- **Evidence:** E04.
- **Status:** REVERSED.

---

## Ingestion decisions

### D-22 — Structural chunking · KEPT
- **Decision:** text PDFs split at lines matching `^\d+\.\s+[A-Z]` (first line = title; newline kept after each heading; wrapped lines joined with spaces); the scan split where the vertical gap exceeds 2.0× the median line gap (top-most box = title; lines joined with spaces); title prefixed to every chunk; overlap 0; fallback only for a body over 150 bge tokens: k = ceil(tokens / 150), sentences split with `(?<=[.!?])\s+(?=[A-Z])` and grouped evenly into k parts. Result: 42 chunks (36 + 6).
- **Rejected:** fixed-size or recursive character windows with overlap; nltk `sent_tokenize`; a bare `^\d` heading pattern; an initials guard in the sentence regex.
- **Why:** one chunk per policy section, far inside the 512-token window, each carrying its document title.
- **Why not the alternatives:** fixed windows cut rules mid-sentence and their numbers would be tutorial values; overlap repeats text across the 4 retrieval slots; nltk needs `punkt` data downloaded at runtime; wrapped lines start with digits in three files ("2026 peer group…", "2,500 additionally…", "180 elsewhere…"); an initials guard is YAGNI (none in the corpus) — the "John D. Doe" split is documented by a test.
- **Evidence:** E01 (sections 35–74 bge tokens; documents 279–364; corpus ~2,157); K03 (text layer wraps with `\r\n` about every 95 characters); E02 (paragraph gaps 41–55 px = 2.9×–3.9× the 14 px median; in-paragraph 0.7×–1.4×; the regex finds 17 correct sentences).
- **Status:** kept.

### D-23 — Embedding model and query encoding · KEPT
- **Decision:** `BAAI/bge-small-en-v1.5` (sentence-transformers, CPU); no query prefix; `normalize_embeddings=True` is redundant; the first run downloads the model automatically.
- **Rejected:** `all-MiniLM-L6-v2`; the bge query instruction prefix; a hosted embedding API.
- **Why:** the `.env.example` default; 512-token window; 384 dimensions; output already unit-norm (CLS pooling → Normalize).
- **Why not the alternatives:** MiniLM has a 256-token window and encoded a 13-word query slower (15.2 vs 6.8 ms median); the prefix gave the same hits with slightly lower scores.
- **Evidence:** E01 (bge first load 21.7 s; warm encode ~7 ms median, p95 15–18 ms); E03 (no prefix: hit@1 13/15, hit@3 15/15); K03 (unit-norm output verified by running code).
- **Status:** kept (A-21: first run needs network, ~130 MB).

### D-24 — Ingestion run semantics · KEPT
- **Decision:** payload `text`, `department`, `access_level` (int), `source_file`, `page` (1-based), `model_name`, `chunk_index`; point id `uuid5(NAMESPACE_URL, f"file://{source_file}/{page}#{chunk_index}")`; collection recreated every run; disk validated against the 7-row table (missing mapped file, unmapped `*.pdf`, path/casing mismatch → fail); Qdrant pinged before models load; library code raises domain errors (e.g. `IngestConfigError`) and only the CLI maps them to exit 1; corpus expectations (42, 6, fallback unused) live only in tests.
- **Rejected:** incremental upserts with versioning; normalising folder casing; `SystemExit` inside library code; runtime count assertions in the ingestion script.
- **Why:** no stale chunks without versioning logic; reproducible ids; RBAC metadata cannot drift silently; testable library.
- **Why not the alternatives:** normalising casing masks a deployment error; `SystemExit` makes tests assert process exits; corpus counts in product code break on any other document set.
- **Evidence:** K03 corrections.
- **Status:** kept.

### D-25 — Model-swap detection and startup checks · KEPT
- **Decision:** every payload stores `model_name`; at startup the server checks that the collection exists, its vector size equals the model dimension (384) and a sampled payload's `model_name` equals `EMBEDDING_MODEL`; a failed check raises in the lifespan and uvicorn exits with code 3.
- **Rejected:** collection-level metadata; no check.
- **Why:** swapping `EMBEDDING_MODEL` without re-ingesting silently ruins retrieval even when dimensions match.
- **Why not the alternatives:** collection-level metadata support is unverified (U-12).
- **Evidence:** E01 (bge-small and MiniLM are both 384-d); K04 verified (uvicorn 0.54.0: lifespan startup exception → `STARTUP_FAILURE` = 3; tests assert the lifespan raises).
- **Status:** kept.

---

## Retrieval decisions

### D-26 — Qdrant server through AsyncQdrantClient · KEPT
- **Decision:** Qdrant server in Docker (`qdrant/qdrant:v1.19.1`) via `AsyncQdrantClient(url=…)`; ingestion writes with the sync `QdrantClient`.
- **Rejected:** Qdrant embedded/local mode (`QdrantLocal`, `AsyncQdrantLocal`); Chroma local persistent mode (listed as an option in K02; no evidence-based comparison is recorded).
- **Why:** native async I/O; filters evaluated inside the database index.
- **Why not the alternatives:** local mode is pure Python + numpy, evaluates filters in Python and does no thread offloading, so it blocks the event loop and is not DB-layer filtering. Chroma was not compared head-to-head (post-review): Qdrant was kept because `AsyncQdrantClient` is natively async and the brief's own `.env.example` points the evaluator at Qdrant in Docker (`docker run -p 6333:6333 qdrant/qdrant`); Chroma's local client is synchronous (it would need `asyncio.to_thread`), and a second vector adapter is code the rubric does not ask for.
- **Evidence:** K04 verified in qdrant-client 1.19.1 source; E03 (filtered query median 1.7 ms, p95 2.3 ms); the brief's `.env.example`.
- **Status:** kept; post-review: Chroma reason stated, no Chroma adapter.

### D-27 — RBAC filter expression · KEPT
- **Decision:** inside `query_points`: `Filter(must=[FieldCondition(key="department", match=MatchAny(any=[user.department, "hr"])), FieldCondition(key="access_level", range=Range(lte=user.level))])`; payload indexes keyword(`department`), integer(`access_level`); Reading A; no finance exception for executives.
- **Rejected:** Reading B (the `hr` exception also skips the level); post-retrieval filtering; a second exception for executives.
- **Why:** one `must` clause expresses "department ∈ {own, hr} and level ≤ own" — the brief's "cleanest way"; it fails closed on malformed payloads.
- **Why not the alternatives:** Reading B lets `emp-001` read the manager-only review; post-filtering is forbidden and starves the top-k; a second exception overrides explicit authorisation logic (raised as the README improvement instead).
- **Evidence:** E03 (0 restricted-file leaks over 24 filtered queries; points lacking `department` or `access_level`, or with `access_level "1"`, never returned; a float `1.0` probe was returned → ints only); visible counts 12/18/24/30.
- **Status:** kept (A-01, A-02); the absence of finance access for executives is the consequence of this expression plus the single `hr` exception, not a rule the brief states (D-74).

### D-28 — Retrieval parameters · KEPT
- **Decision:** cosine distance, k = 4, no score threshold, current question only.
- **Rejected:** k = 8; a similarity threshold.
- **Why:** high recall (hit@3 15/15) for ~300–360 prompt tokens.
- **Why not the alternatives:** k = 8 hands `emp-001` (12 visible chunks) most of their accessible universe every turn; top-1 scores overlap (answerable 0.556–0.869, median 0.782; no allowed answer 0.412–0.590, median 0.512), so any threshold misfires — refusal relies on the prompt.
- **Evidence:** E03; K05 corrections (token estimate).
- **Status:** kept (README tradeoff).

---

## LLM-layer decisions

### D-29 — One OpenAI-compatible adapter, provider by configuration · KEPT
- **Decision:** one adapter over `openai.AsyncOpenAI`; `LLM_PROVIDER` (default `groq`); per-provider variables exactly as in `.env.example`; `/v1` appended to `OLLAMA_BASE_URL`; startup fails when the selected provider lacks its key (except Ollama) or model.
- **Rejected:** native SDK adapters (Groq, Gemini, Anthropic); a generic `LLM_BASE_URL` setting.
- **Why:** every listed provider documents an OpenAI-compatible endpoint; the brief asks for a thin swappable interface.
- **Why not the alternatives:** native adapters add code without need; base URLs belong to the per-provider table.
- **Evidence:** E05; E10 (Anthropic's layer exists but is "not considered a long-term or production-ready solution").
- **Status:** kept (A-22).

### D-30 — Default Groq `openai/gpt-oss-120b` · KEPT
- **Decision:** Groq with `GROQ_MODEL=openai/gpt-oss-120b`, the only model default in code.
- **Rejected:** `llama-3.3-70b-versatile`; `gemini-2.0-flash`; OpenRouter `meta-llama/llama-3.3-70b-instruct:free`; Gemini's free tier; `qwen/qwen3.8-27b` on Groq; Ollama as the default.
- **Why:** on Groq's free plan (30 RPM, 1K RPD, 8K TPM, 200K TPD); tool use documented; deliberation is documented to arrive in a separate `reasoning` field, so a content-only adapter should not show it (not live-verified, U-02); Groq does not retain customer data for inference by default (up to 30 days for reliability/abuse monitoring); training use is not stated (U-08).
- **Why not the alternatives:** llama-3.3-70b-versatile is tagged Enterprise and missing from the free-plan table; gemini-2.0-flash is shut down; the OpenRouter `:free` llama model is absent; Gemini free-tier content is "used to improve our products"; qwen3.8 defaults to raw format (deliberation inside `content`) and raw + tools returns HTTP 400; local models were excluded as evidence sources, so Ollama stays a swap-in.
- **Evidence:** E05, E09.
- **Status:** kept; tool calling and streaming are each documented, but their combination is not stated in the docs and was not live-verified (U-01); gpt-oss has no parallel tool calls (not needed).

### D-31 — LLM port and stream mechanics · KEPT
- **Decision:** `def stream_chat(messages, tools, tool_choice) -> AsyncIterator[TextDelta | ToolCallRequest]`, `ToolCallRequest(id, name, raw_arguments, parsed_arguments)`; the adapter yields each text delta at once, accumulates tool deltas per `index` (id/name set once, argument fragments appended, parsed at the end), skips empty-`choices` chunks, closes the stream with `async with`, applies the 8 s first-token timeout and maps SDK errors to catalog errors; only the transport touches the WebSocket.
- **Rejected:** an LLM function that sends frames; buffering pass-1 events.
- **Why:** in the SDK's streamed types only `index` is required; `id`/`name` may appear in a single fragment; arguments are JSON pieces parseable only at the end; a chunk may carry content, tool calls, both or neither.
- **Why not the alternatives:** frames from the LLM layer break the layering; buffering is fake streaming (R-03).
- **Evidence:** E07; E14 (`AsyncStream` supports `async with`; `__aexit__` awaits `close()`).
- **Status:** kept (U-02); round 10: the 8 s timer runs from `create` to the first chunk of any kind (D-56) and the stream is consumed inside `aclosing` (D-62).

### D-32 — Two passes, at most one tool round · KEPT
- **Decision:** pass 1 with the tool and `tool_choice="auto"`; on a tool call: validate, IDOR check, run; pass 2 with the same tools and `tool_choice="none"`; then `done`.
- **Rejected:** multi-round tool loops; removing tools in pass 2.
- **Why:** a fixed sequence in code bounds latency and cost and is part of the security posture; `"none"` prevents a second tool call.
- **Evidence:** E10 (Anthropic top-level `tool_choice` not listed).
- **Status:** kept (U-05); round 10: only the first of several tool calls is executed (D-60); an IDOR mismatch skips the tool but pass 2 still runs (D-52).

### D-33 — Parallel tool: TaskGroup inside a timeout · KEPT
- **Decision:** `asyncio.TaskGroup` over the three fetches inside `asyncio.timeout(2.0)`; any failure or timeout → `ToolExecutionError`; proof by test spies and elapsed < 1.35 s; no timing code in production.
- **Rejected:** sequential awaits; plain `asyncio.gather`; `gather(return_exceptions=True)`; a lower-bound timing assertion.
- **Why:** TaskGroup cancels the siblings on the first failure and raises an ExceptionGroup; the timeout cancels all tasks.
- **Why not the alternatives:** sequential takes 3.003 s; plain gather raises at once but leaves siblings running to completion (orphans); `return_exceptions=True` returns partial results after 1.0 s; a lower bound proves nothing about overlap.
- **Evidence:** E06 (TaskGroup 1.001 s; ×20 median 1.0014 s, max 1.0016 s); E08 (`except` and `except*` cannot share a `try`; no `return` in `except*`).
- **Status:** kept.

### D-34 — Canonical prompt and message layout · KEPT
- **Decision:** the canonical system prompt (ARCHITECTURE §8) with `{user_id}` = JWT `sub`; excerpts in the user message as `<excerpt source="…" page="…">` blocks before "Question: …"; inline citations; plain text; fixed refusal.
- **Rejected:** a shorter draft prompt without the tool-use rule; Markdown output.
- **Why:** covers excerpts and tool data, greetings, refusal, citation labels, plain text (the client renders text literally), excerpts as data, grade-independent entitlements, and when to call the tool.
- **Why not the alternatives:** without rule 4 the model has no instruction on when or how to call the tool.
- **Status:** kept. Security does not depend on the prompt: RBAC filter, IDOR check, fixed two-pass sequence and JWT validation are code.

### D-35 — Output limit and provider extras · KEPT
- **Decision:** `max_tokens` 1500 (`MAX_TOKENS`); provider-specific fields from optional JSON `GROQ_EXTRA_PARAMS`, sent only when `LLM_PROVIDER=groq` and the variable is set; `.env.example` sets `{"reasoning_effort":"low"}` inside the Groq block.
- **Rejected:** `max_completion_tokens`; a 512 cap; hard-coded `reasoning_effort`; a provider-wide `LLM_EXTRA_PARAMS` (post-review: it stays set when a reviewer switches `LLM_PROVIDER`, and a provider that rejects `reasoning_effort` would answer HTTP 400 → "System configuration error. Please contact support." — U-07).
- **Why:** `max_tokens` has the widest support; fields some providers reject stay out of code and are scoped to the provider they were written for, like `GROQ_API_KEY` / `GROQ_MODEL`.
- **Evidence:** E09 (gpt-oss `reasoning_effort` low|medium|high); E10, corrected (Anthropic lists `max_tokens` and `max_completion_tokens` as fully supported and ignores `reasoning_effort`; D-55).
- **Status:** kept (U-03, U-07); post-review: renamed to `GROQ_EXTRA_PARAMS` and scoped to Groq.

### D-36 — Conversation history window · KEPT
- **Decision:** last 3 question/answer pairs of final plain text, sent only to the LLM as alternating user/assistant messages; appended by the consumer only after `done` was sent; `run_turn` receives an immutable tuple snapshot; excerpts and tool messages are never stored.
- **Rejected:** full history; storing excerpts or tool payloads; appending a placeholder answer.
- **Why:** bounded tokens (pass-1 input ~1,000–1,100 tokens with N = 3, against an 8K TPM free plan); failed turns do not pollute context.
- **Evidence:** K05 and K07 corrections; E05.
- **Status:** OPTIONAL (round 11, D-73): built last, only if time remains; the core pipeline is stateless.

### D-37 — LLM failure policy · KEPT
- **Decision:** one fixed catalog string per failure; no retries; 401 and 404 → configuration message; 429 → busy message; 5xx / connection → unavailable message; 8 s first-token or 30 s turn → timeout message; the SDK's own `APITimeoutError` (a subclass of `APIConnectionError`) also maps to the timeout message and is caught before the connection mapping (C06-STATE); mid-stream failure, empty output and `length` each have their own text.
- **Rejected:** retries with backoff; the earlier per-failure strings; treating 404 as transient.
- **Why:** interactive turn; free-tier retry-after is too long; partial text cannot be replayed over the WebSocket without duplicate output; retrying a 404 cannot help.
- **Status:** kept (catalog: ARCHITECTURE §10); round 10 adds HTTP 400 and `content_filter` mappings (D-59) and drops any separate connect timeout (D-56); round 11 consolidates the strings (D-67).

### D-38 — Confidentiality disclosure · KEPT
- **Decision:** the README states that OCR and embeddings are local, that up to 4 role-filtered excerpts per turn (including "Executive Restricted" strategic-plan text for executives) reach the hosted LLM, and that `LLM_PROVIDER=ollama` keeps inference local.
- **Why:** the hosted LLM sees retrieved chunks — the same concern that ruled out hosted OCR.
- **Evidence:** E05 ("Consequence to analyse").
- **Status:** kept.

---

## WebSocket-session decisions

### D-39 — Auth handshake · KEPT
- **Decision:** accept, then wait `AUTH_TIMEOUT_SECONDS` = 10 for the first frame; `jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "exp", "department", "level"]}, leeway=10)`; catch only `jwt.PyJWTError` and `ValidationError`; coarse `auth_failed` texts with details only in logs; send `auth_failed`, then `close(code=1008)` guarded by `except WebSocketDisconnect` only; `authenticate()` returns claims or `None`.
- **Rejected:** 3 s (D-15); detailed reasons to the client; matching `RuntimeError` message strings on the close path.
- **Why:** 10 s fits manual token pasting; 1008 is Policy Violation; the close race is clean.
- **Evidence:** E13 (50/50 races: client saw 1008; 0 server exceptions).
- **Status:** kept (A-13, A-14, A-24).

### D-40 — Inbound frame validation · KEPT
- **Decision:** one discriminated `TypeAdapter(Annotated[AuthFrame | MessageFrame, Field(discriminator="type")]).validate_json`; `text` uses `StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)`; extra fields ignored; errors mapped from `errors()[0]["type"]` and `loc[-1] == "text"`.
- **Rejected:** `Field(min_length=1)`; matching `loc == ("text",)`.
- **Why:** one parse yields typed frames and precise error types.
- **Why not the alternatives:** `Field(min_length=1)` accepts `" "`; in the discriminated union the location is `("message", "text")`.
- **Evidence:** E12, E14.
- **Status:** kept; round 11 maps every authenticated-state validation failure to "Invalid message structure" or the length message (D-67).

### D-41 — Sequential loop, disconnect and shutdown · KEPT
- **Decision:** no separate turn task; a disconnect surfaces as `WebSocketDisconnect` (1006) on the next send and unwinds the turn; the LLM stream closes through its `async with`; tool tasks die with the TaskGroup; on shutdown uvicorn sends 1012 and the lifespan closes the Qdrant and OpenAI clients.
- **Rejected:** a concurrent receiver task per turn.
- **Why:** simplest correct structure; a concurrent receiver would consume queued messages and break D-08.
- **Evidence:** E11; E12 (`ClientDisconnected` is an `OSError`); E13 (SIGINT → 1012); E14.
- **Status:** kept; a disconnect during retrieval or the tool is noticed at the next send.

### D-42 — Error catalog and last-resort handler · SUPERSEDED (D-67)
- **Decision:** one merged catalog of exact client texts (ARCHITECTURE §10); a turn failure sends one `error` frame, no `done`, socket open; a last-resort `except Exception` logs the traceback and sends "Something went wrong. Please try again."; `WebSocketDisconnect` is re-raised, not handled there.
- **Why:** the brief requires a user-facing error with the connection kept open on LLM or tool failure; an unexpected bug must not close the socket.
- **Status:** SUPERSEDED by the consolidated catalog (D-67); the one-frame / socket-open / last-resort behaviour is unchanged.

### D-43 — Operational minimalism · KEPT
- **Decision:** no `/health`; no connection manager, session registry or global state; logs carry per-connection and per-turn metadata (e.g. `sub`, error category) and never message text, tokens, excerpts or raw JWTs; warnings for client validation errors, bad tokens and auth timeouts; errors for upstream and Qdrant failures.
- **Rejected:** a health endpoint; deep startup health checks; a global history dict.
- **Why:** YAGNI — evaluation is `test_client.html` over `/ws/chat`; isolation by construction.
- **Status:** kept.

### D-44 — No-blocking split · KEPT
- **Decision:** model load (lifespan) and `encode` through `asyncio.to_thread`; Qdrant, OpenAI streaming and the `asyncio.sleep` mocks on the loop; `jwt.decode` and logging on the loop.
- **Why:** `encode` is a synchronous CPU call and the model load takes seconds; `jwt.decode` and logging take microseconds.
- **Evidence:** E01 (warm encode ~7 ms median, p95 15–18 ms; first load 21.7 s incl. download).
- **Status:** kept.

---

## Architecture and delivery decisions

### D-45 — Ports and adapters · KEPT
- **Decision:** `app/` with `domain` (models, events, exceptions, constants, prompt, orchestrator, ports as `typing.Protocol`), `adapters`, `transport/websocket`, `ingestion`; `app/main.py` (server) and `scripts/ingest.py` (CLI) are the only two composition roots (D-66); the four Protocols live in `app/domain/ports.py` (D-53); ports split by side (async query embedder / sync document embedder; async vector reader / sync vector writer); no `@runtime_checkable`.
- **Rejected:** adapters importing transport; one vector-store port for both sides.
- **Why:** providers swap without core changes; the CLI is synchronous, the server asynchronous; fakes plug in for tests.
- **Status:** kept, amended in round 10 (D-53, D-57, D-66).

### D-46 — Composition root and app factory · KEPT
- **Decision:** `create_app(settings, orchestrator, use_lifespan)`; `app = create_app()` is import-safe because settings load inside the lifespan; the lifespan loads the model in a thread and injects it into `SentenceTransformerAdapter(model=…)`; instances on `app.state`, read by the route through `Depends`.
- **Rejected:** module-level settings; adapters that load their own model.
- **Why:** transport tests build the app with a fake orchestrator and no lifespan (no Qdrant, no model); the injected model lets unit tests use a fake model (round 11: the blocking proof patches `asyncio.to_thread` instead of timing a stub, D-69).
- **Status:** kept.

### D-47 — Configuration policy · KEPT
- **Decision:** `IngestConfig` (docs dir, Qdrant, embedding; ignores `JWT_SECRET`) and `ServerConfig` (secret, provider routing, `MAX_TOKENS`, `GROQ_EXTRA_PARAMS` — post-review, was `LLM_EXTRA_PARAMS` — Qdrant, embedding), both `pydantic-settings` with `env_file=".env"` (resolved against the working directory, so the server starts in `miniragchatbot/`, D-76); behaviour constants in `app/domain/constants.py`; only `GROQ_MODEL` has a model default; stale model names only as comments in `.env.example`.
- **Rejected:** one shared settings class; k and timeouts as environment variables; `LLM_BASE_URL`.
- **Why:** ingestion runs without server secrets; each constant is justified once in the README.
- **Status:** kept.

### D-48 — Turn consumer · KEPT
- **Decision:** the transport wraps the turn in `asyncio.timeout(30.0)` and iterates `run_turn` inside `contextlib.aclosing`; `TurnError(message)` is the base of `EmbeddingError`, `VectorSearchError`, `ToolExecutionError` and the adapter's LLM errors, so one `except TurnError` sends the catalog text.
- **Rejected:** holding the timeout inside the turn generator.
- **Why:** an async generator holding `asyncio.timeout` across yields, abandoned while still referenced, later cancels the consumer task (spurious `CancelledError` while it waits for the next frame).
- **Evidence:** E15.
- **Status:** kept; extended in round 10 (D-62).

### D-49 — Packaging and tooling · KEPT
- **Decision:** Python ≥ 3.11; `uv sync --python 3.12`; `pyproject.toml` plus pinned `requirements.txt` (`uv pip compile`); `pyjwt` and `python-dotenv` as dependencies; Qdrant image `v1.19.1`; package `app/`; ruff (E, W, F, I, UP, B, ASYNC, SIM, C90 with `max-complexity = 10` — C90 added post-review so the rubric's "small functions" has a check) + mypy strict with the pydantic plugin; `uvicorn[standard]` and dev `httpx` (pre-build, D-83); no pre-commit hooks.
- **Rejected:** `src/` layout; system Python; pip-only setup; pre-commit hooks.
- **Why:** `asyncio.TaskGroup` / `asyncio.timeout` need 3.11; system `python3` is 3.9.6 and fastapi 0.142.2, qdrant-client 1.19.1, sentence-transformers 6.1.0 and openai 3.24.0 need ≥ 3.10; uv 0.12.18 is installed; `app/` makes `uvicorn app.main:app --reload` work verbatim; `mint_tokens.py` needs pyjwt and python-dotenv.
- **Evidence:** brief §7 measured facts; K02 verified (libraries need ≥ 3.10); K07 (3.11 for `TaskGroup` and `asyncio.timeout`).
- **Status:** kept; mypy runs as `uv run mypy app scripts` (D-54).

### D-50 — Seven vertical-slice commits · KEPT
- **Decision:** (1) skeleton: auth + stub stream visible in `test_client.html`; (2) real LLM streaming; (3) ingestion CLI; (4) RBAC retrieval + grounded prompt; (5) parallel tool + pass 2; (6) error catalog, timeouts, startup checks; (7) README + verification checklist (the eval was cut, D-72); tests ship with each commit and each passes ruff, mypy and its tests.
- **Why:** the brief evaluates commits ("Show your commits. We care about how you iterate").
- **Status:** kept (IMPLEMENTATION-PLAN); round 10: every test ships in the commit that introduces its code (D-58); round 11: optional commit 8 for conversation memory (D-73).

### D-51 — Offline-by-default verification · KEPT
- **Decision:** default `uv run pytest` is offline (markers `model`, `qdrant`, `live_llm` excluded by `addopts`); fakes for every port; RBAC proven by seeded payloads and filtered counts (`qdrant` only); blocking proven with a 200 ms stub and a mutation; the OpenAI adapter tested offline with synthetic chunks and kept in coverage; live-only proofs for tool choice, cadence and refusal wording; timeouts patched; branch coverage ≥ 85 % on `app/`.
- **Rejected:** timing the real model; omitting the adapter from coverage; waiting real 8/10/30 s.
- **Why:** an evaluator may have no key and no Docker; with ~7 ms encodes a real-model timing test cannot separate threaded from blocking (the stall is < 20 ms either way).
- **Evidence:** E01, E07.
- **Status:** kept (TEST-PLAN); round 10: flat files with K09 names (D-53), 10-case JWT matrix (D-61); round 11: sync transport tests, timeout parameters, isolated collection (D-68), one-test blocking proof (D-69), counter cut (D-70), 80 % gate on the full local suite (D-71), golden-set eval cut (D-72). The decision text's 200 ms stub + mutation, patched timeouts and ≥ 85 % are superseded accordingly (D-69, D-68, D-71).

---

## Round-10 resolutions (D-52…D-66)

### D-52 — An IDOR denial goes to pass 2 as a tool result (O-01) · NEW
- **Decision:** the orchestrator compares the tool call's `user_id` with the JWT `sub` before calling the tool; on mismatch it does not call the tool and sends the tool result "Access denied: caller may only query their own context." to pass 2, so the model explains in conversation; the port is `get_employee_context(user_id)` with no `caller_id`.
- **Rejected:** ending the turn with a catalog error frame (K09 NFR-06; K10 first reply); the check inside the tool with a `caller_id` parameter (K05 body, K07 port).
- **Why:** a graceful in-dialogue refusal instead of an abrupt error frame (the README tradeoff: one extra LLM pass in exchange); the check stays in code before any lookup.
- **Why not the alternatives:** an error frame is abrupt and no catalog string covers it; with the check in the orchestrator the tool port needs no `caller_id`.
- **Status:** NEW; resolves O-01 and D-09's open mechanism.

### D-53 — Flat test files, canonical K09 names, one ports module (O-02, O-03, O-04) · NEW
- **Decision:** flat `tests/test_*.py` files with markers separating unit / `qdrant` / `model` / `live_llm`; K09 test names (PRD FRs + implementation plan) are canonical; one `app/domain/ports.py` holds the four Protocols.
- **Rejected:** K08's nested layout and names; a `ports/` package (both re-proposed by a context-free reply, overruled by the K10 reviewer note).
- **Why:** simpler, and the PRD and plan already use them; markers already separate the suites; four small Protocols fit one module.
- **Why not the alternatives:** nested directories add boilerplate the markers make unnecessary; a package adds files for four small classes.
- **Status:** NEW.

### D-54 — Qdrant command and mypy scope (O-05, O-06) · NEW
- **Decision:** `docker run -d --name qdrant -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1`; `uv run mypy app scripts` (strict via `pyproject.toml`).
- **Rejected:** `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.19.1`; `uv run mypy app`; `uv run mypy --strict .`.
- **Why:** a named daemon container does not block the terminal, keeps the index across restarts and omits the unused gRPC port; `scripts/ingest.py` is production code and is type-checked strictly without pulling in test fixtures.
- **Why not the alternatives:** without a volume the index is lost when the container goes; `mypy app` skips the CLI; `mypy --strict .` also type-checks tests and fixtures.
- **Status:** NEW.

### D-55 — Evidence settlements (O-07, O-08, O-22) · NEW
- **Decision:** the only Groq data statement is "does not retain customer data for inference by default (up to 30 days for reliability/abuse monitoring)"; training use is not stated, so U-08 stays UNVERIFIED. RR-01 likelihood is High. Anthropic lists both `max_tokens` and `max_completion_tokens` as fully supported (E10 corrected).
- **Rejected:** "no training use by default"; Medium likelihood for RR-01; "E10 lists only `max_tokens`".
- **Why:** each follows the evidence — E05, K09's complete risk list, and the E10 correction.
- **Status:** NEW; D-30 and D-35 follow it.

### D-56 — One first-chunk timer, no connect timeout (O-09, O-21) · NEW
- **Decision:** no separate connect timeout; the 8 s timer runs from request start (`create`) to the first chunk of any kind — text, deliberation-only or tool-call; the 30 s turn timeout bounds everything else.
- **Rejected:** a 3.0 s connect timeout (K05 body, C05-STATE; re-proposed by K10's context-free table); timing to the first text token (K09 NFR-02) or to the first non-empty delta (K10 first reply).
- **Why:** a hung connection is caught by the same 8 s timer; a tool-only pass 1 or a model that deliberates first would otherwise trip a false timeout.
- **Why not the alternatives:** a connect timeout duplicates what the 8 s timer already bounds; a text-token definition fires during valid tool calls.
- **Status:** NEW; the constant keeps its name `FIRST_TOKEN_TIMEOUT_SECONDS`.

### D-57 — Pydantic schemas allowed in the domain (O-10) · NEW
- **Decision:** pydantic models may live in `domain` (schemas only, e.g. `UserClaims`); I/O, network and database libraries may not.
- **Rejected:** a standard-library-only domain with claims mapped from a transport model.
- **Why:** pydantic is a validation library, not an I/O framework; no duplicate mapping layer.
- **Status:** NEW; amends D-45's dependency rule.

### D-58 — Tests ship with the code they guard (O-11) · NEW
- **Decision:** every test ships in the commit that introduces the code it guards — the JWT matrix in commit 1, the blocking-detector test in commit 4, the live tests in commits 2, 4 and 5.
- **Rejected:** K09's placement (blocking-detector test in commit 6, JWT matrix in commit 7).
- **Why:** the register's rule that tests ship with each commit; each slice verifies itself.
- **Status:** NEW; amends D-50.

### D-59 — Two more error mappings, no new strings (O-12, O-13) · NEW
- **Decision:** openai `BadRequestError` (HTTP 400) → "System configuration error. Please contact support."; `finish_reason="content_filter"` → the last-resort "Something went wrong. Please try again."
- **Rejected:** new catalog strings; `content_filter` → "The answer was cut short. Please ask a narrower question." (K10 gap reply).
- **Why:** a 400 means misconfigured request parameters, such as an invalid `GROQ_EXTRA_PARAMS` (post-review name); the generic message is honest.
- **Why not the alternatives:** "ask a narrower question" would mislead for a filtered answer.
- **Status:** NEW; extends D-37; its `content_filter` mapping is superseded in round 11 (→ "AI service temporarily unavailable. Please try again.", D-67).

### D-60 — Only the first tool call is executed (O-14) · NEW
- **Decision:** if pass 1 yields several tool calls, execute only the first, echo only that call in the pass-2 assistant message, and log a warning.
- **Rejected:** failing the turn with an invalid-tool-request error frame (K10 gap reply); executing every call.
- **Why:** graceful and trivial to implement; one tool round stays one tool call; every echoed call id has its tool message, which OpenAI-compatible APIs expect.
- **Why not the alternatives:** an error frame is abrupt for a recoverable case; executing every call breaks the one-tool-round design.
- **Status:** NEW; extends D-32.

### D-61 — The JWT matrix has 10 cases (O-15) · NEW
- **Decision:** case 10 is a token without `exp`.
- **Rejected:** the 9-case matrix.
- **Why:** D-12 and R-14 require `exp`; the matrix now proves it.
- **Status:** NEW; the test is `test_jwt_matrix_ten_cases` (K09's `test_jwt_matrix_nine_cases`, renamed to match its content).

### D-62 — `aclosing` around every streaming generator (O-16) · NEW
- **Decision:** the adapter stream inside `run_turn` and `run_turn` inside the consumer are each consumed inside `contextlib.aclosing`; no timeout context stays open across a `yield`.
- **Rejected:** `aclosing` only in the consumer, leaving the adapter stream to the async-generator finalizer.
- **Why:** the upstream HTTP stream closes promptly and deterministically on a disconnect or timeout (E15).
- **Status:** NEW; extends D-48.

### D-63 — Injectable token counter (O-17) · NEW
- **Decision:** the chunker takes an injectable token counter whose default is the bge tokenizer.
- **Rejected:** chunker tests that need the real tokenizer (and so the `model` marker).
- **Why:** offline unit tests of the 150-token fallback need no model download.
- **Status:** SUPERSEDED in round 11 (D-70): the counter is cut.

### D-64 — Embedding-provider and docs-dir rules (O-18, O-19) · NEW
- **Decision:** an `EMBEDDING_PROVIDER` other than `sentence-transformers` fails fast at startup or ingestion with a configuration error; the CLI's `--docs-dir` overrides `IngestConfig.DOCS_DIR`.
- **Rejected:** silently ignoring other provider values; the environment value winning over the CLI flag.
- **Why:** only sentence-transformers is implemented, so an early configuration error beats a runtime crash; explicit CLI flags conventionally take precedence.
- **Status:** NEW; extends D-23 and D-47.

### D-65 — OpenRouter and OpenAI base URLs (O-20) · NEW
- **Decision:** OpenRouter `https://openrouter.ai/api/v1`; OpenAI `https://api.openai.com/v1`.
- **Why:** completes the per-provider base-URL table (K05 recorded Groq, Gemini, Ollama and Anthropic only).
- **Status:** NEW; extends D-29.

### D-66 — A second, CLI-only composition root (O-23) · NEW
- **Decision:** `scripts/ingest.py` is the second, CLI-only composition root (`app/main.py` for the server); the dependency-rule test allows exactly these two.
- **Rejected:** wiring the ingestion adapters through `app/main.py` (K07's "sole module" wording).
- **Why:** ingestion runs standalone; making the web composition root wire offline tools would couple the CLI to the server.
- **Status:** NEW; amends D-45.

---

## Round-11 accuracy changes (D-67…D-75)

### D-67 — Consolidated error catalog · NEW (round 11)
- **Decision:** 10 turn-error strings plus the 4 unchanged `auth_failed` texts. "Invalid message structure" (invalid JSON, wrong or missing type or field, a second auth frame); "Message text must be between 1 and 2000 characters"; "Knowledge base search temporarily unavailable" (embedding or Qdrant failure); "Failed to execute employee lookup." (tool failure or timeout, or an invalid tool request incl. unparseable arguments); "System is busy due to high demand. Please try again shortly." (429); "System configuration error. Please contact support." (400, 401, 404); "Response generation timed out. Please try again." (8 s first-chunk timer, 30 s turn timeout, SDK `APITimeoutError`); "The answer was cut short. Please ask a narrower question." (`length`); "AI service temporarily unavailable. Please try again." (5xx, connection error, mid-stream drop, empty answer, `content_filter`); last resort "Something went wrong. Please try again."
- **Rejected:** the 16-string catalog (D-42) with six bespoke strings, now retired: "Invalid JSON payload", "Session is already authenticated", "Failed to process query embedding", "The assistant produced an invalid tool request.", "Connection lost during generation. Please try again.", "The assistant produced an empty response. Please try again."; mapping `content_filter` to the last-resort message (D-59).
- **Why:** fewer bespoke strings and less mapping boilerplate while every failure domain stays covered (K11).
- **Why not the alternatives:** the 16-string (20-row) catalog was over-engineered for a 4–6 hour take-home (K11).
- **Status:** NEW; supersedes D-42 and D-59's `content_filter` mapping; amends D-37 and D-40.

### D-68 — Test mechanics: sync transport tests, timeout parameters, isolated collection · NEW (round 11)
- **Decision:** transport tests are plain sync `def` tests; every timeout is a parameter of the function or constructor that applies it, with the constant as default, and tests pass small values; integration tests use `QDRANT_COLLECTION=acme_policies_test`.
- **Rejected:** async transport tests; monkeypatching imported timeout constants; integration tests on the production collection.
- **Why:** the Starlette `TestClient` WebSocket API is synchronous; a constant imported with `from … import` is not affected by patching its source module; ingestion tests recreate the collection and would wipe the seeded RBAC data (K11).
- **Status:** NEW; amends D-51.

### D-69 — One-test blocking proof · NEW (round 11)
- **Decision:** one unit test patches `asyncio.to_thread` in the embedder module and asserts `encode` is dispatched through it.
- **Rejected:** the 5 ms heartbeat with a 200 ms blocking stub and a mutation adapter (< 20 ms threaded, ≥ 180 ms mutation).
- **Why:** it proves the non-blocking intent without a timing harness (K11).
- **Why not the alternatives:** the harness mostly tests the standard library's `asyncio.to_thread` and adds timing flakiness (K11).
- **Status:** NEW; amends D-51 and D-46.

### D-70 — Injectable token counter cut · NEW (round 11)
- **Decision:** no injectable counter; the chunker counts with the bge tokenizer, and tokenizer-dependent chunker tests carry the `model` marker.
- **Rejected:** the injectable counter (D-63).
- **Why:** keeps domain signatures clean; downloading the model once for these tests is acceptable (K11).
- **Status:** NEW; supersedes D-63.

### D-71 — Coverage gate on the full local suite · NEW (round 11)
- **Decision:** ≥ 80 % branch coverage on `app/`, measured on `uv run pytest -m "not live_llm"` (Docker Qdrant + model); the offline default suite has no coverage gate.
- **Rejected:** ≥ 85 % branch coverage from the offline suite alone.
- **Why:** with the counter cut, tokenizer- and Qdrant-dependent code is exercised only by `model`/`qdrant` tests, so coverage is measured where those tests run (K11).
- **Status:** NEW; amends D-51.

### D-72 — Automated golden-set eval cut · NEW (round 11)
- **Decision:** no automated 24-question golden-set eval; the deterministic RBAC count test (12/18/24/30) and the manual `test_client.html` checklist remain.
- **Rejected:** the automated golden-set retrieval eval in commit 7.
- **Why:** the seeded counts prove the DB-layer filter deterministically; a semantic eval is unnecessary overhead for the time budget (K11).
- **Status:** NEW; amends D-51.

### D-73 — Conversation memory is optional; the core is stateless · NEW (round 11)
- **Decision:** conversation memory (S-03, last 3 question/answer pairs) is implemented last, only if time remains (optional commit 8); the core pipeline answers each message on its own.
- **Rejected:** memory as part of the core plan.
- **Why:** a stateless RAG pipeline fulfils the brief; bounded history is a stretch goal, secondary to a working vertical slice (K11).
- **Status:** NEW; amends D-36 and D-50.

### D-74 — Wording: our assumptions are not brief rules · NEW (round 11)
- **Decision:** treating `test_client.html` and `mint_tokens.py` as read-only is our assumption (A-26) — the brief does not forbid editing them; executives lacking finance access is the consequence of the brief's formula plus its single `hr` exception, not a rule the brief states.
- **Rejected:** "must not be modified"; "literal brief rule".
- **Why:** the brief says neither (K11 brief-coverage review).
- **Status:** NEW; affects D-27 and A-02.

### D-75 — Evidence upgrades and the Origin rule · NEW (round 11)
- **Decision:** WebSocket Origin handling is verified live — handshakes with Origin `null` and with a foreign origin are accepted by default — and no Origin check is added: auth is an in-band JWT, not cookies, so a foreign page gains nothing without a token, and an allow-list rejecting `null` would break the provided client. sentence-transformers truncation beyond `max_seq_length` (K02) and bge unit-norm output (K03) are verified by running code.
- **Rejected:** an Origin allow-list.
- **Evidence:** E17; K02; K03.
- **Status:** NEW.

## Post-review corrections (D-76…D-77)

### D-76 — Project root is `miniragchatbot/` · NEW (post-review)
- **Decision:** all code is built inside `miniragchatbot/`, next to the brief's provided `docs/`, `mint_tokens.py`, `test_client.html`, `.env.example` and `.gitignore`; every path and command in these documents is relative to it, and the server, the ingestion CLI and `mint_tokens.py` run from there with one `miniragchatbot/.env`.
- **Rejected:** building at the git repository root, one level above the provided files.
- **Why:** the brief's file tree puts `./docs`, `mint_tokens.py` and `.env.example` at the project root, which in this repository is `miniragchatbot/`. The only `.gitignore` is `miniragchatbot/.gitignore`, so a `.env` or `qdrant_data/` at the repository root would not be ignored. `mint_tokens.py` calls `load_dotenv()` with no path, which searches for `.env` from the script's own folder upward, not from the working directory, while `pydantic-settings` resolves `env_file=".env"` against the working directory; starting the server in `miniragchatbot/` makes both read `miniragchatbot/.env`.
- **Evidence:** `git ls-files` (the provided files are under `miniragchatbot/`); python-dotenv 1.2.4 run on 2026-10-04 (script folder without `.env`, working directory with `.env` → the variable is not loaded); the repository-root `.DS_Store` came with CodeSubmit's starter commit `b376357`, not from this project.
- **Status:** NEW; corrects the reason given in A-25.

### D-77 — Submission path · NEW (post-review)
- **Decision:** the repository's `origin` is the CodeSubmit remote (`git.codesubmit.io/etihad-airways/ai-chatbot-challenge-aspest`), so submitting means pushing `master` there, and only on the owner's explicit go. Whether `deliverables/` is part of the submission is OPEN (owner decision); on 2026-10-04 its commit `02acf12` was local only (`master` 1 ahead of `origin/master`), so either choice was still possible without rewriting pushed history.
- **Rejected:** the brief's generic options (zip by email, a GitHub link), which the CodeSubmit-provided remote replaces in practice. Any extra confirmation step on the CodeSubmit site is not verified here.
- **Why:** no other deliverable covered the brief's "What to submit" delivery step.
- **Status:** NEW; the `deliverables/` question is OPEN.

## Pre-build corrections (D-78…D-85)

Decided on 2026-10-04, before the 2-hour build, after a full read of the deliverables against the brief, `test_client.html`, the decoded PDFs and the build machine. Owner answers the same day: apply all corrections now; pre-flight before the clock; native execution with background reviews; the owner frees port 8000.

### D-78 — Two-hour execution layer · NEW (pre-build)
- **Decision:** the build runs in 120 minutes against [build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md): pre-flight P1–P9 before the clock (no product code); the seven slices time-boxed at 17 / 14 / 20 / 15 / 12 / 15 / 17 minutes plus a 10-minute close-out; native execution (superpowers:executing-plans + superpowers:test-driven-development + ECC skills) with ECC reviewer agents checking each committed slice in the background; every step logged in [build/TRACKER.md](build/TRACKER.md). Tripwires: a slice more than 5 minutes over its box applies the next time-only cut; more than 15 minutes behind at T+66 stops for an owner decision; the same gate failing twice halts for systematic debugging.
- **Rejected:** the 305–360-minute estimate as the plan for this run (IMPLEMENTATION-PLAN §5 stays as the human-pace figure); pre-flight inside the clock; subagent-driven execution (a fresh implementer and fresh reviewers per slice); fully parallel implementation.
- **Why:** the owner's limit is 2 hours including tests and real runs; the pre-flight removes the unknowns that would otherwise surface mid-build (Groq streaming with tools, dependency wheels, OCR, the image tag); background reviews add independent checks without blocking the next slice.
- **Why not the alternatives:** the human-pace estimate is three times the limit; a per-slice subagent pipeline spends the budget on context loading and review hand-offs; parallel implementation of dependent slices breaks the "each slice verified before the next" rule.
- **Evidence:** IMPLEMENTATION-PLAN §5 and U-15 (305–360 min + 20–30 min day-1 checks); owner answers 2026-10-04.
- **Status:** NEW; replaces U-15's estimate for this run only. Time-only cuts, never a MUST: the live citation test, the semantic differential pairs, the NFR-03 latency test, then the manual checklist reduced to its 9 core rows.

### D-79 — One function per test · NEW (pre-build)
- **Decision:** where the test plan names the same behaviour twice (a canonical K09/PRD name plus a plan or K08 name), there is one test function under the canonical name and the other names are aliases. Twenty names fold into fourteen tests (merge list in TEST-PLAN §2); the auth-timeout case ships once, in commit 1, inside `test_auth_failure_emits_frame_and_closes_1008`.
- **Rejected:** writing every listed name as its own function.
- **Why:** duplicate tests cost build time, would run the slow end-to-end ingestion three times, and read as copy-paste to a reviewer; one name per test keeps the tracker's requirement matrix unambiguous.
- **Evidence:** TEST-PLAN §2 before this change (`test_ws_auth_timeout_closes_1008` in commit 1 and `test_auth_timeout_10s_closes_1008` in commit 6 assert the same behaviour); REQUIREMENTS-TRACEABILITY M-27 ("plan: …" alias).
- **Status:** NEW; amends D-53 (names) and D-58 (placement).

### D-80 — Citations are checked by the manual checklist · NEW (pre-build)
- **Decision:** inline citations are spot-checked by the manual checklist, whose answer rows each name the expected `[file.pdf, page 1]`; the live "cited files ⊆ retrieved files" test is optional and first in the time-only cut order.
- **Rejected:** keeping the wording "checked by an offline eval".
- **Why:** that eval was the golden-set eval cut in round 11 (D-72); no commit builds it, so the README must not claim it.
- **Evidence:** D-72; IMPLEMENTATION-PLAN commit 7 (no citation eval); TEST-PLAN §9.
- **Status:** NEW; corrects D-19's replacement wording, PRD §3.2, the README outline's Known limitations, RISKS U-09 and TEST-PLAN §7.

### D-81 — Real-run failure drills for commit 6 · NEW (pre-build)
- **Decision:** commit 6 ends with three drills against the running server: Qdrant stopped mid-session → "Knowledge base search temporarily unavailable" with the socket open, then recovery after `docker start qdrant`; startup against a missing collection → exit code 3; a wrong `GROQ_API_KEY` → "System configuration error. Please contact support." with the socket open.
- **Rejected:** "Manual check: none specified" (tests only).
- **Why:** the owner requires every slice to be seen working in the real system, and error handling is a rubric area; the drills exercise the real adapters, not fakes.
- **Status:** NEW; amends IMPLEMENTATION-PLAN commit 6.

### D-82 — Live cadence test without a timing flake · NEW (pre-build)
- **Decision:** `test_live_streaming_token_cadence` asks a long-answer question ("Summarise every section of the leave policy.") and asserts more than 5 text deltas; the first-to-last spread is logged, not asserted.
- **Rejected:** asserting a spread of more than 0.1 s.
- **Why:** Groq can deliver a short answer in under 0.1 s, so the spread assertion fails on a fast provider although streaming is real; the number of separate frames is the property the rubric checks ("not in one big chunk").
- **Status:** NEW; amends TEST-PLAN §7.

### D-83 — Packaging details fixed before slice 1 · NEW (pre-build)
- **Decision:** runtime dependency `uvicorn[standard]` (not plain `uvicorn`); dev dependency `httpx`; mypy strict with per-module `ignore_missing_imports` only for third-party modules mypy reports as untyped (expected: `rapidocr`), each recorded in the tracker when added.
- **Why:** plain `uvicorn` ships no WebSocket implementation and rejects the upgrade; Starlette's `TestClient` imports `httpx`; fixing the mypy policy up front keeps slice 1 inside its box.
- **Evidence:** pre-flight P4 (all pins resolve together on Python 3.12.14, including websockets 17.2 through the `standard` extra and httpx 0.28.1).
- **Status:** NEW; amends D-49 and ARCHITECTURE §2.

### D-84 — Two scripts named: `scripts/ws_probe.py` and `scripts/scan_secrets.py` · NEW (pre-build)
- **Decision:** a small CLI WebSocket client, `python -m scripts.ws_probe --token <jwt> "<question>"`, prints each frame with a timestamp; it drives the scripted real runs of slices 2–6 and is offered in README §3 as the command-line test. The git-history secrets scan named in commit 7 is `scripts/scan_secrets.py`.
- **Rejected:** driving the browser for every real run (6–8 browser actions per question); leaving the scripts unnamed.
- **Why:** the brief allows "a small test HTML/script" for testing; the probe records exact frame timing as evidence and keeps the browser for slices 1, 5 and 7; naming the scan script removes one decision from the clock.
- **Status:** NEW; `test_client.html` stays the evaluator's tool and is still checked in the browser.

### D-85 — Review-focus tests · NEW (pre-build)
- **Decision:** five cases the spec implies but no test exercised are added to the tests that own the code: a non-PDF file (e.g. `.DS_Store`) in `docs/` is ignored by the access-table check (commit 3); a 2,000-character message is accepted, 2,001 is rejected and an emoji counts as one character (commit 1); an unknown or differently-cased department sees only `hr` content within its level (commit 4); text the model emits before a tool call streams before the ~1 s pause and the turn still ends with one `done` (commit 5); after a mid-stream disconnect a new connection works normally (commit 6).
- **Why:** macOS writes `.DS_Store` into folders that are opened in Finder, which would trip a strict access-table check on the evaluator's machine; the other four are boundary and recovery paths a real user hits.
- **Status:** NEW.

---

## Appendix — superseded statements (do not reuse)

| Superseded statement | Where it appears | Use instead |
|---|---|---|
| OCR when the text layer has "< 50 characters" | K02 OCR section; K03 body step 1 | `len(text.strip()) == 0` (D-06) |
| 3 s auth timeout | K02 D-15 | 10 s (D-39) |
| Server-built "Sources Consulted" block | K02 D-19 and corrections | inline model citations (D-19) |
| Retrieval on `Q(t-1) + Q(t)` | K02 D-21 | current question only (D-21) |
| "The full conversational history" goes to the LLM | K04 body | last 3 pairs (D-36) |
| Encode latency "~300 ms", "~15 ms", "45–90 ms" | K02, K08 bodies | ~7 ms median, p95 15–18 ms (E01) |
| "Offline initial run" of ingestion | K03 body | first run needs network for the model (A-21) |
| Library raises `SystemExit`; tests expect `SystemExit` | K03 tests 4–5 | domain errors; CLI maps to exit 1 (D-24) |
| Runtime assertion of "exactly 5 geometric body paragraphs" in the script | K03 body | counts only in tests (6 scan chunks) |
| FastEmbed | K06 body | sentence-transformers bge-small |
| 404 → "AI service temporarily unavailable" / "Configured model is unavailable." | K06 body / K05 | "System configuration error. Please contact support." |
| `loc == ("text",)` | K06 body | `loc[-1] == "text"` (E14) |
| LLM streaming function sends WebSocket frames | K06 skeleton | adapter yields events; transport sends (D-31) |
| K05 failure-table strings ("Service temporarily unavailable…", "Upstream service error…", "Unable to generate an answer…", "Connection lost mid-response…") | K05 body | consolidated catalog (D-67) |
| Token estimate "chunks ~560 / tool output ~550" | K05 body | ~300–360 / ~55 tokens |
| Shorter digest system prompt | K05 body §6 | canonical prompt (D-34) |
| `max_tokens` 512; `max_completion_tokens` | K05 body | `max_tokens` 1500 (D-35) |
| Hard-coded `reasoning_effort: "low"` | K05 body; K09 RR-02 | via `GROQ_EXTRA_PARAMS` (D-35, post-review) |
| Groq "strict zero-data-retention" | K05 body | E05 wording (D-30) |
| Lower-bound timing assertion for the tool | K05 body | spies + < 1.35 s (D-33) |
| Message-layout example with `leave_policy.pdf` page 2 and `travel_policy.pdf` page 4 | K05 body §6 | all PDFs are 1 page; the file is `travel_reimbursement.pdf` |
| Orchestrator buffering pass-1 events | K07 body | yield each delta as it arrives (D-31) |
| History append with placeholder `"assistant": "..."` | K07 body | append the streamed answer after `done` (D-36) |
| `LLM_BASE_URL` setting; `@runtime_checkable` | K07 body | per-provider URLs; plain Protocols (D-45, D-47) |
| `/ws` route, `Depends`-based session, `"query"` field, sources in `done`, close 1011, `tools=None`, a "leave balance" mock | K07 body (draft) | frozen protocol; same tools in pass 2 |
| HTTP 401/403 handshake rejection, grade inside the JWT, a `data/` folder | K01 body (drafted, then corrected) | in-band auth; grade only from the tool; `./docs/` |
| "Cloud APIs would leak confidential data" OCR rationale | K09 PRD draft | restated D-05 |
| Provider "failover" | K09 PRD draft | configuration swap (D-29) |
| Ingestion through `AsyncQdrantClient` | K09 FR-06 draft | sync `QdrantClient` (FR-06) |
| `auth_success` example with `department: "sales"` | K09 FR-14 draft | `emp-001`, `hr`, 1 |
| Auth timeout → "Invalid or expired token" | K09 FR-15 draft | "Authentication timed out" |
| Each fetch returns a nested dict | K09 FR-24…26 draft | brief's exact dict per fetch; nesting only in the combined result |
| `PYTHONASYNCIODEBUG` + 50 ms lag threshold | K09 NFR-04 draft | one `asyncio.to_thread` patch test (D-69; NFR-04) |
| "within 200 ms and consumes under 4 chunks" | K09 NFR-03 draft | at most 4 chunks; 200 ms ceiling |
| Automated CI secrets scan / CI scripts | K09 NFR-08, NFR-14 drafts | scripted/manual scan; local commit gates (no CI) |
| JWT matrix with RS256 and empty-secret cases | K09 NFR-07 draft | the 10-case matrix (D-61); empty secret covered by FR-21 |
| Startup pre-flight model ping; rate-limit header checks | K09 RR-01 draft | live smoke test + clear 401/404/429 messages |
| 200 ms loop-lag threshold | K09 RR-08 draft | one `asyncio.to_thread` patch test (D-69) |
| `test_unauthorized_query_returns_refusal` as a `qdrant` test | K09 plan, commit 4 | `live_llm` test |
| `test_git_history_contains_no_secrets` as a pytest test | K09 plan, commit 7 | a script |
| `asyncio.to_thread` introduced in commit 6 | K09 plan | from commit 4 |
| README example with an "engineering" department, an "equipment policy", "$500", `equipment_policy.pdf` page 2 | K09 README draft | real corpus example (README outline §3) |
| IDOR denial ends the turn with a catalog error frame | K09 NFR-06; K10 first reply | denial result to pass 2 (D-52) |
| `EmployeeToolPort.get_employee_context(user_id, caller_id)`; the IDOR check inside `mock_service.py` | K07 body; K05 body | port without `caller_id`; check in the orchestrator (D-52) |
| K08 nested test layout and K08 test names as canonical; an `app/domain/ports/` package | K08; K07; K10 context-free table | flat files, K09 names, one `app/domain/ports.py` (D-53) |
| `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.19.1` | K09 README draft | the D-54 command |
| `uv run mypy app`; `uv run mypy --strict .` | K07; K09 plan | `uv run mypy app scripts` (D-54) |
| Groq "no training use by default" | K09 FR-33 correction; K05 body; C05-STATE | E05 retention wording only; U-08 (D-55) |
| A 3.0 s connect timeout | K05 body §8; C05-STATE; K10 context-free table | none; the 8 s timer covers `create` (D-56) |
| The 8 s timer measuring the "first streaming text token" or "first non-empty chunk" | K09 NFR-02; K10 first reply | first chunk of any kind (D-56) |
| `content_filter` → "The answer was cut short. Please ask a narrower question." | K10 gap reply | last-resort message (D-59) |
| Several tool calls → "The assistant produced an invalid tool request." | K10 gap reply | first call only (D-60) |
| A 9-case JWT matrix; `test_jwt_matrix_nine_cases` | K08; K09 plan | 10 cases; `test_jwt_matrix_ten_cases` (D-61) |
| Blocking-detector test in commit 6; JWT matrix in commit 7 | K09 plan | commits 4 and 1 (D-58) |
| The 16-string error catalog, including the retired strings "Invalid JSON payload", "Session is already authenticated", "Failed to process query embedding", "The assistant produced an invalid tool request.", "Connection lost during generation. Please try again.", "The assistant produced an empty response. Please try again." | K06 catalog; register (before round 11) | consolidated catalog (D-67) |
| `content_filter` → "Something went wrong. Please try again." | round 10 (D-59) | "AI service temporarily unavailable. Please try again." (D-67) |
| Async transport tests; monkeypatched timeout constants | K08 body; v1.1 test plan | sync `def` tests; timeout parameters (D-68) |
| Integration tests on the production collection `acme_policies` | v1.1 test plan | `acme_policies_test` (D-68) |
| 5 ms heartbeat + 200 ms stub + mutation blocking detector (< 20 ms / ≥ 180 ms) | K08; v1.1 | one `asyncio.to_thread` patch test (D-69) |
| Injectable token counter for the chunker | round 10 (D-63) | cut; tokenizer-dependent tests carry `model` (D-70) |
| ≥ 85 % branch coverage from the offline suite | K08; register (before round 11) | ≥ 80 % on `uv run pytest -m "not live_llm"` (D-71) |
| Automated 24-question golden-set eval | K07 commit 7; v1.1 | cut (D-72) |
| Conversation memory in the core plan | K05/K07; v1.1 | optional commit 8 (D-73) |
| "must not be modified" (provided files); "literal brief rule" (exec/finance) | v1.1 PRD and README outline | our assumption (A-26); consequence of the formula (D-74) |
| Provider-wide `LLM_EXTRA_PARAMS`, sent to whichever provider is selected | v2 deliverables | `GROQ_EXTRA_PARAMS`, sent only when `LLM_PROVIDER=groq` (D-35, post-review) |
| "`load_dotenv()` reads `.env` from the working directory" | v2 PRD A-25 | it searches from `mint_tokens.py`'s own folder upward (D-76) |
| Server and `mint_tokens.py` run "from the repository root" | v2 PRD, RISKS-ASSUMPTIONS, README outline, SIGN-OFF | from `miniragchatbot/` (D-76) |
| Coverage gate held "from the first commit that has code under `app/`" | v2 SIGN-OFF §5 | from commit 6, as in IMPLEMENTATION-PLAN (needs Docker Qdrant and the model; D-71) |
| "Citations are checked by an offline eval" | D-19 replacement; PRD §3.2; README outline Known limitations; RISKS U-09 | the manual checklist (D-80) |
| `test_auth_timeout_10s_closes_1008` in commit 6 | IMPLEMENTATION-PLAN commit 6; TEST-PLAN §2 | the timeout case of `test_auth_failure_emits_frame_and_closes_1008`, commit 1 (D-79) |
| Live cadence "spread over more than 0.1 s" assertion | TEST-PLAN §7 | more than 5 deltas; spread logged, not asserted (D-82) |
| 305–360 minutes as the plan for this build | IMPLEMENTATION-PLAN §5; U-15 | the 2-hour run (D-78) |
