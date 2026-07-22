# Agent Contract

Every agent — orchestrator or specialist, present or future — is defined by a manifest and communicates
through the input/output shapes below. This is the mechanism that lets a new agent be added by dropping a
folder under `03_Agent_Skills/<agent-id>/`, without changing core orchestration code.

Machine-readable schema: `backend/app/agents_registry/manifest_schema.py` (Pydantic `AgentManifest`) and the
run request/result envelopes in `backend/app/agents_registry/contract.py`.

## Manifest (`manifest.yaml`)

```yaml
id: analysis                       # stable slug, matches folder name
display_name: Analysis Agent
version: "0.1.0"
kind: specialist                   # orchestrator | specialist
phase: analysis                    # lifecycle phase this agent owns (null for orchestrator)
runtime: mock                      # mock | llm
requires_review: true
inputs:
  - artefact_type: high_level_requirement
    required: true
outputs:
  - artefact_type: requirement_specification
    template: 04_Templates/requirement_specification.docx
skill_entry: 03_Agent_Skills/analysis/SKILL.md
adapter: app.adapters.mock_agent_adapter:AnalysisMockAdapter
```

Fields are validated by `AgentManifest` at backend startup. A manifest that fails validation (bad schema,
missing adapter module, missing template) is excluded from the registry with a logged reason — it does not
crash boot.

## Execution modes

- **ORCHESTRATED** — the `OrchestratorService` invokes the agent as part of a project's lifecycle, supplying
  approved upstream artefacts as input and writing the resulting state itself.
- **STANDALONE** — a user invokes the agent directly with ad-hoc inputs; the agent may recommend a follow-up
  agent but must never invoke one itself.

## Input sufficiency states

`Sufficient` | `Conditionally Sufficient` | `Insufficient`

## Run states

`Not Started` · `Ready` · `Queued` · `Running` · `Waiting for Clarification` · `Waiting for Human Review` ·
`Blocked` · `Ready for Review` · `In Review` · `Approved` · `Approved with Comments` · `Rework Required` ·
`Rejected` · `Completed` · `Failed` · `Cancelled`

Transitions are enforced by an explicit table + guard functions in
`backend/app/orchestrator/state_machines.py` — see that module for the authoritative edge list.

## Request envelope (`AgentRunRequest`)

execution_mode · project_id · invocation_id · agent_id · task_id · task_request · lifecycle_phase ·
source_artefacts (+versions) · reference_documents · constraints · requested_outputs · output_path ·
previous_output (+version) · reviewer_comments · rework_context · open_clarifications ·
accepted_assumptions · security_context · user_identity · correlation_id

## Result envelope (`AgentRunResult`)

execution_summary · artefacts_produced (+versions) · references_used · assumptions · clarifications ·
risks · decisions · warnings · validation_findings · handoff_package · rework_recommendations ·
downstream_impacts · review_status · execution_metrics · error (nullable)

The result envelope shape is identical whether `runtime: mock` or `runtime: llm` produced it — this is what
lets a specialist agent swap from mock to a real model later via a manifest edit, not a rewrite.
