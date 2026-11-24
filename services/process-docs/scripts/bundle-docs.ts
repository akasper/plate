/**
 * Bundle repo docs/ for the Worker at build/deploy time.
 * Run from a checkout of the release tag you intend to ship.
 */
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const serviceRoot = path.resolve(here, "..");
const docsRoot = path.resolve(serviceRoot, "../../docs");
const outDir = path.join(serviceRoot, "generated");
const outFile = path.join(outDir, "bundle.json");

function releaseTag(): string {
  if (process.env.RELEASE_TAG?.trim()) return process.env.RELEASE_TAG.trim();
  try {
    return execSync("git describe --tags --exact-match", { encoding: "utf8", cwd: serviceRoot }).trim();
  } catch {
    try {
      return execSync("git describe --tags --abbrev=0", { encoding: "utf8", cwd: serviceRoot }).trim();
    } catch {
      return "untagged";
    }
  }
}

function titleFromPath(relPath: string): string {
  const base = relPath.split("/").pop() ?? relPath;
  return base
    .replace(/\.md$/i, "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function walkMd(dir: string, prefix = ""): string[] {
  const out: string[] = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${ent.name}` : ent.name;
    const abs = path.join(dir, ent.name);
    if (ent.isDirectory()) out.push(...walkMd(abs, rel));
    else if (ent.name.endsWith(".md")) out.push(rel.split(path.sep).join("/"));
  }
  return out;
}

if (!fs.existsSync(docsRoot)) {
  console.error(`docs root not found: ${docsRoot}`);
  process.exit(1);
}

const tag = releaseTag();
const paths = walkMd(docsRoot).sort();
const docs: Record<string, string> = {};
const index = paths.map((p) => {
  const abs = path.join(docsRoot, p);
  const content = fs.readFileSync(abs, "utf8");
  docs[p] = content;
  return { path: p, title: titleFromPath(p) };
});

fs.mkdirSync(outDir, { recursive: true });
const bundle = { releaseTag: tag, index, docs };
fs.writeFileSync(outFile, JSON.stringify(bundle));
console.log(`Wrote ${outFile} (${index.length} docs, releaseTag=${tag})`);