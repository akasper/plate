export class InvalidDocPathError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InvalidDocPathError";
  }
}

/**
 * Normalise and validate a doc path for bundle lookup (defence in depth).
 */
export function normalizeDocPath(path: string): string {
  let raw = path.trim();
  if (!raw || raw.includes("\0")) {
    throw new InvalidDocPathError(`Invalid path: ${path}`);
  }

  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    throw new InvalidDocPathError(`Invalid path: ${path}`);
  }
  if (decoded.includes("\0")) {
    throw new InvalidDocPathError(`Invalid path: ${path}`);
  }

  const slashNormalised = decoded.replace(/\\/g, "/");
  if (slashNormalised.startsWith("/") || /^[a-zA-Z]:/.test(slashNormalised)) {
    throw new InvalidDocPathError(`Invalid path: ${path}`);
  }
  const normalised = slashNormalised.replace(/^\.\//, "");

  const segments = normalised.split("/").filter((s) => s.length > 0);
  for (const seg of segments) {
    if (seg === "..") {
      throw new InvalidDocPathError(`Invalid path: ${path}`);
    }
  }
  return segments.join("/");
}