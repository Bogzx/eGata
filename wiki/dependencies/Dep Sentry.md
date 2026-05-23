---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dep: Sentry

Optional error reporting. Activated **only** when `SENTRY_DSN` env var is set.

## Setup

[[main]] checks `os.environ["SENTRY_DSN"]`. If present:

```python
sentry_sdk.init(
    dsn=...,
    environment=APP_ENV (default "production"),
    traces_sample_rate=float(SENTRY_TRACES_SAMPLE_RATE or "0.1"),
    integrations=[FastApiIntegration()],
    send_default_pii=False,    # CNPs, phones don't leak into Sentry
)
```

## Why `send_default_pii=False`

GDPR + the data we touch (CNPs, addresses, phones). Sentry must never see PII. The flag disables IP collection, request body capture, etc.

## Optional dep

If `sentry-sdk` isn't installed, the `import` is caught and Sentry stays off. App startup logs a warning and continues.

## See also

- [[main]]
- [[config]] — `APP_ENV`
