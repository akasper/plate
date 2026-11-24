import { marked } from "marked";

marked.setOptions({ gfm: true, async: false });

function headingSlug(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/<[^>]+>/g, "")
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-");
}

marked.use({
  renderer: {
    heading({ text, depth }) {
      const slug = headingSlug(text);
      return `<h${depth} id="${slug}">${text}</h${depth}>\n`;
    },
  },
});

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}

export function wrapDocPage(options: {
  title: string;
  versionLabel: string;
  bodyHtml: string;
  navLinks: { href: string; label: string }[];
}): string {
  const nav = options.navLinks
    .map((l) => `<li><a href="${escapeAttr(l.href)}">${escapeHtml(l.label)}</a></li>`)
    .join("\n");
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(options.title)} — PLATE process (${escapeHtml(options.versionLabel)})</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; line-height: 1.5; }
    body { max-width: 48rem; margin: 0 auto; padding: 1rem 1.25rem 3rem; }
    header { border-bottom: 1px solid #8884; margin-bottom: 1.5rem; padding-bottom: 0.75rem; }
    header a { color: inherit; }
    nav ul { list-style: none; padding: 0; }
    nav li { margin: 0.25rem 0; }
    pre, code { font-size: 0.9em; }
    .muted { opacity: 0.75; font-size: 0.9rem; }
  </style>
</head>
<body>
  <header>
    <p class="muted"><a href="/">plateprocess.dev</a> · PLATE release <strong>${escapeHtml(options.versionLabel)}</strong></p>
    <h1>${escapeHtml(options.title)}</h1>
  </header>
  <main>${options.bodyHtml}</main>
  <nav aria-label="Docs in this version">
    <h2 class="muted">All docs</h2>
    <ul>
${nav}
    </ul>
  </nav>
</body>
</html>`;
}

export function wrapIndexPage(releaseTag: string, entries: { path: string; title: string }[]): string {
  const links = entries.map((e) => ({
    href: `/${encodeURI(e.path.replace(/\.md$/i, ""))}`,
    label: `${e.title} (${e.path})`,
  }));
  const list = links
    .map((l) => `<li><a href="${escapeAttr(l.href)}">${escapeHtml(l.label)}</a></li>`)
    .join("\n");
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PLATE process docs (${escapeHtml(releaseTag)})</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 0 auto; padding: 1.5rem; line-height: 1.5; }
    h1 { font-size: 1.5rem; }
    ul { padding-left: 1.25rem; }
    .muted { opacity: 0.85; font-size: 0.95rem; }
  </style>
</head>
<body>
  <h1>PLATE process docs</h1>
  <p class="muted">Built from git release tag <code>${escapeHtml(releaseTag)}</code> (not a Worker URL version prefix).</p>
  <p><a href="/mcp">MCP endpoint</a> · read-only tools for agents</p>
  <ul>
${list}
  </ul>
</body>
</html>`;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escapeAttr(s: string): string {
  return escapeHtml(s);
}

export { headingSlug };