# Sign-off — confidence, day-1 verification, accepted risks, verdict

Purpose: the final confidence assessment of the plan before implementation starts — how sure we are that each requirement will hold when the evaluator runs `test_client.html`, what must be verified in the first hour, which risks are knowingly accepted, and the go/no-go verdict.
Sources: K12 (round 12, Gemini 3.1 Pro, with reviewer corrections), K11, DECISIONS-REGISTER, REQUIREMENTS-TRACEABILITY.md, RISKS-ASSUMPTIONS.md, evidence E01-E17.

## 1. Confidence per requirement

HIGH = verified evidence or deterministic code plus a test. MEDIUM = depends on documented-but-unverified provider behaviour, the evaluator's environment, or prompt-driven model behaviour. LOW = none remaining.

| Rows | Confidence | Why | Cheapest action to raise to HIGH |
|---|---|---|---|
| M-01, M-03, M-04, M-05, M-07–M-14, M-16, M-18–M-22, M-24–M-29, M-31–M-34 | HIGH | Deterministic code paths, each with a test (TEST-PLAN) and, where relevant, measured evidence (E01–E04, E06, E11–E15, E17) | — |
| M-02 RAG answers | MEDIUM | Needs the live provider to be available within free-plan limits (RR-01, U-16) | Live smoke test just before submission |
| M-06 vector DB | MEDIUM | Needs Docker on the evaluator machine (RR-05) | Exact `docker run` command in the README; fail-fast startup message |
| M-15 auth_failed then close | MEDIUM | Browser close handshake not yet observed (U-11; E13/E17 used a Python client) | One manual invalid-token check in `test_client.html` |
| M-17 stream frames, C-02 real streaming, R-03 no fake streaming | MEDIUM | Groq tool calling together with `stream=true` is documented separately, not as a combination (U-01, U-02) | Day-1 check 1 (live Groq stream with tools) |
| M-23 model calls the tool, R-11 refuses general knowledge | MEDIUM | Prompt-driven model behaviour (U-09) | Live tests (`-m live_llm`): tool call on "who is my manager", refusal wording |
| M-30 exact protocol for the provided client | MEDIUM | Final proof is the manual browser run (U-11) | Complete the manual checklist (TEST-PLAN) |
| C-01 defensible chunking | MEDIUM | The 2.0x OCR paragraph threshold was measured on one machine (U-10, E02) | Run the `model`-marked ingestion integrity test (42 / 6 chunks) on the evaluator-like machine |
| C-03–C-11, R-01, R-02, R-04–R-10, R-12–R-19 | HIGH | Code + tests + evidence (e.g. E03 filter, E06 TaskGroup, E12 validation, E15 aclosing) | — |

## 2. Day-1 verification checklist (first hour, before features)

All commands run from `miniragchatbot/`. Time (post-review): this hour is not inside IMPLEMENTATION-PLAN §5. Checks 4, 6 and 7 are the same work as the commit-1 setup and the commit-3 ingestion; checks 1–3 (one Groq script) and 5 (OCR) are extra, estimated at 20–30 minutes. For the 2-hour run (pre-build, D-78) every check here runs **before the clock** as pre-flight P1–P9 in [build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md); results are recorded in [build/TRACKER.md](build/TRACKER.md) §3.

| # | Check | Command / script idea | Expected | Fallback |
|---|---|---|---|---|
| 1 | Groq streaming + tool call (U-01, U-02) | ~10-line `openai.AsyncOpenAI` script against Groq with the `get_employee_context` tool and `stream=True` | Tool-call deltas arrive (id/name once, arguments in fragments), no 400; text deltas stream for a non-tool question | Swap `LLM_PROVIDER` by configuration; as a last resort run pass 1 non-streamed and stream pass 2 |
| 2 | `tool_choice="none"` accepted in pass 2 (U-05) | Same script, pass 2 with the tool result, same tools, `tool_choice="none"` | 200 and a text answer | Omit `tool_choice` but keep tools; strip tools only if the provider accepts tool messages without them |
| 3 | Does `max_tokens` bound deliberation tokens? (U-03) | gpt-oss with `reasoning_effort` low and `max_tokens=20` on a reasoning-heavy prompt | Stops with `finish_reason="length"` | Rely on the 8 s first-chunk timer and the 30 s turn timeout; keep 1500 |
| 4 | First-run embedding model download (RR-04) | `uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"` | Downloads ~130 MB once, then loads from cache | Document the network need; pre-warm the HF cache |
| 5 | OCR on the target OS (RR-03, U-10) | Render `strategic_plan.pdf` at 300 dpi with pypdfium2 and run `from rapidocr import RapidOCR` (rapidocr 3.9.2 + onnxruntime) | ~18 lines, bundled models, no system packages (as E01 on this machine) | Pin compatible onnxruntime/opencv wheels; document any OS caveat |
| 6 | Dependency resolution | `uv sync --python 3.12` on the target platform | Every pinned dependency installs (torch CPU, sentence-transformers, rapidocr, onnxruntime, qdrant-client, openai) | Adjust pins; record the change in the README |
| 7 | Qdrant + ingestion | `docker run -d --name qdrant -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant:v1.19.1`, then `uv run python -m scripts.ingest --docs-dir ./docs` | Collection with 42 points; startup checks pass | Fix before writing features |

**Measured on 2026-10-04, before the build (pre-build, D-78; raw output in `build/evidence/`):** uv 0.12.18, Docker 29.7.2 (daemon running) and Python 3.12 via uv are present; `qdrant/qdrant:v1.19.1` is pulled (digest `sha256:12364fe8…`, the same image as the local `latest`); every pinned library resolves together on Python 3.12.14 — fastapi 0.142.2, starlette 1.7.0, uvicorn 0.54.0 with websockets 17.2, pydantic 2.13.5, pydantic-settings 2.15.0, PyJWT 2.15.1, python-dotenv 1.2.4, openai 3.24.0, qdrant-client 1.19.1, sentence-transformers 6.1.0 with torch 2.14.1, pypdfium2 5.13.0, rapidocr 3.9.2, onnxruntime 1.30.0, httpx 0.28.1; bge-small loads with 384 dimensions and a 512-token window (first run including the download: 56.7 s); RapidOCR on the scan at 300 dpi returns 18 lines (minimum confidence 0.984, mean 0.993) and the 2.0× median-gap rule (median 14.1 px) gives 7 groups — the title plus 6 chunks, as E01/E02 recorded; decoding the six text PDFs' content streams shows each as a title plus exactly six numbered headings with nothing in between, and the three digit-start wrapped lines named in D-22 — so the 42-chunk expectation holds before any code exists. PyJWT 2.15.1 accepts a short secret but logs `InsecureKeyLengthWarning`. Open before T0: port 8000 is held by another container (the owner frees it); `miniragchatbot/.env` needs the owner's Groq key, after which checks 1–3 run as pre-flight P7.

## 3. Residual assumptions for README_SUBMISSION.md

Each is also in PRD §4 / RISKS-ASSUMPTIONS.md: exec users cannot read finance (consequence of the brief's formula plus its single hr exception); OCR only when the text layer is empty (`len(text.strip()) == 0`), done locally; one turn at a time per connection, extra messages queue; every message goes through retrieval (no intent classifier); retrieval uses the current question only; the tool's `user_id` must equal the JWT `sub`, otherwise a denial result goes to pass 2; pluggability = one OpenAI-compatible adapter switched by configuration; the provided `mint_tokens.py` and `test_client.html` are used as-is from `miniragchatbot/`, the project root (our assumption — the brief does not forbid editing them; D-76).

## 4. Accepted risks (known, not further mitigated)

| Risk | Accepted because | What we still do |
|---|---|---|
| RR-01 Groq free-tier model or limits change | Provider policy is outside our control; automatic failover would be over-engineering | Configuration swap via `LLM_PROVIDER`; clear 429 / configuration error frames; live smoke test before submission |
| RR-05 evaluator without Docker | Qdrant embedded mode blocks the event loop and filters in Python (rejected) | Exact `docker run` command; fail-fast startup message |
| RR-06 macOS system Python 3.9.6 | TaskGroup / asyncio.timeout need 3.11; no back-port | `requires-python >= 3.11`; `uv sync --python 3.12` in the README |
| RR-02 deliberation latency / token use | Hosted model behaviour | 8 s first-chunk timer, 30 s turn timeout, "cut short" / timeout error frames |
| RR-03 OCR threshold tuned to one scan | A general layout classifier is out of scope | Integrity test (42 / 6 chunks) catches drift |

## 5. Verdict

**GO**: start implementation, on these conditions:
1. Run the day-1 checklist (§2) before writing features. Checks 1, 4, 6 and 7 are blocking.
2. Follow the 7 vertical-slice commits in IMPLEMENTATION-PLAN.md, with tests shipped in the same commit; conversation memory is an optional commit 8.
3. Keep the default `uv run pytest` offline; anything needing the model, Qdrant or a key carries its marker.
4. Hold the coverage gate (≥ 80 % branch on `app/`, `uv run pytest -m "not live_llm"`) from commit 6, as in IMPLEMENTATION-PLAN — it needs Docker Qdrant and the embedding model, which commits 1–2 do not have; earlier commits run their own gates (corrected post-review).
5. Build inside `miniragchatbot/` (D-76). Submission is a push to the CodeSubmit `origin`, only on the owner's explicit go; whether `deliverables/` ships is an open owner decision (D-77).
6. Pre-build (D-78): run the build per [build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md) — pre-flight before the clock, time boxes and tripwires — with [build/TRACKER.md](build/TRACKER.md) updated at every step.
