"""Unit tests for the database redaction helper.

The SQL paths need a live database and are covered by the dry run in the
remediation workflow; these tests exercise the pure value-redaction logic and
the dotenv parsing so the type dispatch cannot silently regress.
"""

from pathlib import Path

from scripts.redact_secrets import ColumnRef, load_env, redact_value
from src.utils.sanitize import REDACTED

SECRET = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7b"

JSON_COLUMN = ColumnRef("bronze", "bronze_raw", "raw_data", "jsonb", ("id",))
URL_COLUMN = ColumnRef("bronze", "bronze_raw", "request_url", "text", ("id",))
ERROR_COLUMN = ColumnRef("metadata", "data_collection_log", "error_message", "text", ("id",))
PLAIN_COLUMN = ColumnRef("silver", "silver_cleaned", "validation_notes", "text", ("id",))


def test_redact_value_redacts_jsonb_by_key_name() -> None:
    """The stored request parameters lose the key, keeping everything else."""
    value = {"rows": [{"v": 1}], "raw_response": [{"request": {"params": {"api_key": SECRET}}}]}

    redacted = redact_value(value, JSON_COLUMN)

    assert redacted["raw_response"][0]["request"]["params"]["api_key"] == REDACTED
    assert redacted["rows"] == value["rows"]


def test_redact_value_sanitizes_url_columns() -> None:
    """A request URL keeps its shape but loses the query-string credential."""
    redacted = redact_value(f"https://api.eia.gov/v2/data/?api_key={SECRET}&n=1", URL_COLUMN)

    assert SECRET not in redacted
    assert "n=1" in redacted


def test_redact_value_sanitizes_error_message_columns() -> None:
    """Requests embeds the URL in exception text; the stored log must not."""
    redacted = redact_value(f"500 for url ?api_key={SECRET}", ERROR_COLUMN)

    assert SECRET not in redacted


def test_redact_value_leaves_ordinary_text_untouched() -> None:
    """A plain human-readable column is not rewritten."""
    assert redact_value("all checks passed", PLAIN_COLUMN) == "all checks passed"


def test_redact_value_passes_none_through() -> None:
    """Null columns stay null."""
    assert redact_value(None, JSON_COLUMN) is None


def test_redact_value_is_idempotent() -> None:
    """A second pass finds nothing to change."""
    value = {"api_key": SECRET}

    once = redact_value(value, JSON_COLUMN)

    assert redact_value(once, JSON_COLUMN) == once


def test_load_env_parses_quotes_and_comments(tmp_path: Path) -> None:
    """dotenv parsing tolerates quotes, blanks, and comments."""
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\nDATABASE_USER="iran_macro"\nDATABASE_PORT=5433\n\n')

    parsed = load_env(env_file)

    assert parsed == {"DATABASE_USER": "iran_macro", "DATABASE_PORT": "5433"}


def test_load_env_missing_file_is_empty(tmp_path: Path) -> None:
    """A missing dotenv file yields no values rather than raising."""
    assert load_env(tmp_path / "nope.env") == {}
