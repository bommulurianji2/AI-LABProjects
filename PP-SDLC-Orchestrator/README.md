# PP-SDLC-Orchestrator

An enterprise, human-governed, multi-agent SDLC platform for delivering Microsoft 365 and Power
Platform solutions. Eleven pluggable agents (one Orchestrator + ten specialists) run in either
**orchestrated** mode (the Orchestrator drives the lifecycle, gating every phase on human review and
approval) or **standalone** mode (a user invokes one agent directly).

This is a **session-1 slice**: the full architecture (plugin registry, Agent Contract, data model, state
machines) is built to spec, with one specialist agent (Analysis) wired end-to-end and proven with real,
passing tests. The remaining nine agents, the full UI, and all M365/Azure integrations are deliberately
deferred — see [`docs/implementation-ledger.md`](docs/implementation-ledger.md) for exactly what's done,
tested, and next.

## What's here

- `backend/` — FastAPI + SQLAlchemy + Alembic backend. See below to run it.
- `03_Agent_Skills/` — one folder per agent; `manifest.yaml` + `SKILL.md` per implemented agent.
  `AGENT_CONTRACT.md` documents the common input/output envelope every agent implements.
- `04_Templates/` — versioned source Word/Excel templates used to render artefacts.
- `00_,05_-10_*` — generated/confidential runtime folders (gitignored; kept in git only as `.gitkeep`).
- `docs/requirements_history/` — the four requirement baselines (v1-v4) preserved verbatim as design
  history.
- `scripts/` — PowerShell dev scripts (`setup.ps1`, `start.ps1`, `test.ps1`).

## Quick start (Windows / PowerShell)

```powershell
.\scripts\setup.ps1   # creates the backend venv, installs deps, applies migrations
.\scripts\start.ps1   # runs the API at http://127.0.0.1:8000 (docs at /docs)
.\scripts\test.ps1    # runs the backend test suite
```

Requires Python 3.11+ on PATH. Node.js/npm are not required yet — the frontend is deferred (see the
ledger).

## Status

Local Development Ready for the Analysis-agent vertical slice. Not yet Integration Test Ready (M365/Azure
adapters are unbuilt, even as mocks), not yet Azure Development Environment Ready, not UAT/Production
Ready. See the ledger for the full breakdown.
