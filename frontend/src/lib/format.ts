// Display formatting. Pure functions so they are trivial to unit test.

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Signed percentage-point change, e.g. +12.5 pp. Input is a 0..1 delta. */
export function formatDeltaPoints(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return "n/a";
  const pp = delta * 100;
  if (Math.abs(pp) < 0.05) return "±0 pp";
  return `${pp > 0 ? "+" : "−"}${Math.abs(pp).toFixed(1)} pp`;
}

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return "n/a";
  return score.toFixed(2);
}

export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return "n/a";
  if (usd === 0) return "$0";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "n/a";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

export function formatTokens(n: number | null | undefined): string {
  if (n === null || n === undefined) return "n/a";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/** Tailwind color class for a 0..1 score or pass rate. */
export function scoreTone(value: number | null | undefined): "good" | "warn" | "bad" | "none" {
  if (value === null || value === undefined) return "none";
  if (value >= 0.8) return "good";
  if (value >= 0.5) return "warn";
  return "bad";
}

export function progressPercent(done: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, Math.round((done / total) * 100));
}

/** One-line preview of a test case's inputs: "question: Where is…, customer: Ben". */
export function previewInputs(inputs: Record<string, unknown>, max = 80): string {
  const text = Object.entries(inputs)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}
