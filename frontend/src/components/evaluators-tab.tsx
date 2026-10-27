import { useState, type FormEvent } from "react";
import type { Schemas } from "../api/client";
import { useCreateEvaluator, useDeleteEvaluator, useEvaluators } from "../api/hooks";
import {
  Badge,
  Button,
  Card,
  Empty,
  ErrorBanner,
  Field,
  Input,
  Loading,
  Select,
  TextArea,
} from "./ui";

type EvalType = Schemas["EvaluatorType"];

// Starter configs shown when a type is picked; the server validates whatever is submitted.
export const CONFIG_TEMPLATES: Record<EvalType, string> = {
  exact_match: JSON.stringify({ case_sensitive: false, strip: true }, null, 2),
  contains: JSON.stringify({ case_sensitive: false }, null, 2),
  regex: JSON.stringify({ pattern: "^\\{.*\\}$" }, null, 2),
  json_schema: JSON.stringify(
    {
      schema: { type: "object", required: ["answer"], properties: { answer: { type: "string" } } },
    },
    null,
    2,
  ),
  llm_judge: JSON.stringify({ rubric: "Is the reply polite and correct?", threshold: 4 }, null, 2),
};

const DESCRIPTIONS: Record<EvalType, string> = {
  exact_match: "Output equals the expected output.",
  contains: "Output contains a value (defaults to the expected output).",
  regex: "Output matches a regular expression.",
  json_schema: "Output is JSON that validates against a JSON Schema.",
  llm_judge: "An LLM scores the output 1–5 against a rubric.",
};

export function EvaluatorsTab({ projectId }: { projectId: number }) {
  const evaluators = useEvaluators(projectId);
  const create = useCreateEvaluator(projectId);
  const del = useDeleteEvaluator(projectId);
  const [type, setType] = useState<EvalType>("contains");
  const [name, setName] = useState("");
  const [weight, setWeight] = useState(1);
  const [config, setConfig] = useState(CONFIG_TEMPLATES.contains);
  const [parseError, setParseError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    let parsed: Record<string, unknown>;
    try {
      parsed = config.trim() ? (JSON.parse(config) as Record<string, unknown>) : {};
    } catch {
      setParseError("Config must be valid JSON");
      return;
    }
    setParseError(null);
    create.mutate({ type, name, weight, config: parsed }, { onSuccess: () => setName("") });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <Card
          title="Evaluators"
          actions={
            <span className="text-xs text-slate-500">
              A case passes when every evaluator passes.
            </span>
          }
        >
          {evaluators.isLoading && <Loading />}
          <ErrorBanner error={evaluators.error ?? del.error} />
          {evaluators.data?.length === 0 && (
            <Empty>No evaluators yet. Runs need at least one.</Empty>
          )}
          <ul className="space-y-2">
            {evaluators.data?.map((ev) => (
              <li
                key={ev.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
                    {ev.name} <Badge tone="info">{ev.type}</Badge> <Badge>weight {ev.weight}</Badge>
                  </div>
                  <pre className="mt-1 overflow-x-auto font-mono text-xs text-slate-500">
                    {JSON.stringify(ev.config)}
                  </pre>
                </div>
                <Button
                  variant="ghost"
                  onClick={() => del.mutate(ev.id)}
                  aria-label={`Delete ${ev.name}`}
                >
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <div className="lg:col-span-2">
        <Card title="Add evaluator">
          <form onSubmit={submit} className="space-y-3">
            <Field label="Type" hint={DESCRIPTIONS[type]}>
              <Select
                value={type}
                onChange={(e) => {
                  const t = e.target.value as EvalType;
                  setType(t);
                  setConfig(CONFIG_TEMPLATES[t]);
                }}
              >
                {Object.keys(CONFIG_TEMPLATES).map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </Select>
            </Field>
            <Field label="Name">
              <Input
                required
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <Field label="Weight" hint="How much this evaluator counts in the case score.">
              <Input
                type="number"
                min={0.1}
                step={0.1}
                value={weight}
                onChange={(e) => setWeight(Number(e.target.value))}
              />
            </Field>
            <Field label="Config (JSON)">
              <TextArea rows={6} value={config} onChange={(e) => setConfig(e.target.value)} />
            </Field>
            <ErrorBanner error={parseError ?? create.error} />
            <Button type="submit" disabled={create.isPending}>
              Add evaluator
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
