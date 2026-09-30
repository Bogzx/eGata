"""Every one of the 23 templates must actually compile.

test_pdf.py only exercises `render_template` on a string; nothing ran
pdflatex over a real .tex in templates/. A template can therefore be
syntactically broken, reference a missing asset, or blow up on a value
containing `&` or `%` and no test would notice until a citizen clicked
"generate".

Opt-in via RUN_PDF_TESTS=1 because a full pass is ~23 pdflatex invocations
and needs TeX Live installed. CI runs it in its own job.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from app.pdf import TEMPLATES_DIR, render_and_compile

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROCEDURES_DIR = BACKEND_DIR / "procedures"
PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_PDF_TESTS") != "1",
        reason="RUN_PDF_TESTS=1 not set; skipping real pdflatex renders",
    ),
    pytest.mark.skipif(
        shutil.which("pdflatex") is None,
        reason="pdflatex not on PATH",
    ),
]

PROCEDURE_FILES = sorted(PROCEDURES_DIR.glob("*.json"))

# Values chosen to exercise LaTeX escaping (escape_latex) rather than to be
# realistic: & % $ # _ { } ~ ^ and backslash all have to survive.
HOSTILE = r"Str. Ștefan & Co. 100% #3 _x_ {y} ~z^2 \ampersand"


def _fields_for(proc: dict) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in proc.get("fields", []):
        name = field["name"]
        options = field.get("options")
        if options:
            values[name] = str(options[0])
        elif name == "cnp":
            values[name] = "2851014123456"
        elif "data" in name or "date" in name:
            values[name] = "01.01.2026"
        else:
            values[name] = HOSTILE
    return values


@pytest.mark.parametrize("proc_path", PROCEDURE_FILES, ids=lambda p: p.stem)
def test_template_compiles_to_a_pdf(proc_path: Path) -> None:
    proc = json.loads(proc_path.read_text(encoding="utf-8"))
    pdf = render_and_compile(proc["template"], _fields_for(proc))
    assert pdf.startswith(b"%PDF-"), f"{proc['id']}: output is not a PDF"
    assert len(pdf) > 1000, f"{proc['id']}: suspiciously small PDF ({len(pdf)} bytes)"


@pytest.mark.parametrize("proc_path", PROCEDURE_FILES, ids=lambda p: p.stem)
def test_no_placeholder_survives_into_the_output(proc_path: Path) -> None:
    """A `{{ name }}` left in the .tex means a typo'd placeholder that would
    print literal braces on the citizen's form."""
    from app.pdf import render_template

    proc = json.loads(proc_path.read_text(encoding="utf-8"))
    rendered = render_template(TEMPLATES_DIR / proc["template"], _fields_for(proc))
    leftover = PLACEHOLDER_RE.findall(rendered)
    assert not leftover, f"{proc['id']}: unsubstituted placeholders {leftover}"


def test_empty_fields_still_compile() -> None:
    """A citizen can generate a PDF from a partly-filled draft; missing values
    become empty strings (pdf.py) and must not break the document."""
    proc = json.loads((PROCEDURES_DIR / "schimbare-domiciliu.json").read_text(encoding="utf-8"))
    pdf = render_and_compile(proc["template"], {})
    assert pdf.startswith(b"%PDF-")


# Beyond the ten TeX specials: the inputs that used to abort pdflatex outright
# (control characters, emoji, non-Latin scripts, blank lines inside
# \underline{...}) and the classic injection attempts. Every template must
# still produce a PDF, and none of the injected commands may take effect.
NASTY = (
    "\\input{/etc/passwd} \\immediate\\write18{touch /tmp/egata-pwned} ^^5c "
    "rând unu\n\nrând doi \x00\x1b 😀 北京 Мария Łódź „Ștefan” — 100 €"
)


@pytest.mark.parametrize("proc_path", PROCEDURE_FILES, ids=lambda p: p.stem)
def test_template_survives_nasty_input(proc_path: Path) -> None:
    proc = json.loads(proc_path.read_text(encoding="utf-8"))
    fields = {
        f["name"]: (str(f["options"][0]) if f.get("options") else NASTY)
        for f in proc.get("fields", [])
    }
    pdf = render_and_compile(proc["template"], fields)
    assert pdf.startswith(b"%PDF-")
    assert b"root:x:0:0" not in pdf
    assert not Path("/tmp/egata-pwned").exists()  # noqa: S108 — the \write18 target above


def test_paranoid_file_access_blocks_absolute_input(tmp_path: Path) -> None:
    """Defense in depth: even LaTeX that bypassed escaping could not read a
    file outside the build directory. The target is plain text, so with
    TeX Live's default openin_any=a this compiles and embeds it."""
    from app.pdf import PdfRenderError, compile_pdf

    secret = tmp_path / "secret.tex"
    secret.write_text("SECRETMARKER", encoding="utf-8")
    with pytest.raises(PdfRenderError):
        compile_pdf(
            "\\documentclass{article}\\begin{document}"
            f"\\input{{{secret}}}\\end{{document}}"
        )
