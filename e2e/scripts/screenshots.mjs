// Captures README/Substack screenshots from a seeded stack: `node scripts/screenshots.mjs`
// Needs the demo data from `python -m app.seed` (project 1, runs 1 = v1 and 2 = v2).
import { chromium } from "@playwright/test";

const base = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const out = new URL("../../docs/screenshots/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
// Let the page's entrance animation finish and start from the top, so every shot shows the page header.
const shot = async (name) => {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${out}${name}.png` });
};

// Logged out: the sign-in page.
await page.goto(`${base}/login`);
await page.getByRole("button", { name: "Log in" }).waitFor();
await shot("login");

await page.getByLabel("Email").fill("demo@evalops.dev");
await page.getByLabel("Password").fill(process.env.DEMO_PASSWORD ?? "evalops-demo-2026");
await page.getByRole("button", { name: "Log in" }).click();
await page.getByRole("heading", { name: "Projects", exact: true }).waitFor();
await shot("projects");

// The sidebar also links to each project, so go by URL rather than by link name.
await page.goto(`${base}/projects/1`);
await page.getByRole("link", { name: "#1", exact: true }).waitFor();
await shot("runs");

await page.goto(`${base}/projects/1?tab=evaluators`);
await page.getByRole("heading", { name: "Add evaluator", exact: true }).waitFor();
await shot("evaluators");

await page.goto(`${base}/runs/1`);
await page.getByText("Pass rate").first().waitFor();
await page.getByText("#1 customer").first().click();
await shot("run-detail");

await page.goto(`${base}/compare?base=1&head=2`);
await page.getByTestId("compare-verdict").waitFor();
await page.getByTestId(/compare-row-/).first().click();
await shot("compare");

// Phone width: the sidebar becomes a drawer.
await page.setViewportSize({ width: 390, height: 780 });
await page.goto(`${base}/projects/1`);
await page.getByRole("link", { name: "#1", exact: true }).waitFor();
await shot("mobile-runs");

await browser.close();
console.log("screenshots written to", out);
