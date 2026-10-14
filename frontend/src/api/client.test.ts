import { api, ApiError, errorMessage, tokenStore, unwrap } from "./client";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  beforeEach(() => localStorage.clear());

  it("attaches the bearer token to every request", async () => {
    tokenStore.set("tok-123");
    const fetchMock = vi.fn(async (req: Request) => {
      expect(req.headers.get("Authorization")).toBe("Bearer tok-123");
      expect(new URL(req.url).pathname).toBe("/api/v1/projects");
      return jsonResponse([]);
    });
    await expect(unwrap(api.GET("/projects", { fetch: fetchMock }))).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("turns API errors into ApiError with the server's message", async () => {
    const fetchMock = async () => jsonResponse({ detail: "project not found" }, 404);
    const err = await unwrap(
      api.GET("/projects/{project_id}", { params: { path: { project_id: 9 } }, fetch: fetchMock }),
    ).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
    expect((err as ApiError).message).toBe("project not found");
  });

  it("logs out when the server rejects the token", async () => {
    tokenStore.set("expired");
    const listener = vi.fn();
    window.addEventListener("evalops:logout", listener);
    await api.GET("/projects", {
      fetch: async () => jsonResponse({ detail: "invalid token" }, 401),
    });
    expect(tokenStore.get()).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener("evalops:logout", listener);
  });
});

describe("errorMessage", () => {
  it("flattens FastAPI validation errors", () => {
    const body = { detail: [{ loc: ["body", "password"], msg: "too short" }] };
    expect(errorMessage(body, 422)).toBe("password: too short");
  });

  it("falls back to the status code", () => {
    expect(errorMessage(null, 500)).toBe("Request failed (500)");
  });
});
