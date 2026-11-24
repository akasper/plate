/** True when Accept allows JSON and/or event-stream with q > 0. */
export function acceptsMcpMediaTypes(acceptHeader: string | null): boolean {
  if (!acceptHeader?.trim()) {
    return true;
  }
  let jsonAllowed = false;
  let sseAllowed = false;
  for (const part of acceptHeader.split(",")) {
    const tokens = part.trim().split(";").map((t) => t.trim());
    const media = tokens[0]?.toLowerCase() ?? "";
    let q = 1;
    for (const token of tokens.slice(1)) {
      if (token.toLowerCase().startsWith("q=")) {
        const parsed = Number.parseFloat(token.slice(2));
        if (!Number.isNaN(parsed)) q = parsed;
      }
    }
    if (q === 0) continue;
    if (media === "*/*" || media === "application/*") {
      jsonAllowed = true;
      sseAllowed = true;
    }
    if (media === "application/json") jsonAllowed = true;
    if (media === "text/event-stream") sseAllowed = true;
  }
  return jsonAllowed || sseAllowed;
}