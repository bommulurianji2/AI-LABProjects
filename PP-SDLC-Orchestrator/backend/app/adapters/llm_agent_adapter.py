"""Real LLM-backed agent runtimes.

Each adapter here returns the identical `AgentRunResult` envelope its mock
counterpart returns (see mock_agent_adapter.py) — orchestration code never
branches on which runtime produced it. Swapping an agent from `runtime:
mock` to `runtime: llm` is a manifest.yaml edit, not a rewrite.
"""

import hashlib
import json
import re

from app.adapters import common, requirement_specification_renderer, ux_design_renderer
from app.adapters.model_providers import factory as model_provider_factory
from app.adapters.model_providers.base import ModelProvider, ModelProviderError
from app.agents_registry.contract import AgentRunRequest, AgentRunResult, ProducedArtefact
from app.config import REPO_ROOT, get_settings

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
# Belt-and-suspenders for models that ignore the "don't add your own
# numbering" instruction (e.g. "REQ-001:", "SCR-1.", "ADR_2:", "1)", "1.").
# Generic across every stable-ID prefix used anywhere in the system (REQ,
# SCR, ADR, DATA, DEF, TC, ...) — not just REQ — so it never needs revisiting
# each time a new LLM adapter for a different agent is added.
_LEADING_ID_PREFIX_RE = re.compile(r"^\s*(?:[A-Za-z]{2,6}[-_]?\d+|\d+)[\.:\)]\s*")


def _extract_json(text: str) -> dict:
    """Models frequently wrap JSON in ```json fences despite instructions
    not to — strip that before parsing rather than failing on it.
    """
    text = text.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ModelProviderError(f"Model did not return valid JSON: {text[:500]!r}") from exc


def _strip_leading_id_prefix(text: str) -> str:
    return _LEADING_ID_PREFIX_RE.sub("", text).strip()


class AnalysisLlmAdapter:
    """Real LLM-backed runtime for the Analysis Agent.

    Accepts an optional injected `provider` for unit testing; when omitted
    (the normal registry-driven path — see AgentRegistry, which always
    constructs adapters with no arguments), it resolves the configured
    provider fresh from settings on every call, so it always reflects
    whatever is currently in backend/.env.
    """

    ARTEFACT_TYPE = "requirement_specification"
    SKILL_RELATIVE_PATH = "03_Agent_Skills/analysis/SKILL.md"
    MIN_REQUIREMENTS = 3
    MAX_REQUIREMENTS = 8

    def __init__(self, provider: ModelProvider | None = None):
        self._provider = provider

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        provider = self._provider or model_provider_factory.get_model_provider()
        settings = get_settings()
        project_name = request.constraints.get("project_name", request.project_id)

        system_prompt = (REPO_ROOT / self.SKILL_RELATIVE_PATH).read_text(encoding="utf-8")
        user_prompt = self._build_user_prompt(project_name=str(project_name), task_request=request.task_request)

        raw_response = provider.complete(system=system_prompt, user=user_prompt)
        parsed = _extract_json(raw_response)

        scope_text = str(parsed.get("scope", "")).strip() or "Scope not specified by the model."
        requirements = [
            _strip_leading_id_prefix(str(r)) for r in parsed.get("functional_requirements", []) if str(r).strip()
        ]
        requirements = [r for r in requirements if r]
        if not requirements:
            raise ModelProviderError("Model response contained no functional requirements.")
        assumptions = [str(a).strip() for a in parsed.get("assumptions", []) if str(a).strip()]
        assumptions_text = "\n".join(assumptions) if assumptions else "No assumptions provided by the model."

        entities = [f"REQ-{i + 1:03d}" for i in range(len(requirements))]
        requirement_lines = [f"{eid}: {text}" for eid, text in zip(entities, requirements, strict=True)]
        version_label = common.version_label(request.run_number)

        output_path = (
            settings.generated_artefacts_dir / request.project_id / self.ARTEFACT_TYPE / f"{version_label}.docx"
        )
        requirement_specification_renderer.render(
            repo_root=REPO_ROOT,
            output_path=output_path,
            project_name=str(project_name),
            version_label=version_label,
            scope_text=scope_text,
            requirement_lines=requirement_lines,
            assumptions_text=assumptions_text,
        )

        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        produced = ProducedArtefact(
            artefact_type=self.ARTEFACT_TYPE,
            stable_key=self.ARTEFACT_TYPE,
            file_path=str(output_path),
            checksum=checksum,
            entities=entities,
        )

        return AgentRunResult(
            execution_summary=f"Generated {self.ARTEFACT_TYPE} with {len(requirements)} LLM-generated requirements.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"requirement_count": len(requirements)},
        )

    def _build_user_prompt(self, *, project_name: str, task_request: str) -> str:
        return (
            f"Project name: {project_name}\n\n"
            "High-level requirement from the user:\n"
            f'"""\n{task_request}\n"""\n\n'
            "Respond with ONLY a JSON object (no markdown code fences, no commentary before or after) "
            "with exactly these keys:\n"
            "{\n"
            '  "scope": "<1-3 sentence summary of what is in scope>",\n'
            '  "functional_requirements": ["<requirement 1>", "<requirement 2>", "..."],\n'
            '  "assumptions": ["<assumption 1>", "..."]\n'
            "}\n\n"
            f"Produce between {self.MIN_REQUIREMENTS} and {self.MAX_REQUIREMENTS} functional requirements. "
            'Each must be a single, clear, testable sentence starting with "The system shall". '
            "Do not add your own numbering, IDs, or labels (e.g. no \"REQ-1:\" or \"1.\" prefixes) — the "
            "calling system assigns stable IDs itself; just provide the plain sentence."
        )


class UxDesignLlmAdapter:
    """Real LLM-backed runtime for the UX Design Agent.

    Reads the upstream Requirement Specification's actual text (see
    OrchestratorService._gather_upstream_artefacts_text) so screens and
    journeys are grounded in what Analysis actually decided, not just the
    original one-line task request repeated at every phase.
    """

    SKILL_RELATIVE_PATH = "03_Agent_Skills/ux_design/SKILL.md"
    MIN_SCREENS = 3
    MAX_SCREENS = 6

    def __init__(self, provider: ModelProvider | None = None):
        self._provider = provider

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        provider = self._provider or model_provider_factory.get_model_provider()
        settings = get_settings()
        project_name = request.constraints.get("project_name", request.project_id)

        system_prompt = (REPO_ROOT / self.SKILL_RELATIVE_PATH).read_text(encoding="utf-8")
        requirement_spec_text = request.upstream_artefacts_text.get("requirement_specification", "")
        user_prompt = self._build_user_prompt(
            project_name=str(project_name),
            task_request=request.task_request,
            requirement_spec_text=requirement_spec_text,
        )

        raw_response = provider.complete(system=system_prompt, user=user_prompt)
        parsed = _extract_json(raw_response)

        personas = [str(p).strip() for p in parsed.get("personas", []) if str(p).strip()]
        journeys = [str(j).strip() for j in parsed.get("journeys", []) if str(j).strip()]
        raw_screens = parsed.get("screens", [])
        screens: list[tuple[str, str]] = []
        for entry in raw_screens:
            if not isinstance(entry, dict):
                continue
            name = _strip_leading_id_prefix(str(entry.get("name", ""))).strip()
            description = str(entry.get("description", "")).strip()
            if name and description:
                screens.append((name, description))

        if not personas or not journeys or not screens:
            raise ModelProviderError(
                "Model response missing required personas, journeys, or screens: " f"{parsed!r}"[:500]
            )

        screen_entities = [f"SCR-{i + 1:03d}" for i in range(len(screens))]
        version_label = common.version_label(request.run_number)
        output_dir = settings.generated_artefacts_dir / request.project_id

        responsive_behavior_text = str(parsed.get("responsive_behavior", "")).strip() or (
            "Responsive behavior not specified by the model."
        )
        accessibility_text = str(parsed.get("accessibility", "")).strip() or (
            "Accessibility considerations not specified by the model."
        )

        spec_produced = ux_design_renderer.render_spec(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            personas=personas,
            journeys=journeys,
            screens=screens,
            screen_entities=screen_entities,
            responsive_behavior_text=responsive_behavior_text,
            accessibility_text=accessibility_text,
        )
        prototype_produced = ux_design_renderer.render_prototype(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            screens=screens,
            screen_entities=screen_entities,
        )

        return AgentRunResult(
            execution_summary=(
                f"Generated {ux_design_renderer.SPEC_ARTEFACT_TYPE} and "
                f"{ux_design_renderer.PROTOTYPE_ARTEFACT_TYPE} with {len(screens)} LLM-generated screens."
            ),
            artefacts_produced=[spec_produced, prototype_produced],
            review_status="ready_for_review",
            execution_metrics={"screen_count": len(screens)},
        )

    def _build_user_prompt(self, *, project_name: str, task_request: str, requirement_spec_text: str) -> str:
        context_section = (
            f'Approved Requirement Specification for this project:\n"""\n{requirement_spec_text}\n"""\n\n'
            if requirement_spec_text
            else ""
        )
        return (
            f"Project name: {project_name}\n\n"
            f"Original high-level requirement from the user:\n\"\"\"\n{task_request}\n\"\"\"\n\n"
            f"{context_section}"
            "Design the UX for this project, grounded in the requirements above. "
            "Respond with ONLY a JSON object (no markdown code fences, no commentary before or after) "
            "with exactly these keys:\n"
            "{\n"
            '  "personas": ["<persona 1 - name and a short description>", "..."],\n'
            '  "journeys": ["<end-to-end user journey 1>", "..."],\n'
            '  "screens": [{"name": "<Screen Name>", "description": "<what it does>"}, "..."],\n'
            '  "navigation": "<1-2 sentence description of top-level navigation>",\n'
            '  "responsive_behavior": "<1-2 sentences on how the layout adapts to mobile>",\n'
            '  "accessibility": "<1-2 sentences on accessibility considerations>"\n'
            "}\n\n"
            f"Produce at least 2 personas, at least 2 journeys, and between {self.MIN_SCREENS} and "
            f"{self.MAX_SCREENS} screens. Do not add your own numbering or IDs to screen names — the "
            "calling system assigns stable IDs itself."
        )
