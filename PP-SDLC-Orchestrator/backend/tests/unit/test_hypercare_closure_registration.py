from app.agents_registry.registry import AgentRegistry


def test_hypercare_closure_agent_registers_from_real_skills_dir():
    reg = AgentRegistry()
    reg.load()

    assert reg.failures == [], f"unexpected registration failures: {reg.failures}"
    entry = reg.get_agent("hypercare_closure")
    assert entry is not None
    assert entry.manifest.phase == "hypercare_closure"
    assert {o.artefact_type for o in entry.manifest.outputs} == {"hypercare_closure_report"}
