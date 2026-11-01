"""Git hook templates and local pre-push / pre-commit enforcement (#1281, #1302)."""

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

PRE_HOOK_COMMAND_KEYS = ("format", "lint", "typecheck")
HOOK_MARKER = "# PLATE pre-push hook"
HOOK_MARKER_PRE_COMMIT = "# PLATE pre-commit hook"
GIT_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
SUPPORTED_HOOKS = frozenset({"pre-push", "pre-commit"})


class GitHookError(Exception):
    """Pre-push hook failed before or during local checks."""


def bundled_pre_push_template_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "git-hooks" / "pre-push"


def repo_pre_push_template_path(repo_root: Path) -> Path:
    return repo_root / "scripts" / "plate" / "pre-push-hook.sh"


def bundled_pre_commit_template_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "git-hooks" / "pre-commit"


def repo_pre_commit_template_path(repo_root: Path) -> Path:
    return repo_root / "scripts" / "plate" / "pre-commit-hook.sh"


def resolve_pre_push_template(repo_root: Path | None = None) -> Path:
    return _resolve_hook_template("pre-push", repo_root)


def resolve_pre_commit_template(repo_root: Path | None = None) -> Path:
    return _resolve_hook_template("pre-commit", repo_root)


def _resolve_hook_template(hook: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root or ".").resolve()
    if hook == "pre-push":
        local = repo_pre_push_template_path(root)
        bundled = bundled_pre_push_template_path()
        label = "pre-push hook template not found (expected bundled data or scripts/plate/pre-push-hook.sh)"
    elif hook == "pre-commit":
        local = repo_pre_commit_template_path(root)
        bundled = bundled_pre_commit_template_path()
        label = "pre-commit hook template not found (expected bundled data or scripts/plate/pre-commit-hook.sh)"
    else:
        raise ValueError(f"unsupported hook: {hook!r}")
    if local.is_file():
        return local
    if bundled.is_file():
        return bundled
    raise FileNotFoundError(label)


def pre_push_template_text() -> str:
    return bundled_pre_push_template_path().read_text(encoding="utf-8")


def _effective_config(repo_root: Path | None) -> dict[str, Any]:
    merged, _meta = _resolve_plate_config(repo_root)
    return merged


def _commands_for_config_key(repo_root: Path | None, config_key: str) -> list[tuple[str, str]]:
    config = _effective_config(repo_root)
    hooks = config.get("hooks") or {}
    if not isinstance(hooks, dict):
        return []
    section = hooks.get(config_key) or {}
    if not isinstance(section, dict):
        return []
    out: list[tuple[str, str]] = []
    for key in PRE_HOOK_COMMAND_KEYS:
        raw = section.get(key)
        if not isinstance(raw, str):
            continue
        cmd = raw.strip()
        if cmd:
            out.append((key, cmd))
    return out


def get_pre_push_commands(repo_root: Path | None = None) -> list[tuple[str, str]]:
    """Return configured (name, command_template) pairs; empty when none configured."""
    return _commands_for_config_key(repo_root, "pre_push")


def get_pre_commit_commands(repo_root: Path | None = None) -> list[tuple[str, str]]:
    """Return configured pre-commit (name, command_template) pairs; empty when none configured."""
    return _commands_for_config_key(repo_root, "pre_commit")


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


def _worktree_unstaged_diff_names(worktree: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(worktree), "diff", "--name-only"],
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
    mutation_mode: str = "worktree",
) -> int:
    proc = subprocess.run(argv, cwd=str(worktree), check=False)
    if proc.returncode != 0:
        print(f"hook: {check_name} failed (exit {proc.returncode})", file=sys.stderr)
        return int(proc.returncode)
    if mutation_mode == "unstaged":
        dirty = _worktree_unstaged_diff_names(worktree).strip()
        if dirty:
            print(
                f"hook: {check_name} modified working tree files; stage the fixes and retry",
                file=sys.stderr,
            )
            return 1
    elif mutation_mode == "worktree":
        if _worktree_porcelain(worktree).strip():
            print(
                f"hook: {check_name} modified files; stage the fixes and retry",
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
            code = run_check_argv(argv, worktree=wt, check_name=name, mutation_mode="worktree")
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


def collect_staged_files(repo_root: Path) -> list[str]:
    """Return sorted staged paths for the index (pre-commit)."""
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--diff-filter=ACMRTUXB",
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip() or proc.stdout.decode(
            "utf-8", errors="replace"
        ).strip()
        raise GitHookError(f"pre-commit: git diff --cached failed: {err or 'unknown error'}")
    return sorted(_parse_name_only_z_output(proc.stdout))


def run_pre_commit_checks(
    repo_root: Path,
    files: list[str],
    commands: list[tuple[str, str]],
) -> int:
    if not files:
        return 0
    present = [rel for rel in files if (repo_root / rel).exists()]
    if not present:
        return 0
    for name, template in commands:
        argv = build_command_argv(template, present)
        code = run_check_argv(argv, worktree=repo_root, check_name=name, mutation_mode="unstaged")
        if code != 0:
            return code
    return 0


def run_pre_commit(repo_root: Path | None = None) -> int:
    root = Path(repo_root or ".").resolve()
    commands = get_pre_commit_commands(root)
    if not commands:
        return 0
    try:
        files = collect_staged_files(root)
    except GitHookError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return run_pre_commit_checks(root, files, commands)


def run_pre_commit_hook(repo_root: Path | None = None) -> int:
    return run_pre_commit(repo_root)


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


def run_pre_push_from_stdin(repo_root: Path | None = None) -> int:
    return run_pre_push(repo_root, stdin=sys.stdin)


def _hook_marker(hook: str) -> str:
    if hook == "pre-commit":
        return HOOK_MARKER_PRE_COMMIT
    return HOOK_MARKER


def _git_hook_filename(hook: str) -> str:
    if hook not in SUPPORTED_HOOKS:
        raise ValueError(f"unsupported hook: {hook!r}")
    return hook


def install_git_hook(
    hook: str,
    repo_root: Path | None = None,
    *,
    force: bool = False,
) -> HookInstallReport:
    if hook not in SUPPORTED_HOOKS:
        raise ValueError(f"unsupported hook: {hook!r}")
    root = Path(repo_root or ".").resolve()
    hooks_dir = git_hooks_dir(root)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    git_name = _git_hook_filename(hook)
    dest = hooks_dir / git_name
    replaced = dest.exists()
    marker = _hook_marker(hook)
    if dest.exists() and not force:
        existing = dest.read_text(encoding="utf-8", errors="replace")
        if marker not in existing:
            raise RuntimeError(
                f"{git_name} hook already exists and is not managed by PLATE; "
                "re-run with --force to replace it"
            )
    template_path = _resolve_hook_template(hook, root)
    content = template_path.read_text(encoding="utf-8")
    dest.write_text(content, encoding="utf-8")
    dest.chmod(dest.stat().st_mode | 0o111)
    return HookInstallReport(
        hook=git_name,
        installed_path=str(dest),
        template_source=str(template_path),
        replaced_existing=replaced,
    )


def install_pre_push_hook(
    repo_root: Path | None = None,
    *,
    force: bool = False,
) -> HookInstallReport:
    return install_git_hook("pre-push", repo_root, force=force)


def install_pre_commit_hook(
    repo_root: Path | None = None,
    *,
    force: bool = False,
) -> HookInstallReport:
    return install_git_hook("pre-commit", repo_root, force=force)


@dataclass
class HookStatusReport:
    repo_root: str
    hook_path: str | None
    hook_installed: bool
    hook_is_plate: bool
    configured_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _single_hook_status(
    root: Path,
    hook: str,
    *,
    command_names: list[str],
) -> HookStatusReport:
    git_name = _git_hook_filename(hook)
    marker = _hook_marker(hook)
    try:
        hooks_dir = git_hooks_dir(root)
        hook_path = hooks_dir / git_name
    except RuntimeError:
        return HookStatusReport(
            repo_root=str(root),
            hook_path=None,
            hook_installed=False,
            hook_is_plate=False,
            configured_commands=command_names,
        )
    installed = hook_path.is_file()
    is_plate = False
    if installed:
        text = hook_path.read_text(encoding="utf-8", errors="replace")
        is_plate = marker in text
    return HookStatusReport(
        repo_root=str(root),
        hook_path=str(hook_path) if installed else None,
        hook_installed=installed,
        hook_is_plate=is_plate,
        configured_commands=command_names,
    )


def pre_push_status(repo_root: Path | None = None) -> HookStatusReport:
    root = Path(repo_root or ".").resolve()
    names = [name for name, _ in get_pre_push_commands(root)]
    return _single_hook_status(root, "pre-push", command_names=names)


def pre_commit_status(repo_root: Path | None = None) -> HookStatusReport:
    root = Path(repo_root or ".").resolve()
    names = [name for name, _ in get_pre_commit_commands(root)]
    return _single_hook_status(root, "pre-commit", command_names=names)


@dataclass
class GitHooksStatusReport:
    repo_root: str
    pre_push: HookStatusReport
    pre_commit: HookStatusReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "pre_push": self.pre_push.to_dict(),
            "pre_commit": self.pre_commit.to_dict(),
        }


def git_hooks_status(repo_root: Path | None = None) -> GitHooksStatusReport:
    root = Path(repo_root or ".").resolve()
    return GitHooksStatusReport(
        repo_root=str(root),
        pre_push=pre_push_status(root),
        pre_commit=pre_commit_status(root),
    )


def validate_hooks_config(hooks: Any) -> None:
    if hooks is None:
        return
    if not isinstance(hooks, dict):
        raise PlateConfigError("'hooks' must be an object if present")
    allowed_hook_names = {"pre_push", "pre_commit"}
    unknown_hooks = sorted(set(hooks) - allowed_hook_names)
    if unknown_hooks:
        raise PlateConfigError(f"unknown hooks keys: {', '.join(unknown_hooks)}")
    for section_key in allowed_hook_names:
        section = hooks.get(section_key)
        if section is None:
            continue
        if not isinstance(section, dict):
            raise PlateConfigError(f"'hooks.{section_key}' must be an object if present")
        unknown_cmds = sorted(set(section) - set(PRE_HOOK_COMMAND_KEYS))
        if unknown_cmds:
            raise PlateConfigError(
                f"unknown hooks.{section_key} keys: {', '.join(unknown_cmds)} "
                f"(allowed: {', '.join(PRE_HOOK_COMMAND_KEYS)})"
            )
        for key in PRE_HOOK_COMMAND_KEYS:
            val = section.get(key)
            if val is not None and not isinstance(val, str):
                raise PlateConfigError(f"hooks.{section_key}.{key} must be a string if present")
