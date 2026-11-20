"""Contract: payload Linux jobs must not hardcode ubuntu-latest (#1489)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

from plate_core.workflow_runs_on import (
    LINUX_RUNS_ON_VAR_EXPRESSION,
    resolve_linux_runs_on,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_WORKFLOWS = (
    REPO_ROOT / "src" / "plate_core" / "template_payload" / ".github" / "workflows"
)
REPO_WORKFLOWS = REPO_ROOT / ".github" / "workflows"


# --- Minimal GitHub Actions expression evaluator ---------------------------------
# Supports exactly what LINUX_RUNS_ON_VAR_EXPRESSION uses: single-quoted string
# literals, true/null, dotted property access, || / && (short-circuit, returning
# operand values), != (loose), parentheses, startsWith() and fromJSON().

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<string>'(?:[^']*)')"
    r"|(?P<op>\|\||&&|!=)"
    r"|(?P<paren>[()])"
    r"|(?P<comma>,)"
    r"|(?P<dot>\.)"
    r"|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"
    r")"
)


def _tokenize(text: str) -> list[tuple[str, object]]:
    tokens: list[tuple[str, object]] = []
    i = 0
    while i < len(text):
        match = _TOKEN_RE.match(text, i)
        if match is None:
            if text[i].isspace():
                i += 1
                continue
            raise ValueError(f"unexpected character {text[i]!r} at {i}")
        i = match.end()
        kind = match.lastgroup
        value = match.group(kind)
        if kind == "string":
            tokens.append(("string", value[1:-1]))
        elif kind == "ident":
            tokens.append(("ident", value))
        else:
            tokens.append((kind, value))
    tokens.append(("eof", None))
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, object]]) -> None:
        self.tokens = tokens
        self.i = 0

    def _peek(self) -> tuple[str, object]:
        return self.tokens[self.i]

    def _advance(self) -> tuple[str, object]:
        token = self.tokens[self.i]
        self.i += 1
        return token

    def parse(self) -> tuple:
        node = self._parse_or()
        if self._peek()[0] != "eof":
            raise ValueError(f"trailing tokens: {self._peek()}")
        return node

    def _parse_or(self) -> tuple:
        node = self._parse_and()
        while self._peek() == ("op", "||"):
            self._advance()
            node = ("or", node, self._parse_and())
        return node

    def _parse_and(self) -> tuple:
        node = self._parse_neq()
        while self._peek() == ("op", "&&"):
            self._advance()
            node = ("and", node, self._parse_neq())
        return node

    def _parse_neq(self) -> tuple:
        node = self._parse_primary()
        if self._peek() == ("op", "!="):
            self._advance()
            return ("not_eq", node, self._parse_primary())
        return node

    def _parse_primary(self) -> tuple:
        token = self._advance()
        if token[0] == "string":
            return ("str", token[1])
        if token == ("paren", "("):
            node = self._parse_or()
            if self._advance() != ("paren", ")"):
                raise ValueError("expected ')'")
            return node
        if token[0] == "ident":
            name = str(token[1])
            if name == "true":
                return ("const", True)
            if name == "null":
                return ("const", None)
            if self._peek() == ("paren", "("):
                self._advance()
                args: list[tuple] = []
                if self._peek() != ("paren", ")"):
                    args.append(self._parse_or())
                    while self._peek() == ("comma", ","):
                        self._advance()
                        args.append(self._parse_or())
                if self._advance() != ("paren", ")"):
                    raise ValueError("expected ')'")
                return ("call", name, args)
            path = [name]
            while self._peek()[0] == "dot":
                self._advance()
                part = self._advance()
                if part[0] != "ident":
                    raise ValueError(f"expected identifier after '.', got {part}")
                path.append(str(part[1]))
            return ("prop", path)
        raise ValueError(f"unexpected token: {token}")


def _truthy(value: object) -> bool:
    return not (value is None or value is False or value == "" or value == 0)


def _loose_neq(left: object, right: object) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left != right
    if left is None or right is None:
        return left is not right
    return left != right


def _eval(node: tuple, context: dict) -> object:
    kind = node[0]
    if kind == "str":
        return node[1]
    if kind == "const":
        return node[1]
    if kind == "prop":
        current: object = context
        for part in node[1]:
            current = current.get(part) if isinstance(current, dict) else None
        return current
    if kind == "call":
        name = node[1]
        args = [_eval(arg, context) for arg in node[2]]
        if name == "startsWith":
            left = "" if args[0] is None else str(args[0])
            right = "" if args[1] is None else str(args[1])
            return left.lower().startswith(right.lower())
        if name == "fromJSON":
            return json.loads(str(args[0]))
        raise ValueError(f"unsupported function {name}")
    if kind == "not_eq":
        return _loose_neq(_eval(node[1], context), _eval(node[2], context))
    if kind == "and":
        left = _eval(node[1], context)
        return left if not _truthy(left) else _eval(node[2], context)
    if kind == "or":
        left = _eval(node[1], context)
        return left if _truthy(left) else _eval(node[2], context)
    raise ValueError(f"unsupported node {kind}")


def evaluate_expression(expression: str, context: dict) -> object:
    body = expression[len("${{ ") : -len(" }}")]
    return _eval(_Parser(_tokenize(body)).parse(), context)


_MISSING = object()


def _eval_linux_runs_on(
    *,
    ci: object = None,
    plate: object = None,
    private: object = True,
    pull_request: object = None,
    repository: str = "acme/app",
) -> object:
    event: dict = {}
    if private is not _MISSING:
        event["repository"] = {"private": private}
    if pull_request is not None:
        event["pull_request"] = pull_request
    context = {
        "vars": {"CI_RUNS_ON": ci, "PLATE_RUNS_ON": plate},
        "github": {"event": event, "repository": repository},
    }
    return evaluate_expression(LINUX_RUNS_ON_VAR_EXPRESSION, context)
ALLOWED_HARDCODED = frozenset(
    {
        "windows-latest",
        "windows-2022",
        "macos-latest",
        "macos-14",
        "macos-13",
    }
)
CONFIGURABLE_MARKERS = (
    "vars.CI_RUNS_ON",
    "vars.PLATE_RUNS_ON",
    "fromJSON(needs.",
)
# Bootstrap jobs run plate-select-runs-on and must stay on hosted Ubuntu (#1489).
BOOTSTRAP_JOB_IDS = frozenset({"labels", "select-runs-on"})


class PayloadWorkflowLinuxRunsOnTests(unittest.TestCase):
    def test_no_linux_job_hardcodes_ubuntu_latest(self):
        violations: list[str] = []
        for path in sorted(PAYLOAD_WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for doc in yaml.safe_load_all(text):
                if not isinstance(doc, dict):
                    continue
                jobs = doc.get("jobs") or {}
                if not isinstance(jobs, dict):
                    continue
                for job_id, job in jobs.items():
                    if not isinstance(job, dict):
                        continue
                    runs_on = job.get("runs-on")
                    if runs_on is None:
                        continue
                    if isinstance(runs_on, list):
                        continue
                    raw = str(runs_on).strip()
                    if raw in ALLOWED_HARDCODED:
                        continue
                    if raw == "ubuntu-latest":
                        if job_id in BOOTSTRAP_JOB_IDS:
                            continue
                        violations.append(f"{path.name} job {job_id}: hardcoded ubuntu-latest")
                        continue
                    if not any(marker in raw for marker in CONFIGURABLE_MARKERS):
                        violations.append(
                            f"{path.name} job {job_id}: unexpected runs-on {raw!r}"
                        )
        self.assertEqual(violations, [])

    def test_build_plate_pr_gates_source_has_no_bare_ubuntu_latest(self):
        script = (
            REPO_ROOT / "scripts" / "build_plate_pr_gates_workflow.py"
        ).read_text(encoding="utf-8")
        for match in re.finditer(r"runs-on:\s*ubuntu-latest", script):
            self.fail(
                "build_plate_pr_gates_workflow.py must use @@LINUX_RUNS_ON@@, "
                f"found bare ubuntu-latest at offset {match.start()}"
            )

    def test_expression_evaluator_and_resolver_agree_on_cases(self):
        configured_array = '["self-hosted", "plate-local"]'
        cases = [
            # name, evaluator kwargs, resolver kwargs, expected
            (
                "unset private push",
                dict(ci=None, plate=None, private=True, pull_request=None),
                dict(
                    ci_runs_on=None,
                    plate_runs_on=None,
                    repository_private=True,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "ubuntu-latest",
            ),
            (
                "plain label private push",
                dict(ci="ubicloud-standard-2", plate=None, private=True, pull_request=None),
                dict(
                    ci_runs_on="ubicloud-standard-2",
                    plate_runs_on=None,
                    repository_private=True,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "ubicloud-standard-2",
            ),
            (
                "json array private push",
                dict(ci=None, plate=configured_array, private=True, pull_request=None),
                dict(
                    ci_runs_on=None,
                    plate_runs_on=configured_array,
                    repository_private=True,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                ["self-hosted", "plate-local"],
            ),
            (
                "json string private push",
                dict(ci='"ubuntu-24.04"', plate=None, private=True, pull_request=None),
                dict(
                    ci_runs_on='"ubuntu-24.04"',
                    plate_runs_on=None,
                    repository_private=True,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "ubuntu-24.04",
            ),
            (
                "ci wins over plate",
                dict(
                    ci="ubicloud-standard-2",
                    plate=configured_array,
                    private=True,
                    pull_request=None,
                ),
                dict(
                    ci_runs_on="ubicloud-standard-2",
                    plate_runs_on=configured_array,
                    repository_private=True,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "ubicloud-standard-2",
            ),
            (
                "fork pr on private repo",
                dict(
                    ci=None,
                    plate=configured_array,
                    private=True,
                    pull_request={"head": {"repo": {"full_name": "evil/plate"}}},
                ),
                dict(
                    ci_runs_on=None,
                    plate_runs_on=configured_array,
                    repository_private=True,
                    pr_head_full_name="evil/plate",
                    repository="acme/app",
                ),
                "ubuntu-latest",
            ),
            (
                "same-repo pr uses configured labels",
                dict(
                    ci=None,
                    plate=configured_array,
                    private=True,
                    pull_request={"head": {"repo": {"full_name": "acme/app"}}},
                ),
                dict(
                    ci_runs_on=None,
                    plate_runs_on=configured_array,
                    repository_private=True,
                    pr_head_full_name="acme/app",
                    repository="acme/app",
                ),
                ["self-hosted", "plate-local"],
            ),
            (
                "public repo always hosted",
                dict(ci=None, plate=configured_array, private=False, pull_request=None),
                dict(
                    ci_runs_on=None,
                    plate_runs_on=configured_array,
                    repository_private=False,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "ubuntu-latest",
            ),
            (
                "missing repository payload",
                dict(ci=None, plate=configured_array, private=_MISSING, pull_request=None),
                dict(
                    ci_runs_on=None,
                    plate_runs_on=configured_array,
                    repository_private=None,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "ubuntu-latest",
            ),
            (
                "deleted fork head repo",
                dict(
                    ci=None,
                    plate=configured_array,
                    private=True,
                    pull_request={"head": {"repo": None}},
                ),
                dict(
                    ci_runs_on=None,
                    plate_runs_on=configured_array,
                    repository_private=True,
                    pr_head_full_name="",
                    repository="acme/app",
                ),
                "ubuntu-latest",
            ),
            (
                "plain label never reaches fromJSON",
                dict(ci="plate-local", plate=None, private=True, pull_request=None),
                dict(
                    ci_runs_on="plate-local",
                    plate_runs_on=None,
                    repository_private=True,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "plate-local",
            ),
            (
                "json empty string falls back to hosted",
                dict(ci='""', plate=None, private=True, pull_request=None),
                dict(
                    ci_runs_on='""',
                    plate_runs_on=None,
                    repository_private=True,
                    pr_head_full_name=None,
                    repository="acme/app",
                ),
                "ubuntu-latest",
            ),
            (
                "fork pr with plain self-hosted label",
                dict(
                    ci="plate-local",
                    plate=None,
                    private=True,
                    pull_request={"head": {"repo": {"full_name": "evil/app"}}},
                ),
                dict(
                    ci_runs_on="plate-local",
                    plate_runs_on=None,
                    repository_private=True,
                    pr_head_full_name="evil/app",
                    repository="acme/app",
                ),
                "ubuntu-latest",
            ),
        ]
        for name, eval_kwargs, resolve_kwargs, expected in cases:
            with self.subTest(case=name):
                evaluated = _eval_linux_runs_on(**eval_kwargs)
                self.assertEqual(evaluated, expected)
                resolved = resolve_linux_runs_on(**resolve_kwargs)
                self.assertEqual(resolved, expected)

    def test_all_configurable_runs_on_use_canonical_expression(self):
        violations: list[str] = []
        for root in (REPO_WORKFLOWS, PAYLOAD_WORKFLOWS):
            for path in sorted(root.glob("*.yml")):
                text = path.read_text(encoding="utf-8")
                for doc in yaml.safe_load_all(text):
                    if not isinstance(doc, dict):
                        continue
                    jobs = doc.get("jobs") or {}
                    if not isinstance(jobs, dict):
                        continue
                    for job_id, job in jobs.items():
                        if not isinstance(job, dict):
                            continue
                        runs_on = job.get("runs-on")
                        if not isinstance(runs_on, str):
                            continue
                        if (
                            "vars.CI_RUNS_ON" not in runs_on
                            and "vars.PLATE_RUNS_ON" not in runs_on
                        ):
                            continue
                        if runs_on != LINUX_RUNS_ON_VAR_EXPRESSION:
                            violations.append(f"{path}: {job_id}: {runs_on!r}")
        self.assertEqual(violations, [])

    def test_self_hosted_runners_docs_marker_block_identical(self):
        begin = "<!-- PLATES-CORE:BEGIN self-hosted-runner-repository-variables -->"
        end = "<!-- PLATES-CORE:END self-hosted-runner-repository-variables -->"
        paths = [
            REPO_ROOT / "docs" / "migration" / "self-hosted-runners.md",
            REPO_ROOT
            / "src"
            / "plate_core"
            / "template_payload"
            / "docs"
            / "migration"
            / "self-hosted-runners.md",
        ]
        blocks: list[str] = []
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count(begin), 1, path)
            self.assertEqual(text.count(end), 1, path)
            start = text.index(begin)
            stop = text.index(end) + len(end)
            block = text[start:stop]
            self.assertIn("## Repository variables (all payload Linux jobs)", block)
            blocks.append(block)
        self.assertEqual(blocks[0], blocks[1])


if __name__ == "__main__":
    unittest.main()