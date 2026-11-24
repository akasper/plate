import { describe, expect, it } from "vitest";
import {
  TAG_PATTERN,
  compareSemverTags,
  pickLatestTag,
  tagFromVersion,
  versionMatchesRelease,
} from "../src/versions";

describe("versions", () => {
  it("normalizes tags", () => {
    expect(tagFromVersion("0.12.0")).toBe("v0.12.0");
    expect(tagFromVersion("v0.12.0")).toBe("v0.12.0");
    expect(tagFromVersion("latest")).toBe("latest");
  });

  it("rejects non-semver suffixes in pattern", () => {
    expect(TAG_PATTERN.test("1.2.3-evil")).toBe(false);
    expect(tagFromVersion("1.2.3-evil")).toBe("1.2.3-evil");
    expect(versionMatchesRelease("1.2.3-evil", "v0.12.0")).toBe(false);
  });

  it("picks latest semver tag", () => {
    expect(pickLatestTag(["v0.11.0", "v0.12.0", "v0.10.1", "v0.12.0-rc1"])).toBe("v0.12.0");
  });

  it("compares semver", () => {
    expect(compareSemverTags("v0.12.0", "v0.11.0")).toBeGreaterThan(0);
    expect(compareSemverTags("v0.10.0", "v0.12.0")).toBeLessThan(0);
  });

  it("matches deployed release only", () => {
    expect(versionMatchesRelease("latest", "v0.12.0")).toBe(true);
    expect(versionMatchesRelease("LATEST", "v0.12.0")).toBe(true);
    expect(versionMatchesRelease("v0.12.0", "v0.12.0")).toBe(true);
    expect(versionMatchesRelease("v0.11.0", "v0.12.0")).toBe(false);
    expect(versionMatchesRelease(undefined, "v0.12.0")).toBe(true);
  });

  it("rejects invalid tag shapes", () => {
    expect(pickLatestTag(["vfoo", "v1.2"])).toBeNull();
    expect(versionMatchesRelease("vfoo", "v0.12.0")).toBe(false);
  });
});