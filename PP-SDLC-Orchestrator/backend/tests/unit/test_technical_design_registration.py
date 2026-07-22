from app.agents_registry.registry import AgentRegistry


def test_technical_design_agent_registers_from_real_skills_dir():
    reg = AgentRegistry()
    reg.load()  # real 03_Agent_Skills dir

    assert reg.failures == [], f"unexpected registration failures: {reg.failures}"
    entry = reg.get_agent("technical_design")
    assert entry is not None
    assert entry.manifest.phase == "technical_design"
    assert entry.manifest.kind == "specialist"
    assert {o.artefact_type for o in entry.manifest.outputs} == {
        "solution_approach",
        "architecture_handbook",
    }
