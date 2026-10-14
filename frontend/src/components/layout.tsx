import { Link, Outlet } from "react-router-dom";
import { useMe } from "../api/hooks";
import { useAuth } from "../lib/auth";
import { Button } from "./ui";

export function Layout() {
  const { logout, isAuthenticated } = useAuth();
  const me = useMe(isAuthenticated);
  return (
    <div className="min-h-screen">
      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-slate-900">
            <span className="rounded bg-indigo-600 px-1.5 py-0.5 text-xs font-bold text-white">
              EO
            </span>
            EvalOps
          </Link>
          <div className="flex items-center gap-3 text-sm text-slate-600">
            {me.data && <span>{me.data.email}</span>}
            <Button variant="ghost" onClick={logout}>
              Log out
            </Button>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  back,
  actions,
}: {
  title: string;
  subtitle?: string;
  back?: { to: string; label: string };
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        {back && (
          <Link to={back.to} className="text-xs text-indigo-600 hover:underline">
            ← {back.label}
          </Link>
        )}
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}
