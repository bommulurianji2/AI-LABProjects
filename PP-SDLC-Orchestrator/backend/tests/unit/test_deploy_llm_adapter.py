import json

import pytest
from docx import Document

from app.adapters.llm_agent_adapter import DeployLlmAdapter, DeploymentBlockedError
from app.adapters.model_providers.base import ModelProviderError
from app.agents_registry.contract import AgentRunRequest
from tests.fixtures.fake_model_provider import FakeModelProvider

_CLEAR_RESPONSE = {
    "defects_clear": True,
    "open_defect_summary": "",
    "deployment_configuration": "Solution deployed via Power Platform CLI import into the target environment.",
    "pre_deployment_verification": (
        "Verified: the Test Workbook's Defects sheet shows zero open defects for this version."
    ),
    "rollback_plan": "Prior solution version remains installed and can be re-activated.",
    "deployment_evidence": "Deployment evidence is attached per the organization's retention policy.",
}

_BLOCKED_RESPONSE = {
    "defects_clear": False,
    "open_defect_summary": "DEF-002 (TC-004) is Open — booking conflict flow still allows overlap.",
    "deployment_configuration": "",
    "pre_deployment_verification": "",
    "rollback_plan": "",
    "deployment_evidence": "",
}


def _make_request(**overrides) -> AgentRunRequest:
    defaults = dict(
        execution_mode="orchestrated",
        project_id="proj-1",
        invocation_id="inv-1",
        agent_id="deploy",
        task_id="task-1",
        task_request="Deploy the booking portal",
        lifecycle_phase="deploy",
        constraints={"project_name": "Facilities Booking Portal"},
        run_number=1,
        upstream_artefacts_text={
            "test_workbook": "[Defects]\nDefect ID | Related Test | Description | Status",
        },
    )
    defaults.update(overrides)
    return AgentRunRequest(**defaults)


def test_execute_renders_artefact_when_defects_clear():
    adapter = DeployLlmAdapter(provider=FakeModelProvider(json.dumps(_CLEAR_RESPONSE)))

    result = adapter.execute(_make_request())

    assert len(result.artefacts_produced) == 1
    produced = result.artefacts_produced[0]
    assert produced.artefact_type == "iq_document"
    assert produced.entities == []

    doc = Document(produced.file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Facilities Booking Portal" in full_text
    assert "zero open defects" in full_text


def test_execute_raises_deployment_blocked_when_defects_not_clear():
    adapter = DeployLlmAdapter(provider=FakeModelProvider(json.dumps(_BLOCKED_RESPONSE)))

    with pytest.raises(DeploymentBlockedError, match="DEF-002"):
        adapter.execute(_make_request())


def test_deployment_blocked_error_is_a_model_provider_error():
    assert issubclass(DeploymentBlockedError, ModelProviderError)


def test_upstream_test_workbook_text_is_included_in_prompt():
    provider = FakeModelProvider(json.dumps(_CLEAR_RESPONSE))
    adapter = DeployLlmAdapter(provider=provider)

    adapter.execute(_make_request())

    call = provider.calls[0]
    assert "Deploy Agent" in call["system"]
    assert "[Defects]" in call["user"]


def test_no_upstream_text_omits_context_gracefully():
    provider = FakeModelProvider(json.dumps(_CLEAR_RESPONSE))
    adapter = DeployLlmAdapter(provider=provider)

    adapter.execute(_make_request(upstream_artefacts_text={}))

    assert "Approved" not in provider.calls[0]["user"]


def test_missing_defect_summary_falls_back_to_generic_message():
    response = dict(_BLOCKED_RESPONSE)
    response["open_defect_summary"] = ""
    adapter = DeployLlmAdapter(provider=FakeModelProvider(json.dumps(response)))

    with pytest.raises(DeploymentBlockedError, match="unspecified open defects"):
        adapter.execute(_make_request())


def test_malformed_json_raises_model_provider_error():
    adapter = DeployLlmAdapter(provider=FakeModelProvider("not json"))

    with pytest.raises(ModelProviderError):
        adapter.execute(_make_request())
