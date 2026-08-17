> **Archived — describes a superseded architecture.**
>
> This document was written when eGata ran on a Gemini backend with a
> different set of HTTP endpoints. The agent now runs on Azure OpenAI through
> an in-process, state-gated tool dispatcher (`backend/app/session_engine.py`,
> `backend/app/agent_tools/`), and several endpoints referenced below no
> longer exist. Counts and status claims here also disagree with the current
> README. Kept for history; do not use it as a description of the system.

# Frontend Spec — Cluj Hackathon 2026

Small, opinionated stack chosen for a 48-hour build with a 25-point UX weight. Optimized for speed of execution, "wow" polish out of the box, and accessibility (WCAG AA) by default.

## Stack at a glance

| Layer       | Choice                          | Why                                                         |
|-------------|---------------------------------|-------------------------------------------------------------|
| Framework   | Next.js 15 (App Router)         | Lovable generates it natively; route transitions; SSR for SEO |
| Language    | TypeScript (strict)             | Catches dumb mistakes at 3 AM                               |
| Runtime     | React 19                        | Server Components reduce client JS                          |
| Styling     | Tailwind CSS v4                 | Fastest way to a clean, modern look                         |
| Components  | shadcn/ui (Radix under the hood)| AA accessibility built-in; copy-paste, no lock-in           |
| Icons       | Lucide                          | One coherent family (per guide's advice)                    |
| Animation   | Framer Motion                   | 150–300ms transitions and microinteractions trivially       |
| Forms       | React Hook Form + Zod           | Inline validation as you type                               |
| State       | Zustand (UI) + TanStack Query (async) | Tiny, no boilerplate                                  |
| Auth (sim)  | Auth.js v5 (Credentials + TOTP) | Simulates ROeID login + 2FA                                 |
| DB          | Supabase (Postgres)             | Free tier, instant API, RLS for access control              |
| Deploy      | Vercel                          | `git push` → live URL, preview per PR                       |
| Package mgr | pnpm                            | Faster installs, strict deps                                |

## Project structure

```
/app
  /(public)         # landing, login
  /(citizen)        # logged-in citizen area
  /(officer)        # civil-servant view (different RLS scope)
  /api              # route handlers (mock public-data endpoints)
/components
  /ui               # shadcn primitives
  /feature          # composed feature components
/lib
  /auth             # ROeID simulation + 2FA helpers
  /ledger           # simulated tamper-evident log (hash-chained)
  /mocks            # fixtures shaped like data.gov.ro / ANAF / etc.
  /validators       # Zod schemas (CNP, IBAN, dates)
/styles
  globals.css       # Tailwind base + design tokens
```

## Design tokens (Tailwind theme)

- **Spacing**: 4px base, generous (16/24/32 between sections).
- **Radius**: `--radius: 0.75rem` — modern, not cartoonish.
- **Type**: Inter (UI) + JetBrains Mono (code/IDs). System fallback first for performance.
- **Palette**: neutral slate base + one restrained accent. Avoid full Romanian-flag-as-UI — that screams "government website circa 2007".
- **Contrast**: every text/bg pair ≥ 4.5:1 (AA). Verified with the Tailwind a11y plugin.

## Animation rules

- Route transitions: `opacity + 4px translateY`, 200ms, `easeOut`.
- Buttons: scale `0.97` on press, 80ms.
- Skeletons (not spinners) for any load > 200ms.
- Respect `prefers-reduced-motion` — disable transitions, keep instant.

## Accessibility checklist

- All interactive elements reachable by Tab; visible focus ring.
- Forms: `<label>` linked to inputs, `aria-describedby` for help text.
- Toasts and modals announce via `role="status"` / Radix Dialog.
- No color-only state (always add icon or text).
- Test with VoiceOver / NVDA at least once before submit.

## Auth flow (simulated ROeID)

1. `POST /api/auth/credentials` → password check against seeded user.
2. Server generates 6-digit code, stores hash + 60s TTL in Redis (or in-memory map for demo).
3. UI shows 2FA screen → user enters code → session cookie set (HTTP-only, SameSite=Lax).
4. Optional WebAuthn step for "passkey" demo polish.

## "Immutable ledger" (simulated)

- Append-only `events` table: `{ id, prev_hash, payload, hash, signed_at }`.
- `hash = sha256(prev_hash + payload)`.
- A `/verify` endpoint walks the chain and reports the first broken link, if any.
- Enough to satisfy the guide's blockchain/ledger requirement without dragging in actual chain infra.

## Performance budget

- First Load JS < 200 KB on the citizen home.
- LCP < 2.5s on a throttled mid-tier Android.
- Images via `next/image`, AVIF where supported.
- Fonts: `next/font` with `display: swap`, subset to Latin Extended A (Romanian diacritics).

## Bootstrap commands

```bash
pnpm create next-app@latest noqueue --typescript --tailwind --app --eslint
cd noqueue
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button card dialog form input label sheet sonner tabs
pnpm add framer-motion zustand @tanstack/react-query zod react-hook-form @hookform/resolvers next-auth@beta
pnpm add -D @types/node prettier prettier-plugin-tailwindcss
```

## Done = these are true

- [ ] Deploys on Vercel from `main`.
- [ ] Login + 2FA work end-to-end with seeded user.
- [ ] One full citizen flow shippable on phone (no horizontal scroll, no tap targets < 44px).
- [ ] Lighthouse: Perf ≥ 90, A11y ≥ 95 on the demo pages.
- [ ] README explains the stack and how to run locally in < 3 commands.
