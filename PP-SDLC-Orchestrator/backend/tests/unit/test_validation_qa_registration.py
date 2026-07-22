from app.agents_registry.registry import AgentRegistry


def test_validation_qa_agent_registers_from_real_skills_dir():
    reg = AgentRegistry()
    reg.load()

    assert reg.failures == [], f"unexpected registration failures: {reg.failures}"
    entry = reg.get_agent("validation_qa")
    assert entry is not None
    assert entry.manifest.phase == "validation_qa"
    assert {o.artefact_type for o in entry.manifest.outputs} == {"validation_report"}
