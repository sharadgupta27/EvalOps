import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useMe, useProjects } from "../api/hooks";
import { useAuth } from "../lib/auth";
import { Icon, Logo, type IconName } from "./Icon";

const COLLAPSED_KEY = "evalops.sidebar-collapsed";
const MAX_SIDEBAR_PROJECTS = 8;

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

function NavItem({
  to,
  icon,
  label,
  collapsed,
  onNavigate,
  end,
}: {
  to: string;
  icon: IconName;
  label: string;
  collapsed: boolean;
  onNavigate: () => void;
  end?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      aria-label={label}
      title={collapsed ? label : undefined}
      onClick={onNavigate}
      className={({ isActive }) =>
        `group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${collapsed ? "lg:justify-center lg:px-0" : ""} ${
          isActive
            ? "bg-indigo-50 text-indigo-700"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`
      }
    >
      <Icon name={icon} className="h-[18px] w-[18px]" />
      <span className={`truncate ${collapsed ? "lg:hidden" : ""}`}>{label}</span>
    </NavLink>
  );
}

export function Layout() {
  const { logout, isAuthenticated } = useAuth();
  const me = useMe(isAuthenticated);
  const projects = useProjects();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawer, setDrawer] = useState(false);

  function toggleCollapsed() {
    setCollapsed((value) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, value ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !value;
    });
  }

  const email = me.data?.email;
  const initial = (email ?? "?").slice(0, 1).toUpperCase();
  const close = () => setDrawer(false);
  const recent = projects.data?.slice(0, MAX_SIDEBAR_PROJECTS) ?? [];

  return (
    <div className="flex min-h-full bg-slate-50/60">
      {drawer && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
          onClick={close}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 ${
          collapsed ? "lg:w-[4.5rem]" : "lg:w-64"
        } ${drawer ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div
          className={`flex items-center gap-2 px-4 pt-4 ${collapsed ? "lg:flex-col lg:px-0" : "justify-between"}`}
        >
          <Link
            to="/"
            className="flex items-center gap-2.5 text-lg font-bold tracking-tight text-slate-900"
            aria-label="EvalOps home"
          >
            <Logo />
            <span className={collapsed ? "lg:hidden" : ""}>EvalOps</span>
          </Link>
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 lg:block"
          >
            <Icon name="panel" className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={close}
            aria-label="Close menu"
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden"
          >
            <Icon name="close" className="h-5 w-5" />
          </button>
        </div>

        <div className={`mt-5 px-3 ${collapsed ? "lg:px-2" : ""}`}>
          <Link
            to="/"
            onClick={close}
            title={collapsed ? "New project" : undefined}
            className={`flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm transition-colors hover:border-indigo-300 hover:bg-indigo-50/50 ${collapsed ? "lg:justify-center lg:px-0" : ""}`}
          >
            <span className="grid h-5 w-5 place-items-center rounded-full bg-indigo-600 text-white">
              <Icon name="plus" className="h-3.5 w-3.5" />
            </span>
            <span className={collapsed ? "lg:hidden" : ""}>New project</span>
          </Link>
        </div>

        <nav
          className={`mt-4 flex-1 space-y-1 overflow-y-auto px-3 ${collapsed ? "lg:px-2" : ""}`}
          aria-label="Main"
        >
          <NavItem
            to="/"
            end
            icon="projects"
            label="Projects"
            collapsed={collapsed}
            onNavigate={close}
          />
          {recent.length > 0 && (
            <>
              <p
                className={`px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400 ${collapsed ? "lg:hidden" : ""}`}
              >
                Recent
              </p>
              {recent.map((p) => (
                <NavItem
                  key={p.id}
                  to={`/projects/${p.id}`}
                  icon="chart"
                  label={p.name}
                  collapsed={collapsed}
                  onNavigate={close}
                />
              ))}
            </>
          )}
        </nav>

        <div className={`border-t border-slate-100 p-3 ${collapsed ? "lg:p-2" : ""}`}>
          <div
            className={`flex items-center gap-2.5 rounded-xl bg-slate-50 p-2 ${collapsed ? "lg:flex-col lg:bg-transparent" : ""}`}
          >
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-amber-300 to-orange-400 text-sm font-bold text-slate-900">
              {initial}
            </span>
            <div className={`min-w-0 flex-1 ${collapsed ? "lg:hidden" : ""}`}>
              <p className="truncate text-sm font-medium text-slate-900">{email ?? "Signed in"}</p>
              <p className="truncate text-xs text-slate-500">Prompt testing</p>
            </div>
            <button
              type="button"
              onClick={logout}
              aria-label="Log out"
              title="Log out"
              className="rounded-lg p-1.5 text-slate-500 hover:bg-white hover:text-slate-900"
            >
              <Icon name="logout" className="h-[18px] w-[18px]" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-2.5 backdrop-blur lg:hidden">
          <button
            type="button"
            onClick={() => setDrawer(true)}
            aria-label="Open menu"
            className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
          >
            <Icon name="menu" className="h-5 w-5" />
          </button>
          <span className="flex items-center gap-2 font-bold text-slate-900">
            <Logo className="h-6 w-6" />
            EvalOps
          </span>
        </header>
        <main className="w-full flex-1 px-4 py-6 sm:px-8 sm:py-8">
          <div className="mx-auto max-w-6xl animate-rise">
            <Outlet />
          </div>
        </main>
      </div>
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
          <Link
            to={back.to}
            className="mb-1 inline-flex items-center gap-1 text-xs font-medium text-indigo-700 hover:underline"
          >
            <Icon name="back" className="h-3 w-3" />
            {back.label}
          </Link>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
