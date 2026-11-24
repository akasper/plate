import type { Env } from "./env";
import { createDocStore, DocStoreError } from "./doc-store";
import { markdownToHtml, wrapDocPage, wrapIndexPage } from "./html";

const RESERVED = new Set(["mcp", "health"]);

export async function handleWebsiteRequest(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const store = createDocStore(env);

  let rest = url.pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  if (!rest) {
    try {
      const tag = store.releaseTag();
      const entries = await store.listDocs("latest");
      return htmlResponse(wrapIndexPage(tag, entries));
    } catch (err) {
      if (err instanceof DocStoreError) {
        return new Response(err.message, { status: 404 });
      }
      throw err;
    }
  }

  const head = rest.split("/")[0] ?? "";
  if (RESERVED.has(head)) {
    return new Response("Not found", { status: 404 });
  }

  try {
    const tag = store.releaseTag();
    const docPath = rest.endsWith(".md") ? rest : `${rest}.md`;
    const markdown = await store.getDoc(docPath, "latest");
    const entries = await store.listDocs("latest");
    const navLinks = entries.map((e) => ({
      href: `/${e.path.replace(/\.md$/i, "")}`,
      label: e.title,
    }));
    const title = entries.find((e) => e.path === docPath)?.title ?? docPath;
    const page = wrapDocPage({
      title,
      versionLabel: tag,
      bodyHtml: markdownToHtml(markdown),
      navLinks,
    });
    return htmlResponse(page);
  } catch (err) {
    if (err instanceof DocStoreError) {
      const status = err.code === "not_found" || err.code === "unknown_version" ? 404 : 502;
      return new Response(err.message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    throw err;
  }
}

function htmlResponse(body: string): Response {
  return new Response(body, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "public, max-age=300",
    },
  });
}