"""Shared PLATE workflow runs-on selection (#1214).

Adopters may set repository variable ``PLATE_RUNS_ON`` to a JSON array of runner
labels (for example ``["self-hosted", "plate-local"]``). Heavy jobs probe for an
idle self-hosted runner with those labels and fall back to ``ubuntu-latest`` when
none is available, with a bounded wait. Public repositories and fork pull requests
always use GitHub-hosted runners.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

PLATE_RUNS_ON_VAR = "PLATE_RUNS_ON"
PLATE_RUNNER_PROBE_TIMEOUT_VAR = "PLATE_RUNNER_PROBE_TIMEOUT_SECONDS"
DEFAULT_PROBE_TIMEOUT_SECONDS = 30
DEFAULT_RUNS_ON: tuple[str, ...] = ("ubuntu-latest",)
HOSTED_RUNNER_LABELS: frozenset[str] = frozenset(
    {
        "ubuntu-latest",
        "ubuntu-24.04",
        "ubuntu-22.04",
        "windows-latest",
        "windows-2022",
        "macos-latest",
        "macos-14",
        "macos-13",
    }
)

# Expression used when a job reads ``needs.<job>.outputs.runs_on`` after the probe step.
RUNS_ON_FROM_NEEDS_OUTPUT = "${{ fromJSON(needs.{needs_job}.outputs.runs_on) }}"

# Default override when no dynamic probe job ran (lightweight jobs only).
RUNS_ON_VAR_EXPRESSION = (
    '${{ fromJSON(vars.PLATE_RUNS_ON || \'["ubuntu-latest"]\') }}'
)


def parse_runs_on_var(raw: str | None) -> list[str]:
    """Parse ``PLATE_RUNS_ON`` repository variable text into a label list."""
    if raw is None or not str(raw).strip():
        return list(DEFAULT_RUNS_ON)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return list(DEFAULT_RUNS_ON)
    if isinstance(parsed, str):
        return [parsed]
    if isinstance(parsed, list) and all(isinstance(x, str) and x for x in parsed):
        return list(parsed)
    return list(DEFAULT_RUNS_ON)


def is_hosted_only(labels: Sequence[str]) -> bool:
    return bool(labels) and all(label in HOSTED_RUNNER_LABELS for label in labels)


def runner_is_idle_match(
    runner: Mapping[str, Any], required_labels: Sequence[str]
) -> bool:
    if runner.get("status") != "online":
        return False
    if runner.get("busy"):
        return False
    runner_labels = {lbl.get("name") for lbl in (runner.get("labels") or [])}
    return all(label in runner_labels for label in required_labels)


def has_idle_runner(
    runners: Sequence[Mapping[str, Any]], required_labels: Sequence[str]
) -> bool:
    return any(runner_is_idle_match(r, required_labels) for r in runners)


def choose_runs_on(
    *,
    plate_runs_on_var: str | None,
    is_private_repo: bool,
    is_fork_pull_request: bool,
    runners: Sequence[Mapping[str, Any]] | None = None,
) -> list[str]:
    """Return the label list heavy jobs should use after a runner probe completes."""
    if not is_private_repo or is_fork_pull_request:
        return list(DEFAULT_RUNS_ON)

    configured = parse_runs_on_var(plate_runs_on_var)
    if is_hosted_only(configured):
        return configured

    if runners is None:
        return list(DEFAULT_RUNS_ON)

    if has_idle_runner(runners, configured):
        return configured
    return list(DEFAULT_RUNS_ON)


def composite_action_yaml() -> str:
    """Composite action that probes runners and sets ``runs_on`` output."""
    script = github_script_select_runs_on().strip()
    indented = "\n".join(f"            {line}" for line in script.splitlines())
    return f"""name: PLATE select runs-on
description: >-
  Choose runs-on labels from PLATE_RUNS_ON with idle-runner probe and hosted fallback (#1214).
inputs:
  probe-timeout-seconds:
    description: Max seconds to wait for an idle matching self-hosted runner
    required: false
    default: '{DEFAULT_PROBE_TIMEOUT_SECONDS}'
  plate-runs-on:
    description: Value of repository variable PLATE_RUNS_ON (JSON label array)
    required: false
    default: ''
  github-token:
    description: >-
      Token for the self-hosted runner list API. GITHUB_TOKEN cannot call this
      endpoint; use a classic PAT with repo scope or a fine-grained PAT with
      Administration read on the repository. Defaults to the job GITHUB_TOKEN.
    required: false
    default: ''
outputs:
  runs_on:
    description: JSON array for runs-on (for example ["ubuntu-latest"])
    value: ${{{{ steps.select.outputs.runs_on }}}}
runs:
  using: composite
  steps:
    - id: select
      uses: actions/github-script@v8
      env:
        PLATE_RUNS_ON: ${{{{ inputs.plate-runs-on }}}}
        PLATE_RUNNER_PROBE_TIMEOUT_SECONDS: ${{{{ inputs.probe-timeout-seconds }}}}
      with:
        github-token: ${{{{ inputs.github-token || github.token }}}}
        script: |
{indented}
"""


def github_script_select_runs_on() -> str:
    """JavaScript body for the select-runs-on github-script step."""
    return """
const DEFAULT_RUNS_ON = ['ubuntu-latest'];
const HOSTED = new Set(%s);

function parseConfigured(raw) {
  if (!raw || !String(raw).trim()) return [...DEFAULT_RUNS_ON];
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed === 'string') return [parsed];
    if (Array.isArray(parsed) && parsed.every((x) => typeof x === 'string' && x)) {
      return parsed;
    }
  } catch (e) {
    core.info(`PLATE_RUNS_ON parse failed: ${e.message}`);
  }
  return [...DEFAULT_RUNS_ON];
}

function isHostedOnly(labels) {
  return labels.length > 0 && labels.every((l) => HOSTED.has(l));
}

function runnerMatches(runner, required) {
  if (runner.status !== 'online' || runner.busy) return false;
  const names = new Set((runner.labels || []).map((l) => l.name));
  return required.every((label) => names.has(label));
}

async function listRunners() {
  try {
    const { data } = await github.rest.actions.listSelfHostedRunnersForRepo({
      owner: context.repo.owner,
      repo: context.repo.repo,
    });
    return data.runners || [];
  } catch (err) {
    const status = err.status || err.response?.status;
    core.warning(
      `Self-hosted runner probe failed (${status || 'network'}: ${err.message || err}); ` +
        `treating as no idle runner and falling back to hosted.`,
    );
    return null;
  }
}

function isUnsafeForLocal() {
  const repo = context.payload.repository;
  if (!repo?.private) {
    core.info('Public repository: forcing GitHub-hosted runners.');
    return true;
  }
  const pr = context.payload.pull_request;
  if (pr?.head?.repo?.full_name) {
    const canonical = `${context.repo.owner}/${context.repo.repo}`;
    if (pr.head.repo.full_name !== canonical) {
      core.info('Fork pull request: forcing GitHub-hosted runners.');
      return true;
    }
  }
  return false;
}

const configured = parseConfigured(process.env.PLATE_RUNS_ON);
let chosen = [...configured];

if (isUnsafeForLocal()) {
  chosen = [...DEFAULT_RUNS_ON];
} else if (!isHostedOnly(configured)) {
  const timeoutSec = Math.max(
    0,
    parseInt(process.env.PLATE_RUNNER_PROBE_TIMEOUT_SECONDS || '%d', 10) || 0,
  );
  const deadline = Date.now() + timeoutSec * 1000;
  let idle = false;
  while (Date.now() <= deadline) {
    const runners = await listRunners();
    if (runners === null) {
      idle = false;
      break;
    }
    idle = runners.some((r) => runnerMatches(r, configured));
    if (idle) {
      core.info(`Idle self-hosted runner available for ${JSON.stringify(configured)}.`);
      break;
    }
    if (timeoutSec === 0) break;
    core.info('No idle matching runner; waiting before retry or hosted fallback...');
    if (Date.now() >= deadline) break;
    await new Promise((resolve) => setTimeout(resolve, Math.min(5000, deadline - Date.now())));
  }
  if (!idle) {
    core.info(
      `Probe timed out after ${timeoutSec}s; falling back to ${JSON.stringify(DEFAULT_RUNS_ON)}.`,
    );
    chosen = [...DEFAULT_RUNS_ON];
  }
}

core.setOutput('runs_on', JSON.stringify(chosen));
core.info(`PLATE runs-on selection: ${JSON.stringify(chosen)}`);
""" % (
        json.dumps(sorted(HOSTED_RUNNER_LABELS)),
        DEFAULT_PROBE_TIMEOUT_SECONDS,
    )


def action_paths(repo_root: Any) -> tuple[Any, Any]:
    from pathlib import Path

    root = Path(repo_root)
    return (
        root / ".github" / "actions" / "plate-select-runs-on" / "action.yml",
        root
        / "src"
        / "plate_core"
        / "template_payload"
        / ".github"
        / "actions"
        / "plate-select-runs-on"
        / "action.yml",
    )
