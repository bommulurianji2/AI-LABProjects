from app.agents_registry.registry import AgentRegistry


def test_ux_design_agent_registers_from_real_skills_dir():
    reg = AgentRegistry()
    reg.load()  # real 03_Agent_Skills dir

    assert reg.failures == [], f"unexpected registration failures: {reg.failures}"
    entry = reg.get_agent("ux_design")
    assert entry is not None
    assert entry.manifest.phase == "ux_design"
    assert entry.manifest.kind == "specialist"
    assert {o.artefact_type for o in entry.manifest.outputs} == {
        "ux_design_specification",
        "ux_interactive_prototype",
    }
