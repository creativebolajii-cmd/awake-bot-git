import { randomBytes } from "node:crypto";
import type { ScrapeRequest } from "../lib/pythonRuntime";

const TTL_MS = 30 * 60 * 1000;

interface Entry<T> {
  value: T;
  expiresAt: number;
}

function makeStore<T>() {
  const map = new Map<string, Entry<T>>();

  function sweep() {
    const now = Date.now();
    for (const [key, entry] of map) {
      if (entry.expiresAt < now) map.delete(key);
    }
  }

  return {
    put(value: T): string {
      sweep();
      const id = randomBytes(6).toString("hex");
      map.set(id, { value, expiresAt: Date.now() + TTL_MS });
      return id;
    },
    get(id: string): T | undefined {
      const entry = map.get(id);
      if (!entry) return undefined;
      if (entry.expiresAt < Date.now()) {
        map.delete(id);
        return undefined;
      }
      return entry.value;
    },
  };
}

export type PendingScrape = Pick<ScrapeRequest, "source" | "url" | "site">;

export const pendingScrapes = makeStore<PendingScrape>();
export const scrapeResults = makeStore<Record<string, unknown>>();
