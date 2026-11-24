const TAG_PATTERN = /^v?\d+\.\d+\.\d+/;

export function normalizeVersionParam(version: string | undefined): string {
  const v = (version ?? "latest").trim();
  if (!v) return "latest";
  return v;
}

export function tagFromVersion(version: string): string {
  if (version === "latest") return "latest";
  const trimmed = version.replace(/^\/+|\/+$/g, "");
  if (trimmed.startsWith("v")) return trimmed;
  if (TAG_PATTERN.test(trimmed)) return `v${trimmed.replace(/^v/, "")}`;
  return trimmed;
}

/** Accept only the deployed release tag (or latest / omitted). */
export function versionMatchesRelease(version: string | undefined, releaseTag: string): boolean {
  const v = normalizeVersionParam(version);
  if (v === "latest") return true;
  const wanted = tagFromVersion(v);
  const deployed = tagFromVersion(releaseTag);
  return wanted === deployed || v === releaseTag;
}

export function compareSemverTags(a: string, b: string): number {
  const pa = parseSemver(a);
  const pb = parseSemver(b);
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pa[i] - pb[i];
  }
  return 0;
}

function parseSemver(tag: string): [number, number, number] {
  const m = tag.replace(/^v/, "").match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!m) return [0, 0, 0];
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

export function pickLatestTag(tags: string[]): string | null {
  const semver = tags.filter((t) => TAG_PATTERN.test(t));
  if (semver.length === 0) return null;
  semver.sort(compareSemverTags);
  return semver[semver.length - 1] ?? null;
}