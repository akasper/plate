"""Trusted harvest rules for plates-on-issue-closed (#1472 S3).

Centralizes label matching, author trust, usage-block parsing, and COSTS.md row
formatting so the GitHub Actions workflow and unit tests stay aligned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})

# Explicit automation logins allowed when author_association is not human-trusted
# (e.g. github-actions[bot] posting a mirrored row, Copilot posting closure).
TRUSTED_BOT_LOGINS = frozenset(
    {
        "github-actions[bot]",
        "copilot-swe-agent",
        "cursor[bot]",
    }
)

HARVEST_ISSUE_TYPE_LABELS = frozenset({"Feature", "Question"})

USAGE_BLOCK_RE = re.compile(
    r"===\s*USAGE REPORT\s*===\s*\n?(.*?)(?:\n?\s*===\s*END USAGE REPORT\s*===|$)",
    re.IGNORECASE | re.DOTALL,
)

TOKENS_FIELD_RE = re.compile(r"tokens?\s*:\s*(\S+)", re.IGNORECASE)
COST_FIELD_RE = re.compile(r"cost\s*:\s*(\S+)", re.IGNORECASE)
DURATION_FIELD_RE = re.compile(r"duration\s*:\s*(\S+)", re.IGNORECASE)

TOKENS_VALUE_RE = re.compile(r"^\d{1,12}$")
COST_VALUE_RE = re.compile(r"^\$\d{1,8}(?:\.\d{1,2})?$")
DURATION_VALUE_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")

COST_ROW_MARKER = "<!-- PLATE-USAGE-COST-ROW -->"


def normalize_label_names(labels: list[Any]) -> list[str]:
    out: list[str] = []
    for label in labels or []:
        if isinstance(label, dict):
            name = label.get("name")
            if name:
                out.append(str(name))
        elif label:
            out.append(str(label))
    return out


def issue_has_harvest_type_label(labels: list[Any]) -> bool:
    """Exact match on issue type labels (no substring matching on joined names)."""
    names = set(normalize_label_names(labels))
    return bool(names.intersection(HARVEST_ISSUE_TYPE_LABELS))


def resolve_harvest_issue_type(labels: list[Any]) -> str | None:
    names = set(normalize_label_names(labels))
    if "Feature" in names:
        return "Feature"
    if "Question" in names:
        return "Question"
    return None


def is_trusted_usage_report_author(
    *,
    author_association: str | None,
    login: str | None,
) -> bool:
    assoc = (author_association or "").upper()
    if assoc in TRUSTED_ASSOCIATIONS:
        return True
    user_login = (login or "").strip()
    return user_login in TRUSTED_BOT_LOGINS


def parse_validated_usage_fields(block: str) -> dict[str, str] | None:
    """Return tokens/cost/duration only when every field matches strict patterns."""
    tokens_m = TOKENS_FIELD_RE.search(block or "")
    cost_m = COST_FIELD_RE.search(block or "")
    dur_m = DURATION_FIELD_RE.search(block or "")
    if not tokens_m or not cost_m or not dur_m:
        return None

    tokens = tokens_m.group(1).strip()
    cost = cost_m.group(1).strip()
    duration = dur_m.group(1).strip()

    if not TOKENS_VALUE_RE.match(tokens):
        return None
    if not COST_VALUE_RE.match(cost):
        return None
    if not DURATION_VALUE_RE.match(duration):
        return None

    return {"tokens": tokens, "cost": cost, "duration": duration}


def extract_usage_block(body: str) -> str | None:
    m = USAGE_BLOCK_RE.search(body or "")
    return m.group(1) if m else None


def md_cell_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


@dataclass(frozen=True)
class UsageCostRow:
    closed_at_iso: str
    issue_number: int
    issue_html_url: str
    issue_type: str
    tokens: str
    cost: str
    duration: str
    source_comment_url: str

    def issue_cell(self) -> str:
        """Issue link only — never embed the issue title (untrusted prose)."""
        return f"[#{self.issue_number}]({self.issue_html_url})"

    def markdown_table_row(self) -> str:
        source = f"[comment]({self.source_comment_url})"
        return (
            f"| {self.closed_at_iso} | {self.issue_cell()} | {self.issue_type} | "
            f"{self.tokens} | {self.cost} | {self.duration} | {source} |"
        )

    def recorded_comment_body(self) -> str:
        return "\n".join(
            [
                COST_ROW_MARKER,
                "",
                "Validated usage cost row (automation; trusted author + strict field parse):",
                "",
                self.markdown_table_row(),
            ]
        )


def select_trusted_usage_report_comment(
    comments: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Most recent comment with a USAGE REPORT block from a trusted author."""
    for comment in reversed(comments or []):
        body = comment.get("body") or ""
        if not re.search(r"===\s*USAGE REPORT\s*===", body, re.I):
            continue
        user = comment.get("user") or {}
        if not is_trusted_usage_report_author(
            author_association=comment.get("author_association"),
            login=user.get("login"),
        ):
            continue
        block = extract_usage_block(body)
        if block is None:
            continue
        if parse_validated_usage_fields(block) is None:
            continue
        return comment
    return None


def workflow_github_script() -> str:
    """JavaScript body for actions/github-script (kept in sync via build script)."""
    bots = ", ".join(repr(b) for b in sorted(TRUSTED_BOT_LOGINS))
    assocs = ", ".join(repr(a) for a in sorted(TRUSTED_ASSOCIATIONS))
    return f"""const TRUSTED_ASSOCIATIONS = new Set([{assocs}]);
const TRUSTED_BOT_LOGINS = new Set([{bots}]);
const USAGE_BLOCK_RE = /===\\s*USAGE REPORT\\s*===([\\s\\S]*?)(?:\\n===\\s*END USAGE REPORT\\s*===|$)/i;
const TOKENS_FIELD_RE = /tokens?\\s*:\\s*(\\S+)/i;
const COST_FIELD_RE = /cost\\s*:\\s*(\\S+)/i;
const DURATION_FIELD_RE = /duration\\s*:\\s*(\\S+)/i;
const TOKENS_VALUE_RE = /^\\d{{1,12}}$/;
const COST_VALUE_RE = /^\\$\\d{{1,8}}(?:\\.\\d{{1,2}})?$/;
const DURATION_VALUE_RE = /^\\d{{2}}:\\d{{2}}:\\d{{2}}$/;
const COST_ROW_MARKER = {COST_ROW_MARKER!r};

const isTrustedAuthor = (comment) => {{
  const assoc = String(comment.author_association || '').toUpperCase();
  if (TRUSTED_ASSOCIATIONS.has(assoc)) return true;
  const login = (comment.user && comment.user.login) || '';
  return TRUSTED_BOT_LOGINS.has(login);
}};

const parseValidatedFields = (block) => {{
  const tokensM = block.match(TOKENS_FIELD_RE);
  const costM = block.match(COST_FIELD_RE);
  const durM = block.match(DURATION_FIELD_RE);
  if (!tokensM || !costM || !durM) return null;
  const tokens = tokensM[1].trim();
  const cost = costM[1].trim();
  const duration = durM[1].trim();
  if (!TOKENS_VALUE_RE.test(tokens) || !COST_VALUE_RE.test(cost) || !DURATION_VALUE_RE.test(duration)) {{
    return null;
  }}
  return {{ tokens, cost, duration }};
}};

const issue = context.payload.issue;
const issueType = (() => {{
  const names = new Set((issue.labels || []).map((label) => (typeof label === 'string' ? label : label.name || '')));
  if (names.has('Feature')) return 'Feature';
  if (names.has('Question')) return 'Question';
  return null;
}})();
if (!issueType) {{
  core.info('Issue lacks exact Feature/Question label; skipping harvest.');
  core.setOutput('has_report', 'false');
  return;
}}

const comments = await github.paginate(github.rest.issues.listComments, {{
  owner: context.repo.owner,
  repo: context.repo.repo,
  issue_number: issue.number,
  per_page: 100
}});

let reportComment = null;
let parsed = null;
for (let i = comments.length - 1; i >= 0; i -= 1) {{
  const comment = comments[i];
  const body = comment.body || '';
  if (!/===\\s*USAGE REPORT\\s*===/i.test(body)) continue;
  if (!isTrustedAuthor(comment)) {{
    core.warning(`Ignoring usage report on #${{issue.number}} from untrusted author ${{comment.user?.login || 'unknown'}} (${{comment.author_association || 'NONE'}}).`);
    continue;
  }}
  const blockMatch = body.match(USAGE_BLOCK_RE);
  const block = blockMatch ? blockMatch[1] : '';
  const fields = parseValidatedFields(block);
  if (!fields) {{
    core.warning(`Ignoring malformed usage report on #${{issue.number}} (strict field validation failed).`);
    continue;
  }}
  reportComment = comment;
  parsed = fields;
  break;
}}

if (!reportComment || !parsed) {{
  core.warning(`No trusted, valid usage report block found for issue #${{issue.number}}.`);
  core.setOutput('has_report', 'false');
  return;
}}

const closedAt = new Date(issue.closed_at || Date.now()).toISOString();
const issueCell = `[#${{issue.number}}](${{issue.html_url}})`;
const sourceCell = `[comment](${{reportComment.html_url}})`;
const row = `| ${{closedAt}} | ${{issueCell}} | ${{issueType}} | ${{parsed.tokens}} | ${{parsed.cost}} | ${{parsed.duration}} | ${{sourceCell}} |`;
const recordBody = [
  COST_ROW_MARKER,
  '',
  'Validated usage cost row (automation; trusted author + strict field parse):',
  '',
  row
].join('\\n');

const alreadyRecorded = comments.some((c) => (c.body || '').includes(COST_ROW_MARKER) && (c.body || '').includes(reportComment.html_url));
core.setOutput('has_report', 'true');
core.setOutput('tokens', parsed.tokens);
core.setOutput('cost', parsed.cost);
core.setOutput('duration', parsed.duration);
core.setOutput('comment_url', reportComment.html_url);
core.setOutput('row', row);
core.setOutput('record_body', recordBody);
core.setOutput('already_recorded', alreadyRecorded ? 'true' : 'false');
"""