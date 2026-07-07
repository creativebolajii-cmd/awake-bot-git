import type { ScrapeRequest } from "../lib/pythonRuntime";

export interface DetectedSource {
  source: ScrapeRequest["source"];
  site?: "nkiri" | "dramakey";
}

export function detectSource(url: string): DetectedSource | null {
  let host: string;
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }

  if (host.includes("9jarocks")) {
    return { source: "9jarocks" };
  }
  if (host.includes("naijaprey")) {
    return { source: "naijaprey" };
  }
  if (host.includes("dramakey")) {
    return { source: "nkiri-dramakey", site: "dramakey" };
  }
  if (host.includes("nkiri")) {
    return { source: "nkiri-dramakey", site: "nkiri" };
  }
  return null;
}
