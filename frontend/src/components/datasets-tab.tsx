import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useCreateDataset, useDatasets } from "../api/hooks";
import { Button, Card, Empty, ErrorBanner, Field, Input, Loading } from "./ui";

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
          <ul className="divide-y divide-slate-100">
            {datasets.data?.map((d) => (
              <li key={d.id} className="flex items-center justify-between py-3">
                <Link
                  to={`/datasets/${d.id}?project=${projectId}`}
                  className="font-medium text-indigo-700 hover:underline"
                >
                  {d.name}
                </Link>
                <span className="text-sm text-slate-500">{d.case_count} cases</span>
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
