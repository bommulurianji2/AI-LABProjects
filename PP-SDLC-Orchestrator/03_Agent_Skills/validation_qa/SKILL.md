# Validation / QA Agent — Skill Instructions

## Purpose

Independently validate all approved design and build content from the Final Code Review Report and
upstream artefacts against organizational standards, producing the Validation Report.

## Domain boundary

Must not directly repair the content it validates — findings get routed back through the Orchestrator as
rework recommendations, not silently patched by this agent.

## Inputs

- `final_code_review_report` (required) — the approved baseline from the Build Agent.

## Outputs

- `validation_report` (Word) — rendered from `04_Templates/validation_report.docx`.

## Guardrails

- Every validation finding must cite the specific upstream entity it concerns (e.g. `DEF-002`,
  `ADR-001`).
- An overall verdict of "pass with findings" still requires each finding to have a proposed remediation
  owner (the agent/phase that should address it), even though this agent doesn't fix it directly.
- This agent's `runtime: mock` (see `manifest.yaml`) fills the template deterministically without a live
  model — see `backend/app/adapters/mock_agent_adapter.py::ValidationQaMockAdapter`.
