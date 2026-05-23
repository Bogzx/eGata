import { expect, test } from "@playwright/test";

import {
  collectPageErrors,
  expectChatStream,
  loginViaBackend,
  primeSession,
} from "./helpers";

test.describe("smoke", () => {
  test("login → home page loads with citizen greeting", async ({ page }) => {
    const getErrors = collectPageErrors(page);
    const session = await loginViaBackend();
    await primeSession(page, session);

    await page.goto("/home");
    // ChatSurface waits for the citizen to hydrate; once it's done the
    // composer text input is mounted. Use that as a single readiness signal.
    const composer = page.getByRole("textbox").first();
    await expect(composer).toBeVisible({ timeout: 20_000 });

    const fatal = getErrors().filter(
      (e) =>
        !e.includes("favicon") &&
        !e.includes("HMR") &&
        !e.includes("[Fast Refresh]"),
    );
    expect(fatal, `unexpected console errors: ${fatal.join("\n")}`).toEqual([]);
  });

  test("send text message → assistant response arrives", async ({ page }) => {
    const session = await loginViaBackend();
    await primeSession(page, session);

    await page.goto("/home");
    const composer = page.getByRole("textbox").first();
    await expect(composer).toBeVisible({ timeout: 20_000 });

    await composer.fill("Vreau să îmi schimb domiciliul.");
    await expectChatStream(page, async () => {
      await composer.press("Enter");
    });

    // Assistant message body should appear. We don't assert on its exact text
    // — the LLM can phrase things differently — but the chat surface must
    // surface at least one agent bubble whose text is non-empty.
    const agentBubble = page.locator(".bubble-agent").first();
    await expect(agentBubble).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(
        async () => {
          const t = (await agentBubble.textContent()) ?? "";
          return t.trim().length;
        },
        {
          timeout: 30_000,
          message: "agent bubble appeared but stayed empty",
        },
      )
      .toBeGreaterThan(2);
  });
});
