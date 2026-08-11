"""Renders the Deploy Agent's IQ Document — shared by DeployMockAdapter
and DeployLlmAdapter so the two runtimes differ only in where the
deployment content comes from, not in how the template gets filled.
"""

import hashlib
from pathlib import Path

from docx import Document

from app.agents_registry.contract import ProducedArtefact

ARTEFACT_TYPE = "iq_document"
TEMPLATE_RELATIVE_PATH = "04_Templates/iq_document.docx"


def render(
    *,
    repo_root: Path,
    output_dir: Path,
    project_name: str,
    version_label: str,
    deployment_configuration_text: str,
    pre_deployment_verification_text: str,
    rollback_plan_text: str,
    deployment_evidence_text: str,
) -> ProducedArtefact:
    doc = Document(str(repo_root / TEMPLATE_RELATIVE_PATH))
    for para in doc.paragraphs:
        if "{{PROJECT_NAME}}" in para.text:
            para.text = para.text.replace("{{PROJECT_NAME}}", str(project_name))
        elif "{{VERSION_LABEL}}" in para.text:
            para.text = para.text.replace("{{VERSION_LABEL}}", version_label)
        elif "{{DEPLOYMENT_CONFIGURATION}}" in para.text:
            para.text = deployment_configuration_text
        elif "{{PRE_DEPLOYMENT_VERIFICATION}}" in para.text:
            para.text = pre_deployment_verification_text
        elif "{{ROLLBACK_PLAN}}" in para.text:
            para.text = rollback_plan_text
        elif "{{DEPLOYMENT_EVIDENCE}}" in para.text:
            para.text = deployment_evidence_text

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
