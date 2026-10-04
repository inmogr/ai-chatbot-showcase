# Planning deliverables — index

Planning documents for the Mini RAG Chatbot take-home (FastAPI WebSocket RAG + RBAC at the Qdrant query layer + a parallel mock tool + a free-tier LLM). The plan only; no product code is included. The code is built inside `miniragchatbot/`, and every path and command in these documents is relative to it (DECISIONS D-76).

The planning sources are not in this git repository. They live in the workspace's `planning/` folder next to it: canonical decisions `../../planning/inputs/attach/DECISIONS-REGISTER.md`, evidence `../../planning/evidence/` (E01–E17), round-by-round knowledge `../../planning/knowledge/` (K01–K12). Every `inputs/…`, `knowledge/…` and `evidence/…` path cited in these documents is relative to that `planning/` folder.

Post-review corrections (2026-10-04) are applied in place; the list is in DECISIONS.md, "Corrected after the 2026-10-04 review". Pre-build corrections for the 2-hour run (D-78…D-85) are applied in place too; the list is in DECISIONS.md, "Corrected before the 2-hour build".

Reading order:
1. [PRD.md](PRD.md) — problem, users, scope, assumptions, functional requirements FR-01–FR-34, non-functional requirements NFR-01–NFR-15, risks, resolved and unverified items.
2. [ARCHITECTURE.md](ARCHITECTURE.md) — module tree, ports, composition, turn flow, error catalog, system prompt, runtime behaviour.
3. [DECISIONS.md](DECISIONS.md) — every decision with why / why not, including reversed and superseded ones.
4. [REQUIREMENTS-TRACEABILITY.md](REQUIREMENTS-TRACEABILITY.md) — each brief requirement to FR/NFR, test, marker and evidence.
5. [TEST-PLAN.md](TEST-PLAN.md) — test layout, markers, commands, key test designs, manual test_client.html checklist.
6. [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) — 7 vertical-slice commits (+ optional 8), gates, time estimate, cut order.
7. [README_SUBMISSION-OUTLINE.md](README_SUBMISSION-OUTLINE.md) — the submission README's sections with the exact numbers to cite.
8. [RISKS-ASSUMPTIONS.md](RISKS-ASSUMPTIONS.md) — risk register, assumptions, unverified claims and how each gets verified.
9. [SIGN-OFF.md](SIGN-OFF.md) — confidence per requirement, day-1 verification checklist, accepted risks, GO verdict.
10. [build/EXECUTION-PLAN.md](build/EXECUTION-PLAN.md) — the 2-hour run: pre-flight, time boxes, every step with its skill or agent, tripwires, the one-name-per-test inventory.
11. [build/TRACKER.md](build/TRACKER.md) — live build state: resume point, clock, step log, requirement status, deviations, review findings, incidents, evidence index.

How the plan was produced: 12 review rounds (rounds 1–4 and 11–12 on Gemini 3.1 Pro with Extended thinking, rounds 5–10 on Gemini 3.8 Flash with Extended thinking); every answer was challenged with the brief and with measured evidence before it entered the plan.
