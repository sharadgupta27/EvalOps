import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useCreateDataset, useDatasets } from "../api/hooks";
import { Badge, Button, Card, Empty, ErrorBanner, Field, Input, Loading } from "./ui";

export function DatasetsTab({ projectId }: { projectId: number }) {
  const datasets = useDatasets(projectId);
  const create = useCreateDataset(projectId);
  const [name, setName] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate({ name }, { onSuccess: () => setName("") });
  }

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <div className="md:col-span-2">
        <Card title="Datasets">
          {datasets.isLoading && <Loading />}
          <ErrorBanner error={datasets.error} />
          {datasets.data?.length === 0 && <Empty>No datasets yet.</Empty>}
          <ul className="space-y-2">
            {datasets.data?.map((d) => (
              <li key={d.id}>
                <Link
                  to={`/datasets/${d.id}?project=${projectId}`}
                  className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50"
                >
                  <span className="font-medium text-slate-900">{d.name}</span>
                  <Badge>{d.case_count} cases</Badge>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <Card title="New dataset">
        <form onSubmit={submit} className="space-y-3">
          <Field label="Name">
            <Input
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="golden-v1"
            />
          </Field>
          <ErrorBanner error={create.error} />
          <Button type="submit" disabled={create.isPending}>
            Create dataset
          </Button>
        </form>
      </Card>
    </div>
  );
}
