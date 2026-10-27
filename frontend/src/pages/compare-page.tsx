import { useSearchParams } from "react-router-dom";
import { useCompare } from "../api/hooks";
import { CompareTable } from "../components/compare-table";
import { PageHeader } from "../components/layout";
import { Card, ErrorBanner, Loading, Stat } from "../components/ui";
import { compareVerdict } from "../lib/compare";
import { formatCost, formatDeltaPoints, formatPercent } from "../lib/format";

export function ComparePage() {
  const [params] = useSearchParams();
  const base = Number(params.get("base"));
  const head = Number(params.get("head"));
  const cmp = useCompare(base, head);

  if (cmp.isLoading) return <Loading />;
  if (cmp.error) return <ErrorBanner error={cmp.error} />;
  if (!cmp.data) return <ErrorBanner error="Pick two runs to compare." />;
  const d = cmp.data;
  const verdict = compareVerdict(d.counts, d.pass_rate_delta);
  const verdictClass = {
    good: "border-emerald-200 bg-emerald-50 text-emerald-800",
    bad: "border-red-200 bg-red-50 text-red-800",
    neutral: "border-slate-200 bg-white text-slate-700",
  }[verdict.tone];

  return (
    <>
      <PageHeader
        title={`Compare ${d.base.prompt_label} → ${d.head.prompt_label}`}
        subtitle={`Run #${d.base.id} (base) vs run #${d.head.id} (head) on the same dataset`}
        back={{ to: `/projects/${d.base.project_id}`, label: "Project" }}
      />
      <div
        className={`mb-6 rounded-2xl border px-4 py-3 text-sm font-medium ${verdictClass}`}
        data-testid="compare-verdict"
      >
        {verdict.text}
      </div>
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat
          label="Pass rate"
          value={`${formatPercent(d.base.summary?.pass_rate)} → ${formatPercent(d.head.summary?.pass_rate)}`}
          sub={formatDeltaPoints(d.pass_rate_delta)}
        />
        <Stat label="Regressed" value={d.counts.regressed} />
        <Stat label="Improved" value={d.counts.improved} sub={`${d.counts.unchanged} unchanged`} />
        <Stat
          label="Cost"
          value={`${formatCost(d.base.cost_usd)} → ${formatCost(d.head.cost_usd)}`}
          sub={
            d.cost_delta_pct === null
              ? undefined
              : `${d.cost_delta_pct > 0 ? "+" : ""}${d.cost_delta_pct}%`
          }
        />
      </div>
      <Card title="Cases">
        <CompareTable cases={d.cases} baseRunId={d.base.id} headRunId={d.head.id} />
      </Card>
    </>
  );
}
