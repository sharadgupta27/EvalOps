// TanStack Query hooks: the only way components read or change server state.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "./client";

const ACTIVE_RUN = new Set(["queued", "running"]);

export const keys = {
  me: ["me"] as const,
  projects: ["projects"] as const,
  project: (id: number) => ["project", id] as const,
  versions: (pid: number) => ["versions", pid] as const,
  datasets: (pid: number) => ["datasets", pid] as const,
  dataset: (id: number) => ["dataset", id] as const,
  cases: (id: number) => ["cases", id] as const,
  evaluators: (pid: number) => ["evaluators", pid] as const,
  runs: (pid: number) => ["runs", pid] as const,
  run: (id: number) => ["run", id] as const,
  results: (id: number) => ["results", id] as const,
  compare: (base: number, head: number) => ["compare", base, head] as const,
  policy: (pid: number) => ["policy", pid] as const,
  keys: (pid: number) => ["api-keys", pid] as const,
};

const pp = (project_id: number) => ({ params: { path: { project_id } } });
const dp = (dataset_id: number) => ({ params: { path: { dataset_id } } });

// --- auth --------------------------------------------------------------------
export const useMe = (enabled: boolean) =>
  useQuery({ queryKey: keys.me, queryFn: () => unwrap(api.GET("/auth/me")), enabled });

export const useLogin = () =>
  useMutation({
    mutationFn: (body: Schemas["LoginRequest"]) => unwrap(api.POST("/auth/login", { body })),
  });

export const useRegister = () =>
  useMutation({
    mutationFn: (body: Schemas["RegisterRequest"]) => unwrap(api.POST("/auth/register", { body })),
  });

// --- projects ------------------------------------------------------------------
export const useProjects = () =>
  useQuery({ queryKey: keys.projects, queryFn: () => unwrap(api.GET("/projects")) });

export const useProject = (id: number) =>
  useQuery({
    queryKey: keys.project(id),
    queryFn: () => unwrap(api.GET("/projects/{project_id}", pp(id))),
  });

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ProjectCreate"]) => unwrap(api.POST("/projects", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE("/projects/{project_id}", pp(id))),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  });
}

// --- prompt versions --------------------------------------------------------------
export const useVersions = (pid: number) =>
  useQuery({
    queryKey: keys.versions(pid),
    queryFn: () => unwrap(api.GET("/projects/{project_id}/prompt-versions", pp(pid))),
  });

export function useCreateVersion(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["PromptVersionCreate"]) =>
      unwrap(api.POST("/projects/{project_id}/prompt-versions", { ...pp(pid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.versions(pid) }),
  });
}

// --- datasets & cases -----------------------------------------------------------
export const useDatasets = (pid: number) =>
  useQuery({
    queryKey: keys.datasets(pid),
    queryFn: () => unwrap(api.GET("/projects/{project_id}/datasets", pp(pid))),
  });

export const useDataset = (id: number) =>
  useQuery({
    queryKey: keys.dataset(id),
    queryFn: () => unwrap(api.GET("/datasets/{dataset_id}", dp(id))),
  });

export function useCreateDataset(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["DatasetCreate"]) =>
      unwrap(api.POST("/projects/{project_id}/datasets", { ...pp(pid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.datasets(pid) }),
  });
}

export const useCases = (id: number) =>
  useQuery({
    queryKey: keys.cases(id),
    queryFn: () => unwrap(api.GET("/datasets/{dataset_id}/cases", dp(id))),
  });

function useInvalidateDataset(id: number) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: keys.cases(id) });
    void qc.invalidateQueries({ queryKey: keys.dataset(id) });
    void qc.invalidateQueries({ queryKey: ["datasets"] });
  };
}

export function useCreateCase(datasetId: number) {
  const onSuccess = useInvalidateDataset(datasetId);
  return useMutation({
    mutationFn: (body: Schemas["TestCaseCreate"]) =>
      unwrap(api.POST("/datasets/{dataset_id}/cases", { ...dp(datasetId), body })),
    onSuccess,
  });
}

export function useDeleteCase(datasetId: number) {
  const onSuccess = useInvalidateDataset(datasetId);
  return useMutation({
    mutationFn: (case_id: number) =>
      unwrap(
        api.DELETE("/datasets/{dataset_id}/cases/{case_id}", {
          params: { path: { dataset_id: datasetId, case_id } },
        }),
      ),
    onSuccess,
  });
}

export function useImportCases(datasetId: number) {
  const onSuccess = useInvalidateDataset(datasetId);
  return useMutation({
    mutationFn: (file: File) =>
      unwrap(
        api.POST("/datasets/{dataset_id}/import", {
          ...dp(datasetId),
          // openapi-fetch types multipart bodies as the schema; FormData is what goes on the wire.
          body: { file: file as unknown as string },
          bodySerializer: (body) => {
            const form = new FormData();
            form.append("file", body.file as unknown as File);
            return form;
          },
        }),
      ),
    onSuccess,
  });
}

// --- evaluators ----------------------------------------------------------------
export const useEvaluators = (pid: number) =>
  useQuery({
    queryKey: keys.evaluators(pid),
    queryFn: () => unwrap(api.GET("/projects/{project_id}/evaluators", pp(pid))),
  });

export function useCreateEvaluator(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["EvaluatorCreate"]) =>
      unwrap(api.POST("/projects/{project_id}/evaluators", { ...pp(pid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.evaluators(pid) }),
  });
}

export function useDeleteEvaluator(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (evaluator_id: number) =>
      unwrap(
        api.DELETE("/projects/{project_id}/evaluators/{evaluator_id}", {
          params: { path: { project_id: pid, evaluator_id } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.evaluators(pid) }),
  });
}

// --- runs ---------------------------------------------------------------------
export const useRuns = (pid: number) =>
  useQuery({
    queryKey: keys.runs(pid),
    queryFn: () => unwrap(api.GET("/projects/{project_id}/runs", pp(pid))),
    // Keep polling while anything is still in flight.
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE_RUN.has(r.status)) ? 1500 : false),
  });

export const useRun = (id: number) =>
  useQuery({
    queryKey: keys.run(id),
    queryFn: () => unwrap(api.GET("/runs/{run_id}", { params: { path: { run_id: id } } })),
    refetchInterval: (q) => (q.state.data && ACTIVE_RUN.has(q.state.data.status) ? 1000 : false),
  });

export const useResults = (id: number, enabled: boolean) =>
  useQuery({
    queryKey: keys.results(id),
    queryFn: () => unwrap(api.GET("/runs/{run_id}/results", { params: { path: { run_id: id } } })),
    enabled,
  });

export function useCreateRun(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["RunCreate"]) =>
      unwrap(api.POST("/projects/{project_id}/runs", { ...pp(pid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.runs(pid) }),
  });
}

export const useCompare = (base: number, head: number) =>
  useQuery({
    queryKey: keys.compare(base, head),
    queryFn: () => unwrap(api.GET("/runs/compare", { params: { query: { base, head } } })),
    enabled: base > 0 && head > 0,
  });

// --- gate policy & API keys -------------------------------------------------------
export const useGatePolicy = (pid: number) =>
  useQuery({
    queryKey: keys.policy(pid),
    queryFn: () => unwrap(api.GET("/projects/{project_id}/gate-policy", pp(pid))),
  });

export function useSaveGatePolicy(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["GatePolicy"]) =>
      unwrap(api.PUT("/projects/{project_id}/gate-policy", { ...pp(pid), body })),
    onSuccess: (data) => qc.setQueryData(keys.policy(pid), data),
  });
}

export const useApiKeys = (pid: number) =>
  useQuery({
    queryKey: keys.keys(pid),
    queryFn: () => unwrap(api.GET("/projects/{project_id}/api-keys", pp(pid))),
  });

export function useCreateApiKey(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ApiKeyCreate"]) =>
      unwrap(api.POST("/projects/{project_id}/api-keys", { ...pp(pid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.keys(pid) }),
  });
}

export function useRevokeApiKey(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key_id: number) =>
      unwrap(
        api.DELETE("/projects/{project_id}/api-keys/{key_id}", {
          params: { path: { project_id: pid, key_id } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.keys(pid) }),
  });
}
