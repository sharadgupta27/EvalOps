import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { tokenStore } from "../api/client";
import { AuthProvider } from "../lib/auth";

// The page only knows the hooks; mock them so the test exercises UI behaviour only.
const loginMock = vi.fn();
const registerMock = vi.fn();
vi.mock("../api/hooks", () => ({
  useLogin: () => ({ mutateAsync: loginMock, isPending: false, error: null, reset: vi.fn() }),
  useRegister: () => ({ mutateAsync: registerMock, isPending: false, error: null, reset: vi.fn() }),
}));

const { LoginPage } = await import("./login-page");

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<p>projects home</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    loginMock.mockReset().mockResolvedValue({ access_token: "jwt-1", token_type: "bearer" });
    registerMock.mockReset().mockResolvedValue({});
  });

  it("logs in, stores the token and redirects", async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText("Email"), "priya@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(loginMock).toHaveBeenCalledWith({ email: "priya@example.com", password: "secret-pass" });
    await waitFor(() => expect(screen.getByText("projects home")).toBeInTheDocument());
    expect(tokenStore.get()).toBe("jwt-1");
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("registers first in sign-up mode", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: /No account/ }));
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.type(screen.getByLabelText(/Password/), "long-enough");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(registerMock).toHaveBeenCalledOnce());
    expect(loginMock).toHaveBeenCalledOnce();
  });
});
