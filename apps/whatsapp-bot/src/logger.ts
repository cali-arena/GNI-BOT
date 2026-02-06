/**
 * Structured logger with optional correlation context (item_id, template, channel, attempt, error_code).
 */

type LogLevel = "debug" | "info" | "warn" | "error";

export type LogContext = {
  correlation_id?: string;
  item_id?: number | string;
  template?: string;
  channel?: string;
  attempt?: number;
  error_code?: string;
  [key: string]: unknown;
};

const LOG_LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const minLevel: LogLevel = (process.env.LOG_LEVEL as LogLevel) || "info";

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVEL_ORDER[level] >= LOG_LEVEL_ORDER[minLevel];
}

function mergeData(ctx: LogContext | undefined, data?: object): object {
  if (!ctx && !data) return {};
  return { ...ctx, ...(data || {}) };
}

function format(level: string, msg: string, data?: object): string {
  const ts = new Date().toISOString();
  const extra = data && Object.keys(data).length > 0 ? ` ${JSON.stringify(data)}` : "";
  return `${ts} [${level.toUpperCase()}] ${msg}${extra}`;
}

function logWith(ctx: LogContext | undefined) {
  return {
    debug(msg: string, data?: object): void {
      if (shouldLog("debug")) console.debug(format("debug", msg, mergeData(ctx, data)));
    },
    info(msg: string, data?: object): void {
      if (shouldLog("info")) console.log(format("info", msg, mergeData(ctx, data)));
    },
    warn(msg: string, data?: object): void {
      if (shouldLog("warn")) console.warn(format("warn", msg, mergeData(ctx, data)));
    },
    error(msg: string, data?: object): void {
      if (shouldLog("error")) console.error(format("error", msg, mergeData(ctx, data)));
    },
  };
}

export const logger = logWith(undefined);

/** Return a logger that includes the given context in every log line. */
export function withContext(ctx: LogContext): ReturnType<typeof logWith> {
  return logWith(ctx);
}
