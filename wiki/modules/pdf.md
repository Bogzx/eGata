---
type: module
path: "backend/app/pdf.py"
status: active
language: python
purpose: "LaTeX template fill + pdflatex subprocess."
depends_on: []
used_by: [documents, agent_tools/complete_document]
created: 2026-05-23
updated: 2026-05-23
---

# pdf

Renders a `.tex` template with field values, escapes LaTeX-unsafe characters, runs `pdflatex` twice in a temp dir, returns the PDF bytes.

## Pipeline

```
fields dict ─► render_template ─► escaped .tex
                                     │
                                     ▼
                              compile_pdf (pdflatex × 2)
                                     │
                                     ▼
                                  PDF bytes
```

## `render_template(template_path, fields)`

Reads the template, replaces `{{ snake_case }}` placeholders with `escape_latex(str(value))`. Unknown placeholders become empty strings (never raises) — the template is the contract; missing keys are intentional.

## `escape_latex(value)`

Single regex over the LaTeX special chars: `\ & % $ # _ { } ~ ^`. Always called before substitution. **Security-critical**: a citizen-supplied field that contained `\input{/etc/passwd}` would otherwise execute. The five tests in `test_pdf.py` exist to keep this honest.

## `compile_pdf(tex_source)`

Writes the `.tex` to a tempdir, copies `templates/base.tex` and `templates/assets/` in, runs:

```
pdflatex -interaction=nonstopmode -halt-on-error -output-directory <tmp> <tmp>/doc.tex
```

twice (for internal references like ToC). On non-zero exit, reads the last 1500 chars of `doc.log` and raises `RuntimeError` with the tail. Timeout 60s.

> [!gotcha] `pdflatex` must be on `PATH`
> The Dockerfile ([[Dockerfile]]) installs `texlive-latex-base/recommended/extra/fonts-recommended/lang-european + lmodern`. On Windows dev you need MiKTeX or TeX Live + PATH set.

## `render_and_compile(template_filename, fields) → bytes`

The one-call helper used by [[documents]]`.generate_pdf` and [[complete_document]].

## See also

- [[Flow Document Lifecycle]]
- templates/*.tex — actual LaTeX templates
