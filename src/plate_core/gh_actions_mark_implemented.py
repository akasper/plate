"""GitHub Actions entry: mark ``status:implemented`` + integration close (#427 / #1385).

Invoked from ``plate-pr-gates`` with ``GITHUB_EVENT_PATH`` and ``GITHUB_TOKEN`` set.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from plate_core.integration_close import render_close_comment, should_auto_close_issue
from plate_core.issue_status_lifecycle import (
    ALLOWED_STATUS_LABELS,
    should_apply_status_implemented,
    transition_label_deltas,
)
from plate_core.pr_gates_closing import parse_strict_closing_issue_numbers


def _req_json(method: str, url: str, token: str, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "plate-pr-gates-mark-implemented",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
        method=method,
    )
    with urllib.request.urlopen(r, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not token or not event_path:
        print("GITHUB_TOKEN and GITHUB_EVENT_PATH are required.", file=sys.stderr)
        return 1

    with open(event_path, encoding="utf-8") as f:
        event = json.load(f)

    repo = event["repository"]
    owner = repo["owner"]["login"]
    name = repo["name"]
    api = f"https://api.github.com/repos/{owner}/{name}"

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")

    if event_name == "pull_request":
        pr = event.get("pull_request") or {}
        base_ref = (pr.get("base") or {}).get("ref") or ""
        pr_body = pr.get("body")
        pr_number = pr.get("number")
        is_pr = True
    else:
        base_ref = (event.get("ref") or "").replace("refs/heads/", "")
        pr_body = None
        pr_number = None
        is_pr = False

    def is_integration(ref: str) -> bool:
        if not ref or ref == "main":
            return False
        return (
            ref == "release"
            or ref.startswith("release-")
            or ref.startswith("release/")
            or ref.startswith("epic/")
            or ref.startswith("epic-")
        )

    if not is_integration(base_ref):
        print(f"Not a PLATE integration merge (base={base_ref!r}); skipping.")
        return 0

    if not is_pr:
        print(
            "Push event without pull_request payload: cannot parse Closes keywords "
            "(reason push_event_no_pr_body, #1385); skipping mark-implemented."
        )
        return 0

    linked = parse_strict_closing_issue_numbers(
        pr_body,
        owner=owner,
        repo=name,
    )
    if not linked:
        print("No linked issues via closing keywords; nothing to label/close.")
        return 0

    labeled: list[int] = []
    closed: list[int] = []
    skipped: list[dict[str, Any]] = []

    for num in linked:
        try:
            issue = _req_json("GET", f"{api}/issues/{num}", token)
        except urllib.error.HTTPError as e:
            print(f"Could not fetch #{num}: {e}", file=sys.stderr)
            continue
        if issue.get("pull_request"):
            skipped.append({"number": num, "reason": "is_pull_request"})
            continue
        if issue.get("state") != "open":
            skipped.append({"number": num, "reason": f"already_{issue.get('state')}"})
            continue

        names: list[str] = []
        for lab in issue.get("labels") or []:
            if isinstance(lab, dict) and lab.get("name"):
                names.append(str(lab["name"]))
            elif isinstance(lab, str):
                names.append(lab)

        if should_apply_status_implemented(names):
            try:
                remove, add = transition_label_deltas(names, "integrate_merge")
            except Exception as e:
                print(f"Skip labeling #{num}: {e}", file=sys.stderr)
                skipped.append({"number": num, "reason": f"status_validation:{e}"})
            else:
                for old in remove:
                    if old in ALLOWED_STATUS_LABELS:
                        path = urllib.parse.quote(old, safe="")
                        try:
                            _req_json("DELETE", f"{api}/issues/{num}/labels/{path}", token)
                        except urllib.error.HTTPError:
                            pass
                to_add = sorted(add)
                if to_add:
                    try:
                        _req_json("POST", f"{api}/issues/{num}/labels", token, {"labels": to_add})
                    except urllib.error.HTTPError as e:
                        print(f"Failed to label #{num}: {e}", file=sys.stderr)
                        skipped.append({"number": num, "reason": f"label_http:{e}"})
                        continue
                labeled.append(num)
                print(
                    f"Labeled #{num} for integration merge to {base_ref}: "
                    f"+{to_add} -{sorted(remove)}."
                )

        decision = should_auto_close_issue(names)
        if not decision["close"]:
            print(f"Skip auto-close #{num}: {decision['reason']}.")
            skipped.append({"number": num, "reason": decision["reason"]})
            continue

        body = render_close_comment(pr_number=int(pr_number), base_ref=base_ref)
        try:
            _req_json("POST", f"{api}/issues/{num}/comments", token, {"body": body})
            _req_json(
                "PATCH",
                f"{api}/issues/{num}",
                token,
                {"state": "closed", "state_reason": "completed"},
            )
            closed.append(num)
            print(f"Closed #{num}.")
        except urllib.error.HTTPError as e:
            print(f"Failed to close #{num}: {e}", file=sys.stderr)

    print(
        "Integration close audit:",
        f"labeled={labeled}",
        f"closed={closed}",
        f"skipped={json.dumps(skipped)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
