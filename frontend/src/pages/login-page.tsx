import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useLogin, useRegister } from "../api/hooks";
import { Icon, Logo, type IconName } from "../components/Icon";
import { Button, ErrorBanner, Field, Input } from "../components/ui";
import { useAuth } from "../lib/auth";

const POINTS: { icon: IconName; text: string }[] = [
  { icon: "git", text: "Every prompt version is saved and can be compared run against run" },
  { icon: "chart", text: "Pass rate, score, latency and cost for each change, case by case" },
  { icon: "shield", text: "A CI gate stops a regression before it reaches users" },
];

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const loginMut = useLogin();
  const registerMut = useRegister();
  const busy = loginMut.isPending || registerMut.isPending;
  const error = loginMut.error ?? registerMut.error;

  if (isAuthenticated) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (mode === "register") await registerMut.mutateAsync({ email, password });
    const token = await loginMut.mutateAsync({ email, password });
    login(token.access_token);
  }

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <section className="relative isolate hidden overflow-hidden bg-slate-950 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(70% 60% at 20% 10%, rgb(79 70 229 / 0.55), transparent 70%), radial-gradient(60% 50% at 90% 80%, rgb(14 165 233 / 0.4), transparent 70%), radial-gradient(40% 40% at 60% 40%, rgb(168 85 247 / 0.3), transparent 70%)",
          }}
        />
        <div className="flex items-center gap-3 text-xl font-bold">
          <Logo className="h-10 w-10" />
          EvalOps
        </div>
        <div>
          <h2 className="max-w-md text-4xl font-extrabold leading-tight tracking-tight">
            Ship prompt changes without the guesswork.
          </h2>
          <ul className="mt-8 space-y-4">
            {POINTS.map((point) => (
              <li key={point.text} className="flex items-start gap-3 text-slate-200">
                <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/10 ring-1 ring-white/15">
                  <Icon name={point.icon} className="h-4 w-4" />
                </span>
                {point.text}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-slate-400">Part of the CiteSure family of tools.</p>
      </section>

      <div className="relative isolate grid place-items-center px-4 py-10">
        <div className="aurora absolute inset-0 -z-10 lg:hidden" aria-hidden="true" />
        <div className="w-full max-w-sm space-y-6">
          <div className="text-center">
            <div className="mx-auto mb-3 flex justify-center lg:hidden">
              <Logo className="h-12 w-12" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {mode === "register" ? "Create your account" : "Welcome back"}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {mode === "register"
                ? "It takes a few seconds."
                : "Sign in to EvalOps. Unit tests for your prompts."}
            </p>
          </div>
          <form
            onSubmit={(e) => void submit(e).catch(() => undefined)}
            className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
          >
            <Field label="Email">
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </Field>
            <Field
              label="Password"
              hint={mode === "register" ? "At least 8 characters." : undefined}
            >
              <Input
                type="password"
                required
                minLength={mode === "register" ? 8 : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "register" ? "new-password" : "current-password"}
              />
            </Field>
            <ErrorBanner error={error} />
            <Button type="submit" disabled={busy} className="w-full py-2.5">
              {mode === "login" ? "Log in" : "Create account"}
            </Button>
            <button
              type="button"
              className="w-full text-center text-sm font-medium text-indigo-700 hover:underline"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                loginMut.reset();
                registerMut.reset();
              }}
            >
              {mode === "login" ? "No account? Register" : "Have an account? Log in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
