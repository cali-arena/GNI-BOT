/**
 * WhatsApp Bot service: QR-based session + internal HTTP endpoint to send messages to a group.
 * Env: AUTH_FOLDER, PORT, WA_TARGET_GROUP_JID / WA_TARGET_GROUP_NAME, WA_ADMIN_NUMBER, etc.
 *
 * CLI: node dist/index.js --print-groups  → print group names + JIDs then exit.
 */

import { logger } from "./logger.js";
import { ensureAuthFolder } from "./store.js";
import { fetchAllGroupsList, getSocket, readyPromise, startWa } from "./wa.js";
import { startWebhookServer } from "./webhook.js";

async function printGroups(): Promise<void> {
  await ensureAuthFolder();
  await startWa();
  await readyPromise;
  const wa = getSocket();
  if (!wa) {
    logger.error("Not connected");
    process.exit(1);
  }
  const groups = await fetchAllGroupsList(wa);
  console.log("Group name\tGroup JID");
  console.log("----------\t---------");
  for (const { name, jid } of groups) {
    console.log(`${name}\t${jid}`);
  }
  process.exit(0);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.includes("--print-groups")) {
    await printGroups();
    return;
  }

  logger.info("Starting whatsapp-bot");
  await ensureAuthFolder();
  startWebhookServer();
  await startWa();
}

main().catch((e) => {
  logger.error("Fatal error", { err: String(e) });
  process.exit(1);
});
