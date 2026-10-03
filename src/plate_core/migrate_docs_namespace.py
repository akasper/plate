"""Safe migration of PLATE docs from docs/ root to docs/plate/ namespace.

Addresses #1027: provides a purpose-built migration command that:
- Uses git mv to move PLATE-owned doc directories
- Preserves customized files (AGENTS.md, SPEC.md, CURRENT.md, product docs)
- Rewrites references in workflows, scripts, and selected repository files
- Reports stale references in protected files as manual follow-ups
- Is idempotent (safe to re-run)
- Dry-run by default

PLATE-owned doc directories:
- adr/, audits/, bootstrap/, design/, marketing/, migration/, research/, wiki/

PLATE-owned root doc files (only if they match template content):
- README.md (must contain "# Documentation Index" and "playwright-e2e-guide.md")
- playwright-e2e-guide.md (must contain template title)

Never moved or overwritten:
- AGENTS.md, SPEC.md, CURRENT.md (stale references reported for manual correction)
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

from .payload_surface import PLATE_DOCS_SUBDIRS, is_plate_owned_root_doc

# PLATE-owned doc directories that should be moved
PLATE_DOC_DIRS = sorted(PLATE_DOCS_SUBDIRS)

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
    return is_plate_owned_root_doc(path)


def _is_plate_playwright_guide(path: Path) -> bool:
    """Check if playwright-e2e-guide.md is the PLATE template version."""
    return is_plate_owned_root_doc(path)


def _find_files_matching_patterns(
    target_dir: Path, patterns: list[str]
) -> list[Path]:
    """Find all files matching the given glob patterns."""
    found = []
    for pattern in patterns:
        found.extend(target_dir.glob(pattern))
    return sorted(set(found))


def _update_references_in_file(
    file_path: Path, root_files_moved: list[str], dirs_moved: list[str], dry_run: bool = True
) -> tuple[bool, int]:
    """Update doc/ references to docs/plate/ in a file.
    
    Args:
        file_path: File to update
        root_files_moved: List of root files being moved (e.g. ["README.md", "playwright-e2e-guide.md"])
        dirs_moved: List of directories actually moved (e.g. ["design", "wiki"])
        dry_run: If True, do not write changes
    
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
    
    # Update references for each actually-moved PLATE doc directory
    for plate_dir in dirs_moved:
        # Match paths like docs/design/ or docs/design or `docs/design with proper boundaries.
        # Use negative lookahead (?![\w/-]) instead of \b to prevent false matches on
        # hyphenated siblings like docs/design-system or docs/wiki-archive.
        patterns = [
            # Match docs/design/ (with trailing slash)
            (rf"\bdocs/{plate_dir}/", rf"docs/plate/{plate_dir}/"),
            # Match docs/design (without trailing slash or another path segment)
            (rf"\bdocs/{plate_dir}(?![\w/-])", rf"docs/plate/{plate_dir}"),
            # Match `docs/design/ (backtick + path with slash)
            (rf"`docs/{plate_dir}/", rf"`docs/plate/{plate_dir}/"),
            # Match `docs/design (backtick + path without slash or another segment)
            (rf"`docs/{plate_dir}(?![\w/-])", rf"`docs/plate/{plate_dir}"),
        ]
        for old_pattern, new_pattern in patterns:
            new_content, n = re.subn(old_pattern, new_pattern, content)
            if n > 0:
                content = new_content
                count += n
    
    # Update references for moved root files (docs/README.md, docs/playwright-e2e-guide.md)
    for root_file in root_files_moved:
        # Match various reference forms:
        # - docs/playwright-e2e-guide.md
        # - `docs/playwright-e2e-guide.md`
        # - docs/playwright-e2e-guide.md) (markdown link)
        # - ../docs/playwright-e2e-guide.md (relative from subdirs)
        # Escape the filename and add terminal boundary to avoid matching
        # docs/README.md.bak or docs/READMEXmd
        # Use (?![\w/.-]) to prevent matching extensions like .bak
        escaped_file = re.escape(root_file)
        patterns = [
            (rf"docs/{escaped_file}(?![\w/.-])", rf"docs/plate/{root_file}"),
            (rf"`docs/{escaped_file}(?![\w/.-])", rf"`docs/plate/{root_file}"),
            (rf"\.\./docs/{escaped_file}(?![\w/.-])", rf"../docs/plate/{root_file}"),
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


def _is_protected_file(file_path: Path, target_dir: Path) -> bool:
    """Check if a file is protected from automatic modification.
    
    Protected files: AGENTS.md, SPEC.md, CURRENT.md, and product docs.
    """
    rel_path = file_path.relative_to(target_dir)
    protected_names = {"AGENTS.md", "SPEC.md", "CURRENT.md"}
    return rel_path.name in protected_names or str(rel_path) in protected_names


def _find_stale_references_in_file(
    file_path: Path, root_files_moved: list[str], dirs_moved: list[str]
) -> list[tuple[int, str, str]]:
    """Find stale references to moved files/dirs in a protected file.
    
    Args:
        file_path: Protected file to scan
        root_files_moved: Root files being moved (e.g. ["README.md", "playwright-e2e-guide.md"])
        dirs_moved: Directories being moved (e.g. ["design", "wiki"])
    
    Returns list of (line_number, old_ref, new_ref) tuples.
    """
    if not file_path.exists():
        return []
    
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    
    stale_refs = []
    for i, line in enumerate(lines, start=1):
        # Check for root file references using boundary-aware regex
        for root_file in root_files_moved:
            # Use terminal-boundary regex to avoid false matches like docs/README.md.bak
            # Pattern matches docs/README.md but NOT docs/README.md.bak or docs/READMEXmd
            pattern = rf"\bdocs/{re.escape(root_file)}(?![\w/.-])"
            
            # Find all matches in the line
            for match in re.finditer(pattern, line):
                old_ref = match.group(0)
                new_ref = f"docs/plate/{root_file}"
                
                # Report each old reference found (don't suppress if new also exists)
                if (i, old_ref, new_ref) not in stale_refs:
                    stale_refs.append((i, old_ref, new_ref))
        
        # Check for directory references
        for dir_name in dirs_moved:
            # Use terminal-boundary regex to avoid false matches like docs/wiki-system
            # Match docs/design/ (with slash) or docs/design (at path terminator)
            # Pattern matches either:
            # - docs/design followed by / (for docs/design/)
            # - docs/design NOT followed by word char, ., or - (for bare docs/design)
            # This prevents matching docs/design-system or docs/design.md
            pattern = rf"\bdocs/{re.escape(dir_name)}(?:/|(?![\w.-]))"
            replacement_base = f"docs/plate/{dir_name}"
            
            # Find all matches in the line
            for match in re.finditer(pattern, line):
                matched_text = match.group(0)
                # Determine the replacement (add slash if original had it)
                if matched_text.endswith("/"):
                    old_ref = matched_text
                    new_ref = replacement_base + "/"
                else:
                    old_ref = matched_text
                    new_ref = replacement_base
                
                # Report each old reference found (don't suppress if new also exists)
                # Only add if not already in the list for this line
                if (i, old_ref, new_ref) not in stale_refs:
                    stale_refs.append((i, old_ref, new_ref))
    
    return stale_refs


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


def _files_are_identical_after_transform(source_file: Path, target_file: Path) -> bool:
    """Check if source file matches target after link transformation.
    
    For README files moved from docs/ to docs/plate/, relative links like
    ../AGENTS.md should become ../../AGENTS.md in the target.
    
    Returns True if target is the transformed equivalent of source.
    """
    if not (source_file.exists() and target_file.exists()):
        return False
    
    try:
        source_content = source_file.read_text(encoding="utf-8")
        target_content = target_file.read_text(encoding="utf-8")
        
        # Apply the expected transformation to source
        expected_target = _rewrite_relative_links(source_content)
        
        # Compare transformed source with actual target
        return expected_target == target_content
    except (OSError, UnicodeDecodeError):
        return False


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
                    plan.errors.append(
                        f"Conflict: both docs/{plate_dir}/ and docs/plate/{plate_dir}/ exist with different contents"
                    )
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
            # Both exist - check if target is the transformed equivalent of source
            if _files_are_identical_after_transform(readme_path, target_readme):
                plan.actions.append(
                    MigrationAction(
                        action_type="skip",
                        source="docs/README.md",
                        target="docs/plate/README.md",
                        reason="Identical after transformation - will reconcile by removing source",
                    )
                )
            else:
                # Different content - conflict
                plan.actions.append(
                    MigrationAction(
                        action_type="conflict",
                        source="docs/README.md",
                        target="docs/plate/README.md",
                        reason="Both exist with different content - manual resolution needed",
                    )
                )
                plan.ok = False
                plan.errors.append(
                    "Conflict: both docs/README.md and docs/plate/README.md exist with different content"
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
            # Both exist - check if identical (no link transformation for this file)
            try:
                source_content = playwright_guide.read_bytes()
                target_content = target_guide.read_bytes()
                if source_content == target_content:
                    plan.actions.append(
                        MigrationAction(
                            action_type="skip",
                            source="docs/playwright-e2e-guide.md",
                            target="docs/plate/playwright-e2e-guide.md",
                            reason="Identical duplicate - will reconcile by removing source",
                        )
                    )
                else:
                    # Different content - conflict
                    plan.actions.append(
                        MigrationAction(
                            action_type="conflict",
                            source="docs/playwright-e2e-guide.md",
                            target="docs/plate/playwright-e2e-guide.md",
                            reason="Both exist with different content - manual resolution needed",
                        )
                    )
                    plan.ok = False
                    plan.errors.append(
                        "Conflict: both docs/playwright-e2e-guide.md and docs/plate/playwright-e2e-guide.md exist with different content"
                    )
            except (OSError, UnicodeDecodeError):
                # Can't read - treat as conflict
                plan.actions.append(
                    MigrationAction(
                        action_type="conflict",
                        source="docs/playwright-e2e-guide.md",
                        target="docs/plate/playwright-e2e-guide.md",
                        reason="Cannot compare files - manual resolution needed",
                    )
                )
                plan.ok = False
                plan.errors.append(
                    "Conflict: cannot compare docs/playwright-e2e-guide.md and docs/plate/playwright-e2e-guide.md"
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
    
    # Determine which root files and directories are being moved
    root_files_moved = []
    dirs_moved = []
    for action in plan.actions:
        if action.action_type in ("move_file", "skip"):
            # Extract filename from source like "docs/README.md" or "docs/playwright-e2e-guide.md"
            if action.source.startswith("docs/") and "/" not in action.source[5:]:
                # It's a root file like docs/README.md
                filename = action.source.split("/", 1)[1]
                if filename not in root_files_moved:
                    root_files_moved.append(filename)
        if action.action_type in ("move_dir", "skip"):
            # Extract directory name from source like "docs/design/"
            if action.source.startswith("docs/") and action.source.endswith("/"):
                dir_name = action.source[5:-1]  # Remove "docs/" prefix and trailing "/"
                if dir_name not in dirs_moved:
                    dirs_moved.append(dir_name)
    
    # Plan reference updates
    ref_files = _find_files_matching_patterns(target_path, REFERENCE_FILES)
    for ref_file in ref_files:
        relative = ref_file.relative_to(target_path)
        # Skip if the file doesn't exist or is not a file
        if not ref_file.is_file():
            continue
        
        # Check if this is a protected file
        if _is_protected_file(ref_file, target_path):
            # For protected files, find stale references but don't update them
            stale_refs = _find_stale_references_in_file(ref_file, root_files_moved, dirs_moved)
            if stale_refs:
                # Group by unique (old, new) pairs
                unique_refs = {}
                for line_num, old, new in stale_refs:
                    key = (old, new)
                    if key not in unique_refs:
                        unique_refs[key] = []
                    unique_refs[key].append(line_num)
                
                for (old, new), lines in unique_refs.items():
                    plan.actions.append(
                        MigrationAction(
                            action_type="manual_followup",
                            source=str(relative),
                            target=None,
                            reason=f"Lines {', '.join(map(str, lines))}: {old} → {new}",
                        )
                    )
        else:
            # Check if file has references that need updating
            # Use the computed dirs_moved set so the plan matches what apply will execute
            changed, count = _update_references_in_file(
                ref_file, root_files_moved, dirs_moved, dry_run=True
            )
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
    
    # Preflight check: verify all moves and reconciliations are possible before doing anything
    move_actions = [
        a for a in plan.actions
        if a.action_type in ("move_dir", "move_file")
    ]
    # Also check skip actions that involve reconciliation (source removal)
    reconcile_actions = [
        a for a in plan.actions
        if a.action_type == "skip" and "reconcile by removing source" in a.reason
    ]

    affected_actions = [
        a for a in plan.actions
        if a.action_type in ("move_dir", "move_file", "update_refs", "rewrite_links")
        or a in reconcile_actions
    ]
    for action in affected_actions:
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                action.source,
            ],
            cwd=target_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0:
            plan.ok = False
            plan.errors.append(
                f"Preflight failed: cannot check status for {action.source}: {status.stderr.strip()}"
            )
            return plan
        status_lines = status.stdout.splitlines()
        source_action = action.action_type in ("move_dir", "move_file") or action in reconcile_actions
        if status_lines and source_action:
            # Any status output (including untracked files) fails preflight for moves/reconciliations.
            # This prevents silently moving/deleting untracked content alongside tracked files.
            plan.ok = False
            plan.errors.append(
                f"Preflight failed: {action.source} contains uncommitted or untracked content. "
                f"Commit or stash changes before migrating."
            )
            return plan
        if status_lines:
            plan.ok = False
            plan.errors.append(
                f"Preflight failed: planned path has pre-existing changes: {action.source}"
            )
            return plan
    
    for action in move_actions:
        source_path = target_path / action.source
        if not source_path.exists():
            plan.ok = False
            plan.errors.append(f"Preflight failed: source does not exist: {action.source}")
            return plan
        target_path_full = target_path / action.target
        if target_path_full.exists():
            plan.ok = False
            plan.errors.append(
                f"Preflight failed: destination already exists: {action.target}"
            )
            return plan
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", action.source],
            cwd=target_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if tracked.returncode != 0:
            plan.ok = False
            plan.errors.append(
                f"Preflight failed: source is not tracked by Git: {action.source}"
            )
            return plan
    
    # Preflight reconciliation actions (source removal for identical duplicates)
    for action in reconcile_actions:
        source_path = target_path / action.source
        if not source_path.exists():
            plan.ok = False
            plan.errors.append(f"Preflight failed: reconciliation source does not exist: {action.source}")
            return plan
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", action.source],
            cwd=target_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if tracked.returncode != 0:
            plan.ok = False
            plan.errors.append(
                f"Preflight failed: reconciliation source is not tracked by Git: {action.source}"
            )
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
            # Handle reconciliation of identical duplicates (dirs and files)
            if "Identical" in action.reason and "reconcile by removing source" in action.reason:
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
                    plan.ok = False
                
        elif action.action_type == "update_refs":
            # Determine which root files are being moved (needed for reference updates)
            root_files_moved = []
            for a in plan.actions:
                if a.action_type in ("move_file", "skip"):
                    if a.source.startswith("docs/") and "/" not in a.source[5:]:
                        filename = a.source.split("/", 1)[1]
                        if filename not in root_files_moved:
                            root_files_moved.append(filename)
            
            # Determine which directories were actually moved or reconciled
            dirs_moved = []
            for a in plan.actions:
                if a.action_type == "move_dir":
                    # Extract dir name from source like "docs/design/"
                    dir_name = a.source.replace("docs/", "").rstrip("/")
                    if dir_name and dir_name not in dirs_moved:
                        dirs_moved.append(dir_name)
                elif a.action_type == "skip" and "reconcile by removing source" in a.reason:
                    # Extract dir name from source like "docs/wiki/"
                    dir_name = a.source.replace("docs/", "").rstrip("/")
                    if dir_name and dir_name not in dirs_moved:
                        dirs_moved.append(dir_name)
            
            file_path = target_path / action.source
            try:
                changed, count = _update_references_in_file(
                    file_path, root_files_moved, dirs_moved, dry_run=False
                )
                if changed:
                    # Stage the updated file
                    subprocess.run(
                        ["git", "add", str(file_path)],
                        cwd=target_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                elif not changed:
                    plan.warnings.append(
                        f"Expected to update {action.source} but no changes made"
                    )
            except subprocess.CalledProcessError as e:
                plan.errors.append(
                    f"Failed to stage {action.source}: {e.stderr}"
                )
                plan.ok = False
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
