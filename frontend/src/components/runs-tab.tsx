import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCreateRun, useDatasets, useRuns, useVersions } from "../api/hooks";
import { formatCost, formatPercent, progressPercent } from "../lib/format";
import { Icon } from "./Icon";
import {
  Button,
  Card,
  Empty,
  ErrorBanner,
  Field,
  Loading,
  ProgressBar,
  ScoreBadge,
  Select,
  StatusBadge,
} from "./ui";

export function RunsTab({ projectId }: { projectId: number }) {
  const runs = useRuns(projectId);
  const versions = useVersions(projectId);
  const datasets = useDatasets(projectId);
  const create = useCreateRun(projectId);
  const navigate = useNavigate();
  const [versionId, setVersionId] = useState<number>(0);
  const [datasetId, setDatasetId] = useState<number>(0);
  const [selected, setSelected] = useState<number[]>([]);

  const vId = versionId || versions.data?.[0]?.id || 0;
  const dId = datasetId || datasets.data?.[0]?.id || 0;

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      { prompt_version_id: vId, dataset_id: dId },
      { onSuccess: (run) => navigate(`/runs/${run.id}`) },
    );
  }

  function toggle(id: number) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));
  }

  const [a, b] = [...selected].sort((x, y) => x - y);

  return (
    <div className="space-y-6">
      <Card title="Start a run">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <Field label="Prompt version">
            <Select
              value={vId}
              onChange={(e) => setVersionId(Number(e.target.value))}
              aria-label="Prompt version"
            >
              {versions.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Dataset">
            <Select
              value={dId}
              onChange={(e) => setDatasetId(Number(e.target.value))}
              aria-label="Dataset"
            >
              {datasets.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.case_count})
                </option>
              ))}
            </Select>
          </Field>
          <Button type="submit" disabled={!vId || !dId || create.isPending}>
            <Icon name="sparkle" className="h-4 w-4" />
            Run evaluation
          </Button>
        </form>
        <div className="mt-3">
          <ErrorBanner error={create.error} />
        </div>
      </Card>

      <Card
        title="Runs"
        actions={
          <Button
            variant="secondary"
            disabled={selected.length !== 2}
            onClick={() => navigate(`/compare?base=${a}&head=${b}`)}
            title="Select two runs on the same dataset"
          >
            Compare selected ({selected.length}/2)
          </Button>
        }
      >
        {runs.isLoading && <Loading />}
        <ErrorBanner error={runs.error} />
        {runs.data?.length === 0 && <Empty>No runs yet.</Empty>}
        {!!runs.data?.length && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm [&_td]:pr-4 [&_th]:whitespace-nowrap [&_th]:pr-4">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="w-8" />
                  <th className="py-2">Run</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Pass rate</th>
                  <th>Cost</th>
                  <th>Trigger</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {runs.data.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/70">
                    <td>
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
                        aria-label={`Select run ${r.id}`}
                        checked={selected.includes(r.id)}
                        onChange={() => toggle(r.id)}
                      />
                    </td>
                    <td className="py-2">
                      <Link
                        to={`/runs/${r.id}`}
                        className="font-semibold text-indigo-700 hover:underline"
                      >
                        #{r.id}
                      </Link>
                      {r.git_sha && (
                        <span className="ml-2 font-mono text-xs text-slate-400">
                          {r.git_sha.slice(0, 7)}
                        </span>
                      )}
                    </td>
                    <td>{r.prompt_label}</td>
                    <td className="w-40">
                      {r.status === "running" || r.status === "queued" ? (
                        <ProgressBar percent={progressPercent(r.progress.done, r.progress.total)} />
                      ) : (
                        <StatusBadge status={r.status} />
                      )}
                    </td>
                    <td>
                      <ScoreBadge value={r.summary?.pass_rate}>
                        {formatPercent(r.summary?.pass_rate)}
                      </ScoreBadge>
                    </td>
                    <td className="font-mono text-xs">{formatCost(r.cost_usd)}</td>
                    <td className="text-xs text-slate-500">{r.triggered_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
