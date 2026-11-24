/** Embedded docs for unit tests and optional offline dev (DOC_SOURCE=fixture). */

export const FIXTURE_INDEX = [
  { path: "agents/autopilot-doctrine.md", title: "Autopilot Doctrine" },
  { path: "wiki/Home.md", title: "Home" },
  { path: "research/README.md", title: "README" },
] as const;

export const FIXTURE_DOCS: Record<string, string> = {
  "agents/autopilot-doctrine.md": `# Autopilot Doctrine

Agents ship small PRs and wait for human review unless autonomous mode applies.

See also [Home](../wiki/Home.md).
`,
  "wiki/Home.md": `# PLATE process docs (fixture)

Welcome to the fixture doc set used in CI for plateprocess.dev.
`,
  "research/README.md": `# Research notes

Fixture research index for search_docs tests. Keyword: PLATEPROCESS_FIXTURE_TOKEN.
`,
};