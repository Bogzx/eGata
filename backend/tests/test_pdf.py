from __future__ import annotations

from pathlib import Path

from app.pdf import (
    LATEX_ESCAPE_MAP,
    escape_latex,
    render_template,
)


def test_escape_latex_handles_all_special_chars() -> None:
    raw = "A & B 100% $5 #1 _x {y} ~ ^ \\"
    out = escape_latex(raw)
    assert "\\&" in out
    assert "\\%" in out
    assert "\\$" in out
    assert "\\#" in out
    assert "\\_" in out
    assert "\\{" in out and "\\}" in out
    assert "\\textasciitilde" in out
    assert "\\textasciicircum" in out
    assert "\\textbackslash" in out


def test_escape_latex_preserves_romanian_diacritics() -> None:
    assert escape_latex("Cluj-Napoca, Avram Iancu") == "Cluj-Napoca, Avram Iancu"
    assert escape_latex("căsătorit") == "căsătorit"
    assert escape_latex("Înregistrare") == "Înregistrare"


def test_escape_map_covers_required_chars() -> None:
    assert set(LATEX_ESCAPE_MAP.keys()) >= {"&", "%", "$", "#", "_", "{", "}", "~", "^", "\\"}


def test_render_template_substitutes_fields(tmp_path: Path) -> None:
    tpl = tmp_path / "x.tex"
    tpl.write_text(
        "Hello {{name}} CNP {{cnp}} amount {{amount}}", encoding="utf-8"
    )
    result = render_template(
        tpl, fields={"name": "Maria & Co", "cnp": "2851014123456", "amount": "100$"}
    )
    assert "Maria \\& Co" in result
    assert "2851014123456" in result
    assert "100\\$" in result


def test_render_template_handles_missing_field_with_blank(tmp_path: Path) -> None:
    tpl = tmp_path / "x.tex"
    tpl.write_text("a {{present}} b {{absent}} c", encoding="utf-8")
    result = render_template(tpl, fields={"present": "X"})
    assert "a X b  c" in result


# ---- sanitize_text / escape_latex against hostile input -------------------
#
# Values reach the template from citizens and from the model, so they are
# untrusted. These pin the two properties that matter: no TeX command can be
# formed, and nothing in the value can make pdflatex abort (which would leave
# a citizen unable to get their form at all).

import re as _re  # noqa: E402
from unittest.mock import patch as _patch  # noqa: E402

import pytest  # noqa: E402

from app.pdf import (  # noqa: E402
    PdfRenderError,
    PdfRendererUnavailable,
    _is_supported,
    compile_pdf,
    sanitize_text,
)

HOSTILE_VALUES = [
    r"\input{/etc/passwd}",
    r"\immediate\write18{touch /tmp/pwned}",
    "^^5cinput{/etc/passwd}",
    r"\catcode`\@=0 @input",
    "line one\n\nline two",
    "a\r\nb\tc",
    "nul\x00byte",
    "esc\x1b[31m\x7f",
    "rtl \u202e override",
    "zero\u200bwidth",
    "Maria 😀🇷🇴",
    "北京市",
    "Мария Иванова",
    "Łódź, Gdańsk, Żółć",
    "Ștefan cel Mare, ş ţ Ș Ț â î ă",
    "Ĳ2 ĳ0",
    "„ghilimele” — «guillemets» … 100 €",
]


@pytest.mark.parametrize("value", HOSTILE_VALUES)
def test_escaped_value_cannot_form_a_command(value: str) -> None:
    out = escape_latex(value)
    # Every backslash in the output starts one of the escapes we emit.
    for m in _re.finditer(r"\\", out):
        tail = out[m.start():]
        assert _re.match(
            r"\\(textbackslash\{\}|textasciitilde\{\}|textasciicircum\{\}|[&%$#_{}])",
            tail,
        ), f"stray control sequence in {out!r}"
    assert "^^" not in out


@pytest.mark.parametrize("value", HOSTILE_VALUES)
def test_sanitized_value_is_typesettable(value: str) -> None:
    out = sanitize_text(value)
    assert all(_is_supported(c) for c in out), repr(out)
    assert "\n" not in out and "\r" not in out and "\t" not in out


def test_sanitize_keeps_romanian_text_verbatim() -> None:
    text = "Ștefan cel Mare nr. 5, ap. 3 — „Țara” șăîâ"
    assert sanitize_text(text) == text


def test_sanitize_folds_to_base_letters_and_marks_losses() -> None:
    assert sanitize_text("Gdańsk ę") == "Gdańsk e"  # ń typesets, ę folds
    assert sanitize_text("Мария") == "?????"  # visible loss, not a crash
    assert sanitize_text("ok 😀") == "ok "  # pictographs dropped


def test_ij_ligatures_fold_before_a_digit_can_follow() -> None:
    # Found by fuzzing against real pdflatex: "Ĳ2" aborted the render.
    assert sanitize_text("Ĳ2 ĳ0") == "IJ2 ij0"


def test_blank_lines_collapse_to_a_space() -> None:
    # A blank line inside \underline{...} ends the paragraph mid-argument and
    # aborts pdflatex (cerere-certificat-urbanism and both prelungire-*
    # templates did exactly that).
    assert escape_latex("rând unu\n\n\nrând doi") == "rând unu rând doi"


def test_missing_pdflatex_is_a_clear_error() -> None:
    with _patch("app.pdf.subprocess.run", side_effect=FileNotFoundError("pdflatex")):
        with pytest.raises(PdfRendererUnavailable):
            compile_pdf(r"\documentclass{article}\begin{document}x\end{document}")


def test_render_failure_does_not_carry_the_tex_log(tmp_path: Path) -> None:
    """The TeX log echoes field values (CNP, address); it must not reach the
    exception message that callers hand to HTTP clients and the model."""
    from subprocess import CompletedProcess

    def fake_run(args, cwd, **_kw):  # type: ignore[no-untyped-def]
        (Path(cwd) / "doc.log").write_text("! Error on line: CNP 2851014123456")
        return CompletedProcess(args, 1, b"", b"")

    with _patch("app.pdf.subprocess.run", side_effect=fake_run):
        with pytest.raises(PdfRenderError) as exc:
            compile_pdf("irrelevant")
    assert "2851014123456" not in str(exc.value)


def test_pdflatex_runs_without_shell_escape_and_with_paranoid_file_access() -> None:
    from subprocess import CompletedProcess

    captured: dict = {}

    def fake_run(args, cwd, env, **_kw):  # type: ignore[no-untyped-def]
        captured["args"], captured["env"] = args, env
        (Path(cwd) / "doc.pdf").write_bytes(b"%PDF-1.4")
        return CompletedProcess(args, 0, b"", b"")

    with _patch("app.pdf.subprocess.run", side_effect=fake_run):
        compile_pdf("irrelevant")
    assert "-no-shell-escape" in captured["args"]
    assert captured["env"]["shell_escape"] == "f"
    assert captured["env"]["openin_any"] == "p"
    assert captured["env"]["openout_any"] == "p"
