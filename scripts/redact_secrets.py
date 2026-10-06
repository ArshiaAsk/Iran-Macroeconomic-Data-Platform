#!/usr/bin/env python3
"""
Redact credentials that are already stored in the platform database.

This is a remediation tool, not a collector: it walks the platform schemas,
finds values sitting under a credential key name (``api_key``, ``token``,
``password``, ...) or inside a URL, and replaces them with ``REDACTED``. It is
idempotent -- a second run reports no changes -- so it is safe to re-run.

It defaults to a dry run that only *reports* what it would change. Pass
``--apply`` to write; a fresh ``pg_dump`` backup is taken first unless
``--no-backup`` is given.

The key value is never printed; only key names and short fingerprints appear in
the output.

Usage::

    python scripts/redact_secrets.py                     # dry run against .env
    python scripts/redact_secrets.py --apply             # back up, then redact
    python scripts/redact_secrets.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.sanitize import (  # noqa: E402
    find_sensitive_pairs,
    redact_secrets,
    sanitize_text,
    sanitize_url,
)

PLATFORM_SCHEMAS = ("bronze", "silver", "gold", "metadata")
JSON_TYPES = frozenset({"jsonb", "json"})
TEXT_TYPES = frozenset({"text", "character varying"})

# Only rows whose text form mentions a credential key are fetched; the database
# does the bulk of the filtering.
SQL_PREFILTER = (
    r"(api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|private[_-]?key|x[_-]?api[_-]?key|password|secret|token|authorization)"
)

EXIT_OK = 0
EXIT_CHANGES_PENDING = 1
EXIT_ERROR = 2


@dataclass(frozen=True)
class ColumnRef:
    """A database column the redactor knows how to rewrite."""

    schema: str
    table: str
    column: str
    data_type: str
    primary_key: tuple[str, ...]

    @property
    def qualified(self) -> str:
        """``schema.table`` label."""
        return f"{self.schema}.{self.table}"

    @property
    def label(self) -> str:
        """``schema.table.column`` label."""
        return f"{self.schema}.{self.table}.{self.column}"


@dataclass
class Change:
    """One row that the redactor would (or did) rewrite."""

    column: ColumnRef
    primary_key: tuple[Any, ...]
    redacted_value: Any
    keys: list[tuple[str, str]]

    def render(self) -> str:
        """Secret-free description of the change."""
        keys = ", ".join(f"{name}={digest}" for name, digest in self.keys) or "url"
        return f"{self.column.label} pk={self.primary_key}: {keys}"


def load_env(path: Path) -> dict[str, str]:
    """Read ``KEY=VALUE`` pairs from a dotenv file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def connection_url(explicit: str | None) -> str:
    """
    Resolve the database URL from an argument or the project ``.env``.

    Args:
        explicit: ``--database-url`` value, if given

    Returns:
        A libpq connection URL
    """
    if explicit:
        return explicit
    env = load_env(REPO_ROOT / ".env")
    return (
        f"postgresql://{env.get('DATABASE_USER', 'iran_macro')}:"
        f"{env.get('DATABASE_PASSWORD', '')}@"
        f"{env.get('DATABASE_HOST', 'localhost')}:"
        f"{env.get('DATABASE_PORT', '5432')}/"
        f"{env.get('DATABASE_NAME', 'iran_macro_db')}"
    )


def _primary_key_columns(cursor: Any, schema: str, table: str) -> tuple[str, ...]:
    """Return the ordered primary-key column names for a table, if any."""
    cursor.execute(
        """
        select a.attname
        from pg_index i
        join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
        where i.indrelid = %s::regclass and i.indisprimary
        order by array_position(i.indkey, a.attnum)
        """,
        (f"{schema}.{table}",),
    )
    return tuple(row[0] for row in cursor.fetchall())


def discover_columns(cursor: Any) -> list[ColumnRef]:
    """
    List every scannable column in the platform schemas.

    Args:
        cursor: Open database cursor

    Returns:
        One :class:`ColumnRef` per jsonb/text column that has a primary key
    """
    cursor.execute(
        """
        select table_schema, table_name, column_name, data_type
        from information_schema.columns
        where table_schema = any(%s) and data_type = any(%s)
        order by table_schema, table_name, ordinal_position
        """,
        (list(PLATFORM_SCHEMAS), list(JSON_TYPES | TEXT_TYPES)),
    )
    refs: list[ColumnRef] = []
    for schema, table, column, data_type in cursor.fetchall():
        primary_key = _primary_key_columns(cursor, schema, table)
        if not primary_key:
            continue
        refs.append(ColumnRef(schema, table, column, data_type, primary_key))
    return refs


def redact_value(value: Any, column: ColumnRef) -> Any:
    """
    Apply the right redactor for a column's type.

    Args:
        value: Current column value
        column: Column metadata

    Returns:
        The redacted value (equal to ``value`` when nothing needed changing)
    """
    if value is None:
        return value
    if column.data_type in JSON_TYPES:
        return redact_secrets(value)
    if column.column.endswith("url") or column.column in {"request_url", "source_url"}:
        return sanitize_url(value)
    return sanitize_text(value)


def collect_changes(cursor: Any, columns: Sequence[ColumnRef]) -> list[Change]:
    """
    Find every row whose value would change under redaction.

    Args:
        cursor: Open database cursor
        columns: Columns to inspect

    Returns:
        One :class:`Change` per affected row, in column order
    """
    changes: list[Change] = []
    for column in columns:
        pk = ", ".join(f'"{name}"' for name in column.primary_key)
        query = (
            f'select {pk}, "{column.column}" from "{column.schema}"."{column.table}" '
            f'where "{column.column}"::text ~* %s'
        )
        cursor.execute(query, (SQL_PREFILTER,))
        for row in cursor.fetchall():
            primary_key = tuple(row[: len(column.primary_key)])
            current = row[len(column.primary_key)]
            redacted = redact_value(current, column)
            if redacted == current:
                continue
            keys = find_sensitive_pairs(str(current))
            changes.append(Change(column, primary_key, redacted, keys))
    return changes


def apply_changes(cursor: Any, changes: Sequence[Change]) -> None:
    """
    Write the redacted values back, one row at a time.

    Args:
        cursor: Open database cursor
        changes: Changes returned by :func:`collect_changes`
    """
    for change in changes:
        column = change.column
        where = " and ".join(f'"{name}" = %s' for name in column.primary_key)
        value = (
            Json(change.redacted_value) if column.data_type in JSON_TYPES else change.redacted_value
        )
        cursor.execute(
            f'update "{column.schema}"."{column.table}" set "{column.column}" = %s where {where}',
            (value, *change.primary_key),
        )


def make_backup(url: str) -> Path:
    """
    Take a fresh custom-format backup before any write.

    Args:
        url: Database connection URL

    Returns:
        Path of the created archive

    Raises:
        RuntimeError: If ``pg_dump`` is missing or fails
    """
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    backup_dir = REPO_ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"iran_macro_db_pre_redact_{stamp}.bak"

    env = os.environ.copy()
    if parts.password:
        env["PGPASSWORD"] = parts.password
    command = [
        "pg_dump",
        "-Fc",
        "-h",
        parts.hostname or "localhost",
        "-p",
        str(parts.port or 5432),
        "-U",
        parts.username or "iran_macro",
        "-d",
        (parts.path or "/iran_macro_db").lstrip("/"),
        "-f",
        str(target),
    ]
    result = subprocess.run(command, env=env, capture_output=True, check=False)
    if result.returncode != 0:
        msg = f"pg_dump failed: {result.stderr.decode(errors='replace')[:300]}"
        raise RuntimeError(msg)
    return target


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="redact_secrets.py",
        description="Replace stored credentials with REDACTED (dry run by default).",
    )
    parser.add_argument("--database-url", default=None, help="override the .env connection URL")
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--no-backup", action="store_true", help="skip the pre-apply backup")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Entry point: report or apply credential redaction.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 clean/applied, 1 dry run with pending changes, 2 error)
    """
    args = build_parser().parse_args(argv)
    url = connection_url(args.database_url)

    try:
        with psycopg2.connect(url) as conn, conn.cursor() as cursor:
            columns = discover_columns(cursor)
            changes = collect_changes(cursor, columns)
            print(f"scanned {len(columns)} column(s); {len(changes)} row(s) need redaction")
            for change in changes:
                print(f"  {change.render()}")

            if not changes:
                print("OK: nothing to redact")
                return EXIT_OK

            if not args.apply:
                print("dry run: re-run with --apply to write the changes")
                return EXIT_CHANGES_PENDING

            if not args.no_backup:
                backup = make_backup(url)
                print(f"backup written: {backup}")
            apply_changes(cursor, changes)
            print(f"applied {len(changes)} redaction(s)")
            return EXIT_OK
    except (psycopg2.Error, RuntimeError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
