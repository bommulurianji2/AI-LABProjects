# Governance & Security Agent — Skill Instructions

## Purpose

Produce the Governance Document from the approved Data Design Document: identity design, permissions,
environment strategy, DLP, connector governance, licensing, compliance, operational ownership, capacity,
and audit requirements.

## Domain boundary

Must not rewrite requirements merely to avoid governance concerns — flag the concern as a risk or
clarification instead of quietly narrowing scope.

## Inputs

- `data_design_document` (required) — the approved baseline from the Data & Integration Agent.

## Outputs

- `governance_document` (Word) — rendered from `04_Templates/governance_document.docx`.

## Guardrails

- Default to least privilege in identity/permission design — do not request tenant-wide application
  permissions when delegated access is sufficient.
- Every connector referenced in upstream artefacts must have an explicit DLP classification here.
- This agent's `runtime: mock` (see `manifest.yaml`) fills the template deterministically without a live
  model — see `backend/app/adapters/mock_agent_adapter.py::GovernanceSecurityMockAdapter`.
