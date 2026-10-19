// Client-side logic for the Compare view: filtering, sorting and the headline verdict.
import type { Schemas } from "../api/client";

export type CompareCase = Schemas["CompareCase"];
export type Bucket = Schemas["CompareBucket"];
export type BucketFilter = Bucket | "all" | "changed";

export const BUCKET_ORDER: Bucket[] = ["regressed", "improved", "added", "removed", "unchanged"];

export function filterCases(
  cases: CompareCase[],
  filter: BucketFilter,
  search = "",
): CompareCase[] {
  const needle = search.trim().toLowerCase();
  return cases.filter((c) => {
    if (filter === "changed" && c.bucket === "unchanged") return false;
    if (filter !== "all" && filter !== "changed" && c.bucket !== filter) return false;
    if (!needle) return true;
    const haystack = [
      JSON.stringify(c.inputs),
      c.expected_output ?? "",
      c.base_output ?? "",
      c.head_output ?? "",
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

/** Worst first: bucket order, then the largest score drop. */
export function sortCases(cases: CompareCase[]): CompareCase[] {
  return [...cases].sort((a, b) => {
    const byBucket = BUCKET_ORDER.indexOf(a.bucket) - BUCKET_ORDER.indexOf(b.bucket);
    if (byBucket !== 0) return byBucket;
    return (a.delta ?? 0) - (b.delta ?? 0) || a.test_case_id - b.test_case_id;
  });
}

export type Verdict = { tone: "good" | "bad" | "neutral"; text: string };

export function compareVerdict(counts: Schemas["CompareCounts"], passRateDelta: number): Verdict {
  if (counts.regressed > 0) {
    const s = counts.regressed === 1 ? "" : "s";
    return { tone: "bad", text: `${counts.regressed} case${s} regressed` };
  }
  if (counts.improved > 0 || passRateDelta > 0) {
    return { tone: "good", text: `No regressions, ${counts.improved} improved` };
  }
  return { tone: "neutral", text: "No change between runs" };
}

/**
 * A minimal word-level diff for side-by-side outputs: marks words in `head` that are not in
 * `base`. Good enough to make changed wording jump out without pulling in a diff library.
 */
export function highlightNewWords(base: string, head: string): { text: string; added: boolean }[] {
  const baseWords = new Set(base.toLowerCase().split(/\s+/).filter(Boolean));
  return head
    .split(/(\s+)/)
    .filter((part) => part !== "")
    .map((part) => ({
      text: part,
      added: !/^\s+$/.test(part) && !baseWords.has(part.toLowerCase()),
    }));
}

const CSV_COLUMNS: { header: string; value: (c: CompareCase) => unknown }[] = [
  { header: "test_case_id", value: (c) => c.test_case_id },
  { header: "bucket", value: (c) => c.bucket },
  { header: "base_passed", value: (c) => c.base_passed },
  { header: "head_passed", value: (c) => c.head_passed },
  { header: "base_score", value: (c) => c.base_score },
  { header: "head_score", value: (c) => c.head_score },
  { header: "delta", value: (c) => c.delta },
  { header: "inputs", value: (c) => JSON.stringify(c.inputs) },
  { header: "expected_output", value: (c) => c.expected_output },
  { header: "base_output", value: (c) => c.base_output },
  { header: "head_output", value: (c) => c.head_output },
];

/**
 * One CSV cell. Text cells are untrusted (inputs and model outputs), so a leading formula
 * trigger gets a `'` prefix to stop spreadsheets from evaluating it. Numbers we produce
 * ourselves (e.g. a negative delta) are left alone so they stay numeric.
 */
export function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  let text = String(value);
  if (typeof value === "string" && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** RFC 4180 CSV of compare cases, in the order given, with CRLF line endings. */
export function compareCasesToCsv(cases: CompareCase[]): string {
  const rows = [
    CSV_COLUMNS.map((col) => col.header),
    ...cases.map((c) => CSV_COLUMNS.map((col) => csvCell(col.value(c)))),
  ];
  return rows.map((r) => r.join(",")).join("\r\n") + "\r\n";
}
