"""MCP tools for Playwright E2E testing and scaffolding."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _get_template_repo() -> Path:
    """Get path to plate_template repository."""
    cwd = Path.cwd()
    template = cwd.parent / "plate_template"
    if template.exists():
        return template
    raise RuntimeError(
        f"Could not find plate_template repository. "
        f"Expected at: {template}"
    )


class InitPlaywrightTool:
    """Initialize Playwright E2E testing in a repo."""

    @staticmethod
    def execute(repo_path: str, template_repo: str | None = None) -> dict:
        """
        Copy Playwright config, example specs, and GIF scripts from template.

        Args:
            repo_path: Path to target repo
            template_repo: Source template path (optional; uses plate_template if not provided)

        Returns:
            {
                'status': 'success' or 'error',
                'files_created': [...],
                'next_steps': [...]
            }
        """
        repo = Path(repo_path).resolve()
        if not repo.exists():
            return {"status": "error", "message": f"Repository not found: {repo_path}"}

        try:
            if template_repo:
                template = Path(template_repo).resolve()
            else:
                template = _get_template_repo()

            if not template.exists():
                return {"status": "error", "message": f"Template not found: {template}"}

            files_created = []

            # Copy playwright.config.ts
            src_config = template / "playwright.config.ts"
            dst_config = repo / "playwright.config.ts"
            if src_config.exists():
                shutil.copy2(src_config, dst_config)
                files_created.append("playwright.config.ts")

            # Copy tests/e2e/
            src_e2e = template / "tests" / "e2e"
            dst_e2e = repo / "tests" / "e2e"
            if src_e2e.exists():
                if dst_e2e.exists():
                    shutil.rmtree(dst_e2e)
                shutil.copytree(src_e2e, dst_e2e)
                files_created.append("tests/e2e/")

            # Copy e2e scripts
            src_scripts = template / "scripts"
            dst_scripts = repo / "scripts"
            dst_scripts.mkdir(exist_ok=True)
            for script in ["e2e-record.sh", "e2e-record.ps1"]:
                src = src_scripts / script
                dst = dst_scripts / script
                if src.exists():
                    shutil.copy2(src, dst)
                    files_created.append(f"scripts/{script}")

            # Generate sample .env if it doesn't exist
            env_file = repo / ".env.local"
            if not env_file.exists():
                env_file.write_text("BASE_URL=http://localhost:3000\n")
                files_created.append(".env.local")

            # Ensure package.json has playwright dependency
            package_json = repo / "package.json"
            if package_json.exists():
                with open(package_json, encoding='utf-8-sig') as f:
                    data = json.load(f)
                if "@playwright/test" not in data.get("devDependencies", {}):
                    if "devDependencies" not in data:
                        data["devDependencies"] = {}
                    data["devDependencies"]["@playwright/test"] = "^1.40.0"
                    with open(package_json, 'w') as f:
                        json.dump(data, f, indent=2)
                    files_created.append("package.json (updated)")

            next_steps = [
                "Run: npm install",
                "Run: npm run test:e2e to verify setup",
                "Write tests in tests/e2e/specs/",
                "Run: npm run test:e2e:headed to see tests with browser",
            ]

            return {
                "status": "success",
                "files_created": files_created,
                "next_steps": next_steps,
            }

        except Exception as exc:
            return {"status": "error", "message": str(exc)}


class RecordE2eGifTool:
    """Record and generate a demo GIF from E2E test."""

    @staticmethod
    def execute(repo_path: str, test_name: str, quality: str = "medium") -> dict:
        """
        Record and generate a demo GIF from E2E test.

        Args:
            repo_path: Path to repo
            test_name: Name of test to record (e.g., 'login')
            quality: 'low' (10fps), 'medium' (15fps), 'high' (30fps)

        Returns:
            {'status': 'success' or 'error', 'gif_path': '...', 'size_bytes': ...}
        """
        repo = Path(repo_path).resolve()
        if not repo.exists():
            return {"status": "error", "message": f"Repository not found: {repo_path}"}

        if not test_name:
            return {"status": "error", "message": "test_name is required"}

        try:
            # Validate test_name to prevent injection
            if not test_name.replace("-", "").replace("_", "").isalnum():
                return {
                    "status": "error",
                    "message": f"Invalid test name: {test_name}",
                }

            # Determine platform and script
            import sys

            is_windows = sys.platform == "win32"
            script_name = "e2e-record.ps1" if is_windows else "e2e-record.sh"
            script_path = repo / "scripts" / script_name

            if not script_path.exists():
                return {
                    "status": "error",
                    "message": f"Recording script not found: {script_path}",
                }

            # Call the recording script
            if is_windows:
                result = subprocess.run(
                    ["powershell", "-File", str(script_path), test_name, quality],
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                )
            else:
                result = subprocess.run(
                    ["bash", str(script_path), test_name, quality],
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "message": f"Recording failed: {result.stderr}",
                }

            # Check for generated GIF
            gif_path = (
                repo / "tests" / "e2e" / "fixtures" / "gifs" / f"{test_name}.gif"
            )
            if gif_path.exists():
                size_bytes = gif_path.stat().st_size
                return {
                    "status": "success",
                    "gif_path": str(gif_path),
                    "size_bytes": size_bytes,
                }
            else:
                return {
                    "status": "warning",
                    "message": f"Recording completed but GIF not found at {gif_path}",
                }

        except Exception as exc:
            return {"status": "error", "message": str(exc)}


class ValidateE2eTestsTool:
    """Validate Playwright E2E setup."""

    @staticmethod
    def execute(repo_path: str) -> dict:
        """
        Check playwright.config.ts, example specs, scripts, etc.

        Args:
            repo_path: Path to repo

        Returns:
            {
                'valid': bool,
                'issues': [...],
                'recommendations': [...]
            }
        """
        repo = Path(repo_path).resolve()
        if not repo.exists():
            return {
                "valid": False,
                "issues": [f"Repository not found: {repo_path}"],
                "recommendations": [],
            }

        issues = []
        recommendations = []

        # Check playwright.config.ts
        if not (repo / "playwright.config.ts").exists():
            issues.append("Missing playwright.config.ts")
            recommendations.append(
                "Run: @copilot init-playwright"
            )

        # Check tests/e2e directory
        if not (repo / "tests" / "e2e").is_dir():
            issues.append("Missing tests/e2e directory")
            recommendations.append(
                "Run: @copilot init-playwright"
            )

        # Check for at least one spec file
        specs_dir = repo / "tests" / "e2e" / "specs"
        if specs_dir.is_dir():
            spec_files = list(specs_dir.glob("*.spec.ts"))
            if not spec_files:
                issues.append("No test specs found in tests/e2e/specs/")
                recommendations.append(
                    "Create a test spec: tests/e2e/specs/example.spec.ts"
                )
        else:
            issues.append("Missing tests/e2e/specs directory")

        # Check package.json for Playwright dependency
        package_json = repo / "package.json"
        if package_json.exists():
            try:
                with open(package_json, encoding='utf-8-sig') as f:
                    data = json.load(f)
                dev_deps = data.get("devDependencies", {})
                if "@playwright/test" not in dev_deps:
                    issues.append("@playwright/test not in devDependencies")
                    recommendations.append("Run: npm install @playwright/test")
            except Exception as e:
                issues.append(f"Could not parse package.json: {e}")
        else:
            issues.append("Missing package.json")

        # Check for recording scripts
        if not (repo / "scripts" / "e2e-record.sh").exists():
            recommendations.append("Copy e2e-record.sh from plate_template/scripts/")
        if not (repo / "scripts" / "e2e-record.ps1").exists():
            recommendations.append("Copy e2e-record.ps1 from plate_template/scripts/")

        # Check .env.local
        if not (repo / ".env.local").exists():
            recommendations.append("Create .env.local with BASE_URL=http://localhost:3000")

        valid = len(issues) == 0

        return {
            "valid": valid,
            "issues": issues,
            "recommendations": recommendations,
        }
