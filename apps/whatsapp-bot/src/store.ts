/**
 * Session store path and helpers. Baileys auth state is file-based via useMultiFileAuthState.
 * This module exposes the auth folder for wa.ts and ensures the directory exists.
 */

import { mkdir } from "fs/promises";
import { join } from "path";
import { env } from "./env.js";
import { logger } from "./logger.js";

export function getAuthFolder(): string {
  return env.AUTH_FOLDER;
}

/** Ensure auth folder exists (called at startup). */
export async function ensureAuthFolder(): Promise<string> {
  const folder = getAuthFolder();
  try {
    await mkdir(folder, { recursive: true });
    logger.debug("Auth folder ready", { folder });
  } catch (e) {
    logger.error("Failed to create auth folder", { folder, err: String(e) });
    throw e;
  }
  return folder;
}

const SESSIONS_BASE = process.env.WA_SESSIONS_BASE ?? "/data/wa_sessions";

/** Ensure session folder exists for a user (e.g. /data/wa_sessions/user_123). */
export async function ensureUserSessionFolder(userId: number): Promise<string> {
  const folder = join(SESSIONS_BASE, `user_${userId}`);
  try {
    await mkdir(folder, { recursive: true });
    logger.debug("User session folder ready", { userId, folder });
  } catch (e) {
    logger.error("Failed to create user session folder", { userId, folder, err: String(e) });
    throw e;
  }
  return folder;
}
