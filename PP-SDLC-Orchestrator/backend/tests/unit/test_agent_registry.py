import yaml

from app.agents_registry.registry import AgentRegistry

VALID_ADAPTER = "tests.fixtures.dummy_adapter:DummyAdapter"
NO_EXECUTE_ADAPTER = "tests.fixtures.dummy_adapter:AdapterWithoutExecute"


def _write_manifest(agent_dir, manifest: dict) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")


def _base_manifest(tmp_path, **overrides) -> dict:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("stub skill instructions", encoding="utf-8")
    manifest = {
        "id": "sample_agent",
        "display_name": "Sample Agent",
        "version": "0.1.0",
        "kind": "specialist",
        "phase": "analysis",
        "runtime": "mock",
        "requires_review": True,
        "inputs": [],
        "outputs": [],
        "skill_entry": str(skill_path),
        "adapter": VALID_ADAPTER,
    }
    manifest.update(overrides)
    return manifest


def test_valid_manifest_is_registered(tmp_path):
    skills_dir = tmp_path / "skills"
    _write_manifest(skills_dir / "sample_agent", _base_manifest(tmp_path))

    reg = AgentRegistry()
    reg.load(skills_dir)

    assert reg.get_agent("sample_agent") is not None
    assert [m.id for m in reg.list_agents()] == ["sample_agent"]
    assert reg.failures == []


def test_folder_without_manifest_is_silently_skipped(tmp_path):
    skills_dir = tmp_path / "skills"
    (skills_dir / "not_yet_implemented").mkdir(parents=True)

    reg = AgentRegistry()
    reg.load(skills_dir)

    assert reg.list_agents() == []
    assert reg.failures == []


def test_invalid_schema_is_excluded_not_fatal(tmp_path):
    skills_dir = tmp_path / "skills"
    # kind is not one of the allowed literals -> Pydantic ValidationError
    _write_manifest(skills_dir / "broken", _base_manifest(tmp_path, kind="not_a_real_kind"))

    reg = AgentRegistry()
    reg.load(skills_dir)  # must not raise

    assert reg.list_agents() == []
    assert len(reg.failures) == 1
    assert "invalid manifest" in reg.failures[0].reason


def test_specialist_without_phase_is_rejected(tmp_path):
    skills_dir = tmp_path / "skills"
    _write_manifest(skills_dir / "broken", _base_manifest(tmp_path, phase=None))

    reg = AgentRegistry()
    reg.load(skills_dir)

    assert reg.list_agents() == []
    assert len(reg.failures) == 1


def test_missing_adapter_module_is_excluded_not_fatal(tmp_path):
    skills_dir = tmp_path / "skills"
    _write_manifest(
        skills_dir / "sample_agent",
        _base_manifest(tmp_path, adapter="nonexistent.module.path:Foo"),
    )

    reg = AgentRegistry()
    reg.load(skills_dir)  # must not raise

    assert reg.list_agents() == []
    assert len(reg.failures) == 1
    assert "adapter import failed" in reg.failures[0].reason


def test_adapter_missing_execute_method_is_excluded(tmp_path):
    skills_dir = tmp_path / "skills"
    _write_manifest(
        skills_dir / "sample_agent",
        _base_manifest(tmp_path, adapter=NO_EXECUTE_ADAPTER),
    )

    reg = AgentRegistry()
    reg.load(skills_dir)

    assert reg.list_agents() == []
    assert len(reg.failures) == 1
    assert "no execute()" in reg.failures[0].reason


def test_missing_skill_entry_file_is_excluded(tmp_path):
    skills_dir = tmp_path / "skills"
    manifest = _base_manifest(tmp_path)
    manifest["skill_entry"] = str(tmp_path / "does_not_exist.md")
    _write_manifest(skills_dir / "sample_agent", manifest)

    reg = AgentRegistry()
    reg.load(skills_dir)

    assert reg.list_agents() == []
    assert "skill_entry not found" in reg.failures[0].reason


def test_missing_template_file_is_excluded(tmp_path):
    skills_dir = tmp_path / "skills"
    manifest = _base_manifest(
        tmp_path,
        outputs=[{"artefact_type": "spec", "template": str(tmp_path / "missing.docx")}],
    )
    _write_manifest(skills_dir / "sample_agent", manifest)

    reg = AgentRegistry()
    reg.load(skills_dir)

    assert reg.list_agents() == []
    assert "template not found" in reg.failures[0].reason


def test_missing_skills_dir_does_not_raise(tmp_path):
    reg = AgentRegistry()
    reg.load(tmp_path / "does_not_exist_at_all")
    assert reg.list_agents() == []
