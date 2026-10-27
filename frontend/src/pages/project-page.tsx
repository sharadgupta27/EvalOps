import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useDeleteProject, useProject } from "../api/hooks";
import { PageHeader } from "../components/layout";
import { DatasetsTab } from "../components/datasets-tab";
import { EvaluatorsTab } from "../components/evaluators-tab";
import { RunsTab } from "../components/runs-tab";
import { SettingsTab } from "../components/settings-tab";
import { Button, ErrorBanner, Loading } from "../components/ui";
import { VersionsTab } from "../components/versions-tab";

const TABS = [
  { id: "runs", label: "Runs" },
  { id: "versions", label: "Prompt versions" },
  { id: "datasets", label: "Datasets" },
  { id: "evaluators", label: "Evaluators" },
  { id: "settings", label: "Gate & API keys" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function ProjectPage() {
  const projectId = Number(useParams().projectId);
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as TabId | null) ?? "runs";
  const project = useProject(projectId);
  const del = useDeleteProject();
  const navigate = useNavigate();

  if (project.isLoading) return <Loading />;
  if (project.error) return <ErrorBanner error={project.error} />;
  if (!project.data) return null;

  return (
    <>
      <PageHeader
        title={project.data.name}
        subtitle={project.data.description}
        back={{ to: "/", label: "Projects" }}
        actions={
          <Button
            variant="danger"
            onClick={() => {
              if (confirm(`Delete "${project.data.name}" and all its data?`)) {
                del.mutate(projectId, { onSuccess: () => navigate("/") });
              }
            }}
          >
            Delete project
          </Button>
        }
      />
      <div role="tablist" className="mb-6 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setParams({ tab: t.id })}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-indigo-300 bg-indigo-50 text-indigo-800"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "runs" && <RunsTab projectId={projectId} />}
      {tab === "versions" && <VersionsTab projectId={projectId} />}
      {tab === "datasets" && <DatasetsTab projectId={projectId} />}
      {tab === "evaluators" && <EvaluatorsTab projectId={projectId} />}
      {tab === "settings" && <SettingsTab projectId={projectId} />}
    </>
  );
}
