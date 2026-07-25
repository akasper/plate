"""Per-Feature explanatory GIF/video capture + approval (#636).

Lifecycle for every Feature:
  plan_capture → record (via record_e2e_gif / Playwright) → register artifact
  → user approve → attach to fragment media[] (#635) / feature closure

Durable registry under .agentic/feature_media/. Complements release_media and
feature_loop media_capture stage.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEATURE_MEDIA_DIR = Path(".agentic/feature_media")
REGISTRY_FILE = "registry.json"
DEFAULT_GIF_DIR = Path("tests/e2e/fixtures/gifs")
MARKER_BEGIN = "<!-- PLATE-FEATURE-MEDIA:BEGIN -->"
MARKER_END = "<!-- PLATE-FEATURE-MEDIA:END -->"

STATUSES = (
    "planned",
    "recorded",
    "pending_approval",
    "approved",
    "rejected",
    "attached",
    "skipped",
)


@dataclass
class FeatureMediaRecord:
    id: str
    feature_number: int | None
    feature_title: str
    test_name: str
    status: str = "planned"
    gif_path: str | None = None
    video_path: str | None = None
    size_bytes: int | None = None
    quality: str = "medium"
    caption: str = ""
    fragment_slug: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureMediaRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or FEATURE_MEDIA_DIR
    if d.name == REGISTRY_FILE:
        return d
    return d / REGISTRY_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "records": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "records": []}
        data.setdefault("version", 1)
        data.setdefault("records", [])
        if not isinstance(data["records"], list):
            data["records"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "records": []}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def render_feature_media_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def slugify_test_name(title: str, feature_number: int | None = None) -> str:
    """Safe alnum test_name for record_e2e_gif / e2e-record.sh."""
    base = re.sub(r"[^a-zA-Z0-9]+", "-", (title or "feature").strip().lower()).strip("-")
    base = re.sub(r"-+", "-", base)[:40] or "feature"
    # record_e2e_gif requires isalnum after removing - and _
    if feature_number is not None:
        return f"feature-{feature_number}-{base}".replace("--", "-")[:60]
    return f"feature-{base}"[:60]


def expected_gif_path(test_name: str, *, repo_root: Path | None = None) -> Path:
    root = repo_root or Path(".")
    return root / DEFAULT_GIF_DIR / f"{test_name}.gif"


def plan_feature_media(
    *,
    feature_number: int | None = None,
    feature_title: str = "",
    test_name: str | None = None,
    caption: str | None = None,
    fragment_slug: str | None = None,
    quality: str = "medium",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a planned media capture record for a Feature."""
    title = (feature_title or "").strip() or (
        f"Feature #{feature_number}" if feature_number else "Untitled feature"
    )
    tname = (test_name or "").strip() or slugify_test_name(title, feature_number)
    # ensure record_e2e_gif accepts name
    safe = tname.replace("-", "").replace("_", "")
    if not safe.isalnum():
        tname = slugify_test_name(title, feature_number)
    ts = _now()
    rec = FeatureMediaRecord(
        id=f"fmedia-{uuid.uuid4().hex[:10]}",
        feature_number=feature_number,
        feature_title=title,
        test_name=tname,
        status="planned",
        gif_path=str(DEFAULT_GIF_DIR / f"{tname}.gif"),
        caption=caption or f"Demo: {title}",
        fragment_slug=fragment_slug,
        quality=quality or "medium",
        created_at=ts,
        updated_at=ts,
    )
    data = _load(base_dir)
    data["records"].append(rec.to_dict())
    _save(data, base_dir)
    packet = {
        "steps": [
            f"Ensure Playwright E2E covers the Feature behavior (test name: {tname})",
            f"Record: plate record_e2e_gif / MCP record_e2e_gif test_name={tname} quality={quality}",
            f"Expected path: {rec.gif_path}",
            f"Register result: plate_feature_media_register {rec.id}",
            "Approve via feed or plate_feature_media_decide",
            "Attach to fragment media[] with plate_feature_media_attach_fragment",
        ],
        "record_e2e_gif_args": {
            "test_name": tname,
            "quality": quality,
        },
        "ask_user_question": {
            "question": f"Feature media plan for {title}: record GIF from test '{tname}'?",
            "options": [
                {
                    "id": "record",
                    "label": "Record now",
                    "description": f"record_e2e_gif test_name={tname}",
                },
                {
                    "id": "skip",
                    "label": "Skip media",
                    "description": f"plate_feature_media_skip {rec.id}",
                },
            ],
        },
    }
    return {
        "ok": True,
        "record": rec.to_dict(),
        "packet": packet,
        "marker": render_feature_media_marker(
            {"id": rec.id, "test_name": tname, "status": "planned"}
        ),
    }


def register_capture(
    record_id: str,
    *,
    gif_path: str | None = None,
    video_path: str | None = None,
    size_bytes: int | None = None,
    quality: str | None = None,
    capture_result: dict[str, Any] | None = None,
    submit_for_approval: bool = True,
    base_dir: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Register a recorded GIF/video against a planned Feature media record."""
    data = _load(base_dir)
    found = None
    for r in data["records"]:
        if r.get("id") == record_id:
            found = r
            break
    if not found:
        return {"ok": False, "error": f"record not found: {record_id}"}

    cr = capture_result or {}
    path = gif_path or cr.get("gif_path") or found.get("gif_path")
    if path:
        # prefer relative path under repo
        try:
            root = (repo_root or Path(".")).resolve()
            p = Path(path)
            if p.is_absolute():
                try:
                    path = str(p.resolve().relative_to(root))
                except ValueError:
                    path = str(p)
        except Exception:
            pass
        found["gif_path"] = path
    if video_path or cr.get("video_path"):
        found["video_path"] = video_path or cr.get("video_path")
    sz = size_bytes if size_bytes is not None else cr.get("size_bytes")
    if sz is not None:
        found["size_bytes"] = int(sz)
    if quality or cr.get("quality"):
        found["quality"] = quality or cr.get("quality")
    if cr.get("status") == "error":
        found["status"] = "planned"
        found.setdefault("metadata", {})["last_error"] = cr.get("message")
        found["updated_at"] = _now()
        _save(data, base_dir)
        return {"ok": False, "error": cr.get("message") or "capture failed", "record": found}

    # verify file if local
    root = repo_root or Path(".")
    exists = False
    if found.get("gif_path"):
        exists = (root / found["gif_path"]).is_file() or Path(found["gif_path"]).is_file()
    found["status"] = "pending_approval" if submit_for_approval else "recorded"
    if not exists and not found.get("video_path"):
        found.setdefault("metadata", {})["file_missing"] = True
    found["updated_at"] = _now()
    _save(data, base_dir)
    return {
        "ok": True,
        "record": found,
        "file_exists": exists,
        "fragment_media_entry": to_fragment_media_entry(found),
    }


def to_fragment_media_entry(record: dict[str, Any]) -> dict[str, Any]:
    """Convert registry record to fragment media[] item (#635)."""
    return {
        "type": "gif" if (record.get("gif_path") or "").endswith(".gif") else "video",
        "path": record.get("gif_path") or record.get("video_path"),
        "caption": record.get("caption") or record.get("feature_title") or "Feature demo",
        "feature": record.get("fragment_slug")
        or (
            f"feature-{record.get('feature_number')}"
            if record.get("feature_number")
            else record.get("test_name")
        ),
        "approval_status": (
            "approved"
            if record.get("status") in ("approved", "attached")
            else "pending"
            if record.get("status") == "pending_approval"
            else record.get("status") or "pending"
        ),
    }


def list_feature_media(
    *,
    status: str = "all",
    feature_number: int | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    out = []
    for r in _load(base_dir).get("records") or []:
        if status and status != "all" and r.get("status") != status:
            continue
        if feature_number is not None and r.get("feature_number") != feature_number:
            continue
        out.append(r)
    return out[: max(1, int(limit or 50))]


def get_feature_media(record_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    for r in _load(base_dir).get("records") or []:
        if r.get("id") == record_id:
            return r
    return None


def decide_feature_media(
    record_id: str,
    decision: str,
    *,
    decided_by: str = "human",
    note: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    data = _load(base_dir)
    found = None
    for r in data["records"]:
        if r.get("id") == record_id:
            found = r
            break
    if not found:
        return {"ok": False, "error": f"record not found: {record_id}"}
    dec = (decision or "").lower().strip()
    if dec in ("approve", "approved"):
        found["status"] = "approved"
        found["approved_by"] = decided_by
        found["approved_at"] = _now()
    elif dec in ("reject", "rejected"):
        found["status"] = "rejected"
    elif dec in ("skip", "skipped"):
        found["status"] = "skipped"
    else:
        return {"ok": False, "error": f"invalid decision: {decision}"}
    if note:
        found.setdefault("metadata", {})["decision_note"] = note
    found["updated_at"] = _now()
    _save(data, base_dir)
    return {"ok": True, "record": found, "fragment_media_entry": to_fragment_media_entry(found)}


def skip_feature_media(
    record_id: str, *, note: str = "", base_dir: Path | None = None
) -> dict[str, Any]:
    return decide_feature_media(record_id, "skip", note=note or "skipped", base_dir=base_dir)


def attach_to_fragment_file(
    record_id: str,
    fragment_path: str | Path,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Append approved media entry to an unreleased fragment JSON file."""
    rec = get_feature_media(record_id, base_dir=base_dir)
    if not rec:
        return {"ok": False, "error": f"record not found: {record_id}"}
    if rec.get("status") not in ("approved", "recorded", "pending_approval", "attached"):
        return {"ok": False, "error": f"status {rec.get('status')} not attachable"}
    path = Path(fragment_path)
    if not path.is_file():
        return {"ok": False, "error": f"fragment not found: {fragment_path}"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(data, dict):
        return {"ok": False, "error": "fragment must be JSON object"}
    media = list(data.get("media") or [])
    entry = to_fragment_media_entry(rec)
    # dedupe by path
    media = [m for m in media if not (isinstance(m, dict) and m.get("path") == entry.get("path"))]
    media.append(entry)
    data["media"] = media
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    # mark attached in registry
    reg = _load(base_dir)
    for r in reg["records"]:
        if r.get("id") == record_id:
            r["status"] = "attached"
            r["fragment_slug"] = data.get("slug") or r.get("fragment_slug")
            r["updated_at"] = _now()
            break
    _save(reg, base_dir)
    return {"ok": True, "fragment_path": str(path), "media_entry": entry, "record_id": record_id}


def feature_media_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    items = []
    for r in list_feature_media(status="pending_approval", limit=limit, base_dir=base_dir):
        items.append(
            {
                "id": r.get("id"),
                "item_type": "feature_media",
                "title": f"Approve Feature media: {r.get('feature_title')}",
                "feature_number": r.get("feature_number"),
                "gif_path": r.get("gif_path"),
                "test_name": r.get("test_name"),
                "badges": ["feature_media", "pending_approval", "gif"],
                "source": "feature_media",
                "impact": "medium",
                "reason": "Approve explanatory GIF/video before Feature ship (#636)",
                "ask_user_question": {
                    "question": f"Approve demo media for {r.get('feature_title')} ({r.get('gif_path')})?",
                    "options": [
                        {
                            "id": "approve",
                            "label": "Approve",
                            "description": f"plate_feature_media_decide {r.get('id')} approve",
                        },
                        {
                            "id": "reject",
                            "label": "Reject / re-record",
                            "description": f"plate_feature_media_decide {r.get('id')} reject",
                        },
                        {
                            "id": "skip",
                            "label": "Skip media for this Feature",
                            "description": f"plate_feature_media_skip {r.get('id')}",
                        },
                    ],
                },
                "marker": render_feature_media_marker(
                    {"id": r.get("id"), "status": r.get("status"), "path": r.get("gif_path")}
                ),
            }
        )
    # also surface planned items lightly
    for r in list_feature_media(status="planned", limit=max(1, limit // 2), base_dir=base_dir):
        items.append(
            {
                "id": r.get("id"),
                "item_type": "feature_media_plan",
                "title": f"Record Feature media: {r.get('feature_title')}",
                "feature_number": r.get("feature_number"),
                "test_name": r.get("test_name"),
                "badges": ["feature_media", "planned"],
                "source": "feature_media",
                "impact": "low",
                "reason": f"Record via record_e2e_gif test_name={r.get('test_name')}",
                "ask_user_question": {
                    "question": f"Record GIF for {r.get('feature_title')}?",
                    "options": [
                        {
                            "id": "record",
                            "label": "Record",
                            "description": f"record_e2e_gif {r.get('test_name')}",
                        },
                        {
                            "id": "skip",
                            "label": "Skip",
                            "description": f"plate_feature_media_skip {r.get('id')}",
                        },
                    ],
                },
            }
        )
        if len(items) >= limit:
            break
    return items[:limit]


def plan_for_feature_loop(
    feature_number: int | None,
    feature_title: str,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Helper for feature_loop media_capture stage."""
    return plan_feature_media(
        feature_number=feature_number,
        feature_title=feature_title,
        base_dir=base_dir,
    )
