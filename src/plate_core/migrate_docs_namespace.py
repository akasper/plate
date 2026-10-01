"""Safe migration of PLATE docs from docs/ root to docs/plate/ namespace.

Addresses #1027: provides a purpose-built migration command that:
- Uses git mv to move PLATE-owned doc directories
- Preserves customized files (AGENTS.md, SPEC.md, CURRENT.md, product docs)
- Rewrites references in repository files
- Is idempotent (safe to re-run)
- Dry-run by default

PLATE-owned doc directories:
- adr/, audits/, bootstrap/, design/, marketing/, migration/, research/, wiki/

PLATE-owned root doc files (only if they match template content):
- README.md (must contain "# Documentation Index" and "playwright-e2e-guide.md")
- playwright-e2e-guide.md (must contain template title)

Never touched:
- AGENTS.md, SPEC.md, CURRENT.md (only their internal references are updated)
- Product documentation directories
- Any files outside docs/
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# PLATE-owned doc directories that should be moved
PLATE_DOC_DIRS = [
    "adr",
    "audits",
    "bootstrap",
    "design",
    "marketing",
    "migration",
    "research",
    "wiki",
]

# Files that are never moved (only their references are updated)
PROTECTED_FILES = {"AGENTS.md", "SPEC.md", "CURRENT.md"}

# Files that need reference updates
REFERENCE_FILES = [
    "AGENTS.md",
    "SPEC.md",
    "CONTRIBUTING.md",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".github/ISSUE_TEMPLATE/*.yml",
    ".github/ISSUE_TEMPLATE/*.yaml",
    ".github/copilot-instructions.md",
    ".github/agents/*.agent.md",
    ".agentic/skills.yml",
    ".agentic/migration.yml",
    "scripts/README.md",
    "scripts/bootstrap_github.sh",
    "scripts/BootstrapGitHub.ps1",
]


@dataclass
class MigrationAction:
    """Represents a single migration action."""
    action_type: str  # move_dir | move_file | skip | update_refs | conflict | rewrite_links
    source: str
    target: str | None = None
    reason: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "source": self.source,
            "target": self.target,
            "reason": self.reason,
        }


@dataclass
class MigrationPlan:
    """Migration plan with all actions."""
    target_dir: Path
    apply_mode: bool
    actions: list[MigrationAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ok: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "apply_mode": self.apply_mode,
            "target_dir": str(self.target_dir),
            "actions": [a.to_dict() for a in self.actions],
            "warnings": self.warnings,
            "errors": self.errors,
            "summary": {
                "move_dir": len([a for a in self.actions if a.action_type == "move_dir"]),
                "move_file": len([a for a in self.actions if a.action_type == "move_file"]),
                "skip": len([a for a in self.actions if a.action_type == "skip"]),
                "update_refs": len([a for a in self.actions if a.action_type == "update_refs"]),
                "conflict": len([a for a in self.actions if a.action_type == "conflict"]),
                "rewrite_links": len([a for a in self.actions if a.action_type == "rewrite_links"]),
            },
        }


def _is_git_repo(target_dir: Path) -> bool:
    """Check if the target directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _is_plate_readme(path: Path) -> bool:
    """Check if README.md is the PLATE template version."""
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return (
        "# Documentation Index" in content
        and "playwright-e2e-guide.md" in content
    )


def _is_plate_playwright_guide(path: Path) -> bool:
    """Check if playwright-e2e-guide.md is the PLATE template version."""
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return "Playwright E2E Testing & Demo GIF Generation Guide" in content


def _find_files_matching_patterns(
    target_dir: Path, patterns: list[str]
) -> list[Path]:
    """Find all files matching the given glob patterns."""
    found = []
    for pattern in patterns:
        found.extend(target_dir.glob(pattern))
    return sorted(set(found))


def _update_references_in_file(
    file_path: Path, dry_run: bool = True
) -> tuple[bool, int]:
    """Update doc/ references to docs/plate/ in a file.
    
    Returns (changed, count) where changed is True if file was modified
    and count is the number of replacements made.
    """
    if not file_path.exists():
        return False, 0
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, 0
    
    original = content
    count = 0
    
    # Update references for each PLATE doc directory
    for plate_dir in PLATE_DOC_DIRS:
        # Match paths like docs/design/ or `docs/design/
        patterns = [
            (rf"docs/{plate_dir}/", rf"docs/plate/{plate_dir}/"),
            (rf"`docs/{plate_dir}/", rf"`docs/plate/{plate_dir}/"),
        ]
        for old_pattern, new_pattern in patterns:
            new_content, n = re.subn(old_pattern, new_pattern, content)
            if n > 0:
                content = new_content
                count += n
    
    changed = content != original
    
    if changed and not dry_run:
        file_path.write_text(content, encoding="utf-8")
    
    return changed, count


def _rewrite_relative_links(content: str) -> str:
    """Rewrite relative links when moving README from docs/ to docs/plate/.
    
    Links like ../AGENTS.md need to become ../../AGENTS.md
    Links like ../tests/e2e need to become ../../tests/e2e
    """
    # Match markdown links: [text](../path) or [text](../)
    def rewrite_link(match):
        text = match.group(1)
        path = match.group(2)
        # If it starts with ../, add another ../
        if path.startswith("../"):
            return f"[{text}](../{path})"
        return match.group(0)
    
    # Pattern: [text](../something)
    content = re.sub(r'\[([^\]]+)\]\((\.\.\/[^)]+)\)', rewrite_link, content)
    
    return content


def _directories_are_identical(dir1: Path, dir2: Path) -> bool:
    """Check if two directories have identical contents (structure and content).
    
    Returns True only if both dirs exist, have the same file structure,
    and all files have identical content.
    """
    if not (dir1.exists() and dir2.exists()):
        return False
    
    if not (dir1.is_dir() and dir2.is_dir()):
        return False
    
    # Get all relative file paths in both directories
    files1 = {f.relative_to(dir1) for f in dir1.rglob("*") if f.is_file()}
    files2 = {f.relative_to(dir2) for f in dir2.rglob("*") if f.is_file()}
    
    # Different file structure
    if files1 != files2:
        return False
    
    # Check that all files have identical content
    for rel_path in files1:
        file1 = dir1 / rel_path
        file2 = dir2 / rel_path
        try:
            content1 = file1.read_bytes()
            content2 = file2.read_bytes()
            if content1 != content2:
                return False
        except (OSError, UnicodeDecodeError):
            # If we can't read, consider them different
            return False
    
    return True


def plan_migration(target_dir: Path | str) -> MigrationPlan:
    """Plan the migration of PLATE docs to docs/plate/ namespace.
    
    Args:
        target_dir: Repository root directory
        
    Returns:
        MigrationPlan with all planned actions
    """
    target_path = Path(target_dir).resolve()
    plan = MigrationPlan(target_dir=target_path, apply_mode=False)
    
    # Check if it's a git repo
    if not _is_git_repo(target_path):
        plan.errors.append(
            f"Not a git repository: {target_path}. "
            "This command requires git to safely move files."
        )
        plan.ok = False
        return plan
    
    docs_dir = target_path / "docs"
    if not docs_dir.exists():
        plan.warnings.append("No docs/ directory found. Nothing to migrate.")
        return plan
    
    plate_docs_dir = docs_dir / "plate"
    
    # Plan moving PLATE doc directories
    for plate_dir in PLATE_DOC_DIRS:
        source_dir = docs_dir / plate_dir
        target_dir_path = plate_docs_dir / plate_dir
        
        if source_dir.exists() and source_dir.is_dir():
            if target_dir_path.exists():
                # Both exist - check if identical
                if _directories_are_identical(source_dir, target_dir_path):
                    plan.actions.append(
                        MigrationAction(
                            action_type="skip",
                            source=f"docs/{plate_dir}/",
                            target=f"docs/plate/{plate_dir}/",
                            reason="Identical duplicate - will reconcile by removing source",
                        )
                    )
                else:
                    # Conflicting duplicates
                    plan.actions.append(
                        MigrationAction(
                            action_type="conflict",
                            source=f"docs/{plate_dir}/",
                            target=f"docs/plate/{plate_dir}/",
                            reason="Both exist with different contents - manual resolution needed",
                        )
                    )
                    plan.ok = False
            else:
                plan.actions.append(
                    MigrationAction(
                        action_type="move_dir",
                        source=f"docs/{plate_dir}/",
                        target=f"docs/plate/{plate_dir}/",
                        reason="PLATE-owned directory",
                    )
                )
    
    # Check PLATE root doc files
    readme_path = docs_dir / "README.md"
    if _is_plate_readme(readme_path):
        target_readme = plate_docs_dir / "README.md"
        if target_readme.exists():
            plan.actions.append(
                MigrationAction(
                    action_type="skip",
                    source="docs/README.md",
                    target="docs/plate/README.md",
                    reason="Target already exists (idempotent)",
                )
            )
        else:
            plan.actions.append(
                MigrationAction(
                    action_type="move_file",
                    source="docs/README.md",
                    target="docs/plate/README.md",
                    reason="PLATE template README",
                )
            )
            # Add link rewriting action for moved README
            plan.actions.append(
                MigrationAction(
                    action_type="rewrite_links",
                    source="docs/plate/README.md",
                    target=None,
                    reason="Fix relative links after move from docs/ to docs/plate/",
                )
            )
    
    playwright_guide = docs_dir / "playwright-e2e-guide.md"
    if _is_plate_playwright_guide(playwright_guide):
        target_guide = plate_docs_dir / "playwright-e2e-guide.md"
        if target_guide.exists():
            plan.actions.append(
                MigrationAction(
                    action_type="skip",
                    source="docs/playwright-e2e-guide.md",
                    target="docs/plate/playwright-e2e-guide.md",
                    reason="Target already exists (idempotent)",
                )
            )
        else:
            plan.actions.append(
                MigrationAction(
                    action_type="move_file",
                    source="docs/playwright-e2e-guide.md",
                    target="docs/plate/playwright-e2e-guide.md",
                    reason="PLATE template guide",
                )
            )
    
    # Plan reference updates
    ref_files = _find_files_matching_patterns(target_path, REFERENCE_FILES)
    for ref_file in ref_files:
        relative = ref_file.relative_to(target_path)
        # Skip if the file doesn't exist or is not a file
        if not ref_file.is_file():
            continue
        
        # Check if file has references that need updating
        changed, count = _update_references_in_file(ref_file, dry_run=True)
        if changed:
            plan.actions.append(
                MigrationAction(
                    action_type="update_refs",
                    source=str(relative),
                    target=None,
                    reason=f"{count} reference(s) to update",
                )
            )
    
    # Check if there's anything to do
    move_actions = [
        a for a in plan.actions
        if a.action_type in ("move_dir", "move_file", "update_refs")
    ]
    if not move_actions:
        if not plan.warnings:
            plan.warnings.append(
                "No PLATE docs found to migrate, or migration already complete."
            )
    
    return plan


def apply_migration(target_dir: Path | str) -> MigrationPlan:
    """Apply the migration plan to move PLATE docs to docs/plate/ namespace.
    
    Args:
        target_dir: Repository root directory
        
    Returns:
        MigrationPlan with results of applied actions
    """
    target_path = Path(target_dir).resolve()
    plan = plan_migration(target_path)
    plan.apply_mode = True
    
    if not plan.ok:
        return plan
    
    docs_dir = target_path / "docs"
    plate_docs_dir = docs_dir / "plate"
    
    # Preflight check: verify all moves are possible before doing anything
    move_actions = [
        a for a in plan.actions
        if a.action_type in ("move_dir", "move_file")
    ]
    for action in move_actions:
        source_path = target_path / action.source
        if not source_path.exists():
            plan.ok = False
            plan.errors.append(f"Preflight failed: source does not exist: {action.source}")
            return plan
    
    # Create docs/plate/ if needed
    if move_actions and not plate_docs_dir.exists():
        try:
            plate_docs_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            plan.errors.append(f"Failed to create docs/plate/: {e}")
            plan.ok = False
            return plan
    
    # Apply move actions
    for action in plan.actions:
        if action.action_type == "move_dir":
            source_path = target_path / action.source
            target_path_full = target_path / action.target
            
            try:
                # Use git mv for proper git tracking
                result = subprocess.run(
                    ["git", "mv", str(source_path), str(target_path_full)],
                    cwd=target_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                plan.errors.append(
                    f"Failed to git mv {action.source}: {e.stderr}"
                )
                plan.ok = False
                # Stop immediately - do not continue with reference updates
                return plan
                
        elif action.action_type == "move_file":
            source_path = target_path / action.source
            target_path_full = target_path / action.target
            
            try:
                # Use git mv for proper git tracking
                result = subprocess.run(
                    ["git", "mv", str(source_path), str(target_path_full)],
                    cwd=target_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                plan.errors.append(
                    f"Failed to git mv {action.source}: {e.stderr}"
                )
                plan.ok = False
                # Stop immediately - do not continue with reference updates
                return plan
                
        elif action.action_type == "skip":
            # Handle reconciliation of identical duplicates
            if "Identical duplicate" in action.reason:
                source_path = target_path / action.source
                try:
                    subprocess.run(
                        ["git", "rm", "-rf", str(source_path)],
                        cwd=target_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    plan.ok = False
                    plan.errors.append(
                        f"Failed to reconcile duplicate {action.source}: {e.stderr}"
                    )
                    return plan
        
        elif action.action_type == "rewrite_links":
            # Rewrite relative links in moved files
            file_path = target_path / action.source
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    new_content = _rewrite_relative_links(content)
                    if new_content != content:
                        file_path.write_text(new_content, encoding="utf-8")
                        # Stage the change
                        subprocess.run(
                            ["git", "add", str(file_path)],
                            cwd=target_path,
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                except (OSError, subprocess.CalledProcessError) as e:
                    plan.errors.append(
                        f"Failed to rewrite links in {action.source}: {e}"
                    )
                
        elif action.action_type == "update_refs":
            file_path = target_path / action.source
            try:
                changed, count = _update_references_in_file(
                    file_path, dry_run=False
                )
                if not changed:
                    plan.warnings.append(
                        f"Expected to update {action.source} but no changes made"
                    )
            except Exception as e:
                plan.errors.append(
                    f"Failed to update references in {action.source}: {e}"
                )
                plan.ok = False
    
    return plan


def migrate_docs_namespace(
    target_dir: Path | str | None = None,
    apply: bool = False,
) -> MigrationPlan:
    """Migrate PLATE docs from docs/ root to docs/plate/ namespace.
    
    Args:
        target_dir: Repository root directory (default: current directory)
        apply: If True, apply the migration; if False, dry-run only
        
    Returns:
        MigrationPlan with planned or applied actions
    """
    if target_dir is None:
        target_dir = Path.cwd()
    
    if apply:
        return apply_migration(target_dir)
    else:
        return plan_migration(target_dir)
