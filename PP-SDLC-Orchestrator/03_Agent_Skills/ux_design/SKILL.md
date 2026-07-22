# UX Design Agent — Skill Instructions

## Purpose

Produce the UX Design Specification and a separate interactive HTML prototype from the approved
Requirement Specification: personas, journeys, screen inventory, navigation, responsive behavior,
accessibility considerations, and embedded wireframes (in the Word document) plus a standalone
interactive HTML prototype (kept as HTML, never folded into the Word document).

## Domain boundary

Must not select licensing or final data architecture — those belong to the Governance & Security Agent
and the Data & Integration Agent respectively.

## Inputs

- `requirement_specification` (required) — the approved baseline from the Analysis Agent.

## Outputs

- `ux_design_specification` (Word) — rendered from `04_Templates/ux_design_specification.docx`.
- `ux_interactive_prototype` (HTML) — rendered from `04_Templates/ux_interactive_prototype.html`. Stays
  HTML per the frozen MVP baseline (`docs/requirements_history/v1.md`) — never converted to a Word
  embed.

## Guardrails

- Screen inventory entries get stable IDs (`SCR-00N`) that must survive reruns unchanged as long as the
  underlying screen is unchanged.
- Every screen in the inventory should have a corresponding entry in the interactive prototype's
  navigation — don't let the two artefacts drift apart.
- This agent's `runtime: mock` (see `manifest.yaml`) fills both templates deterministically without a
  live model — see `backend/app/adapters/mock_agent_adapter.py::UxDesignMockAdapter`.
