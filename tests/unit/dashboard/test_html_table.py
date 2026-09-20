"""Tests for the RTL HTML table and its typed cell model (Task 15)."""

import pytest

from dashboard.components.direction import direction_css
from dashboard.components.escaping import escape_html
from dashboard.components.html_table import (
    Cell,
    Dot,
    Ltr,
    StatusChip,
    Text,
    TwoLine,
    UnitChip,
    build_html_table,
)
from dashboard.formatting import MISSING_VALUE

HOSTILE = "<script>alert(\"x\") & 'y'</script>"
PERSIAN = "قیمت مصرف‌کننده"


def _one_cell(cell: Cell) -> str:
    """Render a single cell in a one-column, one-row table."""
    return build_html_table(("ستون",), ((cell,),))


#: Every cell variant carrying the hostile payload, for the escaping sweep.
HOSTILE_CELLS = [
    Text(HOSTILE),
    Ltr(HOSTILE),
    UnitChip(HOSTILE),
    StatusChip(HOSTILE, "ok"),
    Dot(HOSTILE, "warn"),
    TwoLine(HOSTILE, (Ltr(HOSTILE),)),
]


@pytest.mark.parametrize("cell", HOSTILE_CELLS)
def test_every_cell_variant_escapes_the_hostile_payload(cell: Cell) -> None:
    markup = _one_cell(cell)

    assert HOSTILE not in markup
    assert escape_html(HOSTILE) in markup


@pytest.mark.parametrize("cell", HOSTILE_CELLS)
def test_every_cell_variant_keeps_persian_text_readable(cell: Cell) -> None:
    payload_cell = _replace_payload(cell, PERSIAN)

    markup = _one_cell(payload_cell)

    assert PERSIAN in markup


def _replace_payload(cell: Cell, value: str) -> Cell:
    """Rebuild ``cell`` with ``value`` in place of the hostile payload."""
    if isinstance(cell, StatusChip | Dot):
        return type(cell)(value, cell.tone)
    if isinstance(cell, TwoLine):
        return TwoLine(value, (Ltr(value),))
    return type(cell)(value)


def test_escapes_the_title_attribute() -> None:
    markup = _one_cell(Text("x", title='a"b<c>&'))

    assert 'title="a&quot;b&lt;c&gt;&amp;"' in markup
    assert 'title="a"b<c>&"' not in markup


def test_semantic_markup_and_rtl_wrapper() -> None:
    markup = build_html_table(("منبع", "وضعیت"), ((Text("SCI"), StatusChip("موفق", "ok")),))

    assert markup.startswith('<div class="dt-wrap" dir="rtl">')
    assert "<table" in markup
    assert '<th scope="col">منبع</th>' in markup
    assert "<tbody>" in markup and "</table>" in markup
    assert "<svg" not in markup


def test_density_toggles_the_class() -> None:
    comfortable = build_html_table(("h",), ((Text("v"),),))
    compact = build_html_table(("h",), ((Text("v"),),), density="compact")

    assert 'class="dt comfortable"' in comfortable
    assert 'class="dt compact"' in compact


def test_unknown_density_raises() -> None:
    with pytest.raises(ValueError, match="unknown density"):
        build_html_table(("h",), ((Text("v"),),), density="cosy")


@pytest.mark.parametrize("tone", ["ok", "warn", "err", "accent", "neutral"])
def test_known_tones_render_their_class(tone: str) -> None:
    assert f'class="chip tone-{tone}"' in _one_cell(StatusChip("x", tone))
    assert f'class="dot tone-{tone}"' in _one_cell(Dot("x", tone))


def test_unknown_tone_raises_so_data_cannot_inject_a_class() -> None:
    # A data-derived tone outside the closed set must raise, never reach a class.
    with pytest.raises(ValueError, match="unknown tone"):
        _one_cell(StatusChip("x", "ok; background:url(x)"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown tone"):
        _one_cell(Dot("x", "critical"))  # type: ignore[arg-type]


def test_null_renders_the_placeholder_for_text_like_cells() -> None:
    assert MISSING_VALUE in _one_cell(Text(None))
    assert MISSING_VALUE in _one_cell(Ltr(None))
    assert MISSING_VALUE in _one_cell(UnitChip(None))
    assert MISSING_VALUE in _one_cell(TwoLine(None))
    # The placeholder is wrapped in the muted ``na`` class.
    assert f'<span class="na">{MISSING_VALUE}</span>' in _one_cell(Text(None))


def test_null_is_not_turned_into_a_placeholder_for_chips_and_dots() -> None:
    chip = _one_cell(StatusChip(None, "ok"))
    dot = _one_cell(Dot(None, "warn"))

    assert MISSING_VALUE not in chip
    assert MISSING_VALUE not in dot
    # The chip/dot shape still renders, with an empty label.
    assert '<span class="chip tone-ok"></span>' in chip
    assert '<span class="dot tone-warn"></span>' in dot


def test_custom_null_placeholder_is_used_and_escaped() -> None:
    markup = build_html_table(("h",), ((Text(None),),), null_placeholder="<na>")

    assert "&lt;na&gt;" in markup
    assert "<na>" not in markup


def test_ltr_cells_are_isolated() -> None:
    markup = _one_cell(Ltr("TGJU.USD.FREE"))

    assert '<bdi class="ltr">TGJU.USD.FREE</bdi>' in markup


def test_unit_chip_is_an_ltr_span() -> None:
    markup = _one_cell(UnitChip("current US$"))

    assert '<span class="unit">current US$</span>' in markup


def test_two_line_renders_primary_and_secondary_parts() -> None:
    markup = _one_cell(TwoLine("شاخص قیمت", (Ltr("SCI.CPI.URBAN.B2016"),)))

    assert '<span class="name">شاخص قیمت</span>' in markup
    assert '<span class="sm tm">' in markup
    assert '<bdi class="ltr">SCI.CPI.URBAN.B2016</bdi>' in markup


def test_two_line_omits_the_secondary_line_when_empty() -> None:
    markup = _one_cell(TwoLine("only"))

    assert '<span class="sm tm">' not in markup
    assert "only" in markup


def test_wrapper_scrolls_within_its_own_box_and_caps_long_tokens() -> None:
    css = direction_css()

    # AM-26: the wrapper scrolls sideways; long ids/units cannot break the page.
    assert ".dt-wrap {" in css
    assert "overflow-x: auto;" in css
    assert "max-width: 24ch;" in css  # .dt .ltr
    assert "max-width: 20ch;" in css  # .unit
    assert "text-overflow: ellipsis;" in css
    # The table CSS is emitted by the shell owner exactly once, never per table.
    assert css.count(".dt-wrap {") == 1
