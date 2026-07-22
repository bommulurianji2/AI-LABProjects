from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ManifestInput(BaseModel):
    artefact_type: str
    required: bool = True


class ManifestOutput(BaseModel):
    artefact_type: str
    template: str  # path relative to repo root, e.g. "04_Templates/requirement_specification.docx"


class AgentManifest(BaseModel):
    """Schema for `03_Agent_Skills/<agent-id>/manifest.yaml`.

    Adding a new agent to the platform means adding a new manifest that
    validates against this schema — no core orchestration code changes.
    """

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str
    version: str
    kind: Literal["orchestrator", "specialist"]
    phase: str | None = None
    runtime: Literal["mock", "llm"] = "mock"
    requires_review: bool = True
    inputs: list[ManifestInput] = Field(default_factory=list)
    outputs: list[ManifestOutput] = Field(default_factory=list)
    skill_entry: str
    adapter: str  # "module.path:ClassName"

    @field_validator("phase")
    @classmethod
    def specialist_requires_phase(cls, v, info):
        kind = info.data.get("kind")
        if kind == "specialist" and not v:
            raise ValueError("specialist agents must declare a phase")
        if kind == "orchestrator" and v:
            raise ValueError("orchestrator must not declare a phase")
        return v

    @field_validator("adapter")
    @classmethod
    def adapter_must_be_module_colon_class(cls, v: str) -> str:
        if ":" not in v or not all(part.strip() for part in v.split(":", 1)):
            raise ValueError("adapter must be of the form 'module.path:ClassName'")
        return v
