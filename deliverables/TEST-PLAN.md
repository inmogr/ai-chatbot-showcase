# Test Plan

This plan defines how every requirement is proven: the offline-by-default guarantee, the flat test layout, markers and exact commands, the fakes and test seams, the key test designs (streaming, blocking, JWT, RBAC, retrieval, ingestion, lifecycle, adapter, error catalog), timeout parameters, live-only tests, coverage and static gates, and the manual `test_client.html` checklist per user. Version 2 applies the round-11 accuracy changes on top of round 10: sync transport tests, timeouts as parameters, an isolated integration collection, a one-test blocking proof, no injectable token counter, an 80 % coverage gate on the full local suite, no automated golden-set eval, the consolidated error catalog and optional conversation memory. Requirement-to-test mapping is in [REQUIREMENTS-TRACEABILITY.md](REQUIREMENTS-TRACEABILITY.md).

Sources: `knowledge/K08-verification.md` (corrections applied), `inputs/attach/DECISIONS-REGISTER.md` (Verification; round-10 and round-11 changes), `knowledge/K10-consolidation.md`, `knowledge/K11-accuracy.md`, `knowledge/K03` (ingestion tests), `K04` (RBAC invariants), `K05` (tool proof), `K06`/`K07` (transport, E15), `K09` corrections (NFR-15 fixture, live and script reclassifications, canonical names), `inputs/attach/C06-STATE.md`, `C08-STATE.md`; evidence E01, E02, E03, E06, E07, E12, E13, E14, E15.

---

## 1. Guarantees

- **`uv run pytest` is offline:** no Docker, no embedding-model download, no API key, no network. Tests marked `model`, `qdrant` or `live_llm` are excluded by `addopts`. An evaluator with no key and no Docker gets a green run. The offline suite has no coverage gate (§8).
- **Every MUST row has a test or check** (traceability matrix); live-only items have an offline mechanics test as well.
- **Every test ships in the commit that introduces the code it guards** (round 10, O-11) and is written first within that commit; each commit passes ruff, mypy and its tests.
- **Transport tests are plain synchronous `def` tests**, because the Starlette `TestClient` WebSocket API is synchronous; async unit tests run under `asyncio_mode = "auto"` (round 11).
- **No real waits for production timeouts:** every timeout is a parameter of the function or constructor that applies it, with the constant as its default; tests pass small values (no monkeypatching of imported constants; round 11). The longest real wait is the tool's ~1 s parallel run, which the parallelism proof needs; the other real delays are short (0.03 s fake-LLM gaps, a ~0.2 s auth timeout passed by the test).
- **Integration tests use an isolated collection**, `QDRANT_COLLECTION=acme_policies_test`, so ingestion tests cannot wipe the seeded RBAC data (round 11).
- Target runtime of the default suite: < 2 s (K08 estimate, not measured — U-14).

## 2. Layout (flat files)

All tests are flat `tests/test_*.py` files; markers, not directories, separate unit, `qdrant`, `model` and `live_llm` tests. File names come from K09's plan; `test_live_groq.py` and `test_protocols.py` are K08's names, flattened, for tests K09's plan has no file for. The commit column follows O-11.

**One function per test (pre-build, D-79).** Where the table lists a canonical name and a plan or K08 name for the same behaviour, they are one test function under the canonical name; the other names are aliases only. Merges: `test_auth_success_payload_emission` ← `test_ws_auth_first_frame_success`; `test_auth_failure_emits_frame_and_closes_1008` (timeout, non-JSON, non-auth and bad-token cases) ← `test_ws_auth_invalid_payload_closes_1008`, `test_ws_auth_timeout_closes_1008`, `test_auth_timeout_10s_closes_1008`; `test_stream_finishes_with_done_frame` ← `test_ws_stub_stream_and_done`; `test_jwt_validation_strict_hs256_env_secret` ← `test_jwt_decode_valid_claims`; `test_extract_text_pdf_native_layer` + `test_extract_scanned_pdf_rapidocr_fallback` ← `test_pdfium_and_rapidocr_text_extraction`; `test_ingest_cli_execution_and_exit_code` (one end-to-end run, repeated once to prove recreation) ← `test_cli_recreates_collection`, `test_qdrant_collection_recreation_and_chunk_count`; `test_access_level_canonical_mapping_and_fail_fast` ← `test_cli_access_table_mismatch_fails_fast`; the four `test_rbac_filter_*_chunks` tests ← `test_rbac_database_layer_filter_enforcement`, `test_hr_exception_allows_cross_department_access`; `test_tool_idor_validation_against_jwt_sub` (match and mismatch) ← `test_idor_mismatch_denies_tool_call`; `test_turn_invokes_employee_context_on_personal_query` ← `test_orchestrator_pass1_captures_tool_call`, `test_orchestrator_pass2_completes_stream_with_tool_context`; `test_employee_tool_returns_brief_payloads` ← `test_employee_tool_returns_profile_payload` / `_manager_payload` / `_team_payload`; `test_employee_tool_executes_parallel_under_1_35s` ← `test_tool_execution_parallel_under_1_35s`; `test_downstream_failure_emits_error_frame_and_keeps_socket_open` ← `test_socket_stays_open_after_operational_error`. Twenty names fold into fourteen tests. The complete inventory — file, slice, marker and the rows each test proves — is [build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md) §5.

| File | Commit | Holds (canonical K09 names where they exist) |
|---|---|---|
| `tests/conftest.py` | 1+ | fakes, fixtures, `make_user_token`, `create_app` wiring, the isolated test collection name, marker skips |
| `tests/test_auth.py` | 1 (+4) | `test_jwt_decode_valid_claims`, `test_jwt_decode_expired_token`, `test_jwt_decode_unpinned_algorithm_rejected`, `test_jwt_missing_secret_fails_fast`, `test_jwt_validation_strict_hs256_env_secret`; claims-model checks; `ServerConfig` validation (provider key/model; commit 4 adds the `EMBEDDING_PROVIDER` fail-fast check) |
| `tests/test_websocket_protocol.py` | 1 (+6) | sync transport tests: `test_ws_chat_endpoint_accepts_connection`, `test_first_frame_auth_payload_received`, `test_auth_success_payload_emission`, `test_auth_failure_emits_frame_and_closes_1008`, `test_chat_message_frame_validated`, `test_stream_tokens_progressive_frames`, `test_stream_finishes_with_done_frame`, `test_client_html_exact_protocol_flow`; plan tests `test_ws_auth_first_frame_success`, `test_ws_auth_invalid_payload_closes_1008`, `test_ws_auth_timeout_closes_1008`, `test_ws_stub_stream_and_done`; `test_jwt_matrix_ten_cases`; `test_fastapi_app_lifespan_and_startup` (lifespan checks added in commit 6); log capture |
| `tests/test_protocols.py` | 1 (+2…5) | `test_clean_architecture_dependency_rules` (commit 1; `scripts/ingest.py` allowed from commit 3); `test_openai_adapter_satisfies_stream_chat_protocol` (commit 2) and each later adapter's Protocol assignment as it lands |
| `tests/test_llm_adapter.py` | 2 | `test_stream_chat_yields_text_deltas_progressively`, `test_stream_chat_accumulates_tool_call_deltas`, `test_stream_chat_first_token_timeout_triggers_error`, `test_stream_chat_maps_429_to_busy_catalog_message`, `test_stream_chat_skips_empty_choice_chunks`; the other adapter error mappings; early close of the adapter stream inside `run_turn` |
| `tests/test_live_groq.py` | 2, 5 | `live_llm`: `test_live_streaming_token_cadence` (commit 2), `test_live_llm_invokes_employee_tool` (commit 5) |
| `tests/test_extractor.py` | 3 | `test_extract_text_pdf_native_layer`; `test_extract_scanned_pdf_rapidocr_fallback`, `test_pdfium_and_rapidocr_text_extraction` (`model`) |
| `tests/test_chunker.py` | 3 | `test_structural_heading_chunks`; `test_scanned_gap_chunks` (OCR-boxes fixture); sentence-regex limitation; UUIDv5; tokenizer-dependent tests — the 150-token fallback and `test_total_corpus_chunk_count_is_42` — carry `model` |
| `tests/test_ingestion_cli.py` | 3 | `test_cli_access_table_mismatch_fails_fast`, `test_access_level_canonical_mapping_and_fail_fast`, FR-07/08/10/11 payload tests; `test_cli_recreates_collection`, `test_ingest_cli_execution_and_exit_code`, `test_qdrant_collection_recreation_and_chunk_count` (`model` + `qdrant`, isolated collection); ingestion-side `EMBEDDING_PROVIDER` fail-fast |
| `tests/test_rbac_retrieval.py` | 4 | `test_qdrant_rbac_department_and_level_filter` (spy); the four count tests and `test_rbac_database_layer_filter_enforcement`, `test_hr_exception_allows_cross_department_access` (`qdrant`); NFR-03 latency (`qdrant`); differential pairs (`qdrant` + `model`); `verify_collection_health` unit tests; `test_unauthorized_query_returns_refusal` (`live_llm`) |
| `tests/test_prompt_construction.py` | 4 | `test_prompt_formats_excerpts_as_data_blocks`, `test_prompt_withholds_user_department_and_level`, `test_rag_pipeline_retrieval_and_inline_citations` |
| `tests/test_async_blocking.py` | 4 | `test_embedding_inference_runs_in_thread_pool` — patches `asyncio.to_thread` in the embedder module |
| `tests/test_employee_tool.py` | 5 | `test_tool_execution_parallel_under_1_35s`, `test_employee_tool_executes_parallel_under_1_35s`, `test_tool_subtask_failure_raises_catalog_error`, `test_employee_tool_returns_profile_payload` / `_manager_payload` / `_team_payload` |
| `tests/test_orchestrator_two_pass.py` | 5 | `test_orchestrator_pass1_captures_tool_call`, `test_idor_mismatch_denies_tool_call`, `test_orchestrator_pass2_completes_stream_with_tool_context`, `test_tool_idor_validation_against_jwt_sub`, `test_turn_invokes_employee_context_on_personal_query`; first tool call only |
| `tests/test_error_catalog.py` | 6 | sync transport tests: `test_catalog_exact_strings_mapped_verbatim`, `test_socket_stays_open_after_operational_error`, `test_downstream_failure_emits_error_frame_and_keeps_socket_open`; frame-validation errors; no retries; queueing |
| `tests/test_timeouts.py` | 6 | sync transport tests: `test_turn_timeout_30s_terminates_turn` (small timeout passed as a parameter); the `aclosing` disconnect regression, followed by a fresh connection that works normally (D-85). The auth-timeout case lives in commit 1's `test_auth_failure_emits_frame_and_closes_1008` (D-79) |
| `tests/test_submission_checklist.py` | 7 | `test_offline_suite_requires_no_external_services`, `test_submission_files_and_env_template_present`, `test_readme_submission_contains_required_sections`, `test_readme_documents_provider_selection_rationale` |

The optional memory commit (8, S-03) adds its tests (§5.15) to the existing files that cover the prompt builder and the consumer. The OCR-boxes JSON fixture (§5.7) sits with the test data; its path is not fixed in the sources.

## 3. Markers, configuration and commands

```toml
# pyproject.toml
[tool.pytest.ini_options]
minversion = "8.0"
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-m 'not qdrant and not live_llm and not model'"
markers = [
    "model: Tests requiring local SentenceTransformer model weights (~130MB)",
    "qdrant: Integration tests requiring Qdrant server at localhost:6333",
    "live_llm: E2E tests requiring live Groq API key",
]
```

| Purpose | Command | Needs |
|---|---|---|
| Default offline suite (no coverage gate) | `uv run pytest` | nothing |
| Embedding-model tests (ingestion integrity, tokenizer-dependent chunker tests) | `uv run pytest -m model` | model download (network on first run) |
| Qdrant tests (RBAC counts) | `uv run pytest -m qdrant` | Docker Qdrant on :6333 |
| End-to-end ingestion, semantic differential pairs | `uv run pytest -m "qdrant and model"` | both |
| Full local suite + coverage gate | `uv run pytest -m "not live_llm" --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80` | Docker Qdrant + model |
| Live provider tests | `GROQ_API_KEY=gsk_... uv run pytest -m live_llm` | a provider key |

Integration tests run against `QDRANT_COLLECTION=acme_policies_test` (set by `conftest.py`), never the production collection `acme_policies`. `conftest.py` skips marked tests when the Qdrant port or the key is missing, so a selected marker without its dependency skips rather than fails (C08-STATE).

## 4. Fakes and test seams

| Seam | Purpose |
|---|---|
| `FakeLLMPort` | Implements `LLMPort`; yields scripted `TextDelta` / `ToolCallRequest` sequences with configurable `asyncio.sleep` delays; records the `messages`, `tools` and `tool_choice` of each call |
| `FakeVectorReader` | Implements `VectorReaderPort`; holds `PolicyChunk`s in memory and applies the scope in memory — a test double for orchestrator tests only (the production reader never filters in Python) |
| `FakeQueryEmbedder` | Implements `QueryEmbedderPort`; returns `[0.05] * 384` instantly |
| `FakeEmployeeService` | Implements `EmployeeToolPort` (`get_employee_context(user_id)`); returns the canned combined result without sleeping and records whether it was called |
| Fake `AsyncOpenAI` client | Yields synthetic `ChatCompletionChunk` objects shaped per E07; raises SDK exceptions on demand; can hang in `create()` or before the first chunk |
| `asyncio.to_thread` spy | Patched in the embedder module (`app/adapters/embedder/sentence_transformer.py`) to record that `encode` is dispatched through it (round 11) |
| Fake embedding model | Injected into `SentenceTransformerAdapter(model=…)` so unit tests need no download |
| Timeout parameters | The auth handler, the turn consumer, the LLM adapter and the employee tool take their timeout as a parameter whose default is the constant; tests pass small values (round 11) |
| `make_user_token(...)` (conftest) | Mints HS256 tokens with the test secret: `fin-001` (finance, 1) and the malformed variants; `mint_tokens.py` is treated as read-only (our assumption, A-26) |
| `create_app(settings, orchestrator, use_lifespan=False)` | Builds the app with a fake orchestrator — no Qdrant, no model, no key |
| Starlette `TestClient.websocket_connect` | Drives `/ws/chat` from plain sync `def` transport tests |
| Seeded Qdrant collection | The 42 real payloads (`department`, `access_level`, `source_file`, `page` from the access table, 6 chunks per file) with synthetic vectors, in `acme_policies_test` |
| OCR-boxes fixture | The 18 RapidOCR lines (text + box geometry) of `strategic_plan.pdf`, recorded once |

## 5. Key test designs

### 5.1 Progressive streaming (FR-17, C-02) — transport (sync), default, commit 1
A fake turn yields 7 text deltas with a 0.03 s pause between them; the test records a monotonic timestamp per received frame. Assert: exactly 7 `stream` frames; their texts concatenate exactly to the scripted answer; total stream duration ≥ 0.15 s; every inter-frame gap ≥ 0.015 s; then one `done`. This proves frames leave as deltas arrive, not as one buffered burst.

### 5.2 Blocking proof (NFR-04, C-03) — unit, default, commit 4
`test_embedding_inference_runs_in_thread_pool` patches `asyncio.to_thread` in the embedder module and asserts that `embed_query` dispatches the injected model's `encode` through it (round 11). The earlier heartbeat-and-mutation harness was dropped: the test proves the architectural intent without timing the event loop.

### 5.3 JWT matrix and first-frame rules (NFR-07, FR-13…FR-15, FR-21) — transport (sync), default, commit 1
`test_jwt_matrix_ten_cases`: each case connects, sends `{"type": "auth", "token": …}` and expects `{"type": "auth_failed", "message": "Invalid or expired token"}` followed by close code 1008:

1. expired token (`exp` in the past beyond the 10 s leeway)
2. signed with a different secret
3. `alg: none` — minted with `jwt.encode(payload, None, algorithm="none")` or a hand-built `header.payload.` string (PyJWT refuses to encode `none` with a non-empty key, K11)
4. missing `sub`
5. missing `department`
6. missing `level`
7. `level: "1"`
8. `level: true`
9. `level: 1.0`
10. missing `exp` (round 10, O-15)

First-frame rules: non-JSON → "Invalid JSON frame"; a `message` frame first → "Authentication required as first frame"; `{"type": "auth"}` without a token → "Authentication required as first frame" (error location `("auth", "token")`, E14); silence → "Authentication timed out", with a small auth timeout passed as a parameter; all followed by close 1008. A valid token → exactly `{"type": "auth_success", "user_id": "emp-001", "department": "hr", "level": 1}`. Unit tests on the claims model (`test_auth.py`): unknown department accepted, empty `department` rejected, `level` 0 rejected.

### 5.4 RBAC proof by seeded payloads and filtered counts (NFR-05, FR-03, FR-20, C-04) — integration, `qdrant`, commit 4
Seed `acme_policies_test` with the 42 real payloads and synthetic vectors (no model needed). For each scope, `count` with the filter the reader builds must equal: `emp-001` (hr, 1) **12**, `mgr-002` (hr, 2) **18**, `fin-001` (finance, 1) **24**, `exec-003` (exec, 3) **30**. A filtered scroll per scope contains no forbidden `source_file` (e.g. `exec-003` never gets `expense_policy.pdf` or `travel_reimbursement.pdf`; `emp-001` never gets `performance_review.pdf`). Canonical names: `test_rbac_filter_emp001_sees_12_chunks`, `test_rbac_filter_mgr002_sees_18_chunks`, `test_rbac_filter_fin001_sees_24_chunks`, `test_rbac_filter_exec003_sees_30_chunks_and_no_finance`.
NFR-03 companion (`qdrant`): a filtered `query_points` returns at most 4 chunks in < 200 ms (test ceiling; measured median 1.7 ms, p95 2.3 ms — E03).
Unit companions (default): a spy on `query_points` asserts the exact `must` list (`department MatchAny [department, "hr"]`, `access_level Range(lte=level)`) and limit 4 (FR-19); `query_points` is called and `search` never is; no code path queries without the filter.

### 5.5 Semantic differential pairs — integration, `qdrant` + `model`, commit 4
With the real embedder and the 42 real chunks in `acme_policies_test`:
- "Flight class over 10 hours" → `travel_reimbursement.pdf` retrieved for `fin-001`; absent for `emp-001` and `exec-003`.
- "Performance rating calibration" → `performance_review.pdf` retrieved for `mgr-002`; absent for `emp-001`.
- "Annual leave rollover" → `leave_policy.pdf` retrieved for `emp-001`, `fin-001` and `exec-003` (the `hr` exception).

The automated 24-question golden-set eval was cut in round 11: the deterministic counts (§5.4) prove the DB-layer filter, and the manual checklist (§9) spot-checks answers.

### 5.6 Ingestion integrity — integration, `model` (+ `qdrant` when writing), commit 3
On the real PDFs: 42 chunks in total; 6 from `strategic_plan.pdf`; every payload has `department` as `str`, `access_level` as `int` (never float), `source_file` a file name, `page == 1`; the fallback packer is never called for the six text PDFs (spy); after writing to `acme_policies_test`, a scroll returns 42 points whose `access_level` equals the table value keyed by `department/source_file`.
Tokenizer-dependent chunker tests — the 150-token fallback on synthetic text, the corpus counts — carry `model`, because they use the real bge tokenizer (round 11; no injectable counter).
Unit companions (default suite, synthetic input, no tokenizer): the sentence regex on `"Cost is USD 2,500. Next is Q2 2026. John D. Doe agreed."` returns exactly `["Cost is USD 2,500.", "Next is Q2 2026.", "John D.", "Doe agreed."]` (documented limitation); headings found only by `^\d+\.\s+[A-Z]` (wrapped lines starting with digits are not headings); `HR/leave_policy.pdf`, an unmapped `*.pdf` or a missing mapped file raise the domain error (not `SystemExit`); point ids are deterministic UUIDv5 values; an `EMBEDDING_PROVIDER` other than `sentence-transformers` fails fast (round 10, O-18).

### 5.7 OCR-boxes fixture (NFR-15) — unit, default, commit 3
The recorded boxes of `strategic_plan.pdf` feed the geometric grouping with the 2.0× median-gap threshold: 7 groups (title, intro, Priority 1–4, Board approval) → 6 chunks, each prefixed with "Strategic Plan 2026-2028 (Scanned Copy)". Runs without OCR or the model. Gap data: E02 (median 14 px; paragraph gaps 2.9×–3.9×; in-paragraph 0.7×–1.4×). Canonical name: `test_scanned_gap_chunks`.

### 5.8 `aclosing` and disconnect regression (E15, round 10 O-16)
- Unit, default, commit 2 (`test_llm_adapter.py`): when `run_turn` is closed early, the adapter stream it consumes inside `contextlib.aclosing` is closed (its cleanup has run); a consumer that stops early inside `aclosing` and then awaits completes normally (E15 reproduction).
- Transport (sync), default, commit 6 (`test_timeouts.py`): open a WebSocket, start a turn whose fake LLM streams with delays, and disconnect after the first `stream` frame. Assert both generators' cleanup ran (the turn generator and the adapter stream) and no spurious `CancelledError` reached the connection task.

### 5.9 OpenAI adapter with synthetic chunks (E07) — unit, default, commit 2
1. Fragmented tool call: chunk 1 carries `id="call_1"`, `name="get_employee_context"`, `arguments='{"user_'`; chunk 2 carries `arguments='id": "emp-001"}'` and `finish_reason="tool_calls"` → one `ToolCallRequest` with `parsed_arguments == {"user_id": "emp-001"}`.
2. Chunks with `choices=[]` are skipped without `IndexError`.
3. Text deltas are yielded one by one as they arrive.
4. Error translation to the consolidated catalog (round 11): `RateLimitError` (429) → "System is busy due to high demand. Please try again shortly."; `AuthenticationError` (401), `NotFoundError` (404), `BadRequestError` (400) → "System configuration error. Please contact support."; `InternalServerError` (5xx), `APIConnectionError`, a mid-stream failure, an empty stream and `finish_reason="content_filter"` → "AI service temporarily unavailable. Please try again."; `finish_reason="length"` → "The answer was cut short. Please ask a narrower question."; unparseable tool arguments → "Failed to execute employee lookup."; the SDK's `APITimeoutError` → "Response generation timed out. Please try again.", caught before `APIConnectionError` (C06-STATE).
5. First-token timer with a small timer value passed to the adapter's constructor (round 10, O-09 / O-21): a `create()` that hangs, or a stream whose first chunk arrives too late, → "Response generation timed out. Please try again."; a first chunk of any kind — text, deliberation-only or a tool-call delta — stops the timer.

Canonical names: `test_stream_chat_yields_text_deltas_progressively`, `test_stream_chat_accumulates_tool_call_deltas`, `test_stream_chat_first_token_timeout_triggers_error`, `test_stream_chat_maps_429_to_busy_catalog_message`, `test_stream_chat_skips_empty_choice_chunks`.

### 5.10 Orchestrator two-pass logic — unit, default (commits 4 and 5)
- Retrieval completes before pass 1 is called (FR-02, commit 4).
- Pass 1 receives the tool and `tool_choice="auto"`; after a tool call the tool runs and pass 2 receives the same tools and `tool_choice="none"` (FR-23); never a second tool round.
- Pass-1 deltas are yielded as they arrive (event timing with a delayed fake), not collected first.
- The system prompt contains the caller's `sub` and neither `department` nor `level` (`test_prompt_withholds_user_department_and_level`); excerpts are formatted as labelled data blocks (`test_prompt_formats_excerpts_as_data_blocks`).
- Embedder or reader failure → "Knowledge base search temporarily unavailable" (both, round 11).
- IDOR (round 10, O-01; `test_idor_mismatch_denies_tool_call`, `test_tool_idor_validation_against_jwt_sub`): a tool call whose `user_id` differs from the JWT `sub` → `FakeEmployeeService` is never called, and pass 2 receives a tool message whose content is "Access denied: caller may only query their own context."; the turn ends with pass-2 text and `done`, not an error frame. A matching `user_id` → the tool is called once with that `user_id`.
- Several tool calls in pass 1 (round 10, O-14) → only the first is executed, only that call is echoed in the pass-2 assistant message, and a warning is logged.
- An unknown tool name or a missing/non-string `user_id` → "Failed to execute employee lookup." (round 11).

### 5.11 Parallel tool — unit, default, commit 5
Spies wrap the three fetchers (each `asyncio.sleep(1.0)`); assert all three were called and the call took < 1.35 s (sequential would take ≥ 3 s; E06 measured 1.001 s). No lower bound. Each fetch returns the brief's exact dict and the combined result nests them under `profile` / `manager` / `team`. A failing fetch → `ToolExecutionError` with the siblings cancelled (`test_tool_subtask_failure_raises_catalog_error`). The tool's timeout parameter keeps its 2.0 s default here. The tool itself does no IDOR check (the orchestrator does, §5.10).

### 5.12 Error catalog and socket persistence — transport (sync), default, commit 6
- Authenticated-state validation (E12, E14; lives in commit 1's `test_chat_message_frame_validated`, where `frames.py` lands — D-79; plus the 2,000-character boundary and an emoji message — D-85): text `" "` → length message; 2,001 non-whitespace characters → length message; `{"type": "ping"}`, `{"text": "hi"}`, `{"type": "message", "text": 5}`, non-JSON text and a second auth frame → "Invalid message structure" (round 11); an extra field is ignored. The socket stays open after each.
- Turn errors: a fake orchestrator raising each `TurnError` subclass → exactly one `error` frame carrying one of the 10 consolidated turn-error strings, no `done`, and the next message is processed; an unexpected exception → "Something went wrong. Please try again."; a failing fake LLM is called once (no retries).
- Queueing: two messages sent back-to-back get two complete answers in order, never interleaved.
- Canonical names: `test_catalog_exact_strings_mapped_verbatim`, `test_socket_stays_open_after_operational_error`, `test_downstream_failure_emits_error_frame_and_keeps_socket_open`.

### 5.13 Startup and configuration — unit, default
`verify_collection_health` (commit 4, `test_rbac_retrieval.py`) raises for a missing collection, a vector size of 768 instead of 384, and a sampled `model_name` that differs from `EMBEDDING_MODEL`; the lifespan raises (commit 6; uvicorn's exit code 3 is not asserted). `ServerConfig` (`test_auth.py`): missing or empty `JWT_SECRET` → error (`test_jwt_missing_secret_fails_fast`); a selected provider without key or model → error; Ollama without a key → accepted; an `EMBEDDING_PROVIDER` other than `sentence-transformers` → configuration error (round 10, O-18; commit 4).

### 5.14 Logging, dependency rule, Protocol conformance — unit, default
- Log capture (NFR-12, commit 1): after a turn with known text, no log record contains the message text, a streamed token, an excerpt or the raw JWT.
- Dependency rule (C-09, `test_clean_architecture_dependency_rules`, commit 1): concrete adapters are imported only by `app/main.py` and `scripts/ingest.py` — exactly these two composition roots (round 10, O-23; the CLI exists from commit 3); `domain` imports no I/O, network or database library (`pydantic` schemas are allowed, round 10, O-10); `transport` imports no concrete adapter.
- Protocol conformance (M-28, `test_openai_adapter_satisfies_stream_chat_protocol`): each adapter instance is assigned to a variable typed as its Protocol from `app/domain/ports.py`; mypy strict fails on any mismatch.

### 5.15 Conversation memory (optional S-03, commit 8)
Only if the optional memory commit is built: a pair is appended to the connection's history only after `done` was sent and never after an error; the window keeps the last 3 pairs; `run_turn` receives the history as a tuple; the query embedding never contains history.

## 6. Timeout parameters in tests (round 11)

| Timeout | Parameter of | Default | Value in tests |
|---|---|---|---|
| auth | the auth handler | `AUTH_TIMEOUT_SECONDS` = 10.0 | ~0.2 s in the auth-timeout tests |
| first token (first chunk) | the LLM adapter's constructor | `FIRST_TOKEN_TIMEOUT_SECONDS` = 8.0 | a sub-second value in the adapter timer tests |
| turn | the turn consumer | `TURN_TIMEOUT_SECONDS` = 30.0 | a sub-second value in the turn-timeout test |
| tool | the employee tool's constructor | `TOOL_TIMEOUT_SECONDS` = 2.0 | unchanged in the parallel tool test (real 1 s sleeps) |

## 7. Live-only tests (`live_llm`, need a key)

| Test | Commit | Proves | Assertion |
|---|---|---|---|
| `test_live_streaming_token_cadence` (C-02) | 2 | real provider streaming | a long-answer question ("Summarise every section of the leave policy.") yields more than 5 text deltas; the first-to-last spread is logged, not asserted — Groq can finish a short answer in under 0.1 s (pre-build, D-82) |
| `test_live_llm_invokes_employee_tool` (M-23) | 5 | the real model chooses the tool | "who is my manager" yields exactly one `ToolCallRequest` for `get_employee_context` anywhere in the stream |
| `test_unauthorized_query_returns_refusal` and refusal wording | 4 | prompt-driven refusal (R-11, A-16) | an off-corpus question (e.g. "What is the capital of France?") and `emp-001` asking about executive strategy each get exactly "I cannot find that information in the authorised company policies." |
| Citation check (needs model output) — optional, first time-only cut (D-78, D-80) | 7 | inline citations are grounded | the files an answer cites are a subset of the files retrieved for that turn (K04, D-19); without it, the manual checklist (§9) checks each answer row's expected citation |

These verify U-01, U-02 and U-09; everything else is proven offline or locally. The README test notice is in [README_SUBMISSION-OUTLINE.md](README_SUBMISSION-OUTLINE.md).

## 8. Coverage and static gates

```toml
[tool.coverage.run]
branch = true
source = ["app"]
omit = [
    "app/main.py",     # lifespan composition root
    "tests/*",
]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "class .*\\bProtocol\\):",
]
```

- Gate: ≥ 80 % branch coverage on `app/`, measured on the full local suite `uv run pytest -m "not live_llm"` (Docker Qdrant + embedding model; round 11). The offline default suite has no coverage gate. The OpenAI adapter is not omitted (synthetic chunks); the scan logic is covered by the boxes fixture.
- Static gates per commit: `uv run ruff check .` (rules per D-49, including `C90` with `max-complexity = 10` for the rubric's "small functions", post-review) and `uv run mypy app scripts` (strict via `pyproject.toml`; round 10, O-06).
- Secrets: a scripted git-history scan before submission (NFR-08) — a script, not a pytest test; no CI exists.

## 9. Manual `test_client.html` checklist

Start Qdrant (`docker run -d --name qdrant -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1`), ingest, start the server, open `test_client.html` (file://), paste a token from `uv run python mint_tokens.py` (or the test helper for `fin-001`). Expected answers below are the corpus facts the model should state; exact wording is model output (U-09) except the fixed refusal. Rows marked *(added)* are not in K08's checklist: the `fin-001` rows use golden-set questions (K04), and the last two exercise decided behaviour (D-39 auth failure in a real browser, which closes U-11; D-08 sequential turns).

| Token | Question / action | Expected visible result | What it verifies |
|---|---|---|---|
| `emp-001` | "How many leave days do I get?" | 22 working days of paid annual leave, cites `[leave_policy.pdf, page 1]`; text appears progressively | allowed `hr` retrieval; streaming |
| `emp-001` | "What are the rating distributions for performance reviews?" | "I cannot find that information in the authorised company policies." | Qdrant returns 4 allowed `hr` chunks (no threshold); the refusal is prompt-driven |
| `emp-001` | "What is the meal per-diem for North America?" | the fixed refusal | finance excluded at the DB layer |
| `emp-001` | "Who is my manager?" | ~1 s pause, then that the manager is John Smith; no PDF citation | tool called; three fetches in parallel |
| `emp-001` | "How much leave do I have given my grade?" | grade Senior; 22 working days; the entitlement does not depend on grade | tool data + policy (prompt rule 6) |
| `mgr-002` | "What is the expected distribution across ratings in performance reviews?" | roughly 10/20/50/15/5, cites `[performance_review.pdf, page 1]` | level-2 `hr` access |
| `mgr-002` | "Can I fly business class for flights over 10 hours?" | the fixed refusal | finance excluded for an `hr` manager |
| `exec-003` | "What are the strategic priorities for APAC expansion?" | doubling APAC revenue by end of 2027, Singapore hub, about USD 45 million; cites `[strategic_plan.pdf, page 1]` | scanned PDF was OCR'd and indexed |
| `exec-003` | "What is the peer group size for executive base pay?" | 18 comparable companies, cites `[compensation_committee.pdf, page 1]` | level-3 `exec` access |
| `exec-003` | "How many days of paid sick leave do employees get?" | 10 days of paid sick leave, cites `[leave_policy.pdf, page 1]` | `hr` exception for `exec` |
| `exec-003` | "What expenses require Finance Partner pre-approval?" | the fixed refusal | no finance access for executives (formula + single `hr` exception) |
| `fin-001` *(added)* | "What is the nightly rate cap for hotels?" | USD 250 in designated high-cost cities, USD 180 elsewhere, cites `[travel_reimbursement.pdf, page 1]` | finance access |
| `fin-001` *(added)* | "Can I book flights directly with an airline?" | travel must be booked through the corporate travel portal; direct bookings are not reimbursable except in documented emergencies | finance access |
| any | type only spaces in the input box and press Enter | nothing is sent — the client trims and drops empty input | client-side behaviour |
| any (wscat or a Python client) | send `{"type": "message", "text": "   "}` | error "Message text must be between 1 and 2000 characters"; the socket stays open | server-side validation |
| any *(added)* | paste an invalid token and connect | "auth failed: Invalid or expired token"; the log shows `socket closed (code=1008)` | auth failure path in a real browser (U-11) |
| any *(added)* | send a second message while an answer is streaming | the second answer starts only after the first finishes, in its own bubble | sequential turns |
