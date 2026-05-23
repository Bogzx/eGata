# CivicAI — Plan 1: Frontend Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deployed Next.js frontend with all citizen-facing surfaces wired to mock data, ready to integrate with the real backend at Checkpoint 1.

**Architecture:** Single Next.js 15 codebase, App Router, Tailwind + shadcn + framer-motion. MSW for mocks during Wave 1. Vercel deploy.

**Tech Stack:** Next.js 15, TypeScript (strict), Tailwind CSS, shadcn/ui, framer-motion, tesseract.js, mrz, MSW, Vitest + Testing Library, Playwright.

**Dependencies:** None (parallel with Plan 2). Consumes the OpenAPI contract from `contracts/openapi.yaml` (frozen via roadmap §3).

**Interfaces with other plans:**
- Plan 2 ships the FastAPI backend including a mock `/agent/chat`. Until Checkpoint 1, Plan 1 mocks all calls via MSW against the contract in roadmap §3.
- Plan 3 replaces `frontend/lib/useVoiceAgent.ts` — Plan 1 ships a stub with the exact signature from roadmap §4.
- Plan 4 wires the accessibility toggle behaviors — Plan 1 ships the toggles as UI-only.

---

### Task 1: Scaffold Next.js 15 + TypeScript strict + Tailwind

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/.eslintrc.json`
- Create: `frontend/.prettierrc.json`
- Create: `frontend/.gitignore`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx` (temporary placeholder)
- Create: `frontend/app/globals.css`

- [ ] **Step 1: Initialize Next.js 15 app via create-next-app**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
npx --yes create-next-app@15 frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias "@/*" --use-npm --no-turbopack
```

Expected output: `Success! Created frontend at ...`. Confirms `frontend/package.json`, `frontend/app/`, `frontend/tailwind.config.ts` exist.

- [ ] **Step 2: Enforce TypeScript strict mode**

Open `frontend/tsconfig.json` and ensure `"strict": true`, add `"noUncheckedIndexedAccess": true` and `"noFallthroughCasesInSwitch": true` under `compilerOptions`.

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noFallthroughCasesInSwitch": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Add Prettier config**

Create `frontend/.prettierrc.json`:

```json
{
  "semi": true,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "all",
  "printWidth": 100,
  "plugins": ["prettier-plugin-tailwindcss"]
}
```

- [ ] **Step 4: Install dev/runtime deps**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npm install framer-motion clsx tailwind-merge class-variance-authority lucide-react @radix-ui/react-slot @radix-ui/react-label @radix-ui/react-dialog @radix-ui/react-toast tesseract.js mrz zustand
npm install -D prettier prettier-plugin-tailwindcss msw vitest @vitejs/plugin-react @vitest/ui jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @playwright/test @axe-core/playwright @types/node
```

Verify `package.json` lists all of the above.

- [ ] **Step 5: Wire npm scripts**

Edit `frontend/package.json` `scripts` section to:

```json
{
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "format": "prettier --write .",
  "typecheck": "tsc --noEmit",
  "test": "vitest run",
  "test:watch": "vitest",
  "e2e": "playwright test",
  "e2e:install": "playwright install --with-deps chromium"
}
```

- [ ] **Step 6: Verify build is green**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npm run typecheck
npm run lint
npm run build
```

Expected: `Compiled successfully`. If errors come from default `app/page.tsx`, ignore — Task 14 replaces it.

- [ ] **Step 7: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/
git commit -m "feat(plan-1): scaffold Next.js 15 + TS strict + Tailwind"
```

---

### Task 2: Initialize shadcn/ui + base components

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/lib/utils.ts`
- Create: `frontend/components/ui/button.tsx`
- Create: `frontend/components/ui/input.tsx`
- Create: `frontend/components/ui/label.tsx`
- Create: `frontend/components/ui/card.tsx`
- Create: `frontend/components/ui/dialog.tsx`
- Create: `frontend/components/ui/toast.tsx`
- Create: `frontend/components/ui/badge.tsx`
- Create: `frontend/components/ui/separator.tsx`
- Create: `frontend/components/ui/textarea.tsx`
- Modify: `frontend/app/globals.css` (add shadcn CSS variables)

- [ ] **Step 1: Initialize shadcn**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npx --yes shadcn@latest init --yes --defaults --css app/globals.css --base-color slate --no-rsc
```

Expected: writes `components.json` and patches `tailwind.config.ts` + `app/globals.css` with the shadcn theme variables.

- [ ] **Step 2: Add primitives**

```bash
npx --yes shadcn@latest add button input label card dialog toast badge separator textarea --yes --overwrite
```

Verify each file exists under `frontend/components/ui/`.

- [ ] **Step 3: Sanity-render a button to confirm shadcn works**

Replace `frontend/app/page.tsx` with:

```tsx
import { Button } from "@/components/ui/button";

export default function Page() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background text-foreground">
      <Button>CivicAI</Button>
    </main>
  );
}
```

Run `npm run build`. Expected: green build.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/
git commit -m "feat(plan-1): add shadcn/ui primitives"
```

---

### Task 3: Vitest + Testing Library setup

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/tests/sanity.test.tsx`

- [ ] **Step 1: Write vitest.config.ts**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./") },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    css: false,
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
  },
});
```

- [ ] **Step 2: Write vitest.setup.ts**

```ts
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 3: Write a sanity test that should pass**

`frontend/tests/sanity.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/button";

describe("sanity", () => {
  it("renders a shadcn button", () => {
    render(<Button>CivicAI</Button>);
    expect(screen.getByRole("button", { name: "CivicAI" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run tests**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npm run test
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/
git commit -m "test(plan-1): wire vitest + testing-library"
```

---

### Task 4: Playwright setup

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/smoke.spec.ts`

- [ ] **Step 1: Install browsers**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npm run e2e:install
```

- [ ] **Step 2: Write playwright.config.ts**

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    locale: "ro-RO",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
```

- [ ] **Step 3: Write smoke E2E**

`frontend/e2e/smoke.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("home page renders CivicAI button", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "CivicAI" })).toBeVisible();
});
```

- [ ] **Step 4: Run Playwright smoke**

```bash
npm run e2e
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/
git commit -m "test(plan-1): wire playwright smoke"
```

---

### Task 5: Shared TypeScript types

**Files:**
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/types.test.ts`

- [ ] **Step 1: Write a failing type test**

`frontend/lib/types.test.ts`:

```ts
import { describe, it, expectTypeOf } from "vitest";
import type {
  Citizen,
  CitizenAttributes,
  Procedure,
  ProcedureField,
  NextStep,
  Document,
  LedgerEntry,
  Reminder,
  ChatToolCall,
  VoicePreferences,
} from "./types";

describe("types", () => {
  it("Document.status is the literal union", () => {
    expectTypeOf<Document["status"]>().toEqualTypeOf<"draft" | "finalized">();
  });

  it("LedgerEntry.event_type covers all 6 events", () => {
    expectTypeOf<LedgerEntry["event_type"]>().toEqualTypeOf<
      | "doc_created"
      | "completed_draft"
      | "pdf_generated"
      | "delivered"
      | "redirected"
      | "reminder_created"
    >();
  });

  it("CitizenAttributes.marital_status accepts 4 RO values", () => {
    const ok: CitizenAttributes["marital_status"] = "căsătorit";
    expectTypeOf(ok).toEqualTypeOf<
      "necăsătorit" | "căsătorit" | "divorțat" | "văduv" | undefined
    >();
  });

  it("Procedure.scope is union", () => {
    expectTypeOf<Procedure["scope"]>().toEqualTypeOf<"primarie" | "external">();
  });

  it("NextStep.kind union", () => {
    expectTypeOf<NextStep["kind"]>().toEqualTypeOf<
      "in_scope_procedure" | "external_redirect"
    >();
  });

  it("Reminder.status union", () => {
    expectTypeOf<Reminder["status"]>().toEqualTypeOf<
      "pending" | "started" | "done" | "dismissed"
    >();
  });

  it("ChatToolCall has the right shape", () => {
    const tc: ChatToolCall = { name: "lookup_procedure", arguments: { query: "x" } };
    expectTypeOf(tc).toMatchTypeOf<ChatToolCall>();
  });

  it("VoicePreferences flags are optional booleans", () => {
    expectTypeOf<VoicePreferences>().toMatchTypeOf<{
      simple_language?: boolean;
      voice_only?: boolean;
    }>();
  });

  it("ProcedureField.options is optional", () => {
    const f: ProcedureField = {
      name: "tip_proprietate",
      label: "Tip proprietate",
      source: "ask",
      required: true,
    };
    expectTypeOf(f.options).toEqualTypeOf<string[] | undefined>();
  });

  it("Citizen.id is string", () => {
    expectTypeOf<Citizen["id"]>().toEqualTypeOf<string>();
  });
});
```

Run `npm run test` — file `types.ts` doesn't exist yet, so test fails to import. That's the red.

- [ ] **Step 2: Write `frontend/lib/types.ts`**

```ts
export type Citizen = {
  id: string;
  cnp: string;
  nume: string;
  prenume: string;
  data_nasterii: string;
  email: string;
  phone: string;
  attributes: CitizenAttributes;
};

export type CitizenAttributes = {
  owns_vehicle?: boolean;
  marital_status?: "necăsătorit" | "căsătorit" | "divorțat" | "văduv";
  has_children?: boolean;
  employer?: string;
  medic_familie?: string;
  preferred_language?: "ro" | "en";
  current_address?: string;
  accessibility?: {
    voice_only?: boolean;
    simple_language?: boolean;
    large_text?: boolean;
  };
};

export type Procedure = {
  id: string;
  title: string;
  description: string;
  scope: "primarie" | "external";
  category: string;
  synonyms: string[];
  sample_queries: string[];
  fields: ProcedureField[];
  template: string;
  next_steps: NextStep[];
};

export type ProcedureField = {
  name: string;
  label: string;
  source: string;
  required: boolean;
  options?: string[];
  suggest_default?: string;
  redact_in_voice?: boolean;
};

export type NextStep = {
  kind: "in_scope_procedure" | "external_redirect";
  procedure_id?: string;
  redirect_target?: string;
  deadline_days?: number;
  title: string;
  applies_if?: string;
};

export type Document = {
  id: string;
  citizen_id: string;
  procedure_id: string;
  status: "draft" | "finalized";
  fields: Record<string, unknown>;
  pdf_url?: string;
  delivery?: "save" | "send" | "print";
  ref_number?: string;
  created_at: string;
  delivered_at?: string;
};

export type LedgerEntry = {
  id: number;
  event_type:
    | "doc_created"
    | "completed_draft"
    | "pdf_generated"
    | "delivered"
    | "redirected"
    | "reminder_created";
  payload_hash: string;
  prev_hash: string;
  row_hash: string;
  created_at: string;
};

export type LedgerResponse = {
  entries: LedgerEntry[];
  verified: boolean;
};

export type Reminder = {
  id: string;
  citizen_id: string;
  trigger_doc_id?: string;
  kind: "in_scope_procedure" | "external_redirect";
  procedure_id?: string;
  redirect_target?: string;
  title: string;
  due_date?: string;
  status: "pending" | "started" | "done" | "dismissed";
  created_at: string;
};

export type ChatToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type VoicePreferences = {
  simple_language?: boolean;
  voice_only?: boolean;
};

export type LoginChallenge = {
  challenge_id: string;
  phone_hint: string;
};

export type AuthSession = {
  access_token: string;
  citizen_id: string;
};

export type ProcedureLookupMatch = {
  procedure_id: string;
  title: string;
  score: number;
};

export type ProcedureLookupResponse = {
  matches: ProcedureLookupMatch[];
  redirect_candidate: string | null;
};

export type ChatMessage = {
  role: "user" | "agent";
  text: string;
  tool_calls?: ChatToolCall[];
};

export type ChatResponse = {
  conversation_id: string;
  message: string;
  tool_calls: ChatToolCall[];
};
```

- [ ] **Step 3: Run tests — expect green**

```bash
npm run test
```

Expected: all `types.test.ts` cases pass.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/lib/types.ts frontend/lib/types.test.ts
git commit -m "feat(plan-1): shared TypeScript types matching OpenAPI contract"
```

---

### Task 6: API client

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/api.test.ts`
- Create: `frontend/lib/session.ts`
- Create: `frontend/.env.local.example`

- [ ] **Step 1: Write session storage helper**

`frontend/lib/session.ts`:

```ts
const KEY = "civicai.session";

export type StoredSession = {
  access_token: string;
  citizen_id: string;
};

export function getSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

export function setSession(s: StoredSession): void {
  window.localStorage.setItem(KEY, JSON.stringify(s));
}

export function clearSession(): void {
  window.localStorage.removeItem(KEY);
}
```

- [ ] **Step 2: Write a failing API client test**

`frontend/lib/api.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { api, ApiError } from "./api";

describe("api client", () => {
  const fetchSpy = vi.fn();

  beforeEach(() => {
    fetchSpy.mockReset();
    vi.stubGlobal("fetch", fetchSpy);
    vi.stubGlobal("localStorage", {
      getItem: () => JSON.stringify({ access_token: "tok", citizen_id: "cid" }),
      setItem: () => {},
      removeItem: () => {},
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POST /auth/login-roeid sends persona_id", async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ challenge_id: "ch1", phone_hint: "***1234" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const r = await api.loginRoeid({ persona_id: "maria-ionescu" });
    expect(r.challenge_id).toBe("ch1");
    const [, init] = fetchSpy.mock.calls[0]!;
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      persona_id: "maria-ionescu",
    });
  });

  it("GET /citizens/me sends Authorization header", async () => {
    fetchSpy.mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "u1",
          cnp: "1",
          nume: "X",
          prenume: "Y",
          data_nasterii: "1985-03-14",
          email: "x@y",
          phone: "+40",
          attributes: {},
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await api.getCitizenMe();
    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get("Authorization")).toBe("Bearer tok");
  });

  it("non-2xx throws ApiError", async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ detail: "nope" }), { status: 400 }),
    );
    await expect(api.getCitizenMe()).rejects.toBeInstanceOf(ApiError);
  });
});
```

Run `npm run test` — fails (no `api.ts`). Red.

- [ ] **Step 3: Write the API client**

`frontend/lib/api.ts`:

```ts
import { getSession } from "./session";
import type {
  AuthSession,
  Citizen,
  ChatResponse,
  Document,
  LedgerResponse,
  LoginChallenge,
  Procedure,
  ProcedureLookupResponse,
  VoicePreferences,
} from "./types";

const BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

type ReqOpts = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
};

async function request<T>(path: string, opts: ReqOpts = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const s = getSession();
    if (s) headers["Authorization"] = `Bearer ${s.access_token}`;
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, parsed, `${method} ${path} → ${res.status}`);
  }
  return parsed as T;
}

export const api = {
  loginRoeid: (b: { persona_id?: string }) =>
    request<LoginChallenge>("/auth/login-roeid", { method: "POST", body: b, auth: false }),

  loginMrz: (b: { cnp: string; nume: string; prenume: string }) =>
    request<LoginChallenge>("/auth/login-mrz", { method: "POST", body: b, auth: false }),

  otp: (b: { challenge_id: string; code: string }) =>
    request<AuthSession>("/auth/otp", { method: "POST", body: b, auth: false }),

  getCitizenMe: () => request<Citizen>("/citizens/me"),

  lookupProcedure: (b: { query: string }) =>
    request<ProcedureLookupResponse>("/procedures/lookup", { method: "POST", body: b }),

  listProcedures: () => request<Procedure[]>("/procedures"),

  getProcedure: (id: string) => request<Procedure>(`/procedures/${id}`),

  createDocument: (b: { procedure_id: string }) =>
    request<Document>("/documents", { method: "POST", body: b }),

  getDocument: (id: string) => request<Document>(`/documents/${id}`),

  listDocuments: () => request<Document[]>("/documents"),

  patchDocumentFields: (id: string, fields: Record<string, unknown>) =>
    request<Document>(`/documents/${id}/fields`, { method: "PATCH", body: { fields } }),

  generatePdf: (id: string) =>
    request<{ pdf_url: string }>(`/documents/${id}/generate-pdf`, { method: "POST" }),

  deliverDocument: (id: string, delivery: "save" | "send" | "print") =>
    request<Document>(`/documents/${id}/deliver`, { method: "POST", body: { delivery } }),

  getDocumentLedger: (id: string) =>
    request<LedgerResponse>(`/documents/${id}/ledger`),

  chat: (b: {
    conversation_id?: string | null;
    document_id?: string;
    message: string;
    preferences?: VoicePreferences;
  }) => request<ChatResponse>("/agent/chat", { method: "POST", body: b }),
};
```

- [ ] **Step 3b: Write env example**

`frontend/.env.local.example`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_DEMO_MODE=1
NEXT_PUBLIC_USE_MOCKS=1
```

Copy to `frontend/.env.local` locally; commit only the example file.

- [ ] **Step 4: Run tests — expect green**

```bash
npm run test
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/lib/api.ts frontend/lib/api.test.ts frontend/lib/session.ts frontend/.env.local.example
git commit -m "feat(plan-1): typed API client + session storage"
```

---

### Task 7: MSW handlers + fixtures

**Files:**
- Create: `frontend/mocks/fixtures.ts`
- Create: `frontend/mocks/handlers.ts`
- Create: `frontend/mocks/browser.ts`
- Create: `frontend/mocks/server.ts`
- Create: `frontend/mocks/handlers.test.ts`
- Create: `frontend/public/mockServiceWorker.js` (generated)
- Create: `frontend/components/MockProvider.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Generate the MSW service worker**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npx --yes msw init public/ --save
```

Confirm `frontend/public/mockServiceWorker.js` exists.

- [ ] **Step 2: Write demo fixtures**

`frontend/mocks/fixtures.ts`:

```ts
import type { Citizen, Document, LedgerResponse, Procedure, Reminder } from "@/lib/types";

export const maria: Citizen = {
  id: "00000000-0000-0000-0000-000000000001",
  cnp: "2851014123456",
  nume: "Ionescu",
  prenume: "Maria",
  data_nasterii: "1985-03-14",
  email: "maria@example.com",
  phone: "+40712345678",
  attributes: {
    owns_vehicle: true,
    marital_status: "necăsătorit",
    has_children: false,
    employer: "SC Acme SRL",
    medic_familie: "Dr. Popescu, Cluj",
    preferred_language: "ro",
    current_address: "Str. Avram Iancu 5, Cluj-Napoca",
    accessibility: { voice_only: false, simple_language: false, large_text: false },
  },
};

export const schimbareDomiciliu: Procedure = {
  id: "schimbare-domiciliu",
  title: "Schimbare domiciliu",
  description: "Înscrierea mențiunii de stabilire a domiciliului",
  scope: "primarie",
  category: "evidenta-persoanelor",
  synonyms: ["mutare", "schimbat adresa", "domiciliu nou"],
  sample_queries: [
    "vreau să-mi schimb domiciliul",
    "m-am mutat la altă adresă",
    "trebuie să schimb adresa pe buletin",
  ],
  fields: [
    { name: "nume_complet", label: "Nume complet", source: "id_scan|profile", required: true },
    { name: "cnp", label: "CNP", source: "id_scan|profile", required: true, redact_in_voice: true },
    { name: "adresa_curenta", label: "Adresă curentă", source: "id_scan|profile", required: true },
    { name: "adresa_noua", label: "Adresă nouă", source: "ask", required: true },
    {
      name: "tip_proprietate",
      label: "Tip proprietate",
      source: "ask",
      options: ["proprietar", "chiriaș", "găzduit"],
      required: true,
    },
    {
      name: "motivul",
      label: "Motivul cererii",
      source: "ask",
      suggest_default: "Schimbare loc de muncă",
      required: false,
    },
  ],
  template: "schimbare-domiciliu.tex",
  next_steps: [
    {
      kind: "in_scope_procedure",
      procedure_id: "preschimbare-ci",
      deadline_days: 15,
      title: "Preschimbare carte de identitate",
    },
    {
      kind: "external_redirect",
      redirect_target: "DRPCIV",
      deadline_days: 30,
      title: "Actualizare certificat înmatriculare auto",
      applies_if: "owns_vehicle == true",
    },
    { kind: "external_redirect", redirect_target: "CNAS", title: "Actualizare medic de familie" },
    {
      kind: "external_redirect",
      redirect_target: "ANAF",
      title: "Notificare schimbare domiciliu fiscal",
    },
  ],
};

export const knownProcedures: Procedure[] = [
  schimbareDomiciliu,
  {
    id: "preschimbare-ci",
    title: "Preschimbare carte de identitate",
    description: "Preschimbarea cărții de identitate",
    scope: "primarie",
    category: "evidenta-persoanelor",
    synonyms: ["buletin nou", "schimb buletin"],
    sample_queries: ["vreau să-mi schimb buletinul"],
    fields: [
      { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
      { name: "cnp", label: "CNP", source: "profile", required: true },
    ],
    template: "preschimbare-ci.tex",
    next_steps: [],
  },
];

const now = new Date().toISOString();

export const draftDoc: Document = {
  id: "11111111-1111-1111-1111-111111111111",
  citizen_id: maria.id,
  procedure_id: "schimbare-domiciliu",
  status: "draft",
  fields: {
    nume_complet: "Maria Ionescu",
    cnp: "2851014123456",
    adresa_curenta: "Str. Avram Iancu 5, Cluj-Napoca",
  },
  created_at: now,
};

export const deliveredDoc: Document = {
  id: "22222222-2222-2222-2222-222222222222",
  citizen_id: maria.id,
  procedure_id: "certificat-fiscal",
  status: "finalized",
  fields: { nume_complet: "Maria Ionescu", scopul: "credit bancar" },
  delivery: "send",
  ref_number: "CV-A4B7",
  pdf_url: "https://example.com/doc-2222.pdf",
  created_at: now,
  delivered_at: now,
};

export const ledgerFor = (docId: string): LedgerResponse => ({
  entries: [
    {
      id: 1,
      event_type: "doc_created",
      payload_hash: "0xpayloaddoc",
      prev_hash: "0x0000000000000000000000000000000000000000000000000000000000000000",
      row_hash: "0xrow1",
      created_at: now,
    },
    {
      id: 2,
      event_type: "completed_draft",
      payload_hash: "0xpayloadcompleted",
      prev_hash: "0xrow1",
      row_hash: "0xrow2",
      created_at: now,
    },
    {
      id: 3,
      event_type: "pdf_generated",
      payload_hash: "0xpayloadpdf",
      prev_hash: "0xrow2",
      row_hash: "0xrow3",
      created_at: now,
    },
    {
      id: 4,
      event_type: "delivered",
      payload_hash: "0xpayloaddelivered",
      prev_hash: "0xrow3",
      row_hash: "0xrow4",
      created_at: now,
    },
  ],
  verified: true,
});

export const seededReminders: Reminder[] = [
  {
    id: "r1",
    citizen_id: maria.id,
    kind: "in_scope_procedure",
    procedure_id: "preschimbare-ci",
    title: "Cartea de identitate expiră în 23 de zile",
    due_date: "2026-06-15",
    status: "pending",
    created_at: now,
  },
  {
    id: "r2",
    citizen_id: maria.id,
    kind: "external_redirect",
    redirect_target: "DRPCIV",
    title: "Actualizare certificat înmatriculare auto",
    due_date: "2026-06-22",
    status: "pending",
    created_at: now,
  },
];

export function pickAgentReply(message: string): { text: string; tool_calls: { name: string; arguments: Record<string, unknown> }[] } {
  const m = message.toLowerCase();
  if (m.includes("domic") || m.includes("mutare") || m.includes("adresa")) {
    return {
      text: "Înțeleg că vrei să-ți schimbi domiciliul. Continuăm?",
      tool_calls: [{ name: "lookup_procedure", arguments: { query: message } }],
    };
  }
  if (m.includes("anaf") || m.includes("taxa") || m.includes("impozit")) {
    return {
      text: "Asta nu e treaba primăriei — vă rog vizitați ghiseul.ro pentru ANAF.",
      tool_calls: [{ name: "find_redirect", arguments: { query: message } }],
    };
  }
  if (m.includes("adres") && m.includes("nou")) {
    return {
      text: "Am notat noua adresă. Care e tipul de proprietate: proprietar, chiriaș sau găzduit?",
      tool_calls: [{ name: "set_field", arguments: { field: "adresa_noua", value: message } }],
    };
  }
  return {
    text: "Spune-mi te rog mai multe despre ce ai nevoie de la primărie.",
    tool_calls: [],
  };
}
```

- [ ] **Step 3: Write the handlers**

`frontend/mocks/handlers.ts`:

```ts
import { http, HttpResponse } from "msw";
import {
  deliveredDoc,
  draftDoc,
  knownProcedures,
  ledgerFor,
  maria,
  pickAgentReply,
  schimbareDomiciliu,
  seededReminders,
} from "./fixtures";
import type { Document } from "@/lib/types";

const BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "http://localhost:8000";

const documents = new Map<string, Document>();
documents.set(draftDoc.id, { ...draftDoc });
documents.set(deliveredDoc.id, { ...deliveredDoc });

let docCounter = 100;

export const handlers = [
  http.post(`${BASE}/auth/login-roeid`, async ({ request }) => {
    const body = (await request.json()) as { persona_id?: string };
    return HttpResponse.json({
      challenge_id: `ch_roeid_${body.persona_id ?? "default"}`,
      phone_hint: "***5678",
    });
  }),

  http.post(`${BASE}/auth/login-mrz`, async ({ request }) => {
    const body = (await request.json()) as { cnp: string };
    return HttpResponse.json({
      challenge_id: `ch_mrz_${body.cnp.slice(-4)}`,
      phone_hint: "***5678",
    });
  }),

  http.post(`${BASE}/auth/otp`, async ({ request }) => {
    const body = (await request.json()) as { code: string };
    if (body.code !== "123456") {
      return HttpResponse.json({ detail: "Cod OTP incorect" }, { status: 401 });
    }
    return HttpResponse.json({
      access_token: "mock-token-maria",
      citizen_id: maria.id,
    });
  }),

  http.get(`${BASE}/citizens/me`, () => HttpResponse.json(maria)),

  http.post(`${BASE}/procedures/lookup`, async ({ request }) => {
    const body = (await request.json()) as { query: string };
    const q = body.query.toLowerCase();
    if (q.includes("anaf") || q.includes("taxa") || q.includes("impozit")) {
      return HttpResponse.json({ matches: [], redirect_candidate: "ANAF" });
    }
    const score = q.includes("domic") || q.includes("mutare") || q.includes("adresa") ? 0.92 : 0.32;
    return HttpResponse.json({
      matches:
        score > 0.5
          ? [
              { procedure_id: "schimbare-domiciliu", title: "Schimbare domiciliu", score },
              { procedure_id: "preschimbare-ci", title: "Preschimbare CI", score: 0.41 },
            ]
          : [],
      redirect_candidate: score > 0.5 ? null : "ANAF",
    });
  }),

  http.get(`${BASE}/procedures`, () => HttpResponse.json(knownProcedures)),

  http.get(`${BASE}/procedures/:id`, ({ params }) => {
    const p = knownProcedures.find((x) => x.id === params.id);
    if (!p) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(p);
  }),

  http.post(`${BASE}/documents`, async ({ request }) => {
    const body = (await request.json()) as { procedure_id: string };
    docCounter += 1;
    const id = `33333333-3333-3333-3333-${String(docCounter).padStart(12, "0")}`;
    const doc: Document = {
      id,
      citizen_id: maria.id,
      procedure_id: body.procedure_id,
      status: "draft",
      fields:
        body.procedure_id === schimbareDomiciliu.id
          ? {
              nume_complet: "Maria Ionescu",
              cnp: "2851014123456",
              adresa_curenta: "Str. Avram Iancu 5, Cluj-Napoca",
            }
          : { nume_complet: "Maria Ionescu", cnp: "2851014123456" },
      created_at: new Date().toISOString(),
    };
    documents.set(id, doc);
    return HttpResponse.json(doc, { status: 201 });
  }),

  http.get(`${BASE}/documents`, () =>
    HttpResponse.json(Array.from(documents.values()).filter((d) => d.citizen_id === maria.id)),
  ),

  http.get(`${BASE}/documents/:id`, ({ params }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(d);
  }),

  http.patch(`${BASE}/documents/:id/fields`, async ({ params, request }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body = (await request.json()) as { fields: Record<string, unknown> };
    const updated: Document = { ...d, fields: { ...d.fields, ...body.fields } };
    documents.set(updated.id, updated);
    return HttpResponse.json(updated);
  }),

  http.post(`${BASE}/documents/:id/generate-pdf`, ({ params }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const url = `https://example.com/doc-${d.id}.pdf`;
    documents.set(d.id, { ...d, pdf_url: url });
    return HttpResponse.json({ pdf_url: url });
  }),

  http.post(`${BASE}/documents/:id/deliver`, async ({ params, request }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body = (await request.json()) as { delivery: "save" | "send" | "print" };
    const updated: Document = {
      ...d,
      status: "finalized",
      delivery: body.delivery,
      ref_number: `CV-${d.id.slice(0, 4).toUpperCase()}`,
      delivered_at: new Date().toISOString(),
    };
    documents.set(d.id, updated);
    return HttpResponse.json(updated);
  }),

  http.get(`${BASE}/documents/:id/ledger`, ({ params }) =>
    HttpResponse.json(ledgerFor(String(params.id))),
  ),

  http.post(`${BASE}/agent/chat`, async ({ request }) => {
    const body = (await request.json()) as {
      conversation_id?: string | null;
      message: string;
    };
    const reply = pickAgentReply(body.message);
    return HttpResponse.json({
      conversation_id: body.conversation_id ?? "conv_mock_1",
      message: reply.text,
      tool_calls: reply.tool_calls,
    });
  }),

  http.get(`${BASE}/reminders`, () => HttpResponse.json(seededReminders)),
];
```

- [ ] **Step 4: Write browser and server bootstraps**

`frontend/mocks/browser.ts`:

```ts
import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
```

`frontend/mocks/server.ts`:

```ts
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

- [ ] **Step 5: Write a handlers test (node SSR-side)**

`frontend/mocks/handlers.test.ts`:

```ts
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

describe("MSW handlers", () => {
  it("login-roeid returns challenge", async () => {
    const r = await fetch(`${BASE}/auth/login-roeid`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona_id: "maria-ionescu" }),
    });
    const json = (await r.json()) as { challenge_id: string };
    expect(json.challenge_id).toContain("ch_roeid_maria-ionescu");
  });

  it("otp with 123456 issues token", async () => {
    const r = await fetch(`${BASE}/auth/otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ challenge_id: "ch", code: "123456" }),
    });
    expect(r.status).toBe(200);
    const json = (await r.json()) as { access_token: string };
    expect(json.access_token).toBe("mock-token-maria");
  });

  it("otp with wrong code rejects", async () => {
    const r = await fetch(`${BASE}/auth/otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ challenge_id: "ch", code: "000000" }),
    });
    expect(r.status).toBe(401);
  });

  it("agent chat returns canned RO reply for domiciliu", async () => {
    const r = await fetch(`${BASE}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "Vreau să-mi schimb domiciliul" }),
    });
    const json = (await r.json()) as { message: string };
    expect(json.message).toContain("schimbi domiciliul");
  });

  it("agent chat redirects for ANAF", async () => {
    const r = await fetch(`${BASE}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "Vreau să plătesc impozite la ANAF" }),
    });
    const json = (await r.json()) as { message: string };
    expect(json.message.toLowerCase()).toContain("ghiseul.ro");
  });
});
```

- [ ] **Step 6: Write the browser mount component**

`frontend/components/MockProvider.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

export function MockProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(
    process.env.NEXT_PUBLIC_USE_MOCKS !== "1",
  );

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_USE_MOCKS !== "1") return;
    let cancelled = false;
    void (async () => {
      const { worker } = await import("@/mocks/browser");
      await worker.start({ onUnhandledRequest: "warn", quiet: true });
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready) return null;
  return <>{children}</>;
}
```

- [ ] **Step 7: Mount the MockProvider in the root layout**

Replace `frontend/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { MockProvider } from "@/components/MockProvider";

export const metadata: Metadata = {
  title: "CivicAI — Asistentul tău digital la primărie",
  description: "Spune-i ce ai nevoie. Îți spune ce acte îți trebuie.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ro">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <MockProvider>{children}</MockProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 8: Run tests**

```bash
npm run test
```

Expected: all green including `handlers.test.ts`.

- [ ] **Step 9: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/mocks/ frontend/public/mockServiceWorker.js frontend/components/MockProvider.tsx frontend/app/layout.tsx
git commit -m "feat(plan-1): MSW handlers + fixtures for Wave 1"
```

---

### Task 8: Romanian i18n with standard/simple variants

**Files:**
- Create: `frontend/lib/i18n.ts`
- Create: `frontend/lib/i18n.test.ts`

- [ ] **Step 1: Write a failing test**

`frontend/lib/i18n.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { t, getVariant } from "./i18n";

describe("i18n", () => {
  it("returns standard variant by default", () => {
    expect(t("home.greeting", { prenume: "Maria" })).toContain("Bună ziua, Maria");
  });

  it("simple variant exists for greeting", () => {
    expect(t("home.greeting", { prenume: "Maria" }, "simple")).toContain("Salut, Maria");
  });

  it("missing key throws in dev", () => {
    expect(() => t("nope.does_not_exist" as never)).toThrow();
  });

  it("getVariant returns 'simple' when accessibility.simple_language=true", () => {
    expect(getVariant({ accessibility: { simple_language: true } })).toBe("simple");
    expect(getVariant({})).toBe("standard");
  });
});
```

- [ ] **Step 2: Write `i18n.ts`**

`frontend/lib/i18n.ts`:

```ts
import type { CitizenAttributes } from "./types";

type Variant = "standard" | "simple";

type Entry = { standard: string; simple?: string };

const strings = {
  "app.title": { standard: "CivicAI" },
  "app.tagline": {
    standard: "Spune-i ce ai nevoie. Îți spune ce acte îți trebuie.",
    simple: "Spune ce vrei. Te ajutăm cu actele.",
  },
  "login.title": { standard: "Conectare cu ROeID" },
  "login.subtitle": {
    standard: "Confirmă identitatea ca să continuăm.",
    simple: "Spune cine ești ca să mergem mai departe.",
  },
  "login.roeid_button": { standard: "Login cu ROeID" },
  "login.persona_label": { standard: "Persona demo (dev)" },
  "login.scan_id_button": { standard: "Scanează buletinul" },
  "login.manual_cnp_button": { standard: "Introdu CNP manual" },
  "otp.title": {
    standard: "Introdu codul primit prin SMS",
    simple: "Scrie codul primit pe telefon",
  },
  "otp.phone_hint": { standard: "Cod trimis la {{phone_hint}}" },
  "otp.submit": { standard: "Confirmă" },
  "otp.error": { standard: "Cod incorect. Mai încearcă o dată." },
  "home.greeting": {
    standard: "Bună ziua, {{prenume}}.",
    simple: "Salut, {{prenume}}!",
  },
  "home.recommended_title": {
    standard: "Următoarele acțiuni recomandate",
    simple: "Ce-ar fi bine să faci mai departe",
  },
  "home.documents_title": { standard: "Documente recente" },
  "home.start_new": { standard: "Începe o cerere nouă" },
  "req.title": { standard: "Cerere: {{title}}" },
  "req.auto_filled_intro": {
    standard: "Am completat din profilul tău:",
    simple: "Am pus aici lucrurile pe care le știam deja despre tine:",
  },
  "req.more_needed": {
    standard: "Mai am nevoie de {{count}} lucruri. Cum vrei să le completăm?",
    simple: "Mai trebuie să-mi spui {{count}} lucruri. Cum vrei să-mi spui?",
  },
  "mode.manual": { standard: "Manual" },
  "mode.guided": { standard: "Pe ecran" },
  "mode.voice": { standard: "Vocal" },
  "mode.switch": { standard: "Schimbă modul" },
  "chat.input_placeholder": {
    standard: "Scrie aici ce ai nevoie...",
    simple: "Spune cu cuvintele tale...",
  },
  "chat.send": { standard: "Trimite" },
  "delivery.save": { standard: "Salvează ca PDF" },
  "delivery.send": { standard: "Trimite la primărie" },
  "delivery.print": { standard: "Tipărește" },
  "delivery.confirmation": {
    standard: "Cererea ta a fost trimisă. Număr de înregistrare: {{ref}}",
    simple: "Gata! Numărul cererii tale este {{ref}}.",
  },
  "doc.audit_title": { standard: "Istoric integritate" },
  "doc.audit_verified": { standard: "Chain verificat" },
  "doc.audit_unverified": { standard: "Atenție: lanț de verificare deteriorat" },
  "doc.download_pdf": { standard: "Descarcă PDF" },
  "doc.ref_number": { standard: "Număr de înregistrare: {{ref}}" },
  "kiosk.accessibility_corner": { standard: "Pentru persoane cu nevoi speciale" },
  "a11y.voice_only": { standard: "Mod vocal" },
  "a11y.simple_language": { standard: "Explică-mi mai simplu" },
  "a11y.large_text": { standard: "Text mai mare" },
  "mrz.title": { standard: "Scanează buletinul" },
  "mrz.instruction": {
    standard: "Poziționează partea de jos a buletinului în chenar.",
    simple: "Pune actul cu fața în jos, în chenar.",
  },
  "mrz.manual_fallback": { standard: "Introdu CNP manual" },
  "mrz.scanning": { standard: "Se citește..." },
  "mrz.failed": { standard: "Nu am reușit să citesc buletinul. Mai încearcă." },
  "common.continue": { standard: "Continuă" },
  "common.cancel": { standard: "Anulează" },
  "common.back": { standard: "Înapoi" },
  "common.loading": { standard: "Se încarcă..." },
  "common.error": { standard: "A apărut o eroare. Încearcă din nou." },
} as const satisfies Record<string, Entry>;

export type StringKey = keyof typeof strings;

function interpolate(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, k: string) => {
    const v = params[k];
    return v === undefined ? `{{${k}}}` : String(v);
  });
}

export function t(
  key: StringKey,
  params: Record<string, string | number> = {},
  variant: Variant = "standard",
): string {
  const entry = strings[key];
  if (!entry) {
    throw new Error(`i18n: missing key "${key}"`);
  }
  const tmpl = variant === "simple" && entry.simple ? entry.simple : entry.standard;
  return interpolate(tmpl, params);
}

export function getVariant(attrs: CitizenAttributes | undefined): Variant {
  return attrs?.accessibility?.simple_language ? "simple" : "standard";
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/lib/i18n.ts frontend/lib/i18n.test.ts
git commit -m "feat(plan-1): Romanian i18n with simple-language variants"
```

---

### Task 9: Kiosk-mode detection

**Files:**
- Create: `frontend/lib/kioskMode.ts`
- Create: `frontend/lib/kioskMode.test.ts`

- [ ] **Step 1: Write a failing test**

`frontend/lib/kioskMode.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { detectKioskMode } from "./kioskMode";

const desktop = { searchParams: "", viewportWidth: 1280, hasTouch: false, idleMs: 0 };
const tablet = { searchParams: "", viewportWidth: 1100, hasTouch: true, idleMs: 0 };
const idleTablet = { searchParams: "", viewportWidth: 1100, hasTouch: true, idleMs: 90_000 };

describe("kioskMode", () => {
  it("explicit ?mode=kiosk wins", () => {
    expect(detectKioskMode({ ...desktop, searchParams: "?mode=kiosk" })).toBe(true);
  });

  it("explicit ?mode=mobile wins", () => {
    expect(detectKioskMode({ ...tablet, searchParams: "?mode=mobile" })).toBe(false);
  });

  it("desktop without touch is not kiosk", () => {
    expect(detectKioskMode(desktop)).toBe(false);
  });

  it("touch + large viewport + idle ≥ 60s is kiosk", () => {
    expect(detectKioskMode(idleTablet)).toBe(true);
  });

  it("touch + large viewport + active is not kiosk", () => {
    expect(detectKioskMode(tablet)).toBe(false);
  });

  it("touch but small screen is not kiosk", () => {
    expect(detectKioskMode({ ...tablet, viewportWidth: 600 })).toBe(false);
  });
});
```

- [ ] **Step 2: Implement detection**

`frontend/lib/kioskMode.ts`:

```ts
"use client";

import { useEffect, useState } from "react";

export type KioskInputs = {
  searchParams: string;
  viewportWidth: number;
  hasTouch: boolean;
  idleMs: number;
};

const IDLE_THRESHOLD_MS = 60_000;
const KIOSK_MIN_VIEWPORT_PX = 1000;

export function detectKioskMode(inputs: KioskInputs): boolean {
  const params = new URLSearchParams(inputs.searchParams);
  const mode = params.get("mode");
  if (mode === "kiosk") return true;
  if (mode === "mobile" || mode === "desktop") return false;
  if (!inputs.hasTouch) return false;
  if (inputs.viewportWidth < KIOSK_MIN_VIEWPORT_PX) return false;
  return inputs.idleMs >= IDLE_THRESHOLD_MS;
}

export function useKioskMode(): boolean {
  const [isKiosk, setIsKiosk] = useState(false);

  useEffect(() => {
    let lastActivity = Date.now();
    let raf = 0;

    const sample = () => {
      const next = detectKioskMode({
        searchParams: window.location.search,
        viewportWidth: window.innerWidth,
        hasTouch: window.matchMedia("(pointer: coarse)").matches,
        idleMs: Date.now() - lastActivity,
      });
      setIsKiosk((prev) => (prev === next ? prev : next));
      raf = window.requestAnimationFrame(() => {
        window.setTimeout(sample, 5_000);
      });
    };

    const reset = () => {
      lastActivity = Date.now();
    };

    sample();
    window.addEventListener("pointerdown", reset);
    window.addEventListener("keydown", reset);
    window.addEventListener("touchstart", reset);

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("pointerdown", reset);
      window.removeEventListener("keydown", reset);
      window.removeEventListener("touchstart", reset);
    };
  }, []);

  return isKiosk;
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/lib/kioskMode.ts frontend/lib/kioskMode.test.ts
git commit -m "feat(plan-1): kiosk-mode detection (query + viewport + touch + idle)"
```

---

### Task 10: useVoiceAgent stub

**Files:**
- Create: `frontend/lib/useVoiceAgent.ts`
- Create: `frontend/lib/useVoiceAgent.test.tsx`

- [ ] **Step 1: Write the failing test**

`frontend/lib/useVoiceAgent.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useVoiceAgent } from "./useVoiceAgent";

describe("useVoiceAgent (stub)", () => {
  it("starts in idle state with empty transcript", () => {
    const { result } = renderHook(() => useVoiceAgent());
    expect(result.current.state).toBe("idle");
    expect(result.current.lastTranscript).toBe("");
    expect(result.current.lastAgentMessage).toBe("");
  });

  it("start() throws because voice is not yet implemented", async () => {
    const { result } = renderHook(() => useVoiceAgent());
    await expect(result.current.start({})).rejects.toThrow(/Voice not yet implemented/);
  });

  it("stop, sendText, registerToolHandler do not throw", async () => {
    const { result } = renderHook(() => useVoiceAgent());
    await act(async () => {
      result.current.stop();
      await result.current.sendText("test");
      result.current.registerToolHandler(async () => ({}));
    });
    expect(result.current.state).toBe("idle");
  });
});
```

- [ ] **Step 2: Implement the stub matching the roadmap §4 contract exactly**

`frontend/lib/useVoiceAgent.ts`:

```ts
"use client";

import { useCallback, useMemo } from "react";
import type { VoicePreferences } from "./types";

export type VoiceAgentState = "idle" | "connecting" | "listening" | "speaking" | "error";

export type ToolCallHandler = (
  name: string,
  args: Record<string, unknown>,
) => Promise<Record<string, unknown>>;

export type VoiceAgentHook = {
  state: VoiceAgentState;
  start: (opts: {
    documentId?: string;
    preferences?: VoicePreferences;
    onAgentMessage?: (text: string) => void;
    onTranscript?: (text: string) => void;
  }) => Promise<void>;
  stop: () => void;
  sendText: (text: string) => Promise<void>;
  registerToolHandler: (handler: ToolCallHandler) => void;
  lastTranscript: string;
  lastAgentMessage: string;
};

export function useVoiceAgent(): VoiceAgentHook {
  const start = useCallback(async () => {
    throw new Error("Voice not yet implemented (Plan 3 wires Gemini Live).");
  }, []);

  const stop = useCallback(() => {
    // no-op stub
  }, []);

  const sendText = useCallback(async (_text: string) => {
    // no-op stub; Plan 3 forwards text to the Gemini Live session.
  }, []);

  const registerToolHandler = useCallback((_handler: ToolCallHandler) => {
    // no-op stub
  }, []);

  return useMemo(
    () => ({
      state: "idle" as VoiceAgentState,
      start,
      stop,
      sendText,
      registerToolHandler,
      lastTranscript: "",
      lastAgentMessage: "",
    }),
    [start, stop, sendText, registerToolHandler],
  );
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/lib/useVoiceAgent.ts frontend/lib/useVoiceAgent.test.tsx
git commit -m "feat(plan-1): useVoiceAgent stub matching roadmap §4 contract"
```

---

### Task 11: MRZ wrapper (tesseract.js + mrz)

**Files:**
- Create: `frontend/lib/mrz.ts`
- Create: `frontend/lib/mrz.test.ts`

- [ ] **Step 1: Write a failing test**

`frontend/lib/mrz.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";

vi.mock("tesseract.js", () => ({
  createWorker: vi.fn(async () => ({
    recognize: vi.fn(async () => ({
      data: {
        text:
          "IDROUIONESCU<<MARIA<<<<<<<<<<<<<<<<<<<<<<\n2851014123456ROU8503141F3506159<<<<<<<<<<<<<<00",
      },
    })),
    terminate: vi.fn(async () => undefined),
  })),
}));

vi.mock("mrz", () => ({
  parse: vi.fn(() => ({
    valid: true,
    fields: {
      firstName: "MARIA",
      lastName: "IONESCU",
      personalNumber: "2851014123456",
      birthDate: "850314",
      sex: "F",
    },
  })),
}));

import { parseMrzFromImage } from "./mrz";

describe("mrz wrapper", () => {
  it("returns parsed CNP + names from a fake image", async () => {
    const blob = new Blob([new Uint8Array([0])], { type: "image/png" });
    const r = await parseMrzFromImage(blob);
    expect(r.cnp).toBe("2851014123456");
    expect(r.nume).toBe("Ionescu");
    expect(r.prenume).toBe("Maria");
  });
});
```

- [ ] **Step 2: Implement the wrapper**

`frontend/lib/mrz.ts`:

```ts
import { createWorker } from "tesseract.js";
import { parse as parseMrz } from "mrz";

export type MrzResult = {
  cnp: string;
  nume: string;
  prenume: string;
  data_nasterii?: string;
  valid: boolean;
};

function titleCase(s: string): string {
  return s
    .toLowerCase()
    .split(/\s+/)
    .map((p) => (p ? p[0]!.toUpperCase() + p.slice(1) : p))
    .join(" ");
}

function isoFromMrzDate(yy_mm_dd: string | undefined): string | undefined {
  if (!yy_mm_dd || yy_mm_dd.length !== 6) return undefined;
  const yy = Number(yy_mm_dd.slice(0, 2));
  const mm = yy_mm_dd.slice(2, 4);
  const dd = yy_mm_dd.slice(4, 6);
  const century = yy <= new Date().getFullYear() % 100 ? 2000 : 1900;
  return `${century + yy}-${mm}-${dd}`;
}

export async function parseMrzFromImage(image: Blob): Promise<MrzResult> {
  const worker = await createWorker("ron+eng");
  try {
    const { data } = await worker.recognize(image);
    const lines = data.text
      .split(/\r?\n/)
      .map((l) => l.replace(/\s+/g, "").toUpperCase())
      .filter((l) => l.length >= 30 && /[<A-Z0-9]/.test(l));

    // Try every 2-line and 3-line window until mrz.parse accepts one.
    for (let size = 3; size >= 2; size -= 1) {
      for (let i = 0; i + size <= lines.length; i += 1) {
        const candidate = lines.slice(i, i + size);
        try {
          const parsed = parseMrz(candidate);
          if (parsed.valid && parsed.fields.personalNumber) {
            return {
              cnp: String(parsed.fields.personalNumber),
              nume: titleCase(String(parsed.fields.lastName ?? "")),
              prenume: titleCase(String(parsed.fields.firstName ?? "")),
              data_nasterii: isoFromMrzDate(parsed.fields.birthDate as string | undefined),
              valid: true,
            };
          }
        } catch {
          continue;
        }
      }
    }

    return { cnp: "", nume: "", prenume: "", valid: false };
  } finally {
    await worker.terminate();
  }
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/lib/mrz.ts frontend/lib/mrz.test.ts
git commit -m "feat(plan-1): MRZ wrapper around tesseract.js + mrz"
```

---

### Task 12: MRZ scanner component + manual CNP fallback

**Files:**
- Create: `frontend/components/MrzScanner.tsx`
- Create: `frontend/components/MrzScanner.test.tsx`

- [ ] **Step 1: Write a failing test**

`frontend/components/MrzScanner.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MrzScanner } from "./MrzScanner";

vi.mock("@/lib/mrz", () => ({
  parseMrzFromImage: vi.fn(async () => ({
    cnp: "2851014123456",
    nume: "Ionescu",
    prenume: "Maria",
    valid: true,
  })),
}));

describe("MrzScanner", () => {
  it("offers manual fallback button", () => {
    render(<MrzScanner onParsed={() => {}} />);
    expect(screen.getByRole("button", { name: /Introdu CNP manual/i })).toBeInTheDocument();
  });

  it("manual fallback submits a CNP form", async () => {
    const onParsed = vi.fn();
    render(<MrzScanner onParsed={onParsed} />);
    await userEvent.click(screen.getByRole("button", { name: /Introdu CNP manual/i }));
    await userEvent.type(screen.getByLabelText(/CNP/i), "2851014123456");
    await userEvent.type(screen.getByLabelText(/Nume/i), "Ionescu");
    await userEvent.type(screen.getByLabelText(/Prenume/i), "Maria");
    await userEvent.click(screen.getByRole("button", { name: /Continuă/i }));
    expect(onParsed).toHaveBeenCalledWith({
      cnp: "2851014123456",
      nume: "Ionescu",
      prenume: "Maria",
      valid: true,
    });
  });

  it("upload path calls parser and forwards parsed payload", async () => {
    const onParsed = vi.fn();
    render(<MrzScanner onParsed={onParsed} />);
    const file = new File([new Uint8Array([0])], "id.jpg", { type: "image/jpeg" });
    const input = screen.getByTestId("mrz-upload") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(onParsed).toHaveBeenCalled());
    expect(onParsed.mock.calls[0]![0]).toMatchObject({ cnp: "2851014123456" });
  });
});
```

- [ ] **Step 2: Implement the component**

`frontend/components/MrzScanner.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/lib/i18n";
import { parseMrzFromImage, type MrzResult } from "@/lib/mrz";

type Props = {
  onParsed: (r: MrzResult) => void;
};

type Mode = "camera" | "upload" | "manual";

export function MrzScanner({ onParsed }: Props) {
  const [mode, setMode] = useState<Mode>("camera");
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (mode !== "camera") {
      streamRef.current?.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        if (cancelled) {
          stream.getTracks().forEach((tr) => tr.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
      } catch {
        setMode("upload");
      }
    })();
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
    };
  }, [mode]);

  async function captureFrame(): Promise<Blob | null> {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0);
    return await new Promise((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.9),
    );
  }

  async function runParse(blob: Blob) {
    setScanning(true);
    setError(null);
    try {
      const r = await parseMrzFromImage(blob);
      if (!r.valid) {
        setError(t("mrz.failed"));
        return;
      }
      onParsed(r);
    } catch {
      setError(t("mrz.failed"));
    } finally {
      setScanning(false);
    }
  }

  if (mode === "manual") {
    return (
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          onParsed({
            cnp: String(data.get("cnp") ?? ""),
            nume: String(data.get("nume") ?? ""),
            prenume: String(data.get("prenume") ?? ""),
            valid: true,
          });
        }}
      >
        <h2 className="text-xl font-semibold">{t("mrz.manual_fallback")}</h2>
        <div>
          <Label htmlFor="cnp">CNP</Label>
          <Input id="cnp" name="cnp" required pattern="\d{13}" inputMode="numeric" />
        </div>
        <div>
          <Label htmlFor="nume">Nume</Label>
          <Input id="nume" name="nume" required />
        </div>
        <div>
          <Label htmlFor="prenume">Prenume</Label>
          <Input id="prenume" name="prenume" required />
        </div>
        <Button type="submit">{t("common.continue")}</Button>
      </form>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{t("mrz.title")}</h2>
      <p className="text-sm text-muted-foreground">{t("mrz.instruction")}</p>

      {mode === "camera" ? (
        <div className="relative overflow-hidden rounded-lg border bg-black">
          <video
            ref={videoRef}
            className="aspect-video w-full"
            playsInline
            muted
            aria-label="Camera preview"
          />
          <div className="pointer-events-none absolute inset-x-8 bottom-12 h-16 rounded border-2 border-yellow-300/80" />
        </div>
      ) : (
        <label
          htmlFor="mrz-upload-input"
          className="flex aspect-video w-full cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30 text-sm text-muted-foreground"
        >
          Apasă pentru a încărca o poză cu buletinul
        </label>
      )}

      <input
        id="mrz-upload-input"
        data-testid="mrz-upload"
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void runParse(f);
        }}
      />

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          disabled={scanning || mode !== "camera"}
          onClick={async () => {
            const blob = await captureFrame();
            if (blob) void runParse(blob);
          }}
        >
          {scanning ? t("mrz.scanning") : "Capturează"}
        </Button>
        <Button type="button" variant="outline" onClick={() => setMode("upload")}>
          Încarcă o poză
        </Button>
        <Button type="button" variant="ghost" onClick={() => setMode("manual")}>
          {t("login.manual_cnp_button")}
        </Button>
      </div>

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/MrzScanner.tsx frontend/components/MrzScanner.test.tsx
git commit -m "feat(plan-1): MRZ scanner component with camera + upload + manual fallback"
```

---

### Task 13: LoginButton + persona chooser

**Files:**
- Create: `frontend/components/LoginButton.tsx`
- Create: `frontend/components/LoginButton.test.tsx`

- [ ] **Step 1: Write a failing test**

`frontend/components/LoginButton.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginButton } from "./LoginButton";

const loginRoeid = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { loginRoeid: (b: { persona_id?: string }) => loginRoeid(b) },
  ApiError: class extends Error {},
}));

describe("LoginButton", () => {
  beforeEach(() => loginRoeid.mockReset());

  it("shows demo persona chooser when NEXT_PUBLIC_DEMO_MODE=1", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    render(<LoginButton onChallenge={() => {}} />);
    expect(screen.getByLabelText(/Persona demo/i)).toBeInTheDocument();
    vi.unstubAllEnvs();
  });

  it("hides demo persona chooser otherwise", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");
    render(<LoginButton onChallenge={() => {}} />);
    expect(screen.queryByLabelText(/Persona demo/i)).not.toBeInTheDocument();
    vi.unstubAllEnvs();
  });

  it("clicking ROeID button triggers loginRoeid and forwards challenge", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
    loginRoeid.mockResolvedValue({ challenge_id: "ch1", phone_hint: "***1234" });
    const onChallenge = vi.fn();
    render(<LoginButton onChallenge={onChallenge} />);
    await userEvent.click(screen.getByRole("button", { name: /Login cu ROeID/i }));
    expect(loginRoeid).toHaveBeenCalled();
    expect(onChallenge).toHaveBeenCalledWith({ challenge_id: "ch1", phone_hint: "***1234" });
    vi.unstubAllEnvs();
  });
});
```

- [ ] **Step 2: Implement LoginButton**

`frontend/components/LoginButton.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { LoginChallenge } from "@/lib/types";

const DEMO_PERSONAS = [
  { id: "maria-ionescu", label: "Maria Ionescu" },
  { id: "ion-popescu", label: "Ion Popescu" },
  { id: "ana-georgescu", label: "Ana Georgescu" },
];

type Props = {
  onChallenge: (c: LoginChallenge) => void;
};

export function LoginButton({ onChallenge }: Props) {
  const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "1";
  const [persona, setPersona] = useState(DEMO_PERSONAS[0]!.id);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.loginRoeid(demoMode ? { persona_id: persona } : {});
      onChallenge(r);
    } catch {
      setError(t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      {demoMode ? (
        <div className="space-y-1">
          <Label htmlFor="persona">{t("login.persona_label")}</Label>
          <select
            id="persona"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
          >
            {DEMO_PERSONAS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <Button onClick={handleClick} disabled={loading} className="w-full" size="lg">
        {loading ? t("common.loading") : t("login.roeid_button")}
      </Button>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/LoginButton.tsx frontend/components/LoginButton.test.tsx
git commit -m "feat(plan-1): LoginButton with demo persona chooser"
```

---

### Task 14: Login + OTP pages and OtpInput component

**Files:**
- Create: `frontend/components/OtpInput.tsx`
- Create: `frontend/components/OtpInput.test.tsx`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/login/otp/page.tsx`

- [ ] **Step 1: Failing test for OtpInput**

`frontend/components/OtpInput.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OtpInput } from "./OtpInput";

describe("OtpInput", () => {
  it("calls onComplete when 6 digits typed", async () => {
    const onComplete = vi.fn();
    render(<OtpInput onComplete={onComplete} />);
    const input = screen.getByLabelText(/Cod OTP/i);
    await userEvent.type(input, "123456");
    expect(onComplete).toHaveBeenCalledWith("123456");
  });

  it("strips non-digits", async () => {
    const onComplete = vi.fn();
    render(<OtpInput onComplete={onComplete} />);
    const input = screen.getByLabelText(/Cod OTP/i);
    await userEvent.type(input, "1a2b3c4d5e6f");
    expect(onComplete).toHaveBeenCalledWith("123456");
  });
});
```

- [ ] **Step 2: Implement OtpInput**

`frontend/components/OtpInput.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  onComplete: (code: string) => void;
  error?: string | null;
};

export function OtpInput({ onComplete, error }: Props) {
  const [value, setValue] = useState("");

  return (
    <div className="space-y-2">
      <Label htmlFor="otp">Cod OTP</Label>
      <Input
        id="otp"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={value}
        onChange={(e) => {
          const next = e.target.value.replace(/\D/g, "").slice(0, 6);
          setValue(next);
          if (next.length === 6) onComplete(next);
        }}
        aria-invalid={error ? "true" : undefined}
        className="text-center text-2xl tracking-[0.5em]"
      />
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 3: Run OtpInput test**

```bash
npm run test -- OtpInput
```

Expected: pass.

- [ ] **Step 4: Login page**

`frontend/app/login/page.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoginButton } from "@/components/LoginButton";
import { t } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("login.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{t("login.subtitle")}</p>
          <LoginButton
            onChallenge={(c) => {
              const params = new URLSearchParams({
                challenge_id: c.challenge_id,
                phone_hint: c.phone_hint,
              });
              router.push(`/login/otp?${params.toString()}`);
            }}
          />
        </CardContent>
      </Card>
    </main>
  );
}
```

- [ ] **Step 5: OTP page**

`frontend/app/login/otp/page.tsx`:

```tsx
"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OtpInput } from "@/components/OtpInput";
import { api, ApiError } from "@/lib/api";
import { setSession } from "@/lib/session";
import { t } from "@/lib/i18n";

function OtpForm() {
  const params = useSearchParams();
  const router = useRouter();
  const challengeId = params.get("challenge_id") ?? "";
  const phoneHint = params.get("phone_hint") ?? "";
  const [error, setError] = useState<string | null>(null);

  async function submit(code: string) {
    setError(null);
    try {
      const session = await api.otp({ challenge_id: challengeId, code });
      setSession(session);
      router.push("/");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError(t("otp.error"));
      } else {
        setError(t("common.error"));
      }
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{t("otp.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {t("otp.phone_hint", { phone_hint: phoneHint })}
        </p>
        <OtpInput onComplete={submit} error={error} />
      </CardContent>
    </Card>
  );
}

export default function OtpPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <Suspense fallback={null}>
        <OtpForm />
      </Suspense>
    </main>
  );
}
```

- [ ] **Step 6: Tests pass + Next build**

```bash
npm run test
npm run build
```

- [ ] **Step 7: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/OtpInput.tsx frontend/components/OtpInput.test.tsx frontend/app/login/
git commit -m "feat(plan-1): login + OTP pages with shadcn cards"
```

---

### Task 15: KioskShell + kiosk path on /login

**Files:**
- Create: `frontend/components/KioskShell.tsx`
- Modify: `frontend/app/login/page.tsx`

- [ ] **Step 1: Write KioskShell**

`frontend/components/KioskShell.tsx`:

```tsx
"use client";

import { type ReactNode, useState } from "react";
import { Button } from "@/components/ui/button";
import { AccessibilityToggles } from "@/components/AccessibilityToggles";
import { t } from "@/lib/i18n";

type Props = {
  children: ReactNode;
};

export function KioskShell({ children }: Props) {
  const [accessibilityOpen, setAccessibilityOpen] = useState(false);

  return (
    <div className="fixed inset-0 flex flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-8 py-4">
        <h1 className="text-3xl font-bold">{t("app.title")}</h1>
        <Button
          variant="outline"
          size="lg"
          className="text-lg"
          onClick={() => setAccessibilityOpen((v) => !v)}
          aria-expanded={accessibilityOpen}
        >
          {t("kiosk.accessibility_corner")}
        </Button>
      </header>
      {accessibilityOpen ? (
        <section className="border-b bg-muted/30 px-8 py-6">
          <AccessibilityToggles />
        </section>
      ) : null}
      <main className="flex-1 overflow-auto px-8 py-8 [&_button]:min-h-[3rem] [&_input]:min-h-[3rem]">
        {children}
      </main>
    </div>
  );
}
```

(`AccessibilityToggles` is created in Task 22; reference here is intentional — that task lands before any deploy. To unblock the build now, also create a temporary stub: `frontend/components/AccessibilityToggles.tsx` returning `<div />` — Task 22 replaces it.)

- [ ] **Step 2: Add the temporary AccessibilityToggles stub**

`frontend/components/AccessibilityToggles.tsx`:

```tsx
"use client";

export function AccessibilityToggles() {
  return <div />;
}
```

- [ ] **Step 3: Wire kiosk detection into login page**

Replace `frontend/app/login/page.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoginButton } from "@/components/LoginButton";
import { MrzScanner } from "@/components/MrzScanner";
import { KioskShell } from "@/components/KioskShell";
import { useKioskMode } from "@/lib/kioskMode";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { LoginChallenge, MrzResult } from "@/lib/mrz";

function nav(router: ReturnType<typeof useRouter>, c: LoginChallenge) {
  const params = new URLSearchParams({
    challenge_id: c.challenge_id,
    phone_hint: c.phone_hint,
  });
  router.push(`/login/otp?${params.toString()}`);
}

function LoginCard({ onChallenge }: { onChallenge: (c: LoginChallenge) => void }) {
  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{t("login.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{t("login.subtitle")}</p>
        <LoginButton onChallenge={onChallenge} />
      </CardContent>
    </Card>
  );
}

function KioskLogin() {
  const router = useRouter();
  const [path, setPath] = useState<"chooser" | "roeid" | "mrz">("chooser");
  const [error, setError] = useState<string | null>(null);

  async function submitMrz(r: MrzResult) {
    setError(null);
    try {
      const c = await api.loginMrz({ cnp: r.cnp, nume: r.nume, prenume: r.prenume });
      nav(router, c);
    } catch (e) {
      if (e instanceof ApiError) setError(t("common.error"));
      else throw e;
    }
  }

  return (
    <KioskShell>
      <div className="mx-auto max-w-3xl space-y-8">
        {path === "chooser" ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Button size="lg" className="h-32 text-2xl" onClick={() => setPath("roeid")}>
              {t("login.roeid_button")}
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="h-32 text-2xl"
              onClick={() => setPath("mrz")}
            >
              {t("login.scan_id_button")}
            </Button>
          </div>
        ) : null}

        {path === "roeid" ? <LoginCard onChallenge={(c) => nav(router, c)} /> : null}
        {path === "mrz" ? <MrzScanner onParsed={submitMrz} /> : null}
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}

        {path !== "chooser" ? (
          <Button variant="ghost" onClick={() => setPath("chooser")}>
            {t("common.back")}
          </Button>
        ) : null}
      </div>
    </KioskShell>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const isKiosk = useKioskMode();
  if (isKiosk) return <KioskLogin />;
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <LoginCard onChallenge={(c) => nav(router, c)} />
    </main>
  );
}
```

Also export `LoginChallenge` and `MrzResult` from their modules already (they are, via `lib/types.ts` and `lib/mrz.ts`).

- [ ] **Step 4: Build is green**

```bash
npm run build
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/KioskShell.tsx frontend/components/AccessibilityToggles.tsx frontend/app/login/page.tsx
git commit -m "feat(plan-1): KioskShell + kiosk login chooser (ROeID vs MRZ)"
```

---

### Task 16: DocumentList, ReminderCard shells, citizen home

**Files:**
- Create: `frontend/components/DocumentList.tsx`
- Create: `frontend/components/ReminderCard.tsx`
- Create: `frontend/app/page.tsx` (replace placeholder)

- [ ] **Step 1: DocumentList**

`frontend/components/DocumentList.tsx`:

```tsx
"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Document, Procedure } from "@/lib/types";

type Props = {
  documents: Document[];
  procedures: Procedure[];
};

export function DocumentList({ documents, procedures }: Props) {
  if (documents.length === 0) {
    return <p className="text-sm text-muted-foreground">Nu ai documente încă.</p>;
  }
  const titleOf = (id: string) =>
    procedures.find((p) => p.id === id)?.title ?? id;

  return (
    <ul className="space-y-3">
      {documents.map((d) => (
        <li key={d.id}>
          <Link href={`/doc/${d.id}`} className="block">
            <Card className="transition hover:bg-accent/40 focus-within:ring-2">
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <p className="font-medium">{titleOf(d.procedure_id)}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(d.created_at).toLocaleDateString("ro-RO")}
                  </p>
                </div>
                {d.status === "finalized" ? (
                  <Badge variant="default">Trimisă</Badge>
                ) : (
                  <Badge variant="secondary">În lucru</Badge>
                )}
              </CardContent>
            </Card>
          </Link>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 2: ReminderCard shell (no actions yet — Plan 4 wires)**

`frontend/components/ReminderCard.tsx`:

```tsx
"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Reminder } from "@/lib/types";

type Props = {
  reminder: Reminder;
};

export function ReminderCard({ reminder }: Props) {
  const isExternal = reminder.kind === "external_redirect";
  return (
    <Card className="border-l-4 border-l-primary">
      <CardContent className="space-y-2 p-4">
        <div className="flex items-start gap-2">
          <span aria-hidden className="text-xl">
            {isExternal ? "↪" : "⚠"}
          </span>
          <p className="font-medium">{reminder.title}</p>
        </div>
        {reminder.due_date ? (
          <p className="text-xs text-muted-foreground">
            Termen: {new Date(reminder.due_date).toLocaleDateString("ro-RO")}
          </p>
        ) : null}
        <Button variant="outline" size="sm" disabled aria-label="Acțiune disponibilă în Plan 4">
          {isExternal ? "Vezi cum" : "Start now"}
        </Button>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Citizen home page**

Replace `frontend/app/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DocumentList } from "@/components/DocumentList";
import { ReminderCard } from "@/components/ReminderCard";
import { api } from "@/lib/api";
import { getVariant, t } from "@/lib/i18n";
import type { Citizen, Document, Procedure, Reminder } from "@/lib/types";
import { useKioskMode } from "@/lib/kioskMode";
import { KioskShell } from "@/components/KioskShell";
import { getSession } from "@/lib/session";
import { useRouter } from "next/navigation";

function HomeBody({
  citizen,
  documents,
  procedures,
  reminders,
}: {
  citizen: Citizen;
  documents: Document[];
  procedures: Procedure[];
  reminders: Reminder[];
}) {
  const variant = getVariant(citizen.attributes);
  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <h1 className="text-3xl font-bold">
        {t("home.greeting", { prenume: citizen.prenume }, variant)}
      </h1>

      <section aria-labelledby="reminders-heading" className="space-y-3">
        <h2 id="reminders-heading" className="text-xl font-semibold">
          {t("home.recommended_title", {}, variant)}
        </h2>
        <div className="space-y-3">
          {reminders.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nimic urgent.</p>
          ) : (
            reminders.map((r) => <ReminderCard key={r.id} reminder={r} />)
          )}
        </div>
      </section>

      <section aria-labelledby="documents-heading" className="space-y-3">
        <h2 id="documents-heading" className="text-xl font-semibold">
          {t("home.documents_title")}
        </h2>
        <DocumentList documents={documents} procedures={procedures} />
      </section>

      <div>
        <Link href="/req/new">
          <Button size="lg">+ {t("home.start_new")}</Button>
        </Link>
      </div>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const isKiosk = useKioskMode();
  const [citizen, setCitizen] = useState<Citizen | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getSession()) {
      router.replace("/login");
      return;
    }
    void (async () => {
      try {
        const [c, docs, procs, rs] = await Promise.all([
          api.getCitizenMe(),
          api.listDocuments(),
          api.listProcedures(),
          fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/reminders`)
            .then((r) => (r.ok ? (r.json() as Promise<Reminder[]>) : []))
            .catch(() => []),
        ]);
        setCitizen(c);
        setDocuments(docs);
        setProcedures(procs);
        setReminders(rs);
      } catch {
        setError(t("common.error"));
      }
    })();
  }, [router]);

  if (error) return <p role="alert" className="p-6 text-destructive">{error}</p>;
  if (!citizen) return <p className="p-6 text-muted-foreground">{t("common.loading")}</p>;

  const body = (
    <HomeBody
      citizen={citizen}
      documents={documents}
      procedures={procedures}
      reminders={reminders}
    />
  );

  return isKiosk ? <KioskShell>{body}</KioskShell> : <main>{body}</main>;
}
```

- [ ] **Step 4: Build is green**

```bash
npm run build
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/DocumentList.tsx frontend/components/ReminderCard.tsx frontend/app/page.tsx
git commit -m "feat(plan-1): citizen home with DocumentList + ReminderCard shells"
```

---

### Task 17: FormPreview component

**Files:**
- Create: `frontend/components/FormPreview.tsx`
- Create: `frontend/components/FormPreview.test.tsx`

- [ ] **Step 1: Failing test**

`frontend/components/FormPreview.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FormPreview } from "./FormPreview";
import type { Procedure } from "@/lib/types";

const procedure: Procedure = {
  id: "schimbare-domiciliu",
  title: "Schimbare domiciliu",
  description: "",
  scope: "primarie",
  category: "evidenta-persoanelor",
  synonyms: [],
  sample_queries: [],
  template: "schimbare-domiciliu.tex",
  next_steps: [],
  fields: [
    { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
    { name: "cnp", label: "CNP", source: "profile", required: true },
    { name: "adresa_noua", label: "Adresă nouă", source: "ask", required: true },
  ],
};

describe("FormPreview", () => {
  it("renders procedure title and fields", () => {
    render(<FormPreview procedure={procedure} values={{}} />);
    expect(screen.getByText("Schimbare domiciliu")).toBeInTheDocument();
    expect(screen.getByText("Nume complet")).toBeInTheDocument();
    expect(screen.getByText("CNP")).toBeInTheDocument();
    expect(screen.getByText("Adresă nouă")).toBeInTheDocument();
  });

  it("marks filled fields with the filled value", () => {
    render(
      <FormPreview procedure={procedure} values={{ adresa_noua: "Str. Plopilor 15" }} />,
    );
    expect(screen.getByText("Str. Plopilor 15")).toBeInTheDocument();
  });

  it("shows the empty-state placeholder for missing fields", () => {
    render(<FormPreview procedure={procedure} values={{}} />);
    const placeholders = screen.getAllByText("________________");
    expect(placeholders.length).toBeGreaterThan(0);
  });

  it("highlights the active field", () => {
    render(<FormPreview procedure={procedure} values={{}} activeField="adresa_noua" />);
    expect(screen.getByTestId("field-adresa_noua")).toHaveAttribute(
      "data-active",
      "true",
    );
  });
});
```

- [ ] **Step 2: Implement FormPreview**

`frontend/components/FormPreview.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import type { Procedure } from "@/lib/types";

type Props = {
  procedure: Procedure;
  values: Record<string, unknown>;
  activeField?: string;
};

export function FormPreview({ procedure, values, activeField }: Props) {
  return (
    <article
      aria-labelledby="form-preview-title"
      className="rounded-lg border bg-white p-8 font-serif text-black shadow-sm"
    >
      <header className="mb-6 border-b border-black/20 pb-4 text-center">
        <h2 id="form-preview-title" className="text-2xl font-bold uppercase tracking-wider">
          {procedure.title}
        </h2>
        {procedure.description ? (
          <p className="mt-1 text-sm">{procedure.description}</p>
        ) : null}
      </header>

      <dl className="space-y-3">
        {procedure.fields.map((field) => {
          const v = values[field.name];
          const filled = v !== undefined && v !== null && String(v).length > 0;
          const isActive = activeField === field.name;
          return (
            <motion.div
              key={field.name}
              data-testid={`field-${field.name}`}
              data-active={isActive ? "true" : "false"}
              initial={false}
              animate={
                isActive
                  ? { backgroundColor: "rgb(254 240 138)" }
                  : { backgroundColor: "rgba(0,0,0,0)" }
              }
              transition={{ duration: 0.2 }}
              className="grid grid-cols-[12rem_1fr] items-baseline gap-3 rounded px-2 py-1"
            >
              <dt className="text-sm font-medium">
                {field.label}
                {field.required ? <span aria-hidden> *</span> : null}
              </dt>
              <dd className="border-b border-dotted border-black/40 text-base">
                {filled ? <span>{String(v)}</span> : <span>________________</span>}
              </dd>
            </motion.div>
          );
        })}
      </dl>

      <footer className="mt-8 grid grid-cols-2 gap-8 text-sm">
        <div>
          <p className="font-medium">Data:</p>
          <p>____________</p>
        </div>
        <div className="text-right">
          <p className="font-medium">Semnătură:</p>
          <p>____________</p>
        </div>
      </footer>
    </article>
  );
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test -- FormPreview
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/FormPreview.tsx frontend/components/FormPreview.test.tsx
git commit -m "feat(plan-1): FormPreview HTML mockup with framer-motion field highlight"
```

---

### Task 18: ChatPanel component

**Files:**
- Create: `frontend/components/ChatPanel.tsx`
- Create: `frontend/components/ChatPanel.test.tsx`

- [ ] **Step 1: Failing test**

`frontend/components/ChatPanel.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "./ChatPanel";

const chat = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { chat: (b: unknown) => chat(b) },
  ApiError: class extends Error {},
}));

describe("ChatPanel", () => {
  it("renders initial messages", () => {
    render(
      <ChatPanel
        documentId="doc1"
        messages={[{ role: "agent", text: "Bună!" }]}
        onMessagesChange={() => {}}
      />,
    );
    expect(screen.getByText("Bună!")).toBeInTheDocument();
  });

  it("submitting text calls api.chat and appends both messages", async () => {
    chat.mockResolvedValue({
      conversation_id: "c1",
      message: "Înțeleg că vrei să-ți schimbi domiciliul.",
      tool_calls: [{ name: "lookup_procedure", arguments: { query: "x" } }],
    });
    const onMessagesChange = vi.fn();
    render(
      <ChatPanel
        documentId="doc1"
        messages={[]}
        onMessagesChange={onMessagesChange}
      />,
    );
    await userEvent.type(screen.getByRole("textbox"), "Vreau să mă mut");
    await userEvent.click(screen.getByRole("button", { name: /Trimite/i }));
    await waitFor(() =>
      expect(onMessagesChange).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ role: "user", text: "Vreau să mă mut" }),
          expect.objectContaining({
            role: "agent",
            text: expect.stringContaining("schimbi domiciliul"),
          }),
        ]),
      ),
    );
  });

  it("renders tool-call traces", () => {
    render(
      <ChatPanel
        documentId="doc1"
        messages={[
          {
            role: "agent",
            text: "ok",
            tool_calls: [{ name: "lookup_procedure", arguments: { query: "x" } }],
          },
        ]}
        onMessagesChange={() => {}}
      />,
    );
    expect(screen.getByText(/lookup_procedure/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement ChatPanel**

`frontend/components/ChatPanel.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { ChatMessage, VoicePreferences } from "@/lib/types";

type Props = {
  documentId: string;
  messages: ChatMessage[];
  onMessagesChange: (m: ChatMessage[]) => void;
  preferences?: VoicePreferences;
};

export function ChatPanel({ documentId, messages, onMessagesChange, preferences }: Props) {
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    const userMsg: ChatMessage = { role: "user", text };
    const next = [...messages, userMsg];
    onMessagesChange(next);
    setDraft("");
    try {
      const r = await api.chat({
        conversation_id: conversationId,
        document_id: documentId,
        message: text,
        preferences,
      });
      setConversationId(r.conversation_id);
      const agentMsg: ChatMessage = {
        role: "agent",
        text: r.message,
        tool_calls: r.tool_calls,
      };
      onMessagesChange([...next, agentMsg]);
    } catch (e) {
      if (e instanceof ApiError) setError(t("common.error"));
      else throw e;
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-full flex-col" aria-label="Chat cu asistentul">
      <ol className="flex-1 space-y-3 overflow-auto p-4" aria-live="polite">
        {messages.map((m, i) => (
          <li
            key={i}
            className={
              m.role === "agent"
                ? "rounded-lg bg-muted px-4 py-3 text-sm"
                : "ml-12 rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground"
            }
          >
            <p className="whitespace-pre-wrap">{m.text}</p>
            {m.tool_calls && m.tool_calls.length > 0 ? (
              <ul className="mt-2 space-y-1 text-xs opacity-70">
                {m.tool_calls.map((tc, j) => (
                  <li key={j}>
                    <code>
                      {tc.name}({JSON.stringify(tc.arguments)})
                    </code>
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ol>
      {error ? <p role="alert" className="px-4 text-sm text-destructive">{error}</p> : null}
      <form
        className="flex gap-2 border-t p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          placeholder={t("chat.input_placeholder")}
          aria-label="Mesaj nou"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <Button type="submit" disabled={sending || draft.trim().length === 0}>
          {sending ? t("common.loading") : t("chat.send")}
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test -- ChatPanel
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/ChatPanel.tsx frontend/components/ChatPanel.test.tsx
git commit -m "feat(plan-1): ChatPanel with tool-call traces"
```

---

### Task 19: CompletionModeSelector + completion-mode state

**Files:**
- Create: `frontend/lib/completionMode.ts`
- Create: `frontend/lib/completionMode.test.ts`
- Create: `frontend/components/CompletionModeSelector.tsx`
- Create: `frontend/components/CompletionModeSelector.test.tsx`

- [ ] **Step 1: Failing test for state machine**

`frontend/lib/completionMode.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { reduceCompletionMode } from "./completionMode";

describe("reduceCompletionMode", () => {
  it("starts undecided", () => {
    expect(reduceCompletionMode({ mode: null }, { type: "noop" }).mode).toBeNull();
  });

  it("CHOOSE picks the mode", () => {
    expect(reduceCompletionMode({ mode: null }, { type: "CHOOSE", mode: "manual" }).mode).toBe(
      "manual",
    );
  });

  it("SWITCH replaces the mode mid-flow", () => {
    expect(
      reduceCompletionMode({ mode: "manual" }, { type: "SWITCH", mode: "guided" }).mode,
    ).toBe("guided");
  });

  it("RESET clears the choice", () => {
    expect(reduceCompletionMode({ mode: "voice" }, { type: "RESET" }).mode).toBeNull();
  });
});
```

- [ ] **Step 2: Implement the reducer**

`frontend/lib/completionMode.ts`:

```ts
export type CompletionMode = "manual" | "guided" | "voice";

export type CompletionModeState = {
  mode: CompletionMode | null;
};

export type CompletionModeAction =
  | { type: "CHOOSE"; mode: CompletionMode }
  | { type: "SWITCH"; mode: CompletionMode }
  | { type: "RESET" }
  | { type: "noop" };

export function reduceCompletionMode(
  state: CompletionModeState,
  action: CompletionModeAction,
): CompletionModeState {
  switch (action.type) {
    case "CHOOSE":
    case "SWITCH":
      return { mode: action.mode };
    case "RESET":
      return { mode: null };
    case "noop":
    default:
      return state;
  }
}

const KEY = (docId: string) => `civicai.mode.${docId}`;

export function loadPersistedMode(docId: string): CompletionMode | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(KEY(docId));
  return v === "manual" || v === "guided" || v === "voice" ? v : null;
}

export function persistMode(docId: string, mode: CompletionMode | null): void {
  if (typeof window === "undefined") return;
  if (mode === null) window.localStorage.removeItem(KEY(docId));
  else window.localStorage.setItem(KEY(docId), mode);
}
```

- [ ] **Step 3: Implement CompletionModeSelector**

`frontend/components/CompletionModeSelector.tsx`:

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { t } from "@/lib/i18n";
import type { CompletionMode } from "@/lib/completionMode";

type Props = {
  current: CompletionMode | null;
  onChange: (mode: CompletionMode) => void;
  variant?: "initial" | "switcher";
};

const MODES: Array<{ key: CompletionMode; label: string }> = [
  { key: "manual", label: "manual" },
  { key: "guided", label: "guided" },
  { key: "voice", label: "voice" },
];

export function CompletionModeSelector({ current, onChange, variant = "initial" }: Props) {
  return (
    <div
      role="radiogroup"
      aria-label={variant === "switcher" ? t("mode.switch") : "Mod de completare"}
      className={
        variant === "switcher"
          ? "flex gap-2"
          : "grid grid-cols-1 gap-3 sm:grid-cols-3"
      }
    >
      {MODES.map((m) => {
        const labelKey =
          m.key === "manual" ? "mode.manual" : m.key === "guided" ? "mode.guided" : "mode.voice";
        const isActive = current === m.key;
        return (
          <Button
            key={m.key}
            role="radio"
            aria-checked={isActive}
            variant={isActive ? "default" : "outline"}
            size={variant === "switcher" ? "sm" : "lg"}
            className={variant === "initial" ? "h-20 text-lg" : ""}
            onClick={() => onChange(m.key)}
          >
            {t(labelKey as "mode.manual" | "mode.guided" | "mode.voice")}
          </Button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Test the selector**

`frontend/components/CompletionModeSelector.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CompletionModeSelector } from "./CompletionModeSelector";

describe("CompletionModeSelector", () => {
  it("renders three radios", () => {
    render(<CompletionModeSelector current={null} onChange={() => {}} />);
    expect(screen.getAllByRole("radio")).toHaveLength(3);
  });

  it("clicking emits the mode", async () => {
    const onChange = vi.fn();
    render(<CompletionModeSelector current={null} onChange={onChange} />);
    await userEvent.click(screen.getByRole("radio", { name: /Vocal/i }));
    expect(onChange).toHaveBeenCalledWith("voice");
  });

  it("highlights the active mode", () => {
    render(<CompletionModeSelector current="manual" onChange={() => {}} />);
    expect(screen.getByRole("radio", { name: /Manual/i })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});
```

- [ ] **Step 5: Tests pass**

```bash
npm run test
```

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/lib/completionMode.ts frontend/lib/completionMode.test.ts frontend/components/CompletionModeSelector.tsx frontend/components/CompletionModeSelector.test.tsx
git commit -m "feat(plan-1): CompletionModeSelector + persisted mode state"
```

---

### Task 20: ManualFillForm + GuidedFillFlow + VocalFillFlow

**Files:**
- Create: `frontend/components/ManualFillForm.tsx`
- Create: `frontend/components/ManualFillForm.test.tsx`
- Create: `frontend/components/GuidedFillFlow.tsx`
- Create: `frontend/components/VocalFillFlow.tsx`

- [ ] **Step 1: Failing test for ManualFillForm**

`frontend/components/ManualFillForm.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ManualFillForm } from "./ManualFillForm";
import type { Procedure } from "@/lib/types";

const procedure: Procedure = {
  id: "schimbare-domiciliu",
  title: "Schimbare domiciliu",
  description: "",
  scope: "primarie",
  category: "evidenta-persoanelor",
  synonyms: [],
  sample_queries: [],
  template: "",
  next_steps: [],
  fields: [
    { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
    { name: "adresa_noua", label: "Adresă nouă", source: "ask", required: true },
    {
      name: "tip_proprietate",
      label: "Tip proprietate",
      source: "ask",
      required: true,
      options: ["proprietar", "chiriaș"],
    },
  ],
};

describe("ManualFillForm", () => {
  it("only renders fields not already in values", () => {
    render(
      <ManualFillForm
        procedure={procedure}
        values={{ nume_complet: "Maria" }}
        onPatch={() => {}}
      />,
    );
    expect(screen.queryByLabelText(/Nume complet/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Adresă nouă/i)).toBeInTheDocument();
  });

  it("submitting calls onPatch with new field values", async () => {
    const onPatch = vi.fn();
    render(
      <ManualFillForm
        procedure={procedure}
        values={{ nume_complet: "Maria" }}
        onPatch={onPatch}
      />,
    );
    await userEvent.type(screen.getByLabelText(/Adresă nouă/i), "Str. Plopilor 15");
    await userEvent.selectOptions(screen.getByLabelText(/Tip proprietate/i), "chiriaș");
    await userEvent.click(screen.getByRole("button", { name: /Salvează/i }));
    expect(onPatch).toHaveBeenCalledWith({
      adresa_noua: "Str. Plopilor 15",
      tip_proprietate: "chiriaș",
    });
  });
});
```

- [ ] **Step 2: Implement ManualFillForm**

`frontend/components/ManualFillForm.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Procedure, ProcedureField } from "@/lib/types";

type Props = {
  procedure: Procedure;
  values: Record<string, unknown>;
  onPatch: (delta: Record<string, unknown>) => void | Promise<void>;
};

function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

export function ManualFillForm({ procedure, values, onPatch }: Props) {
  const remaining: ProcedureField[] = procedure.fields.filter(
    (f) => !isFilled(values[f.name]),
  );
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onPatch(draft);
    } finally {
      setSubmitting(false);
    }
  }

  if (remaining.length === 0) {
    return <p className="text-sm text-muted-foreground">Toate câmpurile sunt completate.</p>;
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      {remaining.map((f) => (
        <div key={f.name} className="space-y-1">
          <Label htmlFor={f.name}>
            {f.label}
            {f.required ? <span aria-hidden> *</span> : null}
          </Label>
          {f.options ? (
            <select
              id={f.name}
              required={f.required}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={draft[f.name] ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, [f.name]: e.target.value }))}
            >
              <option value="" disabled>
                — alege —
              </option>
              {f.options.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          ) : (
            <Input
              id={f.name}
              required={f.required}
              defaultValue={f.suggest_default}
              value={draft[f.name] ?? f.suggest_default ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, [f.name]: e.target.value }))}
            />
          )}
        </div>
      ))}
      <Button type="submit" disabled={submitting}>
        {submitting ? "Se salvează..." : "Salvează"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 3: Implement GuidedFillFlow**

`frontend/components/GuidedFillFlow.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Procedure, ProcedureField } from "@/lib/types";

type Props = {
  procedure: Procedure;
  values: Record<string, unknown>;
  onPatch: (delta: Record<string, unknown>) => void | Promise<void>;
  onActiveFieldChange?: (name: string | undefined) => void;
};

function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

export function GuidedFillFlow({ procedure, values, onPatch, onActiveFieldChange }: Props) {
  const remaining: ProcedureField[] = useMemo(
    () => procedure.fields.filter((f) => !isFilled(values[f.name])),
    [procedure.fields, values],
  );
  const current = remaining[0];
  const [draft, setDraft] = useState("");

  if (!current) {
    return <p className="text-sm text-muted-foreground">Toate câmpurile sunt completate.</p>;
  }

  onActiveFieldChange?.(current.name);

  async function submit() {
    const value = draft.trim() || current?.suggest_default || "";
    if (!value && current?.required) return;
    await onPatch({ [current!.name]: value });
    setDraft("");
  }

  return (
    <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
      <p className="text-base">
        <strong>{current.label}</strong>
        {current.suggest_default ? (
          <span className="ml-2 text-sm text-muted-foreground">
            (sugestie: {current.suggest_default})
          </span>
        ) : null}
      </p>

      {current.options ? (
        <div className="flex flex-wrap gap-2">
          {current.options.map((opt) => (
            <Button
              key={opt}
              size="lg"
              variant="outline"
              onClick={async () => {
                await onPatch({ [current.name]: opt });
              }}
            >
              {opt}
            </Button>
          ))}
        </div>
      ) : (
        <div className="flex gap-2">
          <Label htmlFor={`guided-${current.name}`} className="sr-only">
            {current.label}
          </Label>
          <Input
            id={`guided-${current.name}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={current.suggest_default ?? ""}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void submit();
              }
            }}
          />
          <Button onClick={submit}>OK</Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Implement VocalFillFlow (UI shell only — stub will throw)**

`frontend/components/VocalFillFlow.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useVoiceAgent } from "@/lib/useVoiceAgent";
import type { Procedure, VoicePreferences } from "@/lib/types";

type Props = {
  procedure: Procedure;
  documentId: string;
  values: Record<string, unknown>;
  onPatch: (delta: Record<string, unknown>) => void | Promise<void>;
  preferences?: VoicePreferences;
};

export function VocalFillFlow({ procedure, documentId, preferences }: Props) {
  void procedure;
  const agent = useVoiceAgent();
  const [transcript, setTranscript] = useState("");
  const [agentMsg, setAgentMsg] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setError(null);
    try {
      await agent.start({
        documentId,
        preferences,
        onAgentMessage: (m) => setAgentMsg(m),
        onTranscript: (t) => setTranscript(t),
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => () => agent.stop(), [agent]);

  return (
    <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
      <div className="flex items-center gap-3">
        <Button onClick={start} disabled={agent.state !== "idle"} size="lg">
          {agent.state === "idle" ? "Pornește conversația vocală" : agent.state}
        </Button>
        <span className="text-xs text-muted-foreground">Stare: {agent.state}</span>
      </div>

      <section aria-live="polite" className="space-y-2">
        <div>
          <p className="text-xs font-medium uppercase text-muted-foreground">Tu</p>
          <p className="rounded bg-background p-3 text-sm">{transcript || "..."}</p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-muted-foreground">Asistent</p>
          <p className="rounded bg-background p-3 text-sm">{agentMsg || "..."}</p>
        </div>
      </section>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error} — folosește butoanele de text până la activare.
        </p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Tests pass**

```bash
npm run test
npm run build
```

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/ManualFillForm.tsx frontend/components/ManualFillForm.test.tsx frontend/components/GuidedFillFlow.tsx frontend/components/VocalFillFlow.tsx
git commit -m "feat(plan-1): manual + guided + vocal fill flows"
```

---

### Task 21: Procedure flow page `/req/[id]`

**Files:**
- Create: `frontend/app/req/new/page.tsx`
- Create: `frontend/app/req/[id]/page.tsx`

- [ ] **Step 1: `/req/new` triggers RAG lookup then creates document**

`frontend/app/req/new/page.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getSession } from "@/lib/session";
import type { ProcedureLookupMatch } from "@/lib/types";

export default function NewRequestPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ProcedureLookupMatch[] | null>(null);
  const [redirectCandidate, setRedirectCandidate] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !getSession()) router.replace("/login");
  }, [router]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMatches(null);
    setRedirectCandidate(null);
    try {
      const r = await api.lookupProcedure({ query });
      setMatches(r.matches);
      setRedirectCandidate(r.redirect_candidate);
    } catch (e) {
      if (e instanceof ApiError) setError(t("common.error"));
      else throw e;
    } finally {
      setLoading(false);
    }
  }

  async function pick(procedureId: string) {
    const doc = await api.createDocument({ procedure_id: procedureId });
    router.push(`/req/${doc.id}`);
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle>Ce ai nevoie de la primărie?</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex gap-2" onSubmit={search}>
            <div className="flex-1">
              <Label htmlFor="query" className="sr-only">
                Descrie ce ai nevoie
              </Label>
              <Input
                id="query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ex: vreau să-mi schimb domiciliul"
                required
              />
            </div>
            <Button type="submit" disabled={loading || !query.trim()}>
              {loading ? t("common.loading") : "Caută"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {matches && matches.length > 0 ? (
        <ul className="space-y-3">
          {matches.map((m) => (
            <li key={m.procedure_id}>
              <Card className="cursor-pointer transition hover:bg-accent/40">
                <CardContent
                  className="flex items-center justify-between p-4"
                  onClick={() => void pick(m.procedure_id)}
                >
                  <div>
                    <p className="font-medium">{m.title}</p>
                    <p className="text-xs text-muted-foreground">
                      Potrivire: {(m.score * 100).toFixed(0)}%
                    </p>
                  </div>
                  <Button>{t("common.continue")}</Button>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      ) : null}

      {redirectCandidate ? (
        <Card className="border-amber-500">
          <CardContent className="space-y-2 p-4">
            <p className="font-medium">
              Asta nu e treaba primăriei — te ducem la {redirectCandidate}.
            </p>
            <p className="text-sm text-muted-foreground">
              Pe roadmap avem integrarea directă. Momentan, vă rugăm vizitați site-ul instituției.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </main>
  );
}
```

- [ ] **Step 2: `/req/[id]` page**

`frontend/app/req/[id]/page.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ChatPanel } from "@/components/ChatPanel";
import { CompletionModeSelector } from "@/components/CompletionModeSelector";
import { FormPreview } from "@/components/FormPreview";
import { GuidedFillFlow } from "@/components/GuidedFillFlow";
import { KioskShell } from "@/components/KioskShell";
import { ManualFillForm } from "@/components/ManualFillForm";
import { VocalFillFlow } from "@/components/VocalFillFlow";
import { api } from "@/lib/api";
import {
  loadPersistedMode,
  persistMode,
  reduceCompletionMode,
  type CompletionMode,
} from "@/lib/completionMode";
import { getVariant, t } from "@/lib/i18n";
import { useKioskMode } from "@/lib/kioskMode";
import { getSession } from "@/lib/session";
import type {
  ChatMessage,
  Citizen,
  Document,
  Procedure,
} from "@/lib/types";

function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

function buildAutoFillSummary(procedure: Procedure, values: Record<string, unknown>): {
  filled: { label: string; value: string }[];
  missingCount: number;
} {
  const filled: { label: string; value: string }[] = [];
  let missing = 0;
  for (const f of procedure.fields) {
    const v = values[f.name];
    if (isFilled(v)) filled.push({ label: f.label, value: String(v) });
    else if (f.required) missing += 1;
  }
  return { filled, missingCount: missing };
}

export default function ProcedureFlowPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const docId = params.id;
  const isKiosk = useKioskMode();

  const [doc, setDoc] = useState<Document | null>(null);
  const [procedure, setProcedure] = useState<Procedure | null>(null);
  const [citizen, setCitizen] = useState<Citizen | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeField, setActiveField] = useState<string | undefined>(undefined);
  const [delivering, setDelivering] = useState<"save" | "send" | "print" | null>(null);
  const [refNumber, setRefNumber] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [modeState, dispatchMode] = useReducer(reduceCompletionMode, { mode: null });

  useEffect(() => {
    if (typeof window !== "undefined" && !getSession()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    void (async () => {
      try {
        const d = await api.getDocument(docId);
        const p = await api.getProcedure(d.procedure_id);
        const c = await api.getCitizenMe();
        setDoc(d);
        setProcedure(p);
        setCitizen(c);
        const persisted = loadPersistedMode(d.id);
        if (persisted) dispatchMode({ type: "CHOOSE", mode: persisted });
      } catch {
        setError(t("common.error"));
      }
    })();
  }, [docId]);

  useEffect(() => {
    if (doc) persistMode(doc.id, modeState.mode);
  }, [doc, modeState.mode]);

  const variant = useMemo(() => getVariant(citizen?.attributes), [citizen]);

  if (error) return <p role="alert" className="p-6 text-destructive">{error}</p>;
  if (!doc || !procedure || !citizen)
    return <p className="p-6 text-muted-foreground">{t("common.loading")}</p>;

  const summary = buildAutoFillSummary(procedure, doc.fields);

  async function patchFields(delta: Record<string, unknown>) {
    const updated = await api.patchDocumentFields(doc!.id, delta);
    setDoc(updated);
  }

  async function deliver(channel: "save" | "send" | "print") {
    setDelivering(channel);
    try {
      await api.generatePdf(doc!.id);
      const updated = await api.deliverDocument(doc!.id, channel);
      setDoc(updated);
      if (updated.ref_number) setRefNumber(updated.ref_number);
    } catch {
      setError(t("common.error"));
    } finally {
      setDelivering(null);
    }
  }

  const allFilled =
    procedure.fields.filter((f) => f.required && !isFilled(doc.fields[f.name])).length === 0;

  const completionPane = (() => {
    if (!modeState.mode) {
      return (
        <div className="space-y-4">
          <p>{t("req.auto_filled_intro", {}, variant)}</p>
          <ul className="space-y-1 text-sm">
            {summary.filled.map((f) => (
              <li key={f.label}>
                <span aria-hidden>✓ </span>
                <strong>{f.label}:</strong> {f.value}
              </li>
            ))}
          </ul>
          <p>{t("req.more_needed", { count: summary.missingCount }, variant)}</p>
          <CompletionModeSelector
            current={null}
            onChange={(m) => dispatchMode({ type: "CHOOSE", mode: m })}
          />
        </div>
      );
    }
    if (modeState.mode === "manual") {
      return <ManualFillForm procedure={procedure} values={doc.fields} onPatch={patchFields} />;
    }
    if (modeState.mode === "guided") {
      return (
        <GuidedFillFlow
          procedure={procedure}
          values={doc.fields}
          onPatch={patchFields}
          onActiveFieldChange={setActiveField}
        />
      );
    }
    return (
      <VocalFillFlow
        procedure={procedure}
        documentId={doc.id}
        values={doc.fields}
        onPatch={patchFields}
        preferences={{
          simple_language: citizen.attributes.accessibility?.simple_language,
          voice_only: citizen.attributes.accessibility?.voice_only,
        }}
      />
    );
  })();

  const body = (
    <div className="grid h-[calc(100vh-3rem)] gap-4 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-4 overflow-auto">
        <Card>
          <CardContent className="space-y-2 p-4">
            <h1 className="text-2xl font-bold">
              {t("req.title", { title: procedure.title })}
            </h1>
            {modeState.mode ? (
              <CompletionModeSelector
                current={modeState.mode}
                variant="switcher"
                onChange={(m) => dispatchMode({ type: "SWITCH", mode: m })}
              />
            ) : null}
          </CardContent>
        </Card>

        <Card className="flex-1">
          <CardContent className="space-y-4 p-4">{completionPane}</CardContent>
        </Card>

        <Card className="h-[40%] min-h-[16rem]">
          <CardContent className="h-full p-0">
            <ChatPanel
              documentId={doc.id}
              messages={messages}
              onMessagesChange={setMessages}
              preferences={{
                simple_language: citizen.attributes.accessibility?.simple_language,
                voice_only: citizen.attributes.accessibility?.voice_only,
              }}
            />
          </CardContent>
        </Card>

        {allFilled && doc.status !== "finalized" ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap gap-2"
          >
            <Button
              onClick={() => void deliver("save")}
              disabled={delivering !== null}
              variant="outline"
            >
              {t("delivery.save")}
            </Button>
            <Button
              onClick={() => void deliver("send")}
              disabled={delivering !== null}
            >
              {t("delivery.send")}
            </Button>
            <Button
              onClick={() => void deliver("print")}
              disabled={delivering !== null}
              variant="outline"
            >
              {t("delivery.print")}
            </Button>
          </motion.div>
        ) : null}

        {refNumber ? (
          <Card className="border-green-600">
            <CardContent className="p-4">
              <p className="font-medium">
                {t("delivery.confirmation", { ref: refNumber }, variant)}
              </p>
            </CardContent>
          </Card>
        ) : null}
      </div>

      <div className="overflow-auto">
        <FormPreview
          procedure={procedure}
          values={doc.fields}
          activeField={activeField}
        />
      </div>
    </div>
  );

  return isKiosk ? <KioskShell>{body}</KioskShell> : <main>{body}</main>;
}
```

- [ ] **Step 3: Build green**

```bash
npm run build
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/app/req/
git commit -m "feat(plan-1): /req/new + /req/[id] procedure flow with all three modes"
```

---

### Task 22: AuditTimeline + document detail page

**Files:**
- Create: `frontend/components/AuditTimeline.tsx`
- Create: `frontend/components/AuditTimeline.test.tsx`
- Create: `frontend/app/doc/[id]/page.tsx`

- [ ] **Step 1: Failing test for AuditTimeline**

`frontend/components/AuditTimeline.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuditTimeline } from "./AuditTimeline";
import type { LedgerResponse } from "@/lib/types";

const ledger: LedgerResponse = {
  verified: true,
  entries: [
    {
      id: 1,
      event_type: "doc_created",
      payload_hash: "0xa",
      prev_hash: "0x0",
      row_hash: "0xb",
      created_at: "2026-05-23T10:00:00.000Z",
    },
    {
      id: 2,
      event_type: "delivered",
      payload_hash: "0xc",
      prev_hash: "0xb",
      row_hash: "0xd",
      created_at: "2026-05-23T10:05:00.000Z",
    },
  ],
};

describe("AuditTimeline", () => {
  it("renders verified state", () => {
    render(<AuditTimeline ledger={ledger} />);
    expect(screen.getByText(/Chain verificat/i)).toBeInTheDocument();
  });

  it("renders unverified warning", () => {
    render(<AuditTimeline ledger={{ ...ledger, verified: false }} />);
    expect(screen.getByText(/lanț de verificare deteriorat/i)).toBeInTheDocument();
  });

  it("lists each event in Romanian", () => {
    render(<AuditTimeline ledger={ledger} />);
    expect(screen.getByText(/Document creat/i)).toBeInTheDocument();
    expect(screen.getByText(/Trimis/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement AuditTimeline**

`frontend/components/AuditTimeline.tsx`:

```tsx
"use client";

import type { LedgerEntry, LedgerResponse } from "@/lib/types";
import { t } from "@/lib/i18n";

const EVENT_LABEL: Record<LedgerEntry["event_type"], string> = {
  doc_created: "Document creat",
  completed_draft: "Ciornă completată",
  pdf_generated: "PDF generat",
  delivered: "Trimis la primărie",
  redirected: "Redirecționat",
  reminder_created: "Reminder creat",
};

type Props = {
  ledger: LedgerResponse;
};

export function AuditTimeline({ ledger }: Props) {
  return (
    <section aria-labelledby="audit-heading" className="space-y-4">
      <h2 id="audit-heading" className="text-xl font-semibold">
        {t("doc.audit_title")}
      </h2>

      <ol className="relative space-y-4 border-l-2 border-muted pl-6">
        {ledger.entries.map((e) => (
          <li key={e.id} className="relative">
            <span
              aria-hidden
              className="absolute -left-[1.55rem] top-1 h-3 w-3 rounded-full bg-primary"
            />
            <p className="font-medium">{EVENT_LABEL[e.event_type]}</p>
            <p className="text-xs text-muted-foreground">
              {new Date(e.created_at).toLocaleString("ro-RO")}
            </p>
            <p className="break-all font-mono text-[10px] text-muted-foreground/80">
              row_hash: {e.row_hash}
            </p>
          </li>
        ))}
      </ol>

      <p
        role="status"
        className={
          ledger.verified ? "text-sm font-medium text-green-700" : "text-sm font-medium text-destructive"
        }
      >
        {ledger.verified ? `✓ ${t("doc.audit_verified")}` : `⚠ ${t("doc.audit_unverified")}`}
      </p>
    </section>
  );
}
```

- [ ] **Step 3: Document detail page**

`frontend/app/doc/[id]/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AuditTimeline } from "@/components/AuditTimeline";
import { FormPreview } from "@/components/FormPreview";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getSession } from "@/lib/session";
import type { Document, LedgerResponse, Procedure } from "@/lib/types";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [doc, setDoc] = useState<Document | null>(null);
  const [procedure, setProcedure] = useState<Procedure | null>(null);
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !getSession()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    void (async () => {
      try {
        const d = await api.getDocument(params.id);
        const p = await api.getProcedure(d.procedure_id);
        const l = await api.getDocumentLedger(d.id);
        setDoc(d);
        setProcedure(p);
        setLedger(l);
      } catch {
        setError(t("common.error"));
      }
    })();
  }, [params.id]);

  if (error) return <p role="alert" className="p-6 text-destructive">{error}</p>;
  if (!doc || !procedure || !ledger)
    return <p className="p-6 text-muted-foreground">{t("common.loading")}</p>;

  return (
    <main className="mx-auto grid max-w-5xl gap-6 p-6 md:grid-cols-[2fr_3fr]">
      <div className="space-y-4">
        <Card>
          <CardContent className="space-y-3 p-4">
            <h1 className="text-2xl font-bold">{procedure.title}</h1>
            <p className="text-sm text-muted-foreground">
              Stare:{" "}
              {doc.status === "finalized" ? "Trimisă" : "În lucru"}
              {doc.ref_number ? ` · ${t("doc.ref_number", { ref: doc.ref_number })}` : ""}
            </p>
            {doc.pdf_url ? (
              <a href={doc.pdf_url} target="_blank" rel="noreferrer">
                <Button variant="outline">{t("doc.download_pdf")}</Button>
              </a>
            ) : null}
            {doc.status !== "finalized" ? (
              <Link href={`/req/${doc.id}`}>
                <Button>{t("common.continue")}</Button>
              </Link>
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <AuditTimeline ledger={ledger} />
          </CardContent>
        </Card>
      </div>
      <FormPreview procedure={procedure} values={doc.fields} />
    </main>
  );
}
```

- [ ] **Step 4: Tests pass + build**

```bash
npm run test
npm run build
```

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/AuditTimeline.tsx frontend/components/AuditTimeline.test.tsx frontend/app/doc/
git commit -m "feat(plan-1): /doc/[id] with AuditTimeline + ledger fetch"
```

---

### Task 23: AccessibilityToggles UI (Plan 4 wires behavior)

**Files:**
- Replace: `frontend/components/AccessibilityToggles.tsx`
- Create: `frontend/components/AccessibilityToggles.test.tsx`

- [ ] **Step 1: Failing test**

`frontend/components/AccessibilityToggles.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccessibilityToggles } from "./AccessibilityToggles";

describe("AccessibilityToggles", () => {
  it("renders three toggles", () => {
    render(<AccessibilityToggles />);
    expect(screen.getByRole("switch", { name: /Mod vocal/i })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /Explică-mi mai simplu/i })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /Text mai mare/i })).toBeInTheDocument();
  });

  it("persists state to localStorage", async () => {
    render(<AccessibilityToggles />);
    await userEvent.click(screen.getByRole("switch", { name: /Mod vocal/i }));
    const raw = window.localStorage.getItem("civicai.a11y");
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw!).voice_only).toBe(true);
  });
});
```

- [ ] **Step 2: Implement the UI toggles (no behavior wiring — Plan 4 does)**

Replace `frontend/components/AccessibilityToggles.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";

const KEY = "civicai.a11y";

type State = {
  voice_only: boolean;
  simple_language: boolean;
  large_text: boolean;
};

const defaults: State = {
  voice_only: false,
  simple_language: false,
  large_text: false,
};

function load(): State {
  if (typeof window === "undefined") return defaults;
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return defaults;
  try {
    return { ...defaults, ...(JSON.parse(raw) as Partial<State>) };
  } catch {
    return defaults;
  }
}

function persist(s: State) {
  window.localStorage.setItem(KEY, JSON.stringify(s));
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-lg border bg-background p-3">
      <span className="text-sm font-medium">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={
          checked
            ? "h-7 w-12 rounded-full bg-primary transition"
            : "h-7 w-12 rounded-full bg-muted transition"
        }
      >
        <span
          aria-hidden
          className={
            checked
              ? "block h-6 w-6 translate-x-5 rounded-full bg-white shadow transition"
              : "block h-6 w-6 translate-x-1 rounded-full bg-white shadow transition"
          }
        />
      </button>
    </label>
  );
}

export function AccessibilityToggles() {
  const [state, setState] = useState<State>(defaults);

  useEffect(() => {
    setState(load());
  }, []);

  function update<K extends keyof State>(k: K, v: State[K]) {
    setState((prev) => {
      const next = { ...prev, [k]: v };
      persist(next);
      return next;
    });
  }

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Toggle
        label={t("a11y.voice_only")}
        checked={state.voice_only}
        onChange={(v) => update("voice_only", v)}
      />
      <Toggle
        label={t("a11y.simple_language")}
        checked={state.simple_language}
        onChange={(v) => update("simple_language", v)}
      />
      <Toggle
        label={t("a11y.large_text")}
        checked={state.large_text}
        onChange={(v) => update("large_text", v)}
      />
    </div>
  );
}
```

- [ ] **Step 3: Tests pass**

```bash
npm run test
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/components/AccessibilityToggles.tsx frontend/components/AccessibilityToggles.test.tsx
git commit -m "feat(plan-1): AccessibilityToggles UI (behavior wired by Plan 4)"
```

---

### Task 24: WCAG AA baseline pass (focus, ARIA, contrast, axe-core E2E)

**Files:**
- Modify: `frontend/app/globals.css` (focus-visible ring + reduced-motion)
- Create: `frontend/e2e/a11y.spec.ts`

- [ ] **Step 1: Ensure focus rings + reduced-motion in globals.css**

Append to `frontend/app/globals.css`:

```css
@layer base {
  *:focus-visible {
    outline: 2px solid hsl(var(--ring));
    outline-offset: 2px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
  }
}
```

- [ ] **Step 2: Write axe-core Playwright spec**

`frontend/e2e/a11y.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const pages = [
  { name: "login", path: "/login" },
  { name: "otp", path: "/login/otp?challenge_id=ch&phone_hint=***1234" },
];

for (const p of pages) {
  test(`a11y: ${p.name}`, async ({ page }) => {
    await page.goto(p.path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
  });
}
```

- [ ] **Step 3: Run E2E + verify**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npm run e2e
```

Expected: a11y specs pass. If any violation, fix in components and re-run.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/app/globals.css frontend/e2e/a11y.spec.ts
git commit -m "chore(plan-1): focus-visible + reduced-motion + axe-core E2E"
```

---

### Task 25: Playwright E2E for login + procedure flow against MSW

**Files:**
- Create: `frontend/e2e/login-procedure.spec.ts`

- [ ] **Step 1: Write the spec**

`frontend/e2e/login-procedure.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("citizen logs in and completes a procedure end-to-end", async ({ page }) => {
  await page.goto("/login");

  await page.getByRole("button", { name: /Login cu ROeID/i }).click();
  await expect(page).toHaveURL(/\/login\/otp\?/);

  await page.getByLabel(/Cod OTP/i).fill("123456");
  await expect(page).toHaveURL("/");

  await expect(page.getByRole("heading", { name: /Bună ziua/i })).toBeVisible();

  await page.getByRole("link", { name: /Start o cerere nouă|Începe o cerere nouă/i }).click();
  await page
    .getByPlaceholder(/Ex: vreau să-mi schimb domiciliul/i)
    .fill("vreau să-mi schimb domiciliul");
  await page.getByRole("button", { name: "Caută" }).click();
  await page.getByRole("button", { name: /Continuă/i }).first().click();

  await expect(page.getByRole("heading", { name: /Cerere:/i })).toBeVisible();
  await page.getByRole("radio", { name: /Manual/i }).click();

  await page.getByLabel(/Adresă nouă/i).fill("Str. Plopilor 15, Cluj-Napoca");
  await page.getByLabel(/Tip proprietate/i).selectOption("proprietar");
  await page.getByLabel(/Motivul cererii/i).fill("Schimbare loc de muncă");

  await page.getByRole("button", { name: /Salvează/i }).click();

  await page.getByRole("button", { name: /Trimite la primărie/i }).click();
  await expect(page.getByText(/Număr de înregistrare:/i)).toBeVisible({ timeout: 10_000 });
});
```

- [ ] **Step 2: Ensure MSW is on by default during E2E**

Add to `frontend/playwright.config.ts` under `use`:

```ts
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    locale: "ro-RO",
  },
  // ...
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { NEXT_PUBLIC_USE_MOCKS: "1", NEXT_PUBLIC_DEMO_MODE: "1" },
  },
```

(Edit the existing `webServer` block to include `env`.)

- [ ] **Step 3: Run E2E**

```bash
npm run e2e
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/e2e/login-procedure.spec.ts frontend/playwright.config.ts
git commit -m "test(plan-1): E2E login + procedure flow against MSW"
```

---

### Task 26: Vercel deploy + smoke test

**Files:**
- Create: `frontend/vercel.json`
- Modify: `frontend/README.md`

- [ ] **Step 1: Login to Vercel + link the project**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon/frontend
npx --yes vercel@latest login
npx --yes vercel@latest link --yes --project civicai-frontend
```

Expected: writes `frontend/.vercel/`.

- [ ] **Step 2: Configure rewrites for the API base (Wave 1 still uses MSW in browser; this aligns post-Checkpoint 1)**

`frontend/vercel.json`:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "installCommand": "npm install",
  "framework": "nextjs",
  "regions": ["fra1"],
  "github": { "silent": true }
}
```

- [ ] **Step 3: Set required env vars on Vercel for the Preview environment**

```bash
npx --yes vercel@latest env add NEXT_PUBLIC_DEMO_MODE preview --yes <<< "1"
npx --yes vercel@latest env add NEXT_PUBLIC_USE_MOCKS preview --yes <<< "1"
npx --yes vercel@latest env add NEXT_PUBLIC_API_BASE_URL preview --yes <<< "https://civicai-backend-staging.example.com"
```

(If Plan 2's backend URL is not yet known, use a placeholder; MSW will short-circuit network calls regardless.)

- [ ] **Step 4: Deploy preview**

```bash
npx --yes vercel@latest --yes
```

Capture the deployed URL printed at the end of the command (e.g. `https://civicai-frontend-xxxx.vercel.app`).

- [ ] **Step 5: Smoke test the deployed URL**

```bash
npx --yes playwright test --config frontend/playwright.config.ts -g "smoke" --reporter=line
```

Override `baseURL` for this run:

```bash
PLAYWRIGHT_BASE_URL=https://civicai-frontend-xxxx.vercel.app npx --yes playwright test --config frontend/playwright.config.ts -g "home page renders CivicAI button"
```

(If your shell does not support inline env-vars — common on PowerShell — set `$env:PLAYWRIGHT_BASE_URL` first; on bash use the inline form above.)

Update `playwright.config.ts` `use.baseURL` to honor `PLAYWRIGHT_BASE_URL` if it exists:

```ts
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000",
    // ...
  },
```

- [ ] **Step 6: Update frontend README with deploy URL**

`frontend/README.md`:

```markdown
# CivicAI — Frontend (Plan 1)

Next.js 15 + Tailwind + shadcn/ui + framer-motion.

## Quickstart
```bash
npm install
cp .env.local.example .env.local
npm run dev
```

## Tests
- `npm run test` — Vitest unit + component tests.
- `npm run e2e` — Playwright E2E against MSW mocks.

## Deploys
Preview: <paste preview URL from Task 26>

## Checkpoint 1 handoff
- Set `NEXT_PUBLIC_USE_MOCKS=0` and `NEXT_PUBLIC_API_BASE_URL=https://<railway-url>` to switch to the real Plan 2 backend.
- Delete `frontend/mocks/` once integration is verified.
```

- [ ] **Step 7: Commit**

```bash
cd C:/Users/Bogdan/Documents/ClujHackathon
git add frontend/vercel.json frontend/README.md frontend/playwright.config.ts
git commit -m "chore(plan-1): Vercel preview deploy + smoke test config"
```

---

## Self-review checklist

- [ ] Every Plan 1 scope item from roadmap §6 is covered:
  - Next.js 15 + Tailwind + shadcn + framer-motion → Tasks 1, 2.
  - All page routes (`/`, `/login`, `/login/otp`, `/req/[id]`, `/doc/[id]`) → Tasks 14, 15, 16, 21, 22.
  - Kiosk-mode detection → Task 9 (logic) + Task 15 (UI shell).
  - Browser-side MRZ → Tasks 11, 12.
  - All UI components from roadmap §2 → Tasks 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 23.
  - API client + types → Tasks 5, 6.
  - MSW for Wave 1 → Task 7.
  - `useVoiceAgent` stub → Task 10.
  - Romanian i18n with `.standard`/`.simple` → Task 8.
  - WCAG AA baseline → Task 24.
  - Vercel deploy → Task 26.
- [ ] Every Checkpoint 1 frontend requirement from roadmap §5 has a task:
  - Deployed to Vercel → Task 26.
  - `/login` → OTP → session → Tasks 14 + 15.
  - `/` with citizen profile → Task 16.
  - `/?mode=kiosk` with MRZ scanner → Tasks 9 + 12 + 15.
  - MRZ parses test buletin → Tasks 11 + 12.
  - `/req/[id]` chat + preview side-by-side → Task 21.
  - Preview updates as fields fill → Tasks 17 + 21.
  - Save/Send/Print → Task 21.
  - `/doc/[id]` audit timeline → Task 22.
  - Lighthouse a11y ≥ 95 → Task 24.

---

## Notes for the executing agent

- Wave 1 ships with MSW intercepting every backend call. Plan 2 may deploy in parallel; do not block on its URL.
- After Checkpoint 1, set `NEXT_PUBLIC_USE_MOCKS=0` on Vercel and delete `frontend/mocks/`.
- `useVoiceAgent` is a stub; clicking the "Vocal" mode start button surfaces the `Voice not yet implemented` error in red text. This is expected — Plan 3 replaces the hook body.
- `AccessibilityToggles` persists toggle state but applies no behavior in Wave 1; Plan 4 hooks `voice_only` to the voice session and `simple_language` to the chat request body, and adds the `large_text` Tailwind class to the `<html>` element.
- `ReminderCard` action buttons are disabled in Wave 1. Plan 4 enables "Start now" (creates a doc) and "Vezi cum" (external redirect dialog).
- Framer-motion is used minimally (`FormPreview` field highlight, delivery panel fade-in). Plan 4 adds page transitions and reminder card entry animations.
