# Implementation Ledger

Living record of what's done, tested, deferred, and blocked. Update this every session — do not let it
go stale.

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
