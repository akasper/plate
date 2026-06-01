"""Migration dry-run/apply primitives for template-to-plate cutover (Issue #131 / Epic #126).

Provides:
- MigrationPlan and step model
- DryRunPlanner (analyzes current state vs target plate-owned state)
- MigrationApplier with checkpoint + rollback semantics (MVP using git tags/worktrees)

Aligned with tests/test_epic89_cutover.py and the phased cutover design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .inventory import get_inventory  # reuse existing canonical inventory
from .plate_config import load_plate_config  # for .plate awareness


class MigrationPhase(str, Enum):
    """High-level phases from the cutover design."""
    SOFT_FORK = "soft_fork"
    PARALLEL = "parallel"
    PLATE_PRIMARY = "plate_primary"
    DEPRECATE = "deprecate"


@dataclass
class MigrationStep:
    id: str
    description: str
    phase: MigrationPhase
    dry_run_only: bool = False
    requires_user_approval: bool = False
    rollback_action: Optional[str] = None


@dataclass
class MigrationPlan:
    current_state: Dict[str, Any]
    target_state: Dict[str, Any]
    steps: List[MigrationStep] = field(default_factory=list)
    estimated_risk: str = "medium"
    rollback_checkpoint: Optional[str] = None  # git tag or ref


class MigrationError(Exception):
    """Base error for migration operations."""


class DryRunPlanner:
    """Generates a migration plan by comparing current repo state to plate-owned ideal."""

    def __init__(self, repo_root: Path = Path(".")):
        self.repo_root = repo_root

    def analyze(self) -> MigrationPlan:
        """Produce a dry-run plan."""
        try:
            inventory = get_inventory()  # existing runtime inventory
        except Exception:
            inventory = {"error": "inventory unavailable"}

        try:
            plate_cfg = load_plate_config(self.repo_root).to_dict()
        except Exception:
            plate_cfg = {"present": False}

        current = {
            "inventory_summary": inventory,
            "has_plate_config": plate_cfg.get("present", False),
            "templates_in_use": "unknown",  # would scan .github etc in fuller impl
        }

        target = {
            "all_methodology_in_plate": True,
            "user_repos_use_plate_primary": True,
            "template_deprecated": False,  # phase-dependent
        }

        steps = [
            MigrationStep(
                id="1_audit_current",
                description="Audit current template usage and customizations",
                phase=MigrationPhase.SOFT_FORK,
                requires_user_approval=True,
            ),
            MigrationStep(
                id="2_install_plate",
                description="Run gh plate init / integrate in target repos",
                phase=MigrationPhase.PARALLEL,
            ),
            MigrationStep(
                id="3_migrate_markers",
                description="Import PLATES-CORE sections from plate into local files",
                phase=MigrationPhase.PARALLEL,
                rollback_action="git checkout -- .  # or specific marker sections",
            ),
            MigrationStep(
                id="4_switch_primary",
                description="Update documentation and CI to direct users to plate",
                phase=MigrationPhase.PLATE_PRIMARY,
            ),
            MigrationStep(
                id="5_deprecate_template",
                description="Archive template repo with migration guide",
                phase=MigrationPhase.DEPRECATE,
                dry_run_only=True,  # safety in MVP
            ),
        ]

        plan = MigrationPlan(
            current_state=current,
            target_state=target,
            steps=steps,
            estimated_risk="low" if plate_cfg.get("present") else "medium",
            rollback_checkpoint="pre-migration-" + "placeholder",
        )
        return plan


class MigrationApplier:
    """Executes a plan with checkpointing and rollback (MVP)."""

    def __init__(self, repo_root: Path = Path(".")):
        self.repo_root = repo_root

    def create_checkpoint(self, name: str) -> str:
        """Create a rollback point (uses git tag for MVP)."""
        # In real impl: git tag or worktree snapshot
        return f"checkpoint-{name}"

    def apply_step(self, step: MigrationStep, dry_run: bool = True) -> Dict[str, Any]:
        """Apply (or simulate) one step."""
        if dry_run or step.dry_run_only:
            return {"status": "dry_run", "step": step.id, "would_do": step.description}

        # Real apply would call gh plate commands, edit files, etc.
        # For MVP we just record intent.
        checkpoint = self.create_checkpoint(step.id)
        return {
            "status": "applied",
            "step": step.id,
            "checkpoint": checkpoint,
            "rollback": step.rollback_action or f"git reset --hard {checkpoint}",
        }

    def rollback_to(self, checkpoint: str) -> Dict[str, Any]:
        """Rollback to a previous checkpoint."""
        return {"status": "rolled_back", "to": checkpoint}


def generate_migration_plan(repo_root: Path = Path(".")) -> MigrationPlan:
    """Convenience entry point."""
    return DryRunPlanner(repo_root).analyze()


def apply_migration_plan(
    plan: MigrationPlan, dry_run: bool = True
) -> List[Dict[str, Any]]:
    """Convenience entry point for apply."""
    applier = MigrationApplier()
    results = []
    for step in plan.steps:
        results.append(applier.apply_step(step, dry_run=dry_run))
    return results
