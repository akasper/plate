"""Tests for migrate_docs_namespace (#1027)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from plate_core.migrate_docs_namespace import (
    _is_plate_readme,
    _is_plate_playwright_guide,
    migrate_docs_namespace,
    plan_migration,
    apply_migration,
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
            
            # Should have manual followup for AGENTS.md (protected file)
            manual_followup = [a for a in plan.actions if a.action_type == "manual_followup"]
            followup_sources = {a.source for a in manual_followup}
            self.assertIn("AGENTS.md", followup_sources, "AGENTS.md should be in manual followup (protected)")
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
            
            # AGENTS.md is protected - check references were NOT updated
            agents_content = (repo / "AGENTS.md").read_text()
            # Old references should still be there (not updated)
            self.assertIn("docs/design/", agents_content)
            self.assertIn("docs/wiki/", agents_content)
            self.assertIn("docs/research/", agents_content)
            # Should have manual_followup actions for AGENTS.md
            followup = [a for a in plan.actions if a.action_type == "manual_followup" and "AGENTS.md" in a.source]
            self.assertGreater(len(followup), 0, "Should have manual followup actions for AGENTS.md")
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
            
            # SPEC.md is protected - references should NOT be updated
            spec_content = (repo / "SPEC.md").read_text()
            self.assertIn("docs/design/", spec_content, "SPEC.md should not be modified (protected)")
            
            # AGENTS.md is also protected - references should NOT be updated
            self.assertTrue((repo / "AGENTS.md").exists())
            agents_content = (repo / "AGENTS.md").read_text()
            self.assertIn("docs/design/", agents_content, "AGENTS.md should not be modified (protected)")
            
            # Should have manual_followup actions for both
            followup = [a for a in plan.actions if a.action_type == "manual_followup"]
            followup_sources = {a.source for a in followup}
            self.assertIn("SPEC.md", followup_sources, "Should list SPEC.md for manual followup")
            self.assertIn("AGENTS.md", followup_sources, "Should list AGENTS.md for manual followup")
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

    def test_template_payload_guide_sync(self):
        """Test that docs/migration guide is synced to template payload."""
        repo_guide = Path(__file__).parent.parent / "docs/migration/namespace-docs-migration.md"
        template_guide = (
            Path(__file__).parent.parent
            / "src/plate_core/template_payload/docs/migration/namespace-docs-migration.md"
        )
        
        self.assertTrue(repo_guide.exists(), "Repository migration guide not found")
        self.assertTrue(template_guide.exists(), "Template payload migration guide not found")
        
        repo_content = repo_guide.read_text(encoding="utf-8")
        template_content = template_guide.read_text(encoding="utf-8")
        
        self.assertEqual(
            repo_content,
            template_content,
            "Migration guide in template payload must match repository guide",
        )
    
    def test_duplicate_directories_conflict(self):
        """Test that duplicate directories with different contents are detected as conflict."""
        repo = create_temp_repo()
        try:
            # Create both docs/design/ and docs/plate/design/ with different content
            design_dir = repo / "docs/design"
            plate_design_dir = repo / "docs/plate/design"
            design_dir.mkdir(parents=True)
            plate_design_dir.mkdir(parents=True)
            
            (design_dir / "feature.md").write_text("# Original content", encoding="utf-8")
            (plate_design_dir / "feature.md").write_text("# Different content", encoding="utf-8")
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            
            plan = plan_migration(repo)
            
            # Should report conflict
            self.assertFalse(plan.ok, "Plan should fail with conflicting duplicates")
            conflict_actions = [a for a in plan.actions if a.action_type == "conflict"]
            self.assertGreater(len(conflict_actions), 0, "Should have conflict action")
            self.assertIn("design", conflict_actions[0].source)
        finally:
            import shutil
            shutil.rmtree(repo.parent)
    
    def test_duplicate_directories_reconciliation(self):
        """Test that identical duplicate directories are reconciled."""
        repo = create_temp_repo()
        try:
            # Create both docs/design/ and docs/plate/design/ with identical content
            design_dir = repo / "docs/design"
            plate_design_dir = repo / "docs/plate/design"
            design_dir.mkdir(parents=True)
            plate_design_dir.mkdir(parents=True)
            
            (design_dir / "feature.md").write_text("# Same content", encoding="utf-8")
            (plate_design_dir / "feature.md").write_text("# Same content", encoding="utf-8")
            (repo / "AGENTS.md").write_text("See docs/design/ for details.\n", encoding="utf-8")

            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add duplicates"], cwd=repo, check=True)
            
            plan = plan_migration(repo)
            
            # Should be OK and plan reconciliation
            self.assertTrue(plan.ok, "Plan should succeed with identical duplicates")
            skip_actions = [
                a for a in plan.actions 
                if a.action_type == "skip" and "Identical duplicate" in a.reason
            ]
            self.assertGreater(len(skip_actions), 0, "Should have reconciliation action")
            followups = [
                a for a in plan.actions
                if a.action_type == "manual_followup" and a.source == "AGENTS.md"
            ]
            self.assertGreater(
                len(followups),
                0,
                "Protected references to a reconciled directory should be reported",
            )
            
            # Apply and verify reconciliation
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Apply should succeed")
            self.assertFalse((repo / "docs/design").exists(), "Source should be removed")
            self.assertTrue(
                (repo / "docs/plate/design/feature.md").exists(),
                "Target should remain"
            )
        finally:
            import shutil
            shutil.rmtree(repo.parent)

    def test_untracked_later_move_fails_preflight_without_partial_migration(self):
        """Test that all move sources are preflighted before any move is applied."""
        repo = create_temp_repo()
        try:
            docs = repo / "docs"
            design_dir = docs / "design"
            wiki_dir = docs / "wiki"
            design_dir.mkdir(parents=True)
            wiki_dir.mkdir()
            (design_dir / "feature.md").write_text("# Tracked", encoding="utf-8")
            (wiki_dir / "guide.md").write_text("# Untracked", encoding="utf-8")

            subprocess.run(["git", "add", "docs/design"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add tracked design docs"], cwd=repo, check=True)

            result = apply_migration(repo)

            self.assertFalse(result.ok, "An untracked move source should fail preflight")
            self.assertTrue(
                any("not tracked by Git: docs/wiki/" in error for error in result.errors),
                "The preflight error should identify the untracked source",
            )
            self.assertTrue(design_dir.exists(), "Earlier tracked source must not be moved")
            self.assertFalse(
                (docs / "plate" / "design").exists(),
                "No earlier move should be applied before preflight completes",
            )
        finally:
            import shutil
            shutil.rmtree(repo.parent)
    
    def test_successful_migration_updates_references(self):
        """Test that successful migration updates references correctly."""
        repo = create_temp_repo()
        try:
            # Verify that a successful migration updates references in non-protected files
            design_dir = repo / "docs/design"
            design_dir.mkdir(parents=True)
            (design_dir / "feature.md").write_text("# Test", encoding="utf-8")
            
            # Use CONTRIBUTING.md instead of AGENTS.md (which is protected)
            contributing_path = repo / "CONTRIBUTING.md"
            contributing_path.write_text("See docs/design/ for details.", encoding="utf-8")
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add docs"], cwd=repo, check=True)
            
            # Migration should succeed and update references
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Migration should succeed")
            
            content = contributing_path.read_text(encoding="utf-8")
            self.assertIn("docs/plate/design/", content,
                         "References should be updated after successful migration in non-protected files")
            
            # Verify the move happened
            self.assertFalse((repo / "docs/design").exists(), "Source should be moved")
            self.assertTrue((repo / "docs/plate/design/feature.md").exists(), "Target should exist")
        finally:
            import shutil
            shutil.rmtree(repo.parent)
    
    def test_reference_updates_in_scripts(self):
        """Test that references in bootstrap scripts and migration.yml are updated."""
        repo = create_temp_repo()
        try:
            # Create scripts with references to docs/wiki/
            scripts_dir = repo / "scripts"
            scripts_dir.mkdir(parents=True)
            
            bootstrap_sh = scripts_dir / "bootstrap_github.sh"
            bootstrap_sh.write_text(
                'wiki_source="$LOCAL_REPO/docs/wiki/Home.md"\n'
                'echo "Initialized from docs/wiki/Home.md"\n',
                encoding="utf-8"
            )
            
            bootstrap_ps1 = scripts_dir / "BootstrapGitHub.ps1"
            bootstrap_ps1.write_text(
                'Write-Host "Initialized from docs/wiki/Home.md."\n',
                encoding="utf-8"
            )
            
            # Create migration.yml with references
            agentic_dir = repo / ".agentic"
            agentic_dir.mkdir(parents=True)
            migration_yml = agentic_dir / "migration.yml"
            migration_yml.write_text(
                'guides:\n  - docs/migration/guide.md\n  - docs/migration/checklist.md\n',
                encoding="utf-8"
            )
            
            # Create the referenced wiki dir
            wiki_dir = repo / "docs/wiki"
            wiki_dir.mkdir(parents=True)
            (wiki_dir / "Home.md").write_text("# Home", encoding="utf-8")
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add scripts"], cwd=repo, check=True)
            
            plan = plan_migration(repo)
            self.assertTrue(plan.ok, "Planning should succeed")
            
            # Check that update_refs actions include the scripts and migration.yml
            ref_actions = [a for a in plan.actions if a.action_type == "update_refs"]
            ref_sources = [a.source for a in ref_actions]
            
            self.assertIn("scripts/bootstrap_github.sh", ref_sources)
            self.assertIn("scripts/BootstrapGitHub.ps1", ref_sources)
            self.assertIn(".agentic/migration.yml", ref_sources)
            
            # Apply and verify
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Apply should succeed")
            
            # Check references were updated
            updated_sh = bootstrap_sh.read_text(encoding="utf-8")
            self.assertIn("docs/plate/wiki/Home.md", updated_sh)
            
            updated_ps1 = bootstrap_ps1.read_text(encoding="utf-8")
            self.assertIn("docs/plate/wiki/Home.md", updated_ps1)
            
            updated_yml = migration_yml.read_text(encoding="utf-8")
            self.assertIn("docs/plate/migration/guide.md", updated_yml)
        finally:
            import shutil
            shutil.rmtree(repo.parent)
    
    def test_readme_relative_link_rewriting(self):
        """Test that relative links in moved README are rewritten."""
        repo = create_temp_repo()
        try:
            # Create a PLATE README with relative links
            docs_dir = repo / "docs"
            docs_dir.mkdir(parents=True)
            readme = docs_dir / "README.md"
            readme.write_text(
                "# Documentation Index\n\n"
                "See [AGENTS.md](../AGENTS.md) for process.\n"
                "See [E2E Guide](../tests/e2e/README.md) for testing.\n"
                "See [playwright-e2e-guide.md](./playwright-e2e-guide.md) for Playwright.\n",
                encoding="utf-8"
            )
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add README"], cwd=repo, check=True)
            
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Apply should succeed")
            
            # Check that the moved README has rewritten links
            moved_readme = repo / "docs/plate/README.md"
            self.assertTrue(moved_readme.exists(), "README should be moved")
            
            content = moved_readme.read_text(encoding="utf-8")
            self.assertIn("](../../AGENTS.md)", content, "Should rewrite ../AGENTS.md")
            self.assertIn("](../../tests/e2e/README.md)", content, "Should rewrite ../tests/e2e")
            self.assertIn("](./playwright-e2e-guide.md)", content, "Should preserve same-dir link")
        finally:
            import shutil
            shutil.rmtree(repo.parent)
    
    def test_duplicate_readme_identical_after_transform(self):
        """Test that duplicate README files identical after transform are reconciled."""
        repo = create_temp_repo()
        try:
            # Create README at both locations with transform applied
            docs_dir = repo / "docs"
            plate_docs_dir = docs_dir / "plate"
            docs_dir.mkdir(parents=True)
            plate_docs_dir.mkdir(parents=True)
            
            # Source with original links (must have markers for _is_plate_readme)
            source_readme = docs_dir / "README.md"
            source_readme.write_text(
                "# Documentation Index\n\n"
                "See [playwright-e2e-guide.md](./playwright-e2e-guide.md) and [AGENTS.md](../AGENTS.md).\n",
                encoding="utf-8"
            )
            
            # Target with transformed links (../ -> ../../)
            target_readme = plate_docs_dir / "README.md"
            target_readme.write_text(
                "# Documentation Index\n\n"
                "See [playwright-e2e-guide.md](./playwright-e2e-guide.md) and [AGENTS.md](../../AGENTS.md).\n",
                encoding="utf-8"
            )
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add duplicates"], cwd=repo, check=True)
            
            plan = plan_migration(repo)
            self.assertTrue(plan.ok, "Plan should succeed with identical-after-transform duplicates")
            
            skip_actions = [
                a for a in plan.actions 
                if a.action_type == "skip" and "Identical after transformation" in a.reason
            ]
            self.assertEqual(len(skip_actions), 1, "Should have one reconciliation action for README")
            
            # Apply and verify reconciliation
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Apply should succeed")
            self.assertFalse((repo / "docs/README.md").exists(), "Source README should be removed")
            self.assertTrue((repo / "docs/plate/README.md").exists(), "Target README should remain")
        finally:
            import shutil
            shutil.rmtree(repo.parent)
    
    def test_duplicate_readme_conflict(self):
        """Test that duplicate README files with different content report conflict."""
        repo = create_temp_repo()
        try:
            # Create README at both locations with different content
            docs_dir = repo / "docs"
            plate_docs_dir = docs_dir / "plate"
            docs_dir.mkdir(parents=True)
            plate_docs_dir.mkdir(parents=True)
            
            # Must have markers for _is_plate_readme
            source_readme = docs_dir / "README.md"
            source_readme.write_text(
                "# Documentation Index\n\nOriginal content with playwright-e2e-guide.md reference.\n",
                encoding="utf-8"
            )
            
            target_readme = plate_docs_dir / "README.md"
            target_readme.write_text(
                "# Documentation Index\n\nDifferent content with playwright-e2e-guide.md reference.\n",
                encoding="utf-8"
            )
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add conflicting READMEs"], cwd=repo, check=True)
            
            plan = plan_migration(repo)
            
            # Should report conflict
            self.assertFalse(plan.ok, "Plan should fail with conflicting README duplicates")
            conflict_actions = [a for a in plan.actions if a.action_type == "conflict" and "README" in a.source]
            self.assertEqual(len(conflict_actions), 1, "Should have conflict action for README")
            self.assertIn("README", plan.errors[0], "Should have error about README conflict")
        finally:
            import shutil
            shutil.rmtree(repo.parent)


class TestModuleEntrypoint(unittest.TestCase):
    """Test that the module can be invoked with python -m."""
    
    def test_module_entrypoint_help(self):
        """Test that python -m plate_core.cli migrate-docs-namespace --help works."""
        result = subprocess.run(
            [sys.executable, "-m", "plate_core.cli", "migrate-docs-namespace", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, "Should exit with 0 for --help")
        self.assertIn("migrate-docs-namespace", result.stdout, "Should show command help")
        self.assertIn("--apply", result.stdout, "Should show --apply option")


class TestRootFileReferenceRewriting(unittest.TestCase):
    """Test reference rewriting for moved root files."""
    
    def test_root_file_references_updated(self):
        """Test that references to moved root files are updated."""
        repo = create_temp_repo()
        try:
            # Create PLATE README and playwright guide
            docs_dir = repo / "docs"
            docs_dir.mkdir(parents=True)
            
            readme = docs_dir / "README.md"
            readme.write_text(
                "# Documentation Index\n\nSee playwright-e2e-guide.md\n",
                encoding="utf-8"
            )
            
            guide = docs_dir / "playwright-e2e-guide.md"
            guide.write_text(
                "Playwright E2E Testing & Demo GIF Generation Guide\n",
                encoding="utf-8"
            )
            
            # Create a file that references the guide
            contributing = repo / "CONTRIBUTING.md"
            contributing.write_text(
                "See `docs/playwright-e2e-guide.md` for testing.\n"
                "Also see docs/playwright-e2e-guide.md) for more.\n",
                encoding="utf-8"
            )
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add docs"], cwd=repo, check=True)
            
            plan = plan_migration(repo)
            self.assertTrue(plan.ok, "Plan should succeed")
            
            # Should have update_refs action for CONTRIBUTING.md
            update_actions = [a for a in plan.actions if a.action_type == "update_refs"]
            update_sources = {a.source for a in update_actions}
            self.assertIn("CONTRIBUTING.md", update_sources, "Should update CONTRIBUTING.md")
            
            # Apply and verify
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Apply should succeed")
            
            # Check references were updated
            updated_content = contributing.read_text(encoding="utf-8")
            self.assertIn("docs/plate/playwright-e2e-guide.md", updated_content)
            self.assertNotIn("docs/playwright-e2e-guide.md", updated_content)
        finally:
            import shutil
            shutil.rmtree(repo.parent)
    
    def test_protected_files_not_modified(self):
        """Test that protected files (AGENTS.md, SPEC.md, CURRENT.md) are not modified."""
        repo = create_temp_repo()
        try:
            # Create PLATE playwright guide
            docs_dir = repo / "docs"
            docs_dir.mkdir(parents=True)
            
            guide = docs_dir / "playwright-e2e-guide.md"
            guide.write_text(
                "Playwright E2E Testing & Demo GIF Generation Guide\n",
                encoding="utf-8"
            )
            
            # Create protected files with references
            agents = repo / "AGENTS.md"
            agents.write_text(
                "See docs/playwright-e2e-guide.md for E2E testing.\n",
                encoding="utf-8"
            )
            
            spec = repo / "SPEC.md"
            spec.write_text(
                "Evidence: docs/playwright-e2e-guide.md\n",
                encoding="utf-8"
            )
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add docs"], cwd=repo, check=True)
            
            plan = plan_migration(repo)
            self.assertTrue(plan.ok, "Plan should succeed")
            
            # Should have manual_followup actions for protected files
            followup_actions = [a for a in plan.actions if a.action_type == "manual_followup"]
            followup_sources = {a.source for a in followup_actions}
            self.assertIn("AGENTS.md", followup_sources, "Should list AGENTS.md for manual followup")
            self.assertIn("SPEC.md", followup_sources, "Should list SPEC.md for manual followup")
            
            # Apply
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Apply should succeed")
            
            # Verify protected files were NOT modified
            agents_content = agents.read_text(encoding="utf-8")
            spec_content = spec.read_text(encoding="utf-8")
            self.assertIn("docs/playwright-e2e-guide.md", agents_content, "AGENTS.md should not be modified")
            self.assertIn("docs/playwright-e2e-guide.md", spec_content, "SPEC.md should not be modified")
        finally:
            import shutil
            shutil.rmtree(repo.parent)


class TestReferenceStaging(unittest.TestCase):
    """Test that reference updates are staged."""
    
    def test_reference_updates_staged(self):
        """Test that reference files are staged after update."""
        repo = create_temp_repo()
        try:
            # Create PLATE docs
            docs_dir = repo / "docs"
            docs_dir.mkdir(parents=True)
            
            guide = docs_dir / "playwright-e2e-guide.md"
            guide.write_text(
                "Playwright E2E Testing & Demo GIF Generation Guide\n",
                encoding="utf-8"
            )
            
            # Create file with reference
            contributing = repo / "CONTRIBUTING.md"
            contributing.write_text(
                "See docs/playwright-e2e-guide.md for testing.\n",
                encoding="utf-8"
            )
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add docs"], cwd=repo, check=True)
            
            # Apply migration
            result = apply_migration(repo)
            self.assertTrue(result.ok, "Apply should succeed")
            
            # Check staged files
            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            staged_files = staged.stdout.strip().split("\n")
            
            # Should include the moved file and the reference update
            self.assertIn("docs/plate/playwright-e2e-guide.md", staged_files, "Moved file should be staged")
            self.assertIn("CONTRIBUTING.md", staged_files, "Reference file should be staged")
            
            # Commit should leave clean working tree
            subprocess.run(["git", "commit", "-m", "Migrate docs"], cwd=repo, check=True)
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(status.stdout.strip(), "", "Working tree should be clean after commit")
        finally:
            import shutil
            shutil.rmtree(repo.parent)


class TestPreflightChecks(unittest.TestCase):
    """Test preflight validation before migration."""
    
    def test_preflight_fails_on_untracked_reconciliation_source(self):
        """Test that preflight fails if reconciliation source is untracked."""
        repo = create_temp_repo()
        try:
            # Create identical duplicates (both tracked initially)
            docs_dir = repo / "docs"
            plate_docs_dir = docs_dir / "plate" / "design"
            docs_dir.mkdir(parents=True)
            plate_docs_dir.mkdir(parents=True)
            
            source_dir = docs_dir / "design"
            source_dir.mkdir()
            (source_dir / "feature.md").write_text("# Same", encoding="utf-8")
            (plate_docs_dir / "feature.md").write_text("# Same", encoding="utf-8")
            
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add duplicates"], cwd=repo, check=True)
            
            # Now remove the source from git tracking (but leave the file)
            subprocess.run(["git", "rm", "--cached", "-r", "docs/design"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "Untrack source"], cwd=repo, check=True)
            
            # Migration should fail at preflight
            result = apply_migration(repo)
            self.assertFalse(result.ok, "Should fail preflight with untracked reconciliation source")
            self.assertTrue(
                any("reconciliation source is not tracked" in e for e in result.errors),
                "Should report untracked reconciliation source in errors"
            )
        finally:
            import shutil
            shutil.rmtree(repo.parent)


if __name__ == '__main__':
    unittest.main()
