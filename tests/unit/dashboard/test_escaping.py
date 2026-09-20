"""Tests for the HTML escaping helper (Task 15)."""

from dashboard.components.escaping import escape_html

#: A payload that exercises every character HTML escaping must neutralise.
HOSTILE = "<script>alert(\"x\") & 'y'</script>"
PERSIAN = "قیمت مصرف‌کننده — شاخص"


def test_escapes_the_five_html_metacharacters() -> None:
    escaped = escape_html("&<>\"'")

    assert escaped == "&amp;&lt;&gt;&quot;&#x27;"


def test_neutralises_a_script_payload() -> None:
    escaped = escape_html(HOSTILE)

    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "&amp;" in escaped
    assert "&quot;" in escaped
    # The raw payload cannot survive as a substring.
    assert HOSTILE not in escaped


def test_persian_text_is_preserved_verbatim() -> None:
    assert escape_html(PERSIAN) == PERSIAN


def test_non_string_values_are_coerced_not_raised() -> None:
    assert escape_html(42) == "42"
    assert escape_html(None) == "None"
    assert escape_html("<b>") == "&lt;b&gt;"


def test_escaping_is_a_single_pass_and_does_not_double_escape_semantics() -> None:
    # A pre-escaped ampersand is escaped once more (idempotence is not claimed);
    # the point is that the function never *unescapes*.
    assert escape_html("&amp;") == "&amp;amp;"
