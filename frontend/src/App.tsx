import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/layout";
import { useAuth } from "./lib/auth";
import { ComparePage } from "./pages/compare-page";
import { DatasetPage } from "./pages/dataset-page";
import { LoginPage } from "./pages/login-page";
import { ProjectPage } from "./pages/project-page";
import { ProjectsPage } from "./pages/projects-page";
import { RunPage } from "./pages/run-page";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="/datasets/:datasetId" element={<DatasetPage />} />
        <Route path="/runs/:runId" element={<RunPage />} />
        <Route path="/compare" element={<ComparePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
