"""Minimal MCP stdio server for plate_core v1 baseline."""

from __future__ import annotations

import json
import sys

from .baseline_catalog import BaselineCatalogError, delegate_to_agent, get_agent, get_skill, list_agents, list_skills
from .bootstrap import run_bootstrap
from .epics import get_epic_status
from .features import get_features
from .health import get_health
from .mcp.tools import InitPlaywrightTool, RecordE2eGifTool, ValidateE2eTestsTool
from .pr_babysit import babysit_pr, resolve_review_thread
from .mcp.curiosity_tools import (
    CURIOSITY_TOOLS,
    GetAnswersTool,
    GetQuestionTool,
    ListQuestionsTool,
    RecordAnswerTool,
    SynthesizePrioritiesTool,
)


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _plan_epic_stub(args: dict) -> object:
    """Stub for the interactive epic planning tool. Returns a planning schema dict."""
    class _Stub:
        def to_dict(self) -> dict:
            return {
                "tool": "plate_plan_epic",
                "status": "stub",
                "input_received": {k: v for k, v in args.items()},
                "planning_schema": {
                    "epic": {"title": None, "problem_statement": None, "acceptance_criteria": [], "scope_in": [], "scope_out": [], "dependencies": []},
                    "session_state": {"turn": 0, "phase": "detection"},
                    "child_issues": {"research": [], "design": [], "feature": []},
                },
                "note": "Phase 1 stub. Full interactive planning is handled in Copilot chat via the interactive-epic-planning skill.",
            }
    return _Stub()


def _handle_tools_call(req_id: object, params: dict) -> None:
    name = params.get("name")
    args = params.get("arguments", {}) or {}

    try:
        if name == "plate_health":
            report = get_health(args.get("repo"))
            payload = report.to_dict()
        elif name == "plate_epic_status":
            report = get_epic_status(args.get("repo"))
            payload = report.to_dict()
        elif name == "init_playwright":
            payload = InitPlaywrightTool.execute(
                args.get("repo_path", "."),
                args.get("template_repo"),
                bool(args.get("force", False)),
            )
        elif name == "record_e2e_gif":
            test_name = args.get("test_name")
            if not test_name:
                raise ValueError("test_name is required")
            payload = RecordE2eGifTool.execute(
                args.get("repo_path", "."),
                test_name,
                args.get("quality", "medium"),
            )
        elif name == "validate_e2e_tests":
            payload = ValidateE2eTestsTool.execute(args.get("repo_path", "."))
        elif name == "plate_agents":
            payload = {"agents": [agent.to_dict() for agent in list_agents()]}
        elif name == "plate_agent":
            payload = get_agent(args.get("agent_id")).to_dict()
        elif name == "plate_skills":
            payload = {"skills": [skill.to_dict() for skill in list_skills()]}
        elif name == "plate_skill":
            payload = get_skill(args.get("skill_id")).to_dict()
        elif name == "plate_delegate_to_agent":
            agent_id = args.get("agent_id")
            task_description = args.get("task_description")
            if not agent_id:
                raise ValueError("agent_id is required")
            if not task_description:
                raise ValueError("task_description is required")
            payload = delegate_to_agent(agent_id, task_description).to_dict()
        elif name == "plate_features":
            payload = get_features(args.get("repo")).to_dict()
        elif name == "plate_bootstrap":
            payload = run_bootstrap(args.get("repo"), apply_mode=bool(args.get("apply", False))).to_dict()
        elif name == "plate_plan_epic":
            payload = _plan_epic_stub(args).to_dict()
        elif name == "plate_pr_babysit":
            pr_number = args.get("pr_number")
            if pr_number is None:
                raise ValueError("pr_number is required")
            pr_number = int(pr_number)
            if pr_number <= 0:
                raise ValueError("pr_number must be > 0")
            payload = babysit_pr(
                pr_number=pr_number,
                repo=args.get("repo"),
                agent_logins=args.get("agents"),
                act=bool(args.get("act", False)),
            ).to_dict()
        elif name == "plate_resolve_review_thread":
            thread_id = args.get("thread_id")
            if not thread_id:
                raise ValueError("thread_id is required")
            payload = resolve_review_thread(
                thread_id=thread_id,
                repo=args.get("repo"),
            )
        elif name in CURIOSITY_TOOLS:
            # Curiosity / Q&A Mode tools (Epic #139 / Feature #154)
            tool_cls = CURIOSITY_TOOLS[name]
            # Pass through common args + any tool-specific ones
            payload = tool_cls.execute(**args)
        else:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                }
            )
            return

        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(payload)}],
                    "isError": False,
                },
            }
        )
    except Exception as exc:
        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            }
        )


def run() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        req_id = req.get("id")
        method = req.get("method")

        if method == "initialize":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "plate-mcp", "version": "0.1.0"},
                        "capabilities": {"tools": {}},
                    },
                }
            )
        elif method == "tools/list":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "plate_health",
                                "description": "Return PLATE health summary for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_epic_status",
                                "description": "Return Epic and child issue summary for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "init_playwright",
                                "description": "Initialize Playwright E2E testing in a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_path": {
                                            "type": "string",
                                            "description": "Path to target repository. Defaults to current directory.",
                                        },
                                        "template_repo": {
                                            "type": "string",
                                            "description": "Path to template source override. Defaults to plate payload in this repository.",
                                        },
                                        "force": {
                                            "type": "boolean",
                                            "description": "Overwrite existing tests/e2e/ directory. Defaults to false.",
                                        },
                                    },
                                    "required": [],
                                },
                            },
                            {
                                "name": "record_e2e_gif",
                                "description": "Record and generate a demo GIF from a Playwright E2E test.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_path": {
                                            "type": "string",
                                            "description": "Path to repository with Playwright setup.",
                                        },
                                        "test_name": {
                                            "type": "string",
                                            "description": "Name of test to record (e.g., 'login', 'feature-flow').",
                                        },
                                        "quality": {
                                            "type": "string",
                                            "description": "Quality: 'low' (10fps), 'medium' (15fps), 'high' (30fps). Defaults to 'medium'.",
                                        },
                                    },
                                    "required": ["repo_path", "test_name"],
                                },
                            },
                            {
                                "name": "validate_e2e_tests",
                                "description": "Validate Playwright E2E setup and detect missing configuration.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo_path": {
                                            "type": "string",
                                            "description": "Path to repository. Defaults to current directory.",
                                        }
                                    },
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_agents",
                                "description": "Return the baseline agent catalog.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_agent",
                                "description": "Return one baseline agent by id.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "agent_id": {
                                            "type": "string",
                                            "description": "Baseline agent id.",
                                        }
                                    },
                                    "required": ["agent_id"],
                                },
                            },
                            {
                                "name": "plate_skills",
                                "description": "Return the baseline skill catalog.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
                                    "required": [],
                                },
                            },
                            {
                                "name": "plate_skill",
                                "description": "Return one baseline skill by id.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "skill_id": {
                                            "type": "string",
                                            "description": "Baseline skill id.",
                                        }
                                    },
                                    "required": ["skill_id"],
                                },
                            },
                            {
                                "name": "plate_features",
                                "description": "Return optional PLATE capability detection for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "plate_bootstrap",
                                "description": "Plan or apply baseline PLATE bootstrap actions for a repository.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "apply": {
                                            "type": "boolean",
                                            "description": "When true, apply supported actions; default false (dry-run).",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_plan_epic",
                                "description": "Return the interactive epic planning schema for a repository session. Phase 1 stub.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "session_state": {
                                            "type": "object",
                                            "description": "Optional resumption state from a prior planning session.",
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_pr_babysit",
                                "description": (
                                    "Inspect a pull request for unresolved third-party agent feedback and optionally "
                                    "post a babysitting trigger comment for the plate agent."
                                ),
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "pr_number": {
                                            "type": "integer",
                                            "description": "Pull request number.",
                                        },
                                        "agents": {
                                            "type": "string",
                                            "description": "Optional comma-separated GitHub logins treated as third-party agents.",
                                        },
                                        "act": {
                                            "type": "boolean",
                                            "description": "When true, post a babysit trigger comment if actionable threads exist.",
                                        },
                                    },
                                    "required": ["pr_number"],
                                },
                            },
                            {
                                "name": "plate_resolve_review_thread",
                                "description": "Resolve a pull request review thread via GitHub GraphQL resolveReviewThread.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "thread_id": {
                                            "type": "string",
                                            "description": "GraphQL node ID of the review thread to resolve.",
                                        },
                                    },
                                    "required": ["thread_id"],
                                },
                            },
                            {
                                "name": "plate_delegate_to_agent",
                                "description": (
                                    "Route a task to a specific baseline plate agent and return a delegation "
                                    "instruction with the agent's details, skills, constraints, and a ready-to-use "
                                    "delegation prompt. Call this when the user asks to delegate work to a specific "
                                    "agent, wants to know how to use an agent for a task, or an orchestrator needs "
                                    "to route a task to the right agent."
                                ),
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "agent_id": {
                                            "type": "string",
                                            "description": "Baseline agent id to delegate the task to.",
                                        },
                                        "task_description": {
                                            "type": "string",
                                            "description": "Free-text description of the task to delegate.",
                                        },
                                    },
                                    "required": ["agent_id", "task_description"],
                                },
                            },
                            # === Curiosity / Q&A Mode tools (Epic #139, Feature #154) ===
                            # See docs/design/qanda-mcp-cli-surfaces.md and docs/design/curiosity-answer-model.md
                            {
                                "name": "plate_list_questions",
                                "description": "List open Question issues (informational goals) for Curiosity / Q&A Mode. Returns summaries with answer_signal hints. Use with plate_synthesize_priorities for agent-driven prioritization.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional if running inside repo clone.",
                                        },
                                        "state": {
                                            "type": "string",
                                            "description": "open or closed. Defaults to open.",
                                            "default": "open",
                                        },
                                        "limit": {
                                            "type": "integer",
                                            "description": "Max results (default 20).",
                                            "default": 20,
                                        },
                                    },
                                },
                            },
                            {
                                "name": "plate_get_question",
                                "description": "Fetch full details + recent comments + detected PLATE-ANSWER blocks for one Question issue. Powers answer lookup and blocking Question resumption flows.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question_number": {
                                            "type": "integer",
                                            "description": "The GitHub issue number of the Question.",
                                        },
                                        "repo": {
                                            "type": "string",
                                            "description": "owner/name. Optional.",
                                        },
                                        "include_comments": {
                                            "type": "boolean",
                                            "description": "Include recent comments and answer block detection (default true).",
                                            "default": True,
                                        },
                                    },
                                    "required": ["question_number"],
                                },
                            },
                            {
                                "name": "plate_record_answer",
                                "description": "Persist an answer to a Question as a structured PLATE-ANSWER comment block (per Answer Model). This is the primary ingestion hook for Contemplation Engine (#149) and blocking Question resumption (#148). Returns the posted comment + block for logging.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question_number": {"type": "integer", "description": "Target Question issue number."},
                                        "answer_text": {"type": "string", "description": "The user's or agent's answer text (never lost)."},
                                        "answered_by": {"type": "string", "description": "Username or agent id. Defaults to 'agent'."},
                                        "session": {"type": "string", "description": "Optional session/turn id for provenance."},
                                        "source": {"type": "string", "description": "qanda | agent-contemplation | manual | blocking", "default": "qanda"},
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "agent_actions": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "E.g. ['Created: #147', 'Updated wiki'] for Contemplation log.",
                                        },
                                    },
                                    "required": ["question_number", "answer_text"],
                                },
                            },
                            {
                                "name": "plate_get_answers",
                                "description": "Return answers for a Question. Prefers the fast committed docs/curiosity/answers.yml index (Answer Model #150); falls back to scanning PLATE-ANSWER comment blocks on the issue.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question_number": {"type": "integer", "description": "The Question issue number."},
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                    },
                                    "required": ["question_number"],
                                },
                            },
                            {
                                "name": "plate_synthesize_priorities",
                                "description": "Return a ranked list of open Questions with rationale. Initial heuristic implementation; agents and future plate_plan_epic evolution provide richer LLM synthesis. Use before presenting via native Copilot TUI or gh plate qanda.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "repo": {"type": "string", "description": "owner/name. Optional."},
                                        "max_results": {"type": "integer", "description": "Top N to return (default 5).", "default": 5},
                                    },
                                },
                            },
                        ]
                    },
                }
            )
        elif method == "tools/call":
            _handle_tools_call(req_id, req.get("params", {}) or {})
        elif method == "notifications/initialized":
            continue
        elif req_id is None:
            continue
        else:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                }
            )


if __name__ == "__main__":
    run()
