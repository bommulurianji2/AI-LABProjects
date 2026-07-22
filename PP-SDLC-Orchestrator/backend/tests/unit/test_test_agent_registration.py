from app.agents_registry.registry import AgentRegistry


def test_test_agent_registers_from_real_skills_dir():
    reg = AgentRegistry()
    reg.load()

    assert reg.failures == [], f"unexpected registration failures: {reg.failures}"
    entry = reg.get_agent("test")
    assert entry is not None
    assert entry.manifest.phase == "test"
    assert {o.artefact_type for o in entry.manifest.outputs} == {"test_workbook"}
