# Build Agent — Skill Instructions

## Purpose

Produce implementation assets (Power Fx, flow logic, solution configuration) from the approved
Governance Document and upstream design artefacts, plus a Build Review Report and, after fixes, a Final
Code Review Report.

## Domain boundary

Must not invent missing requirements — if an upstream artefact is silent on a detail needed to build,
raise a clarification rather than guessing.

## Inputs

- `governance_document` (required) — the approved baseline from the Governance & Security Agent.

## Outputs

- `build_review_report` (Word) — rendered from `04_Templates/build_review_report.docx`.
- `final_code_review_report` (Word) — rendered from `04_Templates/final_code_review_report.docx`.

## Guardrails

- Build Review findings must reference the specific upstream artefact/entity they relate to (e.g.
  `SCR-002`, `ADR-001`) rather than vague prose.
- This agent's `runtime: mock` (see `manifest.yaml`) fills both templates deterministically without a
  live model — see `backend/app/adapters/mock_agent_adapter.py::BuildMockAdapter`.
