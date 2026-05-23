import type { Page, Request } from "@playwright/test";

const API_BASE = process.env.API_BASE ?? "http://127.0.0.1:8000";
const DEFAULT_PERSONA = "maria-ionescu";

export type AuthedSession = {
  access_token: string;
  citizen_id: string;
};

/** Hit the backend directly to mint a fresh demo session, bypassing the
 * UI's two-step ROeID + OTP dance. The login button + OTP code path is
 * covered by dedicated tests; everything else just wants a logged-in
 * page so it can exercise the feature under test. */
export async function loginViaBackend(
  persona: string = DEFAULT_PERSONA,
): Promise<AuthedSession> {
  const challenge = await fetch(`${API_BASE}/auth/login-roeid`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ persona_id: persona }),
  });
  if (!challenge.ok) {
    throw new Error(
      `login-roeid failed: ${challenge.status} ${await challenge.text()}`,
    );
  }
  const { challenge_id } = (await challenge.json()) as {
    challenge_id: string;
    phone_hint: string;
  };
  const otp = await fetch(`${API_BASE}/auth/otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ challenge_id, code: "123456" }),
  });
  if (!otp.ok) {
    throw new Error(`otp failed: ${otp.status} ${await otp.text()}`);
  }
  return (await otp.json()) as AuthedSession;
}

/** Drop an authed session into the page's localStorage so subsequent
 * routes treat the user as logged in. Must be called BEFORE navigating
 * to any protected route (AccessGate redirects unauthed users to /login). */
export async function primeSession(
  page: Page,
  session: AuthedSession,
): Promise<void> {
  // First navigate to the origin so we have a real window to write
  // localStorage on (a blank page about:blank has no localStorage).
  await page.goto("/");
  await page.evaluate((s) => {
    window.localStorage.setItem("civicai.session", JSON.stringify(s));
  }, session);
}

/** Wait for one outbound POST /agent/chat/stream and assert the response
 * is a 200 SSE stream — surfaces 4xx/5xx as a fast failure instead of a
 * timeout-on-empty-bubble. */
export async function expectChatStream(
  page: Page,
  trigger: () => Promise<void>,
): Promise<void> {
  const waitForStream = page.waitForResponse(
    (resp) =>
      resp.url().includes("/agent/chat/stream") && resp.request().method() === "POST",
    { timeout: 30_000 },
  );
  await trigger();
  const resp = await waitForStream;
  if (resp.status() !== 200) {
    const body = await resp.text().catch(() => "<no body>");
    throw new Error(
      `agent/chat/stream returned ${resp.status()}: ${body.slice(0, 500)}`,
    );
  }
}

/** Console / pageerror sink — append every console.error and unhandled
 * exception so a test can assert that nothing went sideways outside its
 * happy path. Returns a getter for the collected error lines. */
export function collectPageErrors(page: Page): () => string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`[console] ${msg.text()}`);
  });
  page.on("pageerror", (err) => {
    errors.push(`[pageerror] ${err.message}`);
  });
  page.on("requestfailed", (req: Request) => {
    const fail = req.failure()?.errorText ?? "unknown";
    // ERR_ABORTED fires when Next.js cancels an in-flight RSC fetch during a
    // client-side navigation (e.g. when /home pushes the user back to /login
    // mid-fetch). It's noise, not an app bug.
    if (fail.includes("ERR_ABORTED")) return;
    errors.push(`[requestfailed] ${req.method()} ${req.url()} — ${fail}`);
  });
  return () => errors.slice();
}
