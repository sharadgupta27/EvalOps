import { useState, type FormEvent } from "react";
import { useCreateVersion, useVersions } from "../api/hooks";
import { Badge, Button, Card, Empty, ErrorBanner, Field, Input, Loading, TextArea } from "./ui";

const EXAMPLE = `You are a polite, friendly support agent.
Reply in JSON with a single field "answer".
Customer {{customer}} asks:
{{question}}`;

export function VersionsTab({ projectId }: { projectId: number }) {
  const versions = useVersions(projectId);
  const create = useCreateVersion(projectId);
  const [label, setLabel] = useState("");
  const [template, setTemplate] = useState(EXAMPLE);
  const [model, setModel] = useState("");
  const [system, setSystem] = useState("");
  const [maxTokens, setMaxTokens] = useState(2048);

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        label,
        template,
        model: model || undefined,
        params: { max_tokens: maxTokens, system, temperature: null },
      },
      { onSuccess: () => setLabel("") },
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="space-y-3 lg:col-span-3">
        {versions.isLoading && <Loading />}
        <ErrorBanner error={versions.error} />
        {versions.data?.length === 0 && <Empty>No prompt versions yet.</Empty>}
        {versions.data?.map((v) => (
          <Card
            key={v.id}
            title={
              <span className="flex items-center gap-2">
                {v.label} <Badge>{v.model}</Badge>
              </span>
            }
            actions={
              <span className="text-xs text-slate-400">
                {new Date(v.created_at).toLocaleString()}
              </span>
            }
          >
            <pre className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-xs">
              {v.template}
            </pre>
            <div className="mt-2 flex flex-wrap gap-1 text-xs text-slate-500">
              variables:
              {v.variables.map((name) => (
                <Badge key={name} tone="info">
                  {name}
                </Badge>
              ))}
            </div>
          </Card>
        ))}
      </div>
      <div className="lg:col-span-2">
        <Card title="New version">
          <p className="mb-3 text-xs text-slate-500">
            Versions are immutable: to change a prompt, save a new version and compare runs.
          </p>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Label" hint="Letters, digits, . _ - (e.g. v2 or v2-shorter)">
              <Input
                required
                pattern="[A-Za-z0-9._\-]+"
                maxLength={40}
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </Field>
            <Field label="Template" hint="Use {{variable}} for test-case inputs.">
              <TextArea
                required
                rows={7}
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
              />
            </Field>
            <Field label="System prompt (optional)">
              <TextArea rows={2} value={system} onChange={(e) => setSystem(e.target.value)} />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Model" hint="Blank = server default">
                <Input value={model} onChange={(e) => setModel(e.target.value)} />
              </Field>
              <Field label="Max tokens">
                <Input
                  type="number"
                  min={1}
                  max={32000}
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                />
              </Field>
            </div>
            <ErrorBanner error={create.error} />
            <Button type="submit" disabled={create.isPending}>
              Save version
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
