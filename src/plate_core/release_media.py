"""Release notes media (GIF/video) support (#635).

Fragments may declare a `media` array. Release cut aggregates media into
release.json entries and rendered GitHub Release markdown.

Media item schema:
  type: gif | video | image | link
  path: repo-relative path (e.g. tests/e2e/fixtures/gifs/foo.gif)
  url: absolute URL (optional alternative to path)
  caption: short description
  feature: optional feature slug or issue ref
  approval_status: pending | approved | rejected (default pending)

Does not capture/record media itself — hosts use record-e2e-gif / Playwright.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEDIA_TYPES = ("gif", "video", "image", "link")
APPROVAL_STATUSES = ("pending", "approved", "rejected")
MARKER_BEGIN = "<!-- PLATE-RELEASE-MEDIA:BEGIN -->"
MARKER_END = "<!-- PLATE-RELEASE-MEDIA:END -->"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_media_item(raw: Any) -> dict[str, Any] | None:
    """Normalize one media dict; return None if unusable."""
    if not isinstance(raw, dict):
        if isinstance(raw, str) and raw.strip():
            # bare path/url
            s = raw.strip()
            lower = s.lower().split("?", 1)[0]
            if lower.endswith(".gif"):
                kind = "gif"
            elif lower.endswith((".mp4", ".webm", ".mov")):
                kind = "video"
            elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                kind = "image"
            elif s.startswith("http"):
                kind = "link"
            else:
                kind = "image"
            return {
                "type": kind,
                "path": None if s.startswith("http") else s,
                "url": s if s.startswith("http") else None,
                "caption": "",
                "feature": None,
                "approval_status": "pending",
            }
        return None
    path = raw.get("path") or raw.get("file")
    url = raw.get("url") or raw.get("href")
    if not path and not url:
        return None
    mtype = str(raw.get("type") or "").lower().strip()
    if mtype not in MEDIA_TYPES:
        # infer
        target = str(path or url or "")
        if target.endswith(".gif"):
            mtype = "gif"
        elif target.endswith((".mp4", ".webm", ".mov")):
            mtype = "video"
        elif target.startswith("http") and not path:
            mtype = "link"
        else:
            mtype = "image"
    status = str(raw.get("approval_status") or raw.get("status") or "pending").lower()
    if status not in APPROVAL_STATUSES:
        status = "pending"
    return {
        "type": mtype,
        "path": str(path) if path else None,
        "url": str(url) if url else None,
        "caption": str(raw.get("caption") or raw.get("title") or "").strip(),
        "feature": raw.get("feature") or raw.get("slug") or raw.get("issue"),
        "approval_status": status,
        "alt": str(raw.get("alt") or raw.get("caption") or "demo media").strip(),
    }


def extract_media_from_fragment(fragment: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull normalized media list from a fragment dict."""
    raw = fragment.get("media") or fragment.get("demo_media") or []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        n = normalize_media_item(item)
        if n:
            # inherit feature from fragment slug if missing
            if not n.get("feature") and fragment.get("slug"):
                n["feature"] = fragment.get("slug")
            out.append(n)
    return out


def collect_release_media(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate all media from fragments with source slug."""
    all_media: list[dict[str, Any]] = []
    for f in fragments:
        for m in extract_media_from_fragment(f):
            item = dict(m)
            item["source_slug"] = f.get("slug") or f.get("_source_file") or ""
            item["change_type"] = f.get("change_type")
            all_media.append(item)
    return all_media


def media_approval_summary(media: list[dict[str, Any]]) -> dict[str, Any]:
    pending = [m for m in media if m.get("approval_status") == "pending"]
    approved = [m for m in media if m.get("approval_status") == "approved"]
    rejected = [m for m in media if m.get("approval_status") == "rejected"]
    return {
        "n_total": len(media),
        "n_pending": len(pending),
        "n_approved": len(approved),
        "n_rejected": len(rejected),
        "ready_for_release": len(pending) == 0 and len(media) > 0,
        "has_media": len(media) > 0,
        "pending": pending,
        "approved": approved,
    }


def decide_media_item(
    media: list[dict[str, Any]],
    *,
    index: int | None = None,
    path: str | None = None,
    url: str | None = None,
    decision: str = "approve",
) -> dict[str, Any]:
    """Set approval_status on matching media item(s) in a list (mutates copy)."""
    dec = (decision or "approve").lower().strip()
    if dec in ("approve", "approved"):
        status = "approved"
    elif dec in ("reject", "rejected"):
        status = "rejected"
    else:
        return {"ok": False, "error": f"invalid decision: {decision}", "media": media}
    updated = [dict(m) for m in media]
    matched = 0
    for i, m in enumerate(updated):
        hit = False
        if index is not None and i == index:
            hit = True
        if path and m.get("path") == path:
            hit = True
        if url and m.get("url") == url:
            hit = True
        if hit:
            m["approval_status"] = status
            m["decided_at"] = _now()
            matched += 1
    if matched == 0:
        return {"ok": False, "error": "no media item matched", "media": updated}
    return {"ok": True, "matched": matched, "media": updated, "status": status}


def render_media_markdown(media: list[dict[str, Any]], *, only_approved: bool = False) -> str:
    """Render media block for release notes / GitHub Release body."""
    items = media
    if only_approved:
        items = [m for m in media if m.get("approval_status") == "approved"]
    if not items:
        return ""
    lines = ["### Demo media", ""]
    for m in items:
        caption = m.get("caption") or m.get("feature") or m.get("alt") or "Demo"
        status = m.get("approval_status") or "pending"
        badge = "" if status == "approved" else f" *({status})*"
        path = m.get("path")
        url = m.get("url")
        mtype = m.get("type") or "image"
        if path and not url:
            # markdown relative embed for gif/image; link for video
            if mtype in ("gif", "image"):
                lines.append(f"![{caption}]({path}){badge}")
            else:
                lines.append(f"- **{caption}:** [`{path}`]({path}){badge}")
        elif url:
            if mtype in ("gif", "image") and not url.endswith((".mp4", ".webm")):
                lines.append(f"![{caption}]({url}){badge}")
            else:
                lines.append(f"- **{caption}:** [view media]({url}){badge}")
        else:
            lines.append(f"- {caption}{badge}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_entry_media_lines(entry: dict[str, Any]) -> list[str]:
    """Lines to append under a single release entry."""
    media = entry.get("media") or []
    if not media:
        return []
    lines = ["- **Media:**"]
    for m in media:
        cap = m.get("caption") or m.get("feature") or "demo"
        ref = m.get("path") or m.get("url") or ""
        st = m.get("approval_status") or "pending"
        lines.append(f"  - [{m.get('type', 'media')}] {cap}: {ref} ({st})")
    return lines


def attach_media_to_entry(entry: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """Copy normalized media from fragment onto release entry."""
    media = extract_media_from_fragment(fragment)
    if media:
        entry = dict(entry)
        entry["media"] = media
    return entry


def validate_media_paths(
    media: list[dict[str, Any]],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Check that path-based media files exist (optional local check)."""
    root = repo_root or Path(".")
    missing = []
    present = []
    for m in media:
        p = m.get("path")
        if not p:
            continue
        full = root / p
        if full.is_file():
            present.append(p)
        else:
            missing.append(p)
    return {
        "ok": len(missing) == 0,
        "n_checked": len(present) + len(missing),
        "present": present,
        "missing": missing,
    }


def media_feed_items(media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Feed presentation for pending media approval."""
    items = []
    for i, m in enumerate(media):
        if m.get("approval_status") != "pending":
            continue
        ref = m.get("path") or m.get("url") or f"item-{i}"
        items.append(
            {
                "id": f"media-{i}-{m.get('source_slug') or 'frag'}",
                "item_type": "release_media",
                "title": f"Approve release media: {m.get('caption') or ref}",
                "path": m.get("path"),
                "url": m.get("url"),
                "type": m.get("type"),
                "source_slug": m.get("source_slug"),
                "badges": ["release_media", m.get("type") or "media", "pending"],
                "source": "release_media",
                "impact": "medium",
                "reason": "User approval of GIF/video for release notes (#635)",
                "ask_user_question": {
                    "question": f"Approve media for release notes: {ref}?",
                    "options": [
                        {"id": "approve", "label": "Approve", "description": "Include in GitHub Release body"},
                        {"id": "reject", "label": "Reject", "description": "Omit from release notes"},
                    ],
                },
            }
        )
    return items


def build_media_manifest(
    fragments: list[dict[str, Any]],
    *,
    version: str | None = None,
) -> dict[str, Any]:
    """Build a release media manifest for cut_release / finalize."""
    media = collect_release_media(fragments)
    summary = media_approval_summary(media)
    return {
        "version": version,
        "generated_at": _now(),
        "media": media,
        "summary": summary,
        "markdown_all": render_media_markdown(media, only_approved=False),
        "markdown_approved": render_media_markdown(media, only_approved=True),
        "marker": f"{MARKER_BEGIN}\n{json.dumps({'n': len(media), 'pending': summary['n_pending']}, indent=2)}\n{MARKER_END}\n",
    }
