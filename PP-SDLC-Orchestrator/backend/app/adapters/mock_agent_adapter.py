"""Deterministic mock runtimes for specialist agents.

Each adapter here returns the same `AgentRunResult` envelope shape a future
`runtime: llm` adapter would return from a real model call — orchestration
code never branches on which produced it.
"""

import hashlib
import html

from docx import Document

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


def _deterministic_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _version_label(run_number: int) -> str:
    return "v0.1" if run_number == 1 else f"v0.{run_number}"


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

        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        doc = Document(str(REPO_ROOT / self.TEMPLATE_RELATIVE_PATH))
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{SCOPE}}" in para.text:
                para.text = f"Scope derived from: {request.task_request}"
            elif "{{REQUIREMENTS_TABLE}}" in para.text:
                para.text = ""
                for entity, text in zip(entities, chosen, strict=True):
                    doc.add_paragraph(f"{entity}: {text}")
            elif "{{ASSUMPTIONS}}" in para.text:
                para.text = "No blocking assumptions for this mock run."

        output_dir = settings.generated_artefacts_dir / request.project_id / self.ARTEFACT_TYPE
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{version_label}.docx"
        doc.save(output_path)

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
        spec_produced = self._render_spec(
            project_name, version_label, personas, journeys, screens, screen_entities, output_dir
        )
        prototype_produced = self._render_prototype(project_name, version_label, screens, screen_entities, output_dir)

        return AgentRunResult(
            execution_summary=(
                f"Generated {self.SPEC_ARTEFACT_TYPE} and {self.PROTOTYPE_ARTEFACT_TYPE} "
                f"with {screen_count} seeded screens."
            ),
            artefacts_produced=[spec_produced, prototype_produced],
            review_status="ready_for_review",
            execution_metrics={"seed": seed, "screen_count": screen_count},
        )

    def _render_spec(self, project_name, version_label, personas, journeys, screens, screen_entities, output_dir):
        doc = Document(str(REPO_ROOT / self.SPEC_TEMPLATE_RELATIVE_PATH))
        screen_lines = [
            f"{eid}: {name} — {desc}" for eid, (name, desc) in zip(screen_entities, screens, strict=True)
        ]
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{PERSONAS}}" in para.text:
                para.text = ""
                for persona in personas:
                    doc.add_paragraph(persona)
            elif "{{JOURNEYS}}" in para.text:
                para.text = ""
                for journey in journeys:
                    doc.add_paragraph(journey)
            elif "{{SCREEN_INVENTORY}}" in para.text:
                para.text = ""
                for line in screen_lines:
                    doc.add_paragraph(line)
            elif "{{NAVIGATION}}" in para.text:
                para.text = "Top-level navigation: " + " | ".join(name for name, _ in screens)
            elif "{{RESPONSIVE_BEHAVIOR}}" in para.text:
                para.text = (
                    "Layouts collapse to a single column below 768px; the Approvals Queue "
                    "prioritizes card view on mobile."
                )
            elif "{{ACCESSIBILITY}}" in para.text:
                para.text = (
                    "All interactive elements are keyboard-reachable; color contrast meets "
                    "WCAG AA; forms carry explicit labels."
                )
            elif "{{PROTOTYPE_REF}}" in para.text:
                para.text = para.text.replace("{{PROTOTYPE_REF}}", self.PROTOTYPE_ARTEFACT_TYPE)

        spec_dir = output_dir / self.SPEC_ARTEFACT_TYPE
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / f"{version_label}.docx"
        doc.save(spec_path)
        checksum = hashlib.sha256(spec_path.read_bytes()).hexdigest()

        return ProducedArtefact(
            artefact_type=self.SPEC_ARTEFACT_TYPE,
            stable_key=self.SPEC_ARTEFACT_TYPE,
            file_path=str(spec_path),
            checksum=checksum,
            entities=list(screen_entities),
        )

    def _render_prototype(self, project_name, version_label, screens, screen_entities, output_dir):
        template_text = (REPO_ROOT / self.PROTOTYPE_TEMPLATE_RELATIVE_PATH).read_text(encoding="utf-8")

        # project_name is user-supplied (Project.name via the API) and gets embedded into
        # an HTML file that may later be opened in a browser — escape it to avoid the
        # prototype becoming an XSS vector. Screen names/descriptions come from the fixed
        # SCREEN_POOL, not user input, so they don't need escaping today, but would if a
        # future runtime sources them from free text.
        safe_project_name = html.escape(str(project_name))

        nav_links = " ".join(
            f'<a href="#{eid}">{html.escape(name)}</a>'
            for eid, (name, _) in zip(screen_entities, screens, strict=True)
        )
        screens_html = "\n".join(
            f'<section class="screen" id="{eid}"><h2>{eid}: {html.escape(name)}</h2><p>{html.escape(desc)}</p></section>'
            for eid, (name, desc) in zip(screen_entities, screens, strict=True)
        )
        rendered = (
            template_text.replace("{{PROJECT_NAME}}", safe_project_name)
            .replace("{{VERSION_LABEL}}", version_label)
            .replace("{{NAVIGATION_LINKS}}", nav_links)
            .replace("{{SCREENS}}", screens_html)
        )

        prototype_dir = output_dir / self.PROTOTYPE_ARTEFACT_TYPE
        prototype_dir.mkdir(parents=True, exist_ok=True)
        prototype_path = prototype_dir / f"{version_label}.html"
        prototype_path.write_text(rendered, encoding="utf-8")
        checksum = hashlib.sha256(prototype_path.read_bytes()).hexdigest()

        return ProducedArtefact(
            artefact_type=self.PROTOTYPE_ARTEFACT_TYPE,
            stable_key=self.PROTOTYPE_ARTEFACT_TYPE,
            file_path=str(prototype_path),
            checksum=checksum,
            entities=list(screen_entities),
        )


class TechnicalDesignMockAdapter:
    """Deterministic mock runtime for the Technical Design Agent.

    Produces two artefacts per run: the Solution Approach Document and the
    Architecture Handbook — both Word, per the authoritative artefact set.
    """

    SOLUTION_APPROACH_ARTEFACT_TYPE = "solution_approach"
    ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE = "architecture_handbook"
    SOLUTION_APPROACH_TEMPLATE_RELATIVE_PATH = "04_Templates/solution_approach.docx"
    ARCHITECTURE_HANDBOOK_TEMPLATE_RELATIVE_PATH = "04_Templates/architecture_handbook.docx"

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
        solution_approach_produced = self._render_solution_approach(
            project_name, version_label, options, decisions, adr_entities, risks, output_dir
        )
        architecture_handbook_produced = self._render_architecture_handbook(
            project_name, version_label, output_dir
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

    def _render_solution_approach(
        self, project_name, version_label, options, decisions, adr_entities, risks, output_dir
    ):
        doc = Document(str(REPO_ROOT / self.SOLUTION_APPROACH_TEMPLATE_RELATIVE_PATH))
        decision_lines = [
            f"{eid}: {text}" for eid, text in zip(adr_entities, decisions, strict=True)
        ]
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{OPTION_ANALYSIS}}" in para.text:
                para.text = ""
                for name, tradeoff in options:
                    doc.add_paragraph(f"Option — {name}: {tradeoff}")
                doc.add_paragraph(f"Recommended: {options[0][0]}")
            elif "{{ARCHITECTURE_DECISIONS}}" in para.text:
                para.text = ""
                for line in decision_lines:
                    doc.add_paragraph(line)
            elif "{{RISKS}}" in para.text:
                para.text = ""
                for risk in risks:
                    doc.add_paragraph(risk)
            elif "{{LIMITATIONS}}" in para.text:
                para.text = ""
                for limitation in LIMITATION_POOL:
                    doc.add_paragraph(limitation)
            elif "{{DEPENDENCIES}}" in para.text:
                para.text = ""
                for dependency in DEPENDENCY_POOL:
                    doc.add_paragraph(dependency)

        output_path_dir = output_dir / self.SOLUTION_APPROACH_ARTEFACT_TYPE
        output_path_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_path_dir / f"{version_label}.docx"
        doc.save(output_path)
        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        return ProducedArtefact(
            artefact_type=self.SOLUTION_APPROACH_ARTEFACT_TYPE,
            stable_key=self.SOLUTION_APPROACH_ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=list(adr_entities),
        )

    def _render_architecture_handbook(self, project_name, version_label, output_dir):
        doc = Document(str(REPO_ROOT / self.ARCHITECTURE_HANDBOOK_TEMPLATE_RELATIVE_PATH))
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{LOGICAL_ARCHITECTURE}}" in para.text:
                para.text = (
                    "Power Platform canvas/model-driven app frontend, Dataverse as the system of "
                    "record, Power Automate for workflow orchestration."
                )
            elif "{{INTEGRATION_OVERVIEW}}" in para.text:
                para.text = (
                    "External systems are integrated via dedicated custom connectors; no direct "
                    "HTTP calls from flows to third-party APIs."
                )
            elif "{{INFRASTRUCTURE_OVERVIEW}}" in para.text:
                para.text = (
                    "Dev/test/prod Power Platform environments with solution-based ALM; Azure "
                    "services (if any) sit behind the same connector layer."
                )

        output_path_dir = output_dir / self.ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE
        output_path_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_path_dir / f"{version_label}.docx"
        doc.save(output_path)
        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        return ProducedArtefact(
            artefact_type=self.ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE,
            stable_key=self.ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=[],
        )


class DataIntegrationMockAdapter:
    """Deterministic mock runtime for the Data & Integration Agent.

    Fills 04_Templates/data_design_document.docx with a seeded Dataverse
    schema, relationships, external-source mapping, and connector design.
    """

    ARTEFACT_TYPE = "data_design_document"
    TEMPLATE_RELATIVE_PATH = "04_Templates/data_design_document.docx"

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

        doc = Document(str(REPO_ROOT / self.TEMPLATE_RELATIVE_PATH))
        entity_lines = [
            f"{eid}: {name} — {desc}" for eid, (name, desc) in zip(data_entities, entities_chosen, strict=True)
        ]
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{DATAVERSE_SCHEMA}}" in para.text:
                para.text = ""
                for line in entity_lines:
                    doc.add_paragraph(line)
            elif "{{RELATIONSHIPS}}" in para.text:
                para.text = ""
                for rel in relationships:
                    doc.add_paragraph(rel)
            elif "{{EXTERNAL_SOURCES}}" in para.text:
                para.text = ""
                for src in EXTERNAL_SOURCE_POOL:
                    doc.add_paragraph(src)
            elif "{{CONNECTORS}}" in para.text:
                para.text = ""
                for conn in CONNECTOR_POOL:
                    doc.add_paragraph(conn)
            elif "{{DATA_MIGRATION}}" in para.text:
                para.text = "No legacy data migration in scope for this mock run."
            elif "{{REPORTING_MODEL}}" in para.text:
                para.text = "Power BI reporting deferred until reporting requirements are confirmed."

        output_dir = settings.generated_artefacts_dir / request.project_id / self.ARTEFACT_TYPE
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{version_label}.docx"
        doc.save(output_path)
        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        produced = ProducedArtefact(
            artefact_type=self.ARTEFACT_TYPE,
            stable_key=self.ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=data_entities,
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

    ARTEFACT_TYPE = "governance_document"
    TEMPLATE_RELATIVE_PATH = "04_Templates/governance_document.docx"

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        settings = get_settings()
        seed = _deterministic_seed(
            request.project_id, request.lifecycle_phase or "governance_security", str(request.run_number)
        )
        version_label = _version_label(request.run_number)
        project_name = request.constraints.get("project_name", request.project_id)

        doc = Document(str(REPO_ROOT / self.TEMPLATE_RELATIVE_PATH))
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{IDENTITY_DESIGN}}" in para.text:
                para.text = "Microsoft Entra ID as the identity provider; delegated permissions by default."
            elif "{{PERMISSIONS}}" in para.text:
                para.text = "Least privilege: delegated Graph permissions unless an application-only flow is justified."
            elif "{{ENVIRONMENT_STRATEGY}}" in para.text:
                para.text = "Separate dev, test, and production Power Platform environments with solution-based ALM."
            elif "{{DLP}}" in para.text:
                para.text = ""
                for line in DLP_POOL:
                    doc.add_paragraph(line)
            elif "{{CONNECTOR_GOVERNANCE}}" in para.text:
                para.text = "Every connector introduced by an upstream artefact requires an explicit DLP classification here before use."
            elif "{{LICENSING}}" in para.text:
                para.text = ""
                for line in LICENSING_POOL:
                    doc.add_paragraph(line)
            elif "{{COMPLIANCE}}" in para.text:
                para.text = "No regulated data categories identified for this mock run; revisit if PII/PHI scope changes."
            elif "{{OPERATIONAL_OWNERSHIP}}" in para.text:
                para.text = "Platform Administrator role owns environment health; Project Owner owns business escalation."
            elif "{{AUDIT_REQUIREMENTS}}" in para.text:
                para.text = "All approval and rework events are captured in the RunEvent audit log; retained per organizational policy."

        output_dir = settings.generated_artefacts_dir / request.project_id / self.ARTEFACT_TYPE
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{version_label}.docx"
        doc.save(output_path)
        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        produced = ProducedArtefact(
            artefact_type=self.ARTEFACT_TYPE,
            stable_key=self.ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=[],
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

    BUILD_REVIEW_ARTEFACT_TYPE = "build_review_report"
    FINAL_CODE_REVIEW_ARTEFACT_TYPE = "final_code_review_report"
    BUILD_REVIEW_TEMPLATE_RELATIVE_PATH = "04_Templates/build_review_report.docx"
    FINAL_CODE_REVIEW_TEMPLATE_RELATIVE_PATH = "04_Templates/final_code_review_report.docx"

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
        build_review_produced = self._render_build_review(
            project_name, version_label, findings, defect_entities, output_dir
        )
        final_code_review_produced = self._render_final_code_review(
            project_name, version_label, defect_entities, output_dir
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

    def _render_build_review(self, project_name, version_label, findings, defect_entities, output_dir):
        doc = Document(str(REPO_ROOT / self.BUILD_REVIEW_TEMPLATE_RELATIVE_PATH))
        finding_lines = [f"{eid}: {text}" for eid, text in zip(defect_entities, findings, strict=True)]
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{IMPLEMENTATION_ASSETS}}" in para.text:
                para.text = "Canvas app screens, Dataverse solution, and Power Automate flows built per the approved design artefacts."
            elif "{{CONFIGURATION_SUMMARY}}" in para.text:
                para.text = "Environment variables and connection references configured per the Governance Document."
            elif "{{BUILD_FINDINGS}}" in para.text:
                para.text = ""
                for line in finding_lines:
                    doc.add_paragraph(line)
            elif "{{FIXES_APPLIED}}" in para.text:
                para.text = ""
                for eid in defect_entities:
                    doc.add_paragraph(f"{eid}: fixed and re-verified in this mock build run.")

        output_path_dir = output_dir / self.BUILD_REVIEW_ARTEFACT_TYPE
        output_path_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_path_dir / f"{version_label}.docx"
        doc.save(output_path)
        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        return ProducedArtefact(
            artefact_type=self.BUILD_REVIEW_ARTEFACT_TYPE,
            stable_key=self.BUILD_REVIEW_ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=list(defect_entities),
        )

    def _render_final_code_review(self, project_name, version_label, defect_entities, output_dir):
        doc = Document(str(REPO_ROOT / self.FINAL_CODE_REVIEW_TEMPLATE_RELATIVE_PATH))
        for para in doc.paragraphs:
            if "{{PROJECT_NAME}}" in para.text:
                para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
            elif "{{VERSION_LABEL}}" in para.text:
                para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
            elif "{{REVIEW_SCOPE}}" in para.text:
                para.text = "Full review of all implementation assets produced in this build cycle."
            elif "{{FINDINGS}}" in para.text:
                para.text = "No new findings beyond those already tracked in the Build Review Report."
            elif "{{RESOLUTION_STATUS}}" in para.text:
                para.text = ""
                for eid in defect_entities:
                    doc.add_paragraph(f"{eid}: resolved.")

        output_path_dir = output_dir / self.FINAL_CODE_REVIEW_ARTEFACT_TYPE
        output_path_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_path_dir / f"{version_label}.docx"
        doc.save(output_path)
        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        return ProducedArtefact(
            artefact_type=self.FINAL_CODE_REVIEW_ARTEFACT_TYPE,
            stable_key=self.FINAL_CODE_REVIEW_ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=list(defect_entities),
        )
