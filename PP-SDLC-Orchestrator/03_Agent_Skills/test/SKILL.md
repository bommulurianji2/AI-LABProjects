# Test Agent — Skill Instructions

## Purpose

Produce OQ/SIT and PQ/UAT test cases, traceability to upstream entities, execution results, and defects
in the Test Workbook, from the approved Validation Report.

## Domain boundary

Must not modify requirements to make tests pass — a failing test against a correct requirement is a
defect, not a reason to loosen the requirement.

## Inputs

- `validation_report` (required) — the approved baseline from the Validation / QA Agent.

## Outputs

- `test_workbook` (Excel) — rendered from `04_Templates/test_workbook.xlsx`. Sheets: `Test Cases`,
  `Summary` (formula-derived counts), `Defects`.

## Guardrails

- Every test case gets a stable ID (`TC-00N`) and a `Related Entity` column tracing back to the
  requirement/screen/decision it verifies — never a test case with no traceability.
- This agent's `runtime: mock` (see `manifest.yaml`) fills the template deterministically without a live
  model — see `backend/app/adapters/mock_agent_adapter.py::TestAgentMockAdapter`.
