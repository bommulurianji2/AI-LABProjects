"""Renders the Hypercare & Closure Agent's Hypercare & Closure Report —
shared by HypercareClosureMockAdapter and HypercareClosureLlmAdapter so
the two runtimes differ only in where the closure content comes from, not
in how the template gets filled.
"""

import hashlib
from pathlib import Path

from docx import Document

from app.agents_registry.contract import ProducedArtefact

ARTEFACT_TYPE = "hypercare_closure_report"
TEMPLATE_RELATIVE_PATH = "04_Templates/hypercare_closure_report.docx"


def render(
    *,
    repo_root: Path,
    output_dir: Path,
    project_name: str,
    version_label: str,
    hypercare_plan_text: str,
    issue_resolution_text: str,
    handover_text: str,
    lessons_learned_text: str,
    closure_statement_text: str,
) -> ProducedArtefact:
    doc = Document(str(repo_root / TEMPLATE_RELATIVE_PATH))
    for para in doc.paragraphs:
        if "{{PROJECT_NAME}}" in para.text:
            para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
        elif "{{VERSION_LABEL}}" in para.text:
            para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
        elif "{{HYPERCARE_PLAN}}" in para.text:
            para.text = hypercare_plan_text
        elif "{{ISSUE_RESOLUTION}}" in para.text:
            para.text = issue_resolution_text
        elif "{{HANDOVER}}" in para.text:
            para.text = handover_text
        elif "{{LESSONS_LEARNED}}" in para.text:
            para.text = lessons_learned_text
        elif "{{CLOSURE_STATEMENT}}" in para.text:
            para.text = closure_statement_text

    output_path_dir = output_dir / ARTEFACT_TYPE
    output_path_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_path_dir / f"{version_label}.docx"
    doc.save(output_path)
    checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

    return ProducedArtefact(
        artefact_type=ARTEFACT_TYPE,
        stable_key=ARTEFACT_TYPE,
        file_path=str(output_path),
        checksum=checksum,
        entities=[],
    )
