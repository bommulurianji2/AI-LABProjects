from app.agents_registry.registry import AgentRegistry


def test_build_agent_registers_from_real_skills_dir():
    reg = AgentRegistry()
    reg.load()

    assert reg.failures == [], f"unexpected registration failures: {reg.failures}"
    entry = reg.get_agent("build")
    assert entry is not None
    assert entry.manifest.phase == "build"
    assert {o.artefact_type for o in entry.manifest.outputs} == {
        "build_review_report",
        "final_code_review_report",
    }
