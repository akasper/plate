"""Baseline agent and skill catalog for plate_core."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .context_map import get_context_route


class BaselineCatalogError(ValueError):
    """Raised when the baseline catalog is missing or invalid."""


@dataclass(frozen=True)
class BaselineSkill:
    id: str
    name: str
    description: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    examples: tuple[str, ...]
    owning_agent_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "examples": list(self.examples),
            "owning_agent_ids": list(self.owning_agent_ids),
        }


@dataclass(frozen=True)
class BaselineInformationalGoal:
    """Default informational goal (for #222 catalog, usable by #221 audit and bootstrap)."""

    id: str
    title: str
    body: str
    related_goals: tuple[str, ...] = ()
    provenance_hint: str = ""
    priority_rationale: str = ""
    refinement_note: str = ""
    provided_by: str = "platform"  # "platform" or extension id for #226 extensibility

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "related_goals": list(self.related_goals),
            "provenance_hint": self.provenance_hint,
            "priority_rationale": self.priority_rationale,
            "refinement_note": self.refinement_note,
            "provided_by": self.provided_by,
        }


@dataclass(frozen=True)
class BaselineAgent:
    id: str
    name: str
    description: str
    primary_skill_ids: tuple[str, ...]
    constraints: tuple[str, ...]
    surfaces: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "primary_skill_ids": list(self.primary_skill_ids),
            "constraints": list(self.constraints),
            "surfaces": list(self.surfaces),
        }


@dataclass(frozen=True)
class BaselineCatalog:
    schema_version: int
    agents: tuple[BaselineAgent, ...]
    skills: tuple[BaselineSkill, ...]
    informational_goals: tuple[BaselineInformationalGoal, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "agents": [agent.to_dict() for agent in self.agents],
            "skills": [skill.to_dict() for skill in self.skills],
            "informational_goals": [g.to_dict() for g in self.informational_goals],
        }

    def agent_by_id(self, agent_id: str) -> BaselineAgent:
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        raise BaselineCatalogError(f"Unknown agent: {agent_id}")

    def skill_by_id(self, skill_id: str) -> BaselineSkill:
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        raise BaselineCatalogError(f"Unknown skill: {skill_id}")

    def list_informational_goals(self) -> tuple[BaselineInformationalGoal, ...]:
        return self.informational_goals

    def informational_goal_by_id(self, goal_id: str) -> BaselineInformationalGoal:
        for g in self.informational_goals:
            if g.id == goal_id:
                return g
        raise BaselineCatalogError(f"Unknown informational goal: {goal_id}")


def _catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "baseline_catalog.yml"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BaselineCatalogError(message)


def _as_str_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{field_name} must be a list")
    items: list[str] = []
    for item in value:
        _require(isinstance(item, str) and item, f"{field_name} entries must be non-empty strings")
        items.append(item)
    return tuple(items)


def _load_yaml() -> dict[str, Any]:
    path = _catalog_path()
    _require(path.exists(), f"Baseline catalog not found at {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    _require(isinstance(data, dict), "Baseline catalog must be a mapping")
    return data


def _load_agents(raw_agents: Any) -> tuple[BaselineAgent, ...]:
    _require(isinstance(raw_agents, list), "agents must be a list")
    agents: list[BaselineAgent] = []
    seen: set[str] = set()
    for item in raw_agents:
        _require(isinstance(item, dict), "each agent must be a mapping")
        agent_id = item.get("id")
        _require(isinstance(agent_id, str) and agent_id, "agent.id must be a non-empty string")
        _require(agent_id not in seen, f"duplicate agent id: {agent_id}")
        seen.add(agent_id)
        agents.append(
            BaselineAgent(
                id=agent_id,
                name=item.get("name", agent_id),
                description=item.get("description", ""),
                primary_skill_ids=_as_str_tuple(item.get("primary_skill_ids", []), f"agent {agent_id} primary_skill_ids"),
                constraints=_as_str_tuple(item.get("constraints", []), f"agent {agent_id} constraints"),
                surfaces=_as_str_tuple(item.get("surfaces", []), f"agent {agent_id} surfaces"),
            )
        )
    return tuple(agents)


def _load_skills(raw_skills: Any) -> tuple[BaselineSkill, ...]:
    _require(isinstance(raw_skills, list), "skills must be a list")
    skills: list[BaselineSkill] = []
    seen: set[str] = set()
    for item in raw_skills:
        _require(isinstance(item, dict), "each skill must be a mapping")
        skill_id = item.get("id")
        _require(isinstance(skill_id, str) and skill_id, "skill.id must be a non-empty string")
        _require(skill_id not in seen, f"duplicate skill id: {skill_id}")
        seen.add(skill_id)
        skills.append(
            BaselineSkill(
                id=skill_id,
                name=item.get("name", skill_id),
                description=item.get("description", ""),
                inputs=_as_str_tuple(item.get("inputs", []), f"skill {skill_id} inputs"),
                outputs=_as_str_tuple(item.get("outputs", []), f"skill {skill_id} outputs"),
                examples=_as_str_tuple(item.get("examples", []), f"skill {skill_id} examples"),
                owning_agent_ids=_as_str_tuple(item.get("owning_agent_ids", []), f"skill {skill_id} owning_agent_ids"),
            )
        )
    return tuple(skills)


def _load_informational_goals(raw_goals: Any) -> tuple[BaselineInformationalGoal, ...]:
    if raw_goals is None:
        return ()
    _require(isinstance(raw_goals, list), "informational_goals must be a list or absent")
    goals: list[BaselineInformationalGoal] = []
    seen: set[str] = set()
    for item in raw_goals:
        _require(isinstance(item, dict), "each informational_goal must be a mapping")
        gid = item.get("id")
        _require(isinstance(gid, str) and gid, "informational_goal.id must be a non-empty string")
        _require(gid not in seen, f"duplicate informational_goal id: {gid}")
        seen.add(gid)
        goals.append(
            BaselineInformationalGoal(
                id=gid,
                title=item.get("title", gid),
                body=item.get("body", ""),
                related_goals=_as_str_tuple(item.get("related_goals", []), f"informational_goal {gid} related_goals"),
                provenance_hint=item.get("provenance_hint", ""),
                priority_rationale=item.get("priority_rationale", ""),
                refinement_note=item.get("refinement_note", ""),
                provided_by=item.get("provided_by", "platform"),
            )
        )
    return tuple(goals)


@lru_cache(maxsize=1)
def load_baseline_catalog() -> BaselineCatalog:
    data = _load_yaml()
    schema_version = data.get("schema_version")
    _require(schema_version == 1, "baseline catalog schema_version must be 1")
    agents = _load_agents(data.get("agents"))
    skills = _load_skills(data.get("skills"))
    informational_goals = _load_informational_goals(data.get("informational_goals"))

    agent_ids = {agent.id for agent in agents}
    skill_ids = {skill.id for skill in skills}

    for agent in agents:
        _require(agent.surfaces, f"agent {agent.id} must define at least one surface")
        for skill_id in agent.primary_skill_ids:
            _require(skill_id in skill_ids, f"agent {agent.id} references unknown skill {skill_id}")

    for skill in skills:
        _require(skill.owning_agent_ids, f"skill {skill.id} must have at least one owning agent")
        for agent_id in skill.owning_agent_ids:
            _require(agent_id in agent_ids, f"skill {skill.id} references unknown agent {agent_id}")

    return BaselineCatalog(schema_version=1, agents=agents, skills=skills, informational_goals=informational_goals)


@dataclass(frozen=True)
class DelegationResult:
    """Result of delegating a task to a baseline agent."""

    agent_id: str
    agent_name: str
    agent_description: str
    task_description: str
    task: dict[str, Any]
    artifacts: dict[str, Any]
    retrieval_hints: dict[str, Any]
    constraints: tuple[str, ...]
    delegation_prompt: str
    relevant_skills: tuple[BaselineSkill, ...]
    surfaces: tuple[str, ...]
    invocation_hints: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_description": self.agent_description,
            "task_description": self.task_description,
            "task": dict(self.task),
            "artifacts": dict(self.artifacts),
            "retrieval_hints": dict(self.retrieval_hints),
            "constraints": list(self.constraints),
            "delegation_prompt": self.delegation_prompt,
            "relevant_skills": [s.to_dict() for s in self.relevant_skills],
            "surfaces": list(self.surfaces),
            "invocation_hints": dict(self.invocation_hints),
        }


def build_delegation_prompt(
    agent: BaselineAgent,
    task: str,
    skills: list[BaselineSkill],
) -> str:
    """Build a deterministic delegation prompt from catalog data. No LLM call needed."""
    packet = build_delegation_packet(agent, task, skills)
    skill_names = [s.name for s in skills]
    if len(skill_names) > 2:
        skill_summary = f"{', '.join(skill_names[:2])} +{len(skill_names) - 2} more"
    else:
        skill_summary = ", ".join(skill_names) if skill_names else "(none)"

    out_of_scope = "; ".join(packet["task"]["out_of_scope"])
    return (
        f"Act as the {agent.name}.\n"
        f"Task: {packet['task']['summary']}\n"
        f"Kind: {packet['task']['kind']}\n"
        f"Skills: {skill_summary}\n"
        f"Success: {packet['task']['success_signal']}\n"
        f"Out of scope: {out_of_scope}\n"
        f"If more context is needed: {packet['retrieval_hints']['first_steps'][0]}"
    )


def build_delegation_packet(
    agent: BaselineAgent,
    task: str,
    skills: list[BaselineSkill],
) -> dict[str, Any]:
    """Build the packet-first delegation contract used by CLI, MCP, and prompt renderers."""
    route = get_context_route("delegation")
    first_skill = skills[0].id if skills else None
    task_kind = infer_delegation_task_kind(agent, skills)
    working_set = [f"gh plate agents show {agent.id}"]
    if first_skill:
        working_set.append(f"gh plate skills show {first_skill}")

    return {
        "task": {
            "summary": task,
            "kind": task_kind,
            "success_signal": f"Return a focused {task_kind} outcome that completes the delegated task.",
            "scope": [task],
            "out_of_scope": [
                "Re-explaining broad repository rules",
                "Unrelated work outside the delegated task",
            ],
        },
        "artifacts": {
            "authoritative": ["docs/wiki/Agent-Context-Map.md"],
            "working_set": working_set,
            "references": list(route.reference_docs),
        },
        "retrieval_hints": {
            "concern": route.id,
            "first_steps": [
                "gh plate context show delegation",
                f"gh plate agents show {agent.id}",
            ],
        },
        "constraints": tuple(agent.constraints) + ("Keep the response scoped to the delegated task.",),
    }


def infer_delegation_task_kind(agent: BaselineAgent, skills: list[BaselineSkill]) -> str:
    values = " ".join([agent.id, agent.name, agent.description, *(skill.id for skill in skills)]).lower()
    if "research" in values:
        return "research"
    if "design" in values:
        return "design"
    if "review" in values or "audit" in values or "security" in values:
        return "triage"
    if "manager" in values or "planner" in values:
        return "planning"
    return "implementation"


def delegate_to_agent(agent_id: str, task_description: str) -> DelegationResult:
    """Look up an agent by id and assemble a DelegationResult for routing the task."""
    catalog = load_baseline_catalog()
    agent = catalog.agent_by_id(agent_id)  # raises BaselineCatalogError if unknown

    skill_map = {s.id: s for s in catalog.skills}
    relevant_skills = tuple(
        skill_map[sid] for sid in agent.primary_skill_ids if sid in skill_map
    )

    packet = build_delegation_packet(agent, task_description, list(relevant_skills))
    prompt = build_delegation_prompt(agent, task_description, list(relevant_skills))

    hints: dict[str, str] = {
        "copilot_plugin": (
            f"Select the '{agent_id}' agent in the Copilot agent picker and pass the short rendered prompt or packet fields."
        ),
        "gh_plate": f"gh plate agents show {agent_id}",
        "mcp": f"Call plate_delegate_to_agent with agent_id={agent_id} and task_description=<task>.",
    }

    return DelegationResult(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_description=agent.description,
        task_description=task_description,
        task=packet["task"],
        artifacts=packet["artifacts"],
        retrieval_hints=packet["retrieval_hints"],
        constraints=packet["constraints"],
        delegation_prompt=prompt,
        relevant_skills=relevant_skills,
        surfaces=agent.surfaces,
        invocation_hints=hints,
    )


def list_agents() -> tuple[BaselineAgent, ...]:
    return load_baseline_catalog().agents


def list_skills() -> tuple[BaselineSkill, ...]:
    return load_baseline_catalog().skills


def get_agent(agent_id: str) -> BaselineAgent:
    return load_baseline_catalog().agent_by_id(agent_id)


def get_skill(skill_id: str) -> BaselineSkill:
    return load_baseline_catalog().skill_by_id(skill_id)


def list_informational_goals() -> tuple[BaselineInformationalGoal, ...]:
    return load_baseline_catalog().informational_goals


def get_informational_goal(goal_id: str) -> BaselineInformationalGoal:
    return load_baseline_catalog().informational_goal_by_id(goal_id)
