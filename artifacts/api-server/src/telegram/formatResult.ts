function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function field(label: string, value: unknown): string | null {
  if (value === undefined || value === null) return null;
  const str = String(value).trim();
  if (!str) return null;
  return `<b>${escapeHtml(label)}:</b> ${escapeHtml(str)}`;
}

export function formatSummary(result: Record<string, unknown>): string {
  const lines: string[] = [];

  const title = result["_awpt_title"];
  lines.push(`🎬 <b>${escapeHtml(String(title ?? "Untitled"))}</b>`);
  lines.push("");

  const synopsis = result["_awpt_synopsis"];
  if (typeof synopsis === "string" && synopsis.trim()) {
    const trimmed =
      synopsis.length > 600 ? `${synopsis.slice(0, 600)}…` : synopsis;
    lines.push(escapeHtml(trimmed));
    lines.push("");
  }

  const rows = [
    field("Type", result["_awpt_type"]),
    field("Status", result["_awpt_status"]),
    field("Genre", result["_awpt_genre"]),
    field("Release", result["_awpt_release_date"]),
    field("Country", result["_awpt_country"]),
    field("Rating", result["_awpt_ratings"]),
    field("Language", result["_awpt_language"]),
    field("Stars", result["_awpt_stars"]),
    field("File size", result["_awpt_file_size"]),
    field("Total episodes", result["_awpt_total_episodes"]),
    field("Season", result["_awpt_season"]),
    field("Source", result["_awpt_source"]),
  ].filter((line): line is string => line !== null);

  lines.push(...rows);

  const trailer = result["_awpt_trailer_url"];
  if (typeof trailer === "string" && trailer.trim()) {
    lines.push("");
    lines.push(`🎞️ <a href="${escapeHtml(trailer)}">Trailer</a>`);
  }

  return lines.join("\n");
}

export function getPosterUrl(result: Record<string, unknown>): string | null {
  const poster = result["_awpt_poster"];
  return typeof poster === "string" && /^https?:\/\//.test(poster)
    ? poster
    : null;
}

const TELEGRAM_MESSAGE_LIMIT = 4096;

export function chunkForTelegram(text: string, limit = TELEGRAM_MESSAGE_LIMIT): string[] {
  if (text.length <= limit) return [text];
  const chunks: string[] = [];
  let remaining = text;
  while (remaining.length > 0) {
    chunks.push(remaining.slice(0, limit));
    remaining = remaining.slice(limit);
  }
  return chunks;
}
