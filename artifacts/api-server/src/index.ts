import app from "./app";
import { logger } from "./lib/logger";
import { startTelegramBot } from "./telegram/bot";

const rawPort = process.env["PORT"];

if (!rawPort) {
  throw new Error(
    "PORT environment variable is required but was not provided.",
  );
}

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

app.listen(port, (err) => {
  if (err) {
    logger.error({ err }, "Error listening on port");
    process.exit(1);
  }

  logger.info({ port }, "Server listening");

  // Bug 1 fix: start Telegram bot only if token is set.
  // Guard prevents the missing-token error from crashing the HTTP server.
  if (process.env["TELEGRAM_BOT_TOKEN"]) {
    startTelegramBot();
  } else {
    logger.warn("TELEGRAM_BOT_TOKEN not set — Telegram bot will not start");
  }
});
