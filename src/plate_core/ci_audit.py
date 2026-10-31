"""GitHub Actions CI timing audit (#1282).

Splits recent workflow job time into waiting (queued), setup (heuristic), and running.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .github_client import GhApiError, GhClient
from .health import resolve_repo
from .runner import parse_repo_slug

CI_AUDIT_DOC = "docs/design/ci-audit-command.md"

# Documented setup-step name heuristic (case-insensitive substring match).
SETUP_STEP_SUBSTRINGS = ("checkout", "setup", "set up", "install", "cache")

# First step whose name matches any of these (regex) ends the setup phase.
TEST_STEP_PATTERNS = (
    re.compile(r"\btests?\b", re.I),
    re.compile(r"\bpytest\b", re.I),
    re.compile(r"\bunittest\b", re.I),
    re.compile(r"\bnpm run test\b", re.I),
    re.compile(r"\bcargo test\b", re.I),
    re.compile(r"\bgo test\b", re.I),
    re.compile(r"\bvitest\b", re.I),
    re.compile(r"\bjest\b", re.I),
)

CACHE_HIT_SUBSTRINGS = ("cache hit", "cache restored", "restored cache", "cache restore")
CACHE_MISS_SUBSTRINGS = ("cache miss", "cache not found", "no cache", "cache save")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _duration_seconds(start: str | None, end: str | None) -> float:
    s = _parse_ts(start)
    e = _parse_ts(end)
    if not s or not e:
        return 0.0
    return max(0.0, (e - s).total_seconds())


def is_setup_step_name(name: str) -> bool:
    lower = (name or "").lower()
    return any(token in lower for token in SETUP_STEP_SUBSTRINGS)


def is_test_step_name(name: str) -> bool:
    text = name or ""
    return any(p.search(text) for p in TEST_STEP_PATTERNS)


def split_step_seconds(steps: list[dict[str, Any]]) -> tuple[float, float]:
    """Return (setup_seconds, running_seconds) from GitHub job steps."""
    ordered = sorted(steps, key=lambda s: int(s.get("number") or 0))
    setup_secs = 0.0
    running_secs = 0.0
    seen_test = False
    for step in ordered:
        secs = _duration_seconds(step.get("started_at"), step.get("completed_at"))
        name = str(step.get("name") or "")
        if seen_test:
            running_secs += secs
        elif is_test_step_name(name):
            seen_test = True
            running_secs += secs
        elif is_setup_step_name(name):
            setup_secs += secs
        else:
            running_secs += secs
    return setup_secs, running_secs


def cache_visibility_from_steps(steps: list[dict[str, Any]]) -> list[str]:
    """Best-effort cache hit/miss hints from step names (logs are not fetched)."""
    hints: list[str] = []
    for step in steps:
        name = (step.get("name") or "").lower()
        if "cache" not in name:
            continue
        if any(token in name for token in CACHE_HIT_SUBSTRINGS):
            hints.append("hit")
        elif any(token in name for token in CACHE_MISS_SUBSTRINGS):
            hints.append("miss")
        else:
            hints.append("cache_step")
    return hints


def job_waiting_seconds(job: dict[str, Any]) -> float:
    return _duration_seconds(job.get("created_at"), job.get("started_at"))


@dataclass
class JobTimingRow:
    run_id: int
    workflow_name: str
    run_number: int
    job_id: int
    job_name: str
    conclusion: str | None
    waiting_seconds: float
    setup_seconds: float
    running_seconds: float
    cache_hints: list[str] = field(default_factory=list)

    @property
    def total_seconds(self) -> float:
        return self.waiting_seconds + self.setup_seconds + self.running_seconds

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["total_seconds"] = self.total_seconds
        data["waiting_minutes"] = round(self.waiting_seconds / 60.0, 2)
        data["setup_minutes"] = round(self.setup_seconds / 60.0, 2)
        data["running_minutes"] = round(self.running_seconds / 60.0, 2)
        data["total_minutes"] = round(self.total_seconds / 60.0, 2)
        return data


@dataclass
class CostliestJobRow:
    workflow_name: str
    job_name: str
    instances: int
    waiting_seconds: float
    setup_seconds: float
    running_seconds: float
    cache_hits: int
    cache_misses: int
    cache_unknown: int

    @property
    def total_seconds(self) -> float:
        return self.waiting_seconds + self.setup_seconds + self.running_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "job_name": self.job_name,
            "instances": self.instances,
            "waiting_seconds": round(self.waiting_seconds, 1),
            "setup_seconds": round(self.setup_seconds, 1),
            "running_seconds": round(self.running_seconds, 1),
            "total_seconds": round(self.total_seconds, 1),
            "waiting_minutes": round(self.waiting_seconds / 60.0, 2),
            "setup_minutes": round(self.setup_seconds / 60.0, 2),
            "running_minutes": round(self.running_seconds / 60.0, 2),
            "total_minutes": round(self.total_seconds / 60.0, 2),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_unknown": self.cache_unknown,
        }


@dataclass
class CiAuditReport:
    ok: bool
    repo: str
    limit: int
    workflow_runs_fetched: int
    job_instances: list[JobTimingRow] = field(default_factory=list)
    costliest_jobs: list[CostliestJobRow] = field(default_factory=list)
    error: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "repo": self.repo,
            "limit": self.limit,
            "workflow_runs_fetched": self.workflow_runs_fetched,
            "heuristic_doc": CI_AUDIT_DOC,
            "setup_step_substrings": list(SETUP_STEP_SUBSTRINGS),
            "job_instances": [row.to_dict() for row in self.job_instances],
            "costliest_jobs": [row.to_dict() for row in self.costliest_jobs],
            "error": self.error,
            "message": self.message,
        }


def _list_workflow_runs(
    client: GhClient, owner: str, repo: str, limit: int
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    page = 1
    per_page = min(100, max(1, limit))
    while len(runs) < limit:
        payload = client.api(
            f"repos/{owner}/{repo}/actions/runs",
            fields={"per_page": per_page, "page": page},
        )
        batch = list((payload or {}).get("workflow_runs") or [])
        if not batch:
            break
        runs.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return runs[:limit]


def _list_jobs_for_run(
    client: GhClient, owner: str, repo: str, run_id: int
) -> list[dict[str, Any]]:
    payload = client.api(
        f"repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
        fields={"per_page": 100},
    )
    return list((payload or {}).get("jobs") or [])


def _aggregate_costliest(rows: list[JobTimingRow], top_n: int = 15) -> list[CostliestJobRow]:
    buckets: dict[tuple[str, str], CostliestJobRow] = {}
    for row in rows:
        key = (row.workflow_name, row.job_name)
        if key not in buckets:
            buckets[key] = CostliestJobRow(
                workflow_name=row.workflow_name,
                job_name=row.job_name,
                instances=0,
                waiting_seconds=0.0,
                setup_seconds=0.0,
                running_seconds=0.0,
                cache_hits=0,
                cache_misses=0,
                cache_unknown=0,
            )
        bucket = buckets[key]
        bucket.instances += 1
        bucket.waiting_seconds += row.waiting_seconds
        bucket.setup_seconds += row.setup_seconds
        bucket.running_seconds += row.running_seconds
        for hint in row.cache_hints:
            if hint == "hit":
                bucket.cache_hits += 1
            elif hint == "miss":
                bucket.cache_misses += 1
            else:
                bucket.cache_unknown += 1
    ranked = sorted(buckets.values(), key=lambda b: b.total_seconds, reverse=True)
    return ranked[:top_n]


def run_ci_audit(
    repo: str | None = None,
    *,
    limit: int = 30,
    client: GhClient | None = None,
) -> CiAuditReport:
    """Fetch recent workflow runs and compute per-job timing buckets."""
    if limit < 1:
        return CiAuditReport(
            ok=False,
            repo=repo or "",
            limit=limit,
            workflow_runs_fetched=0,
            error="invalid_limit",
            message="--limit must be at least 1",
        )
    gh = client or GhClient()
    try:
        slug = resolve_repo(repo)
        owner, name = parse_repo_slug(slug)
    except (RuntimeError, ValueError) as exc:
        return CiAuditReport(
            ok=False,
            repo=repo or "",
            limit=limit,
            workflow_runs_fetched=0,
            error="repo_resolution",
            message=str(exc),
        )

    try:
        runs = _list_workflow_runs(gh, owner, name, limit)
    except GhApiError as exc:
        return CiAuditReport(
            ok=False,
            repo=slug,
            limit=limit,
            workflow_runs_fetched=0,
            error="github_api",
            message=str(exc),
        )

    job_rows: list[JobTimingRow] = []
    for run in runs:
        run_id = int(run.get("id") or 0)
        if not run_id:
            continue
        workflow_name = str(run.get("name") or run.get("path") or "workflow")
        run_number = int(run.get("run_number") or 0)
        try:
            jobs = _list_jobs_for_run(gh, owner, name, run_id)
        except GhApiError:
            continue
        for job in jobs:
            steps = list(job.get("steps") or [])
            setup_secs, running_secs = split_step_seconds(steps)
            job_rows.append(
                JobTimingRow(
                    run_id=run_id,
                    workflow_name=workflow_name,
                    run_number=run_number,
                    job_id=int(job.get("id") or 0),
                    job_name=str(job.get("name") or "job"),
                    conclusion=job.get("conclusion"),
                    waiting_seconds=job_waiting_seconds(job),
                    setup_seconds=setup_secs,
                    running_seconds=running_secs,
                    cache_hints=cache_visibility_from_steps(steps),
                )
            )

    costliest = _aggregate_costliest(job_rows)
    return CiAuditReport(
        ok=True,
        repo=slug,
        limit=limit,
        workflow_runs_fetched=len(runs),
        job_instances=job_rows,
        costliest_jobs=costliest,
    )


def format_ci_audit_text(report: CiAuditReport) -> str:
    lines: list[str] = []
    if not report.ok:
        lines.append(f"CI audit failed: {report.error or 'unknown'}")
        if report.message:
            lines.append(f"  {report.message}")
        return "\n".join(lines)

    lines.append(f"Repo: {report.repo}")
    lines.append(
        f"Workflow runs fetched: {report.workflow_runs_fetched} (limit={report.limit})"
    )
    lines.append(f"Heuristic: {CI_AUDIT_DOC}")
    lines.append("")
    lines.append("Costliest jobs (aggregated total minutes across fetched runs):")
    if not report.costliest_jobs:
        lines.append("  (no completed jobs in sample)")
    for row in report.costliest_jobs:
        cache_bits = []
        if row.cache_hits:
            cache_bits.append(f"hit={row.cache_hits}")
        if row.cache_misses:
            cache_bits.append(f"miss={row.cache_misses}")
        if row.cache_unknown:
            cache_bits.append(f"cache_steps={row.cache_unknown}")
        cache_txt = f" cache [{', '.join(cache_bits)}]" if cache_bits else ""
        lines.append(
            f"  {row.workflow_name} / {row.job_name} (n={row.instances}): "
            f"total={row.total_seconds / 60.0:.1f}m "
            f"(wait={row.waiting_seconds / 60.0:.1f}m "
            f"setup={row.setup_seconds / 60.0:.1f}m "
            f"run={row.running_seconds / 60.0:.1f}m){cache_txt}"
        )
    lines.append("")
    lines.append("Recent job instances (up to 20):")
    for row in report.job_instances[:20]:
        hints = ",".join(row.cache_hints) if row.cache_hints else "-"
        lines.append(
            f"  run #{row.run_number} {row.workflow_name}/{row.job_name}: "
            f"wait={row.waiting_seconds / 60.0:.1f}m "
            f"setup={row.setup_seconds / 60.0:.1f}m "
            f"run={row.running_seconds / 60.0:.1f}m cache={hints}"
        )
    if len(report.job_instances) > 20:
        lines.append(f"  ... and {len(report.job_instances) - 20} more (use --json for full list)")
    return "\n".join(lines)
