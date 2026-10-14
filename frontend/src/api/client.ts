// The single place the frontend talks HTTP. Types come from schema.d.ts, which is generated
// from ../openapi.yaml by `npm run gen:api`, so a contract change breaks the build, not prod.
import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

const TOKEN_KEY = "evalops.token";

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Error thrown by every hook when the API answers with a non-2xx status. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) =>
          [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "),
        )
        .join("; ");
    }
  }
  return `Request failed (${status})`;
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = tokenStore.get();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401 && tokenStore.get()) {
      tokenStore.clear();
      window.dispatchEvent(new Event("evalops:logout"));
    }
    return response;
  },
};

export const api = createClient<paths>({ baseUrl: `${window.location.origin}/api/v1` });
api.use(authMiddleware);

/** Unwraps an openapi-fetch result: returns data or throws ApiError. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) throw new ApiError(response.status, errorMessage(error, response.status));
  return data as T;
}
