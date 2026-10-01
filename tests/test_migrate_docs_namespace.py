"""Tests for migrate_docs_namespace (#1027)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plate_core.migrate_docs_namespace import (
    _is_plate_readme,
    _is_plate_playwright_guide,
    migrate_docs_namespace,
    plan_migration,
)


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary git repo for testing."""
    repo = tmp_path / "test-repo"
    repo.mkdir()
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    
    return repo


@pytest.fixture
def repo_with_plate_docs(temp_repo: Path) -> Path:
    """Create a repo with PLATE docs at docs/ root."""
    docs = temp_repo / "docs"
    docs.mkdir()
    
    # Create PLATE doc directories
    for plate_dir in ["design", "wiki", "research", "audits"]:
        plate_path = docs / plate_dir
        plate_path.mkdir()
        (plate_path / "example.md").write_text(f"# {plate_dir.title()}\n\nExample content.\n")
    
    # Create PLATE README
    (docs / "README.md").write_text(
        "# Documentation Index\n\n"
        "See playwright-e2e-guide.md for testing.\n"
    )
    
    # Create PLATE playwright guide
    (docs / "playwright-e2e-guide.md").write_text(
        "# Playwright E2E Testing & Demo GIF Generation Guide\n\n"
        "Example guide.\n"
    )
    
    # Create product docs (should not be moved)
    (docs / "api").mkdir()
    (docs / "api" / "index.md").write_text("# API Docs\n")
    
    # Create AGENTS.md with references
    (temp_repo / "AGENTS.md").write_text(
        "# Agents\n\n"
        "See docs/design/ for architecture.\n"
        "See docs/wiki/ for guides.\n"
        "Also check `docs/research/` for findings.\n"
    )
    
    # Initial commit
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )
    
    return temp_repo


def test_is_plate_readme():
    """Test PLATE README detection."""
    tmp = Path("/tmp/test_readme.md")
    
    # PLATE README
    tmp.write_text(
        "# Documentation Index\n\n"
        "See playwright-e2e-guide.md for testing.\n"
    )
    assert _is_plate_readme(tmp)
    
    # Product README
    tmp.write_text("# My Product Docs\n\nDifferent content.\n")
    assert not _is_plate_readme(tmp)
    
    # Cleanup
    tmp.unlink()


def test_is_plate_playwright_guide():
    """Test PLATE playwright guide detection."""
    tmp = Path("/tmp/test_guide.md")
    
    # PLATE guide
    tmp.write_text(
        "# Playwright E2E Testing & Demo GIF Generation Guide\n\n"
        "Example guide.\n"
    )
    assert _is_plate_playwright_guide(tmp)
    
    # Custom guide
    tmp.write_text("# My Custom Testing Guide\n\nDifferent content.\n")
    assert not _is_plate_playwright_guide(tmp)
    
    # Cleanup
    tmp.unlink()


def test_plan_migration_empty_repo(temp_repo: Path):
    """Test planning migration on empty repo."""
    plan = plan_migration(temp_repo)
    
    assert plan.ok
    assert len(plan.warnings) > 0
    assert "No docs/ directory found" in plan.warnings[0]
    assert len(plan.actions) == 0


def test_plan_migration_with_plate_docs(repo_with_plate_docs: Path):
    """Test planning migration on repo with PLATE docs."""
    plan = plan_migration(repo_with_plate_docs)
    
    assert plan.ok
    assert len(plan.errors) == 0
    
    # Should have move actions for PLATE directories
    move_dirs = [a for a in plan.actions if a.action_type == "move_dir"]
    assert len(move_dirs) == 4  # design, wiki, research, audits
    
    dir_sources = {a.source for a in move_dirs}
    assert "docs/design/" in dir_sources
    assert "docs/wiki/" in dir_sources
    assert "docs/research/" in dir_sources
    assert "docs/audits/" in dir_sources
    
    # Should have move actions for PLATE root files
    move_files = [a for a in plan.actions if a.action_type == "move_file"]
    assert len(move_files) == 2  # README.md, playwright-e2e-guide.md
    
    file_sources = {a.source for a in move_files}
    assert "docs/README.md" in file_sources
    assert "docs/playwright-e2e-guide.md" in file_sources
    
    # Should have reference updates
    update_refs = [a for a in plan.actions if a.action_type == "update_refs"]
    assert len(update_refs) > 0
    
    # AGENTS.md should be in reference updates
    ref_sources = {a.source for a in update_refs}
    assert "AGENTS.md" in ref_sources


def test_apply_migration(repo_with_plate_docs: Path):
    """Test applying migration."""
    # Apply migration
    plan = migrate_docs_namespace(target_dir=repo_with_plate_docs, apply=True)
    
    assert plan.ok
    assert len(plan.errors) == 0
    
    # Check that PLATE directories were moved
    docs_plate = repo_with_plate_docs / "docs" / "plate"
    assert docs_plate.exists()
    assert (docs_plate / "design").exists()
    assert (docs_plate / "wiki").exists()
    assert (docs_plate / "research").exists()
    assert (docs_plate / "audits").exists()
    
    # Check that old directories are gone
    docs = repo_with_plate_docs / "docs"
    assert not (docs / "design").exists()
    assert not (docs / "wiki").exists()
    assert not (docs / "research").exists()
    assert not (docs / "audits").exists()
    
    # Check that PLATE files were moved
    assert (docs_plate / "README.md").exists()
    assert (docs_plate / "playwright-e2e-guide.md").exists()
    
    # Check that product docs are still at root
    assert (docs / "api").exists()
    assert (docs / "api" / "index.md").exists()
    
    # Check that references were updated
    agents_content = (repo_with_plate_docs / "AGENTS.md").read_text()
    assert "docs/plate/design/" in agents_content
    assert "docs/plate/wiki/" in agents_content
    assert "docs/plate/research/" in agents_content
    # Old references should be gone
    assert "docs/design/" not in agents_content or "docs/plate/design/" in agents_content
    assert "docs/wiki/" not in agents_content or "docs/plate/wiki/" in agents_content


def test_migration_preserves_customized_files(repo_with_plate_docs: Path):
    """Test that customized files are preserved."""
    # Create customized SPEC.md
    (repo_with_plate_docs / "SPEC.md").write_text(
        "# Product Spec\n\nSee docs/design/ for architecture.\n"
    )
    
    # Create customized CURRENT.md
    (repo_with_plate_docs / "CURRENT.md").write_text(
        "# Current State\n\nSee docs/wiki/ for guides.\n"
    )
    
    # Apply migration
    plan = migrate_docs_namespace(target_dir=repo_with_plate_docs, apply=True)
    
    assert plan.ok
    
    # Check that SPEC.md and CURRENT.md still exist at root
    assert (repo_with_plate_docs / "SPEC.md").exists()
    assert (repo_with_plate_docs / "CURRENT.md").exists()
    
    # Check that their references were updated
    spec_content = (repo_with_plate_docs / "SPEC.md").read_text()
    assert "docs/plate/design/" in spec_content
    
    current_content = (repo_with_plate_docs / "CURRENT.md").read_text()
    assert "docs/plate/wiki/" in current_content


def test_migration_idempotent(repo_with_plate_docs: Path):
    """Test that migration is idempotent."""
    # First migration
    plan1 = migrate_docs_namespace(target_dir=repo_with_plate_docs, apply=True)
    assert plan1.ok
    
    # Second migration (should skip everything)
    plan2 = migrate_docs_namespace(target_dir=repo_with_plate_docs, apply=True)
    assert plan2.ok
    
    # All actions should be skips
    move_actions = [
        a for a in plan2.actions
        if a.action_type in ("move_dir", "move_file")
    ]
    assert len(move_actions) == 0
    
    skip_actions = [a for a in plan2.actions if a.action_type == "skip"]
    # Should have at least some skip actions for dirs/files already moved
    assert len(skip_actions) > 0


def test_migration_no_duplicates(repo_with_plate_docs: Path):
    """Test that migration leaves no duplicates."""
    # Apply migration
    plan = migrate_docs_namespace(target_dir=repo_with_plate_docs, apply=True)
    assert plan.ok
    
    docs = repo_with_plate_docs / "docs"
    
    # Check that no PLATE directories exist at docs/ root
    for plate_dir in ["design", "wiki", "research", "audits", "adr", "audits", 
                      "bootstrap", "marketing", "migration"]:
        assert not (docs / plate_dir).exists(), f"Duplicate: docs/{plate_dir}/ still exists"
    
    # Check that all PLATE directories are only under docs/plate/
    docs_plate = docs / "plate"
    for plate_dir in ["design", "wiki", "research", "audits"]:
        assert (docs_plate / plate_dir).exists(), f"Missing: docs/plate/{plate_dir}/"


def test_plan_migration_non_git_repo(tmp_path: Path):
    """Test that planning fails for non-git repo."""
    # Create a directory without git init
    non_git_repo = tmp_path / "non-git"
    non_git_repo.mkdir()
    
    plan = plan_migration(non_git_repo)
    
    assert not plan.ok
    assert len(plan.errors) > 0
    assert "Not a git repository" in plan.errors[0]


def test_migration_with_product_readme(temp_repo: Path):
    """Test that product README is not moved."""
    docs = temp_repo / "docs"
    docs.mkdir()
    
    # Create PLATE doc directory
    (docs / "design").mkdir()
    (docs / "design" / "example.md").write_text("# Design\n")
    
    # Create product README (not PLATE template)
    (docs / "README.md").write_text("# My Product Documentation\n\nDifferent content.\n")
    
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )
    
    # Plan migration
    plan = plan_migration(temp_repo)
    
    # Should only move design/, not README.md
    move_dirs = [a for a in plan.actions if a.action_type == "move_dir"]
    assert len(move_dirs) == 1
    assert move_dirs[0].source == "docs/design/"
    
    move_files = [a for a in plan.actions if a.action_type == "move_file"]
    readme_moves = [a for a in move_files if "README.md" in a.source]
    assert len(readme_moves) == 0  # Product README should not be moved


def test_dry_run_makes_no_changes(repo_with_plate_docs: Path):
    """Test that dry-run doesn't modify anything."""
    # Get initial state
    docs = repo_with_plate_docs / "docs"
    design_exists_before = (docs / "design").exists()
    plate_exists_before = (docs / "plate").exists()
    
    # Dry-run migration
    plan = migrate_docs_namespace(target_dir=repo_with_plate_docs, apply=False)
    
    assert plan.ok
    assert not plan.apply_mode
    
    # Check state unchanged
    assert (docs / "design").exists() == design_exists_before
    assert (docs / "plate").exists() == plate_exists_before
    
    # AGENTS.md should still have old references
    agents_content = (repo_with_plate_docs / "AGENTS.md").read_text()
    assert "docs/design/" in agents_content
    assert "docs/plate/design/" not in agents_content
