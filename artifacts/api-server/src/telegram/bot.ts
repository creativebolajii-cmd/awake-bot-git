import { Telegraf, Markup } from "telegraf";
import { runScrape } from "../lib/pythonRuntime";
import { logger } from "../lib/logger";
import { detectSource } from "./detectSource";
import { pendingScrapes, scrapeResults } from "./store";
import { chunkForTelegram, formatSummary, getPosterUrl } from "./formatResult";

const SUPPORTED_SITES_HELP =
  "Supported sites:\n" +
  "• 9jarocks (9jarocks.com)\n" +
  "• NaijaPrey (naijaprey.tv)\n" +
  "• Nkiri / Dramakey (nkiri.com / dramakey.com)";

function extractUrl(text: string): string | null {
  const match = text.match(/https?:\/\/\S+/i);
  return match ? match[0] : null;
}

export function startTelegramBot(): Telegraf {
  const token = process.env["TELEGRAM_BOT_TOKEN"];
  if (!token) {
    throw new Error("TELEGRAM_BOT_TOKEN is required to start the Telegram bot");
  }

  const bot = new Telegraf(token);

  bot.start((ctx) => {
    ctx.reply(
      "🎬 <b>AwakeMovies Scraper Bot</b>\n\n" +
        "Send me a link with:\n" +
        "<code>/scrape &lt;url&gt;</code>\n\n" +
        SUPPORTED_SITES_HELP,
      { parse_mode: "HTML" },
    );
  });

  bot.command("scrape", async (ctx) => {
    const url = extractUrl(ctx.message.text);
    if (!url) {
      await ctx.reply("Please provide a URL, e.g. /scrape https://naijaprey.tv/some-title/");
      return;
    }

    const detected = detectSource(url);
    if (!detected) {
      await ctx.reply(`Couldn't recognize that site.\n\n${SUPPORTED_SITES_HELP}`);
      return;
    }

    const pendingId = pendingScrapes.put({
      source: detected.source,
      url,
      site: detected.site,
    });

    await ctx.reply(
      `Detected source: <b>${detected.source}</b>\nIs this a movie or a series?`,
      {
        parse_mode: "HTML",
        ...Markup.inlineKeyboard([
          Markup.button.callback("🎬 Movie", `mode:${pendingId}:movie`),
          Markup.button.callback("📺 Series", `mode:${pendingId}:series`),
        ]),
      },
    );
  });

  bot.action(/^mode:([a-f0-9]+):(movie|series)$/, async (ctx) => {
    const [, pendingId, mode] = ctx.match;
    const pending = pendingScrapes.get(pendingId);
    if (!pending) {
      await ctx.answerCbQuery("This request expired, please /scrape again.");
      return;
    }

    await ctx.answerCbQuery();
    await ctx.editMessageText(`⏳ Scraping (${mode})… this can take up to 35s.`);

    try {
      const result = await runScrape({
        source: pending.source,
        url: pending.url,
        mode: mode as "movie" | "series",
        site: pending.site,
      });

      if (result["error"]) {
        await ctx.reply(`❌ Scrape failed: ${String(result["error"])}`);
        return;
      }

      const resultId = scrapeResults.put(result);
      const summary = formatSummary(result);
      const poster = getPosterUrl(result);
      const keyboard = Markup.inlineKeyboard([
        [
          Markup.button.callback("📄 View Full JSON", `json:${resultId}`),
          Markup.button.callback("📋 Copy JSON", `copy:${resultId}`),
        ],
        [Markup.button.callback("⬇️ Download JSON File", `dl:${resultId}`)],
      ]);

      if (poster) {
        await ctx.replyWithPhoto(
          { url: poster },
          { caption: summary, parse_mode: "HTML", ...keyboard },
        );
      } else {
        await ctx.reply(summary, { parse_mode: "HTML", ...keyboard });
      }
    } catch (err) {
      logger.error({ err }, "telegram scrape failed");
      await ctx.reply("❌ Scrape failed unexpectedly. Please try again.");
    }
  });

  bot.action(/^json:([a-f0-9]+)$/, async (ctx) => {
    const [, resultId] = ctx.match;
    const result = scrapeResults.get(resultId);
    if (!result) {
      await ctx.answerCbQuery("This result expired, please /scrape again.");
      return;
    }
    await ctx.answerCbQuery();
    const pretty = JSON.stringify(result, null, 2);
    for (const chunk of chunkForTelegram(`<pre>${escapeHtmlBlock(pretty)}</pre>`, 4000)) {
      await ctx.reply(chunk, { parse_mode: "HTML" });
    }
  });

  bot.action(/^copy:([a-f0-9]+)$/, async (ctx) => {
    const [, resultId] = ctx.match;
    const result = scrapeResults.get(resultId);
    if (!result) {
      await ctx.answerCbQuery("This result expired, please /scrape again.");
      return;
    }
    await ctx.answerCbQuery();
    const compact = JSON.stringify(result);
    for (const chunk of chunkForTelegram(compact, 4000)) {
      await ctx.reply(`<code>${escapeHtmlBlock(chunk)}</code>`, { parse_mode: "HTML" });
    }
  });

  bot.action(/^dl:([a-f0-9]+)$/, async (ctx) => {
    const [, resultId] = ctx.match;
    const result = scrapeResults.get(resultId);
    if (!result) {
      await ctx.answerCbQuery("This result expired, please /scrape again.");
      return;
    }
    await ctx.answerCbQuery();
    const title =
      typeof result["_awpt_title"] === "string" && result["_awpt_title"]
        ? String(result["_awpt_title"]).replace(/[^a-z0-9 _-]/gi, "").trim() || "scrape"
        : "scrape";
    const json = JSON.stringify(result, null, 2);
    await ctx.replyWithDocument({
      source: Buffer.from(json, "utf-8"),
      filename: `${title}.json`,
    });
  });

  bot.catch((err, ctx) => {
    logger.error({ err, updateType: ctx.updateType }, "telegram bot error");
  });

  bot
    .launch()
    .then(() => logger.info("Telegram bot started (polling)"))
    .catch((err) => logger.error({ err }, "Failed to launch Telegram bot"));

  return bot;
}

function escapeHtmlBlock(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
