import type { Env } from "./env";
import { handleMcpRequest } from "./mcp";
import { handleWebsiteRequest } from "./website";

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/mcp" || url.pathname.startsWith("/mcp/")) {
      return handleMcpRequest(request, env);
    }

    if (url.pathname === "/health") {
      return new Response("ok", { headers: { "Content-Type": "text/plain" } });
    }

    return handleWebsiteRequest(request, env);
  },
} satisfies ExportedHandler<Env>;