import type { Env } from "./env";
import { createDocStore } from "./doc-store";
import {
  MCP_TOOLS,
  mcpGetDoc,
  mcpListDocs,
  mcpSearchDocs,
  getDocSchema,
  listDocsSchema,
  searchDocsSchema,
} from "./mcp-tools";

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

  const accept = request.headers.get("Accept") ?? "application/json";
  if (!accept.includes("application/json") && !accept.includes("text/event-stream")) {
    return jsonRpcError(null, -32600, "Accept must include application/json or text/event-stream");
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonRpcError(null, -32700, "Invalid JSON");
  }

  const messages = Array.isArray(body) ? body : [body];
  const responses: unknown[] = [];

  const store = createDocStore(env);

  for (const msg of messages) {
    const rpc = msg as { jsonrpc?: string; id?: unknown; method?: string; params?: unknown };
    if (rpc.jsonrpc !== "2.0" || rpc.method === undefined) {
      responses.push(rpcError(rpc.id ?? null, -32600, "Invalid Request"));
      continue;
    }

    try {
      const result = await dispatchMethod(rpc.method, rpc.params, store);
      if (rpc.id !== undefined) {
        responses.push({ jsonrpc: "2.0", id: rpc.id, result });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Internal error";
      if (rpc.id !== undefined) {
        responses.push(rpcError(rpc.id, -32603, message));
      }
    }
  }

  const payload = responses.length === 1 ? responses[0] : responses;
  return new Response(JSON.stringify(payload), {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

async function dispatchMethod(method: string, params: unknown, store: ReturnType<typeof createDocStore>): Promise<unknown> {
  switch (method) {
    case "initialize":
      return {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "plate-docs", version: "0.0.1" },
      };
    case "notifications/initialized":
      return null;
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

function toolCallResult(structured: unknown) {
  return {
    content: [{ type: "text", text: JSON.stringify(structured, null, 2) }],
    structuredContent: structured,
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