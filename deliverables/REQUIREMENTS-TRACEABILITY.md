# Requirements Traceability

This matrix traces every K01 MUST row (M-01…M-34) and CRITERIA row (C-01…C-11) to the PRD requirement that satisfies it, the canonical test or check that proves it, the flat test file and the commit it ships in, the test level, the pytest marker and the evidence behind it; it also shows how the design avoids every REJECTED row (R-01…R-19), the status of the STRETCH rows (S-01…S-03), and where the IMPLICIT and GUIDANCE rows land. Version 1.1 applied the round-10 resolutions: K09 test names are canonical (O-03), tests live in flat `tests/test_*.py` files (O-02) and ship in the commit that introduces the code they guard (O-11); K08 names are kept only as aliases. Version 2 applies round 11: sync transport tests, timeouts as parameters, the isolated integration collection, a one-test blocking proof, tokenizer-dependent chunker tests under `model`, the consolidated catalog and optional conversation memory.

Sources: `knowledge/K01-requirements.md` (row IDs and wording), `knowledge/K08-verification.md` (levels, markers, aliases), `knowledge/K09-prd-plan.md` (FR/NFR and canonical test names, corrected), `inputs/attach/DECISIONS-REGISTER.md` (incl. round-10 and round-11 changes), `knowledge/K10-consolidation.md`, `knowledge/K11-accuracy.md`; evidence E01–E15.

Levels: **unit** (pure Python with fakes, default suite) · **transport** (plain sync `def` tests with the Starlette WebSocket test client against `create_app(..., use_lifespan=False)`, default suite) · **integration** (needs Docker Qdrant and/or the embedding model; uses `QDRANT_COLLECTION=acme_policies_test`) · **live** (needs a provider key) · **manual** (human check) · **README** (document check). Markers: `none` = runs in the default offline `uv run pytest`; `model`, `qdrant`, `live_llm` are excluded by default (`addopts`). Files are under `tests/`; the number after "·" is the commit (IMPLEMENTATION-PLAN).

## 1. MUST and CRITERIA rows

| K01 | Requirement (short) | FR / NFR | Test (canonical) | File · commit | Level | Marker | Evidence | Alias (K08) |
|---|---|---|---|---|---|---|---|---|
| M-01 | FastAPI application | FR-01 | `test_fastapi_app_lifespan_and_startup` | `test_websocket_protocol.py` · 1 (+6) | unit | none | — | `test_app_instance_and_routes` |
| M-02 | Answer with RAG | FR-02 | `test_rag_pipeline_retrieval_and_inline_citations` | `test_prompt_construction.py` · 4 | unit | none | E03 | `test_orchestrator_retrieves_before_llm` |
| M-03 | Enforce RBAC per user | FR-03, NFR-05 | `test_rbac_database_layer_filter_enforcement` | `test_rbac_retrieval.py` · 4 | integration | `qdrant` | E03 | `test_rbac_filter_isolation` |
| M-04 | Text-layer and scanned PDFs | FR-04 | `test_pdfium_and_rapidocr_text_extraction` | `test_extractor.py` · 3 | integration | `model` | E01, E02 | `test_ocr_scanned_pdf_extraction` |
| M-05 | Ingestion script | FR-05 | `test_ingest_cli_execution_and_exit_code` | `test_ingestion_cli.py` · 3 | integration | `model` + `qdrant` | — | `test_ingest_cli_execution` |
| M-06 | Chunks + metadata in a vector DB | FR-06 | `test_qdrant_collection_recreation_and_chunk_count` | `test_ingestion_cli.py` · 3 | integration | `model` + `qdrant` | E03 | `test_qdrant_payload_schema` |
| M-07 | `department` from the folder | FR-07 | `test_metadata_department_extracted_from_folder` | `test_ingestion_cli.py` · 3 | unit | none | — | `test_metadata_department_derivation` |
| M-08 | Integer `access_level` | FR-08 | `test_metadata_access_level_integer_type` | `test_ingestion_cli.py` · 3 | unit | none | E03 (float probe returned) | `test_metadata_access_level_strict_int` |
| M-09 | Exact 7-row mapping | FR-09 | `test_access_level_canonical_mapping_and_fail_fast` | `test_ingestion_cli.py` · 3 | unit | none | — | `test_metadata_mapping_table_exact` |
| M-10 | `source_file` | FR-10 | `test_metadata_source_file_persisted` | `test_ingestion_cli.py` · 3 | unit | none | — | `test_metadata_source_file_preserved` |
| M-11 | `page` | FR-11 | `test_metadata_page_number_1_based` | `test_ingestion_cli.py` · 3 | unit | none | brief §7 (all 1 page) | `test_metadata_page_number_set` |
| M-12 | Expose `/ws/chat` | FR-12 | `test_ws_chat_endpoint_accepts_connection` | `test_websocket_protocol.py` · 1 | transport | none | — | `test_ws_route_accepts_connection` |
| M-13 | Auth frame first | FR-13 | `test_first_frame_auth_payload_received` | `test_websocket_protocol.py` · 1 | transport | none | E12 | `test_auth_first_frame_enforced` |
| M-14 | Exact `auth_success` | FR-14 | `test_auth_success_payload_emission` | `test_websocket_protocol.py` · 1 | transport | none | — | `test_auth_success_payload_shape` |
| M-15 | `auth_failed` then close | FR-15, NFR-10 | `test_auth_failure_emits_frame_and_closes_1008` | `test_websocket_protocol.py` · 1 | transport | none | E13 | `test_auth_failed_closes_1008` |
| M-16 | Exact message frame | FR-16 | `test_chat_message_frame_validated` | `test_websocket_protocol.py` · 1 | transport | none | E12, E14 | `test_message_frame_dispatch` |
| M-17 | Stream frames | FR-17 | `test_stream_tokens_progressive_frames` | `test_websocket_protocol.py` · 1 | transport | none | E07 | `test_stream_frame_delivery` |
| M-18 | `done` frame | FR-18 | `test_stream_finishes_with_done_frame` | `test_websocket_protocol.py` · 1 | transport | none | — | `test_done_frame_on_completion` |
| M-19 | Exact filter logic | FR-19 | `test_qdrant_rbac_department_and_level_filter` | `test_rbac_retrieval.py` · 4 | unit | none | E03 | `test_qdrant_filter_clause_structure` |
| M-20 | `hr` exception | FR-20 | `test_hr_exception_allows_cross_department_access` | `test_rbac_retrieval.py` · 4 | integration | `qdrant` | E03 | `test_hr_exception_cross_department` |
| M-21 | JWT with `JWT_SECRET` | FR-21, NFR-07 | `test_jwt_validation_strict_hs256_env_secret`; `test_jwt_matrix_ten_cases` | `test_auth.py`, `test_websocket_protocol.py` · 1 | unit + transport | none | K02 verified (PyJWT) | `test_jwt_secret_validation` |
| M-22 | One tool for the LLM | FR-22, NFR-06 | `test_tool_idor_validation_against_jwt_sub`; `test_idor_mismatch_denies_tool_call` | `test_orchestrator_two_pass.py` · 5 | unit | none | — | `test_tool_schema_declaration` |
| M-23 | LLM invokes the tool for personal questions | FR-23 | `test_turn_invokes_employee_context_on_personal_query` (fake LLM); `test_live_llm_invokes_employee_tool` | `test_orchestrator_two_pass.py`, `test_live_groq.py` · 5 | unit + live | none / `live_llm` | E05 (U-01) | — |
| M-24 | Exact mock profile | FR-24 | `test_employee_tool_returns_profile_payload` | `test_employee_tool.py` · 5 | unit | none | — | `test_tool_mock_profile_output` |
| M-25 | Exact mock manager | FR-25 | `test_employee_tool_returns_manager_payload` | `test_employee_tool.py` · 5 | unit | none | — | `test_tool_mock_manager_output` |
| M-26 | Exact mock team | FR-26 | `test_employee_tool_returns_team_payload` | `test_employee_tool.py` · 5 | unit | none | — | `test_tool_mock_team_output` |
| M-27 | ~1 s, in parallel | FR-27, NFR-01 | `test_employee_tool_executes_parallel_under_1_35s` (plan: `test_tool_execution_parallel_under_1_35s`) | `test_employee_tool.py` · 5 | unit | none | E06 | `test_tool_parallel_duration_under_1350ms` |
| M-28 | Pluggable LLM / embeddings | FR-28 | `test_openai_adapter_satisfies_stream_chat_protocol` | `test_protocols.py` · 2 | unit (mypy-checked) | none | E05, E10 | `test_adapter_port_type_conformance` |
| M-29 | User-facing error, socket open | FR-29, NFR-09, NFR-11 | `test_downstream_failure_emits_error_frame_and_keeps_socket_open` | `test_error_catalog.py` · 6 | transport | none | E11 | `test_turn_error_keeps_socket_open` |
| M-30 | Exact protocol for the test client | FR-30 | `test_client_html_exact_protocol_flow`; manual checklist | `test_websocket_protocol.py` · 1; checklist · 7 | transport + manual | none | E13 | `test_test_client_protocol_parity` |
| M-31 | Source code + `.env.example` | FR-31, NFR-08 | `test_submission_files_and_env_template_present`; git-history secrets scan (script) | `test_submission_checklist.py` · 7 | unit + manual | none | — | `check_submission_env_example` |
| M-32 | 8-point README | FR-32 | `test_readme_submission_contains_required_sections` | `test_submission_checklist.py` · 7 | README | none | — | `check_readme_submission_8_sections` |
| M-33 | Provider choice documented | FR-33 | `test_readme_documents_provider_selection_rationale` | `test_submission_checklist.py` · 7 | README | none | E05, E09 | `check_readme_documents_groq_choice` |
| M-34 | Commit history | FR-34 | `test_git_history_reflects_vertical_slices` | manual · 7 | manual | none | — | `check_git_commit_history_depth` |
| C-01 | Defensible chunking | FR-32, FR-04, FR-06 | `test_structural_heading_chunks`, `test_scanned_gap_chunks`, `test_total_corpus_chunk_count_is_42` | `test_chunker.py` · 3 | unit + integration | none / `model` | E01, E02 | `test_chunk_token_bounds_and_headings` |
| C-02 | Real token-by-token streaming | FR-17, FR-30 | `test_stream_tokens_progressive_frames`; `test_live_streaming_token_cadence` | `test_websocket_protocol.py` · 1; `test_live_groq.py` · 2 | transport + live | none / `live_llm` | E07 (U-01) | — |
| C-03 | No blocking calls | NFR-04, FR-27 | `test_embedding_inference_runs_in_thread_pool` | `test_async_blocking.py` · 4 | unit | none | E01 | `test_embed_query_unblocks_event_loop` |
| C-04 | RBAC at the DB layer | FR-03, FR-19, FR-20, NFR-05 | `test_rbac_filter_emp001_sees_12_chunks`, `test_rbac_filter_mgr002_sees_18_chunks`, `test_rbac_filter_fin001_sees_24_chunks`, `test_rbac_filter_exec003_sees_30_chunks_and_no_finance` | `test_rbac_retrieval.py` · 4 | unit + integration | none / `qdrant` | E03 | `test_no_post_retrieval_python_filtering` |
| C-05 | Scanned PDF handled automatically | FR-04 | `test_extract_scanned_pdf_rapidocr_fallback` | `test_extractor.py` · 3 | integration | `model` | E01, E02 | `test_pipeline_zero_intervention_ocr` |
| C-06 | Reasonable error handling | FR-29, NFR-09, NFR-11 | `test_catalog_exact_strings_mapped_verbatim`, `test_socket_stays_open_after_operational_error` | `test_error_catalog.py` · 6 | transport | none | — | `test_error_frames_sanitize_internal_trace` |
| C-07 | Code quality | NFR-14 | gates `uv run ruff check .` (incl. `C90`, `max-complexity = 10`, for "small functions") and `uv run mypy app scripts` | every commit | static gate | — | — | `check_mypy_strict_clean` |
| C-08 | README shows judgment | FR-32, FR-33 | `check_readme_defends_tradeoffs` (K08 name; K09 has none) | review · 7 | README | — | — | — |
| C-09 | Production quality | FR-28, FR-31, NFR-14 | `test_clean_architecture_dependency_rules` (K08 name; K09 has none) | `test_protocols.py` · 1 (+3) | unit | none | — | — |
| C-10 | Candidate understands the code | FR-32, FR-34 | `audit_evaluator_interview_readiness` (K08 name) | manual | manual | — | — | — |
| C-11 | Assumptions documented | FR-32 | `check_readme_documents_assumptions` (K08 name) | review · 7 | README | — | — | — |

Notes:
- C-01 is strategy-neutral (K01 correction): it checks that chunks follow the chosen strategy and that the README defends it with data; it does not presuppose overlap.
- C-02 checks that many `stream` frames arrive spread over time, not one large chunk.
- M-23 and C-02 have an offline mechanics test and a live-only proof; the live part depends on U-01.
- Rows marked `model` and/or `qdrant` follow the K08 correction: end-to-end ingestion needs the embedding model, and writing to Qdrant needs the server.
- `test_jwt_matrix_ten_cases` is K09's `test_jwt_matrix_nine_cases` renamed for the 10th case (missing `exp`, O-15) and moved to commit 1 (O-11).
- Where K09 never named a check, the K08 name is the only name (C-08…C-11, the live tests).
- Round 11: `test_embedding_inference_runs_in_thread_pool` now patches `asyncio.to_thread` in the embedder module (no heartbeat or mutation test); tokenizer-dependent chunker tests carry `model`; the automated golden-set eval is cut (the count tests and the manual checklist remain); the coverage gate (≥ 80 % branch) runs on `uv run pytest -m "not live_llm"`. `test_live_groq.py` and `test_protocols.py` are K08's file names, flattened, because K09's plan has no file for those tests.
- Pre-build (D-79): where a row names two tests that check the same behaviour, they are one function — M-04 → `test_extract_text_pdf_native_layer` + `test_extract_scanned_pdf_rapidocr_fallback`; M-05 and M-06 → `test_ingest_cli_execution_and_exit_code`; M-03 → the four `test_rbac_filter_*_chunks` tests; M-20 → `test_rbac_filter_fin001_sees_24_chunks` + `test_rbac_filter_exec003_sees_30_chunks_and_no_finance`; M-22 → `test_tool_idor_validation_against_jwt_sub`; M-23 → `test_turn_invokes_employee_context_on_personal_query`; M-24…M-26 → `test_employee_tool_returns_brief_payloads`; M-27 → `test_employee_tool_executes_parallel_under_1_35s`; M-29 → `test_downstream_failure_emits_error_frame_and_keeps_socket_open`. The other names in the matrix stay as aliases. Inventory: [build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md) §5.

## 2. REJECTED rows — how the design avoids each

| K01 | Rejected behaviour | How the design avoids it | Proof |
|---|---|---|---|
| R-01 | Filtering chunks after retrieval | The RBAC filter is an argument of `query_points`; no code drops returned chunks | Filter spy (FR-19); count tests (NFR-05); alias `test_no_post_retrieval_python_filtering` |
| R-02 | Committing secrets | `.env` is git-ignored (brief `.gitignore`, which covers `miniragchatbot/` only — the code is built there, D-76); `.env.example` holds placeholders only | Scripted git-history scan (NFR-08) |
| R-03 | Fake streaming | The adapter yields each delta as it arrives and the orchestrator yields each pass-1 delta immediately (buffering was rejected) | Progressive-streaming test (FR-17); live cadence test |
| R-04 | Sequential awaits in the tool | `asyncio.TaskGroup` over the three fetches | `test_employee_tool_executes_parallel_under_1_35s` (E06: 1.001 s vs 3.003 s) |
| R-05 | Manual OCR steps | RapidOCR with models bundled in the wheel, no system packages; OCR triggered automatically by `len(text.strip()) == 0` | FR-04 integration test (`model`) |
| R-06 | Unjustified chunk numbers | Chunks follow document structure; the 150-token fallback bound sits above every measured section (35–74 tokens) and inside the 512-token window (E01); overlap 0 with stated reasons | README §4; chunker tests |
| R-07 | Dead code | ruff `F` rules, mypy strict, no speculative features (no `/health`, no connection manager) | Commit gates (NFR-14) |
| R-08 | Leaking stack traces | Fixed catalog strings only; tracebacks go to server logs; last-resort handler sends "Something went wrong. Please try again." | Error-catalog tests (NFR-09) |
| R-09 | HTTP-handshake auth | The server accepts first, then authenticates the first in-band frame | FR-12, FR-13 tests |
| R-10 | Trusting the LLM's `user_id` | The orchestrator compares the tool call's `user_id` with the JWT `sub` before calling the tool; on mismatch the tool is not called and pass 2 receives the denial result "Access denied: caller may only query their own context." | `test_tool_idor_validation_against_jwt_sub`; `test_idor_mismatch_denies_tool_call`; NFR-06 |
| R-11 | Answering from general knowledge | Grounding prompt with the fixed refusal "I cannot find that information in the authorised company policies." | Live refusal test (`live_llm`, U-09) |
| R-12 | Interleaving concurrent streams | One turn at a time per connection; later messages wait in uvicorn's queue (32, then backpressure) | Queueing test in `test_error_catalog.py`; E11 |
| R-13 | A second RBAC exception | Only the `hr` exception exists; with the brief's formula, executives therefore get no finance access (a consequence, not a stated rule) | `test_rbac_filter_exec003_sees_30_chunks_and_no_finance` (`qdrant`) |
| R-14 | Ignoring `exp` | `exp` is a required claim; expired tokens and tokens without `exp` fail | JWT matrix cases 1 (expired) and 10 (missing `exp`) |
| R-15 | Unpinned JWT algorithm | `algorithms=["HS256"]` | JWT matrix case 3 (`alg: none`) |
| R-16 | Default JWT secret in the server | `JWT_SECRET` is required and non-empty; no literal default; startup fails without it | `test_jwt_missing_secret_fails_fast` (alias `test_jwt_secret_validation`) |
| R-17 | Modifying provided files | `mint_tokens.py` and `test_client.html` are treated as read-only — our assumption (A-26), the brief does not forbid editing them; `fin-001` comes from a test-token helper | Manual review; FR-30 |
| R-18 | Loading the model per request | Loaded once in the lifespan (`asyncio.to_thread`) and injected into the embedder adapter | Lifespan test; blocking detector |
| R-19 | Global shared state | No connection manager or session registry; history is a local variable of the handler | Two-connection isolation is structural (no shared object to cross over) |

## 3. STRETCH rows

| K01 | Stretch item | Status |
|---|---|---|
| S-01 | Reranker | Not in scope (non-goal) |
| S-02 | Hybrid search (BM25 + vector) | Not in scope (non-goal) |
| S-03 | Conversation memory across turns | OPTIONAL (round 11): implemented last, only if time remains (IMPLEMENTATION-PLAN commit 8); the core pipeline is stateless. If built: last 3 question/answer pairs of final plain text, appended after `done`, sent to the LLM only; retrieval uses the current question only (E04: follow-ups 4/4 either way, topic switches 3/3 current-only vs 1/3 concatenated). First item in the cut order |

## 4. IMPLICIT and GUIDANCE rows

| K01 | Statement | Where it lands |
|---|---|---|
| I-01 | Accept the upgrade without auth headers | FR-12, FR-30 |
| I-02 | `done` or `error` terminates a stream | FR-18, FR-29 (one `error`, no `done`) |
| I-03 | Unknown frame types are safe for the client | The server only emits the protocol's five server frames: `auth_success`, `auth_failed`, `stream`, `done`, `error` |
| I-04 | `auth_success` carries `user_id`, `department`, `level` (explicit in the brief) | FR-14 |
| I-05 | Exact runtime error shape `{"type": "error", "message": …}` | FR-29 |
| I-06 | Strict JSON frames | FR-30 |
| G-01 | Prefer free-tier models | FR-33 (Groq free plan, E05) |
| G-02 | Any libraries allowed | ARCHITECTURE §2 dependencies |
| G-03 | Free choice of text vs OCR approach | D-05, D-06 |
| G-04 | Plain text over Markdown (a should-not, the client renders text literally) | Prompt rule 3 |
