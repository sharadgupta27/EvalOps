import { Fragment, useState } from "react";
import { useParams } from "react-router-dom";
import { useResults, useRun } from "../api/hooks";
import { PageHeader } from "../components/layout";
import {
  Badge,
  Card,
  ErrorBanner,
  Loading,
  ProgressBar,
  ScoreBadge,
  Stat,
  StatusBadge,
} from "../components/ui";
import {
  formatCost,
  formatLatency,
  formatPercent,
  formatScore,
  formatTokens,
  previewInputs,
  progressPercent,
} from "../lib/format";

export function RunPage() {
  const runId = Number(useParams().runId);
  const run = useRun(runId);
  const finished = run.data?.status === "succeeded" || run.data?.status === "failed";
  const results = useResults(runId, finished);
  const [open, setOpen] = useState<number | null>(null);

  if (run.isLoading) return <Loading />;
  if (run.error) return <ErrorBanner error={run.error} />;
  if (!run.data) return null;
  const r = run.data;
  const s = r.summary;

  return (
    <>
      <PageHeader
        title={`Run #${r.id} · ${r.prompt_label}`}
        subtitle={`Triggered by ${r.triggered_by}${r.git_sha ? ` at ${r.git_sha.slice(0, 7)}` : ""}`}
        back={{ to: `/projects/${r.project_id}`, label: "Project" }}
        actions={<StatusBadge status={r.status} />}
      />
      {!finished && (
        <Card className="mb-6">
          <div className="mb-2 flex justify-between text-sm font-medium text-slate-600">
            <span>Evaluating cases…</span>
            <span>
              {r.progress.done}/{r.progress.total}
            </span>
          </div>
          <ProgressBar percent={progressPercent(r.progress.done, r.progress.total)} />
        </Card>
      )}
      {r.error && (
        <div className="mb-6">
          <ErrorBanner error={r.error} />
        </div>
      )}
      {s && (
        <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
          <Stat
            label="Pass rate"
            value={formatPercent(s.pass_rate)}
            sub={`${s.passed}/${s.total} passed, ${s.errored} errored`}
          />
          <Stat label="Mean score" value={formatScore(s.mean_score)} />
          <Stat
            label="Latency p50 / p95"
            value={formatLatency(s.latency_p50_ms)}
            sub={`p95 ${formatLatency(s.latency_p95_ms)}`}
          />
          <Stat label="Tokens" value={formatTokens(s.total_tokens)} />
          <Stat label="Cost" value={formatCost(s.cost_usd)} />
        </div>
      )}
      {s && Object.keys(s.mean_scores).length > 0 && (
        <Card title="Mean score per evaluator" className="mb-6">
          <div className="flex flex-wrap gap-3">
            {Object.entries(s.mean_scores).map(([name, v]) => (
              <ScoreBadge key={name} value={v}>
                {name}: {formatScore(v)}
              </ScoreBadge>
            ))}
          </div>
        </Card>
      )}
      {finished && (
        <Card title="Results">
          {results.isLoading && <Loading />}
          <ErrorBanner error={results.error} />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm [&_td]:pr-4 [&_th]:whitespace-nowrap [&_th]:pr-4">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2">Case</th>
                  <th>Result</th>
                  <th className="text-right">Score</th>
                  <th className="text-right">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.data?.map((res) => (
                  <Fragment key={res.id}>
                    <tr
                      className="cursor-pointer hover:bg-slate-50/70"
                      onClick={() => setOpen(open === res.id ? null : res.id)}
                    >
                      <td className="py-2 pr-2">
                        #{res.test_case_id} {previewInputs(res.inputs, 70)}
                      </td>
                      <td>
                        {res.error ? (
                          <Badge tone="warn">error</Badge>
                        ) : res.passed ? (
                          <Badge tone="good">pass</Badge>
                        ) : (
                          <Badge tone="bad">fail</Badge>
                        )}
                      </td>
                      <td className="text-right font-mono">{formatScore(res.score)}</td>
                      <td className="text-right font-mono text-xs">
                        {formatLatency(res.latency_ms)}
                      </td>
                    </tr>
                    {open === res.id && (
                      <tr className="bg-slate-50/70">
                        <td colSpan={4} className="space-y-2 p-4 text-xs">
                          {res.error && <ErrorBanner error={res.error} />}
                          <div>
                            <span className="font-semibold text-slate-500">Output</span>
                            <pre className="mt-1 whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-3">
                              {res.output ?? "(none)"}
                            </pre>
                          </div>
                          <ul className="space-y-1">
                            {res.scores.map((sc) => (
                              <li key={sc.evaluator}>
                                <Badge tone={sc.passed ? "good" : "bad"}>{sc.evaluator}</Badge>{" "}
                                <span className="text-slate-600">{sc.reason}</span>
                              </li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
