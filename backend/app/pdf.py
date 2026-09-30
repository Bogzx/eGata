"""LaTeX field-substitution + pdflatex subprocess PDF compilation.

Field values come from citizens and from the model (set_field), so every one
is untrusted. Two layers keep them inert:

1. `escape_latex` makes a value plain text: the ten TeX specials are escaped
   (so no control sequence, group or `^^` escape can be formed), whitespace is
   collapsed (a blank line inside `\\underline{...}` ends the paragraph and
   aborts the run), and characters the preamble cannot typeset — control
   characters, emoji, CJK, Cyrillic — are folded to a base letter or `?`
   instead of killing the render.
2. pdflatex itself runs with shell escape off and kpathsea's paranoid file
   access, so even a template bug that let a command through could neither
   run a program nor read outside the build directory.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

log = logging.getLogger(__name__)


class PdfRenderError(RuntimeError):
    """pdflatex failed. The message is safe to show; the log stays server-side.

    The TeX log echoes the offending line — i.e. the citizen's CNP, name or
    address — so it goes to the server log, never into an HTTP response, a
    tool result the model reads, or the chat.
    """


class PdfRendererUnavailable(PdfRenderError):
    """pdflatex is not installed (or not on PATH)."""

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
_WHITESPACE_RE = re.compile(r"\s+")

# What base.tex (utf8 inputenc + babel romanian, OT1) can typeset, measured by
# compiling every code point U+00A0..U+024F plus common punctuation through
# real pdflatex. Everything outside this set is folded by `_fold_char`.
_UNSUPPORTED_LATIN = frozenset(
    "\u00d0\u00de\u00f0\u00fe"  # Ð Þ ð þ
    "\u0104\u0105\u0118\u0119\u0126\u0127\u012e\u012f\u0138"
    "\u013f\u0140\u0149\u014a\u014b\u0166\u0167\u0172\u0173\u017f"
    # Ĳ ĳ typeset alone, but as \char156 / \char188 with no terminator: a
    # digit after them extends the number ("Ĳ2" -> \char1562, "Bad character
    # code"). NFKD folds them to IJ / ij.
    "\u0132\u0133"
)
_EXTRA_SUPPORTED = frozenset(
    "\u0218\u0219\u021a\u021b"  # Ș ș Ț ț — comma-below, the correct Romanian forms
    "\u2010\u2011\u2012\u2013\u2014\u2015"  # hyphens and dashes
    "\u2018\u2019\u201a\u201c\u201d\u201e"  # quotes, incl. Romanian „ ”
    "\u2020\u2021\u2022\u2026\u2030\u2039\u203a\u20ac\u2122\u2116\u2044"
)


def _is_supported(ch: str) -> bool:
    cp = ord(ch)
    if 0x20 <= cp < 0x7F:
        return True
    if 0xA0 <= cp <= 0x17F:
        return ch not in _UNSUPPORTED_LATIN
    return ch in _EXTRA_SUPPORTED


def _fold_char(ch: str) -> str:
    """Nearest typesettable text for `ch`: itself, its base letter, or `?`."""
    if _is_supported(ch):
        return ch
    category = unicodedata.category(ch)
    if category in {"Cc", "Cf", "Cs", "Co", "Cn", "So"}:
        # Control / format / surrogate / private-use / unassigned characters
        # (pdflatex rejects most as "invalid character"), and pictographs —
        # an emoji has no place on a form and no sensible stand-in.
        return ""
    base = "".join(
        c
        for c in unicodedata.normalize("NFKD", ch)
        if not unicodedata.combining(c) and _is_supported(c)
    )
    return base or "?"


def sanitize_text(value: str) -> str:
    """Reduce an arbitrary string to text pdflatex will typeset.

    Whitespace runs (including newlines, tabs and blank lines) become a single
    space; unsupported characters are folded. TeX specials are left for
    `escape_latex`.
    """
    value = unicodedata.normalize("NFC", value)
    value = _WHITESPACE_RE.sub(" ", value)
    if all(_is_supported(c) for c in value):
        return value
    return "".join(_fold_char(c) for c in value)


def escape_latex(value: str) -> str:
    return _ESCAPE_RE.sub(lambda m: LATEX_ESCAPE_MAP[m.group(0)], sanitize_text(value))


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
    """Copy base.tex and the assets/ folder next to the rendered .tex."""
    base = TEMPLATES_DIR / "base.tex"
    if base.exists():
        shutil.copy(base, dest / "base.tex")
    assets_dir = TEMPLATES_DIR / "assets"
    if assets_dir.is_dir():
        shutil.copytree(assets_dir, dest / "assets", dirs_exist_ok=True)


# kpathsea reads these from the environment ahead of texmf.cnf. TeX Live's
# defaults are shell_escape=p (a whitelist of programs) and openin_any=a (read
# any file) — neither is needed to typeset a form.
_PDFLATEX_ENV = {"shell_escape": "f", "openin_any": "p", "openout_any": "p"}


def compile_pdf(tex_source: str) -> bytes:
    # ignore_cleanup_errors: on Windows the TeX distribution can still hold
    # doc.log open when the context manager exits, and the resulting
    # PermissionError would surface as a failure *after* a perfectly good PDF
    # had already been produced.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        d = Path(tmp)
        tex_path = d / "doc.tex"
        tex_path.write_text(tex_source, encoding="utf-8")
        _copy_assets(d)

        # Run pdflatex twice to resolve any internal references.
        for _ in range(2):
            try:
                result = subprocess.run(  # noqa: S603,S607
                    [
                        "pdflatex",
                        "-no-shell-escape",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        # Relative to cwd=d: with openin_any=p, TeX Live 2023
                        # (Ubuntu 24.04) refuses to open an absolute input path.
                        tex_path.name,
                    ],
                    cwd=d,
                    env={**os.environ, **_PDFLATEX_ENV},
                    capture_output=True,
                    check=False,
                    timeout=60,
                )
            except FileNotFoundError as exc:
                raise PdfRendererUnavailable(
                    "pdflatex is not installed on the server"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise PdfRenderError("PDF rendering timed out") from exc
            if result.returncode != 0:
                tex_log = (
                    (d / "doc.log").read_text(encoding="utf-8", errors="replace")
                    if (d / "doc.log").exists()
                    else ""
                )
                log.error(
                    "pdflatex failed rc=%s; log tail:\n%s",
                    result.returncode,
                    tex_log[-1500:],
                )
                raise PdfRenderError(
                    f"PDF rendering failed (pdflatex rc={result.returncode})"
                )

        pdf_path = d / "doc.pdf"
        if not pdf_path.exists():
            raise PdfRenderError("pdflatex produced no PDF")
        return pdf_path.read_bytes()


def render_and_compile(template_filename: str, fields: dict[str, Any]) -> bytes:
    template_path = TEMPLATES_DIR / template_filename
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_filename}")
    tex_source = render_template(template_path, fields)
    return compile_pdf(tex_source)
