"""LaTeX field-substitution + pdflatex subprocess PDF compilation."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

LATEX_ESCAPE_MAP: dict[str, str] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_ESCAPE_RE = re.compile("|".join(re.escape(c) for c in LATEX_ESCAPE_MAP))
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def escape_latex(value: str) -> str:
    return _ESCAPE_RE.sub(lambda m: LATEX_ESCAPE_MAP[m.group(0)], value)


def render_template(template_path: Path, fields: dict[str, Any]) -> str:
    template = template_path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        raw = fields.get(key, "")
        if raw is None:
            raw = ""
        return escape_latex(str(raw))

    return _PLACEHOLDER_RE.sub(repl, template)


def _copy_assets(dest: Path) -> None:
    """Copy base.tex and other shared assets next to the rendered .tex."""
    base = TEMPLATES_DIR / "base.tex"
    if base.exists():
        shutil.copy(base, dest / "base.tex")


def compile_pdf(tex_source: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        tex_path = d / "doc.tex"
        tex_path.write_text(tex_source, encoding="utf-8")
        _copy_assets(d)

        # Run pdflatex twice to resolve any internal references.
        for _ in range(2):
            result = subprocess.run(  # noqa: S603,S607
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory",
                    str(d),
                    str(tex_path),
                ],
                cwd=d,
                capture_output=True,
                check=False,
                timeout=60,
            )
            if result.returncode != 0:
                log = (d / "doc.log").read_text(encoding="utf-8", errors="replace") if (d / "doc.log").exists() else ""
                raise RuntimeError(
                    f"pdflatex failed (rc={result.returncode}). Log tail:\n{log[-1500:]}"
                )

        pdf_path = d / "doc.pdf"
        if not pdf_path.exists():
            raise RuntimeError("pdflatex produced no PDF")
        return pdf_path.read_bytes()


def render_and_compile(template_filename: str, fields: dict[str, Any]) -> bytes:
    template_path = TEMPLATES_DIR / template_filename
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_filename}")
    tex_source = render_template(template_path, fields)
    return compile_pdf(tex_source)
