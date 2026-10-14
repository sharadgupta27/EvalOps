import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useLogin, useRegister } from "../api/hooks";
import { Button, ErrorBanner, Field, Input } from "../components/ui";
import { useAuth } from "../lib/auth";

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
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={(e) => void submit(e).catch(() => undefined)}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow-sm ring-1 ring-slate-200"
      >
        <div>
          <h1 className="text-xl font-semibold">EvalOps</h1>
          <p className="text-sm text-slate-500">Unit tests for your prompts.</p>
        </div>
        <Field label="Email">
          <Input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </Field>
        <Field label="Password" hint={mode === "register" ? "At least 8 characters." : undefined}>
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
        <Button type="submit" disabled={busy} className="w-full justify-center">
          {mode === "login" ? "Log in" : "Create account"}
        </Button>
        <button
          type="button"
          className="w-full text-center text-sm text-indigo-600 hover:underline"
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
  );
}
