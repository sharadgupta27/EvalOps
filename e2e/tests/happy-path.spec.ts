// The happy path from plan.md §1, driven through the real UI:
// sign up → project → v1 + dataset import + evaluators → run → v2 → run → compare.
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const CSV = path.resolve(here, "../../docs/examples/support_cases.csv");

const V1 = `You are a polite, friendly support agent.
Reply in JSON with a single field "answer".
Customer {{customer}} asks:
{{question}}`;
const V2 = `Be terse: answer in one word.
Customer {{customer}} asks:
{{question}}`;

async function openTab(page: Page, name: string) {
  await page.getByRole("tab", { name }).click();
}

async function createVersion(page: Page, label: string, template: string) {
  await openTab(page, "Prompt versions");
  await page.getByLabel("Label").fill(label);
  await page.getByLabel("Template").fill(template);
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByRole("heading", { name: new RegExp(`^${label}`) })).toBeVisible();
}

async function addEvaluator(page: Page, type: string, name: string, config?: string) {
  await page.getByRole("combobox").selectOption(type);
  await page.getByLabel("Name").fill(name);
  if (config) await page.getByLabel("Config (JSON)").fill(config);
  await page.getByRole("button", { name: "Add evaluator" }).click();
  await expect(page.getByRole("button", { name: `Delete ${name}` })).toBeVisible();
}

async function runVersion(page: Page, label: string) {
  await openTab(page, "Runs");
  await page.getByLabel("Prompt version").selectOption({ label });
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(page).toHaveURL(/\/runs\/\d+$/);
  await expect(page.getByText("succeeded")).toBeVisible();
  return Number(page.url().split("/").pop());
}

test("prompt regression is caught end to end", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/login");
  await page.getByRole("button", { name: /No account/ }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/Password/).fill("e2e-password-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();

  await page.getByLabel("Name").fill("Support reply generator");
  await page.getByRole("button", { name: "Create project" }).click();
  await page.getByRole("link", { name: "Support reply generator" }).click();
  const projectUrl = page.url().split("?")[0]!;

  await createVersion(page, "v1", V1);

  await openTab(page, "Datasets");
  await page.getByLabel("Name").fill("golden");
  await page.getByRole("button", { name: "Create dataset" }).click();
  await page.getByRole("link", { name: "golden" }).click();
  await page.getByLabel("Dataset file").setInputFiles(CSV);
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByTestId("import-report")).toContainText("Imported 30 case(s)");

  await page.goto(`${projectUrl}?tab=evaluators`);
  await addEvaluator(page, "contains", "mentions-topic");
  await addEvaluator(
    page,
    "json_schema",
    "json-answer",
    '{"schema": {"type": "object", "required": ["answer"]}}',
  );
  await addEvaluator(page, "llm_judge", "polite-and-correct");

  await page.goto(projectUrl);
  const base = await runVersion(page, "v1");
  await expect(page.getByText("30/30 passed, 0 errored")).toBeVisible();

  await page.goto(projectUrl);
  await createVersion(page, "v2", V2);
  const head = await runVersion(page, "v2");
  await expect(page.getByText("0/30 passed", { exact: false })).toBeVisible();

  await page.goto(`/compare?base=${base}&head=${head}`);
  await expect(page.getByTestId("compare-verdict")).toHaveText("30 cases regressed");
  await page.getByTestId(/compare-row-/).first().click();
  await expect(page.getByText("Base output")).toBeVisible();
});
