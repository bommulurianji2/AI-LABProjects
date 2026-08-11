# Implementation Ledger

Living record of what's done, tested, deferred, and blocked. Update this every session — do not let it
go stale.

## Session 16 — 2026-08-11

Fixes a real gap found via manual browser smoke testing after the LLM rollout completed: with all 11
agents now real, a local end-to-end walkthrough was run through the actual frontend for the first time
this session, surfacing a governance hole that every prior test (unit, integration, and the many manual
API-level chain runs) had missed because they all either created a `User` row directly via the DB session
or, for the one HTTP-level test that didn't, happened to pass a string that was never checked.

### The gap

The review form's reviewer field has a placeholder of `reviewer@example.test`, implying an email, but the
value is passed straight through as `reviewer_id` — a foreign key to `users.id`. There was no `/users`
endpoint, no picker, and (this was the actual bug) no validation: SQLite doesn't enforce foreign keys by
default, so `submit_review` silently accepted any string and recorded it as a `Review.reviewer_id`, which
is supposed to be an auditable governance record, not free text. This would also have started throwing
raw `IntegrityError`s instead of a clear domain error the moment the database moves to Postgres (which
enforces FKs by default) — so it was a real blocker for the "real thing" test, not just a rough edge.

### Completed

- **`GET /users`** and **`POST /users`** (`app/api/routes.py`, schemas in `app/api/schemas.py`): `POST` is
  get-or-create by email (idempotent — 201 on genuine creation, 200 returning the existing row on a repeat
  email) since reviewers are picked from a short internal list here, not self-registered.
- **`OrchestratorService.submit_review`** now looks up the reviewer by ID and raises `OrchestrationError`
  (surfaced as HTTP 409) if no such `User` exists, checked before any state mutation so a bad reviewer_id
  has no side effects.
- Fixed two existing tests (`test_api_full_loop.py`, `test_multi_artefact_run_listing.py`) that were
  passing a bogus reviewer_id with no corresponding `User` row — they only ever passed because of the
  exact gap above.
- **Frontend**: replaced the free-text reviewer input with a `<select>` populated from `GET /users`, plus
  an inline "+ Add reviewer" form that calls `POST /users` and auto-selects the result. Persists the
  last-used reviewer per browser in `localStorage` (pure UX convenience for repeated manual testing, not
  an identity mechanism).

### Tests executed (all passing — 397 backend tests, 8 new)

- `test_users_api.py` (8 cases): create returns 201 and persists, default role, idempotent get-or-create
  by email, list ordering, submit_review rejects an unknown reviewer_id (both at the HTTP layer and
  directly against `OrchestratorService`), and the accepted path for both layers.
- Frontend: `npx tsc --noEmit` clean, `npm run lint` clean.

### Manual verification

Ran a full local smoke test through the real frontend (backend on :8000, frontend on :3000, both started
manually — no `.claude/launch.json` exists for this project yet, so the browser preview tool's
`preview_start({name})` path isn't wired up; used `preview_start({url})` against a manually-started `npm
run dev` instead): created a project, started an Analysis run, confirmed the generated Requirement
Specification is genuinely tailored to the prompt (not templated) via the actual download endpoint,
advanced through UX Design (both artefacts, including the interactive HTML prototype, rendering
correctly), then specifically exercised the new reviewer picker — selected an existing reviewer, added a
new one inline, confirmed it appeared and auto-selected, and completed the review to advance the phase.
Also confirmed via curl that a bogus `reviewer_id` is now correctly rejected with a 409 and a clear
message, and that a real one still succeeds.

### Deferred / next

- No `.claude/launch.json` for this project — future browser-tool sessions should add one (`npm run dev`
  in `frontend/`) so `preview_start({name})` works instead of manually backgrounding `npm run dev`.
- Local testing vs. a real deployment: still no Postgres, no Entra ID auth (reviewer identity is
  self-asserted, not authenticated — the fix above closes the *data-integrity* gap, not an *auth* gap),
  no Key Vault, no CI/CD, no M365/Graph adapters. All previously deferred and tracked, not blocking local
  functional testing.

## Session 15 — 2026-08-11

Completes the LLM rollout: the eleventh and final agent, Hypercare & Closure, is now `runtime: llm`.
Every specialist agent in PP-SDLC-Orchestrator now produces real, grounded, model-generated content —
the mock runtime remains only as the deterministic, network-free path used by the test suite.

### Completed

- Extracted `HypercareClosureMockAdapter`'s rendering into a shared `app/adapters/hypercare_closure_renderer.py`
  (single `render()` function, no stable-ID entities — same shape as Governance & Security and Deploy).
- **`HypercareClosureLlmAdapter`** (`llm_agent_adapter.py`): reads all eleven prior artefact types via
  `_format_multi_artefact_context`, in particular the IQ Document's pre-deployment verification (which
  already carries the Test Workbook's defect status forward from Deploy). Unlike Deploy, this agent does
  not re-gate on defects — Deploy already refused to proceed if any were open — its guardrail is narrower:
  never produce an empty closure statement. The adapter raises `ModelProviderError` if the model omits
  one, exactly the "never close silently without that check" failure mode the guardrail exists to prevent.
- **`03_Agent_Skills/hypercare_closure/manifest.yaml` now declares `runtime: llm`** — the eleventh and
  final agent. `SKILL.md` updated with the standard "Implementation note" pattern.
- Extended `FakeModelProvider`'s default response with Hypercare & Closure's schema keys.

### Tests executed (all passing — 389 backend tests, 6 new)

- `test_hypercare_closure_llm_adapter.py` (6 cases): real rendering from model content, upstream IQ
  Document context actually included in the prompt, graceful omission when no upstream text exists, an
  empty closure statement raises, a missing free-text field falls back gracefully, malformed JSON raises.

### Manual verification with the real OpenRouter key

Attempted a full ten-phase chain (Analysis → ... → Deploy → Hypercare & Closure) for a fictitious "Office
Supply Request Tracker" project; Deploy correctly blocked again on two real, legitimate defects found by
Test (a Dataverse naming-convention risk and a UX/data mismatch on a filter control) — the same guardrail
verified in session 14 holding again, on a different project. Since reaching Hypercare & Closure through
the full chain requires the real Test Agent to report zero defects (not something to force), verified
`HypercareClosureLlmAdapter` directly against the real provider instead, with a synthetic-but-realistic
IQ Document/Governance Document context describing a clean deployment. The generated closure report's
closure statement quoted the IQ Document's exact section and defect-free wording ("Section 3
Pre-Deployment Verification... zero open defects... all 5 test cases TC-001 through TC-005 passed"),
referenced the Governance Document's ownership section by name, and produced a coherent, non-templated
hypercare narrative (specific dates, a plausible minor issue, a documented resolution) — confirming
genuine grounding for the final agent in the rollout.

### Rollout complete

All 11 agents (Orchestrator's specialist roster: Analysis, UX Design, Technical Design, Data &
Integration, Governance & Security, Build, Validation/QA, Test, Deploy, Hypercare & Closure — the
Orchestrator itself is a domain service, not a manifest-registered agent) are now `runtime: llm`. The
`runtime: mock` adapters and their shared renderers remain in place — every real adapter still routes
through the same renderer module its mock counterpart uses — so the full backend test suite stays
deterministic and network-free, and any agent can be reverted to `runtime: mock` with a one-line manifest
edit if needed.

### Deferred / next

- No agents remain on `runtime: mock`. Next-session backlog candidates: Azure deployment, M365
  Graph/SharePoint/Power Platform adapters, Entra ID auth, Playwright E2E suite — all previously deferred
  and tracked, none blocking current functionality.

## Session 14 — 2026-08-11

Continues the LLM rollout to the ninth agent, Deploy — the first agent whose guardrail is a genuine hard
business rule ("must not deploy unapproved or failed components") rather than a content-quality
guideline, and the first to require a real fix in shared infrastructure before it could be implemented
correctly.

### Completed

- **Fixed `document_text.extract_text()` for `.xlsx` files** (`app/adapters/document_text.py`): previously
  any non-`.docx` file fell back to a raw text read, which for a binary zip format like `.xlsx` returns
  garbled bytes, not readable content. This was silently wrong from the moment the Test Agent started
  producing real `.xlsx` output in session 13, but nothing had needed to *read* that upstream text yet.
  Deploy's guardrail — check the Test Workbook's Defects sheet for open items — made it load-bearing.
  Added an openpyxl-based branch that dumps each sheet's non-empty cell values row by row, with 4 new
  unit tests (`test_document_text.py`) covering docx, xlsx-across-sheets, truncation, and the raw-read
  fallback for unknown extensions.
- Extracted `DeployMockAdapter`'s rendering into a shared `app/adapters/deploy_renderer.py` (single
  `render()` function, no stable-ID entities — same shape as Governance & Security).
- **`DeployLlmAdapter`** (`llm_agent_adapter.py`): reads all ten prior artefact types via
  `_format_multi_artefact_context`, in particular the Test Workbook's now-correctly-extracted Defects
  sheet. The model reports `defects_clear: true/false`; when false, the adapter raises a new
  `DeploymentBlockedError` (a `ModelProviderError` subclass) with the model's defect summary rather than
  rendering an IQ Document — the run fails with the blocking reason logged, exactly like any other
  adapter failure, but for a business reason rather than a malformed response.
- **`03_Agent_Skills/deploy/manifest.yaml` now declares `runtime: llm`** — the ninth real agent. `SKILL.md`
  updated to state the hard-block rule explicitly and documents `DeploymentBlockedError` in its
  "Implementation note".
- Extended `FakeModelProvider`'s default response with `defects_clear: true` (plus the deployment text
  fields) so the existing full-suite chain tests keep exercising the normal, non-blocked path.

### Tests executed (all passing — 383 backend tests, 11 new)

- `test_document_text.py` (4 cases): docx paragraph extraction, xlsx multi-sheet row extraction,
  max_chars truncation, raw-read fallback for unrecognized extensions.
- `test_deploy_llm_adapter.py` (7 cases): normal rendering when defects are clear, `DeploymentBlockedError`
  raised with the real defect summary when they aren't, the error is a `ModelProviderError` subclass,
  upstream Test Workbook text actually reaches the prompt, graceful omission with no upstream text, a
  missing defect summary falls back to a generic message, malformed JSON raises.

### Manual verification with the real OpenRouter key

Ran a full nine-phase chain (Analysis → ... → Test → Deploy) for a fictitious "Church Van Fleet
Scheduler" project. The real Test Agent run produced four open defects (a realistic outcome, same as
session 13's finding); Deploy correctly refused to proceed, returning an HTTP 409 whose message named
each open defect by ID (`DEF-001` through `DEF-004`) with its upstream traceability (`REQ-008`, `ADR-003`,
`ADR-005`, `DATA-001`, `DATA-004`) — confirming the hard-block guardrail actually fires against a real
model's real assessment of real upstream content, not just in the unit-test-injected case.

### Deferred / next

- One agent remaining on `runtime: mock`: Hypercare & Closure — the last one in the 11-agent rollout.

## Session 13 — 2026-08-11

Continues the LLM rollout to the eighth agent, Test — the first Excel artefact (rather than Word) to get
a real LLM adapter, and the first agent where a "Failed" outcome is a legitimate, expected result rather
than something to avoid.

### Completed

- Extracted `TestAgentMockAdapter`'s rendering into a shared `app/adapters/test_renderer.py`, exercising
  the openpyxl path this time instead of python-docx — same principle, different library. Removed the
  now-unused `openpyxl.load_workbook` import from `mock_agent_adapter.py`.
- **`TestAgentLlmAdapter`** (`llm_agent_adapter.py`): reads all nine prior artefact types via
  `_format_multi_artefact_context` so test cases trace to real upstream IDs. Per this agent's guardrail
  ("a failing test against a correct requirement is a defect, not a reason to loosen the requirement"),
  `status: "Failed"` is accepted as a normal outcome — the adapter doesn't force everything to pass — and
  writes a corresponding row to the Defects sheet for each failure.
- **`03_Agent_Skills/test/manifest.yaml` now declares `runtime: llm`** — the eighth real agent. `SKILL.md`
  updated with the same grounding guardrail and multi-artefact "Implementation note".
- Extended `FakeModelProvider`'s default response with Test's schema keys (`test_cases`, `defects`).

### Bugs found via testing and fixed

1. **Pytest collection warning**: `TestAgentMockAdapter`/`TestAgentLlmAdapter` are correctly-named
   classes (Test Agent + runtime + Adapter, same convention as every other agent), but their names
   happen to start with "Test", matching pytest's default `Test*` class-discovery pattern. Once a test
   file imported `TestAgentLlmAdapter` by name, pytest tried to collect it as a test class and warned
   about its `__init__` constructor. Fixed by setting `__test__ = False` on both classes — the standard
   pytest opt-out — rather than renaming the agent to avoid a naming collision with a test framework
   convention that has nothing to do with the domain.
2. **Stale seeded-count assertion**: `test_test_agent_chain.py` hardcoded `len(data_rows) == 3` (the
   mock's fixed case count) and asserted all rows "Passed" — both mock-specific. Updated to check
   structure instead (at least one case, every case has a `Related Entity`), matching how
   `test_build_chain.py` and `test_validation_qa_chain.py` were already updated in sessions 11–12 when
   their agents switched off `runtime: mock`.

### Tests executed (all passing — 372 backend tests, 7 new)

- `test_test_agent_llm_adapter.py` (7 cases): real workbook rendering with a mix of Passed/Failed status
  and a matching Defects row, multiple upstream artefacts actually present in the prompt, graceful
  omission when no upstream text exists, a case with no `related_entity` is dropped, missing-cases
  raises, ID-prefix-stripping regression on `related_entity`, malformed JSON raises.

### Manual verification with the real OpenRouter key

Ran a full eight-phase chain (Analysis → UX Design → Technical Design → Data & Integration → Governance
& Security → Build → Validation/QA → Test) for a fictitious "Community Pool Lane Booking" project. The
generated Test Workbook produced 8 test cases spanning OQ/SIT/PQ/UAT, each tracing to a real upstream ID
(`DATA-001`, `REQ-005`, `SCR-001`, `SCR-003`, `REQ-004`, `REQ-007`, `DATA-005`); 4 of the 8 legitimately
failed, and each failure produced a linked Defects-sheet row whose description itself cited the specific
Validation Report finding and upstream gap that caused it — confirming the "failure is a valid outcome,
not something to suppress" guardrail actually holds under a real model.

### Deferred / next

- Remaining agents still on `runtime: mock`: Deploy, Hypercare & Closure.

## Session 12 — 2026-08-11

Continues the LLM rollout to the seventh agent, Validation/QA — reuses the multi-artefact context
pattern introduced for Build in session 11, extended one step further (also reading Build's own two
output artefacts) and adding a stricter guardrail: every finding needs a named remediation owner, not
just an upstream reference.

### Completed

- Extracted `ValidationQaMockAdapter`'s rendering into a shared `app/adapters/validation_qa_renderer.py`
  (single `render()` function — this agent produces one artefact with no stable-ID entities of its own,
  same shape as Governance & Security).
- **`ValidationQaLlmAdapter`** (`llm_agent_adapter.py`): reads all eight prior artefact types (everything
  through Build's Build Review Report and Final Code Review Report) via `_format_multi_artefact_context`.
  Each finding requires both a description and a `remediation_owner`; findings missing an owner are
  dropped rather than rendered with a blank, and if *no* finding survives that filter the adapter raises
  `ModelProviderError` — matches the guardrail that this agent never fixes content directly, so a finding
  with nowhere to route is not useful output.
- **`03_Agent_Skills/validation_qa/manifest.yaml` now declares `runtime: llm`** — the seventh real agent.
  `SKILL.md` updated with the same grounding guardrail and multi-artefact "Implementation note".
- Extended `FakeModelProvider`'s shared `findings` fixture (used by both Build and Validation/QA) with a
  `remediation_owner` field — harmless extra key for Build's schema, required for Validation/QA's.

### Tests executed (all passing — 365 backend tests, 7 new)

- `test_validation_qa_llm_adapter.py` (7 cases): real rendering from model content, multiple upstream
  artefacts actually present in the prompt together, graceful omission when no upstream text exists,
  missing-findings raises, a finding without a remediation owner is silently dropped while others
  survive, *all* findings lacking an owner raises, malformed JSON raises.

### Manual verification with the real OpenRouter key

Ran a full seven-phase chain (Analysis → UX Design → Technical Design → Data & Integration → Governance
& Security → Build → Validation/QA) for a fictitious "Neighborhood Tool Library" project. The generated
Validation Report's five findings each cited real IDs spanning nearly every prior phase in the same run
(`REQ-003`, `ADR-003`, `SCR-001`, `DEF-003`, `ADR-002`) with specific, plausible traceability gaps (e.g.
an accessibility claim in the UX spec with no corresponding schema field to store the data) and named a
concrete remediation owner for each — confirms the pattern holds at eight upstream artefacts deep.

### Deferred / next

- Remaining agents still on `runtime: mock`: Test, Deploy, Hypercare & Closure.

## Session 11 — 2026-08-11

Continues the LLM rollout to the sixth agent, Build — the first agent whose guardrail explicitly
requires citing entities from *any* upstream phase (e.g. `SCR-002`, `ADR-001`), not just its formal
manifest input (the Governance Document), so this is the first real generalization of the
upstream-context pattern beyond "read my one immediate predecessor."

### Completed

- Extracted `BuildMockAdapter`'s rendering into a shared `app/adapters/build_renderer.py`
  (`render_build_review`/`render_final_code_review`), same two-artefact pattern as Technical Design and
  UX Design.
- Added `_format_multi_artefact_context()` to `llm_agent_adapter.py` — a small shared helper (plus an
  `_ARTEFACT_TYPE_LABELS` lookup covering every artefact type in the system so far) that formats
  whichever upstream artefacts are actually present into labeled sections, in a fixed reading order. This
  is now the pattern for any agent whose prompt needs more than one upstream artefact — earlier agents
  used a single `upstream_artefacts_text.get("...")` call because they only ever had one immediate
  predecessor; Build is the first to need several at once.
- **`BuildLlmAdapter`** (`llm_agent_adapter.py`): reads all six prior artefact types (Requirement
  Specification, UX Design Specification, Solution Approach, Architecture Handbook, Data Design
  Document, Governance Document) via the new helper, so findings can cite whichever upstream ID is
  actually relevant. Requires at least one finding, raising `ModelProviderError` otherwise; a finding
  with no `reference` gracefully falls back to its description alone rather than failing.
- **`03_Agent_Skills/build/manifest.yaml` now declares `runtime: llm`** — the sixth real agent. `SKILL.md`
  updated with the same grounding guardrail and an "Implementation note" explicitly calling out that this
  agent reads more than its formal manifest input.
- Extended `FakeModelProvider`'s default response with Build's schema keys (`implementation_assets`,
  `configuration_summary`, `findings`).

### Tests executed (all passing — 358 backend tests, 6 new)

- `test_build_llm_adapter.py` (6 cases): real rendering of both artefacts from model content, multiple
  upstream artefacts (UX Design + Technical Design + Governance) all actually present in the prompt
  together, graceful omission when no upstream text exists, missing-findings raises, a reference-less
  finding falls back to description-only, malformed JSON raises.

### Manual verification with the real OpenRouter key

Ran a full six-phase chain (Analysis → UX Design → Technical Design → Data & Integration → Governance &
Security → Build) for a fictitious "Library Room Reservation" project. The generated Build Review Report
findings each cited a real upstream ID from a *different* phase in the same run — `ADR-003` (Technical
Design), `SCR-003`/`SCR-002`/`SCR-005` (UX Design), `REQ-006` (Analysis), and `DATA-004` (Data &
Integration) — with concrete, plausible Power Platform delegation/concurrency issues tied to each,
confirming the multi-artefact context genuinely reaches the model and gets used, not just included.

### Deferred / next

- Remaining agents still on `runtime: mock`: Validation/QA, Test, Deploy, Hypercare & Closure.

## Session 10 — 2026-08-11

Continues the LLM rollout to the fifth agent, Governance & Security — the first agent whose output is
almost entirely free text plus two short lists (DLP, licensing) rather than a dominant list of
stable-ID entities, so it's the first real test of the pattern on a lighter-structure artefact.

### Completed

- Extracted `GovernanceSecurityMockAdapter`'s rendering into a shared `app/adapters/governance_security_renderer.py`
  (single `render()` function taking every section as a plain text/list parameter — no entity IDs at all
  for this agent, matching the template's shape).
- **`GovernanceSecurityLlmAdapter`** (`llm_agent_adapter.py`): reads
  `upstream_artefacts_text["data_design_document"]` so the DLP classification and connector governance
  sections cover the actual connectors Data & Integration chose, not a generic list. Only the two
  structured list fields (`dlp`, `licensing`) are required and raise `ModelProviderError` if empty; the
  seven free-text fields each get a graceful per-field fallback string if the model omits one, since
  there's no correctness invariant (like a missing entity) that would make a partial free-text response
  actually wrong.
- **`03_Agent_Skills/governance_security/manifest.yaml` now declares `runtime: llm`** — the fifth real
  agent. `SKILL.md` updated with the same grounding guardrail and "Implementation note" pattern.
- Extended `FakeModelProvider`'s default response with Governance & Security's schema keys (the seven
  free-text fields plus `dlp` and `licensing` lists).

### Process note (not a code bug, a repeat of session 9's environment issue)

Manual verification again hit stale local server processes on port 8010 — this time two full python.exe
processes existed simultaneously right after a single `nohup ... &` start, and killing the wrong one
took the good one down with it. Fixed by using `netstat -ano | grep ":8010" | grep LISTENING` to find the
PID that Windows actually has the port bound to, which is authoritative regardless of how many
python.exe processes exist or which one wrote the "Started server process" log line. This is now the
standard verification step: check the port owner via netstat, not the log or the shell job ID, before
trusting a manual test run.

### Tests executed (all passing — 352 backend tests, 7 new)

- `test_governance_security_llm_adapter.py` (7 cases): real rendering from model content, upstream Data
  Design Document context actually included in the prompt, graceful omission when no upstream text
  exists, missing `dlp`/missing `licensing` each raise, a missing free-text field (`compliance`) falls
  back to a placeholder string rather than raising, malformed JSON raises.

### Manual verification with the real OpenRouter key

Ran a full five-phase chain (Analysis → UX Design → Technical Design → Data & Integration → Governance &
Security) for a fictitious "Community Garden Plot Manager" project. The generated Governance Document
named the exact three connectors from that run's real Data Design Document (Dataverse, Power BI, Office
365 Outlook) with individual DLP classifications for each, and cross-referenced real upstream IDs
(`DATA-003`, `SCR-004`) — confirms grounding survives four hops.

### Deferred / next

- Remaining agents still on `runtime: mock`: Build, Validation/QA, Test, Deploy, Hypercare & Closure.

## Session 9 — 2026-08-11

Continues the LLM rollout to the fourth agent, Data & Integration, and catches a real process-hygiene
bug during manual verification (not a code bug — a stale local server left over from the previous
session's testing, listening on the same port and silently serving out-of-date behavior).

### Completed

- Extracted `DataIntegrationMockAdapter`'s rendering into a shared `app/adapters/data_integration_renderer.py`
  (single `render()` function — this agent produces one artefact, unlike Technical Design's two).
- **`DataIntegrationLlmAdapter`** (`llm_agent_adapter.py`): reads `upstream_artefacts_text["solution_approach"]`
  so the Dataverse schema, relationships, external-source mapping, and connector design are grounded in
  Technical Design's actual architecture decisions. Requires at least one entity, raising
  `ModelProviderError` otherwise.
- **`03_Agent_Skills/data_integration/manifest.yaml` now declares `runtime: llm`** — the fourth real
  agent. `SKILL.md` updated with the same grounding guardrail and "Implementation note" pattern.
- Extended `FakeModelProvider`'s default response with Data & Integration's schema keys (`entities`,
  `relationships`, `external_sources`, `connectors`, `data_migration`, `reporting_model`).
- Wrote a reusable manual-verification harness (`chain_runner.py`, kept in the session scratchpad, not
  the repo — it's a dev tool, not application code) that drives a project through N phases against a
  real running backend and prints the final phase's artefacts, so each subsequent agent's real-key
  verification doesn't need a bespoke one-off script.

### Bug found during manual verification (process hygiene, not application code)

The first real-key verification run produced output that was suspiciously identical to the *mock*
adapter's hardcoded pool content ("Request"/"RequestLine"/"Approval"/"Attachment" entities, the exact
string "No legacy data migration in scope for this mock run.") even though the manifest correctly said
`runtime: llm` on disk. Root cause: the previous session's Technical Design verification server was still
running on port 8010 — `pkill -f "uvicorn app.main:app"` does not reliably kill Windows python.exe
processes launched from Git Bash, so it silently no-op'd. The *new* server process failed to bind
(`WinError 10048`, port already in use) and exited, but its error was easy to miss since it was
backgrounded — so requests kept hitting the old, stale-registry process the whole time. Fixed by finding
the actual PID via `Get-CimInstance Win32_Process` and killing it explicitly with
`Stop-Process -Id <pid> -Force`, then re-verifying against a genuinely fresh process. Going forward,
manual verification confirms the *current* server's PID before trusting its output, rather than trusting
that a `pkill`/background-start sequence worked.

### Tests executed (all passing — 345 backend tests, 6 new)

- `test_data_integration_llm_adapter.py` (6 cases): real rendering from model content, upstream Solution
  Approach context actually included in the prompt, graceful omission when no upstream text exists,
  ID-prefix-stripping regression, missing-entities raises, malformed JSON raises.

### Manual verification with the real OpenRouter key (after fixing the stale-server issue above)

Ran a full four-phase chain (Analysis → UX Design → Technical Design → Data & Integration) for a
fictitious "Volunteer Shift Scheduler" project. The generated Data Design Document named
domain-specific entities (`Shift`, `Volunteer`, `ShiftRegistration`, `Administrator`) and explicitly
cross-referenced real upstream IDs from the earlier phases in this same run (e.g. "per SCR-001", "per
ADR-003", "per ADR-004") — confirms grounding survives three hops, not just one.

### Deferred / next

- Remaining agents still on `runtime: mock`: Governance & Security, Build, Validation/QA, Test, Deploy,
  Hypercare & Closure.

## Session 8 — 2026-08-11

Continues the LLM rollout to the third agent, Technical Design — the first agent after UX Design, so it
proves the upstream-context pattern generalizes past a single hop (Analysis → UX Design → Technical
Design, each grounded in the one immediately before it).

### Completed

- Extracted `TechnicalDesignMockAdapter`'s rendering into a shared `app/adapters/technical_design_renderer.py`
  (`render_solution_approach`/`render_architecture_handbook`), same pattern as the Analysis and UX Design
  renderers — mock and LLM adapters differ only in where option/decision/risk content comes from.
- **`TechnicalDesignLlmAdapter`** (`llm_agent_adapter.py`): reads
  `upstream_artefacts_text["ux_design_specification"]` and includes it as real context in the prompt, so
  architecture options, decisions, risks, and the logical architecture are grounded in what UX Design
  actually decided (screens, navigation, responsive behavior) rather than the original one-line task
  request. Requires at least 2 options (first is treated as the recommendation) and at least 1 decision,
  raising `ModelProviderError` otherwise. Produces both artefacts (Solution Approach + Architecture
  Handbook docx) from one model call.
- **`03_Agent_Skills/technical_design/manifest.yaml` now declares `runtime: llm`** — the third real agent.
  `SKILL.md` updated the same way as Analysis/UX Design's: added grounding + Power-Platform-specificity
  guardrails, replaced the mock-only note with an "Implementation note" describing both runtimes.
- Extended `FakeModelProvider`'s default response with Technical Design's schema keys (`options`,
  `architecture_decisions`, `risks`, `limitations`, `dependencies`, `logical_architecture`,
  `integration_overview`, `infrastructure_overview`) — same superset pattern as session 7, no per-agent
  detection logic added to the fixture.

### Tests executed (all passing — 339 backend tests, 8 new)

- `test_technical_design_llm_adapter.py` (8 cases): real rendering of both artefacts from model content,
  upstream UX Design context actually included in the prompt, graceful omission when no upstream text
  exists, ID-prefix-stripping regression (`"ADR-1: ..."` → `"ADR-001: ..."`, not doubled), missing
  `options`/`architecture_decisions` each raise, a single option (no real comparison) raises, malformed
  JSON raises.

### Manual verification with the real OpenRouter key

Ran a full three-phase chain through a temporary local server (Analysis → approve → UX Design → approve
→ Technical Design) for a fictitious "Facilities Booking Portal" project never seen in any prompt or
pool. The generated Solution Approach and Architecture Handbook explicitly referenced details only
present in the real UX Design output for that run (e.g. "the mobile hamburger menu and stacked filter
layout described in the UX specification", a PCF-control workaround for the wireframe's time slot
picker) — confirms the grounding is real, not templated, and that context survives two hops.

### Deferred / next

- Remaining agents still on `runtime: mock`: Data & Integration, Governance & Security, Build,
  Validation/QA, Test, Deploy, Hypercare & Closure — same now-proven pattern applies to each.

## Session 7 — 2026-08-11

Continues session 6's LLM rollout to the second agent, UX Design. This session also fixes a real
architecture gap found while doing it: no agent's output ever actually read the *previous* phase's
approved content — Analysis worked, but every downstream agent would have kept re-deriving from the raw
original task request forever, never actually building on what the upstream agent decided.

### Completed

- **Upstream artefact content plumbing** — the real fix, benefiting every future LLM adapter, not just
  UX Design: `AgentRunRequest` gained `upstream_artefacts_text: dict[str, str]` (artefact_type → extracted
  text); `OrchestratorService._gather_upstream_artefacts_text()` queries every BASELINE artefact version
  for the project and extracts its text via a new `app/adapters/document_text.py::extract_text()` helper
  (docx paragraphs for now; falls back to raw read for other formats), skipping unreadable files with a
  warning rather than failing the run. Populated automatically in `start_run` — no adapter changes needed
  to receive it, they just opt in by reading the dict key they care about.
- **`UxDesignLlmAdapter`** (`llm_agent_adapter.py`): reads `upstream_artefacts_text["requirement_specification"]`
  and includes it as real context in the prompt, so personas/journeys/screens are grounded in what
  Analysis actually decided. Produces both UX artefacts (spec docx + prototype html) from one model call.
- Extracted `UxDesignMockAdapter`'s rendering into a shared `app/adapters/ux_design_renderer.py`
  (`render_spec`/`render_prototype`), mirroring the pattern already used for Analysis — mock and LLM
  adapters differ only in content source, never in template-filling code.
- **`03_Agent_Skills/ux_design/manifest.yaml` now declares `runtime: llm`** — the second real agent.
  `SKILL.md` updated the same way as Analysis's (accurate real system prompt, outdated mock-runtime
  reference replaced with an "Implementation note").
- Generalized the ID-prefix-stripping regex from session 6 (`_LEADING_ID_PREFIX_RE`): it only matched
  `REQ-`-style prefixes, which would have needed revisiting for every new agent's own ID scheme (`SCR-`,
  `ADR-`, `DATA-`, `DEF-`, `TC-`, ...). Now matches any 2-6 letter prefix + digits, generically, once.
- Extended `FakeModelProvider`'s default canned response to be a superset covering every LLM adapter's
  schema so far (Analysis's `scope`/`functional_requirements`/`assumptions` *and* UX Design's
  `personas`/`journeys`/`screens`/...) — each adapter reads only the keys it needs. This is the pattern
  for every future agent added to the rollout: extend the one shared default, don't add per-agent
  detection logic to the fake.

### Bugs found via testing (unit tests this time, not just manual) and fixed

1. **ID-prefix regex was REQ-specific.** The very first UX Design unit test
   (`test_strips_model_supplied_screen_id_prefix`) failed with `"SCR-001: SCR-1: Dashboard"` — doubled,
   exactly the session-6 bug, just with a prefix the old regex didn't know about. Generalized the regex
   (see above) instead of adding a second SCR-specific one, since every future agent will have its own
   prefix.
2. **Global fake-provider stub broke every chain test past UX Design** the moment the manifest switched
   to `runtime: llm` — the stub always returned Analysis-shaped JSON, and `UxDesignLlmAdapter` correctly
   rejected it for missing `personas`/`journeys`/`screens`. Fixed by making the fake response a superset
   rather than teaching the fixture which agent is asking.

### Tests executed (all passing — 331 backend tests, 10 new)

- `test_ux_design_llm_adapter.py` (8 cases: real rendering, upstream-context inclusion, graceful
  omission when no upstream text exists yet, prefix-stripping regression, 3 missing-required-field cases,
  malformed JSON).
- `test_upstream_artefact_context.py` (2 cases): proves a real chain (Analysis approved → UX Design
  started) actually receives the approved Requirement Specification's extracted text — checks for
  `"REQ-001"` and the real project name inside it, not just that the dict is non-empty; and proves the
  first phase (Analysis) correctly receives an empty dict since nothing is upstream of it yet.
- Full suite run three times at key points (before the manifest switch: 323 passed; immediately after:
  caught the fake-provider schema mismatch; after the fix: 331 passed) — the same discipline as session 6.
- **Manual, with the real OpenRouter key**: a full two-phase real chain (pet adoption marketplace) —
  Analysis approved, then UX Design run and inspected. Personas were concrete and specific ("Sarah Chen -
  Shelter Manager", "Marcus Johnson - First-time adopter"), and all 6 screens and both journeys
  explicitly referenced details only present in the approved Requirement Specification (meet-and-greet
  scheduling, health records, shelter dashboard) — direct proof the upstream-context plumbing works, not
  just that two independent LLM calls each produced plausible output.

### Assumptions

- `document_text.extract_text()` only really handles `.docx` properly (paragraph text via python-docx);
  everything else falls back to a raw text read. Fine for now since Analysis's only output (docx) is the
  only thing anything reads upstream of yet — will need real HTML/XLSX-aware extraction once an agent
  downstream of UX Design's prototype or Test's workbook needs to read *those* as upstream context.
- Upstream context is truncated to 8000 characters per artefact (`extract_text(..., max_chars=8000)`) —
  arbitrary but reasonable given typical mock-scale documents; untested against a genuinely long
  real-world requirement specification that might exceed it.

### Repo / branch state

Work done on `feature/ux-design-llm-adapter`, branched from `main` after session 6's PR (#12) merged.
Not yet pushed or PR'd.

### Remaining backlog (updated)

Analysis and UX Design run `runtime: llm`; Technical Design, Data & Integration, Governance & Security,
Build, Validation/QA, Test, Deploy, Hypercare & Closure still run `runtime: mock`. The pattern is now
proven twice (including the harder multi-artefact + upstream-context case) — extending to Technical
Design next would exercise reading UX Design's *two* artefacts (spec + prototype) as upstream context,
the next incremental piece of complexity.

## Session 6 — 2026-08-05

The user flagged that every agent's output was "just basic templates, nothing in them" — correct: every
agent runs `runtime: mock`, deterministic canned-pool text, never real generation from actual input. This
session wires a **real** LLM behind the Analysis agent (the user's own OpenRouter API key), proving the
mock→llm swap point designed back in session 1 actually works, before extending it to the other 10.

### Completed

- **Model provider abstraction** (`backend/app/adapters/model_providers/`): a one-method `ModelProvider`
  Protocol, a real `OpenRouterProvider` (OpenAI-compatible REST API via `httpx`, sync to match the rest
  of the codebase), and a `factory.get_model_provider()` that resolves the configured provider fresh from
  settings on every call — reads `PPSDLC_OPENROUTER_API_KEY`/`_MODEL`/`_BASE_URL` from `backend/.env`.
- **`AnalysisLlmAdapter`** (`backend/app/adapters/llm_agent_adapter.py`): sends `SKILL.md` as the system
  prompt (this is literally what it was written for) and the task request + a JSON-shape instruction as
  the user prompt, parses the response (tolerating markdown-fenced JSON), and renders the same
  `requirement_specification.docx` template the mock adapter uses — via a newly-extracted shared
  `requirement_specification_renderer.render()` so the two runtimes don't duplicate template-filling code.
- **`03_Agent_Skills/analysis/manifest.yaml` now declares `runtime: llm`** — the Analysis agent is for
  real, not mocked, in the actual running app. `SKILL.md` was cleaned up to be an accurate real system
  prompt (its old text referencing "this agent's runtime: mock" was no longer true and has been replaced
  with guardrails a model can actually follow, plus an "Implementation note" documenting both runtimes).
- **Test isolation without touching ~8 existing chain test files**: an autouse `stub_model_provider`
  fixture (`tests/conftest.py`) monkeypatches `model_provider_factory.get_model_provider` to return a
  deterministic `FakeModelProvider` (`tests/fixtures/fake_model_provider.py`) for every test. Every
  existing chain test (which all start with the Analysis phase) keeps passing unmodified, with zero
  network calls and zero cost — verified by running the full suite both before and after the manifest
  switch.
- Refactored `AnalysisMockAdapter` to use the same shared `requirement_specification_renderer` and a new
  `app/adapters/common.py::version_label()` (the mock's own `_version_label` is now an alias to it) — the
  mock stays available and tested, just no longer duplicates rendering logic with the new LLM adapter.
- Moved `.env.example` from the repo root to `backend/.env.example` — a real session-1 bug: `config.py`
  reads `.env` relative to the process's working directory, which is always `backend/` (every script
  `Push-Location`s there first), so the root-level file was never actually the one `Settings` would read.
  Fixed the documented paths inside it to match (relative to `backend/`, not repo root) and added the new
  OpenRouter variables.

### Bugs found via real manual testing (not caught by any unit test) and fixed

1. **Monkeypatch targeted the wrong reference.** `llm_agent_adapter.py` originally did
   `from ...factory import get_model_provider`, binding a local copy at import time; patching
   `factory.get_model_provider` afterward didn't affect that already-bound name. Every chain test that
   reached the Analysis phase failed with a real `ModelProviderError` the first time the manifest was
   switched. Fixed by importing the factory module and calling `model_provider_factory.get_model_provider()`
   — the standard fix for this exact class of mocking mistake.
2. **Doubled requirement ID prefixes with a real model.** First live OpenRouter test produced
   `"REQ-001: REQ-001: The system shall..."` — the model prepended its own `"REQ-001:"` despite the
   prompt not yet forbidding it, and the system's own ID assignment stacked on top. Fixed two ways:
   tightened the prompt to explicitly forbid model-supplied numbering, and added a defensive
   `_strip_leading_id_prefix` regex (handles `"REQ-001:"`, `"REQ-1:"`, `"REQ001:"`, `"1."`, `"1)"`) so a
   future model that ignores the instruction still doesn't produce doubled IDs. Covered by 5 parametrized
   regression cases.
3. **Frontend showed a misleading "Start a run" form on an in-progress phase.** Discovered by starting a
   run via `curl` (a separate session from the browser) then opening that project in the browser — since
   run/artefact state only lives in React state (no "list runs" endpoint yet), the workspace page had no
   way to know a run was already awaiting review, and `canStartRun` didn't check `project.phase_status`
   at all — it would have let the user submit a doomed request the backend would reject with 409. Fixed
   `canStartRun` to also require `phase_status` be `pending`/`rework`, and added an honest in-UI message
   for the "awaiting review but no local run state" case instead of silently showing the wrong form.

### Tests executed (all passing — 321 backend tests, 15 new)

- `test_llm_agent_adapter.py` (11 cases, including 5 parametrized ID-prefix regressions),
  `test_openrouter_provider.py` (4 cases, all network calls mocked via `monkeypatch.setattr(httpx, "post", ...)`).
- Full suite run three times at key points: before the manifest switch (316 passed), immediately after
  (caught the monkeypatch bug, 1 file changed, re-ran clean), and after the prefix fix (321 passed) — each
  confirming zero real network calls happen during `pytest`.
- **Manual, with the user's real OpenRouter key**: three different real scenarios end-to-end (vendor
  invoice approval, contractor onboarding, warranty claims) — two via raw API calls, one by literally
  driving the browser UI (create project → start run → wait for the real model → download and open the
  resulting `.docx`). Every one produced genuinely tailored requirements, scope, and assumptions specific
  to that scenario — not pool-selected boilerplate. This is the first artefact in the whole project
  generated by an actual model rather than canned text.

### Assumptions

- OpenRouter, not Azure OpenAI, is the active provider — a deviation from the original spec's Azure-first
  target, chosen because it's what the user had a key for right now. The `ModelProvider` Protocol is the
  seam that makes swapping to Azure OpenAI/Foundry later a new provider class, not a rewrite.
- Default model is `anthropic/claude-sonnet-4.5` via `PPSDLC_OPENROUTER_MODEL` — easily overridden per the
  user's cost/quality preference; not verified against every possible OpenRouter model, only the account's
  default routing at test time.
- No retry/backoff on transient OpenRouter failures (rate limits, timeouts) — a failure surfaces as a
  clean `ModelProviderError` → run marked `FAILED`, same as any other adapter exception, but the user has
  to manually retry by starting a new run. Acceptable for now, worth revisiting before real usage at scale.

### Repo / branch state

Work done on `feature/analysis-llm-adapter`, branched from `main` after session 5's frontend-shell PR
(#11) merged. Not yet pushed or PR'd.

### Remaining backlog (updated)

The other 10 agents still run `runtime: mock`. Extending `runtime: llm` to each is now a known, proven
pattern (provider abstraction + adapter + manifest edit + no test-file changes needed) rather than new
architecture — the next natural increment. Everything else in the session-1 "Deferred to later sessions"
list (M365/Azure adapters, Entra ID auth, remaining data-model entities, Playwright/security/resilience
suites, Azure IaC) is still untouched.

## Session 5 — 2026-07-22

### Completed

- **Frontend shell** (`frontend/`): Next.js 16 + React 19 + TypeScript, App Router, plain client-side
  data fetching against the FastAPI backend (no Server Components data-fetching layer — deliberate
  choice, see Assumptions). Two pages:
  - `/` — project list + create form.
  - `/projects/[id]` — workspace: current phase/status, start-run action, every artefact a run
    produced (each with its own download link), and the review form (approve / approve with comments /
    rework / reject, with comments).
  - `lib/api.ts` + `lib/types.ts` — a single typed API client, hand-kept in sync with
    `backend/app/api/schemas.py` (no shared codegen yet).
  - Removed the auto-generated placeholder assets/CSS module and the redundant nested
    `frontend/.gitignore` (see Bugs below).
- **Backend additions** needed to actually support the shell (not scope creep — the UI cannot function
  without these): `GET /projects` (list), `GET /artefact-versions/{id}/download` (streams the real file
  with correct content-type), and `GET /runs/{run_id}/artefact-versions` (list — see bug below).
- Added a proper `Artefact` ↔ `ArtefactVersion` SQLAlchemy relationship and an `artefact_type` property
  on `ArtefactVersion`, exposed via `ArtefactVersionResponse.artefact_type`. No migration needed — no new
  column, just an ORM relationship over data that already existed.
- Test infrastructure cleanup: replaced an `importlib.reload(app.main)`-based HTTP test isolation hack
  with a plain `api_client` pytest fixture (see `tests/conftest.py`) — the reload was solving a problem
  that didn't exist, since `lifespan()` already reads `get_settings()` fresh on every `TestClient` entry.

### Bugs found via actual browser testing (not just unit tests) and fixed

Manually driving the UI in a browser against the real backend — not just running the test suite —
surfaced five real defects (four in-session, plus a session-1 gitignore bug this work exposed), all now
fixed and covered:

1. **Multi-artefact runs silently lost data.** The original `GET /runs/{run_id}/artefact-version`
   (singular) returned only the most recent version. For the UX Design Agent (2 artefacts/run), the
   frontend could only ever see one of them — the other was invisible and undownloadable. Fixed by
   replacing it with `GET /runs/{run_id}/artefact-versions` (plural, returns all). Regression test:
   `test_multi_artefact_run_listing.py`.
2. **No way to tell artefacts apart.** Even fixing (1), `ArtefactVersionResponse` had no `artefact_type`
   field — two artefacts from one run would both render as indistinguishable "v0.1 (Draft)" rows. Fixed
   via the new model relationship/property above.
3. **Stale phase/artefact state after actions.** `handleStartRun` and `handleSubmitReview` updated `run`
   but not `project`/`artefactVersions`, so the UI kept showing the phase as "Pending" after a run
   actually moved it to "Awaiting Review", and kept showing "Draft" after approval had actually promoted
   the artefact to "Baseline". Fixed by re-fetching project/artefact state after both actions.
4. **`.gitignore` real bug**: the frontend-scoped rules added in session 1 used `frontend/.next/` etc,
   but the frontend actually lives at `PP-SDLC-Orchestrator/frontend/` — those patterns never matched
   anything and were silently dead. The only thing actually excluding `node_modules`/`.next` was
   create-next-app's own nested `frontend/.gitignore`, which also blanket-excluded `.env.example`
   (defeating the documented-defaults convention used everywhere else in this repo). Fixed by deleting
   the nested file and correcting the root `.gitignore` paths — one source of truth, verified with
   `git check-ignore` against every case (real generated content ignored, `.env.example` and
   `03_Agent_Skills/build/` correctly not ignored).
5. **`react-hooks/set-state-in-effect` lint errors** on both pages' mount-time data fetches — a real
   unmount/race-condition risk (calling `setState` after the component unmounts or `projectId` changes
   before the fetch resolves), not a style nit. Fixed using React's own documented cancellation-guard
   pattern (an `ignore` flag set in the effect's cleanup function), per
   https://react.dev/learn/synchronizing-with-effects#fetching-data.

### Tests executed (all passing — 306 backend tests, 3 new; frontend lint + production build both clean)

- `test_list_projects_endpoint.py`, `test_download_artefact_endpoint.py`,
  `test_multi_artefact_run_listing.py` — new backend coverage for the additions above.
- `npm run lint` — clean (after the effect-pattern fix).
- `npm run build` — production build + TypeScript check both succeed.
- Manual: ran both dev servers, drove the full loop through the actual browser UI — create project →
  start Analysis run → approve → start UX Design run (confirmed **both** artefacts show separately with
  working individual download links) → approve (confirmed **both** promoted to `v1.0`/baseline, phase
  advanced to Technical Design) → downloaded a `.docx` via the UI's link and confirmed it's a real,
  valid Word file (`file` reports "Microsoft Word 2007+"). Checked browser console for errors at each
  step — none.

### Assumptions

- Pages are Client Components doing plain `fetch`-based data loading against the REST API, not Server
  Components / Server Actions. Deliberate: the backend is meant to be a real API boundary usable by
  multiple future channels (Teams, Copilot, etc. per the spec's channel-abstraction requirement), and
  mixing Server Component data-fetching into a thin admin-tool shell adds complexity (CORS becomes
  irrelevant server-side but the mixed data-flow is harder to reason about) without real SEO/SSR benefit
  for an internal tool.
- No auth yet — the reviewer field on the review form is a free-text string, matching the backend's
  current lack of a `/users` endpoint or any FK validation on `reviewer_id`.
- Run/artefact state lives only in the page's React state, not persisted/resumed on refresh — there's
  still no "list runs for a project" endpoint. A page refresh mid-run loses the in-memory run reference
  even though the backend run itself is unaffected. Flagged, not fixed, this session.

### Repo / branch state

Work done on `feature/frontend-shell`, branched from `main` after session 4's 7-agent PR sequence
(#4–#10) all merged. Not yet pushed or PR'd.

## Session 4 — 2026-07-22

The user asked for the remaining 7 agents to be built one after another, each with an automatic PR and
merge (no per-agent confirmation), reporting back only once all are done. This section is updated
incrementally as each agent lands; see the git log for the exact PR-per-agent boundary.

**Outcome: all 7 landed (Data & Integration, Governance & Security, Build, Validation/QA, Test, Deploy,
Hypercare & Closure), each as its own PR, each merged.** Combined with sessions 1-3, all 11 agents from
the Version 1 frozen MVP baseline (Orchestrator + 10 specialists) now exist with a working, tested mock
vertical slice, and the full lifecycle runs end-to-end for a project name of the user's choosing.

**What this milestone does NOT mean**: every agent's mock content is deterministic placeholder text
seeded from small fixed pools, not real analysis of real input documents — there's no live LLM behind
any of them yet (`runtime: mock` in every manifest). No M365/Graph/SharePoint/Power Platform adapter
exists, even mocked. No Azure AI adapter (Document Intelligence, Content Safety, PII) exists, even
mocked. There's still no frontend. Rework is proven for one phase (Technical Design) but not exercised
at every phase. Multi-cycle baseline history (v1.1, v2.0) is still unexercised beyond the first
approval. See each agent's "Session N" entry above for what's specifically deferred per agent, and the
Session 1 entry's "Deferred to later sessions" list for the cross-cutting items (frontend, M365/Azure
adapters, Entra ID auth, the ~21 remaining data-model entities, Playwright/security/resilience test
suites, Azure IaC) — none of that has moved.

### Hypercare & Closure Agent — completed (all 11 agents now implemented)

- `03_Agent_Skills/hypercare_closure/manifest.yaml` + `SKILL.md`, single output
  `hypercare_closure_report` (Word) from `04_Templates/hypercare_closure_report.docx`.
- `HypercareClosureMockAdapter` — hypercare plan, issue resolution, handover, lessons learned, and a
  closure statement that explicitly confirms no unresolved critical defects before declaring closure.
- **This is the final lifecycle phase.** `tests/integration/test_full_lifecycle_chain.py` is the capstone
  test: drives all 10 specialist agents end-to-end (Analysis → UX Design → Technical Design →
  Data & Integration → Governance & Security → Build → Validation/QA → Test → Deploy →
  Hypercare & Closure), asserting `project.status` stays `"active"` through every intermediate approval
  and only becomes `"completed"` once the Hypercare & Closure artefact itself is approved — not merely
  from starting that final run. A second test confirms exactly the 10 expected specialist agent IDs are
  registered with zero validation failures (the Orchestrator, by design, is not manifest-registered —
  see `03_Agent_Skills/orchestrator/SKILL.md`).
- **301 tests passing.** All 11 agents (Orchestrator + 10 specialists) from the Version 1 frozen MVP
  baseline now exist with a working mock vertical slice, tested individually and as one continuous chain.

### Deploy Agent — completed

- `03_Agent_Skills/deploy/manifest.yaml` + `SKILL.md`, single output `iq_document` (Word) from
  `04_Templates/iq_document.docx`.
- `DeployMockAdapter` — states the zero-open-defects pre-deployment check explicitly (encoding the
  "must not deploy unapproved or failed components" guardrail as content, even though there's no live
  defect-count check wired yet — see deferred items) before describing deployment configuration,
  rollback plan, and evidence.
- Chain extended to nine phases; unlocks `hypercare_closure` on approval. Tests:
  `test_deploy_registration.py`, `test_deploy_chain.py`. 298 tests passing.

### Test Agent — completed

- `03_Agent_Skills/test/manifest.yaml` + `SKILL.md`, single output `test_workbook` — **Excel**, not
  Word, exercising the `openpyxl` generation path for the first time (per authoritative artefact set item
  13). Template `04_Templates/test_workbook.xlsx` has three sheets: `Test Cases`, `Summary` (with real
  `COUNTA`/`COUNTIF` formulas, not just static text), `Defects`.
- `TestAgentMockAdapter` — seeds 3 OQ/SIT/PQ/UAT test cases with stable `TC-00N` IDs, each tracing to an
  upstream entity, all `Passed`, zero defects.
- Chain extended to eight phases; unlocks `deploy` on approval. Test coverage explicitly opens the
  generated `.xlsx` with `openpyxl` and asserts sheet names, headers, row data, and the summary formula
  string — not just that a file exists. Tests: `test_test_agent_registration.py`,
  `test_test_agent_chain.py`. 296 tests passing.

### Validation / QA Agent — completed

- `03_Agent_Skills/validation_qa/manifest.yaml` + `SKILL.md`, single output `validation_report` (Word)
  from `04_Templates/validation_report.docx`.
- `ValidationQaMockAdapter` — seeded standards-check findings each citing an upstream entity, plus an
  overall "pass with findings" verdict.
- Chain extended to seven phases; unlocks `test` on approval. Tests: `test_validation_qa_registration.py`,
  `test_validation_qa_chain.py`. 294 tests passing.

### Build Agent — completed

- `03_Agent_Skills/build/manifest.yaml` + `SKILL.md`, two outputs — `build_review_report` and
  `final_code_review_report` (both Word), matching authoritative artefact set items 10-11.
- `BuildMockAdapter` — seeded build findings with stable `DEF-00N` IDs cross-referencing upstream
  entities (e.g. `SCR-004`, `DATA-002`, `ADR-002`); the Final Code Review Report confirms each is
  resolved.
- Chain extended to six phases; unlocks `validation_qa` on approval. Tests: `test_build_registration.py`,
  `test_build_chain.py`. 292 tests passing.

### Governance & Security Agent — completed

- `03_Agent_Skills/governance_security/manifest.yaml` + `SKILL.md`, single output `governance_document`
  (Word) from `04_Templates/governance_document.docx`.
- `GovernanceSecurityMockAdapter` — seeded identity/permissions defaults (least privilege, delegated over
  application permissions), DLP classification, licensing, and audit-log-backed audit requirements.
- Chain extended to five phases; unlocks `build` on approval. Tests:
  `test_governance_security_registration.py`, `test_governance_security_chain.py`. 290 tests passing.

### Data & Integration Agent — completed

- `03_Agent_Skills/data_integration/manifest.yaml` + `SKILL.md`, single output `data_design_document`
  (Word) from `04_Templates/data_design_document.docx`.
- `DataIntegrationMockAdapter` — seeded Dataverse schema entries with stable `DATA-00N` IDs,
  relationships, external-source mapping, and connector design.
- Chain extended to four phases: ... → Technical Design → Data & Integration → unlocks
  `governance_security`. Tests: `test_data_integration_registration.py`,
  `test_data_integration_chain.py`. 288 tests passing.

## Session 3 — 2026-07-22

### Completed

- Third specialist agent: **Technical Design Agent** (`03_Agent_Skills/technical_design/manifest.yaml` +
  `SKILL.md`), producing two Word artefacts per run — `solution_approach` and `architecture_handbook` —
  matching the authoritative artefact set (items 6 and 7). New templates:
  `04_Templates/solution_approach.docx`, `04_Templates/architecture_handbook.docx`.
- `TechnicalDesignMockAdapter` — deterministic seeded option analysis (with an explicit recommendation),
  architecture decisions with stable `ADR-00N` IDs, risks, limitations, and dependencies.
- Added `tests/helpers.py` (`make_orchestrator`, `run_phase_to_approval`) to stop re-deriving the same
  create/run/review boilerplate in every new chain test as the agent count grows.
- Chain now proven three phases deep: Analysis → UX Design → Technical Design → unlocks
  `data_integration`, both Technical Design artefacts correctly promoted to baseline. Also added a
  rejection-path test at this phase (confirms the project stays on `technical_design`, `pending`, ready
  for a fresh run).

### Tests executed (all passing — 286 tests, 3 new)

- `tests/unit/test_technical_design_registration.py` — manifest registers with both declared outputs.
- `tests/integration/test_technical_design_chain.py` — three-phase chain through to
  `data_integration` with correct ADR entity content, and a rejection case.

### Remaining agent backlog (updated)

Analysis, UX Design, and Technical Design are done. Still stub-only: Data & Integration, Governance &
Security, Build, Validation/QA, Test, Deploy, Hypercare & Closure (7 agents).

### Repo / branch state

Work done on `feature/technical-design-agent`, branched from `main` after session 2's
`feature/ux-design-agent` was merged (PR #2). Not yet merged — ask before merging, per the established
pattern (push + PR happens on request; merge happens only when explicitly asked).

## Session 2 — 2026-07-22

### Completed

- Second specialist agent: **UX Design Agent** (`03_Agent_Skills/ux_design/manifest.yaml` + `SKILL.md`),
  producing two artefacts per run — `ux_design_specification` (Word) and `ux_interactive_prototype`
  (HTML, kept as HTML per the frozen MVP baseline, never folded into the Word doc). New template files:
  `04_Templates/ux_design_specification.docx`, `04_Templates/ux_interactive_prototype.html`.
- `UxDesignMockAdapter` (`backend/app/adapters/mock_agent_adapter.py`) — deterministic seeded personas,
  journeys, and a screen inventory with stable `SCR-00N` IDs shared across both artefacts.
- User-supplied `project_name` is HTML-escaped before being embedded in the generated prototype —
  otherwise a project name like `<script>...</script>` would be live markup in a file meant to be opened
  in a browser. Covered by a dedicated XSS test.
- **Bug found and fixed**: `OrchestratorService.submit_review` only promoted the *most recent*
  `ArtefactVersion` for a run to baseline on approval — correct when a run produces exactly one
  artefact (Analysis), silently wrong once a run produces more than one (UX Design's spec + prototype
  would have left the prototype stuck at `draft`/`v0.1` forever). Fixed to iterate every
  `ArtefactVersion` belonging to the run.
- Full two-phase chain proven end-to-end at the service layer: Analysis approved → UX Design run
  (both artefacts generated, real docx + real html) → both approved → phase unlocks to
  `technical_design`.
- Ledger, this entry.

### Tests executed (all passing — 283 tests, 3 new)

- `tests/unit/test_ux_design_registration.py` — manifest registers cleanly from the real skills dir with
  both declared outputs.
- `tests/integration/test_two_phase_chain.py` — the Analysis → UX Design chain (both artefacts
  generated, correct content, both promoted to `v1.0`/`baseline` on approval, phase advances to
  `technical_design`), and a dedicated test that a malicious project name (`<script>...`,
  `<img onerror=...>`) is escaped in the generated HTML prototype rather than surviving as live markup.

### Remaining agent backlog (updated)

Analysis and UX Design are done. Still stub-only: Technical Design, Data & Integration, Governance &
Security, Build, Validation/QA, Test, Deploy, Hypercare & Closure (8 agents).

### Repo / branch state

Work done on `feature/ux-design-agent`, branched from `main` after session 1's
`feature/initial-build` was merged (PR #1) and the repo made public per the original spec. Not yet
merged — ask before merging, per this session's established pattern.

## Session 1 — 2026-07-22

### Completed

- Repo scaffold: legacy folder taxonomy (`00_`–`10_`) alongside `backend/`, `docs/`, `scripts/`;
  `.gitignore` covering secrets, generated/confidential runtime content, and build artefacts.
- `docs/requirements_history/v1.md`–`v4.md` — the four requirement baselines preserved verbatim.
- `03_Agent_Skills/AGENT_CONTRACT.md` — the common manifest shape, execution modes, run states, input
  sufficiency states, and request/result envelopes every agent implements.
- Data model (9 tables — session-1 scope, not the full ~30): `User`, `Project`, `AgentDef`, `AgentRun`,
  `RunEvent`, `Artefact`, `ArtefactVersion`, `Review`, `ReviewComment`. SQLAlchemy generic types + string
  UUID PKs only (Postgres/Azure SQL portable). Initial Alembic migration generated and applied.
- Agent plugin registry (`backend/app/agents_registry/`): `AgentManifest` Pydantic schema, YAML manifest
  loader that validates schema, `skill_entry`/template file existence, and adapter importability —
  excluding (not crashing on) any agent that fails validation.
- State machines (`backend/app/orchestrator/state_machines.py`): full 16-state `AgentRun` transition
  table with review-decision gating on the `IN_REVIEW` edges, and a `Project` phase/phase_status advance
  function. Every transition (allowed and blocked) is table-driven unit-tested.
- `OrchestratorService` (`backend/app/orchestrator/service.py`): the deterministic domain service owning
  version numbers, run state, and phase gating. Specialist agents never write DB state directly.
- Analysis Agent vertical slice: `manifest.yaml` + `SKILL.md` + `AnalysisMockAdapter`
  (`backend/app/adapters/mock_agent_adapter.py`) that deterministically fills
  `04_Templates/requirement_specification.docx` with seeded `REQ-00N` entries.
- FastAPI API (`backend/app/api/`): `POST /projects`, `GET /projects/{id}`, `POST
  /projects/{id}/runs`, `GET /runs/{id}`, `GET /runs/{id}/artefact-version`, `POST /runs/{id}/review`,
  `GET /agents`. Each app instance builds its own DB session factory at startup (`app/main.py` lifespan),
  which is what makes the API independently testable without global state leakage.
- `.env.example`, `README.md`, this ledger.
- `scripts/setup.ps1`, `start.ps1`, `test.ps1` — all three run clean on this machine (verified, not just
  written).
- Manual verification: ran the real server, drove the full loop over HTTP with `curl` (create project →
  start run → fetch artefact version → approve review → confirm phase unlocked to `ux_design` and run
  reached `completed`), and opened the resulting `.docx` with `python-docx` to confirm it's valid,
  non-corrupt, and contains the correct seeded requirements. Test artefacts from this manual pass were
  deleted afterward, not committed.

### Tests executed (all passing — 280 tests)

- `tests/unit/test_state_machines.py` — 265 cases: every transition-table edge, allowed and blocked,
  parametrized exhaustively, plus review-gate and phase-advance behavior.
- `tests/unit/test_migration.py` — initial Alembic migration applies cleanly to a fresh SQLite file;
  all 9 session-1 models are registered.
- `tests/unit/test_agent_registry.py` — 9 cases: valid manifest registers; folder without a manifest is
  silently skipped (not a failure); invalid schema, missing phase on a specialist, missing adapter
  module, adapter missing `execute()`, missing `skill_entry` file, missing template file are all
  excluded without crashing the loader; missing skills dir doesn't raise.
- `tests/integration/test_orchestrator_service.py` — full loop at the service layer (create → run →
  generate docx → review → approve → phase unlock), a rework cycle (rework required → rerun → v0.2 →
  approve), and the guard against starting a second run while one is awaiting review.
- `tests/integration/test_api_full_loop.py` — the same full loop driven over real HTTP via
  `TestClient`, with an isolated temp SQLite DB per test run.

### Failures found and fixed during this session

- `alembic/env.py` originally overwrote any caller-supplied `sqlalchemy.url` with the app's default
  settings URL unconditionally, silently pointing the migration-apply test at the wrong (real) database
  file instead of the test's temp file. Fixed: only fall back to the settings URL if the caller hasn't
  already set one on the `Config` object.
- `db/session.py` originally built a single module-level engine/session-factory at import time from a
  process-wide cached `Settings()` — this made the API layer untestable with an isolated DB (the HTTP
  test's env-var override would be ignored by an already-imported engine). Fixed: each `FastAPI` app
  instance now builds its own session factory in `lifespan()` from settings read at startup, stored on
  `app.state`; `get_session` reads from `request.app.state.session_factory`.
- The mock adapter wrote generated `.docx` output to the real repository's `05_Generated_Artefacts/`
  directory during test runs (no per-test isolation), leaving ~15 stray UUID-named folders on disk after
  a few suite runs. Fixed with an autouse `conftest.py` fixture that points
  `PPSDLC_GENERATED_ARTEFACTS_DIR` at a per-test temp directory; verified the real folder stays empty
  (aside from `.gitkeep`) after a full suite run.
- Initial GitHub CLI install via `winget` (MSI) failed twice with Windows Installer error 1601. Worked
  around by downloading the official portable zip release directly — see Blockers below for what's still
  outstanding.

### Assumptions

- `bommulurianji2/AI-LABProjects` does not exist on GitHub (confirmed via the public API — the account
  has only `C8_HackathonGroup16`, `DAY10`, `outskill-ai-lab`). The user chose to create it once
  authenticated, rather than reuse an existing repo. **Not yet created.**
- Session-1 "one full orchistrated cycle" targets the Analysis agent only, per the approved plan; the
  other nine agents are stub folders (`README.md` only, no manifest) so the registry loader correctly
  skips them without treating their absence as a failure.
- The v0.1 → v1.0 promotion on approval is implemented as an in-place relabel (draft → baseline on the
  same `ArtefactVersion` row), not a copy-on-approve creating a new row. This matches what the approved
  plan explicitly allowed deferring. Multi-baseline history (v1.1, v2.0 via copy) is untested.
- `Review.reviewer_id` is accepted as a raw string and not validated against an existing `User` row
  (no auth/user-management endpoints exist yet in session 1) — SQLite doesn't enforce the FK by default,
  so this doesn't fail today but is not a real integrity guarantee.

### Known limitations (not defects, tracked deliberately)

- The generated docx places the seeded `REQ-00N` paragraphs after the "Assumptions" heading instead of
  under "Functional Requirements" (a `python-docx` insertion-order quirk in the mock adapter). Content is
  100% correct; visual ordering is cosmetic. Flagged in the plan as the first thing to drop under time
  pressure — left as-is by design.
- No background/async task execution — `start_run` runs the mock adapter synchronously within the HTTP
  request. This is fine for a sub-second mock; a real LLM-backed `runtime: llm` adapter will need this
  revisited (background execution + polling) in whichever session adds it.

### Deferred to later sessions (explicit backlog)

- The other 10 agents' real manifests/adapters (UX Design, Technical Design, Data & Integration,
  Governance & Security, Build, Validation/QA, Test, Deploy, Hypercare & Closure) — currently stub
  `README.md`-only folders.
- Frontend: no Next.js app yet. Node.js/npm are not installed on this machine — install before starting
  frontend work.
- All Microsoft Graph / SharePoint / Power Platform adapters (even mocked).
- All Azure AI adapters (Document Intelligence, Content Safety, Language PII) — even mocked.
- Microsoft Entra ID auth — only a conceptual placeholder in `.env.example`; no local-dev auth exists
  yet either (API endpoints are unauthenticated).
- The remaining ~21 data-model entities (Clarification, Assumption, Risk, Decision, Exception,
  ReworkRequest, Defect, TestExecution, Notification, Integration, full AuditEvent, etc.) — session 1 used
  a 9-table subset sufficient to prove the loop.
- Playwright E2E suite, security tests, resilience tests, contract tests against real (non-mock)
  adapters.
- Azure IaC / deployment readiness.
- GitHub: `gh` is installed locally (portable zip at `%LOCALAPPDATA%\gh-cli\bin\gh.exe`) but **not
  authenticated**. The `bommulurianji2/AI-LABProjects` repo does not exist yet. No push, PR, or repo
  creation has happened — everything above is committed locally only, on `feature/initial-build`.

### Unresolved blockers

1. **`gh auth login` requires the user** — cannot be driven from an automated session (interactive
   browser/device flow). Run: `& "$env:LOCALAPPDATA\gh-cli\bin\gh.exe" auth login`
2. **`AI-LABProjects` repo doesn't exist** — needs creating under `bommulurianji2` once authenticated,
   before any remote/push work can proceed.
3. **Node.js/npm not installed** — needed before any frontend work starts.
4. **`winget install GitHub.cli` fails with MSI error 1601** on this machine — root cause not
   investigated (likely a Windows Installer service issue); worked around via the portable zip, but the
   underlying winget/MSI path is still broken if it's needed for something else later.
