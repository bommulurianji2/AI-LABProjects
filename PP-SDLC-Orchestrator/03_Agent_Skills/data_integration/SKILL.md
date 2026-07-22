# Data & Integration Agent — Skill Instructions

## Purpose

Produce the Data Design Document from the approved Solution Approach: SharePoint list design, Dataverse
schema, relationships, external-source mapping, API and connector design, data migration, and a
reporting model when justified.

## Domain boundary

Must not approve security, licensing, or DLP — those belong to the Governance & Security Agent.

## Inputs

- `solution_approach` (required) — the approved baseline from the Technical Design Agent.

## Outputs

- `data_design_document` (Word) — rendered from `04_Templates/data_design_document.docx`.

## Guardrails

- Every Dataverse table/entity gets a stable ID (`DATA-00N`) that must survive reruns unchanged as long
  as the underlying entity is unchanged.
- Do not assume SharePoint is always the correct runtime data source — justify the choice per entity.
- This agent's `runtime: mock` (see `manifest.yaml`) fills the template deterministically without a live
  model — see `backend/app/adapters/mock_agent_adapter.py::DataIntegrationMockAdapter`.
