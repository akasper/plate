"""Minimal MCP stdio server for plate_core v1 baseline."""

from __future__ import annotations

import json
import sys

from .baseline_catalog import get_agent, get_skill, list_agents, list_skills
from .epics import get_epic_status
from .health import get_health
from .mcp.tools import InitPlaywrightTool, RecordE2eGifTool, ValidateE2eTestsTool


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


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
            )
        elif name == "record_e2e_gif":
            payload = RecordE2eGifTool.execute(
                args.get("repo_path", "."),
                args.get("test_name"),
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
                                            "description": "Path to template repository. Defaults to plate_template.",
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
