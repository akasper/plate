import { describe, expect, it } from "vitest";
import { headingSlug, markdownToHtml } from "../src/html";

describe("markdown html", () => {
  it("adds heading ids for fragment links", () => {
    const html = markdownToHtml("## Slice issues\n\nSee [slice](#slice-issues).");
    expect(html).toContain('id="slice-issues"');
    expect(html).toContain("Slice issues");
  });

  it("slugifies headings", () => {
    expect(headingSlug("Slice issues")).toBe("slice-issues");
  });
});