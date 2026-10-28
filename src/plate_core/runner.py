"""Self-hosted Actions runner helpers for private repos (#1210 / #1212)."""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from .github_client import GhApiError, GhClient
from .procutil import run_hidden

SHARED_RUNNER_LABEL = "plate-local"
RUNNER_STATE_REL = Path(".agentic") / "runner.json"
REQUIRED_TOKEN_SCOPES = frozenset({"repo"})
PUBLIC_REPO_ERROR = "public_repo_forbidden"


class SubprocessRunner(Protocol):
    def __call__(
        self, args: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None
    ) -> tuple[int, str, str]: ...


def _default_subprocess(args: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = run_hidden(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_repo_slug(repo: str) -> tuple[str, str]:
    repo = (repo or "").strip()
    if repo.count("/") != 1:
        raise ValueError("REPO must be owner/name")
    owner, name = repo.split("/", 1)
    if not owner or not name:
        raise ValueError("REPO must be owner/name")
    return owner, name


def detect_os_label(explicit: str | None = None) -> str:
    if explicit:
        label = explicit.strip().lower()
        if label not in ("linux", "windows", "macos"):
            raise ValueError("OS label must be one of: linux, windows, macos")
        return label
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def runner_state_path(repo_root: str | Path) -> Path:
    return Path(repo_root).resolve() / RUNNER_STATE_REL


def load_runner_state(repo_root: str | Path) -> dict[str, Any] | None:
    path = runner_state_path(repo_root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_runner_state(repo_root: str | Path, state: dict[str, Any]) -> Path:
    path = runner_state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def clear_runner_state(repo_root: str | Path) -> bool:
    path = runner_state_path(repo_root)
    if path.is_file():
        path.unlink()
        return True
    return False


def _repo_visibility(client: GhClient, owner: str, repo: str) -> dict[str, Any]:
    data = client.api(f"repos/{owner}/{repo}") or {}
    if not isinstance(data, dict):
        raise GhApiError("Unexpected repo metadata response")
    return data


def ensure_private_repo(client: GhClient, owner: str, repo: str) -> dict[str, Any] | None:
    """Return error dict when the repo is public; otherwise return None."""
    meta = _repo_visibility(client, owner, repo)
    if meta.get("private") is not True:
        return {
            "ok": False,
            "error": PUBLIC_REPO_ERROR,
            "message": (
                "Self-hosted runners are allowed only on private repositories. "
                "Never register a runner on a public repo."
            ),
            "repo": f"{owner}/{repo}",
        }
    return None


def runner_labels(os_label: str) -> list[str]:
    return [SHARED_RUNNER_LABEL, os_label]


@dataclass
class RunnerAddReport:
    ok: bool
    dry_run: bool
    repo: str
    labels: list[str]
    ephemeral: bool = True
    actions: list[dict[str, str]] = field(default_factory=list)
    state_path: str | None = None
    error: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def plan_runner_add(
    repo: str,
    *,
    os_label: str | None = None,
    client: GhClient | None = None,
) -> RunnerAddReport:
    owner, name = parse_repo_slug(repo)
    labels = runner_labels(detect_os_label(os_label))
    slug = f"{owner}/{name}"
    client = client or GhClient()
    refusal = ensure_private_repo(client, owner, name)
    if refusal:
        return RunnerAddReport(
            ok=False,
            dry_run=True,
            repo=slug,
            labels=labels,
            error=refusal["error"],
            message=refusal["message"],
        )
    actions = [
        {"action": "fetch_registration_token", "state": "planned"},
        {"action": "configure_ephemeral_runner", "state": "planned", "detail": f"labels={','.join(labels)}"},
        {"action": "record_runner_state", "state": "planned", "detail": str(RUNNER_STATE_REL)},
    ]
    return RunnerAddReport(ok=True, dry_run=True, repo=slug, labels=labels, actions=actions)


def apply_runner_add(
    repo: str,
    *,
    repo_root: str | Path = ".",
    os_label: str | None = None,
    client: GhClient | None = None,
    subprocess_runner: SubprocessRunner | None = None,
    runner_config_cmd: str | None = None,
) -> RunnerAddReport:
    plan = plan_runner_add(repo, os_label=os_label, client=client)
    if not plan.ok:
        plan.dry_run = False
        return plan

    owner, name = parse_repo_slug(repo)
    slug = f"{owner}/{name}"
    labels = plan.labels
    client = client or GhClient()
    subprocess_runner = subprocess_runner or _default_subprocess
    actions: list[dict[str, str]] = []

    token_resp = client.api(
        f"repos/{owner}/{name}/actions/runners/registration-token",
        method="POST",
    ) or {}
    token = token_resp.get("token") if isinstance(token_resp, dict) else None
    if not token:
        return RunnerAddReport(
            ok=False,
            dry_run=False,
            repo=slug,
            labels=labels,
            error="registration_token_failed",
            message="Could not obtain a runner registration token (admin repo access required).",
        )
    actions.append({"action": "fetch_registration_token", "state": "done"})

    local_config = Path(repo_root) / ".agentic" / "runner" / "config.sh"
    config = runner_config_cmd or (str(local_config) if local_config.is_file() else "")

    if config:
        label_arg = ",".join(labels)
        rc, out, err = subprocess_runner(
            [
                config,
                "--url",
                f"https://github.com/{slug}",
                "--token",
                str(token),
                "--labels",
                label_arg,
                "--ephemeral",
                "--unattended",
            ],
            cwd=str(Path(repo_root).resolve()),
        )
        if rc != 0:
            return RunnerAddReport(
                ok=False,
                dry_run=False,
                repo=slug,
                labels=labels,
                actions=actions,
                error="runner_configure_failed",
                message=(err or out or "Runner configure command failed").strip()[:500],
            )
        actions.append({"action": "configure_ephemeral_runner", "state": "done"})
    else:
        actions.append(
            {
                "action": "configure_ephemeral_runner",
                "state": "skipped",
                "detail": "No config.sh found; recorded token registration only",
            }
        )

    state = {
        "repo": slug,
        "labels": labels,
        "ephemeral": True,
        "registered_at": _utc_now_iso(),
        "isolation": {
            "non_admin_user": True,
            "no_personal_files_access": True,
            "ephemeral": True,
        },
    }
    path = save_runner_state(repo_root, state)
    actions.append({"action": "record_runner_state", "state": "done", "detail": str(path)})

    return RunnerAddReport(
        ok=True,
        dry_run=False,
        repo=slug,
        labels=labels,
        actions=actions,
        state_path=str(path),
    )


@dataclass
class RunnerStatusRow:
    id: int
    name: str
    status: str
    busy: bool
    labels: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunnerStatusReport:
    ok: bool
    repo: str | None
    runners: list[RunnerStatusRow] = field(default_factory=list)
    error: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": self.ok, "runners": [r.to_dict() for r in self.runners]}
        if self.repo:
            payload["repo"] = self.repo
        if self.error:
            payload["error"] = self.error
        if self.message:
            payload["message"] = self.message
        return payload


def get_runner_status(
    *,
    repo: str | None = None,
    repo_root: str | Path = ".",
    client: GhClient | None = None,
) -> RunnerStatusReport:
    state = load_runner_state(repo_root)
    slug = repo or (state or {}).get("repo")
    if not slug:
        return RunnerStatusReport(
            ok=False,
            error="repo_required",
            message="Pass REPO as owner/name or register a runner first (add).",
        )
    owner, name = parse_repo_slug(slug)
    client = client or GhClient()
    refusal = ensure_private_repo(client, owner, name)
    if refusal:
        return RunnerStatusReport(
            ok=False,
            repo=slug,
            error=refusal["error"],
            message=refusal["message"],
        )
    data = client.api(f"repos/{owner}/{name}/actions/runners") or {}
    raw = data.get("runners", []) if isinstance(data, dict) else []
    rows: list[RunnerStatusRow] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label_names = [lb.get("name", "") for lb in (item.get("labels") or []) if isinstance(lb, dict)]
        rows.append(
            RunnerStatusRow(
                id=int(item.get("id") or 0),
                name=str(item.get("name") or ""),
                status=str(item.get("status") or "unknown"),
                busy=bool(item.get("busy")),
                labels=label_names,
            )
        )
    return RunnerStatusReport(ok=True, repo=slug, runners=rows)


@dataclass
class RunnerRemoveReport:
    ok: bool
    dry_run: bool
    repo: str | None = None
    removed_runner_ids: list[int] = field(default_factory=list)
    state_cleared: bool = False
    actions: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def plan_runner_remove(
    *,
    repo: str | None = None,
    repo_root: str | Path = ".",
    client: GhClient | None = None,
) -> RunnerRemoveReport:
    state = load_runner_state(repo_root)
    slug = repo or (state or {}).get("repo")
    if not slug:
        return RunnerRemoveReport(
            ok=False,
            dry_run=True,
            error="repo_required",
            message="Pass REPO as owner/name or register a runner first (add).",
        )
    owner, name = parse_repo_slug(slug)
    client = client or GhClient()
    refusal = ensure_private_repo(client, owner, name)
    if refusal:
        return RunnerRemoveReport(
            ok=False,
            dry_run=True,
            repo=slug,
            error=refusal["error"],
            message=refusal["message"],
        )
    status = get_runner_status(repo=slug, repo_root=repo_root, client=client)
    actions = [
        {"action": "remove_runner_registration", "state": "planned", "detail": f"count={len(status.runners)}"},
        {"action": "clear_runner_state", "state": "planned", "detail": str(RUNNER_STATE_REL)},
    ]
    return RunnerRemoveReport(ok=True, dry_run=True, repo=slug, actions=actions)


def apply_runner_remove(
    *,
    repo: str | None = None,
    repo_root: str | Path = ".",
    client: GhClient | None = None,
    subprocess_runner: SubprocessRunner | None = None,
    runner_config_cmd: str | None = None,
) -> RunnerRemoveReport:
    plan = plan_runner_remove(repo=repo, repo_root=repo_root, client=client)
    if not plan.ok:
        plan.dry_run = False
        return plan
    slug = plan.repo
    assert slug
    owner, name = parse_repo_slug(slug)
    client = client or GhClient()
    subprocess_runner = subprocess_runner or _default_subprocess
    actions: list[dict[str, str]] = []
    removed: list[int] = []

    status = get_runner_status(repo=slug, repo_root=repo_root, client=client)
    for row in status.runners:
        client.api(f"repos/{owner}/{name}/actions/runners/{row.id}", method="DELETE")
        removed.append(row.id)
    actions.append({"action": "remove_runner_registration", "state": "done", "detail": f"ids={removed}"})

    local_config = Path(repo_root) / ".agentic" / "runner" / "config.sh"
    config = runner_config_cmd or (str(local_config) if local_config.is_file() else "")
    if config:
        remove_token = client.api(
            f"repos/{owner}/{name}/actions/runners/remove-token",
            method="POST",
        ) or {}
        token = remove_token.get("token") if isinstance(remove_token, dict) else None
        if token:
            subprocess_runner([config, "remove", "--token", str(token)], cwd=str(Path(repo_root).resolve()))
        actions.append({"action": "runner_config_remove", "state": "done"})

    cleared = clear_runner_state(repo_root)
    actions.append({"action": "clear_runner_state", "state": "done" if cleared else "skipped"})

    return RunnerRemoveReport(
        ok=True,
        dry_run=False,
        repo=slug,
        removed_runner_ids=removed,
        state_cleared=cleared,
        actions=actions,
    )


def _gh_auth_scopes(subprocess_runner: SubprocessRunner | None = None) -> list[str]:
    subprocess_runner = subprocess_runner or _default_subprocess
    rc, out, err = subprocess_runner(["gh", "auth", "status", "--hostname", "github.com"])
    text = f"{out}\n{err}"
    if rc != 0:
        return []
    scopes: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if "token scopes:" in lower or "scopes:" in lower:
            part = line.split(":", 1)[-1]
            scopes.extend(s.strip() for s in part.replace(",", " ").split() if s.strip())
    return scopes


@dataclass
class DoctorCheck:
    id: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunnerDoctorReport:
    ok: bool
    checks: list[DoctorCheck] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [c.to_dict() for c in self.checks],
            **({"error": self.error} if self.error else {}),
        }


def run_runner_doctor(
    *,
    repo_root: str | Path = ".",
    client: GhClient | None = None,
    subprocess_runner: SubprocessRunner | None = None,
    service_probe: Callable[[], bool] | None = None,
) -> RunnerDoctorReport:
    client = client or GhClient()
    subprocess_runner = subprocess_runner or _default_subprocess
    checks: list[DoctorCheck] = []
    ok = True

    state = load_runner_state(repo_root)
    if not state:
        checks.append(DoctorCheck("runner_state", "warn", f"Missing {RUNNER_STATE_REL}; run runner add first"))
        ok = False
    else:
        labels = state.get("labels") or []
        expected = {SHARED_RUNNER_LABEL}
        os_labels = [lb for lb in labels if lb in ("linux", "windows", "macos")]
        if SHARED_RUNNER_LABEL not in labels:
            checks.append(DoctorCheck("labels", "fail", f"Missing shared label {SHARED_RUNNER_LABEL}"))
            ok = False
        elif not os_labels:
            checks.append(DoctorCheck("labels", "fail", "Missing OS label (linux, windows, or macos)"))
            ok = False
        else:
            checks.append(DoctorCheck("labels", "pass", f"labels={labels}"))

        if state.get("ephemeral") is not True:
            checks.append(DoctorCheck("ephemeral", "fail", "Runner must be ephemeral"))
            ok = False
        else:
            checks.append(DoctorCheck("ephemeral", "pass", "ephemeral=true"))

        isolation = state.get("isolation") or {}
        iso_ok = bool(isolation.get("non_admin_user")) and bool(isolation.get("no_personal_files_access"))
        if iso_ok:
            checks.append(DoctorCheck("isolation", "pass", "non-admin user and no personal file access declared"))
        else:
            checks.append(
                DoctorCheck(
                    "isolation",
                    "warn",
                    "Set isolation.non_admin_user and isolation.no_personal_files_access in runner state",
                )
            )
            ok = False

        slug = state.get("repo")
        if slug:
            try:
                owner, name = parse_repo_slug(str(slug))
                refusal = ensure_private_repo(client, owner, name)
                if refusal:
                    checks.append(DoctorCheck("repo_visibility", "fail", refusal["message"] or refusal["error"]))
                    ok = False
                else:
                    checks.append(DoctorCheck("repo_visibility", "pass", f"private repo {slug}"))
            except ValueError as exc:
                checks.append(DoctorCheck("repo_visibility", "fail", str(exc)))
                ok = False

    scopes = _gh_auth_scopes(subprocess_runner)
    if not scopes:
        checks.append(DoctorCheck("token_scopes", "fail", "Could not read gh auth scopes (run gh auth login)"))
        ok = False
    elif not REQUIRED_TOKEN_SCOPES.issubset(set(scopes)):
        missing = sorted(REQUIRED_TOKEN_SCOPES - set(scopes))
        checks.append(DoctorCheck("token_scopes", "fail", f"Missing scopes: {', '.join(missing)}"))
        ok = False
    else:
        checks.append(DoctorCheck("token_scopes", "pass", f"scopes include {', '.join(sorted(REQUIRED_TOKEN_SCOPES))}"))

    if service_probe is not None:
        running = service_probe()
        if running:
            checks.append(DoctorCheck("service", "pass", "Runner service/process reported running"))
        else:
            checks.append(DoctorCheck("service", "warn", "Runner service/process not detected"))
            ok = False
    else:
        rc, _, _ = subprocess_runner(["gh", "auth", "status"])
        if rc == 0:
            checks.append(DoctorCheck("gh_cli", "pass", "gh CLI authenticated"))
        else:
            checks.append(DoctorCheck("gh_cli", "fail", "gh CLI not authenticated"))
            ok = False

    return RunnerDoctorReport(ok=ok, checks=checks)
