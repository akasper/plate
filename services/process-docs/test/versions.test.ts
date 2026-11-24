import { describe, expect, it } from "vitest";
import { compareSemverTags, pickLatestTag, tagFromVersion, versionMatchesRelease } from "../src/versions";

describe("versions", () => {
  it("normalizes tags", () => {
    expect(tagFromVersion("0.12.0")).toBe("v0.12.0");
    expect(tagFromVersion("v0.12.0")).toBe("v0.12.0");
    expect(tagFromVersion("latest")).toBe("latest");
  });

  it("picks latest semver tag", () => {
    expect(pickLatestTag(["v0.11.0", "v0.12.0", "v0.10.1"])).toBe("v0.12.0");
  });

  it("compares semver", () => {
    expect(compareSemverTags("v0.12.0", "v0.11.0")).toBeGreaterThan(0);
    expect(compareSemverTags("v0.10.0", "v0.12.0")).toBeLessThan(0);
  });

  it("matches deployed release only", () => {
    expect(versionMatchesRelease("latest", "v0.12.0")).toBe(true);
    expect(versionMatchesRelease("v0.12.0", "v0.12.0")).toBe(true);
    expect(versionMatchesRelease("v0.11.0", "v0.12.0")).toBe(false);
  });
});