"""Attach PR body screenshots via gh --attach (#1051)."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

USER_ATTACHMENTS_PREFIX = "https://github.com/user-attachments/assets/"
MIN_GH_VERSION = (2, 99)

_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

COPILOT_ROUTE_MESSAGE = (
    "Third-party cloud agents without a user PAT cannot upload PR attachments — assign the "
    "issue to GitHub Copilot's cloud coding agent (or a human with local `gh` and a PAT) "
    "for UI screenshot work. Do not commit images or use raw/blob URL workarounds (#1050)."
)

@dataclass(frozen=True)
class PlateEvidenceResult:
    ok: bool
    pr_number: int
    body_file: str
    images: tuple[str, ...]
    user_attachment_urls: tuple[str, ...]
    gh_version: str | None = None
    error: str | None = None
    refused_upload: bool = False

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "pr_number": self.pr_number,
            "body_file": self.body_file,
            "images": list(self.images),
            "user_attachment_urls": list(self.user_attachment_urls),
            "gh_version": self.gh_version,
            "error": self.error,
            "refused_upload": self.refused_upload,
        }


def parse_gh_version(text: str) -> tuple[int, int, int] | None:
    """Parse ``gh version X.Y.Z`` from ``gh --version`` output."""
    match = re.search(r"gh version (\d+)\.(\d+)\.(\d+)", text or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def gh_version_ok(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    return version >= MIN_GH_VERSION


def default_alt_text(image_path: Path) -> str:
    stem = image_path.stem.replace("-", " ").replace("_", " ").strip()
    return stem or image_path.name


def _image_ref_variants(image_path: Path) -> frozenset[str]:
    base = image_path.name
    resolved = str(image_path.resolve())
    parent_rel = image_path.as_posix()
    return frozenset({base, f"./{base}", parent_rel, f"./{parent_rel}", resolved})


def _normalize_ref(url: str) -> str:
    return url.strip().replace("\\", "/")


def _body_references_image(body: str, image_path: Path) -> bool:
    variants = _image_ref_variants(image_path)
    for match in _MD_IMAGE.finditer(body):
        ref = _normalize_ref(match.group(2))
        if ref in variants or ref.endswith("/" + image_path.name):
            return True
    return False


def _fix_empty_alts(body: str, image_path: Path) -> tuple[str, str | None]:
    """Replace empty alt text for refs pointing at ``image_path``; error if still empty."""
    variants = _image_ref_variants(image_path)
    alt_default = default_alt_text(image_path)
    seen = False

    def repl(match: re.Match[str]) -> str:
        nonlocal seen
        alt, url = match.group(1), _normalize_ref(match.group(2))
        if url not in variants and not url.endswith("/" + image_path.name):
            return match.group(0)
        seen = True
        if alt.strip():
            return match.group(0)
        return f"![{alt_default}]({match.group(2)})"

    updated = _MD_IMAGE.sub(repl, body)
    if seen:
        return updated, None
    return body, None


def prepare_body_with_images(body: str, image_paths: Sequence[Path]) -> tuple[str, str | None]:
    """Ensure each image has a non-empty-alt markdown reference."""
    text = body or ""
    for image_path in image_paths:
        text, _ = _fix_empty_alts(text, image_path)
        if not _body_references_image(text, image_path):
            alt = default_alt_text(image_path)
            line = f"\n\n![{alt}](./{image_path.name})\n"
            text = text.rstrip() + line
        # Re-check alt after append
        text2, err = _fix_empty_alts(text, image_path)
        if err:
            return text, err
        text = text2
        for match in _MD_IMAGE.finditer(text):
            ref = _normalize_ref(match.group(2))
            variants = _image_ref_variants(image_path)
            if ref in variants or ref.endswith("/" + image_path.name):
                if not match.group(1).strip():
                    return text, f"empty alt text for image {image_path.name}"
    return text, None


def extract_user_attachment_urls(body: str) -> list[str]:
    urls: list[str] = []
    for match in _MD_IMAGE.finditer(body or ""):
        ref = match.group(2).strip()
        if ref.startswith(USER_ATTACHMENTS_PREFIX):
            urls.append(ref)
    if USER_ATTACHMENTS_PREFIX in (body or ""):
        for part in re.findall(r"https://github\.com/user-attachments/assets/[A-Za-z0-9_-]+", body):
            if part not in urls:
                urls.append(part)
    return urls


def looks_like_refused_upload(output: str) -> bool:
    lower = (output or "").lower()
    if "requires write access" in lower:
        return True
    if "upload" in lower and ("403" in lower or "404" in lower or "refused" in lower):
        return True
    if "attachment" in lower and "not supported" in lower:
        return True
    return False


def bundled_evidence_script() -> Path:
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    for candidate in (
        repo_root / "scripts" / "plate_evidence.sh",
        Path.cwd() / "scripts" / "plate_evidence.sh",
    ):
        if candidate.is_file():
            return candidate
    return repo_root / "scripts" / "plate_evidence.sh"


def _run_cmd(
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> subprocess.CompletedProcess[str]:
    run = runner or subprocess.run
    return run(
        list(argv),
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        check=False,
    )


def run_plate_evidence(
    pr_number: int,
    body_file: str | Path,
    images: Sequence[str | Path],
    *,
    gh: str | None = None,
    env: dict[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> PlateEvidenceResult:
    gh_bin = gh or os.environ.get("GH", "gh")
    body_path = Path(body_file).resolve()
    image_paths = [Path(p).resolve() for p in images]

    if not body_path.is_file():
        return PlateEvidenceResult(
            ok=False,
            pr_number=pr_number,
            body_file=str(body_path),
            images=tuple(str(p) for p in image_paths),
            user_attachment_urls=(),
            error=f"body file not found: {body_path}",
        )

    for image_path in image_paths:
        if not image_path.is_file():
            return PlateEvidenceResult(
                ok=False,
                pr_number=pr_number,
                body_file=str(body_path),
                images=tuple(str(p) for p in image_paths),
                user_attachment_urls=(),
                error=f"image not found: {image_path}",
            )

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    ver_proc = _run_cmd([gh_bin, "--version"], env=merged_env, runner=runner)
    ver_text = (ver_proc.stdout or "") + (ver_proc.stderr or "")
    parsed = parse_gh_version(ver_text)
    if not gh_version_ok(parsed):
        return PlateEvidenceResult(
            ok=False,
            pr_number=pr_number,
            body_file=str(body_path),
            images=tuple(str(p) for p in image_paths),
            user_attachment_urls=(),
            gh_version=ver_text.strip().splitlines()[0] if ver_text.strip() else None,
            error=(
                "GitHub CLI gh >= 2.99 is required for `gh pr edit --attach`. "
                "Upgrade gh, then re-run `gh plate evidence`."
            ),
        )

    original_body = body_path.read_text(encoding="utf-8")
    prepared, prep_err = prepare_body_with_images(original_body, image_paths)
    if prep_err:
        return PlateEvidenceResult(
            ok=False,
            pr_number=pr_number,
            body_file=str(body_path),
            images=tuple(str(p) for p in image_paths),
            user_attachment_urls=(),
            error=prep_err,
        )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".md",
        delete=False,
        prefix="plate-evidence-body-",
    ) as tmp:
        tmp.write(prepared)
        prepared_path = tmp.name

    try:
        edit_argv = [
            gh_bin,
            "pr",
            "edit",
            str(pr_number),
            "--body-file",
            prepared_path,
        ]
        for image_path in image_paths:
            edit_argv.extend(["--attach", str(image_path)])

        edit_proc = _run_cmd(edit_argv, env=merged_env, runner=runner)
        combined = (edit_proc.stdout or "") + (edit_proc.stderr or "")
        if edit_proc.returncode != 0:
            refused = looks_like_refused_upload(combined)
            err = COPILOT_ROUTE_MESSAGE if refused else (combined.strip() or "gh pr edit failed")
            return PlateEvidenceResult(
                ok=False,
                pr_number=pr_number,
                body_file=str(body_path),
                images=tuple(str(p) for p in image_paths),
                user_attachment_urls=(),
                gh_version=ver_text.strip().splitlines()[0] if ver_text.strip() else None,
                error=err,
                refused_upload=refused,
            )

        view_proc = _run_cmd(
            [gh_bin, "pr", "view", str(pr_number), "--json", "body"],
            env=merged_env,
            runner=runner,
        )
        view_out = (view_proc.stdout or "") + (view_proc.stderr or "")
        if view_proc.returncode != 0:
            return PlateEvidenceResult(
                ok=False,
                pr_number=pr_number,
                body_file=str(body_path),
                images=tuple(str(p) for p in image_paths),
                user_attachment_urls=(),
                gh_version=ver_text.strip().splitlines()[0] if ver_text.strip() else None,
                error=view_out.strip() or "gh pr view failed after edit",
            )

        body_after = view_out
        try:
            import json as _json

            data = _json.loads(view_out)
            body_after = str(data.get("body") or "")
        except Exception:
            pass

        urls = extract_user_attachment_urls(body_after)
        if not urls:
            return PlateEvidenceResult(
                ok=False,
                pr_number=pr_number,
                body_file=str(body_path),
                images=tuple(str(p) for p in image_paths),
                user_attachment_urls=(),
                gh_version=ver_text.strip().splitlines()[0] if ver_text.strip() else None,
                error=(
                    "PR body does not contain https://github.com/user-attachments/assets/ "
                    "links after attach; verify gh auth and image markdown references."
                ),
            )

        return PlateEvidenceResult(
            ok=True,
            pr_number=pr_number,
            body_file=str(body_path),
            images=tuple(str(p) for p in image_paths),
            user_attachment_urls=tuple(urls),
            gh_version=ver_text.strip().splitlines()[0] if ver_text.strip() else None,
        )
    finally:
        try:
            os.unlink(prepared_path)
        except OSError:
            pass


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plate_evidence",
        description="Attach images to a PR body with gh pr edit --attach (#1051)",
    )
    parser.add_argument("pr_number", type=int, help="Pull request number")
    parser.add_argument(
        "--body-file",
        required=True,
        help="Markdown file for the PR body (updated references; not overwritten in place)",
    )
    parser.add_argument(
        "images",
        nargs="+",
        help="One or more image paths to attach",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON result on stdout")
    parser.add_argument(
        "--gh",
        default=None,
        help="gh executable (default: $GH or gh)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    result = run_plate_evidence(
        args.pr_number,
        args.body_file,
        args.images,
        gh=args.gh,
    )
    if args.json:
        import json

        print(json.dumps(result.to_dict(), indent=2))
    elif result.ok:
        print(f"Attached {len(result.images)} image(s) to PR #{result.pr_number}.")
        for url in result.user_attachment_urls:
            print(url)
    else:
        print(result.error or "plate evidence failed", file=sys.stderr)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())