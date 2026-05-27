"""Baseline agent and skill catalog for plate_core."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "agents": [agent.to_dict() for agent in self.agents],
            "skills": [skill.to_dict() for skill in self.skills],
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


@lru_cache(maxsize=1)
def load_baseline_catalog() -> BaselineCatalog:
    data = _load_yaml()
    schema_version = data.get("schema_version")
    _require(schema_version == 1, "baseline catalog schema_version must be 1")
    agents = _load_agents(data.get("agents"))
    skills = _load_skills(data.get("skills"))

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

    return BaselineCatalog(schema_version=1, agents=agents, skills=skills)


def list_agents() -> tuple[BaselineAgent, ...]:
    return load_baseline_catalog().agents


def list_skills() -> tuple[BaselineSkill, ...]:
    return load_baseline_catalog().skills


def get_agent(agent_id: str) -> BaselineAgent:
    return load_baseline_catalog().agent_by_id(agent_id)


def get_skill(skill_id: str) -> BaselineSkill:
    return load_baseline_catalog().skill_by_id(skill_id)
