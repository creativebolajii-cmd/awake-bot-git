import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search, Loader2, Download, Play, AlertCircle, Film, Tv, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

// ─── Source detection (mirrors backend detectSource.ts) ───────────────────────
type Source = "9jarocks" | "naijaprey" | "nkiri-dramakey";
type SiteHint = "nkiri" | "dramakey" | undefined;

interface Detected {
  source: Source;
  site?: SiteHint;
  label: string;
}

function detectSource(url: string): Detected | null {
  let host: string;
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
  if (host.includes("9jarocks")) return { source: "9jarocks", label: "9jarocks" };
  if (host.includes("naijaprey")) return { source: "naijaprey", label: "NaijaPrey" };
  if (host.includes("dramakey")) return { source: "nkiri-dramakey", site: "dramakey", label: "Dramakey" };
  if (host.includes("nkiri")) return { source: "nkiri-dramakey", site: "nkiri", label: "Nkiri" };
  return null;
}

// ─── API call ─────────────────────────────────────────────────────────────────
interface ScrapeInput {
  source: Source;
  url: string;
  mode: "movie" | "series";
  site?: SiteHint;
}

type ScrapeResult = Record<string, unknown>;

async function doScrape(input: ScrapeInput): Promise<ScrapeResult> {
  const body: Record<string, string> = { url: input.url, mode: input.mode };
  if (input.site) body["site"] = input.site;

  const res = await fetch(`/api/scrape/${input.source}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data?.error ?? `HTTP ${res.status}`);
  if (data?.error) throw new Error(data.error);
  return data;
}

// ─── Result display helpers ───────────────────────────────────────────────────
function str(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

function MetaRow({ label, value }: { label: string; value: unknown }) {
  const v = str(value);
  if (!v) return null;
  return (
    <div className="flex gap-2 text-sm">
      <span className="text-muted-foreground w-28 shrink-0">{label}</span>
      <span className="text-foreground font-medium">{v}</span>
    </div>
  );
}

interface DownloadLink { quality: string; link: string }
interface Episode { episode: number; title: string; url: string }

// ─── Main component ───────────────────────────────────────────────────────────
export function ScraperForm() {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"movie" | "series">("movie");
  const [showEpisodes, setShowEpisodes] = useState(false);
  const [showJson, setShowJson] = useState(false);

  const detected = url.trim() ? detectSource(url.trim()) : null;

  const mutation = useMutation({
    mutationFn: (vars: ScrapeInput) => doScrape(vars),
    onSuccess: () => {
      setShowEpisodes(false);
      setShowJson(false);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed || !detected) return;
    mutation.mutate({ source: detected.source, url: trimmed, mode, site: detected.site });
  }

  const result = mutation.data;
  const isPending = mutation.isPending;
  const error = mutation.error;

  // Cast arrays
  const downloads = Array.isArray(result?.["_awpt_download_link"])
    ? (result["_awpt_download_link"] as DownloadLink[])
    : [];
  const episodes = Array.isArray(result?.["_awpt_episodes"])
    ? (result["_awpt_episodes"] as Episode[])
    : [];
  const poster = str(result?.["_awpt_poster"]);
  const trailer = str(result?.["_awpt_trailer_url"]);
  const synopsis = str(result?.["_awpt_synopsis"]);

  return (
    <div className="space-y-6">
      {/* ── Input form ── */}
      <Card className="border-border">
        <CardContent className="pt-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* URL input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://naijaprey.tv/movie-title/"
                className="pl-10 h-11 text-sm bg-background"
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            {/* Source badge */}
            {url.trim() && (
              <div className="flex items-center gap-2 text-sm">
                {detected ? (
                  <>
                    <Badge variant="secondary" className="text-xs">
                      Detected: {detected.label}
                    </Badge>
                    <span className="text-muted-foreground text-xs">
                      Source recognised
                    </span>
                  </>
                ) : (
                  <Badge variant="destructive" className="text-xs">
                    Unsupported site
                  </Badge>
                )}
              </div>
            )}

            {/* Mode toggle */}
            <div className="flex gap-3">
              {(["movie", "series"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    mode === m
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {m === "movie" ? <Film className="w-4 h-4" /> : <Tv className="w-4 h-4" />}
                  {m === "movie" ? "Movie" : "Series"}
                </button>
              ))}
            </div>

            {/* Submit */}
            <Button
              type="submit"
              disabled={isPending || !detected}
              className="w-full h-11"
            >
              {isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Scraping… up to 35s
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  Scrape {mode === "movie" ? "Movie" : "Series"}
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* ── Error state ── */}
      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="pt-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-destructive">Scrape failed</p>
              <p className="text-xs text-muted-foreground mt-1">{error.message}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Result ── */}
      {result && !result["error"] && (
        <Card className="border-border overflow-hidden">
          {/* Poster + title row */}
          <div className="flex gap-0">
            {poster && (
              <div className="w-36 shrink-0 hidden sm:block">
                <img
                  src={poster}
                  alt="Poster"
                  className="w-full h-full object-cover"
                  style={{ maxHeight: 220 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            )}
            <div className="flex-1 p-6">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  {str(result["_awpt_type"]) && (
                    <Badge variant="outline" className="mb-2 text-xs uppercase tracking-wide">
                      {str(result["_awpt_type"])}
                    </Badge>
                  )}
                  <CardTitle className="text-xl leading-tight">
                    {str(result["_awpt_title"]) || "Untitled"}
                  </CardTitle>
                  {str(result["_awpt_status"]) && (
                    <span className="text-xs text-muted-foreground mt-1 block">
                      {str(result["_awpt_status"])}
                    </span>
                  )}
                </div>
                {/* JSON download */}
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  onClick={() => {
                    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
                    const a = document.createElement("a");
                    a.href = URL.createObjectURL(blob);
                    a.download = `${str(result["_awpt_title"]).replace(/[^a-z0-9 _-]/gi, "").trim() || "scrape"}.json`;
                    a.click();
                  }}
                >
                  <Download className="w-3.5 h-3.5 mr-1.5" />
                  JSON
                </Button>
              </div>

              {/* Synopsis */}
              {synopsis && (
                <p className="text-sm text-muted-foreground mt-3 leading-relaxed line-clamp-3">
                  {synopsis}
                </p>
              )}
            </div>
          </div>

          <Separator />

          {/* Metadata grid */}
          <CardContent className="pt-5 pb-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <MetaRow label="Genre" value={result["_awpt_genre"]} />
              <MetaRow label="Release" value={result["_awpt_release_date"]} />
              <MetaRow label="Country" value={result["_awpt_country"]} />
              <MetaRow label="Language" value={result["_awpt_language"]} />
              <MetaRow label="Ratings" value={result["_awpt_ratings"]} />
              <MetaRow label="Stars" value={result["_awpt_stars"]} />
              <MetaRow label="Duration" value={result["_awpt_duration"]} />
              <MetaRow label="File size" value={result["_awpt_file_size"]} />
              <MetaRow label="Season" value={result["_awpt_season"]} />
              <MetaRow label="Episodes" value={result["_awpt_total_episodes"]} />
              <MetaRow label="Source" value={result["_awpt_source"]} />
            </div>

            {/* Trailer */}
            {trailer && (
              <a
                href={trailer}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 mt-4 text-sm text-primary hover:underline"
              >
                <Play className="w-4 h-4" />
                Watch Trailer
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </CardContent>

          {/* Download links (movie) */}
          {downloads.length > 0 && (
            <>
              <Separator />
              <CardContent className="pt-4 pb-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Download className="w-4 h-4 text-primary" />
                  Download Links
                </h3>
                <div className="space-y-2">
                  {downloads.map((dl, i) => (
                    <a
                      key={i}
                      href={dl.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between px-3 py-2 rounded-lg border border-border bg-card hover:bg-accent/10 transition-colors group"
                    >
                      <span className="text-sm font-medium">{dl.quality || `Link ${i + 1}`}</span>
                      <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                    </a>
                  ))}
                </div>
              </CardContent>
            </>
          )}

          {/* Episode list (series) */}
          {episodes.length > 0 && (
            <>
              <Separator />
              <CardContent className="pt-4 pb-5">
                <button
                  type="button"
                  onClick={() => setShowEpisodes((v) => !v)}
                  className="flex items-center gap-2 text-sm font-semibold mb-3 hover:text-primary transition-colors w-full text-left"
                >
                  <Tv className="w-4 h-4 text-primary" />
                  {episodes.length} Episode{episodes.length > 1 ? "s" : ""}
                  {showEpisodes ? (
                    <ChevronUp className="w-4 h-4 ml-auto" />
                  ) : (
                    <ChevronDown className="w-4 h-4 ml-auto" />
                  )}
                </button>
                {showEpisodes && (
                  <div className="space-y-2 max-h-72 overflow-y-auto">
                    {episodes.map((ep) => (
                      <a
                        key={ep.episode}
                        href={ep.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between px-3 py-2 rounded-lg border border-border bg-card hover:bg-accent/10 transition-colors group"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-muted-foreground w-8 shrink-0">
                            Ep {ep.episode}
                          </span>
                          <span className="text-sm">{ep.title}</span>
                        </div>
                        <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                      </a>
                    ))}
                  </div>
                )}
              </CardContent>
            </>
          )}

          {/* Raw JSON toggle */}
          <Separator />
          <CardContent className="py-3">
            <button
              type="button"
              onClick={() => setShowJson((v) => !v)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
            >
              {showJson ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {showJson ? "Hide" : "View"} raw JSON
            </button>
            {showJson && (
              <pre className="mt-3 p-3 rounded-lg bg-muted text-xs overflow-auto max-h-72 whitespace-pre-wrap break-all">
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
