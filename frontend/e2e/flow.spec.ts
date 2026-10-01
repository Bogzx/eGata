import { expect, test, type Page } from "@playwright/test";

import { collectPageErrors, loginViaBackend, primeSession } from "./helpers";

// The headline flow, end to end through the UI, against the keyless compose
// stack: request → match → fill → review → deliver → the citizen's browser
// re-verifies the signed audit ledger. The offline agent answers the chat, so
// the steps are deterministic.
//
// E2E_SCREENSHOTS_DIR=<dir> also saves one screenshot per step (the README's
// images come from this).

const SHOTS = process.env.E2E_SCREENSHOTS_DIR;

async function shot(page: Page, name: string): Promise<void> {
  if (!SHOTS) return;
  await page.waitForTimeout(400); // let entry animations settle
  // The floating "Reset demo" dev button (NEXT_PUBLIC_DEMO_MODE) is not part
  // of the product; keep it out of the pictures.
  await page.screenshot({
    path: `${SHOTS}/${name}.png`,
    style: '[aria-label="Resetează datele demo"] { display: none !important; }',
  });
}

/** The widget whose question matches, scoped by its aria-label. */
function widget(page: Page, question: RegExp) {
  return page.getByLabel(question).last();
}

test("request → form → PDF → ledger verified in the browser", async ({ page }) => {
  test.setTimeout(120_000);
  const getErrors = collectPageErrors(page);
  await page.setViewportSize({ width: 1440, height: 900 });

  const session = await loginViaBackend();
  await primeSession(page, session);
  await page.goto("/home");

  const composer = page.getByRole("textbox", { name: "Scrie un mesaj pentru asistent" });
  await expect(composer).toBeVisible({ timeout: 20_000 });

  /** Type a message once the previous turn has finished streaming (the
   * composer is disabled while one runs) and wait for it in the log. A
   * re-render can clear the draft between fill and click (the send button
   * then stays disabled), so fill-and-send is retried until it goes out. */
  async function say(text: string): Promise<void> {
    const send = page.getByRole("button", { name: "Trimite mesajul" });
    await expect(async () => {
      await expect(composer).toBeEnabled();
      await composer.fill(text);
      await send.click({ timeout: 2_000 });
    }).toPass({ timeout: 30_000 });
    await expect(page.getByRole("log").getByRole("listitem").filter({ hasText: text })).toBeVisible();
  }

  await say("vreau să-mi schimb domiciliul");

  // The offline agent finds the procedure and asks to confirm it.
  const confirmMatch = widget(page, /Completăm/);
  await expect(confirmMatch).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".bubble-agent").first()).toContainText("Schimbare domiciliu");
  await shot(page, "01-match");
  await confirmMatch.getByRole("button", { name: "Da" }).click();
  // Opening the document moves the page to /r/<id>, which re-mounts the chat.
  await page.waitForURL(/\/r\/[0-9a-f-]+$/, { timeout: 30_000 });

  // Profile fields are prefilled; it asks only for what is missing.
  const ownership = widget(page, /Tip proprietate/);
  await expect(ownership).toBeVisible({ timeout: 30_000 });
  await say("Str. Lungă 3, Cluj-Napoca");
  await expect(
    page.getByRole("complementary").getByRole("row", { name: /Adresă nouă Str. Lungă 3/ }),
  ).toBeVisible({ timeout: 30_000 });
  await shot(page, "02-filling");
  await ownership.getByRole("button", { name: "proprietar" }).click();

  // Review gate: the citizen confirms the filled form before any delivery.
  const review = widget(page, /Verifică datele/);
  await expect(review).toBeVisible({ timeout: 30_000 });
  await review.scrollIntoViewIfNeeded();
  await shot(page, "03-review");
  await review.getByRole("button", { name: "Da" }).click();

  const deliveryChoice = widget(page, /Cum vrei/);
  await expect(deliveryChoice).toBeVisible({ timeout: 30_000 });
  await deliveryChoice.getByRole("button", { name: "Salvare PDF" }).click();

  // pdflatex renders the form; the agent reports the reference.
  const doneBubble = page.locator(".bubble-agent").filter({ hasText: /CV-[0-9A-F]{4}-[0-9A-F]{4}/ });
  await expect(doneBubble.first()).toBeVisible({ timeout: 60_000 });
  const ref = ((await doneBubble.first().textContent()) ?? "").match(/CV-[0-9A-F]{4}-[0-9A-F]{4}/)![0];
  await shot(page, "04-done");

  // Documentele mele → this document → its history, re-derived and
  // signature-checked by this browser (WebCrypto), not taken from the server.
  await page.getByRole("button", { name: /Documentele mele/ }).click();
  await page.getByRole("button", { name: new RegExp(`număr ${ref}`) }).click();
  // The detail panel slides in over the page; wait until it is fully open.
  await page.waitForFunction(() => {
    const panel = document.querySelector("section.doc-detail.is-open");
    return panel !== null && Math.abs(panel.getBoundingClientRect().left) < 1;
  });
  const status = page.getByRole("status").filter({ hasText: "Verificat în browserul tău" });
  await expect(status).toBeVisible({ timeout: 30_000 });
  await status.scrollIntoViewIfNeeded();
  await expect(status).toContainText("lanț intact");
  await expect(status).toContainText("Amprenta PDF (SHA-256)");
  await shot(page, "05-ledger-verified");

  const fatal = getErrors().filter((e) => !e.includes("favicon"));
  expect(fatal, `unexpected console errors: ${fatal.join("\n")}`).toEqual([]);
});
