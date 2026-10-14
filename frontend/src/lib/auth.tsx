import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { tokenStore } from "../api/client";

type AuthState = {
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [token, setToken] = useState<string | null>(() => tokenStore.get());

  const logout = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    qc.clear();
  }, [qc]);

  const login = useCallback((t: string) => {
    tokenStore.set(t);
    setToken(t);
  }, []);

  useEffect(() => {
    // The API client fires this when the server rejects our token.
    window.addEventListener("evalops:logout", logout);
    return () => window.removeEventListener("evalops:logout", logout);
  }, [logout]);

  const value = useMemo(
    () => ({ isAuthenticated: !!token, login, logout }),
    [token, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
