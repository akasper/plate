import { ZodError } from "zod";
import type { Env } from "./env";
import { acceptsMcpMediaTypes } from "./accept";
import { createDocStore } from "./doc-store";
import {
  MCP_TOOLS,
  mcpGetDoc,
  mcpListDocs,
  mcpSearchDocs,
  getDocSchema,
  listDocsSchema,
  searchDocsSchema,
  type ToolCallOutcome,
} from "./mcp-tools";

const SUPPORTED_PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"] as const;
const LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0];

function negotiateProtocolVersion(offered: string | undefined): string {
  if (offered && (SUPPORTED_PROTOCOL_VERSIONS as readonly string[]).includes(offered)) {
    return offered;
  }
  return LATEST_PROTOCOL_VERSION;
}

function isNotificationMethod(method: string): boolean {
  return method.startsWith("notifications/");
}

type JsonRpcRequest = {
  jsonrpc?: string;
  id?: unknown;
  method?: string;
  params?: unknown;
};

/** Stateless JSON-RPC handler for MCP streamable HTTP (subset used by agents). */
export async function handleMcpRequest(request: Request, env: Env): Promise<Response> {
  if (request.method === "GET") {
    return new Response(
      JSON.stringify({
        name: "plate-docs",
        protocol: "mcp-streamable-http",
        tools: MCP_TOOLS.map((t) => t.name),
      }),
      { headers: { "Content-Type": "application/json" } },
    );
  }

  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  if (!acceptsMcpMediaTypes(request.headers.get("Accept"))) {
    return jsonRpcError(null, -32600, "Accept must include application/json or text/event-stream with q > 0");
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonRpcError(null, -32700, "Invalid JSON");
  }

  if (Array.isArray(body) && body.length === 0) {
    return jsonRpcError(null, -32600, "Invalid Request");
  }

  const messages = Array.isArray(body) ? body : [body];
  const isBatch = Array.isArray(body);
  const responses: unknown[] = [];

  const store = createDocStore(env);

  for (const msg of messages) {
    if (typeof msg !== "object" || msg === null || Array.isArray(msg)) {
      responses.push(rpcError(null, -32600, "Invalid Request"));
      continue;
    }

    const rpc = msg as JsonRpcRequest;
    if (rpc.jsonrpc !== "2.0" || typeof rpc.method !== "string") {
      responses.push(rpcError(rpc.id ?? null, -32600, "Invalid Request"));
      continue;
    }

    const hasId = rpc.id !== undefined && rpc.id !== null;

    if (isNotificationMethod(rpc.method)) {
      if (hasId) {
        responses.push({ jsonrpc: "2.0", id: rpc.id, result: {} });
      }
      continue;
    }

    if (!hasId) {
      continue;
    }

    try {
      const result = await dispatchMethod(rpc.method, rpc.params, store);
      responses.push({ jsonrpc: "2.0", id: rpc.id, result });
    } catch (err) {
      if (err instanceof ZodError) {
        responses.push(rpcError(rpc.id, -32602, "Invalid params"));
        continue;
      }
      const message = err instanceof Error ? err.message : "Internal error";
      responses.push(rpcError(rpc.id, -32603, message));
    }
  }

  if (responses.length === 0) {
    return new Response(null, { status: 202 });
  }

  const payload = !isBatch && responses.length === 1 ? responses[0] : responses;
  return new Response(JSON.stringify(payload), {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

async function dispatchMethod(
  method: string,
  params: unknown,
  store: ReturnType<typeof createDocStore>,
): Promise<unknown> {
  switch (method) {
    case "initialize": {
      const p = params as { protocolVersion?: string } | undefined;
      return {
        protocolVersion: negotiateProtocolVersion(p?.protocolVersion),
        capabilities: { tools: {} },
        serverInfo: { name: "plate-docs", version: "0.0.1" },
      };
    }
    case "tools/list":
      return { tools: MCP_TOOLS };
    case "tools/call": {
      const p = params as { name?: string; arguments?: Record<string, unknown> };
      if (!p?.name) throw new Error("Missing tool name");
      const args = p.arguments ?? {};
      switch (p.name) {
        case "list_docs":
          return toolCallResult(await mcpListDocs(store, listDocsSchema.parse(args)));
        case "get_doc":
          return toolCallResult(await mcpGetDoc(store, getDocSchema.parse(args)));
        case "search_docs":
          return toolCallResult(await mcpSearchDocs(store, searchDocsSchema.parse(args)));
        default:
          throw new Error(`Unknown tool: ${p.name}`);
      }
    }
    default:
      throw new Error(`Unknown method: ${method}`);
  }
}

function toolCallResult(outcome: ToolCallOutcome) {
  const isError = outcome.kind === "err";
  const structured =
    outcome.kind === "ok"
      ? outcome.value
      : { error: outcome.error, code: outcome.code };
  return {
    content: [{ type: "text", text: JSON.stringify(structured, null, 2) }],
    structuredContent: structured,
    isError,
  };
}

function rpcError(id: unknown, code: number, message: string) {
  return { jsonrpc: "2.0", id, error: { code, message } };
}

function jsonRpcError(id: unknown, code: number, message: string): Response {
  return new Response(JSON.stringify(rpcError(id, code, message)), {
    status: 400,
    headers: { "Content-Type": "application/json" },
  });
}

export { negotiateProtocolVersion, LATEST_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS };