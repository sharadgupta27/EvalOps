import { Fragment, useMemo, useState } from "react";
import {
  compareCasesToCsv,
  filterCases,
  highlightNewWords,
  sortCases,
  type BucketFilter,
  type CompareCase,
} from "../lib/compare";
import { formatScore, previewInputs } from "../lib/format";
import { Badge, Button, Empty, Input } from "./ui";

const BUCKET_TONE = {
  regressed: "bad",
  improved: "good",
  unchanged: "none",
  added: "info",
  removed: "warn",
} as const;

const FILTERS: { value: BucketFilter; label: string }[] = [
  { value: "changed", label: "Changed" },
  { value: "regressed", label: "Regressed" },
  { value: "improved", label: "Improved" },
  { value: "all", label: "All" },
];

function downloadCsv(csv: string, filename: string) {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function CompareTable({
  cases,
  baseRunId,
  headRunId,
}: {
  cases: CompareCase[];
  baseRunId?: number;
  headRunId?: number;
}) {
  const [filter, setFilter] = useState<BucketFilter>("changed");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const visible = useMemo(
    () => sortCases(filterCases(cases, filter, search)),
    [cases, filter, search],
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div role="tablist" className="flex rounded-md ring-1 ring-slate-200">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              role="tab"
              aria-selected={filter === f.value}
              onClick={() => setFilter(f.value)}
              className={`px-3 py-1 text-sm first:rounded-l-md last:rounded-r-md ${
                filter === f.value
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <Input
          placeholder="Search inputs and outputs…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
          aria-label="Search cases"
        />
        <span className="text-xs text-slate-500">{visible.length} case(s)</span>
        <Button
          variant="secondary"
          className="ml-auto"
          disabled={visible.length === 0}
          onClick={() =>
            downloadCsv(
              compareCasesToCsv(visible),
              baseRunId !== undefined && headRunId !== undefined
                ? `compare-run-${baseRunId}-vs-${headRunId}.csv`
                : "compare.csv",
            )
          }
        >
          Export CSV
        </Button>
      </div>
      {visible.length === 0 ? (
        <Empty>No cases match this filter.</Empty>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Case</th>
              <th>Change</th>
              <th className="text-right">Base</th>
              <th className="text-right">Head</th>
              <th className="text-right">Δ</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((c) => (
              <Fragment key={c.test_case_id}>
                <tr
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                  onClick={() => setOpen(open === c.test_case_id ? null : c.test_case_id)}
                  data-testid={`compare-row-${c.test_case_id}`}
                >
                  <td className="py-2 pr-2 text-slate-700">
                    #{c.test_case_id} {previewInputs(c.inputs, 70)}
                  </td>
                  <td>
                    <Badge tone={BUCKET_TONE[c.bucket]}>{c.bucket}</Badge>
                  </td>
                  <td className="text-right font-mono">
                    {passMark(c.base_passed)} {formatScore(c.base_score)}
                  </td>
                  <td className="text-right font-mono">
                    {passMark(c.head_passed)} {formatScore(c.head_score)}
                  </td>
                  <td
                    className={`text-right font-mono ${(c.delta ?? 0) < 0 ? "text-rose-600" : "text-emerald-600"}`}
                  >
                    {c.delta === null ? "n/a" : `${c.delta > 0 ? "+" : ""}${c.delta.toFixed(2)}`}
                  </td>
                </tr>
                {open === c.test_case_id && (
                  <tr className="bg-slate-50">
                    <td colSpan={5} className="p-3">
                      <OutputDiff c={c} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const passMark = (p: boolean | null) => (p === null ? "" : p ? "✓" : "✗");

function OutputDiff({ c }: { c: CompareCase }) {
  return (
    <div className="space-y-2">
      {c.expected_output && (
        <p className="text-xs text-slate-500">
          Expected: <span className="font-mono text-slate-700">{c.expected_output}</span>
        </p>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <div className="mb-1 text-xs font-semibold text-slate-500">Base output</div>
          <pre className="whitespace-pre-wrap rounded-sm bg-white p-2 text-xs ring-1 ring-slate-200">
            {c.base_output ?? "(none)"}
          </pre>
        </div>
        <div>
          <div className="mb-1 text-xs font-semibold text-slate-500">
            Head output (new words highlighted)
          </div>
          <pre className="whitespace-pre-wrap rounded-sm bg-white p-2 text-xs ring-1 ring-slate-200">
            {c.head_output === null
              ? "(none)"
              : highlightNewWords(c.base_output ?? "", c.head_output).map((w, i) =>
                  w.added ? (
                    <mark key={i} className="bg-amber-100">
                      {w.text}
                    </mark>
                  ) : (
                    <span key={i}>{w.text}</span>
                  ),
                )}
          </pre>
        </div>
      </div>
    </div>
  );
}
