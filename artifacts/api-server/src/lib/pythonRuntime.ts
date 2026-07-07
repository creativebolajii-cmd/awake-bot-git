import path from "node:path";
import { spawn } from "node:child_process";

const workspaceRoot = process.cwd().endsWith(path.join("artifacts", "api-server"))
  ? path.resolve(process.cwd(), "../..")
  : process.cwd();

const pythonBin =
  process.env["PYTHON_BIN"] ?? path.resolve(workspaceRoot, ".pythonlibs/bin/python3");
const runScrapePath = path.resolve(
  workspaceRoot,
  "artifacts/api-server/src/scrapers/run_scrape.py",
);

export interface ScrapeRequest {
  source: "9jarocks" | "naijaprey" | "nkiri-dramakey";
  url: string;
  mode: "movie" | "series";
  site?: "nkiri" | "dramakey";
}

const SCRAPE_TIMEOUT_MS = 35_000;

export function runScrape(input: ScrapeRequest): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, [runScrapePath], {
      cwd: workspaceRoot,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill("SIGKILL");
      reject(new Error("Scrape timed out — the source site took too long to respond"));
    }, SCRAPE_TIMEOUT_MS);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    child.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(err);
    });

    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(stderr.trim() || `Scraper exited with code ${code}`));
        return;
      }
      const trimmed = stdout.trim();
      if (!trimmed) {
        reject(new Error(stderr.trim() || "Scraper produced no output"));
        return;
      }
      try {
        resolve(JSON.parse(trimmed));
      } catch {
        reject(new Error(stderr.trim() || "Failed to parse scraper output"));
      }
    });

    child.stdin.write(JSON.stringify(input));
    child.stdin.end();
  });
}
