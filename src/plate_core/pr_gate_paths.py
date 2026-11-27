"""Parse PR changed-path manifests for plate-pr-gates (#1182)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChangedPathEntry:
    path: str
    status: str


def parse_scope_tsv(text: str) -> list[ChangedPathEntry]:
    entries: list[ChangedPathEntry] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "\t" not in line:
            entries.append(ChangedPathEntry(path=line, status="modified"))
            continue
        path, status = line.split("\t", 1)
        path = path.strip()
        status = status.strip() or "modified"
        if path:
            entries.append(ChangedPathEntry(path=path, status=status))
    return entries


def scope_paths_from_entries(entries: list[ChangedPathEntry]) -> list[str]:
    return [item.path for item in entries]


def active_paths_from_entries(entries: list[ChangedPathEntry]) -> list[str]:
    return [item.path for item in entries if item.status != "removed"]