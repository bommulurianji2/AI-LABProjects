# Hypercare & Closure Agent — Skill Instructions

## Purpose

Produce the Hypercare & Closure Report from the approved IQ Document: hypercare plan and results, issue
resolution, handover, lessons learned, and closure. This is the final phase — approval of this agent's
artefact completes the project.

## Domain boundary

Must not close projects with unresolved critical defects — the closure statement must explicitly confirm
none are open before declaring closure.

## Inputs

- `iq_document` (required) — the approved baseline from the Deploy Agent.

## Outputs

- `hypercare_closure_report` (Word) — rendered from `04_Templates/hypercare_closure_report.docx`.

## Guardrails

- The closure statement must reference the Test Workbook's defect status (carried forward via the
  IQ Document's pre-deployment verification) — do not close silently without that check.
- This is the last lifecycle phase: approving this artefact sets the project's overall status to
  `completed` (see `app/orchestrator/state_machines.py::advance_phase`).
- This agent's `runtime: mock` (see `manifest.yaml`) fills the template deterministically without a live
  model — see `backend/app/adapters/mock_agent_adapter.py::HypercareClosureMockAdapter`.
