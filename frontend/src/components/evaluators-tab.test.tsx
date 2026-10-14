import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const createMock = vi.fn();
vi.mock("../api/hooks", () => ({
  useEvaluators: () => ({ data: [], isLoading: false, error: null }),
  useCreateEvaluator: () => ({ mutate: createMock, isPending: false, error: null }),
  useDeleteEvaluator: () => ({ mutate: vi.fn(), error: null }),
}));

const { EvaluatorsTab, CONFIG_TEMPLATES } = await import("./evaluators-tab");

describe("EvaluatorsTab", () => {
  beforeEach(() => createMock.mockReset());

  it("swaps in a starter config when the type changes", async () => {
    render(<EvaluatorsTab projectId={1} />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "llm_judge");
    expect(screen.getByLabelText("Config (JSON)")).toHaveValue(CONFIG_TEMPLATES.llm_judge);
  });

  it("refuses invalid JSON without calling the API", async () => {
    render(<EvaluatorsTab projectId={1} />);
    await userEvent.type(screen.getByLabelText("Name"), "judge");
    const config = screen.getByLabelText("Config (JSON)");
    await userEvent.clear(config);
    await userEvent.type(config, "not json");
    await userEvent.click(screen.getByRole("button", { name: "Add evaluator" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Config must be valid JSON");
    expect(createMock).not.toHaveBeenCalled();
  });

  it("submits the parsed config", async () => {
    render(<EvaluatorsTab projectId={1} />);
    await userEvent.type(screen.getByLabelText("Name"), "topic");
    await userEvent.click(screen.getByRole("button", { name: "Add evaluator" }));
    expect(createMock).toHaveBeenCalledWith(
      { type: "contains", name: "topic", weight: 1, config: { case_sensitive: false } },
      expect.anything(),
    );
  });
});
