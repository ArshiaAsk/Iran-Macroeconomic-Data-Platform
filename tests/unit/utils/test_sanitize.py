"""
Unit tests for the shared secret-redaction helpers.

These are the last line of defence for Bronze: the EIA connector redacts its
echoed request parameters, but the central boundary in ``write_bronze`` relies
on :mod:`src.utils.sanitize` to catch anything a connector misses.
"""

from src.utils.sanitize import (
    REDACTED,
    find_sensitive_pairs,
    is_placeholder,
    is_sensitive_key,
    redact_secrets,
    sanitize_params,
    sanitize_text,
    sanitize_url,
)

SECRET = "s3cr3t-value-1234567890"


# ------------------------------------------------------------- is_sensitive_key


def test_sensitive_key_names_are_recognised_in_any_case_or_separator() -> None:
    """The denylist is case-insensitive and treats ``-``/``_`` as equivalent."""
    for name in ("api_key", "API_KEY", "Api-Key", "apikey", "key", "token"):
        assert is_sensitive_key(name) is True
    for name in ("authorization", "Authorization", "password", "secret", "x-api-key"):
        assert is_sensitive_key(name) is True


def test_ordinary_field_names_are_not_sensitive() -> None:
    """Redaction must not touch payload fields like ``value`` or ``indicator``."""
    for name in ("indicator_id", "value", "period", "length", "offset", "country"):
        assert is_sensitive_key(name) is False


def test_placeholders_are_recognised() -> None:
    """A value that is already redacted is not a leak."""
    assert is_placeholder(REDACTED) is True
    assert is_placeholder("***") is True
    assert is_placeholder("") is True
    assert is_placeholder(SECRET) is False


# --------------------------------------------------------------- redact_secrets


def test_redact_secrets_replaces_values_under_sensitive_keys() -> None:
    """Only the credential value is replaced; the payload shape is preserved."""
    payload = {
        "request": {"params": {"api_key": SECRET, "length": 1}},
        "rows": [{"period": "2024-01", "value": "1"}],
    }

    redacted = redact_secrets(payload)

    assert redacted["request"]["params"]["api_key"] == REDACTED
    assert redacted["request"]["params"]["length"] == 1
    assert redacted["rows"] == payload["rows"]
    assert SECRET not in str(redacted)


def test_redact_secrets_walks_nested_lists() -> None:
    """Echoed pages are a list of payloads; every level is scrubbed."""
    pages = [
        {"request": {"params": {"api_key": SECRET}}},
        {"request": {"params": {"token": SECRET}}},
    ]

    redacted = redact_secrets(pages)

    assert redacted[0]["request"]["params"]["api_key"] == REDACTED
    assert redacted[1]["request"]["params"]["token"] == REDACTED
    assert SECRET not in str(redacted)


def test_redact_secrets_replaces_exact_secret_values_in_strings() -> None:
    """A key echoed with no key name attached is caught by exact-value match."""
    redacted = redact_secrets(
        {"note": f"see https://api.example/v2?api_key={SECRET}&x=1"}, [SECRET]
    )

    assert SECRET not in redacted["note"]
    assert "x=1" in redacted["note"]


def test_redact_secrets_does_not_rewrite_payload_text() -> None:
    """Scraper payloads contain page source; structured redaction must not touch it."""
    script = "data: { token: currentToken, location: location.href }"

    redacted = redact_secrets({"html": script})

    assert redacted["html"] == script


def test_redact_secrets_sanitizes_url_valued_keys() -> None:
    """A URL stored under a ``url`` key still gets its query string scrubbed."""
    redacted = redact_secrets({"request_url": f"https://api.example/v2?api_key={SECRET}&n=1"})

    assert SECRET not in redacted["request_url"]
    assert "n=1" in redacted["request_url"]


def test_redact_secrets_is_idempotent() -> None:
    """Running the boundary twice must not change the result."""
    payload = {"api_key": SECRET, "rows": [{"api_key": SECRET}]}

    once = redact_secrets(payload)
    twice = redact_secrets(once)

    assert once == twice


def test_sanitize_params_is_a_redact_alias() -> None:
    """The parameter-named entry point behaves identically."""
    assert sanitize_params({"api_key": SECRET}) == {"api_key": REDACTED}


# ----------------------------------------------------------------- sanitize_text


def test_sanitize_text_redacts_key_value_pairs() -> None:
    """requests embeds the prepared URL -- key included -- in its error text."""
    text = f"500 Server Error for url: https://api.eia.gov/v2/data/?api_key={SECRET}&length=1"

    scrubbed = sanitize_text(text)

    assert SECRET not in scrubbed
    assert f"api_key={REDACTED}" in scrubbed
    assert "length=1" in scrubbed


def test_sanitize_text_redacts_an_exact_secret_with_no_key_name() -> None:
    """Some backends echo the bare credential; ``secrets`` catches that."""
    scrubbed = sanitize_text(f"rejected credential {SECRET}", [SECRET])

    assert SECRET not in scrubbed
    assert REDACTED in scrubbed


def test_sanitize_text_redacts_bearer_tokens() -> None:
    """Authorization headers are a second common leak shape."""
    scrubbed = sanitize_text("Authorization: Bearer abc.def.ghi-jkl")

    assert "abc.def.ghi-jkl" not in scrubbed
    assert "Bearer" in scrubbed


def test_sanitize_text_leaves_placeholders_alone() -> None:
    """Re-running on already-sanitised text is a no-op."""
    assert sanitize_text(f"api_key={REDACTED}") == f"api_key={REDACTED}"


# ------------------------------------------------------------------ sanitize_url


def test_sanitize_url_redacts_sensitive_query_parameters() -> None:
    """The public provenance URL must not carry the credential."""
    url = f"https://api.eia.gov/v2/international/data/?api_key={SECRET}&length=5000"

    safe = sanitize_url(url)

    assert safe is not None
    assert SECRET not in safe
    assert "length=5000" in safe
    assert "api_key=REDACTED" in safe


def test_sanitize_url_redacts_a_password_in_userinfo() -> None:
    """Database URLs can appear in logs; the password must not."""
    safe = sanitize_url("postgresql://iran_macro:supersecret@localhost:5432/iran_macro_db")

    assert safe is not None
    assert "supersecret" not in safe
    assert "iran_macro" in safe
    assert "localhost" in safe


def test_sanitize_url_passes_none_through() -> None:
    """A connector with no request URL stays None."""
    assert sanitize_url(None) is None


# --------------------------------------------------------- find_sensitive_pairs


def test_find_sensitive_pairs_reports_keys_and_fingerprints_only() -> None:
    """The scanner must never surface the secret value itself."""
    hits = find_sensitive_pairs(f'{{"api_key": "{SECRET}"}}')

    assert hits
    key, fingerprint = hits[0]
    assert key == "api_key"
    assert SECRET not in fingerprint
    assert len(fingerprint) == 12


def test_find_sensitive_pairs_ignores_placeholders() -> None:
    """Sanitised payloads produce no findings."""
    assert find_sensitive_pairs(f'{{"api_key": "{REDACTED}"}}') == []


def test_find_sensitive_pairs_ignores_generic_keys_with_code_values() -> None:
    """``token: currentToken`` in page source is a variable, not a credential."""
    assert find_sensitive_pairs("data: { token: currentToken, location: location.href }") == []


def test_find_sensitive_pairs_still_flags_a_generic_key_with_a_real_token() -> None:
    """A long, mixed alphanumeric value under ``token`` is a credential."""
    hits = find_sensitive_pairs(f"token={SECRET}")

    assert hits
    assert hits[0][0] == "token"
