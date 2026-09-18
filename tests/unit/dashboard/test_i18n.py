"""String-catalog invariants for dashboard/i18n.py.

The catalog is the single home for Persian UI chrome; these tests assert that it
resolves, that a miss fails loudly instead of degrading to English, and that it
stays aligned with the navigation registry that keys the page namespace.
"""

import pytest

from dashboard.i18n import (
    KEY_PREFIXES,
    LOCALE,
    STRING_CATALOG,
    TranslationError,
    has_string,
    string_keys,
    t,
)
from dashboard.navigation import GROUPS, PAGES

PERSIAN_RANGE = range(0x0600, 0x0700)


def _has_persian_char(value: str) -> bool:
    return any(ord(character) in PERSIAN_RANGE for character in value)


def test_known_key_resolves() -> None:
    assert t("nav.inflation") == "تورم"
    assert t("app.title") == "سامانه داده‌های اقتصاد کلان ایران"


def test_has_string_reports_catalog_membership() -> None:
    assert has_string("nav.inflation") is True
    assert has_string("nav.missing") is False


def test_missing_key_raises_instead_of_falling_back() -> None:
    with pytest.raises(TranslationError, match="Unknown dashboard string key"):
        t("nav.missing")
    with pytest.raises(KeyError):
        t("chart.missing")


def test_interpolation_fills_placeholders() -> None:
    assert t("metric.selected_indicators", count="۳") == "۳ شاخص انتخاب‌شده"


def test_interpolation_keeps_values_verbatim() -> None:
    # Digit conversion is formatting.py's job; t() must not rewrite a value.
    assert t("metric.selected_indicators", count="3") == "3 شاخص انتخاب‌شده"


def test_unfilled_placeholder_fails_clearly() -> None:
    with pytest.raises(TranslationError, match="Cannot format dashboard string"):
        t("metric.selected_indicators")


def test_extra_arguments_are_tolerated() -> None:
    # Unused kwargs are harmless, matching str.format semantics.
    assert t("nav.inflation", unused="x") == t("nav.inflation")


def test_catalog_is_persian_and_non_empty() -> None:
    for key, value in STRING_CATALOG.items():
        assert value.strip(), key
        assert value == value.strip(), key
        assert _has_persian_char(value), key


def test_catalog_keys_use_a_declared_namespace() -> None:
    for key in STRING_CATALOG:
        assert key.startswith(KEY_PREFIXES), key


def test_catalog_alignment_with_the_page_registry() -> None:
    for spec in PAGES:
        assert has_string(f"nav.{spec.key}"), spec.key
        assert has_string(f"page.{spec.key}"), spec.key
        # The sidebar label and the in-page title share one value per page, so
        # they cannot drift (Task 17).
        assert t(f"nav.{spec.key}") == t(f"page.{spec.key}"), spec.key


def test_catalog_covers_every_sidebar_group() -> None:
    for group in GROUPS:
        assert has_string(f"group.{group}"), group


def test_single_locale_only() -> None:
    assert LOCALE == "fa"
    assert not any(key.endswith((".en", ".fa")) for key in STRING_CATALOG)
    assert not has_string("nav.overview.en")


def test_string_keys_are_sorted_and_complete() -> None:
    keys = string_keys()

    assert keys == tuple(sorted(STRING_CATALOG))
    assert len(keys) == len(set(keys))
