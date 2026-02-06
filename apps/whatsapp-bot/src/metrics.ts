/**
 * Prometheus-style counters for /metrics. All counters survive in process only.
 */

let sendsSuccessTotal = 0;
let sendsFailedTotal = 0;
let rateLimitedTotal = 0;
let disconnectsTotal = 0;

export function incSendsSuccess(): void {
  sendsSuccessTotal += 1;
}

export function incSendsFailed(): void {
  sendsFailedTotal += 1;
}

export function incRateLimited(): void {
  rateLimitedTotal += 1;
}

export function incDisconnects(): void {
  disconnectsTotal += 1;
}

export function getMetrics(): string {
  const lines = [
    "# HELP sends_success_total Number of successful send batches.",
    "# TYPE sends_success_total counter",
    `sends_success_total ${sendsSuccessTotal}`,
    "# HELP sends_failed_total Number of failed send batches.",
    "# TYPE sends_failed_total counter",
    `sends_failed_total ${sendsFailedTotal}`,
    "# HELP rate_limited_total Number of requests rejected by rate limit.",
    "# TYPE rate_limited_total counter",
    `rate_limited_total ${rateLimitedTotal}`,
    "# HELP disconnects_total Number of WhatsApp connection disconnects.",
    "# TYPE disconnects_total counter",
    `disconnects_total ${disconnectsTotal}`,
  ];
  return lines.join("\n") + "\n";
}
