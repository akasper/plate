"""Tests for migrate_docs_namespace (#1027)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from plate_core.migrate_docs_namespace import (
    _is_plate_readme,
    _is_plate_playwright_guide,
    migrate_docs_namespace,
    plan_migration,
)


def create_temp_repo() -> Path:
    """Create a temporary git repo for testing."""
    tmp_dir = tempfile.mkdtemp()
    repo = Path(tmp_dir) / "test-repo"
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


def create_repo_with_plate_docs(repo: Path) -> None:
    """Create PLATE docs at docs/ root in the given repo."""
    docs = repo / "docs"
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
    (repo / "AGENTS.md").write_text(
        "# Agents\n\n"
        "See docs/design/ for architecture.\n"
        "See docs/wiki/ for guides.\n"
        "Also check `docs/research/` for findings.\n"
    )
    
    # Initial commit
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


class TestPlateFileDetection(unittest.TestCase):
    """Tests for PLATE file detection functions."""
    
    def test_is_plate_readme(self):
        """Test PLATE README detection."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
            # PLATE README
            tmp_path.write_text(
                "# Documentation Index\n\n"
                "See playwright-e2e-guide.md for testing.\n"
            )
            self.assertTrue(_is_plate_readme(tmp_path))
            
            # Product README
            tmp_path.write_text("# My Product Docs\n\nDifferent content.\n")
            self.assertFalse(_is_plate_readme(tmp_path))
            
            # Cleanup
            tmp_path.unlink()

    def test_is_plate_playwright_guide(self):
        """Test PLATE playwright guide detection."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
            # PLATE guide
            tmp_path.write_text(
                "# Playwright E2E Testing & Demo GIF Generation Guide\n\n"
                "Example guide.\n"
            )
            self.assertTrue(_is_plate_playwright_guide(tmp_path))
            
            # Custom guide
            tmp_path.write_text("# My Custom Testing Guide\n\nDifferent content.\n")
            self.assertFalse(_is_plate_playwright_guide(tmp_path))
            
            # Cleanup
            tmp_path.unlink()


class TestMigrationPlanning(unittest.TestCase):
    """Tests for migration planning."""
    
    def test_plan_migration_empty_repo(self):
        """Test planning migration on empty repo."""
        repo = create_temp_repo()
        try:
            plan = plan_migration(repo)
            
            self.assertTrue(plan.ok)
            self.assertGreater(len(plan.warnings), 0)
            self.assertIn("No docs/ directory found", plan.warnings[0])
            self.assertEqual(len(plan.actions), 0)
        finally:
            import shutil
            shutil.rmtree(repo.parent)

    def test_plan_migration_with_plate_docs(self):
        """Test planning migration on repo with PLATE docs."""
        repo = create_temp_repo()
        create_repo_with_plate_docs(repo)
        try:
            plan = plan_migration(repo)
    
            self.assertTrue(plan.ok)
            self.assertEqual(len(plan.errors), 0)
            
            # Should have move actions for PLATE directories
            move_dirs = [a for a in plan.actions if a.action_type == "move_dir"]
            self.assertEqual(len(move_dirs), 4)  # design, wiki, research, audits
            
            dir_sources = {a.source for a in move_dirs}
            self.assertIn("docs/design/", dir_sources)
            self.assertIn("docs/wiki/", dir_sources)
            self.assertIn("docs/research/", dir_sources)
            self.assertIn("docs/audits/", dir_sources)
            
            # Should have move actions for PLATE root files
            move_files = [a for a in plan.actions if a.action_type == "move_file"]
            self.assertEqual(len(move_files), 2)  # README.md, playwright-e2e-guide.md
            
            file_sources = {a.source for a in move_files}
            self.assertIn("docs/README.md", file_sources)
            self.assertIn("docs/playwright-e2e-guide.md", file_sources)
            
            # Should have reference updates
            update_refs = [a for a in plan.actions if a.action_type == "update_refs"]
            self.assertGreater(len(update_refs), 0)
            
            # AGENTS.md should be in reference updates
            ref_sources = {a.source for a in update_refs}
            self.assertIn("AGENTS.md", ref_sources)
        finally:
            import shutil
            shutil.rmtree(repo.parent)


class TestMigrationApplication(unittest.TestCase):
    """Tests for migration application."""
    
    def test_apply_migration(self):
        """Test applying migration."""
        repo = create_temp_repo()
        create_repo_with_plate_docs(repo)
        try:
            # Apply migration
            plan = migrate_docs_namespace(target_dir=repo, apply=True)
            
            self.assertTrue(plan.ok)
            self.assertEqual(len(plan.errors), 0)
            
            # Check that PLATE directories were moved
            docs_plate = repo / "docs" / "plate"
            self.assertTrue(docs_plate.exists())
            self.assertTrue((docs_plate / "design").exists())
            self.assertTrue((docs_plate / "wiki").exists())
            self.assertTrue((docs_plate / "research").exists())
            self.assertTrue((docs_plate / "audits").exists())
            
            # Check that old directories are gone
            docs = repo / "docs"
            self.assertFalse((docs / "design").exists())
            self.assertFalse((docs / "wiki").exists())
            self.assertFalse((docs / "research").exists())
            self.assertFalse((docs / "audits").exists())
            
            # Check that PLATE files were moved
            self.assertTrue((docs_plate / "README.md").exists())
            self.assertTrue((docs_plate / "playwright-e2e-guide.md").exists())
            
            # Check that product docs are still at root
            self.assertTrue((docs / "api").exists())
            self.assertTrue((docs / "api" / "index.md").exists())
            
            # Check that references were updated
            agents_content = (repo / "AGENTS.md").read_text()
            self.assertIn("docs/plate/design/", agents_content)
            self.assertIn("docs/plate/wiki/", agents_content)
            self.assertIn("docs/plate/research/", agents_content)
            # Old references should be gone
            self.assertNotIn("docs/design/", agents_content.replace("docs/plate/design/", ""))
        finally:
            import shutil
            shutil.rmtree(repo.parent)


    def test_migration_preserves_customized_files(self):
        """Test that customized files are preserved."""
        repo = create_temp_repo()
        create_repo_with_plate_docs(repo)
        try:
            # Create customized SPEC.md
            (repo / "SPEC.md").write_text(
                "# Product Spec\n\nSee docs/design/ for architecture.\n"
            )
            
            # Apply migration
            plan = migrate_docs_namespace(target_dir=repo, apply=True)
            
            self.assertTrue(plan.ok)
            
            # Check that SPEC.md still exists at root (not moved)
            self.assertTrue((repo / "SPEC.md").exists())
            
            # Check that its references were updated
            spec_content = (repo / "SPEC.md").read_text()
            self.assertIn("docs/plate/design/", spec_content)
            
            # AGENTS.md should also be preserved at root with updated refs
            self.assertTrue((repo / "AGENTS.md").exists())
            agents_content = (repo / "AGENTS.md").read_text()
            self.assertIn("docs/plate/design/", agents_content)
        finally:
            import shutil
            shutil.rmtree(repo.parent)

    def test_migration_idempotent(self):
        """Test that migration is idempotent."""
        repo = create_temp_repo()
        create_repo_with_plate_docs(repo)
        try:
            # First migration
            plan1 = migrate_docs_namespace(target_dir=repo, apply=True)
            self.assertTrue(plan1.ok)
            
            # Second migration (should skip move operations)
            plan2 = migrate_docs_namespace(target_dir=repo, apply=True)
            self.assertTrue(plan2.ok)
            
            # No new move actions should be attempted (only skips and maybe ref updates)
            move_actions = [
                a for a in plan2.actions
                if a.action_type in ("move_dir", "move_file")
            ]
            self.assertEqual(len(move_actions), 0)
            
            # May have skip actions or no actions at all if refs already updated
            # The important thing is no errors and no moves
            self.assertEqual(len(plan2.errors), 0)
        finally:
            import shutil
            shutil.rmtree(repo.parent)

    def test_migration_no_duplicates(self):
        """Test that migration leaves no duplicates."""
        repo = create_temp_repo()
        create_repo_with_plate_docs(repo)
        try:
            # Apply migration
            plan = migrate_docs_namespace(target_dir=repo, apply=True)
            self.assertTrue(plan.ok)
            
            docs = repo / "docs"
            
            # Check that no PLATE directories exist at docs/ root
            for plate_dir in ["design", "wiki", "research", "audits", "adr", 
                              "bootstrap", "marketing", "migration"]:
                self.assertFalse((docs / plate_dir).exists(), 
                                f"Duplicate: docs/{plate_dir}/ still exists")
            
            # Check that all PLATE directories are only under docs/plate/
            docs_plate = docs / "plate"
            for plate_dir in ["design", "wiki", "research", "audits"]:
                self.assertTrue((docs_plate / plate_dir).exists(), 
                               f"Missing: docs/plate/{plate_dir}/")
        finally:
            import shutil
            shutil.rmtree(repo.parent)

    def test_plan_migration_non_git_repo(self):
        """Test that planning fails for non-git repo."""
        tmp_dir = tempfile.mkdtemp()
        try:
            # Create a directory without git init
            non_git_repo = Path(tmp_dir) / "non-git"
            non_git_repo.mkdir()
            
            plan = plan_migration(non_git_repo)
            
            self.assertFalse(plan.ok)
            self.assertGreater(len(plan.errors), 0)
            self.assertIn("Not a git repository", plan.errors[0])
        finally:
            import shutil
            shutil.rmtree(tmp_dir)

    def test_migration_with_product_readme(self):
        """Test that product README is not moved."""
        repo = create_temp_repo()
        try:
            docs = repo / "docs"
            docs.mkdir()
            
            # Create PLATE doc directory
            (docs / "design").mkdir()
            (docs / "design" / "example.md").write_text("# Design\n")
            
            # Create product README (not PLATE template)
            (docs / "README.md").write_text("# My Product Documentation\n\nDifferent content.\n")
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            
            # Plan migration
            plan = plan_migration(repo)
            
            # Should only move design/, not README.md
            move_dirs = [a for a in plan.actions if a.action_type == "move_dir"]
            self.assertEqual(len(move_dirs), 1)
            self.assertEqual(move_dirs[0].source, "docs/design/")
            
            move_files = [a for a in plan.actions if a.action_type == "move_file"]
            readme_moves = [a for a in move_files if "README.md" in a.source]
            self.assertEqual(len(readme_moves), 0)  # Product README should not be moved
        finally:
            import shutil
            shutil.rmtree(repo.parent)

    def test_dry_run_makes_no_changes(self):
        """Test that dry-run doesn't modify anything."""
        repo = create_temp_repo()
        create_repo_with_plate_docs(repo)
        try:
            # Get initial state
            docs = repo / "docs"
            design_exists_before = (docs / "design").exists()
            plate_exists_before = (docs / "plate").exists()
            
            # Dry-run migration
            plan = migrate_docs_namespace(target_dir=repo, apply=False)
            
            self.assertTrue(plan.ok)
            self.assertFalse(plan.apply_mode)
            
            # Check state unchanged
            self.assertEqual((docs / "design").exists(), design_exists_before)
            self.assertEqual((docs / "plate").exists(), plate_exists_before)
            
            # AGENTS.md should still have old references
            agents_content = (repo / "AGENTS.md").read_text()
            self.assertIn("docs/design/", agents_content)
            self.assertNotIn("docs/plate/design/", agents_content)
        finally:
            import shutil
            shutil.rmtree(repo.parent)


if __name__ == '__main__':
    unittest.main()
