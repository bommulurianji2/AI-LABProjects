"""Deterministic mock runtimes for specialist agents.

Each adapter here returns the same `AgentRunResult` envelope shape a future
`runtime: llm` adapter would return from a real model call — orchestration
code never branches on which produced it.
"""

import hashlib

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


def _deterministic_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


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

        version_label = "v0.1" if request.run_number == 1 else f"v0.{request.run_number}"
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
