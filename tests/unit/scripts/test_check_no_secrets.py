"""Unit tests for the pre-share secret scanner.

No database and no ``pg_restore``: the pure functions (``scan_text``,
``scan_dump_text``, ``shannon_entropy``) are fed synthetic input, and ``main``
is exercised on a temporary file so the exit-code contract is covered.
"""

from pathlib import Path

from scripts.check_no_secrets import (
    EXIT_CLEAN,
    EXIT_ERROR,
    EXIT_FINDINGS,
    scan_dump_text,
    scan_text,
    shannon_entropy,
)

EIA_STYLE_KEY = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7b"  # 40 chars, mixed
SECRET = "s3cr3t-value-1234567890"


# ------------------------------------------------------------------ entropy


def test_shannon_entropy_of_a_repeated_character_is_zero() -> None:
    """A constant string carries no information."""
    assert shannon_entropy("aaaaaaaa") == 0.0


def test_shannon_entropy_of_a_random_token_is_high() -> None:
    """A random alphanumeric token scores well above the threshold."""
    assert shannon_entropy(EIA_STYLE_KEY) > 3.0


def test_shannon_entropy_of_an_empty_string_is_zero() -> None:
    """Empty input is defined as zero rather than raising."""
    assert shannon_entropy("") == 0.0


# ------------------------------------------------------------------ scan_text


def test_scan_text_finds_a_named_api_key() -> None:
    """The exact signature of the EIA leak is reported."""
    findings = scan_text(f'{{"api_key": "{EIA_STYLE_KEY}"}}', "cell")

    assert any(f.kind == "named-credential" and f.key == "api_key" for f in findings)
    assert all(EIA_STYLE_KEY not in f.fingerprint for f in findings)


def test_scan_text_ignores_a_sanitised_payload() -> None:
    """A value already replaced by ``REDACTED`` is not a finding."""
    assert scan_text('{"api_key": "REDACTED"}', "cell") == []


def test_scan_text_finds_a_bare_high_entropy_token() -> None:
    """A key with no name attached is still caught."""
    findings = scan_text(f"x {EIA_STYLE_KEY} y", "cell")

    assert any(f.kind == "high-entropy-token" for f in findings)


def test_scan_text_ignores_a_base64_fragment() -> None:
    """A 40-char run inside a longer base64 blob is not a standalone token."""
    blob = "aGVsbG8=" + EIA_STYLE_KEY + "wYXJk"  # no separators: one long run

    assert scan_text(blob, "cell") == []


def test_scan_text_ignores_a_git_sha() -> None:
    """Pure lowercase hex is history noise, not a credential."""
    assert scan_text("commit 0123456789abcdef0123456789abcdef01234567", "cell") == []


def test_scan_text_ignores_javascript_token_assignments() -> None:
    """Page source contains ``token: currentToken``; that is not a secret."""
    assert scan_text("data: { token: currentToken, location: location.href }", "cell") == []


# -------------------------------------------------------------- scan_dump_text


def _synthetic_dump() -> str:
    """A miniature ``pg_restore -f -`` output with one leaking COPY block."""
    return (
        "SET statement_timeout = 0;\n"
        "COPY bronze.bronze_raw (id, raw_data) FROM stdin;\n"
        f'1\t{{"api_key": "{EIA_STYLE_KEY}"}}\n'
        "\\.\n"
        "COPY _timescaledb_internal.compress_hyper_2_1_chunk (blob) FROM stdin;\n"
        f"{EIA_STYLE_KEY}\n"
        "\\.\n"
    )


def test_scan_dump_text_finds_the_named_key_in_a_normal_table() -> None:
    """Named detection runs inside ordinary COPY blocks."""
    findings = scan_dump_text(_synthetic_dump(), "dump")

    assert any(f.location == "dump:bronze.bronze_raw" for f in findings)


def test_scan_dump_text_skips_bare_tokens_in_internal_chunks() -> None:
    """Compressed-chunk blobs must not produce high-entropy noise."""
    findings = scan_dump_text(_synthetic_dump(), "dump")

    internal = [f for f in findings if "_timescaledb_internal" in f.location]
    assert internal == []


# ----------------------------------------------------------------------- main


def test_main_exits_clean_on_a_secret_free_file(tmp_path: Path) -> None:
    """A clean input returns 0."""
    from scripts.check_no_secrets import main

    target = tmp_path / "clean.txt"
    target.write_text("nothing to see here")

    assert main(["--quiet", "--path", str(target)]) == EXIT_CLEAN


def test_main_exits_nonzero_on_a_leaking_file(tmp_path: Path) -> None:
    """A live credential in any scanned file returns 1."""
    from scripts.check_no_secrets import main

    target = tmp_path / "leak.txt"
    target.write_text(f'{{"api_key": "{EIA_STYLE_KEY}"}}')

    assert main(["--quiet", "--path", str(target)]) == EXIT_FINDINGS


def test_main_requires_at_least_one_source() -> None:
    """With no source the CLI is a usage error, not a false 'clean'."""
    from scripts.check_no_secrets import main

    assert main([]) == EXIT_ERROR


def test_main_reports_a_missing_archive_cleanly(tmp_path: Path) -> None:
    """A missing ``.bak`` is an environment error, not a traceback."""
    from scripts.check_no_secrets import main

    assert main(["--bak", str(tmp_path / "nope.bak")]) == EXIT_ERROR
