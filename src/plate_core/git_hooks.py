"""Git hook templates and local pre-push enforcement (#1281)."""

from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO

from .plate_config import PlateConfigError, _resolve_plate_config

PRE_PUSH_COMMAND_KEYS = ("format", "lint", "typecheck")
HOOK_MARKER = "# PLATE pre-push hook"


def bundled_pre_push_template_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "git-hooks" / "pre-push"


def repo_pre_push_template_path(repo_root: Path) -> Path:
    return repo_root / "scripts" / "plate" / "pre-push-hook.sh"


def resolve_pre_push_template(repo_root: Path | None = None) -> Path:
    root = Path(repo_root or ".").resolve()
    local = repo_pre_push_template_path(root)
    if local.is_file():
        return local
    bundled = bundled_pre_push_template_path()
    if bundled.is_file():
        return bundled
    raise FileNotFoundError("pre-push hook template not found (expected bundled data or scripts/plate/pre-push-hook.sh)")


def pre_push_template_text() -> str:
    return bundled_pre_push_template_path().read_text(encoding="utf-8")


def _effective_config(repo_root: Path | None) -> dict[str, Any]:
    merged, _meta = _resolve_plate_config(repo_root)
    return merged


def get_pre_push_commands(repo_root: Path | None = None) -> list[tuple[str, str]]:
    """Return configured (name, shell_command) pairs; empty when none configured."""
    config = _effective_config(repo_root)
    hooks = config.get("hooks") or {}
    if not isinstance(hooks, dict):
        return []
    pre_push = hooks.get("pre_push") or {}
    if not isinstance(pre_push, dict):
        return []
    out: list[tuple[str, str]] = []
    for key in PRE_PUSH_COMMAND_KEYS:
        raw = pre_push.get(key)
        if not isinstance(raw, str):
            continue
        cmd = raw.strip()
        if cmd:
            out.append((key, cmd))
    return out


def parse_pre_push_stdin(stdin: TextIO | None = None) -> list[tuple[str, str, str, str]]:
    """Parse git pre-push stdin lines into (local_ref, local_sha, remote_ref, remote_sha)."""
    stream = stdin if stdin is not None else sys.stdin
    rows: list[tuple[str, str, str, str]] = []
    for line in stream:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 4:
            continue
        rows.append((parts[0], parts[1], parts[2], parts[3]))
    return rows


GIT_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def collect_changed_files_for_push(
    repo_root: Path,
    push_rows: list[tuple[str, str, str, str]],
) -> list[str]:
    """Union of changed paths for commits being pushed (added/modified/etc.)."""
    zero = "0" * 40
    paths: set[str] = set()
    for _local_ref, local_sha, _remote_ref, remote_sha in push_rows:
        if local_sha == zero:
            continue
        if local_sha == remote_sha:
            continue
        base = remote_sha if remote_sha != zero else GIT_EMPTY_TREE
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "diff",
                "--name-only",
                "--diff-filter=ACMRTUXB",
                base,
                local_sha,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            continue
        for rel in proc.stdout.splitlines():
            rel = rel.strip()
            if rel:
                paths.add(rel)
    return sorted(paths)


def render_command_for_files(command_template: str, files: list[str]) -> str:
    quoted = " ".join(shlex.quote(path) for path in files)
    if "{files}" in command_template:
        return command_template.replace("{files}", quoted)
    if quoted:
        return f"{command_template} {quoted}"
    return command_template


def run_shell_command(command: str, *, repo_root: Path) -> int:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(repo_root),
        check=False,
    )
    return int(proc.returncode)


def run_pre_push(
    repo_root: Path | None = None,
    *,
    stdin: TextIO | None = None,
) -> int:
    root = Path(repo_root or ".").resolve()
    commands = get_pre_push_commands(root)
    if not commands:
        return 0
    rows = parse_pre_push_stdin(stdin)
    if not rows:
        return 0
    files = collect_changed_files_for_push(root, rows)
    if not files:
        return 0
    for name, template in commands:
        rendered = render_command_for_files(template, files)
        code = run_shell_command(rendered, repo_root=root)
        if code != 0:
            print(f"pre-push: {name} failed (exit {code})", file=sys.stderr)
            return code
    return 0


def run_pre_push_from_stdin(repo_root: Path | None = None) -> int:
    return run_pre_push(repo_root, stdin=sys.stdin)


def git_hooks_dir(repo_root: Path) -> Path:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--git-path", "hooks"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "not a git repository")
    rel = proc.stdout.strip()
    path = Path(rel)
    if not path.is_absolute():
        top = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        path = Path(top) / path
    return path


@dataclass
class HookInstallReport:
    hook: str
    installed_path: str
    template_source: str
    replaced_existing: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def install_pre_push_hook(
    repo_root: Path | None = None,
    *,
    force: bool = False,
) -> HookInstallReport:
    root = Path(repo_root or ".").resolve()
    hooks_dir = git_hooks_dir(root)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dest = hooks_dir / "pre-push"
    replaced = dest.exists()
    if dest.exists() and not force:
        existing = dest.read_text(encoding="utf-8", errors="replace")
        if HOOK_MARKER not in existing:
            raise RuntimeError(
                "pre-push hook already exists and is not managed by PLATE; "
                "re-run with --force to replace it"
            )
    template_path = resolve_pre_push_template(root)
    content = template_path.read_text(encoding="utf-8")
    dest.write_text(content, encoding="utf-8")
    dest.chmod(dest.stat().st_mode | 0o111)
    return HookInstallReport(
        hook="pre-push",
        installed_path=str(dest),
        template_source=str(template_path),
        replaced_existing=replaced,
    )


@dataclass
class HookStatusReport:
    repo_root: str
    hook_path: str | None
    hook_installed: bool
    hook_is_plate: bool
    configured_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pre_push_status(repo_root: Path | None = None) -> HookStatusReport:
    root = Path(repo_root or ".").resolve()
    try:
        hooks_dir = git_hooks_dir(root)
        hook_path = hooks_dir / "pre-push"
    except RuntimeError:
        return HookStatusReport(
            repo_root=str(root),
            hook_path=None,
            hook_installed=False,
            hook_is_plate=False,
            configured_commands=[name for name, _ in get_pre_push_commands(root)],
        )
    installed = hook_path.is_file()
    is_plate = False
    if installed:
        text = hook_path.read_text(encoding="utf-8", errors="replace")
        is_plate = HOOK_MARKER in text
    return HookStatusReport(
        repo_root=str(root),
        hook_path=str(hook_path) if installed else None,
        hook_installed=installed,
        hook_is_plate=is_plate,
        configured_commands=[name for name, _ in get_pre_push_commands(root)],
    )


def validate_hooks_config(hooks: Any) -> None:
    if hooks is None:
        return
    if not isinstance(hooks, dict):
        raise PlateConfigError("'hooks' must be an object if present")
    allowed_hook_names = {"pre_push"}
    unknown_hooks = sorted(set(hooks) - allowed_hook_names)
    if unknown_hooks:
        raise PlateConfigError(f"unknown hooks keys: {', '.join(unknown_hooks)}")
    pre_push = hooks.get("pre_push")
    if pre_push is None:
        return
    if not isinstance(pre_push, dict):
        raise PlateConfigError("'hooks.pre_push' must be an object if present")
    unknown_cmds = sorted(set(pre_push) - set(PRE_PUSH_COMMAND_KEYS))
    if unknown_cmds:
        raise PlateConfigError(
            f"unknown hooks.pre_push keys: {', '.join(unknown_cmds)} "
            f"(allowed: {', '.join(PRE_PUSH_COMMAND_KEYS)})"
        )
    for key in PRE_PUSH_COMMAND_KEYS:
        val = pre_push.get(key)
        if val is not None and not isinstance(val, str):
            raise PlateConfigError(f"hooks.pre_push.{key} must be a string if present")
