---
type: module
path: "backend/Dockerfile"
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dockerfile

`python:3.12-slim` + texlive + the backend.

## Stages

```dockerfile
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended texlive-lang-european lmodern curl \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY app ./app
COPY procedures ./procedures
COPY templates ./templates
COPY migrations ./migrations
COPY scenarios ./scenarios
COPY institutions ./institutions
COPY scripts ./scripts

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

## Why texlive in the image

[[pdf]] calls `pdflatex` via subprocess. The image installs:

- `texlive-latex-base`, `-recommended`, `-extra` — base macros + standard packages
- `texlive-fonts-recommended` — Latin Modern font
- `texlive-lang-european` — Romanian / Polish / Czech etc. babel data + hyphenation
- `lmodern` — explicit lmodern package for nicer defaults

Final image is ~1GB; texlive is most of it. Acceptable for hackathon.

## Layer hierarchy

1. Base image
2. texlive (rarely changes)
3. Python venv (rarely)
4. `pyproject.toml` + `pip install .` (changes on dep updates)
5. App code (changes per commit)

This ordering maximizes cache hits on app-only changes.

## Files NOT copied in

- `tests/` (not needed at runtime)
- `.venv/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/` (dev only — also blocked by `.dockerignore`)
- `.env` (provided by Railway's env config)
- `CHECKPOINT_1.md`, `RUNBOOK.md` (docs)

## See also

- [[Deployment Railway]]
- [[Dep pdflatex]]
- backend/.dockerignore
