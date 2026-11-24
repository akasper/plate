/**
 * CI link check for docs/ relative markdown links (same rules as the website tree).
 * Run from repo root: cd services/process-docs && npm run check:links
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");
const docsRoot = path.join(repoRoot, "docs");

const BUNDLE_ROOT_FILES = new Set(["AGENTS.md"]);

const LINK_RE = /\[[^\]]*\]\(([^)]+)\)/g;

function collectMdFiles(dir: string): string[] {
  const out: string[] = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) out.push(...collectMdFiles(p));
    else if (ent.name.endsWith(".md")) out.push(p);
  }
  return out;
}

function isExternal(target: string): boolean {
  if (/^[a-z]+:/i.test(target) || target.startsWith("//")) return true;
  if (target === "url" || target === "path") return true;
  return false;
}

function resolveSitePath(_fromDocFile: string, target: string): string | null {
  const base = target.split("#")[0]?.trim() ?? "";
  if (base === "../AGENTS.md" || base === "../../AGENTS.md" || base === "AGENTS.md") {
    return "AGENTS.md";
  }
  const resolved = path.normalize(path.join(path.dirname(_fromDocFile), target));
  const relToDocs = path.relative(docsRoot, resolved);
  if (!relToDocs.startsWith("..") && !path.isAbsolute(relToDocs)) {
    return relToDocs.split(path.sep).join("/");
  }
  const relToRepo = path.relative(repoRoot, resolved).split(path.sep).join("/");
  if (BUNDLE_ROOT_FILES.has(relToRepo)) return relToRepo;
  return null;
}

const files = collectMdFiles(docsRoot);
const errors: string[] = [];

for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  const relFile = path.relative(docsRoot, file).split(path.sep).join("/");
  let m: RegExpExecArray | null;
  while ((m = LINK_RE.exec(text))) {
    let target = m[1].trim();
    if (!target || isExternal(target) || target.startsWith("#")) continue;
    target = target.split("#")[0] ?? "";
    if (!target) continue;
    const sitePath = resolveSitePath(file, target);
    if (!sitePath) {
      continue;
    }
    const onDisk =
      sitePath === "AGENTS.md"
        ? fs.existsSync(path.join(repoRoot, "AGENTS.md"))
        : fs.existsSync(path.join(docsRoot, sitePath));
    if (!onDisk) {
      errors.push(`${relFile}: broken link → ${target} (missing bundled target ${sitePath})`);
    }
  }
}

if (errors.length) {
  console.error("Broken internal doc links:\n" + errors.join("\n"));
  process.exit(1);
}
console.log(`Checked ${files.length} markdown files under docs/ — no broken relative links.`);