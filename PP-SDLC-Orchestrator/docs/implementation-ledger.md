# Implementation Ledger

Living record of what's done, tested, deferred, and blocked. Update this every session — do not let it
go stale.

## Session 4 — 2026-07-22

The user asked for the remaining 7 agents to be built one after another, each with an automatic PR and
merge (no per-agent confirmation), reporting back only once all are done. This section is updated
incrementally as each agent lands; see the git log for the exact PR-per-agent boundary.

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
