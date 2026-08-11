"""Deterministic mock runtimes for specialist agents.

Each adapter here returns the same `AgentRunResult` envelope shape a future
`runtime: llm` adapter would return from a real model call — orchestration
code never branches on which produced it.
"""

import hashlib

from docx import Document

from app.adapters import (
    build_renderer,
    common,
    data_integration_renderer,
    deploy_renderer,
    governance_security_renderer,
    hypercare_closure_renderer,
    requirement_specification_renderer,
    technical_design_renderer,
    test_renderer,
    ux_design_renderer,
    validation_qa_renderer,
)
from app.agents_registry.contract import AgentRunRequest, AgentRunResult, ProducedArtefact
from app.config import REPO_ROOT, get_settings

REQUIREMENT_POOL = [
    "The system shall allow an authenticated user to create a new project.",
    "The system shall capture a high-level requirement document per project.",
    "The system shall record functional and non-functional requirements distinctly.",
    "The system shall generate a versioned artefact for every agent run.",
    "The system shall block phase progression until a human approval is recorded.",
]


PERSONA_POOL = [
    "Priya, an HR administrator who processes requests in bulk and needs fast bulk actions.",
    "Sam, a first-time employee user who needs a simple, guided flow with minimal jargon.",
    "Dana, a line manager who mostly approves or rejects requests from a mobile device.",
]

JOURNEY_POOL = [
    "Submit a new request, receive confirmation, and track its status to resolution.",
    "Review a pending request, add a comment, and approve or reject it.",
    "Search past requests and export a filtered list for reporting.",
]

SCREEN_POOL = [
    ("Dashboard", "Landing screen summarizing open items and recent activity."),
    ("Request Form", "Guided form for submitting a new request."),
    ("Request Detail", "Full detail view with status, history, and actions."),
    ("Approvals Queue", "List of items awaiting the current user's decision."),
]

ARCHITECTURE_OPTION_POOL = [
    (
        "Single-tenant Power Platform environment",
        "Simple to govern, but limits reuse of components across projects.",
    ),
    (
        "Shared Power Platform environment with solution layering",
        "Better reuse, but requires stricter ALM discipline to avoid cross-solution breakage.",
    ),
    (
        "Hybrid: Power Platform frontend with Azure backend services",
        "More flexible integration surface, but higher operational and cost complexity.",
    ),
]

ADR_POOL = [
    "Use a shared Dataverse environment with solution-based ALM for this delivery.",
    "Expose external integrations through a dedicated custom connector rather than direct HTTP calls "
    "from Power Automate.",
    "Keep all AI model calls behind a provider abstraction so the model can be swapped without "
    "touching business logic.",
    "Model the interactive HTML prototype as a standalone artefact, never embedded inside a Word "
    "document.",
]

RISK_POOL = [
    "Underestimating Dataverse API request limits during peak usage.",
    "Vendor lock-in if the AI provider abstraction is bypassed by a specialist agent.",
    "Schema drift between the future Data Design Document and the actual Dataverse solution.",
]

LIMITATION_POOL = [
    "This document does not cover detailed data schema — see the Data Design Document.",
    "This document does not cover security or compliance controls — see the Governance Document.",
]

DEPENDENCY_POOL = [
    "Depends on the approved UX Design Specification for screen and navigation scope.",
    "Depends on Power Platform environment provisioning being complete before Build starts.",
]

DATAVERSE_ENTITY_POOL = [
    ("Request", "Core transactional table holding one row per submitted request."),
    ("RequestLine", "Child table for multi-line requests; relates 1:N to Request."),
    ("Approval", "Records each approval decision against a Request."),
    ("Attachment", "Stores metadata for files attached to a Request (content in SharePoint)."),
]

RELATIONSHIP_POOL = [
    "Request (1) -> RequestLine (N): a request may contain multiple line items.",
    "Request (1) -> Approval (N): a request accumulates one approval record per approver.",
    "Request (1) -> Attachment (N): a request may carry multiple supporting attachments.",
]

EXTERNAL_SOURCE_POOL = [
    "Employee directory sourced from Microsoft Entra ID via Microsoft Graph (read-only).",
    "Cost center reference data sourced from the finance system via a nightly export, not real-time.",
]

CONNECTOR_POOL = [
    "Custom connector wrapping the finance system's REST API; no direct HTTP calls from flows.",
    "Standard SharePoint connector for attachment storage; Dataverse remains the system of record for metadata.",
]

DLP_POOL = [
    "Business data group: Dataverse, SharePoint, Microsoft Teams.",
    "Non-business data group: all other connectors, blocked by default.",
    "Custom connectors require explicit DLP review before promotion past the dev environment.",
]

LICENSING_POOL = [
    "Per-user Power Apps license assumed for all internal users; confirm with the licensing owner before build.",
    "Dataverse capacity consumption estimated from entity count and expected transaction volume.",
]

BUILD_FINDING_POOL = [
    "Approvals Queue screen (SCR-004) missing an empty-state message when no items are pending.",
    "RequestLine (DATA-002) relationship not yet wired to the Request form's subgrid.",
    "Custom connector for the finance system (per ADR-002) not yet configured with retry/backoff.",
]

VALIDATION_FINDING_POOL = [
    "Accessibility check on the Request Form (SCR-002): confirm keyboard focus order matches visual order.",
    "Naming convention check: confirm all Dataverse entities follow the agreed prefix per DATA-001.",
    "Traceability check: confirm every DEF-00N from the Build Review Report has a corresponding fix entry.",
]

TEST_CASE_POOL = [
    ("OQ", "Verify the Request Form submits successfully with all required fields populated.", "REQ-001"),
    ("SIT", "Verify the custom connector to the finance system returns a valid response.", "ADR-002"),
    ("PQ", "Verify an approver can approve a request from the Approvals Queue on mobile.", "SCR-004"),
    ("UAT", "Verify an end user can track a submitted request to resolution.", "REQ-002"),
]


def _deterministic_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


# Single source of truth lives in app.adapters.common - aliased here so the
# ~10 call sites below don't all need touching.
_version_label = common.version_label


class AnalysisMockAdapter:
    """Deterministic mock runtime for the Analysis Agent.

    Fills 04_Templates/requirement_specification.docx with seeded content.
    Same input (project_id, phase, run_number) always yields the same
    requirement selection.
    """

    ARTEFACT_TYPE = "requirement_specification"
    TEMPLATE_RELATIVE_PATH = "04_Templates/requirement_specification.docx"

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "analysis", str(request.run_number)
        )

        count = 3
        start = seed % len(REQUIREMENT_POOL)
        chosen = [REQUIREMENT_POOL[(start + i) % len(REQUIREMENT_POOL)] for i in range(count)]
        entities = [f"REQ-{i + 1:03d}" for i in range(count)]
        requirement_lines = [f"{eid}: {text}" for eid, text in zip(entities, chosen, strict=True)]

        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        output_path = (
            settings.generated_artefacts_dir / request.project_id / self.ARTEFACT_TYPE / f"{version_label}.docx"
        )
        requirement_specification_renderer.render(
            repo_root=REPO_ROOT,
            output_path=output_path,
            project_name=str(project_name),
            version_label=version_label,
            scope_text=f"Scope derived from: {request.task_request}",
            requirement_lines=requirement_lines,
            assumptions_text="No blocking assumptions for this mock run.",
        )

        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        produced = ProducedArtefact(
            artefact_type=self.ARTEFACT_TYPE,
            stable_key=self.ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=entities,
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE} with {count} seeded requirements.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "requirement_count": count},
        )


class UxDesignMockAdapter:
    """Deterministic mock runtime for the UX Design Agent.

    Produces two artefacts: the UX Design Specification (Word) and a
    separate interactive HTML prototype — kept as HTML, never folded into
    the Word document, per the frozen MVP baseline.
    """

    SPEC_ARTEFACT_TYPE = "ux_design_specification"
    PROTOTYPE_ARTEFACT_TYPE = "ux_interactive_prototype"
    SPEC_TEMPLATE_RELATIVE_PATH = "04_Templates/ux_design_specification.docx"
    PROTOTYPE_TEMPLATE_RELATIVE_PATH = "04_Templates/ux_interactive_prototype.html"

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "ux_design", str(request.run_number)
        )
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        p_start = seed % len(PERSONA_POOL)
        personas = [PERSONA_POOL[(p_start + i) % len(PERSONA_POOL)] for i in range(2)]

        j_start = seed % len(JOURNEY_POOL)
        journeys = [JOURNEY_POOL[(j_start + i) % len(JOURNEY_POOL)] for i in range(2)]

        screen_count = 3
        s_start = seed % len(SCREEN_POOL)
        screens = [SCREEN_POOL[(s_start + i) % len(SCREEN_POOL)] for i in range(screen_count)]
        screen_entities = [f"SCR-{i + 1:03d}" for i in range(screen_count)]

        output_dir = settings.generated_artefacts_dir / request.project_id
        spec_produced = ux_design_renderer.render_spec(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            personas=personas,
            journeys=journeys,
            screens=screens,
            screen_entities=screen_entities,
            responsive_behavior_text=(
                "Layouts collapse to a single column below 768px; the Approvals Queue "
                "prioritizes card view on mobile."
            ),
            accessibility_text=(
                "All interactive elements are keyboard-reachable; color contrast meets "
                "WCAG AA; forms carry explicit labels."
            ),
        )
        prototype_produced = ux_design_renderer.render_prototype(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            screens=screens,
            screen_entities=screen_entities,
        )

        return AgentRunResult(
            execution_summary=(
                f"Generated {self.SPEC_ARTEFACT_TYPE} and {self.PROTOTYPE_ARTEFACT_TYPE} "
                f"with {screen_count} seeded screens."
            ),
            artefacts_produced=[spec_produced, prototype_produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "screen_count": screen_count},
        )


class TechnicalDesignMockAdapter:
    """Deterministic mock runtime for the Technical Design Agent.

    Produces two artefacts per run: the Solution Approach Document and the
    Architecture Handbook — both Word, per the authoritative artefact set.
    """

    SOLUTION_APPROACH_ARTEFACT_TYPE = technical_design_renderer.SOLUTION_APPROACH_ARTEFACT_TYPE
    ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE = technical_design_renderer.ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "technical_design", str(request.run_number)
        )
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        o_start = seed % len(ARCHITECTURE_OPTION_POOL)
        options = [ARCHITECTURE_OPTION_POOL[(o_start + i) % len(ARCHITECTURE_OPTION_POOL)] for i in range(2)]

        adr_count = 3
        a_start = seed % len(ADR_POOL)
        decisions = [ADR_POOL[(a_start + i) % len(ADR_POOL)] for i in range(adr_count)]
        adr_entities = [f"ADR-{i + 1:03d}" for i in range(adr_count)]

        r_start = seed % len(RISK_POOL)
        risks = [RISK_POOL[(r_start + i) % len(RISK_POOL)] for i in range(2)]

        output_dir = settings.generated_artefacts_dir / request.project_id
        solution_approach_produced = technical_design_renderer.render_solution_approach(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            options=options,
            decisions=decisions,
            decision_entities=adr_entities,
            risks=risks,
            limitations=LIMITATION_POOL,
            dependencies=DEPENDENCY_POOL,
        )
        architecture_handbook_produced = technical_design_renderer.render_architecture_handbook(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            logical_architecture_text=(
                "Power Platform canvas/model-driven app frontend, Dataverse as the system of "
                "record, Power Automate for workflow orchestration."
            ),
            integration_overview_text=(
                "External systems are integrated via dedicated custom connectors; no direct "
                "HTTP calls from flows to third-party APIs."
            ),
            infrastructure_overview_text=(
                "Dev/test/prod Power Platform environments with solution-based ALM; Azure "
                "services (if any) sit behind the same connector layer."
            ),
        )

        return AgentRunResult(
            execution_summary=(
                f"Generated {self.SOLUTION_APPROACH_ARTEFACT_TYPE} and "
                f"{self.ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE} with {adr_count} seeded architecture decisions."
            ),
            artefacts_produced=[solution_approach_produced, architecture_handbook_produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "adr_count": adr_count},
        )


class DataIntegrationMockAdapter:
    """Deterministic mock runtime for the Data & Integration Agent.

    Fills 04_Templates/data_design_document.docx with a seeded Dataverse
    schema, relationships, external-source mapping, and connector design.
    """

    ARTEFACT_TYPE = data_integration_renderer.ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "data_integration", str(request.run_number)
        )
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        entity_count = 3
        e_start = seed % len(DATAVERSE_ENTITY_POOL)
        entities_chosen = [
            DATAVERSE_ENTITY_POOL[(e_start + i) % len(DATAVERSE_ENTITY_POOL)] for i in range(entity_count)
        ]
        data_entities = [f"DATA-{i + 1:03d}" for i in range(entity_count)]

        rel_start = seed % len(RELATIONSHIP_POOL)
        relationships = [RELATIONSHIP_POOL[(rel_start + i) % len(RELATIONSHIP_POOL)] for i in range(2)]

        output_dir = settings.generated_artefacts_dir / request.project_id
        produced = data_integration_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            entities=entities_chosen,
            entity_ids=data_entities,
            relationships=relationships,
            external_sources=EXTERNAL_SOURCE_POOL,
            connectors=CONNECTOR_POOL,
            data_migration_text="No legacy data migration in scope for this mock run.",
            reporting_model_text="Power BI reporting deferred until reporting requirements are confirmed.",
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE} with {entity_count} seeded Dataverse entities.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "entity_count": entity_count},
        )


class GovernanceSecurityMockAdapter:
    """Deterministic mock runtime for the Governance & Security Agent.

    Fills 04_Templates/governance_document.docx with seeded identity,
    permissions, DLP, licensing, and audit content.
    """

    ARTEFACT_TYPE = governance_security_renderer.ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "governance_security", str(request.run_number)
        )
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        output_dir = settings.generated_artefacts_dir / request.project_id
        produced = governance_security_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            identity_design_text="Microsoft Entra ID as the identity provider; delegated permissions by default.",
            permissions_text=(
                "Least privilege: delegated Graph permissions unless an application-only flow is justified."
            ),
            environment_strategy_text=(
                "Separate dev, test, and production Power Platform environments with solution-based ALM."
            ),
            dlp_lines=DLP_POOL,
            connector_governance_text=(
                "Every connector introduced by an upstream artefact requires an explicit DLP "
                "classification here before use."
            ),
            licensing_lines=LICENSING_POOL,
            compliance_text=(
                "No regulated data categories identified for this mock run; revisit if PII/PHI scope changes."
            ),
            operational_ownership_text=(
                "Platform Administrator role owns environment health; Project Owner owns business escalation."
            ),
            audit_requirements_text=(
                "All approval and rework events are captured in the RunEvent audit log; retained per "
                "organizational policy."
            ),
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE}.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed},
        )


class BuildMockAdapter:
    """Deterministic mock runtime for the Build Agent.

    Produces two artefacts per run: the Build Review Report (seeded
    findings with stable DEF-00N IDs) and the Final Code Review Report
    (confirming those findings are resolved).
    """

    BUILD_REVIEW_ARTEFACT_TYPE = build_renderer.BUILD_REVIEW_ARTEFACT_TYPE
    FINAL_CODE_REVIEW_ARTEFACT_TYPE = build_renderer.FINAL_CODE_REVIEW_ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(request.project_id, request.lifecycle_phase or "build", str(request.run_number))
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        finding_count = 2
        f_start = seed % len(BUILD_FINDING_POOL)
        findings = [BUILD_FINDING_POOL[(f_start + i) % len(BUILD_FINDING_POOL)] for i in range(finding_count)]
        defect_entities = [f"DEF-{i + 1:03d}" for i in range(finding_count)]

        output_dir = settings.generated_artefacts_dir / request.project_id
        build_review_produced = build_renderer.render_build_review(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            implementation_assets_text=(
                "Canvas app screens, Dataverse solution, and Power Automate flows built per the "
                "approved design artefacts."
            ),
            configuration_summary_text=(
                "Environment variables and connection references configured per the Governance Document."
            ),
            findings=findings,
            defect_entities=defect_entities,
            fixes_applied=[f"{eid}: fixed and re-verified in this mock build run." for eid in defect_entities],
        )
        final_code_review_produced = build_renderer.render_final_code_review(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            review_scope_text="Full review of all implementation assets produced in this build cycle.",
            findings_text="No new findings beyond those already tracked in the Build Review Report.",
            defect_entities=defect_entities,
            resolution_lines=[f"{eid}: resolved." for eid in defect_entities],
        )

        return AgentRunResult(
            execution_summary=(
                f"Generated {self.BUILD_REVIEW_ARTEFACT_TYPE} and {self.FINAL_CODE_REVIEW_ARTEFACT_TYPE} "
                f"with {finding_count} seeded findings, all resolved."
            ),
            artefacts_produced=[build_review_produced, final_code_review_produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "finding_count": finding_count},
        )


class ValidationQaMockAdapter:
    """Deterministic mock runtime for the Validation / QA Agent.

    Fills 04_Templates/validation_report.docx with seeded standards-check
    findings, each citing an upstream entity, plus an overall verdict.
    """

    ARTEFACT_TYPE = validation_qa_renderer.ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "validation_qa", str(request.run_number)
        )
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        finding_count = 2
        f_start = seed % len(VALIDATION_FINDING_POOL)
        findings = [
            VALIDATION_FINDING_POOL[(f_start + i) % len(VALIDATION_FINDING_POOL)] for i in range(finding_count)
        ]

        output_dir = settings.generated_artefacts_dir / request.project_id
        produced = validation_qa_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            validation_scope_text=(
                "Independent validation of all approved design and build artefacts for this project."
            ),
            standards_assessment_text=(
                "Assessed against accessibility, naming convention, and traceability standards."
            ),
            findings=findings,
            overall_verdict_text="Pass with findings — see above; no critical defects block progression.",
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE} with {finding_count} seeded findings.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "finding_count": finding_count},
        )


class TestAgentMockAdapter:
    """Deterministic mock runtime for the Test Agent.

    Fills 04_Templates/test_workbook.xlsx — an Excel artefact rather than
    Word, exercising the openpyxl generation path — with seeded OQ/SIT/PQ/UAT
    test cases traced to upstream entities, all passing, zero defects.
    """

    # Tells pytest not to try collecting this as a test class — its name
    # happens to start with "Test" (it's the Test Agent, not a test suite).
    __test__ = False

    ARTEFACT_TYPE = test_renderer.ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(request.project_id, request.lifecycle_phase or "test", str(request.run_number))
        version_label = _version_label(request.run_number)

        case_count = 3
        c_start = seed % len(TEST_CASE_POOL)
        cases = [TEST_CASE_POOL[(c_start + i) % len(TEST_CASE_POOL)] for i in range(case_count)]
        case_entities = [f"TC-{i + 1:03d}" for i in range(case_count)]

        output_dir = settings.generated_artefacts_dir / request.project_id
        produced = test_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            version_label=version_label,
            cases=cases,
            case_entities=case_entities,
            case_statuses=["Passed"] * case_count,
            defects=[],
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE} with {case_count} seeded test cases, all passing.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "case_count": case_count},
        )


class DeployMockAdapter:
    """Deterministic mock runtime for the Deploy Agent.

    Fills 04_Templates/iq_document.docx. The mock assumes the upstream Test
    Workbook showed zero open defects (true for every run in this session's
    mock chain) and states that check explicitly before describing
    deployment steps — per the "must not deploy unapproved or failed
    components" guardrail.
    """

    ARTEFACT_TYPE = deploy_renderer.ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(request.project_id, request.lifecycle_phase or "deploy", str(request.run_number))
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        output_dir = settings.generated_artefacts_dir / request.project_id
        produced = deploy_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            deployment_configuration_text=(
                "Solution deployed via Power Platform CLI import into the target environment, driven "
                "by the approved connection references and environment variables."
            ),
            pre_deployment_verification_text=(
                "Verified: the Test Workbook's Defects sheet shows zero open defects for this version. "
                "Deployment does not proceed if this check fails."
            ),
            rollback_plan_text=(
                "Prior solution version remains installed and can be re-activated; no destructive "
                "schema changes are applied without a separate approved migration step."
            ),
            deployment_evidence_text=(
                "Deployment evidence (solution import log, environment snapshot) is attached per the "
                "organization's evidence retention policy."
            ),
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE}.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed},
        )


class HypercareClosureMockAdapter:
    """Deterministic mock runtime for the Hypercare & Closure Agent — the
    final lifecycle phase. Fills 04_Templates/hypercare_closure_report.docx.
    The closure statement explicitly confirms no unresolved critical
    defects before declaring closure, per the domain guardrail.
    """

    ARTEFACT_TYPE = hypercare_closure_renderer.ARTEFACT_TYPE

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "hypercare_closure", str(request.run_number)
        )
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        output_dir = settings.generated_artefacts_dir / request.project_id
        produced = hypercare_closure_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            hypercare_plan_text=(
                "Two-week hypercare window post-deployment; daily stand-up to triage any reported issues."
            ),
            issue_resolution_text="No issues reported during the hypercare window for this mock run.",
            handover_text=(
                "Operational ownership transferred to the Platform Administrator role per the "
                "Governance Document."
            ),
            lessons_learned_text=(
                "Seeding deterministic mock content early made the full orchestrated loop testable "
                "before any live model integration existed."
            ),
            closure_statement_text=(
                "No unresolved critical defects — confirmed via the Test Workbook and carried forward "
                "through the IQ Document. Project is approved for closure."
            ),
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE}.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed},
        )
