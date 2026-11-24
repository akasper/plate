import { describe, expect, it } from "vitest";
import { InvalidDocPathError, normalizeDocPath } from "../src/doc-path";

describe("normalizeDocPath", () => {
  it("accepts normal paths", () => {
    expect(normalizeDocPath("wiki/Home.md")).toBe("wiki/Home.md");
  });

  it("rejects traversal", () => {
    expect(() => normalizeDocPath("../wiki/Home.md")).toThrow(InvalidDocPathError);
    expect(() => normalizeDocPath("%2e%2e/wiki/Home.md")).toThrow(InvalidDocPathError);
    expect(() => normalizeDocPath("..\\wiki\\Home.md")).toThrow(InvalidDocPathError);
  });

  it("rejects absolute paths", () => {
    expect(() => normalizeDocPath("/etc/passwd")).toThrow(InvalidDocPathError);
  });
});