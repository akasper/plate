"""Copilot code review effort policy helpers (#1095 / Epic #1091).

GitHub's built-in default review effort is Balanced; PLATE adopters should set Lite at
the repository (or org) level for routine cost control. Reading that setting via API is
not yet available in published REST schemas — we probe known preview paths and fall back
to documented manual verification.
"""

from __future__ import annotations

from typing import Any

from .github_client import GhApiError, GhClient

PLATE_PREFERRED_REVIEW_EFFORT = "lite"

CONFIGURE_CODE_REVIEW_DOC = (
    "https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review"
)

_MANUAL_VERIFY_STEPS = [
    "Repository: Settings → Copilot → Code review → set Review effort level to Lite "
    "(not Default/Balanced).",
    "Organization owners: set org default to Lite when repositories inherit org policy.",
    "For PRs labeled risk:high or risk:critical, request Copilot review at Balanced "
    "in the PR Reviewers menu when deeper analysis is worth the spend.",
]

_EFFORT_FIELD_CANDIDATES = (
    "review_effort_level",
    "default_review_effort_level",
    "review_effort",
    "default_review_effort",
    "effort_level",
    "effort",
)

_PROBE_ENDPOINTS = (
    "repos/{repo}/copilot/code-review/configuration",
    "repos/{repo}/copilot/code_review/configuration",
)


def normalize_review_effort(value: object | None) -> str | None:
    """Return lowercase canonical effort (lite|balanced|max) or None."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"lite", "low"}:
        return "lite"
    if text in {"balanced", "medium", "default", "default (balanced)"}:
        return "balanced"
    if text in {"max", "maximum", "high"}:
        return "max"
    if "lite" in text:
        return "lite"
    if "balanced" in text:
        return "balanced"
    if "max" in text:
        return "max"
    return text


def _parse_effort_from_payload(payload: dict[str, Any]) -> str | None:
    for key in _EFFORT_FIELD_CANDIDATES:
        if key in payload:
            normalized = normalize_review_effort(payload.get(key))
            if normalized:
                return normalized
    for nested_key in ("code_review", "codeReview", "review", "settings"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            found = _parse_effort_from_payload(nested)
            if found:
                return found
    return None


def _gh_status_code(exc: GhApiError) -> int | None:
    msg = str(exc).lower()
    if "not found" in msg or "unexpected endpoint" in msg:
        return 404
    for code in (401, 403, 404):
        if str(code) in msg or f"http {code}" in msg:
            return code
    return None


def probe_repository_review_effort(gh: GhClient, repo: str) -> dict[str, Any]:
    """Try to read repository Copilot review effort from GitHub API."""
    last_error: str | None = None
    for pattern in _PROBE_ENDPOINTS:
        endpoint = pattern.format(repo=repo)
        try:
            payload = gh.api(endpoint)
        except GhApiError as exc:
            code = _gh_status_code(exc)
            last_error = str(exc)
            if code == 404:
                continue
            if code in (401, 403):
                return {
                    "probe_status": "forbidden",
                    "effort": None,
                    "endpoint": endpoint,
                    "error": last_error,
                }
            return {
                "probe_status": "error",
                "effort": None,
                "endpoint": endpoint,
                "error": last_error,
            }
        if isinstance(payload, dict):
            effort = _parse_effort_from_payload(payload)
            if effort:
                return {
                    "probe_status": "ok",
                    "effort": effort,
                    "endpoint": endpoint,
                    "preferred_ok": effort == PLATE_PREFERRED_REVIEW_EFFORT,
                }
            return {
                "probe_status": "unsupported",
                "effort": None,
                "endpoint": endpoint,
                "error": "response missing review effort fields",
            }
    return {
        "probe_status": "unavailable",
        "effort": None,
        "endpoint": None,
        "error": last_error or "no configuration endpoint returned effort",
    }


def manual_review_effort_next_step() -> str:
    return (
        "GitHub does not expose repository Copilot review effort via a readable REST API yet "
        f"({CONFIGURE_CODE_REVIEW_DOC}). Human verify: "
        + _MANUAL_VERIFY_STEPS[0]
    )


def summarize_copilot_review_effort(gh: GhClient | None, repo: str | None) -> dict[str, Any]:
    """Health/adopt summary for PLATE Lite effort policy (#1095)."""
    if not repo:
        return {
            "status": "skipped",
            "effort": None,
            "preferred_ok": None,
            "next_step": None,
            "manual_steps": list(_MANUAL_VERIFY_STEPS),
        }
    if gh is None:
        return {
            "status": "manual",
            "effort": None,
            "preferred_ok": None,
            "next_step": manual_review_effort_next_step(),
            "manual_steps": list(_MANUAL_VERIFY_STEPS),
        }

    probe = probe_repository_review_effort(gh, repo)
    probe_status = str(probe.get("probe_status") or "")
    effort = probe.get("effort")

    if probe_status == "ok" and effort:
        preferred_ok = bool(probe.get("preferred_ok"))
        if preferred_ok:
            return {
                "status": "ok",
                "effort": effort,
                "preferred_ok": True,
                "next_step": None,
                "manual_steps": [],
                "probe": probe,
            }
        return {
            "status": "warn",
            "effort": effort,
            "preferred_ok": False,
            "next_step": (
                f"Repository Copilot review effort is {effort!r}; PLATE policy prefers Lite. "
                f"Set Review effort level to Lite: {_MANUAL_VERIFY_STEPS[0]} "
                f"See {CONFIGURE_CODE_REVIEW_DOC}"
            ),
            "manual_steps": list(_MANUAL_VERIFY_STEPS),
            "probe": probe,
        }

    if probe_status == "forbidden":
        return {
            "status": "manual",
            "effort": None,
            "preferred_ok": None,
            "next_step": (
                "Token cannot read Copilot code review settings (403). "
                + manual_review_effort_next_step()
            ),
            "manual_steps": list(_MANUAL_VERIFY_STEPS),
            "probe": probe,
        }

    return {
        "status": "manual",
        "effort": effort,
        "preferred_ok": None,
        "next_step": manual_review_effort_next_step(),
        "manual_steps": list(_MANUAL_VERIFY_STEPS),
        "probe": probe,
    }


def adoption_check_for_review_effort(summary: dict[str, Any]) -> dict[str, Any]:
    """Build a single adoption checklist row from summarize_copilot_review_effort()."""
    status = str(summary.get("status") or "manual")
    effort = summary.get("effort")
    detail_parts: list[str] = []
    if effort:
        detail_parts.append(f"effort={effort}")
    if status == "ok":
        detail_parts.append("repository setting is Lite")
    elif status == "warn":
        detail_parts.append("not Lite — change repository setting")
    else:
        detail_parts.append("manual verification required (API unreadable)")
    detail = "; ".join(detail_parts)
    ok = status == "ok"
    fix = ""
    if not ok:
        fix = summary.get("next_step") or manual_review_effort_next_step()
    return {
        "id": "copilot_review_effort_lite",
        "title": "Copilot code review effort is Lite (GitHub setting)",
        "ok": ok,
        "minutes_if_missing": 0 if ok else 2,
        "fix_command": fix if not ok else "",
        "detail": detail,
    }
