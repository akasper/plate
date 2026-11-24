import { describe, expect, it } from "vitest";
import { createDocStore, DocStoreError } from "../src/doc-store";
import type { Env } from "../src/env";

const fixtureEnv: Env = {
  RELEASE_TAG: "v0.12.0-fixture",
  DOC_SOURCE: "fixture",
};

describe("fixture doc store", () => {
  const store = createDocStore(fixtureEnv);

  it("lists docs", async () => {
    const docs = await store.listDocs("latest");
    expect(docs.length).toBeGreaterThanOrEqual(3);
    expect(docs.some((d) => d.path === "wiki/Home.md")).toBe(true);
  });

  it("gets doc content", async () => {
    const body = await store.getDoc("wiki/Home.md", "v0.12.0-fixture");
    expect(body).toContain("fixture");
  });

  it("unknown path returns not_found", async () => {
    await expect(store.getDoc("nope/missing.md", "latest")).rejects.toMatchObject({
      code: "not_found",
    } satisfies Partial<DocStoreError>);
  });

  it("unknown version", async () => {
    await expect(store.resolveTag("v99.99.99")).rejects.toMatchObject({
      code: "unknown_version",
    });
  });

  it("search finds token", async () => {
    const hits = await store.searchDocs("PLATEPROCESS_FIXTURE_TOKEN", "latest");
    expect(hits.some((h) => h.path === "research/README.md")).toBe(true);
    expect(hits[0]?.snippet.length).toBeGreaterThan(0);
  });
});