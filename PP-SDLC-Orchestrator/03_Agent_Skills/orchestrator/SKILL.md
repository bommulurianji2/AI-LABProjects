# SDLC Orchestrator — Skill Instructions (reference documentation only)

## Purpose

Owns project state, execution, approvals, routing, exceptions, and version tracking across the full
lifecycle. Determines the valid next agent, validates approved upstream artefacts, assembles project
context, assigns execution versions, invokes specialist agents, routes clarifications, pauses for human
review, records approval, unlocks the next phase, routes rework, and reassesses downstream impact.

## Domain boundary

Never rewrites a specialist agent's authoritative artefact directly. Never silently overwrites an
approved artefact version.

## Implementation note

Unlike the specialist agents, the Orchestrator is **not** manifest-registered as a runnable
`AgentAdapter` — it is a deterministic domain service (`backend/app/orchestrator/service.py`,
`OrchestratorService`) because it must own version numbers, state transitions, and approval gating with
full auditability, not produce prompted/non-deterministic output. This folder has no `manifest.yaml` by
design; the agent registry skips folders without one. This `SKILL.md` documents its guardrails for
reference and for a future declarative/LLM-assisted orchestration layer, should one be added.
