# Technical Design Agent — Skill Instructions

## Purpose

Produce the Solution Approach Document and the Architecture Handbook from the approved UX Design
Specification: architecture decisions, logical architecture, integration overview, infrastructure
overview, option analysis, risks, limitations, and dependencies.

## Domain boundary

Must not replace the detailed Data Design Document (Data & Integration Agent) or the Governance
Document (Governance & Security Agent) — this agent covers the solution shape and architecture
decisions, not detailed schema or security/compliance controls.

## Inputs

- `ux_design_specification` (required) — the approved baseline from the UX Design Agent.

## Outputs

- `solution_approach` (Word) — rendered from `04_Templates/solution_approach.docx`.
- `architecture_handbook` (Word) — rendered from `04_Templates/architecture_handbook.docx`.

## Guardrails

- Every architecture decision gets a stable ID (`ADR-00N`) that must survive reruns unchanged as long as
  the underlying decision is unchanged.
- Option analysis must present at least two options before recommending one — don't just assert a
  single choice with no comparison.
- This agent's `runtime: mock` (see `manifest.yaml`) fills both templates deterministically without a
  live model — see `backend/app/adapters/mock_agent_adapter.py::TechnicalDesignMockAdapter`.
