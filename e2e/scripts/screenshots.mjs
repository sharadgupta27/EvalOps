// Captures README/Substack screenshots from a seeded stack: `node scripts/screenshots.mjs`
import { chromium } from "@playwright/test";

const base = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const out = new URL("../../docs/screenshots/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
await page.goto(`${base}/login`);
await page.getByLabel("Email").fill("demo@evalops.dev");
await page.getByLabel("Password").fill(process.env.DEMO_PASSWORD ?? "evalops-demo-2026");
await page.getByRole("button", { name: "Log in" }).click();
await page.getByRole("link", { name: "Support reply generator" }).click();
await page.getByText("#1").waitFor();
await page.screenshot({ path: `${out}runs.png` });
await page.goto(`${base}/runs/1`);
await page.getByText("Pass rate").waitFor();
await page.getByText("#1 customer").first().click();
await page.screenshot({ path: `${out}run-detail.png`, fullPage: false });
await page.goto(`${base}/compare?base=1&head=2`);
await page.getByTestId("compare-verdict").waitFor();
await page.getByTestId(/compare-row-/).first().click();
await page.screenshot({ path: `${out}compare.png` });
await browser.close();
console.log("screenshots written to", out);
