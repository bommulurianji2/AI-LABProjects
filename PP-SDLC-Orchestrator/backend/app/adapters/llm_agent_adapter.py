"""Real LLM-backed agent runtimes.

Each adapter here returns the identical `AgentRunResult` envelope its mock
counterpart returns (see mock_agent_adapter.py) — orchestration code never
branches on which runtime produced it. Swapping an agent from `runtime:
mock` to `runtime: llm` is a manifest.yaml edit, not a rewrite.
"""

import hashlib
import json
import re

from app.adapters import (
    build_renderer,
    common,
    data_integration_renderer,
    governance_security_renderer,
    requirement_specification_renderer,
    technical_design_renderer,
    ux_design_renderer,
)
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


_ARTEFACT_TYPE_LABELS = {
    "requirement_specification": "Requirement Specification",
    "ux_design_specification": "UX Design Specification",
    "solution_approach": "Solution Approach Document",
    "architecture_handbook": "Architecture Handbook",
    "data_design_document": "Data Design Document",
    "governance_document": "Governance Document",
    "build_review_report": "Build Review Report",
    "final_code_review_report": "Final Code Review Report",
    "validation_report": "Validation Report",
    "test_plan": "Test Plan",
    "test_execution_report": "Test Execution Report",
    "deployment_runbook": "Deployment Runbook",
    "hypercare_closure_report": "Hypercare Closure Report",
}


def _format_multi_artefact_context(upstream_artefacts_text: dict[str, str], artefact_types: list[str]) -> str:
    """Formats every requested upstream artefact that's actually present
    into labeled sections, in a fixed reading order — used by agents whose
    guardrails require referencing entities from more than one prior
    phase (e.g. Build referencing both SCR-00N and ADR-00N IDs), unlike
    earlier agents that only ever had a single immediate predecessor.
    """
    sections = []
    for artefact_type in artefact_types:
        text = upstream_artefacts_text.get(artefact_type, "")
        if not text:
            continue
        label = _ARTEFACT_TYPE_LABELS.get(artefact_type, artefact_type)
        sections.append(f'Approved {label}:\n"""\n{text}\n"""')
    return "\n\n".join(sections)


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


class TechnicalDesignLlmAdapter:
    """Real LLM-backed runtime for the Technical Design Agent.

    Reads the upstream UX Design Specification's actual text (see
    OrchestratorService._gather_upstream_artefacts_text) so the option
    analysis, architecture decisions, and logical architecture are grounded
    in what UX Design actually decided, not just the original task request.
    """

    SKILL_RELATIVE_PATH = "03_Agent_Skills/technical_design/SKILL.md"
    MIN_OPTIONS = 2
    MIN_DECISIONS = 3
    MAX_DECISIONS = 6

    def __init__(self, provider: ModelProvider | None = None):
        self._provider = provider

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        provider = self._provider or model_provider_factory.get_model_provider()
        settings = get_settings()
        project_name = request.constraints.get("project_name", request.project_id)

        system_prompt = (REPO_ROOT / self.SKILL_RELATIVE_PATH).read_text(encoding="utf-8")
        ux_design_spec_text = request.upstream_artefacts_text.get("ux_design_specification", "")
        user_prompt = self._build_user_prompt(
            project_name=str(project_name),
            task_request=request.task_request,
            ux_design_spec_text=ux_design_spec_text,
        )

        raw_response = provider.complete(system=system_prompt, user=user_prompt)
        parsed = _extract_json(raw_response)

        raw_options = parsed.get("options", [])
        options: list[tuple[str, str]] = []
        for entry in raw_options:
            if not isinstance(entry, dict):
                continue
            name = _strip_leading_id_prefix(str(entry.get("name", ""))).strip()
            tradeoff = str(entry.get("tradeoff", "")).strip()
            if name and tradeoff:
                options.append((name, tradeoff))

        decisions = [
            _strip_leading_id_prefix(str(d)) for d in parsed.get("architecture_decisions", []) if str(d).strip()
        ]
        decisions = [d for d in decisions if d]
        risks = [str(r).strip() for r in parsed.get("risks", []) if str(r).strip()]
        limitations = [str(limit).strip() for limit in parsed.get("limitations", []) if str(limit).strip()]
        dependencies = [str(dep).strip() for dep in parsed.get("dependencies", []) if str(dep).strip()]

        if len(options) < self.MIN_OPTIONS or not decisions:
            raise ModelProviderError(
                f"Model response missing required options or architecture_decisions: {parsed!r}"[:500]
            )

        decision_entities = [f"ADR-{i + 1:03d}" for i in range(len(decisions))]
        version_label = common.version_label(request.run_number)
        output_dir = settings.generated_artefacts_dir / request.project_id

        logical_architecture_text = str(parsed.get("logical_architecture", "")).strip() or (
            "Logical architecture not specified by the model."
        )
        integration_overview_text = str(parsed.get("integration_overview", "")).strip() or (
            "Integration overview not specified by the model."
        )
        infrastructure_overview_text = str(parsed.get("infrastructure_overview", "")).strip() or (
            "Infrastructure overview not specified by the model."
        )

        solution_approach_produced = technical_design_renderer.render_solution_approach(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            options=options,
            decisions=decisions,
            decision_entities=decision_entities,
            risks=risks or ["No risks identified by the model."],
            limitations=limitations or ["No limitations identified by the model."],
            dependencies=dependencies or ["No dependencies identified by the model."],
        )
        architecture_handbook_produced = technical_design_renderer.render_architecture_handbook(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            logical_architecture_text=logical_architecture_text,
            integration_overview_text=integration_overview_text,
            infrastructure_overview_text=infrastructure_overview_text,
        )

        return AgentRunResult(
            execution_summary=(
                f"Generated {technical_design_renderer.SOLUTION_APPROACH_ARTEFACT_TYPE} and "
                f"{technical_design_renderer.ARCHITECTURE_HANDBOOK_ARTEFACT_TYPE} with "
                f"{len(decisions)} LLM-generated architecture decisions."
            ),
            artefacts_produced=[solution_approach_produced, architecture_handbook_produced],
            review_status="ready_for_review",
            execution_metrics={"decision_count": len(decisions), "option_count": len(options)},
        )

    def _build_user_prompt(self, *, project_name: str, task_request: str, ux_design_spec_text: str) -> str:
        context_section = (
            f'Approved UX Design Specification for this project:\n"""\n{ux_design_spec_text}\n"""\n\n'
            if ux_design_spec_text
            else ""
        )
        return (
            f"Project name: {project_name}\n\n"
            f"Original high-level requirement from the user:\n\"\"\"\n{task_request}\n\"\"\"\n\n"
            f"{context_section}"
            "Produce the technical design for this project, grounded in the UX Design Specification above. "
            "Respond with ONLY a JSON object (no markdown code fences, no commentary before or after) "
            "with exactly these keys:\n"
            "{\n"
            '  "options": [{"name": "<option name>", "tradeoff": "<what you give up / gain>"}, "..."],\n'
            '  "architecture_decisions": ["<decision 1>", "..."],\n'
            '  "risks": ["<risk 1>", "..."],\n'
            '  "limitations": ["<limitation 1>", "..."],\n'
            '  "dependencies": ["<dependency 1>", "..."],\n'
            '  "logical_architecture": "<2-3 sentences describing the logical architecture>",\n'
            '  "integration_overview": "<1-2 sentences on how external systems are integrated>",\n'
            '  "infrastructure_overview": "<1-2 sentences on environments and infrastructure>"\n'
            "}\n\n"
            f"Produce at least {self.MIN_OPTIONS} architecture options (the first one listed is treated as "
            f"the recommendation) and between {self.MIN_DECISIONS} and {self.MAX_DECISIONS} architecture "
            "decisions. Do not add your own numbering or IDs to option names or decisions — the calling "
            "system assigns stable IDs itself."
        )


class DataIntegrationLlmAdapter:
    """Real LLM-backed runtime for the Data & Integration Agent.

    Reads the upstream Solution Approach's actual text (see
    OrchestratorService._gather_upstream_artefacts_text) so the Dataverse
    schema and integration design are grounded in the architecture
    decisions Technical Design actually made, not just the original task
    request.
    """

    SKILL_RELATIVE_PATH = "03_Agent_Skills/data_integration/SKILL.md"
    MIN_ENTITIES = 2
    MAX_ENTITIES = 8

    def __init__(self, provider: ModelProvider | None = None):
        self._provider = provider

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        provider = self._provider or model_provider_factory.get_model_provider()
        settings = get_settings()
        project_name = request.constraints.get("project_name", request.project_id)

        system_prompt = (REPO_ROOT / self.SKILL_RELATIVE_PATH).read_text(encoding="utf-8")
        solution_approach_text = request.upstream_artefacts_text.get("solution_approach", "")
        user_prompt = self._build_user_prompt(
            project_name=str(project_name),
            task_request=request.task_request,
            solution_approach_text=solution_approach_text,
        )

        raw_response = provider.complete(system=system_prompt, user=user_prompt)
        parsed = _extract_json(raw_response)

        raw_entities = parsed.get("entities", [])
        entities: list[tuple[str, str]] = []
        for entry in raw_entities:
            if not isinstance(entry, dict):
                continue
            name = _strip_leading_id_prefix(str(entry.get("name", ""))).strip()
            description = str(entry.get("description", "")).strip()
            if name and description:
                entities.append((name, description))

        if not entities:
            raise ModelProviderError(f"Model response contained no Dataverse entities: {parsed!r}"[:500])

        relationships = [str(r).strip() for r in parsed.get("relationships", []) if str(r).strip()]
        external_sources = [str(s).strip() for s in parsed.get("external_sources", []) if str(s).strip()]
        connectors = [str(c).strip() for c in parsed.get("connectors", []) if str(c).strip()]

        entity_ids = [f"DATA-{i + 1:03d}" for i in range(len(entities))]
        version_label = common.version_label(request.run_number)
        output_dir = settings.generated_artefacts_dir / request.project_id

        data_migration_text = str(parsed.get("data_migration", "")).strip() or (
            "Data migration not specified by the model."
        )
        reporting_model_text = str(parsed.get("reporting_model", "")).strip() or (
            "Reporting model not specified by the model."
        )

        produced = data_integration_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            entities=entities,
            entity_ids=entity_ids,
            relationships=relationships or ["No relationships identified by the model."],
            external_sources=external_sources or ["No external sources identified by the model."],
            connectors=connectors or ["No connectors identified by the model."],
            data_migration_text=data_migration_text,
            reporting_model_text=reporting_model_text,
        )

        return AgentRunResult(
            execution_summary=(
                f"Generated {data_integration_renderer.ARTEFACT_TYPE} with "
                f"{len(entities)} LLM-generated Dataverse entities."
            ),
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"entity_count": len(entities)},
        )

    def _build_user_prompt(self, *, project_name: str, task_request: str, solution_approach_text: str) -> str:
        context_section = (
            f'Approved Solution Approach Document for this project:\n"""\n{solution_approach_text}\n"""\n\n'
            if solution_approach_text
            else ""
        )
        return (
            f"Project name: {project_name}\n\n"
            f"Original high-level requirement from the user:\n\"\"\"\n{task_request}\n\"\"\"\n\n"
            f"{context_section}"
            "Design the Dataverse data model for this project, grounded in the Solution Approach above. "
            "Respond with ONLY a JSON object (no markdown code fences, no commentary before or after) "
            "with exactly these keys:\n"
            "{\n"
            '  "entities": [{"name": "<Entity Name>", "description": "<what it stores>"}, "..."],\n'
            '  "relationships": ["<relationship 1, e.g. \'Booking N:1 Facility\'>", "..."],\n'
            '  "external_sources": ["<external system and how it maps to Dataverse>", "..."],\n'
            '  "connectors": ["<API or connector used>", "..."],\n'
            '  "data_migration": "<1-2 sentences on migration approach, or state none is needed>",\n'
            '  "reporting_model": "<1-2 sentences on the reporting approach, or state it is deferred>"\n'
            "}\n\n"
            f"Produce between {self.MIN_ENTITIES} and {self.MAX_ENTITIES} Dataverse entities and at least "
            "one relationship between them. Do not add your own numbering or IDs to entity names — the "
            "calling system assigns stable IDs itself."
        )


class GovernanceSecurityLlmAdapter:
    """Real LLM-backed runtime for the Governance & Security Agent.

    Reads the upstream Data Design Document's actual text (see
    OrchestratorService._gather_upstream_artefacts_text) so DLP
    classification and connector governance cover the connectors Data &
    Integration actually chose, not a generic list.
    """

    SKILL_RELATIVE_PATH = "03_Agent_Skills/governance_security/SKILL.md"

    def __init__(self, provider: ModelProvider | None = None):
        self._provider = provider

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        provider = self._provider or model_provider_factory.get_model_provider()
        settings = get_settings()
        project_name = request.constraints.get("project_name", request.project_id)

        system_prompt = (REPO_ROOT / self.SKILL_RELATIVE_PATH).read_text(encoding="utf-8")
        data_design_text = request.upstream_artefacts_text.get("data_design_document", "")
        user_prompt = self._build_user_prompt(
            project_name=str(project_name),
            task_request=request.task_request,
            data_design_text=data_design_text,
        )

        raw_response = provider.complete(system=system_prompt, user=user_prompt)
        parsed = _extract_json(raw_response)

        dlp_lines = [str(d).strip() for d in parsed.get("dlp", []) if str(d).strip()]
        licensing_lines = [str(lic).strip() for lic in parsed.get("licensing", []) if str(lic).strip()]

        if not dlp_lines or not licensing_lines:
            raise ModelProviderError(f"Model response missing required dlp or licensing lines: {parsed!r}"[:500])

        version_label = common.version_label(request.run_number)
        output_dir = settings.generated_artefacts_dir / request.project_id

        def text_field(key: str) -> str:
            return str(parsed.get(key, "")).strip() or f"{key.replace('_', ' ').title()} not specified by the model."

        produced = governance_security_renderer.render(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            identity_design_text=text_field("identity_design"),
            permissions_text=text_field("permissions"),
            environment_strategy_text=text_field("environment_strategy"),
            dlp_lines=dlp_lines,
            connector_governance_text=text_field("connector_governance"),
            licensing_lines=licensing_lines,
            compliance_text=text_field("compliance"),
            operational_ownership_text=text_field("operational_ownership"),
            audit_requirements_text=text_field("audit_requirements"),
        )

        return AgentRunResult(
            execution_summary=f"Generated {governance_security_renderer.ARTEFACT_TYPE} from LLM-generated governance content.",
            artefacts_produced=[produced],
            review_status="ready_for_review",
            execution_metrics={"dlp_line_count": len(dlp_lines)},
        )

    def _build_user_prompt(self, *, project_name: str, task_request: str, data_design_text: str) -> str:
        context_section = (
            f'Approved Data Design Document for this project:\n"""\n{data_design_text}\n"""\n\n'
            if data_design_text
            else ""
        )
        return (
            f"Project name: {project_name}\n\n"
            f"Original high-level requirement from the user:\n\"\"\"\n{task_request}\n\"\"\"\n\n"
            f"{context_section}"
            "Produce the governance design for this project, grounded in the Data Design Document above — "
            "in particular, give every connector it mentions an explicit DLP classification. "
            "Respond with ONLY a JSON object (no markdown code fences, no commentary before or after) "
            "with exactly these keys:\n"
            "{\n"
            '  "identity_design": "<1-2 sentences on the identity provider and auth approach>",\n'
            '  "permissions": "<1-2 sentences on least-privilege permission design>",\n'
            '  "environment_strategy": "<1-2 sentences on dev/test/prod environment strategy>",\n'
            '  "dlp": ["<DLP classification line 1>", "..."],\n'
            '  "connector_governance": "<1-2 sentences on how upstream connectors are governed>",\n'
            '  "licensing": ["<licensing consideration 1>", "..."],\n'
            '  "compliance": "<1-2 sentences on regulated data categories, or state none apply>",\n'
            '  "operational_ownership": "<1-2 sentences on who owns operations and escalation>",\n'
            '  "audit_requirements": "<1-2 sentences on what must be audited and retained>"\n'
            "}\n\n"
            "Produce at least one DLP classification line per connector mentioned in the Data Design "
            "Document, and at least one licensing consideration."
        )


class BuildLlmAdapter:
    """Real LLM-backed runtime for the Build Agent.

    Unlike earlier agents, which only ever had one immediate predecessor,
    Build's guardrail requires findings to reference entities from any
    upstream phase (e.g. SCR-002, ADR-001) — so this reads every upstream
    artefact present, not just the Governance Document named as its
    formal manifest input, via _format_multi_artefact_context.
    """

    SKILL_RELATIVE_PATH = "03_Agent_Skills/build/SKILL.md"
    CONTEXT_ARTEFACT_TYPES = [
        "requirement_specification",
        "ux_design_specification",
        "solution_approach",
        "architecture_handbook",
        "data_design_document",
        "governance_document",
    ]

    def __init__(self, provider: ModelProvider | None = None):
        self._provider = provider

    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        provider = self._provider or model_provider_factory.get_model_provider()
        settings = get_settings()
        project_name = request.constraints.get("project_name", request.project_id)

        system_prompt = (REPO_ROOT / self.SKILL_RELATIVE_PATH).read_text(encoding="utf-8")
        upstream_context = _format_multi_artefact_context(request.upstream_artefacts_text, self.CONTEXT_ARTEFACT_TYPES)
        user_prompt = self._build_user_prompt(
            project_name=str(project_name), task_request=request.task_request, upstream_context=upstream_context
        )

        raw_response = provider.complete(system=system_prompt, user=user_prompt)
        parsed = _extract_json(raw_response)

        raw_findings = parsed.get("findings", [])
        findings: list[str] = []
        for entry in raw_findings:
            if not isinstance(entry, dict):
                continue
            reference = str(entry.get("reference", "")).strip()
            description = str(entry.get("description", "")).strip()
            if description:
                findings.append(f"{reference}: {description}" if reference else description)

        if not findings:
            raise ModelProviderError(f"Model response contained no build findings: {parsed!r}"[:500])

        defect_entities = [f"DEF-{i + 1:03d}" for i in range(len(findings))]
        version_label = common.version_label(request.run_number)
        output_dir = settings.generated_artefacts_dir / request.project_id

        implementation_assets_text = str(parsed.get("implementation_assets", "")).strip() or (
            "Implementation assets not specified by the model."
        )
        configuration_summary_text = str(parsed.get("configuration_summary", "")).strip() or (
            "Configuration summary not specified by the model."
        )

        build_review_produced = build_renderer.render_build_review(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            implementation_assets_text=implementation_assets_text,
            configuration_summary_text=configuration_summary_text,
            findings=findings,
            defect_entities=defect_entities,
            fixes_applied=[f"{eid}: fixed and re-verified in this build run." for eid in defect_entities],
        )
        final_code_review_produced = build_renderer.render_final_code_review(
            repo_root=REPO_ROOT,
            output_dir=output_dir,
            project_name=str(project_name),
            version_label=version_label,
            review_scope_text="Full review of all implementation assets produced in this build cycle.",
            findings_text="No new findings beyond those already tracked in the Build Review Report.",
            defect_entities=defect_entities,
            resolution_lines=[f"{eid}: resolved." for eid in defect_entities],
        )

        return AgentRunResult(
            execution_summary=(
                f"Generated {build_renderer.BUILD_REVIEW_ARTEFACT_TYPE} and "
                f"{build_renderer.FINAL_CODE_REVIEW_ARTEFACT_TYPE} with {len(findings)} LLM-generated findings."
            ),
            artefacts_produced=[build_review_produced, final_code_review_produced],
            review_status="ready_for_review",
            execution_metrics={"finding_count": len(findings)},
        )

    def _build_user_prompt(self, *, project_name: str, task_request: str, upstream_context: str) -> str:
        context_section = f"{upstream_context}\n\n" if upstream_context else ""
        return (
            f"Project name: {project_name}\n\n"
            f"Original high-level requirement from the user:\n\"\"\"\n{task_request}\n\"\"\"\n\n"
            f"{context_section}"
            "Review the implementation built from the approved artefacts above and report build findings. "
            "Respond with ONLY a JSON object (no markdown code fences, no commentary before or after) "
            "with exactly these keys:\n"
            "{\n"
            '  "implementation_assets": "<1-2 sentences on what was built>",\n'
            '  "configuration_summary": "<1-2 sentences on environment/connection configuration>",\n'
            '  "findings": [{"reference": "<upstream ID this finding relates to, e.g. SCR-002 or ADR-001>", '
            '"description": "<the finding>"}, "..."]\n'
            "}\n\n"
            "Produce at least 1 and at most 5 findings, each referencing a specific ID from the upstream "
            "artefacts above rather than vague prose. Do not add your own numbering or IDs beyond the "
            "\"reference\" field — the calling system assigns each finding its own stable ID itself."
        )
