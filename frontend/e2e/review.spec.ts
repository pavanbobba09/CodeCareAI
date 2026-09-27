import { expect, test, type Page } from "@playwright/test";

const API = "http://localhost:8010/api/v1";

async function createFromSample(page: Page, label: string): Promise<string> {
  await page.goto("/");
  await page.getByLabel("Load sample note").selectOption({ label });
  await page.getByRole("button", { name: "Save note" }).click();
  await page.waitForURL(/\/notes\/[0-9a-f-]+$/);
  return page.url().split("/").pop() as string;
}

// Must match E2E_NOTE in scripts/fake_llm.py: E11.22 cites sentence 1, N18.32 sentence 2.
const E2E_NOTE =
  "Assessment: Type 2 diabetes mellitus with chronic kidney disease.\n" +
  "Chronic kidney disease stage 3b per recent labs.\n" +
  "Plan: Recheck renal function in 3 months.\n";

test("smoke: create a note, analyze, see evidence, accept, edit and reject", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByLabel("Note text").fill(E2E_NOTE);
  await page.getByRole("button", { name: "Save note" }).click();
  await page.waitForURL(/\/notes\/[0-9a-f-]+$/);
  const noteId = page.url().split("/").pop() as string;

  await page.getByRole("button", { name: "Analyze" }).click();
  const e11 = page.getByRole("article", { name: "Suggestion E11.22" });
  const n18 = page.getByRole("article", { name: "Suggestion N18.32" });
  await expect(e11).toBeVisible();
  await expect(n18).toBeVisible();

  // Each card highlights only its own evidence, and keeps it after the pointer leaves.
  const s1 = page.locator('[data-sentence="1"]');
  const s2 = page.locator('[data-sentence="2"]');
  await e11.getByText("E11.22", { exact: true }).click();
  await page.mouse.move(0, 0);
  await expect(e11).toHaveAttribute("aria-current", "true");
  await expect(s1).toHaveAttribute("data-highlighted", "true");
  await expect(s2).not.toHaveAttribute("data-highlighted", "true");
  await expect(s1).toContainText("Type 2 diabetes mellitus with chronic kidney disease.");

  await n18.getByText("N18.32", { exact: true }).click();
  await page.mouse.move(0, 0);
  await expect(s2).toHaveAttribute("data-highlighted", "true");
  await expect(s1).not.toHaveAttribute("data-highlighted", "true");

  // Keyboard focus selects too.
  await e11.focus();
  await expect(e11).toHaveAttribute("aria-current", "true");
  await expect(s1).toHaveAttribute("data-highlighted", "true");
  await expect(s2).not.toHaveAttribute("data-highlighted", "true");

  await e11.getByRole("button", { name: "Accept" }).click();
  await expect(e11.getByTestId("decision")).toContainText("accept");

  await n18.getByRole("button", { name: "Edit" }).click();
  await n18.getByLabel("Replacement code for N18.32").fill("N18.31");
  await n18.getByRole("button", { name: "Save edit" }).click();
  await expect(n18.getByTestId("decision")).toContainText("edit to N18.31");

  await n18.getByRole("button", { name: "Reject" }).click();
  await n18.getByLabel("Reason for N18.32").fill("Stage not addressed at this visit");
  await n18.getByRole("button", { name: "Confirm reject" }).click();
  await expect(n18.getByTestId("decision")).toContainText("reject");

  // The API recorded all three reviews, append-only.
  const history = await (await request.get(`${API}/notes/${noteId}/history`)).json();
  expect(history.reviews.map((r: { action: string }) => r.action)).toEqual([
    "accept",
    "edit",
    "reject",
  ]);

  // While a re-analysis runs, no review button can be used (the request is only delayed).
  let release = () => {};
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route("**/analyze", async (route) => {
    await gate;
    await route.continue();
  });
  await page.getByRole("button", { name: "Analyze again" }).click();
  await expect(page.getByRole("button", { name: "Analyzing…" })).toBeDisabled();
  for (const name of ["Accept", "Edit", "Reject"]) {
    const buttons = page.getByRole("button", { name, exact: true });
    await expect(buttons).toHaveCount(2);
    for (const button of await buttons.all()) await expect(button).toBeDisabled();
  }
  release();
  await expect(page.getByRole("button", { name: "Analyze again" })).toBeEnabled();
  await expect(e11.getByRole("button", { name: "Accept" })).toBeEnabled();
});

test("failed analysis: the LLM error is shown and nothing partial appears", async ({ page }) => {
  // The fake LLM only knows the worked example, so any other note fails with a 503.
  await createFromSample(page, "Gap: heart failure without a type");

  await page.getByRole("button", { name: "Analyze" }).click();

  const failed = page.getByRole("alert", { name: "Analysis failed" });
  await expect(failed).toBeVisible();
  await expect(failed).toContainText("LLM_UNAVAILABLE");
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Analyze again" })).toBeEnabled();
});
