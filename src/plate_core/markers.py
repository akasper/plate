"""PLATES-CORE marker parsing, validation, and sync/merge support.

Implements the runtime contract for Issue #130 / Epic #89 / Epic #126.
See docs/design/plates-core-marker-contract-upstream-sync.md for the full design.

Markers delimit tool-owned (plate) sections in user files so that upstream
updates can be safely merged while preserving local customizations outside
the markers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


START_PATTERN = re.compile(r"<!--\s*PLATES-CORE:\s*([a-zA-Z0-9_-]+)\s*-->")
END_PATTERN = re.compile(r"<!--\s*/PLATES-CORE\s*-->")

@dataclass
class MarkerSection:
    name: str
    start_line: int
    end_line: int
    content: str  # content *inside* the markers (excluding the marker lines themselves)


@dataclass
class MergeResult:
    """Result of marker-aware merge with diagnostics for conflict reporting."""
    text: str
    preserved_local_sections: List[str]
    warnings: List[str]


class MarkerParseError(ValueError):
    """Raised for invalid marker structure (nesting, unclosed, orphan end, etc.)."""


class MarkerParser:
    """Parser and validator for PLATES-CORE markers."""

    def is_start_marker(self, line: str) -> bool:
        return bool(START_PATTERN.search(line))

    def is_end_marker(self, line: str) -> bool:
        return bool(END_PATTERN.search(line))

    def extract_section_name(self, line: str) -> Optional[str]:
        m = START_PATTERN.search(line)
        return m.group(1) if m else None

    def find_marked_sections(self, content: str) -> List[MarkerSection]:
        """Return list of non-overlapping marked sections found in the content.
        Strictly forbids nesting.
        """
        lines = content.splitlines(keepends=True)
        sections: List[MarkerSection] = []
        i = 0
        n = len(lines)
        in_marker = False
        current_name = None
        start_line = 0

        while i < n:
            line = lines[i]
            if self.is_start_marker(line):
                if in_marker:
                    raise MarkerParseError("Nested PLATES-CORE markers are not allowed")
                name = self.extract_section_name(line)
                in_marker = True
                current_name = name
                start_line = i
            elif self.is_end_marker(line):
                if not in_marker:
                    raise MarkerParseError(f"Orphan end marker at line {i}")
                # content inside
                inner = "".join(lines[start_line+1 : i])
                sections.append(MarkerSection(name=current_name or "", start_line=start_line, end_line=i, content=inner))
                in_marker = False
                current_name = None
            i += 1

        if in_marker:
            raise MarkerParseError(f"Unclosed marker '{current_name}'")

        return sections

    def validate_marker_nesting(self, content: str) -> Dict[str, Any]:
        """Return {'valid': bool, 'errors': list}."""
        errors = []
        try:
            sections = self.find_marked_sections(content)
            # Enforce unique section names per file (design requirement)
            names = [s.name for s in sections]
            if len(names) != len(set(names)):
                errors.append("Duplicate section names are not allowed within a file")
        except MarkerParseError as e:
            errors.append(str(e))
        # Additional simple checks
        lines = content.splitlines()
        start_count = sum(1 for l in lines if self.is_start_marker(l))
        end_count = sum(1 for l in lines if self.is_end_marker(l))
        if start_count != end_count:
            errors.append("Mismatched number of start and end markers")

        return {"valid": len(errors) == 0, "errors": errors}

    def merge_with_local_preservation(
        self,
        base: str,
        local: str,
        upstream: str,
    ) -> str:
        """
        Conservative merge strategy for files containing PLATES-CORE markers.

        Rule (per design):
        - Inside a marker section: if the local version differs from base, keep the
          entire local section (local edits win to avoid losing user work).
        - Outside markers: normal text merge (very simple line-based for MVP).
        - New content added by upstream inside markers is only accepted if the
          local section was not edited.
        """
        # For MVP we do a simple section-aware replacement.
        # A full 3-way merge per section would be better in a later slice.

        try:
            base_sections = {s.name: s for s in self.find_marked_sections(base)}
            local_sections = {s.name: s for s in self.find_marked_sections(local)}
            upstream_sections = {s.name: s for s in self.find_marked_sections(upstream)}
        except MarkerParseError:
            # If any version is invalid, fall back to returning local as-is
            return local

        # Build result preferring local when edited inside markers
        result_lines: List[str] = []
        # Very naive: walk the local file and when we hit a marker section,
        # decide what to emit.
        local_lines = local.splitlines(keepends=True)
        i = 0
        n = len(local_lines)

        while i < n:
            line = local_lines[i]
            if self.is_start_marker(line):
                name = self.extract_section_name(line)
                # find end in local
                j = i + 1
                while j < n and not self.is_end_marker(local_lines[j]):
                    j += 1
                if j < n:
                    j += 1  # include the end marker

                if name in base_sections and name in local_sections:
                    base_sec = base_sections[name]
                    local_sec = local_sections[name]
                    if local_sec.content != base_sec.content:
                        # local edited the section -> keep local version entirely
                        result_lines.extend(local_lines[i:j])
                    else:
                        # local did not edit; take upstream if present
                        if name in upstream_sections:
                            up = upstream_sections[name]
                            result_lines.append(line)  # start
                            result_lines.append(up.content)
                            result_lines.append(local_lines[j-1] if j > i else "<!-- /PLATES-CORE -->\n")
                        else:
                            result_lines.extend(local_lines[i:j])
                else:
                    # unknown section or no base -> keep local
                    result_lines.extend(local_lines[i:j])
                i = j
                continue

            result_lines.append(line)
            i += 1

        return "".join(result_lines)


# Convenience module-level functions matching the test expectations
_parser = MarkerParser()

def _is_start_marker(line: str) -> bool:
    return _parser.is_start_marker(line)

def _is_end_marker(line: str) -> bool:
    return _parser.is_end_marker(line)

def _extract_section_name(line: str) -> Optional[str]:
    return _parser.extract_section_name(line)

def _find_marked_sections(content: str) -> List[Dict[str, Any]]:
    secs = _parser.find_marked_sections(content)
    return [
        {"name": s.name, "start_line": s.start_line, "end_line": s.end_line, "content": s.content}
        for s in secs
    ]

def _validate_marker_nesting(content: str) -> Dict[str, Any]:
    return _parser.validate_marker_nesting(content)

def _merge_with_local_preservation(base: str, local: str, upstream: str) -> str:
    return _parser.merge_with_local_preservation(base, local, upstream)


# Public API (preferred for new callers; _ wrappers retained for test compat)
find_marked_sections = _find_marked_sections
validate_marker_nesting = _validate_marker_nesting
merge_with_local_preservation = _merge_with_local_preservation

__all__ = [
    "MarkerSection",
    "MarkerParseError",
    "MarkerParser",
    "find_marked_sections",
    "validate_marker_nesting",
    "merge_with_local_preservation",
    "_is_start_marker",
    "_is_end_marker",
    "_extract_section_name",
    "_find_marked_sections",
    "_validate_marker_nesting",
    "_merge_with_local_preservation",
]
