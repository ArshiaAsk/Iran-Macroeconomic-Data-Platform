"""
Secret redaction helpers shared by every connector.

Bronze is append-only and long-lived, so a credential that reaches it is
effectively permanent. Two failure modes have to be closed:

1. **Request parameters.** A connector builds a query string containing an
   ``api_key``. Persisting that mapping (or the URL built from it) leaks the
   credential.
2. **Echoed parameters.** Some APIs (EIA v2 among them) echo the request back in
   the response body under ``response.request.params``, so a connector that
   stores the raw payload "verbatim" stores the key even though it never
   intended to.

There are two redaction modes, and they are deliberately kept separate:

* :func:`redact_secrets` works on **structured** payloads. It replaces the value
  under a sensitive key name and, for URL-shaped keys, strips credentials from
  the URL. It does *not* pattern-scan arbitrary strings, because scraper payloads
  legitimately contain HTML/JavaScript (SCI pages include ``token: currentToken``)
  and rewriting those would corrupt Bronze.
* :func:`sanitize_text` works on **free text** -- exception messages, retry logs,
  URLs -- where no structure is available and pattern matching is the only
  option.

``REDACTED`` is the single replacement token so a future scan can recognise a
sanitised value unambiguously.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "REDACTED"

#: Key names whose values are never persisted, logged, or raised. Matching is
#: case-insensitive and treats ``-`` and ``_`` as equivalent, so ``api-key``,
#: ``Api_Key`` and ``API_KEY`` all match.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "key",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "auth_token",
        "password",
        "passwd",
        "pwd",
        "secret",
        "client_secret",
        "private_key",
        "authorization",
        "auth",
        "bearer",
        "x_api_key",
    }
)

#: Generic names that also occur as ordinary payload fields (``token`` in page
#: JavaScript, ``key`` in a lookup table). In free text these are only reported
#: when the value actually looks like a credential.
WEAK_SENSITIVE_KEYS: frozenset[str] = frozenset({"key", "token", "auth", "bearer"})

#: Keys whose string value is a URL and should have its credentials stripped.
URL_KEYS: frozenset[str] = frozenset(
    {"url", "uri", "request_url", "source_url", "endpoint", "href"}
)

#: Values that are already placeholders; redacting them again is a no-op and
#: flagging them would be a false positive.
PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {"redacted", "***", "", "none", "null", "your_eia_api_key_here", "demo_key"}
)

#: HTTP auth scheme names; the token follows the scheme, so the scheme itself is
#: never the secret. ``Authorization: Bearer <token>`` is handled separately.
AUTH_SCHEMES: frozenset[str] = frozenset({"bearer", "basic", "digest", "negotiate"})

# Minimum length and character mix for a value to "look like" a credential.
SECRET_MIN_LENGTH = 16

# ``api_key=VALUE`` / ``"api_key": "VALUE"`` / ``api_key: VALUE`` in free text.
# The optional quote after the key name covers JSON payloads.
_TEXT_KV_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"auth[_-]?token|client[_-]?secret|private[_-]?key|x[_-]?api[_-]?key|"
    r"password|passwd|secret|token|authorization)\b"
    r"[\"']?\s*[:=]\s*"
    r"[\"']?([^\s\"'&,;}\]]+)"
)

# ``Authorization: Bearer <token>``.
_BEARER_PATTERN = re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]{8,})")


def _normalise_key(name: str) -> str:
    """Canonical form of a key name for denylist comparison."""
    return name.strip().lower().replace("-", "_")


def is_sensitive_key(name: str) -> bool:
    """
    Report whether a key name holds a secret.

    Args:
        name: Dictionary key or query-parameter name

    Returns:
        True when the value under this key must be redacted
    """
    return _normalise_key(name) in SENSITIVE_KEYS


def is_placeholder(value: str) -> bool:
    """Report whether a value is already a redaction marker or placeholder."""
    return value.strip().lower() in PLACEHOLDER_VALUES


def looks_like_secret_value(value: str) -> bool:
    """
    Report whether a free-text value has the shape of a credential.

    Used to suppress false positives from generic key names in page source,
    where ``token: currentToken`` is a JavaScript variable, not a secret. A
    credential is at least :data:`SECRET_MIN_LENGTH` characters and mixes
    letters and digits.

    Args:
        value: Candidate value captured after a sensitive key name

    Returns:
        True when the value plausibly is a credential
    """
    if len(value) < SECRET_MIN_LENGTH:
        return False
    return any(char.isdigit() for char in value) and any(char.isalpha() for char in value)


def sanitize_text(text: str, secrets: Iterable[str | None] = ()) -> str:
    """
    Redact credentials embedded in free text.

    Handles the three shapes that leak in practice: ``key=value`` pairs in a
    query string or exception message, ``Authorization: Bearer <token>``
    headers, and exact secret values that appear with no key name attached
    (pass them via ``secrets``).

    Args:
        text: Message, URL, or log line to scrub
        secrets: Exact secret values to replace wherever they appear

    Returns:
        The text with every recognised credential replaced by ``REDACTED``
    """
    scrubbed = text
    for secret in secrets:
        if secret:
            scrubbed = scrubbed.replace(secret, REDACTED)

    # Bearer tokens first: ``Authorization: Bearer <token>`` would otherwise be
    # matched by the generic ``key: value`` pattern with ``Bearer`` as the value.
    scrubbed = _BEARER_PATTERN.sub(lambda m: f"{m.group(1)} {REDACTED}", scrubbed)

    def _replace(match: re.Match[str]) -> str:
        value = match.group(2)
        if is_placeholder(value) or value.lower() in AUTH_SCHEMES:
            return match.group(0)
        return f"{match.group(1)}={REDACTED}"

    return _TEXT_KV_PATTERN.sub(_replace, scrubbed)


def sanitize_url(url: str | None, secrets: Iterable[str | None] = ()) -> str | None:
    """
    Redact sensitive query parameters and userinfo from a URL.

    Args:
        url: Absolute URL, possibly carrying ``?api_key=...`` or ``user:pass@``
        secrets: Exact secret values to replace wherever they appear

    Returns:
        The URL with sensitive parts replaced by ``REDACTED``; ``None`` passes
        through unchanged
    """
    if not url:
        return url
    parts = urlsplit(url)

    netloc = parts.netloc
    if "@" in netloc:
        userinfo, _, host = netloc.rpartition("@")
        if ":" in userinfo:
            user, _, _ = userinfo.partition(":")
            netloc = f"{user}:{REDACTED}@{host}"

    query = parse_qsl(parts.query, keep_blank_values=True)
    if query:
        safe_query = [
            (name, REDACTED if is_sensitive_key(name) else value) for name, value in query
        ]
        rebuilt = urlunsplit(parts._replace(netloc=netloc, query=urlencode(safe_query)))
    else:
        rebuilt = urlunsplit(parts._replace(netloc=netloc))

    return sanitize_text(rebuilt, secrets)


def _replace_exact(text: str, secrets: Iterable[str | None]) -> str:
    """Replace exact secret values in a string, leaving everything else intact."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def redact_secrets(value: Any, secrets: Iterable[str | None] = ()) -> Any:
    """
    Recursively redact sensitive values in a JSON-like structure.

    Mappings keep their shape: a value under a sensitive key becomes
    ``REDACTED``; a value under a URL-shaped key is passed through
    :func:`sanitize_url`; everything else is recursed into. Strings are only
    touched for exact ``secrets`` matches, so HTML/JavaScript payloads are never
    pattern-rewritten and remain byte-faithful.

    Args:
        value: Any JSON-like object (dict, list, scalar)
        secrets: Exact secret values to replace in every string

    Returns:
        A new object of the same shape with credentials redacted
    """
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            normalised = _normalise_key(key) if isinstance(key, str) else ""
            if normalised in SENSITIVE_KEYS:
                redacted[key] = REDACTED
            elif normalised in URL_KEYS and isinstance(item, str):
                redacted[key] = sanitize_url(item, secrets)
            else:
                redacted[key] = redact_secrets(item, secrets)
        return redacted
    if isinstance(value, list | tuple):
        return [redact_secrets(item, secrets) for item in value]
    if isinstance(value, str):
        return _replace_exact(value, secrets)
    return value


def sanitize_params(params: Any, secrets: Iterable[str | None] = ()) -> Any:
    """
    Alias for :func:`redact_secrets` for query-parameter mappings.

    Args:
        params: Request parameters (or any JSON-like object)
        secrets: Exact secret values to replace in every string

    Returns:
        A redacted copy of ``params``
    """
    return redact_secrets(params, secrets)


def find_sensitive_pairs(text: str) -> list[tuple[str, str]]:
    """
    Locate ``key: value`` pairs in text that still hold a live-looking secret.

    Used by the snapshot scanner; the secret value itself is never returned,
    only its key name and a short fingerprint. Generic key names (``token``,
    ``key``) are only reported when the value looks like a credential, so page
    source such as ``token: currentToken`` is not flagged.

    Args:
        text: Text to scan (SQL dump line, log line, ...)

    Returns:
        ``(key_name, fingerprint)`` for every non-placeholder sensitive value
    """
    hits: list[tuple[str, str]] = []
    for match in _TEXT_KV_PATTERN.finditer(text):
        key, value = match.group(1), match.group(2)
        normalised = _normalise_key(key)
        if is_placeholder(value) or value.lower() in AUTH_SCHEMES:
            continue
        if normalised in WEAK_SENSITIVE_KEYS and not looks_like_secret_value(value):
            continue
        digest = hashlib.sha256(value.encode()).hexdigest()[:12]
        hits.append((normalised, digest))
    return hits
