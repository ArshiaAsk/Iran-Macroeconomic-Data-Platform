#!/usr/bin/env python3
"""
Fail if a snapshot still contains a live credential.

Run this against **any** database or ``.bak`` before it is shared, published, or
attached to a release. It looks for two shapes:

1. A value under a credential key name (``api_key``, ``token``, ``password``,
   ...) that is not already ``REDACTED`` -- the precise signature of a leaked
   request parameter or an echoed ``response.request.params``.
2. A bare 40-character high-entropy token -- the shape of an EIA v2 key that
   appears with no key name attached. Pure-hex tokens (git SHAs, hashes) are
   ignored so history dumps do not drown the result in false positives.

Only the key name and a short fingerprint of the value are printed; the secret
itself is never echoed. Exit status is 0 when clean, 1 when anything is found,
and 2 on a usage or environment error, so it can gate a pipeline step.

Usage::

    python scripts/check_no_secrets.py --bak ../hf-space/iran_macro_db.bak
    python scripts/check_no_secrets.py --db-url postgresql://user:pass@host/db
    python scripts/check_no_secrets.py --path backups/ --path Data/
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.sanitize import find_sensitive_pairs, is_placeholder  # noqa: E402

# A bare 40-character alphanumeric token that is *not* pure lowercase hex and is
# not embedded inside a longer base64 blob (``/``, ``+`` and ``=`` continue a
# base64 run, so a token touching one is a fragment, not a standalone value).
HIGH_ENTROPY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9+/=])(?![0-9a-f]{40}\b)[A-Za-z0-9]{40}(?![A-Za-z0-9+/=])"
)
# Minimum Shannon entropy (bits/char) for a token to count as high-entropy.
MIN_ENTROPY_BITS_PER_CHAR = 3.0

# TimescaleDB stores hypertable data in internal chunk tables, and compressed
# chunks as base64-ish blobs whose random substrings look like bare tokens.
# Named-credential detection still runs there; bare-token detection does not.
INTERNAL_TABLE_PREFIX = "_timescaledb_internal."
COPY_BLOCK_PATTERN = re.compile(
    r"^COPY ([^\s(]+)[^\n]*FROM stdin;\n(.*?)^\\\.$",
    re.MULTILINE | re.DOTALL,
)

# Columns whose text form is worth scanning in a live database.
SCANNABLE_TYPES = frozenset({"jsonb", "json", "text", "character varying"})
PLATFORM_SCHEMAS = ("bronze", "silver", "gold", "metadata")

# Pre-filter so the database does the bulk of the work.
SQL_PREFILTER = (
    r"(api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|private[_-]?key|x[_-]?api[_-]?key|password|secret|token|authorization)"
)

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


@dataclass(frozen=True)
class Finding:
    """One suspected secret, identified without revealing its value."""

    location: str
    kind: str
    key: str
    fingerprint: str

    def render(self) -> str:
        """Human-readable, secret-free description."""
        return f"{self.location}: {self.kind} key={self.key!r} value_fp={self.fingerprint}"


def shannon_entropy(text: str) -> float:
    """
    Shannon entropy of a string, in bits per character.

    Args:
        text: Token to measure

    Returns:
        Entropy in bits/char (0.0 for an empty string)
    """
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def fingerprint(value: str) -> str:
    """Short, non-reversible identifier for a secret value."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def scan_text(text: str, location: str, bare_entropy: bool = True) -> list[Finding]:
    """
    Scan a blob of text for named and bare credentials.

    Args:
        text: SQL, log, or file contents
        location: Label included in every finding
        bare_entropy: Also look for bare high-entropy tokens; disable inside
            TimescaleDB compressed-chunk blobs, where random base64 substrings
            would otherwise produce thousands of false positives

    Returns:
        One :class:`Finding` per suspected secret
    """
    findings: list[Finding] = []

    for key, digest in find_sensitive_pairs(text):
        findings.append(Finding(location, "named-credential", key, digest))

    if bare_entropy:
        for match in HIGH_ENTROPY_PATTERN.finditer(text):
            token = match.group(0)
            if is_placeholder(token):
                continue
            if shannon_entropy(token) < MIN_ENTROPY_BITS_PER_CHAR:
                continue
            findings.append(Finding(location, "high-entropy-token", "<bare>", fingerprint(token)))

    return findings


def _iter_text_chunks(path: Path) -> Iterator[str]:
    """Yield a file's text in decoded chunks without loading it all at once."""
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            yield chunk.decode("utf-8", errors="ignore")


def scan_file(path: Path) -> list[Finding]:
    """
    Scan a plain file for credentials.

    Args:
        path: File to scan

    Returns:
        Findings, with the file path as location
    """
    return scan_text("".join(_iter_text_chunks(path)), str(path))


def scan_bak(path: Path) -> list[Finding]:
    """
    Scan a custom-format ``pg_dump`` archive by restoring it to stdout.

    The archive is gzip-compressed, so a raw byte search cannot see inside it;
    ``pg_restore -f -`` decompresses it to SQL text in memory.

    Args:
        path: ``.bak`` / ``.dump`` archive

    Returns:
        Findings, with the archive path as location

    Raises:
        FileNotFoundError: If the archive does not exist
        RuntimeError: If ``pg_restore`` is unavailable or fails
    """
    if not path.exists():
        msg = f"archive not found: {path}"
        raise FileNotFoundError(msg)
    pg_restore = shutil.which("pg_restore")
    if pg_restore is None:
        msg = "pg_restore not found on PATH; install the PostgreSQL client"
        raise RuntimeError(msg)

    result = subprocess.run(
        [pg_restore, "-f", "-", str(path)],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"pg_restore failed for {path}: {result.stderr.decode(errors='replace')[:200]}"
        raise RuntimeError(msg)
    return scan_dump_text(result.stdout.decode("utf-8", errors="ignore"), str(path))


def scan_dump_text(text: str, location: str) -> list[Finding]:
    """
    Scan restored SQL, skipping bare-token noise inside internal chunk blobs.

    Args:
        text: ``pg_restore -f -`` output
        location: Label included in every finding

    Returns:
        Findings across the whole dump
    """
    findings: list[Finding] = []
    cursor = 0
    for match in COPY_BLOCK_PATTERN.finditer(text):
        findings.extend(scan_text(text[cursor : match.start()], location))
        table = match.group(1)
        bare = not table.startswith(INTERNAL_TABLE_PREFIX)
        findings.extend(scan_text(match.group(2), f"{location}:{table}", bare_entropy=bare))
        cursor = match.end()
    findings.extend(scan_text(text[cursor:], location))
    return findings


def _iter_db_text(connection_url: str) -> Iterator[tuple[str, str]]:
    """Yield ``(location, text)`` for every scannable cell in a live database."""
    import psycopg2  # imported lazily so file-only runs need no driver

    with psycopg2.connect(connection_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select table_schema, table_name, column_name
            from information_schema.columns
            where table_schema = any(%s) and data_type = any(%s)
            order by table_schema, table_name, ordinal_position
            """,
            (list(PLATFORM_SCHEMAS), list(SCANNABLE_TYPES)),
        )
        columns = cur.fetchall()

        for schema, table, column in columns:
            location = f"{schema}.{table}.{column}"
            query = (
                f'select "{column}"::text from "{schema}"."{table}" '
                f'where "{column}"::text ~* %s or "{column}"::text ~ %s'
            )
            cur.execute(query, (SQL_PREFILTER, r"\y[A-Za-z0-9]{40}\y"))
            for (cell,) in cur.fetchall():
                yield location, cell


def scan_database(connection_url: str) -> list[Finding]:
    """
    Scan every scannable cell of a live database.

    Args:
        connection_url: libpq/SQLAlchemy-style connection URL

    Returns:
        Findings, with ``schema.table.column`` as location
    """
    findings: list[Finding] = []
    for location, text in _iter_db_text(connection_url):
        findings.extend(scan_text(text, location))
    return findings


def scan_path(path: Path) -> list[Finding]:
    """
    Scan a file, an archive, or a directory tree.

    Args:
        path: File, ``.bak`` archive, or directory

    Returns:
        Findings for everything found beneath ``path``
    """
    if path.is_dir():
        findings: list[Finding] = []
        for child in sorted(path.rglob("*")):
            if child.is_file():
                findings.extend(scan_path(child))
        return findings
    if path.suffix in {".bak", ".dump"}:
        return scan_bak(path)
    return scan_file(path)


def _dedupe(findings: Iterable[Finding]) -> list[Finding]:
    """Collapse identical findings while keeping first-seen order."""
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (finding.location, finding.kind, finding.key, finding.fingerprint)
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="check_no_secrets.py",
        description="Fail if a database, .bak, or file tree still contains a live credential.",
    )
    parser.add_argument(
        "--bak", action="append", default=[], type=Path, help="custom-format dump to scan"
    )
    parser.add_argument("--db-url", default=None, help="live database URL to scan")
    parser.add_argument(
        "--path", action="append", default=[], type=Path, help="file or directory to scan"
    )
    parser.add_argument("--quiet", action="store_true", help="print only the final verdict")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Entry point: scan the requested sources and report a secret-free verdict.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 clean, 1 findings, 2 error)
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.bak and not args.db_url and not args.path:
        parser.print_usage(sys.stderr)
        print("error: give at least one of --bak, --db-url, --path", file=sys.stderr)
        return EXIT_ERROR

    findings: list[Finding] = []
    try:
        for bak in args.bak:
            findings.extend(scan_bak(bak))
        for path in args.path:
            findings.extend(scan_path(path))
        if args.db_url:
            findings.extend(scan_database(args.db_url))
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    findings = _dedupe(findings)
    if not args.quiet:
        for finding in findings:
            print(finding.render())
        print(
            f"scanned: {len(args.bak)} archive(s), {len(args.path)} path(s), "
            f"{'1 database' if args.db_url else 'no database'}"
        )

    if findings:
        print(f"FAIL: {len(findings)} suspected secret(s) found", file=sys.stderr)
        return EXIT_FINDINGS

    print("OK: no live credentials found")
    return EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
