"""Renders the Test Agent's Test Workbook — shared by TestAgentMockAdapter
and TestAgentLlmAdapter so the two runtimes differ only in where test
case/defect content comes from, not in how the workbook gets filled.
"""

import hashlib
from pathlib import Path

from openpyxl import load_workbook

from app.agents_registry.contract import ProducedArtefact

ARTEFACT_TYPE = "test_workbook"
TEMPLATE_RELATIVE_PATH = "04_Templates/test_workbook.xlsx"


def render(
    *,
    repo_root: Path,
    output_dir: Path,
    version_label: str,
    cases: list[tuple[str, str, str]],
    case_entities: list[str],
    case_statuses: list[str],
    defects: list[tuple[str, str, str, str]],
) -> ProducedArtefact:
    wb = load_workbook(str(repo_root / TEMPLATE_RELATIVE_PATH))
    cases_ws = wb["Test Cases"]
    for eid, (test_type, description, related_entity), status in zip(
        case_entities, cases, case_statuses, strict=True
    ):
        cases_ws.append([eid, test_type, description, related_entity, status])

    if defects:
        defects_ws = wb["Defects"]
        for defect_id, related_test, description, status in defects:
            defects_ws.append([defect_id, related_test, description, status])

    output_path_dir = output_dir / ARTEFACT_TYPE
    output_path_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_path_dir / f"{version_label}.xlsx"
    wb.save(output_path)
    checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

    return ProducedArtefact(
        artefact_type=ARTEFACT_TYPE,
        stable_key=ARTEFACT_TYPE,
        file_path=str(output_path),
        checksum=checksum,
        entities=list(case_entities),
    )
