import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
