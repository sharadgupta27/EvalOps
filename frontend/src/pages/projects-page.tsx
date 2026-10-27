import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useCreateProject, useProjects } from "../api/hooks";
import { Icon } from "../components/Icon";
import { PageHeader } from "../components/layout";
import { Button, Card, Empty, ErrorBanner, Field, Input, Loading } from "../components/ui";

export function ProjectsPage() {
  const projects = useProjects();
  const create = useCreateProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      { name, description },
      {
        onSuccess: () => {
          setName("");
          setDescription("");
        },
      },
    );
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
            <ul className="space-y-2">
              {projects.data?.map((p) => (
                <li key={p.id}>
                  <Link
                    to={`/projects/${p.id}`}
                    className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-indigo-50 text-indigo-600">
                      <Icon name="chart" className="h-[18px] w-[18px]" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-slate-900">{p.name}</span>
                      {p.description && (
                        <span className="block truncate text-sm text-slate-500">
                          {p.description}
                        </span>
                      )}
                    </span>
                    <Icon
                      name="arrow"
                      className="h-4 w-4 text-slate-300 transition-colors group-hover:text-indigo-600"
                    />
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
              <Icon name="plus" className="h-4 w-4" />
              Create project
            </Button>
          </form>
        </Card>
      </div>
    </>
  );
}
