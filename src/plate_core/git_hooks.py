"""Git hook templates and local pre-push enforcement (#1281)."""

from __future__ import annotations

import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, TextIO

from .plate_config import PlateConfigError, _resolve_plate_config

PRE_PUSH_COMMAND_KEYS = ("format", "lint", "typecheck")
HOOK_MARKER = "# PLATE pre-push hook"
GIT_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class GitHookError(Exception):
    """Pre-push hook failed before or during local checks."""


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
    """Return configured (name, command_template) pairs; empty when none configured."""
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


def _parse_name_only_z_output(raw: bytes) -> list[str]:
    if not raw:
        return []
    parts = raw.split(b"\0")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    return [part.decode("utf-8", errors="surrogateescape") for part in parts if part]


def collect_changed_files_by_commit(
    repo_root: Path,
    push_rows: list[tuple[str, str, str, str]],
) -> dict[str, list[str]]:
    """Map each pushed local commit to paths changed in that push range (NUL-delimited git output)."""
    zero = "0" * 40
    grouped: dict[str, set[str]] = {}
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
                "-z",
                "--diff-filter=ACMRTUXB",
                base,
                local_sha,
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").strip() or proc.stdout.decode(
                "utf-8", errors="replace"
            ).strip()
            raise GitHookError(
                "pre-push: git diff failed for "
                f"{base[:7]}..{local_sha[:7]}: {err or 'unknown error'}"
            )
        for rel in _parse_name_only_z_output(proc.stdout):
            grouped.setdefault(local_sha, set()).add(rel)
    return {sha: sorted(paths) for sha, paths in grouped.items()}


def collect_changed_files_for_push(
    repo_root: Path,
    push_rows: list[tuple[str, str, str, str]],
) -> list[str]:
    """Flat sorted list of changed paths (union across commits being pushed)."""
    by_commit = collect_changed_files_by_commit(repo_root, push_rows)
    paths: set[str] = set()
    for rels in by_commit.values():
        paths.update(rels)
    return sorted(paths)


def build_command_argv(command_template: str, files: list[str]) -> list[str]:
    """Build argv for subprocess (no shell): POSIX shlex words + literal file paths."""
    if command_template.count("{files}") > 1:
        raise GitHookError("pre-push: command template must contain at most one {files} placeholder")
    if "{files}" in command_template:
        before, after = command_template.split("{files}", 1)
        argv: list[str] = []
        if before.strip():
            argv.extend(shlex.split(before, posix=True))
        argv.extend(files)
        if after.strip():
            argv.extend(shlex.split(after, posix=True))
        return argv
    argv = shlex.split(command_template, posix=True)
    argv.extend(files)
    return argv


def render_command_for_files(command_template: str, files: list[str]) -> str:
    """Deprecated string form; tests and callers should prefer build_command_argv."""
    argv = build_command_argv(command_template, files)
    return " ".join(shlex.quote(part) for part in argv)


def _worktree_porcelain(worktree: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else ""


@contextmanager
def detached_worktree(repo_root: Path, commit: str) -> Iterator[Path]:
    wt_dir = Path(tempfile.mkdtemp(prefix="plate-pre-push-"))
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "add", "--detach", str(wt_dir), commit],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip() or "worktree add failed"
            raise GitHookError(f"pre-push: could not checkout {commit[:7]} for checks: {err}")
        yield wt_dir
    finally:
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(wt_dir)],
            capture_output=True,
            check=False,
        )


def run_check_argv(
    argv: list[str],
    *,
    worktree: Path,
    check_name: str,
) -> int:
    proc = subprocess.run(argv, cwd=str(worktree), check=False)
    if proc.returncode != 0:
        print(f"pre-push: {check_name} failed (exit {proc.returncode})", file=sys.stderr)
        return int(proc.returncode)
    if _worktree_porcelain(worktree).strip():
        print(
            f"pre-push: {check_name} modified files in the pushed commit snapshot; "
            "commit the fixes and push again",
            file=sys.stderr,
        )
        return 1
    return 0


def run_pre_push_checks_on_commit(
    repo_root: Path,
    local_sha: str,
    files: list[str],
    commands: list[tuple[str, str]],
) -> int:
    if not files:
        return 0
    with detached_worktree(repo_root, local_sha) as wt:
        present = [rel for rel in files if (wt / rel).exists()]
        if not present:
            return 0
        for name, template in commands:
            argv = build_command_argv(template, present)
            code = run_check_argv(argv, worktree=wt, check_name=name)
            if code != 0:
                return code
    return 0


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
    try:
        by_commit = collect_changed_files_by_commit(root, rows)
    except GitHookError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not by_commit:
        return 0
    for local_sha, files in by_commit.items():
        code = run_pre_push_checks_on_commit(root, local_sha, files, commands)
        if code != 0:
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
