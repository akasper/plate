import type { Env } from "./env";
import { InvalidDocPathError, normalizeDocPath } from "./doc-path";
import { tagFromVersion, versionMatchesRelease } from "./versions";
import { FIXTURE_INDEX, FIXTURE_DOCS } from "./fixture-data";
import bundle from "../generated/bundle.json";

export interface DocEntry {
  path: string;
  title: string;
}

export interface SearchHit {
  path: string;
  title: string;
  snippet: string;
}

export interface DocStore {
  releaseTag(): string;
  resolveTag(version: string): Promise<string>;
  listDocs(version: string): Promise<DocEntry[]>;
  getDoc(path: string, version: string): Promise<string>;
  searchDocs(query: string, version: string): Promise<SearchHit[]>;
}

export class DocStoreError extends Error {
  constructor(
    message: string,
    readonly code: "unknown_version" | "not_found" | "upstream",
  ) {
    super(message);
    this.name = "DocStoreError";
  }
}

export function createDocStore(env: Env): DocStore {
  if (env.DOC_SOURCE === "fixture") {
    return new FixtureDocStore();
  }
  return new BundledDocStore(env);
}

function lookupDoc(docs: Record<string, string>, key: string): string | undefined {
  if (!Object.hasOwn(docs, key)) return undefined;
  return docs[key];
}

class FixtureDocStore implements DocStore {
  private readonly docs = new Map(Object.entries(FIXTURE_DOCS));

  releaseTag(): string {
    return "v0.12.0-fixture";
  }

  async resolveTag(version: string): Promise<string> {
    if (!versionMatchesRelease(version, this.releaseTag())) {
      throw new DocStoreError(`Unknown version: ${version} (deployed: ${this.releaseTag()})`, "unknown_version");
    }
    return this.releaseTag();
  }

  async listDocs(_version: string): Promise<DocEntry[]> {
    return FIXTURE_INDEX.map((e) => ({ ...e }));
  }

  async getDoc(path: string, _version: string): Promise<string> {
    let key: string;
    try {
      key = normalizeDocPath(path);
    } catch (e) {
      if (e instanceof InvalidDocPathError) throw new DocStoreError(e.message, "not_found");
      throw e;
    }
    const content = this.docs.get(key);
    if (content === undefined) {
      throw new DocStoreError(`No doc at path: ${path}`, "not_found");
    }
    return content;
  }

  async searchDocs(query: string, version: string): Promise<SearchHit[]> {
    const q = query.toLowerCase();
    const hits: SearchHit[] = [];
    for (const entry of await this.listDocs(version)) {
      const body = await this.getDoc(entry.path, version);
      const idx = body.toLowerCase().indexOf(q);
      if (idx >= 0 || entry.path.toLowerCase().includes(q) || entry.title.toLowerCase().includes(q)) {
        const start = Math.max(0, idx - 40);
        const snippet = idx >= 0 ? body.slice(start, start + 120).replace(/\s+/g, " ") : entry.title;
        hits.push({ path: entry.path, title: entry.title, snippet });
      }
    }
    return hits;
  }
}

class BundledDocStore implements DocStore {
  private data = bundle as {
    releaseTag: string;
    index: DocEntry[];
    docs: Record<string, string>;
  };

  constructor(private env: Env) {}

  releaseTag(): string {
    return this.data.releaseTag || this.env.RELEASE_TAG || "unknown";
  }

  async resolveTag(version: string): Promise<string> {
    const tag = this.releaseTag();
    if (!versionMatchesRelease(version, tag)) {
      throw new DocStoreError(
        `Unknown version: ${version}. This deployment serves release tag ${tag} only (from git tag at bundle time).`,
        "unknown_version",
      );
    }
    return tag;
  }

  async listDocs(version: string): Promise<DocEntry[]> {
    await this.resolveTag(version);
    return this.data.index.map((e) => ({ ...e }));
  }

  async getDoc(path: string, version: string): Promise<string> {
    await this.resolveTag(version);
    let rel: string;
    try {
      rel = normalizeDocPath(path);
    } catch (e) {
      if (e instanceof InvalidDocPathError) throw new DocStoreError(e.message, "not_found");
      throw e;
    }
    const content = lookupDoc(this.data.docs, rel);
    if (content === undefined) {
      throw new DocStoreError(`No doc at path: ${path}`, "not_found");
    }
    return content;
  }

  async searchDocs(query: string, version: string): Promise<SearchHit[]> {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    await this.resolveTag(version);
    const hits: SearchHit[] = [];
    const limit = 25;
    for (const entry of this.data.index) {
      if (hits.length >= limit) break;
      const body = lookupDoc(this.data.docs, entry.path) ?? "";
      const idx = body.toLowerCase().indexOf(q);
      const pathMatch = entry.path.toLowerCase().includes(q);
      const titleMatch = entry.title.toLowerCase().includes(q);
      if (idx >= 0 || pathMatch || titleMatch) {
        const start = Math.max(0, idx - 40);
        const snippet =
          idx >= 0 ? body.slice(start, start + 160).replace(/\s+/g, " ").trim() : entry.title;
        hits.push({ path: entry.path, title: entry.title, snippet });
      }
    }
    return hits;
  }
}

export function titleFromPath(relPath: string): string {
  const base = relPath.split("/").pop() ?? relPath;
  return base
    .replace(/\.md$/i, "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}