import { expect, test, type Page } from "@playwright/test";

const API = "http://localhost:8010/api/v1";

async function createFromSample(page: Page, label: string): Promise<string> {
  await page.goto("/");
  await page.getByLabel("Load sample note").selectOption({ label });
  await page.getByRole("button", { name: "Save note" }).click();
  await page.waitForURL(/\/notes\/[0-9a-f-]+$/);
  return page.url().split("/").pop() as string;
}

test("smoke: create a note, analyze, see evidence, accept, edit and reject", async ({
  page,
  request,
}) => {
  const noteId = await createFromSample(page, "Worked example: diabetes with CKD stage 3");

  await page.getByRole("button", { name: "Analyze" }).click();
  const e11 = page.getByRole("article", { name: "Suggestion E11.22" });
  const n18 = page.getByRole("article", { name: "Suggestion N18.30" });
  await expect(e11).toBeVisible();
  await expect(n18).toBeVisible();

  // Evidence: hovering a card highlights its supporting sentence (sentence 1).
  await e11.hover();
  await expect(page.locator('[data-sentence="1"]')).toHaveAttribute("data-highlighted", "true");
  await expect(page.locator('[data-sentence="1"]')).toContainText(
    "Type 2 diabetes mellitus with chronic kidney disease stage 3.",
  );

  await e11.getByRole("button", { name: "Accept" }).click();
  await expect(e11.getByTestId("decision")).toContainText("accept");

  await n18.getByRole("button", { name: "Edit" }).click();
  await n18.getByLabel("Replacement code for N18.30").fill("N18.31");
  await n18.getByRole("button", { name: "Save edit" }).click();
  await expect(n18.getByTestId("decision")).toContainText("edit to N18.31");

  await n18.getByRole("button", { name: "Reject" }).click();
  await n18.getByLabel("Reason for N18.30").fill("Stage not addressed at this visit");
  await n18.getByRole("button", { name: "Confirm reject" }).click();
  await expect(n18.getByTestId("decision")).toContainText("reject");

  // The API recorded all three reviews, append-only.
  const history = await (await request.get(`${API}/notes/${noteId}/history`)).json();
  expect(history.reviews.map((r: { action: string }) => r.action)).toEqual([
    "accept",
    "edit",
    "reject",
  ]);
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
