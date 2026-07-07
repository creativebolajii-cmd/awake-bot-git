import { Router, type IRouter } from "express";
import {
  Scrape9jarocksBody,
  Scrape9jarocksResponse,
  ScrapeNaijapreyBody,
  ScrapeNaijapreyResponse,
  ScrapeNkiriDramakeyBody,
  ScrapeNkiriDramakeyResponse,
  ListScrapeSourcesResponse,
} from "@workspace/api-zod";
import { runScrape } from "../lib/pythonRuntime";

const router: IRouter = Router();

// ─── URL allowlist validation ───────────────────────────────────────────────
// Each source lists the allowed base domains (www. and bare both accepted).
const ALLOWED_BASE_DOMAINS: Record<string, string[]> = {
  "9jarocks": ["9jarocks.com"],
  "naijaprey": ["naijaprey.tv"],
  "nkiri-dramakey": ["nkiri.com", "dramakey.com"],
};

function isAllowedHostname(hostname: string, source: string): boolean {
  const allowed = ALLOWED_BASE_DOMAINS[source] ?? [];
  const h = hostname.toLowerCase();
  return allowed.some((d) => h === d || h.endsWith("." + d));
}

function validateUrl(url: string, source: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return "Invalid URL";
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    return "URL must use http or https";
  }
  if (!isAllowedHostname(parsed.hostname, source)) {
    return `URL hostname '${parsed.hostname}' is not allowed for source '${source}'`;
  }
  return null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────
function scrapeErrorMessage(result: Record<string, unknown>): string | null {
  const e = result["error"];
  return typeof e === "string" && e.trim() ? e.trim() : null;
}

// ─── Routes ─────────────────────────────────────────────────────────────────
router.get("/scrape/sources", (_req, res): void => {
  const sources = ListScrapeSourcesResponse.parse([
    { id: "9jarocks", label: "9jarocks", needsSite: false },
    { id: "naijaprey", label: "NaijaPrey", needsSite: false },
    { id: "nkiri-dramakey", label: "Nkiri / Dramakey", needsSite: true },
  ]);
  res.json(sources);
});

router.post("/scrape/9jarocks", async (req, res): Promise<void> => {
  const parsed = Scrape9jarocksBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const urlError = validateUrl(parsed.data.url, "9jarocks");
  if (urlError) {
    res.status(400).json({ error: urlError });
    return;
  }

  try {
    const result = await runScrape({ source: "9jarocks", ...parsed.data });
    const errMsg = scrapeErrorMessage(result);
    if (errMsg) {
      res.status(500).json({ error: errMsg });
      return;
    }
    res.json(Scrape9jarocksResponse.parse(result));
  } catch (err) {
    req.log.error({ err }, "9jarocks scrape failed");
    res.status(500).json({ error: err instanceof Error ? err.message : "Scrape failed" });
  }
});

router.post("/scrape/naijaprey", async (req, res): Promise<void> => {
  const parsed = ScrapeNaijapreyBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const urlError = validateUrl(parsed.data.url, "naijaprey");
  if (urlError) {
    res.status(400).json({ error: urlError });
    return;
  }

  try {
    const result = await runScrape({ source: "naijaprey", ...parsed.data });
    const errMsg = scrapeErrorMessage(result);
    if (errMsg) {
      res.status(500).json({ error: errMsg });
      return;
    }
    res.json(ScrapeNaijapreyResponse.parse(result));
  } catch (err) {
    req.log.error({ err }, "naijaprey scrape failed");
    res.status(500).json({ error: err instanceof Error ? err.message : "Scrape failed" });
  }
});

router.post("/scrape/nkiri-dramakey", async (req, res): Promise<void> => {
  const parsed = ScrapeNkiriDramakeyBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const urlError = validateUrl(parsed.data.url, "nkiri-dramakey");
  if (urlError) {
    res.status(400).json({ error: urlError });
    return;
  }

  try {
    const result = await runScrape({ source: "nkiri-dramakey", ...parsed.data });
    const errMsg = scrapeErrorMessage(result);
    if (errMsg) {
      res.status(500).json({ error: errMsg });
      return;
    }
    res.json(ScrapeNkiriDramakeyResponse.parse(result));
  } catch (err) {
    req.log.error({ err }, "nkiri-dramakey scrape failed");
    res.status(500).json({ error: err instanceof Error ? err.message : "Scrape failed" });
  }
});

export default router;
