"""MCP tools for Playwright E2E testing and scaffolding."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..template_payload import resolve_template_source_root


# Maximum time (seconds) to wait for an E2E recording script before timing out.
_E2E_RECORDING_TIMEOUT = 120


class InitPlaywrightTool:
    """Initialize Playwright E2E testing in a repo."""

    @staticmethod
    def execute(repo_path: str, template_repo: str | None = None, force: bool = False) -> dict:
        """
        Copy Playwright config, example specs, and GIF scripts from template payload.

        Args:
            repo_path: Path to target repo
            template_repo: Source template path override (optional)
            force: If True, overwrite existing tests/e2e/ directory. Defaults to False.

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
            template = resolve_template_source_root(template_repo)

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
                    if not force:
                        return {
                            "status": "error",
                            "message": (
                                "tests/e2e/ already exists. Backup your existing tests "
                                "first, then pass force=True to overwrite and replace "
                                "existing E2E test content."
                            ),
                        }
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
    """Record and generate a demo GIF from E2E test. Per #263: supports trimming hints, better output info, size suitability checks."""

    @staticmethod
    def execute(repo_path: str, test_name: str, quality: str = "medium", start: str | None = None, duration: int | None = None) -> dict:
        """
        Record and generate a demo GIF from E2E test.

        Args:
            repo_path: Path to repo
            test_name: Name of test to record (e.g., 'login')
            quality: 'low' (10fps), 'medium' (15fps), 'high' (30fps)
            start: Optional start time for trim (e.g. '00:00:05' for gif-from-video)
            duration: Optional duration seconds for trim

        Returns:
            {'status': 'success' or 'error' or 'warning', 'gif_path': '...', 'size_bytes': ..., 'quality': ..., 'recommendations': [...] }
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
                    timeout=_E2E_RECORDING_TIMEOUT,
                )
            else:
                result = subprocess.run(
                    ["bash", str(script_path), test_name, quality],
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    timeout=_E2E_RECORDING_TIMEOUT,
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
            recs = []
            if start or duration:
                recs.append(f"Trim params provided (start={start}, duration={duration}); re-run gif-from-video --start/--duration for precise clip if needed.")
            if gif_path.exists():
                size_bytes = gif_path.stat().st_size
                if size_bytes > 5 * 1024 * 1024:  # >5MB heuristic for wiki/readme suitability
                    recs.append("GIF large; recommend trim with ./scripts/gif-from-video.sh <video> <gif> --start HH:MM:SS --duration SS --quality medium")
                base = {
                    "status": "success",
                    "gif_path": str(gif_path),
                    "size_bytes": size_bytes,
                    "quality": quality,
                }
                if recs:
                    base["recommendations"] = recs
                if start or duration:
                    base["trim"] = {"start": start, "duration": duration}
                return base
            else:
                return {
                    "status": "warning",
                    "message": f"Recording completed but GIF not found at {gif_path}",
                    "recommendations": recs or None,
                }

        except Exception as exc:
            return {"status": "error", "message": str(exc)}


class ValidateE2eTestsTool:
    """Validate Playwright E2E setup. Per #263: clearer status + actionable next-steps, CI/evidence checks."""

    @staticmethod
    def execute(repo_path: str) -> dict:
        """
        Check playwright.config.ts, specs, deps, CI, evidence assets, scripts.

        Returns:
            {
                'status': 'pass' | 'warn' | 'fail',
                'valid': bool,
                'issues': [...],
                'recommendations': [...],
                'next_steps': [...]
            }
        """
        repo = Path(repo_path).resolve()
        if not repo.exists():
            return {
                "status": "fail",
                "valid": False,
                "issues": [f"Repository not found: {repo_path}"],
                "recommendations": ["Ensure repo_path points to a valid checkout."],
                "next_steps": ["Provide a correct repo path or run from within the project."],
            }

        issues = []
        recommendations = []
        next_steps = []

        # Core config
        if not (repo / "playwright.config.ts").exists():
            issues.append("Missing playwright.config.ts (core config)")
            recommendations.append("Run: @copilot init-playwright or copy from plate template")
            next_steps.append("Add playwright.config.ts with projects for chromium (and firefox/webkit for multi-host)")

        # tests/e2e structure
        e2e_dir = repo / "tests" / "e2e"
        if not e2e_dir.is_dir():
            issues.append("Missing tests/e2e directory")
            recommendations.append("Run: @copilot init-playwright")
            next_steps.append("Scaffold tests/e2e/ with specs/ and fixtures/ for visual evidence")
        else:
            specs_dir = e2e_dir / "specs"
            if specs_dir.is_dir():
                spec_files = list(specs_dir.glob("*.spec.ts"))
                if not spec_files:
                    issues.append("No test specs found in tests/e2e/specs/")
                    recommendations.append("Create at least one .spec.ts (see template examples)")
                    next_steps.append("Write a spec exercising a key user flow; record GIF with record_e2e_gif")
            else:
                issues.append("Missing tests/e2e/specs directory")
                next_steps.append("Create tests/e2e/specs/ and add *.spec.ts files")

            # Evidence / visual assets (per #263 AC for GIF evidence)
            fixtures = e2e_dir / "fixtures"
            if fixtures.is_dir():
                gifs = list(fixtures.rglob("*.gif")) + list((fixtures / "gifs").glob("*.gif") if (fixtures / "gifs").is_dir() else [])
                if not gifs:
                    recommendations.append("Record GIF evidence for UI features using record_e2e_gif (retained on failure or for docs)")
            else:
                recommendations.append("Add tests/e2e/fixtures/ (and fixtures/gifs/) for recorded evidence artifacts")

        # package.json deps + scripts
        package_json = repo / "package.json"
        has_pw = False
        if package_json.exists():
            try:
                with open(package_json, encoding='utf-8-sig') as f:
                    data = json.load(f)
                dev_deps = data.get("devDependencies", {}) or {}
                scripts = data.get("scripts", {}) or {}
                if "@playwright/test" not in dev_deps:
                    issues.append("@playwright/test not in devDependencies")
                    recommendations.append("Run: npm install --save-dev @playwright/test")
                    next_steps.append("npm install @playwright/test && npx playwright install --with-deps")
                else:
                    has_pw = True
                if "test:e2e" not in scripts and "e2e" not in scripts:
                    recommendations.append("Add 'test:e2e' script to package.json (e.g. 'playwright test')")
                    next_steps.append("Update package.json scripts so 'npm run test:e2e' works in CI and locally")
            except Exception as e:
                issues.append(f"Could not parse package.json: {e}")
        else:
            issues.append("Missing package.json")

        # CI config (stricter check per #263)
        ci_dir = repo / ".github" / "workflows"
        has_e2e_ci = False
        if ci_dir.is_dir():
            for yml in list(ci_dir.glob("*.yml")) + list(ci_dir.glob("*.yaml")):
                try:
                    txt = yml.read_text(encoding="utf-8", errors="ignore").lower()
                    if "playwright" in txt or "e2e" in txt or "npx playwright" in txt:
                        has_e2e_ci = True
                        break
                except Exception:
                    pass
        if not has_e2e_ci:
            recommendations.append("Add or update .github/workflows/ with E2E job (matrix for hosts, upload artifacts on failure)")
            next_steps.append("Ensure CI runs npx playwright test on PRs; retain videos/GIFs only on failure for cost control")

        # Recording scripts (from payload)
        if not (repo / "scripts" / "e2e-record.sh").exists():
            recommendations.append("Copy e2e-record.sh (and .ps1) from plate template payload scripts/ for reliable GIF capture + trim")
        if not (repo / "scripts" / "e2e-record.ps1").exists():
            recommendations.append("Copy e2e-record.ps1 from plate template payload scripts/")

        # .env / host
        if not (repo / ".env.local").exists():
            recommendations.append("Create .env.local (or equiv) with BASE_URL for the target host")

        # Determine status (clear pass/warn/fail per #263)
        critical = [i for i in issues if "Missing playwright" in i or "Missing tests/e2e" in i or "@playwright/test not in" in i or "Missing package.json" in i]
        if critical:
            status = "fail"
        elif issues:
            status = "warn"
        else:
            status = "pass"

        valid = status == "pass"

        if status == "pass":
            next_steps.append("Run: npm run test:e2e ; use record_e2e_gif for UI PR evidence; validate again after changes")
        elif status == "warn":
            next_steps.append("Address recommendations above, then re-run validate_e2e_tests")
        else:
            next_steps.append("Fix critical issues (core config/deps), then scaffold with init_playwright and re-validate")

        return {
            "status": status,
            "valid": valid,
            "issues": issues,
            "recommendations": recommendations,
            "next_steps": next_steps,
        }
