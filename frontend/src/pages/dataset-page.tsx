import { useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useCases, useCreateCase, useDataset, useDeleteCase, useImportCases } from "../api/hooks";
import { PageHeader } from "../components/layout";
import {
  Badge,
  Button,
  Card,
  Empty,
  ErrorBanner,
  Field,
  Input,
  Loading,
  TextArea,
} from "../components/ui";

export function DatasetPage() {
  const datasetId = Number(useParams().datasetId);
  const projectId = useSearchParams()[0].get("project");
  const dataset = useDataset(datasetId);
  const cases = useCases(datasetId);
  const del = useDeleteCase(datasetId);

  return (
    <>
      <PageHeader
        title={dataset.data?.name ?? "Dataset"}
        subtitle={dataset.data ? `${dataset.data.case_count} test cases` : undefined}
        back={{
          to: projectId
            ? `/projects/${projectId}?tab=datasets`
            : dataset.data
              ? `/projects/${dataset.data.project_id}?tab=datasets`
              : "/",
          label: "Project",
        }}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card title="Test cases">
            {cases.isLoading && <Loading />}
            <ErrorBanner error={cases.error ?? del.error} />
            {cases.data?.length === 0 && <Empty>No cases yet. Import a file or add one.</Empty>}
            {!!cases.data?.length && (
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2">Inputs</th>
                    <th>Expected</th>
                    <th>Tags</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {cases.data.map((c) => (
                    <tr key={c.id} className="border-t border-slate-100 align-top">
                      <td className="py-2 pr-2">
                        <pre className="whitespace-pre-wrap text-xs">
                          {JSON.stringify(c.inputs, null, 1)}
                        </pre>
                      </td>
                      <td className="pr-2 text-xs">
                        {c.expected_output ?? <span className="text-slate-400">none</span>}
                      </td>
                      <td>
                        {c.tags.map((t) => (
                          <Badge key={t}>{t}</Badge>
                        ))}
                      </td>
                      <td>
                        <Button
                          variant="ghost"
                          onClick={() => del.mutate(c.id)}
                          aria-label={`Delete case ${c.id}`}
                        >
                          ✕
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
        <div className="space-y-6">
          <ImportCard datasetId={datasetId} />
          <AddCaseCard datasetId={datasetId} />
        </div>
      </div>
    </>
  );
}

function ImportCard({ datasetId }: { datasetId: number }) {
  const importer = useImportCases(datasetId);
  const [file, setFile] = useState<File | null>(null);
  return (
    <Card title="Import CSV / JSONL">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (file) importer.mutate(file);
        }}
        className="space-y-3"
      >
        <p className="text-xs text-slate-500">
          CSV: an <code>expected_output</code> column, optional <code>tags</code> (; separated),
          every other column is an input. JSONL:{" "}
          <code>{`{"inputs": {...}, "expected_output": "..."}`}</code> per line. Max 2 MB.
        </p>
        <input
          type="file"
          accept=".csv,.jsonl,.ndjson"
          aria-label="Dataset file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm"
        />
        <ErrorBanner error={importer.error} />
        <Button type="submit" disabled={!file || importer.isPending}>
          Import
        </Button>
        {importer.data && (
          <div className="text-sm" data-testid="import-report">
            <p className="text-emerald-700">Imported {importer.data.imported} case(s).</p>
            {importer.data.errors.map((err) => (
              <p key={err.row} className="text-rose-600">
                Row {err.row}: {err.message}
              </p>
            ))}
          </div>
        )}
      </form>
    </Card>
  );
}

function AddCaseCard({ datasetId }: { datasetId: number }) {
  const create = useCreateCase(datasetId);
  const [inputs, setInputs] = useState(
    '{\n  "customer": "Ana",\n  "question": "How do I get a refund?"\n}',
  );
  const [expected, setExpected] = useState("");
  const [tags, setTags] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(inputs) as Record<string, unknown>;
    } catch {
      setParseError("Inputs must be a JSON object");
      return;
    }
    setParseError(null);
    create.mutate({
      inputs: parsed,
      expected_output: expected || null,
      tags: tags
        .split(";")
        .map((t) => t.trim())
        .filter(Boolean),
    });
  }

  return (
    <Card title="Add a case">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Inputs (JSON)">
          <TextArea rows={4} value={inputs} onChange={(e) => setInputs(e.target.value)} />
        </Field>
        <Field label="Expected output">
          <Input value={expected} onChange={(e) => setExpected(e.target.value)} />
        </Field>
        <Field label="Tags" hint="; separated">
          <Input value={tags} onChange={(e) => setTags(e.target.value)} />
        </Field>
        <ErrorBanner error={parseError ?? create.error} />
        <Button type="submit" disabled={create.isPending}>
          Add case
        </Button>
      </form>
    </Card>
  );
}
