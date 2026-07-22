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
