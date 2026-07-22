# Deploy Agent — Skill Instructions

## Purpose

Produce the IQ Document from the approved Test Workbook: deployment configuration, pre-deployment
verification, rollback plan, and deployment evidence.

## Domain boundary

Must not deploy unapproved or failed components — this agent checks that the upstream Test Workbook
shows zero open defects before proceeding to describe a deployment; if defects are open, it must raise a
blocker rather than deploying anyway.

## Inputs

- `test_workbook` (required) — the approved baseline from the Test Agent.

## Outputs

- `iq_document` (Word) — rendered from `04_Templates/iq_document.docx`.

## Guardrails

- Pre-deployment verification must explicitly reference the Test Workbook's zero-defect status before
  describing deployment steps.
- This agent's `runtime: mock` (see `manifest.yaml`) fills the template deterministically without a live
  model — see `backend/app/adapters/mock_agent_adapter.py::DeployMockAdapter`.
