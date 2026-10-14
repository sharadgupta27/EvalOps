import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useCreateProject, useProjects } from "../api/hooks";
import { PageHeader } from "../components/layout";
import { Button, Card, Empty, ErrorBanner, Field, Input, Loading } from "../components/ui";

export function ProjectsPage() {
  const projects = useProjects();
  const create = useCreateProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate({ name, description }, { onSuccess: () => (setName(""), setDescription("")) });
  }

  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="One project per LLM feature you want to keep from regressing."
      />
      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2">
          <Card title="Your projects">
            {projects.isLoading && <Loading />}
            <ErrorBanner error={projects.error} />
            {projects.data?.length === 0 && (
              <Empty>No projects yet. Create one to get started.</Empty>
            )}
            <ul className="divide-y divide-slate-100">
              {projects.data?.map((p) => (
                <li key={p.id}>
                  <Link to={`/projects/${p.id}`} className="block px-1 py-3 hover:bg-slate-50">
                    <div className="font-medium text-indigo-700">{p.name}</div>
                    {p.description && <div className="text-sm text-slate-500">{p.description}</div>}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
        <Card title="New project">
          <form onSubmit={submit} className="space-y-3">
            <Field label="Name">
              <Input
                required
                maxLength={120}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Support reply generator"
              />
            </Field>
            <Field label="Description">
              <Input
                maxLength={2000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>
            <ErrorBanner error={create.error} />
            <Button type="submit" disabled={create.isPending}>
              Create project
            </Button>
          </form>
        </Card>
      </div>
    </>
  );
}
