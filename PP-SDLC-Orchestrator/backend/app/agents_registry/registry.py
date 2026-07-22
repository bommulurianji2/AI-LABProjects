"""Startup-time agent discovery and validation.

Scans `03_Agent_Skills/*/manifest.yaml`, validates each against
`AgentManifest`, checks its adapter module/class and template files exist,
and builds an in-memory registry. A manifest that fails any check is
excluded with a logged reason instead of crashing boot — this is the
mechanism referenced throughout the spec as "add an agent without changing
core code."
"""

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.agents_registry.manifest_schema import AgentManifest
from app.config import REPO_ROOT, get_settings

logger = logging.getLogger(__name__)


@dataclass
class RegistryEntry:
    manifest: AgentManifest
    adapter_class: type


@dataclass
class RegistrationFailure:
    agent_dir: str
    reason: str


@dataclass
class AgentRegistry:
    _entries: dict[str, RegistryEntry] = field(default_factory=dict)
    _failures: list[RegistrationFailure] = field(default_factory=list)

    def load(self, skills_dir: Path | None = None) -> None:
        skills_dir = skills_dir or get_settings().agent_skills_dir
        self._entries = {}
        self._failures = []

        if not skills_dir.exists():
            logger.warning("Agent skills directory does not exist: %s", skills_dir)
            return

        for agent_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            manifest_path = agent_dir / "manifest.yaml"
            if not manifest_path.exists():
                continue  # stub folder for a not-yet-implemented agent - not a failure
            self._load_one(agent_dir, manifest_path)

    def _load_one(self, agent_dir: Path, manifest_path: Path) -> None:
        try:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest = AgentManifest.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            self._fail(agent_dir, f"invalid manifest: {exc}")
            return

        skill_path = REPO_ROOT / manifest.skill_entry
        if not skill_path.exists():
            self._fail(agent_dir, f"skill_entry not found: {manifest.skill_entry}")
            return

        for output in manifest.outputs:
            template_path = REPO_ROOT / output.template
            if not template_path.exists():
                self._fail(agent_dir, f"template not found: {output.template}")
                return

        module_path, class_name = manifest.adapter.split(":", 1)
        try:
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            self._fail(agent_dir, f"adapter import failed: {exc}")
            return

        if not hasattr(adapter_class, "execute"):
            self._fail(agent_dir, f"adapter {manifest.adapter} has no execute() method")
            return

        self._entries[manifest.id] = RegistryEntry(manifest=manifest, adapter_class=adapter_class)

    def _fail(self, agent_dir: Path, reason: str) -> None:
        logger.warning("Excluding agent at %s: %s", agent_dir, reason)
        self._failures.append(RegistrationFailure(agent_dir=str(agent_dir), reason=reason))

    def list_agents(self) -> list[AgentManifest]:
        return [e.manifest for e in self._entries.values()]

    def get_agent(self, agent_id: str) -> RegistryEntry | None:
        return self._entries.get(agent_id)

    @property
    def failures(self) -> list[RegistrationFailure]:
        return list(self._failures)


registry = AgentRegistry()
