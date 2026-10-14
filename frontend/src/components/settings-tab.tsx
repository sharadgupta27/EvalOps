import { useEffect, useState, type FormEvent } from "react";
import type { Schemas } from "../api/client";
import {
  useApiKeys,
  useCreateApiKey,
  useGatePolicy,
  useRevokeApiKey,
  useSaveGatePolicy,
} from "../api/hooks";
import { Badge, Button, Card, ErrorBanner, Field, Input, Loading } from "./ui";

export function SettingsTab({ projectId }: { projectId: number }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <GatePolicyCard projectId={projectId} />
      <ApiKeysCard projectId={projectId} />
    </div>
  );
}

function GatePolicyCard({ projectId }: { projectId: number }) {
  const policy = useGatePolicy(projectId);
  const save = useSaveGatePolicy(projectId);
  const [form, setForm] = useState<Schemas["GatePolicy"] | null>(null);
  useEffect(() => {
    if (policy.data) setForm(policy.data);
  }, [policy.data]);

  if (!form)
    return (
      <Card title="CI gate policy">
        {policy.isLoading ? <Loading /> : <ErrorBanner error={policy.error} />}
      </Card>
    );

  function submit(e: FormEvent) {
    e.preventDefault();
    if (form) save.mutate(form);
  }

  return (
    <Card title="CI gate policy">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Minimum pass rate (%)">
          <Input
            type="number"
            min={0}
            max={100}
            value={Math.round(form.min_pass_rate * 100)}
            onChange={(e) => setForm({ ...form, min_pass_rate: Number(e.target.value) / 100 })}
          />
        </Field>
        <Field label="Max regressed cases vs baseline">
          <Input
            type="number"
            min={0}
            value={form.max_regressions}
            onChange={(e) => setForm({ ...form, max_regressions: Number(e.target.value) })}
          />
        </Field>
        <Field label="Max cost increase (%)">
          <Input
            type="number"
            min={0}
            value={form.max_cost_increase_pct}
            onChange={(e) => setForm({ ...form, max_cost_increase_pct: Number(e.target.value) })}
          />
        </Field>
        <ErrorBanner error={save.error} />
        <Button type="submit" disabled={save.isPending}>
          Save policy
        </Button>
        {save.isSuccess && <span className="ml-2 text-sm text-emerald-600">Saved</span>}
      </form>
    </Card>
  );
}

function ApiKeysCard({ projectId }: { projectId: number }) {
  const keys = useApiKeys(projectId);
  const create = useCreateApiKey(projectId);
  const revoke = useRevokeApiKey(projectId);
  const [name, setName] = useState("ci");

  return (
    <Card title="API keys (for CI, MCP and agents)">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ name });
        }}
        className="mb-4 flex gap-2"
      >
        <Input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Key name"
        />
        <Button type="submit" disabled={create.isPending}>
          Create key
        </Button>
      </form>
      {create.data && (
        <div className="mb-4 rounded-md bg-amber-50 p-3 text-sm ring-1 ring-amber-200">
          <p className="font-medium text-amber-800">
            Copy this key now. It will not be shown again.
          </p>
          <code className="mt-1 block break-all font-mono text-xs" data-testid="new-api-key">
            {create.data.key}
          </code>
        </div>
      )}
      <ErrorBanner error={keys.error ?? create.error ?? revoke.error} />
      <ul className="divide-y divide-slate-100 text-sm">
        {keys.data?.map((k) => (
          <li key={k.id} className="flex items-center justify-between py-2">
            <span>
              {k.name} <code className="text-xs text-slate-500">{k.prefix}…</code>{" "}
              {k.revoked_at && <Badge tone="bad">revoked</Badge>}
            </span>
            {!k.revoked_at && (
              <Button variant="ghost" onClick={() => revoke.mutate(k.id)}>
                Revoke
              </Button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
