import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import type { CompareCase } from "../lib/compare";
import { CompareTable } from "./compare-table";

const cases: CompareCase[] = [
  {
    test_case_id: 1,
    inputs: { question: "Where is my order?" },
    expected_output: "order",
    base_output: '{"answer": "Thanks! Your order shipped."}',
    head_output: "order?",
    base_passed: true,
    head_passed: false,
    base_score: 1,
    head_score: 0.5,
    delta: -0.5,
    bucket: "regressed",
  },
  {
    test_case_id: 2,
    inputs: { question: "Refund?" },
    expected_output: "refund",
    base_output: "refund",
    head_output: "refund",
    base_passed: true,
    head_passed: true,
    base_score: 1,
    head_score: 1,
    delta: 0,
    bucket: "unchanged",
  },
];

describe("CompareTable", () => {
  it("shows only changed cases by default and all cases on demand", async () => {
    render(<CompareTable cases={cases} />);
    expect(screen.getByTestId("compare-row-1")).toBeInTheDocument();
    expect(screen.queryByTestId("compare-row-2")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "All" }));
    expect(screen.getByTestId("compare-row-2")).toBeInTheDocument();
  });

  it("expands a row into a side-by-side diff", async () => {
    render(<CompareTable cases={cases} />);
    const row = screen.getByTestId("compare-row-1");
    expect(within(row).getByText("regressed")).toBeInTheDocument();
    expect(within(row).getByText("-0.50")).toBeInTheDocument();
    await userEvent.click(row);
    expect(screen.getByText("Base output")).toBeInTheDocument();
    expect(screen.getByText("Expected:")).toBeInTheDocument();
    expect(screen.getByText("order?").tagName).toBe("MARK");
  });

  it("filters by search text", async () => {
    render(<CompareTable cases={cases} />);
    await userEvent.click(screen.getByRole("tab", { name: "All" }));
    await userEvent.type(screen.getByLabelText("Search cases"), "refund");
    expect(screen.queryByTestId("compare-row-1")).not.toBeInTheDocument();
    expect(screen.getByTestId("compare-row-2")).toBeInTheDocument();
  });
});

describe("CompareTable CSV export", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // jsdom's Blob has no text(), so read it the old way.
  function readBlob(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(reader.error);
      reader.readAsText(blob);
    });
  }

  function mockObjectUrls() {
    const create = vi.fn<(obj: Blob | MediaSource) => string>(() => "blob:compare");
    const revoke = vi.fn<(url: string) => void>();
    // jsdom does not implement these, so define them to observe the download.
    Object.defineProperty(URL, "createObjectURL", { value: create, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: revoke, configurable: true });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    return { create, revoke, click };
  }

  it("exports only the filtered rows and revokes the object URL", async () => {
    const { create, revoke, click } = mockObjectUrls();
    render(<CompareTable cases={cases} baseRunId={3} headRunId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    expect(create).toHaveBeenCalledTimes(1);
    const text = await readBlob(create.mock.calls[0]?.[0] as Blob);
    const lines = text.trimEnd().split("\r\n");
    expect(lines).toHaveLength(2);
    expect(lines[1]).toMatch(/^1,regressed,/);
    expect(text).not.toContain("Refund?");

    expect((click.mock.contexts[0] as HTMLAnchorElement).download).toBe("compare-run-3-vs-7.csv");
    expect(revoke).toHaveBeenCalledWith("blob:compare");
  });

  it("respects the search filter and falls back to a generic file name", async () => {
    const { create, click } = mockObjectUrls();
    render(<CompareTable cases={cases} />);
    await userEvent.click(screen.getByRole("tab", { name: "All" }));
    await userEvent.type(screen.getByLabelText("Search cases"), "refund");
    await userEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    const text = await readBlob(create.mock.calls[0]?.[0] as Blob);
    const lines = text.trimEnd().split("\r\n");
    expect(lines).toHaveLength(2);
    expect(lines[1]).toMatch(/^2,unchanged,/);
    expect((click.mock.contexts[0] as HTMLAnchorElement).download).toBe("compare.csv");
  });

  it("disables export when no rows match", async () => {
    render(<CompareTable cases={cases} />);
    await userEvent.type(screen.getByLabelText("Search cases"), "nothing matches this");
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeDisabled();
  });
});
