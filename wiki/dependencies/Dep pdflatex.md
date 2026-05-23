---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dep: pdflatex

System binary used by [[pdf]] to render LaTeX templates to PDFs. Called via `subprocess`. Must be on `PATH`.

## Required packages

Per [[Dockerfile]] (Debian-slim base):

```
texlive-latex-base
texlive-latex-recommended
texlive-latex-extra
texlive-fonts-recommended
texlive-lang-european       # Romanian diacritics + babel
lmodern                      # better-looking serif default
```

## Why two passes

```python
for _ in range(2):
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", d, tex_path], ...)
```

Two passes resolve internal references (ToC, cross-refs). For simple forms one is enough, but the templates can use `\ref{}` for section numbers — second pass needed.

## Asset handling

`_copy_assets(d)` copies `templates/base.tex` and `templates/assets/` next to the rendered `.tex` so the template can `\input{base.tex}` and `\includegraphics{assets/stema.png}`.

## Timeout

60s. If pdflatex hangs (rare), the request fails with `RuntimeError` + the tail of `doc.log`.

## Windows dev

Use MiKTeX or TeX Live for Windows. Put `pdflatex.exe` on `PATH`. Test via `pdflatex --version`.

## Why pdflatex instead of WeasyPrint / wkhtmltopdf / pyfpdf

LaTeX gives us pixel-perfect Romanian forms that match the actual primărie paperwork. WeasyPrint can't quite match the typographic feel; the others can't match Romanian diacritics + form-style layout. Trade dev complexity for output quality.

## See also

- [[pdf]]
- [[Dockerfile]]
- templates/*.tex — actual templates
