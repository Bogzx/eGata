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
