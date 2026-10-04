# Implementation Plan

This plan sequences the build as seven thin vertical slices, one commit each, plus one optional slice: for every commit it gives the commit message, goal, files, the tests written first, the gate commands, the manual check and the time estimate. Version 2 applies the K09 corrections and the round-10 and round-11 changes: a stateless core with conversation memory as an optional last commit, the consolidated error catalog, sync transport tests, timeouts as parameters, an isolated integration collection, a one-test blocking proof, no token counter, no golden-set eval and an 80 % coverage gate on the full local suite. It closes with a revised time estimate against the brief's "~4–6 hours" and the cut order, which never cuts a MUST.

Sources: `knowledge/K09-prd-plan.md` (implementation plan and its corrections), `knowledge/K07-architecture.md` (commit messages, slice intent, module paths), `knowledge/K08-verification.md` (key tests, markers), `inputs/attach/DECISIONS-REGISTER.md` (commit slices; round-10 and round-11 changes), `knowledge/K10-consolidation.md`, `knowledge/K11-accuracy.md`, `inputs/00-brief.md` (time budget, commits are evaluated).

---

## 1. Rules for every commit

- One thin vertical slice that runs end-to-end; the first commit is a walking skeleton visible in `test_client.html`.
- Every test ships in the commit that introduces the code it guards and is written first (O-11); the commit passes its gates before it is made.
- Conventional commit messages (titles below, from K07).
- Tests are flat `tests/test_*.py` files with K09's names (O-02/O-03; layout in TEST-PLAN §2); the four Protocols live in one module, `app/domain/ports.py` (O-04).
- Transport tests are plain sync `def` tests; every timeout is a parameter whose default is its constant, and tests pass small values; integration tests use `QDRANT_COLLECTION=acme_policies_test` (round 11).
- The core pipeline is stateless: each message is answered on its own. Conversation memory (S-03) is the optional commit 8 (round 11).
- Gates: `uv run ruff check .` (rules per D-49, including `C90` with `max-complexity = 10`, post-review) · `uv run mypy app scripts` (strict via `pyproject.toml`; O-06) · the tests named per commit.
- Location (post-review, D-76): all code is built inside `miniragchatbot/`, next to the provided `docs/`, `mint_tokens.py`, `test_client.html`, `.env.example` and `.gitignore`. Every file path and command in this plan is relative to `miniragchatbot/` and runs from there. The provided `.gitignore` only covers that folder.

**Prerequisites** (brief §7, measured on the candidate's machine): uv 0.12.18 and Docker are installed; Python 3.12 is provisioned by uv (system `python3` is 3.9.6); a `GROQ_API_KEY` is needed from commit 2 for the manual checks and the `live_llm` tests. Qdrant: `docker run -d --name qdrant -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1` (O-05). Before the 2-hour clock all of this runs as pre-flight P1–P9 ([build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md), D-78).

## 2. Overview

| # | Slice | Minutes (K09 best case) | 2-hour run box (pre-build, D-78) |
|---|---|---|---|
| 1 | Skeleton: auth handshake, protocol, stub streaming | 45 | 17 (T+0–17) |
| 2 | Real LLM streaming adapter | 45 | 14 (T+17–31) |
| 3 | Document ingestion pipeline and CLI | 50 | 20 (T+31–51) |
| 4 | RBAC retrieval and grounded prompting | 45 | 15 (T+51–66) |
| 5 | Parallel employee tool and two-pass orchestration | 45 | 12 (T+66–78) |
| 6 | Error catalog, timeouts, event-loop integrity, lifespan checks | 40 | 15 (T+78–93) |
| 7 | Documentation, verification matrix, submission audit | 35 | 17 (T+93–110) |
| | Close-out: final review, gates, merge to `master` (no push) | — | 10 (T+110–120) |
| | **Commits 1–7** | **305 best case; estimate up to 360 (§5)** | **120 including close-out; pre-flight runs before the clock** |
| 8 | *Optional:* conversation memory (S-03) | not budgeted — only if time remains | not in the 2-hour run |

## 3. Commits

### Commit 1 — Skeleton: auth handshake, protocol, stub streaming (45 min)
- **Message:** `feat(skeleton): walking skeleton with in-band auth and stub token streaming`
- **Goal:** repository structure and packaging; `/ws/chat`; JWT validation (HS256, required claims, leeway 10 s); frame schemas; the auth handshake (auth timeout as a parameter defaulting to 10 s, `auth_failed` then close 1008); a stub turn that streams word deltas and ends with `done`, proving client compatibility.
- **Files:** `pyproject.toml`, `.env.example`, `.gitignore`; `app/__init__.py`, `app/main.py`, `app/config.py` (`ServerConfig`, per K07 — K09's list omitted it); `app/domain/constants.py`, `app/domain/models.py`, `app/domain/events.py`, `app/domain/exceptions.py`; `app/transport/websocket/auth.py`, `frames.py`, `routes.py`; `tests/conftest.py`, `tests/test_auth.py`, `tests/test_websocket_protocol.py`, `tests/test_protocols.py`.
- **Tests written first** (one function per test, D-79; plan names in brackets): `test_jwt_validation_strict_hs256_env_secret` [`test_jwt_decode_valid_claims`], `test_jwt_decode_expired_token`, `test_jwt_decode_unpinned_algorithm_rejected`, `test_jwt_missing_secret_fails_fast`; the sync transport tests `test_ws_chat_endpoint_accepts_connection`, `test_first_frame_auth_payload_received`, `test_auth_success_payload_emission` [`test_ws_auth_first_frame_success`], `test_auth_failure_emits_frame_and_closes_1008` [`test_ws_auth_invalid_payload_closes_1008`, `test_ws_auth_timeout_closes_1008` — one test over the timeout, non-JSON, non-auth and bad-token cases, with a small auth timeout passed as a parameter], `test_chat_message_frame_validated` (including the 2,000-character boundary and an emoji message, D-85), `test_stream_tokens_progressive_frames` [the progressive-streaming test], `test_stream_finishes_with_done_frame` [`test_ws_stub_stream_and_done`], `test_client_html_exact_protocol_flow`; `test_jwt_matrix_ten_cases` (O-11, O-15); `test_clean_architecture_dependency_rules`; the log-capture test (NFR-12).
- **Gates:** `uv run ruff check .` · `uv run mypy app scripts` · `uv run pytest -m "not model and not qdrant and not live_llm"`
- **Manual check:** open `test_client.html`, authenticate with a token from `mint_tokens.py`, send a message; stub frames appear token by token and the streaming cursor clears on `done`.

### Commit 2 — Real LLM streaming adapter (45 min)
- **Message:** `feat(llm): OpenAI-compatible adapter and real token streaming`
- **Goal:** the OpenAI-compatible adapter (`openai.AsyncOpenAI`) behind the streaming port: real text deltas, tool-call argument accumulation per index, empty-`choices` guard; the 8 s first-token timer — a constructor parameter defaulting to `FIRST_TOKEN_TIMEOUT_SECONDS` — which runs from request start (`create`) to the first chunk of any kind, with no separate connect timeout (O-09, O-21); SDK exceptions mapped to the consolidated catalog: 400/401/404 → configuration, 429 → busy, 5xx / connection / mid-stream drop / empty answer / `content_filter` → "AI service temporarily unavailable. Please try again.", `length` → cut short, unparseable tool arguments → "Failed to execute employee lookup.", `APITimeoutError` → timeout (round 11); provider selection by `LLM_PROVIDER` with fail-fast on a missing key or model, OpenRouter and OpenAI base URLs per ARCHITECTURE §9.3 (O-20). K07 adds wiring the prompt builder so the turn streams live LLM output; `run_turn` consumes the adapter stream inside `contextlib.aclosing` (O-16).
- **Files:** `app/domain/ports.py`, `app/adapters/llm/openai_adapter.py`, `app/transport/websocket/routes.py`, `tests/test_llm_adapter.py`, `tests/test_live_groq.py`.
- **Tests written first:** `test_stream_chat_yields_text_deltas_progressively`, `test_stream_chat_accumulates_tool_call_deltas`, `test_stream_chat_first_token_timeout_triggers_error`, `test_stream_chat_maps_429_to_busy_catalog_message`, `test_stream_chat_skips_empty_choice_chunks` — all offline with synthetic chunks; the early-close (`aclosing`) unit test; `test_openai_adapter_satisfies_stream_chat_protocol` (in `test_protocols.py`); `test_live_streaming_token_cadence` (`live_llm`, O-11).
- **Gates:** `uv run ruff check .` · `uv run mypy app scripts` · `uv run pytest -m "not model and not qdrant and not live_llm"`
- **Manual check:** run the server with a valid `GROQ_API_KEY`, send a prompt from `test_client.html`; real tokens stream progressively into the bubble (first live look at Groq streaming; the tool-with-streaming part of U-01 comes in commit 5).

### Commit 3 — Document ingestion pipeline and CLI (50 min)
- **Message:** `feat(ingest): document extraction, RapidOCR fallback, and indexing CLI`
- **Goal:** pypdfium2 extraction with RapidOCR (300 dpi) for pages whose text layer is empty; structural chunking (42 chunks) with the 150-token fallback counted by the bge tokenizer; deterministic UUIDv5 ids; access-table validation; collection recreated with payload indexes; upsert through the synchronous `QdrantClient` (`VectorWriterPort`); CLI mapping domain errors to exit 1, with `--docs-dir` overriding `IngestConfig.DOCS_DIR` (O-19) and an `EMBEDDING_PROVIDER` other than `sentence-transformers` failing fast (O-18). `scripts/ingest.py` is the second, CLI-only composition root (O-23).
- **Files:** `app/ingestion/extractor.py`, `app/ingestion/chunker.py`, `app/adapters/embedder/sentence_transformer.py`, `app/adapters/vector_store/qdrant_writer.py`, `scripts/ingest.py`; `tests/test_extractor.py`, `tests/test_chunker.py`, `tests/test_ingestion_cli.py`. K07's tree also has `app/ingestion/pipeline.py` and `IngestConfig` in `app/config.py`.
- **Tests written first:** `test_extract_text_pdf_native_layer`, `test_extract_scanned_pdf_rapidocr_fallback`; `test_structural_heading_chunks`, `test_scanned_gap_chunks`, `test_total_corpus_chunk_count_is_42`; `test_access_level_canonical_mapping_and_fail_fast` (merges `test_cli_access_table_mismatch_fails_fast`; a stray non-PDF file such as `.DS_Store` is ignored — D-85), `test_ingest_cli_execution_and_exit_code` (one end-to-end run, repeated once to prove recreation — merges `test_cli_recreates_collection` and `test_qdrant_collection_recreation_and_chunk_count`, D-79); the dependency-rule test extended to allow `scripts/ingest.py`. Tests that run OCR or the bge tokenizer (including the 150-token fallback) carry `model`; tests that write to Qdrant carry `qdrant` and use `acme_policies_test`; the OCR-boxes JSON fixture keeps the geometric grouping in the default suite.
- **Gates:** `uv run ruff check .` · `uv run mypy app scripts` · `uv run pytest -m "not model and not qdrant and not live_llm"` · `uv run pytest -m "model and qdrant"` (42 vectors indexed)
- **Manual check:** with Qdrant running, `uv run python -m scripts.ingest --docs-dir ./docs` indexes the corpus, prints the summary (7 files, 42 chunks) and exits 0 (K07 runnable criterion).

### Commit 4 — RBAC retrieval and grounded prompting (45 min)
- **Message:** `feat(rag): RBAC vector retrieval and grounded prompt construction`
- **Goal:** the `AsyncQdrantClient` reader with the filter inside `query_points` (`department MatchAny [user.department, "hr"]` AND `access_level Range(lte=user.level)`); the canonical prompt with excerpt blocks, inline `[file.pdf, page N]` citations and the fixed refusal; retrieval before pass 1 (stateless: no history). **Correction applied:** the embedder runs in the server from this commit, so model load and `encode` go through `asyncio.to_thread` here, not in commit 6; the server-side `EMBEDDING_PROVIDER` fail-fast check lands with the embedder wiring (O-18).
- **Files:** `app/adapters/vector_store/qdrant_reader.py`, `app/domain/prompt.py`, `app/domain/orchestrator.py`; `tests/test_rbac_retrieval.py`, `tests/test_prompt_construction.py`, `tests/test_async_blocking.py`.
- **Tests written first:** `test_rbac_filter_emp001_sees_12_chunks`, `test_rbac_filter_mgr002_sees_18_chunks`, `test_rbac_filter_fin001_sees_24_chunks`, `test_rbac_filter_exec003_sees_30_chunks_and_no_finance` (`qdrant`, seeded payloads in `acme_policies_test`); `test_unauthorized_query_returns_refusal` (**`live_llm`**, corrected from `qdrant` — it checks LLM wording); `test_prompt_formats_excerpts_as_data_blocks`, `test_prompt_withholds_user_department_and_level`; `test_embedding_inference_runs_in_thread_pool` — one unit test that patches `asyncio.to_thread` in the embedder module (round 11; with the code it guards, O-11). Pre-build: the count tests also cover an unknown or differently-cased department that sees only `hr` content (D-85); `test_rbac_database_layer_filter_enforcement` and `test_hr_exception_allows_cross_department_access` are aliases of the count tests (D-79).
- **Gates:** `uv run ruff check .` · `uv run mypy app scripts` · `uv run pytest -m "not model and not qdrant and not live_llm"` · `uv run pytest -m "qdrant"`
- **Manual check:** as `emp-001`, ask about executive strategy → the fixed refusal; ask about the leave policy → grounded answer citing `[leave_policy.pdf, page 1]`.

### Commit 5 — Parallel employee tool and two-pass orchestration (45 min)
- **Message:** `feat(tools): parallel employee context lookup and pass-2 synthesis`
- **Goal:** `get_employee_context(user_id)` with an `asyncio.TaskGroup` over profile, manager and team inside `asyncio.timeout` — the tool's timeout is a constructor parameter defaulting to 2.0 s (< 1.35 s in practice); the two-pass loop (pass 1 `tool_choice="auto"`, pass 2 same tools with `tool_choice="none"`, at most one tool round). The orchestrator compares the tool call's `user_id` with the JWT `sub` before calling the tool; on mismatch it does not call the tool and sends the denial tool result "Access denied: caller may only query their own context." to pass 2 (O-01). If pass 1 yields several tool calls, only the first is executed and echoed, with a warning logged (O-14). An invalid tool request (unknown name, missing or non-string `user_id`) → "Failed to execute employee lookup." (round 11).
- **Files:** `app/adapters/employee_tool/mock_service.py`, `app/domain/orchestrator.py`; `tests/test_employee_tool.py`, `tests/test_orchestrator_two_pass.py`, `tests/test_live_groq.py`.
- **Tests written first** (one function per test, D-79; plan names in brackets): `test_employee_tool_executes_parallel_under_1_35s` [`test_tool_execution_parallel_under_1_35s`], `test_employee_tool_returns_brief_payloads`, `test_tool_subtask_failure_raises_catalog_error`; `test_turn_invokes_employee_context_on_personal_query` [`test_orchestrator_pass1_captures_tool_call`, `test_orchestrator_pass2_completes_stream_with_tool_context` — it also checks that text the model emits before the tool call streams before the ~1 s pause, D-85], `test_tool_idor_validation_against_jwt_sub` [`test_idor_mismatch_denies_tool_call`; on a mismatch the tool is not called and pass 2 receives the denial result]; the first-tool-call-only test; the invalid-tool-request test; `test_live_llm_invokes_employee_tool` (`live_llm`, O-11).
- **Gates:** `uv run ruff check .` · `uv run mypy app scripts` · `uv run pytest -m "not model and not qdrant and not live_llm"`
- **Manual check:** in `test_client.html` ask "Who is my manager and what is my leave entitlement?"; the answer combines the tool data (John Smith) with the retrieved policy (22 working days) after a ~1 s pause (first live look at Groq tool calling with streaming, U-01).

### Commit 6 — Error catalog, timeouts, event-loop integrity, lifespan checks (40 min)
- **Message:** `feat(resilience): error catalog mapping, timeouts, and startup health assertions`
- **Goal:** every domain and provider exception mapped to the consolidated catalog — 10 turn-error strings plus the 4 `auth_failed` texts (round 11) — with the socket kept open; the turn timeout in the consumer — a parameter defaulting to 30 s — with `contextlib.aclosing` and no timeout context open across a `yield` (O-16); the last-resort handler; fail-fast lifespan checks (collection exists, vector size 384, sampled `model_name`) so uvicorn exits with code 3; no startup model ping. (The 8 s first-token timer is in place since commit 2; `asyncio.to_thread` since commit 4.)
- **Files:** `app/domain/exceptions.py`, `app/domain/constants.py`, `app/main.py`, `app/transport/websocket/routes.py`; `tests/test_error_catalog.py`, `tests/test_timeouts.py`.
- **Tests written first:** the sync transport tests `test_catalog_exact_strings_mapped_verbatim`, `test_downstream_failure_emits_error_frame_and_keeps_socket_open` [`test_socket_stays_open_after_operational_error`, D-79], `test_turn_timeout_30s_terminates_turn` (small timeout passed as a parameter), the queueing test; the `aclosing` disconnect regression, followed by a fresh connection that works normally (D-85); the lifespan checks of `test_fastapi_app_lifespan_and_startup`. The auth-timeout case already ships in commit 1, inside `test_auth_failure_emits_frame_and_closes_1008` (D-79).
- **Gates:** `uv run ruff check .` · `uv run mypy app scripts` · `uv run pytest` (default offline suite; no coverage gate) · `uv run pytest -m "not live_llm" --cov=app --cov-branch --cov-fail-under=80` (full local suite; Docker + model)
- **Manual check (pre-build, D-81):** three failure drills against the real server — (1) `docker stop qdrant`, ask a question → `error` "Knowledge base search temporarily unavailable" and the socket stays open; `docker start qdrant` → the next question is answered; (2) start the server with `QDRANT_COLLECTION` pointing at a missing collection → startup aborts with exit code 3 and a clear log line; (3) start it with a wrong `GROQ_API_KEY` → `error` "System configuration error. Please contact support." and the socket stays open.

### Commit 7 — Documentation, verification matrix, submission audit (35 min)
- **Message:** `docs: comprehensive submission README and verification suite`
- **Goal:** `README_SUBMISSION.md` with the 8 mandated sections, provider choice and swap, assumptions, test notice and known limitations; the finance test-token helper; end-to-end verification against the role matrix with the manual checklist. The automated 24-question golden-set eval is cut (round 11): the RBAC count test (12/18/24/30) and the manual checklist remain.
- **Files:** `README_SUBMISSION.md`, `scripts/generate_test_tokens.py`, `tests/test_submission_checklist.py`.
- **Tests written first:** `test_offline_suite_requires_no_external_services` and the README/submission checks (FR-31…FR-33). **Correction applied:** the git-history secrets scan is a script run before submission, not a pytest test (`test_git_history_contains_no_secrets` is dropped as a test).
- **Gates:** `uv run ruff check .` · `uv run mypy app scripts` · `uv run pytest -m "not live_llm" --cov=app --cov-report=term-missing --cov-branch --cov-fail-under=80` (≥ 80 % branch on `app/`) · the secrets-scan script
- **Manual check:** the full checklist (TEST-PLAN §9) with `emp-001`, `mgr-002`, `exec-003` and a generated finance token in `test_client.html`.
- **Submission (post-review, D-77):** the repository's `origin` is the CodeSubmit remote (`git.codesubmit.io/etihad-airways/ai-chatbot-challenge-aspest`), so submitting means pushing `master` there — only on the owner's explicit go. Before pushing, the owner decides whether `deliverables/` is part of the submission (OPEN).

### Commit 8 (optional) — Conversation memory, S-03 (only if time remains)
- **Message:** `feat(memory): bounded conversation history for the LLM` (title not fixed in the sources)
- **Goal:** the last 3 question/answer pairs of final plain text, appended by the consumer only after `done` was sent (never after an error), passed to `run_turn` as a tuple and sent to the LLM as alternating user/assistant messages; retrieval keeps using the current question only (E04). README updated to describe it.
- **Files:** `app/transport/websocket/routes.py`, `app/domain/orchestrator.py`, `app/domain/prompt.py`, `README_SUBMISSION.md`, and tests in the existing flat files.
- **Tests written first:** history appended only after `done`; nothing appended after an error; window trimmed to 3 pairs; history passed as a tuple; history never in the query embedding (TEST-PLAN §5.15).
- **Gates:** as commit 7.
- **Manual check:** ask a follow-up question in `test_client.html` that only makes sense with the previous answer.
- **Time:** not budgeted; start only if commits 1–7 finish within the estimate (§5).

### Register key tests and where they ship (O-11)

| Key test (register / K08) | Ships in | Feature it guards lands in |
|---|---|---|
| Progressive streaming with a delayed fake | commit 1 (`test_websocket_protocol.py`) | commit 1 (stub stream), commit 2 (real adapter) |
| Blocking proof: `asyncio.to_thread` patched in the embedder module | commit 4 (`test_embedding_inference_runs_in_thread_pool`) | commit 4 |
| JWT matrix, 10 cases | commit 1 (`test_jwt_matrix_ten_cases`) | commit 1 |
| RBAC counts 12/18/24/30 (`qdrant`) | commit 4 | commit 4 |
| Semantic differential pairs (`qdrant` + `model`) | commit 4 (`test_rbac_retrieval.py`) | commit 4 |
| Ingestion integrity 42 / 6 (`model`) | commit 3 (`test_total_corpus_chunk_count_is_42`) | commit 3 |
| `aclosing` regression | commit 2 (adapter stream inside `run_turn`) and commit 6 (consumer) | commits 2 and 6 |
| Adapter with synthetic chunks | commit 2 | commit 2 |
| Live-only: cadence, refusal wording, tool choice | commits 2, 4, 5 | commits 2, 4, 5 |
| Conversation-memory tests | optional commit 8 | optional commit 8 |

## 4. Corrections and resolutions applied to K09's plan

1. `asyncio.to_thread` for `encode` exists from commit 4 (the first commit in which the server encodes), not commit 6.
2. `test_unauthorized_query_returns_refusal` is a `live_llm` test (LLM wording), not a `qdrant` test.
3. The secrets scan is a script, not a pytest test.
4. Ingestion writes through the synchronous `QdrantClient` (FR-06 correction).
5. No startup "pre-flight" model ping in the lifespan checks (RR-01 correction).
6. The 305-minute total is optimistic (K09 correction; confirmed in round 11) — see §5.
7. Round 10: tests move to the commit that introduces their code (JWT matrix → commit 1 with 10 cases; blocking proof → commit 4; live tests → commits 2, 4 and 5); flat test files with K09's names; one `app/domain/ports.py`; gates use `uv run mypy app scripts`; the IDOR denial result, first-tool-call-only, first-chunk timer, error mappings, `EMBEDDING_PROVIDER` and `--docs-dir` rules and the second composition root are placed in commits 2–5.
8. Round 11: the catalog is consolidated (10 turn errors + 4 `auth_failed` texts); transport tests are sync `def` tests; timeouts are parameters with the constants as defaults; integration tests use `acme_policies_test`; the blocking proof is one `asyncio.to_thread` patch test; the injectable token counter, the heartbeat/mutation harness and the automated golden-set eval are cut; the coverage gate is ≥ 80 % branch on `uv run pytest -m "not live_llm"`; conversation memory moves to the optional commit 8.
9. Pre-build (2026-10-04, D-78…D-85): the 2-hour execution layer with pre-flight before the clock (D-78); one function per test (D-79); citations checked by the manual checklist (D-80); commit-6 failure drills (D-81); the cadence test de-flaked (D-82); `uvicorn[standard]`, dev `httpx` and the mypy override policy (D-83); `scripts/ws_probe.py` and `scripts/scan_secrets.py` named (D-84); five review-focus test cases (D-85).

## 5. Time estimate (revised)

K09's per-commit figures add up to **305 minutes**. The K09 review called that optimistic, and the round-11 accuracy review called the full plan "highly optimistic and unrealistic for one sitting" unless the cut order was applied. Round 11 applied those cuts: memory moved out of the core, the golden-set eval, the blocking harness and the token counter cut, the catalog consolidated. The honest estimate for commits 1–7 is therefore **between the 305-minute best case and 6 hours (360 minutes)** — the top of the brief's "~4–6 hours" range; plan to 360 minutes. The optional commit 8 is outside this estimate and starts only if commits 1–7 finish with time to spare. Actual time per commit should be tracked so the cut order can be applied early (U-15).

Not inside this estimate (post-review): SIGN-OFF §2's day-1 checklist ("first hour"). Checks 4, 6 and 7 (model download, `uv sync`, Qdrant + ingestion) are the same work as commits 1 and 3. Checks 1–3 (one Groq script) and 5 (OCR) are extra, estimated at 20–30 minutes, so the realistic total is about 6–6.5 hours. The brief states "~4–6 hours of focused work" and "You have 3 days to submit."

**Two-hour run (pre-build, D-78).** The owner's limit for this build is 120 minutes, including tests and real runs. [build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md) fits it: pre-flight P1–P9 before the clock, the boxes in the §2 table, a 10-minute close-out, tripwires and the tracker protocol; actual minutes per slice go to [build/TRACKER.md](build/TRACKER.md). The estimate above stays as the human-pace figure.

## 6. Cut order (never cut a MUST)

Apply from the top when time runs short:

1. **S-03 conversation memory** — already optional (commit 8): skip it. The core pipeline is stateless, so nothing else changes.
2. **S-01 / S-02 reranker and hybrid search** — already non-goals; nothing to remove (listed by K09 for completeness).
3. **Alternative-provider testing** — stop spending time on Ollama or other hosted providers and test only Groq (`openai/gpt-oss-120b`). The LLM port, the single OpenAI-compatible adapter and the `LLM_PROVIDER` configuration path stay: the register requires the `LLM_PROVIDER` selector with per-provider variables, and pluggability is MUST row M-28. K09 words this cut as "restrict adapter wiring solely to Groq"; the register overrides that literal reading, so the cut is limited to testing.
4. **Standalone fixture scripts** — fold `scripts/generate_test_tokens.py` into the pytest fixture `make_user_token`. The manual `fin-001` check depends on having a finance token outside pytest.

Never cut: any MUST row M-01…M-34 (FR-01…FR-34), and none of the error-handling, RBAC, streaming or parallel-tool proofs.

**Time-only cuts for the 2-hour run (pre-build, D-78)** — applied in this order when a slice overruns its box by more than 5 minutes, each logged in the tracker: (a) the live citation test (D-80); (b) the semantic differential pairs (TEST-PLAN §5.5); (c) the NFR-03 latency test; (d) the manual checklist reduced to its 9 core rows (for each of the three brief users one allowed and one refused question, the tool row, the invalid-token row and the whitespace row). None of them is a MUST proof.
