import { z } from "zod";
import type { DocStore } from "./doc-store";
import { DocStoreError } from "./doc-store";
import { normalizeVersionParam } from "./versions";

export const listDocsSchema = z.object({
  version: z.string().optional().describe('PLATE release tag or "latest"'),
});

export const getDocSchema = z.object({
  path: z.string().describe("Doc path relative to docs/, e.g. agents/autopilot-doctrine.md"),
  version: z.string().optional(),
});

export const searchDocsSchema = z.object({
  query: z.string().describe("Search text"),
  version: z.string().optional(),
});

export type ToolCallOutcome =
  | { kind: "ok"; value: Record<string, unknown> }
  | { kind: "err"; error: string; code: string };

export async function mcpListDocs(store: DocStore, args: z.infer<typeof listDocsSchema>): Promise<ToolCallOutcome> {
  const version = normalizeVersionParam(args.version);
  try {
    const tag = await store.resolveTag(version);
    const docs = await store.listDocs(version);
    return { kind: "ok", value: { version, resolved_tag: tag, docs } };
  } catch (e) {
    if (e instanceof DocStoreError) {
      return { kind: "err", error: e.message, code: e.code };
    }
    throw e;
  }
}

export async function mcpGetDoc(store: DocStore, args: z.infer<typeof getDocSchema>): Promise<ToolCallOutcome> {
  const version = normalizeVersionParam(args.version);
  try {
    const tag = await store.resolveTag(version);
    const content = await store.getDoc(args.path, version);
    return { kind: "ok", value: { version, resolved_tag: tag, path: args.path, content } };
  } catch (e) {
    if (e instanceof DocStoreError) {
      return { kind: "err", error: e.message, code: e.code };
    }
    throw e;
  }
}

export async function mcpSearchDocs(store: DocStore, args: z.infer<typeof searchDocsSchema>): Promise<ToolCallOutcome> {
  const version = normalizeVersionParam(args.version);
  try {
    const tag = await store.resolveTag(version);
    const results = await store.searchDocs(args.query, version);
    return { kind: "ok", value: { version, resolved_tag: tag, query: args.query, results } };
  } catch (e) {
    if (e instanceof DocStoreError) {
      return { kind: "err", error: e.message, code: e.code };
    }
    throw e;
  }
}

export const MCP_TOOLS = [
  {
    name: "list_docs",
    description: "List doc paths and titles for a PLATE release version (tag or latest).",
    inputSchema: {
      type: "object",
      properties: {
        version: { type: "string", description: 'Release tag or "latest"' },
      },
    },
  },
  {
    name: "get_doc",
    description: "Return the Markdown content of one doc under docs/.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path relative to docs/" },
        version: { type: "string", description: 'Release tag or "latest"' },
      },
      required: ["path"],
    },
  },
  {
    name: "search_docs",
    description: "Search doc bodies and paths; returns short snippets.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        version: { type: "string", description: 'Release tag or "latest"' },
      },
      required: ["query"],
    },
  },
] as const;