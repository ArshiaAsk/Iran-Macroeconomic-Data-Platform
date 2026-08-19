"""
Retry, backoff, and rate-limiting helpers shared by every connector.

Transient network faults are the norm when collecting Iranian macroeconomic data
from public APIs, so all HTTP calls funnel through :class:`RetryPolicy`.

Only genuinely retryable failures are retried: connection errors, timeouts,
HTTP 429 and HTTP 5xx. Any other 4xx is a permanent client error -- a bad
indicator code will never start working -- so those propagate immediately.

The sleep and clock functions are injectable so unit tests run instantly without
patching :mod:`time`.
"""

import functools
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ParamSpec, TypeVar

# src.utils.exceptions defines its own ConnectionError, which shadows the
# builtin; alias the requests one so the two are never confused.
from requests import ConnectionError as RequestsConnectionError
from requests import HTTPError, Timeout

from src.utils.config import get_config
from src.utils.exceptions import DataRetrievalError
from src.utils.logging import get_logger, log_with_context

P = ParamSpec("P")
T = TypeVar("T")

logger = get_logger(__name__)

# Retryable HTTP statuses: rate limiting plus every server-side error.
RATE_LIMIT_STATUS = 429
SERVER_ERROR_MIN = 500
SERVER_ERROR_MAX = 600

DEFAULT_BASE_DELAY_SECONDS = 1.0
DEFAULT_MAX_DELAY_SECONDS = 30.0
DEFAULT_JITTER_RATIO = 0.25

# Transport-level failures that are always worth another attempt.
RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (Timeout, RequestsConnectionError)


def is_retryable_status(status_code: int) -> bool:
    """
    Report whether an HTTP status justifies another attempt.

    Args:
        status_code: HTTP status code from the response

    Returns:
        True for 429 and any 5xx, False otherwise
    """
    if status_code == RATE_LIMIT_STATUS:
        return True
    return SERVER_ERROR_MIN <= status_code < SERVER_ERROR_MAX


def is_retryable_exception(exc: BaseException) -> bool:
    """
    Report whether an exception represents a transient failure.

    Args:
        exc: Exception raised by the wrapped call

    Returns:
        True if the call should be attempted again
    """
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True
    if isinstance(exc, HTTPError):
        response = exc.response
        return response is not None and is_retryable_status(response.status_code)
    return False


@dataclass
class RetryPolicy:
    """
    Exponential backoff with jitter for transient network failures.

    Attempt ``n`` waits ``min(base_delay * 2 ** (n - 1), max_delay)`` seconds,
    multiplied by a random factor in ``[1, 1 + jitter_ratio]`` so concurrent
    callers do not retry in lockstep. The effective maximum delay is therefore
    ``max_delay * (1 + jitter_ratio)``.
    """

    max_attempts: int
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS
    jitter_ratio: float = DEFAULT_JITTER_RATIO
    sleep: Callable[[float], None] = time.sleep
    jitter_source: Callable[[], float] = random.random

    @classmethod
    def from_config(cls, **overrides: Any) -> "RetryPolicy":
        """
        Build a policy from ``CollectionConfig``.

        ``retry_max`` is the total number of attempts. The config validator
        allows 0, but a call must be attempted at least once, so the value is
        floored at 1.

        Args:
            **overrides: Field values that take precedence over the config

        Returns:
            Configured retry policy
        """
        max_attempts = max(1, get_config().collection.retry_max)
        return cls(max_attempts=max_attempts, **overrides)

    def delay_for(self, attempt: int) -> float:
        """
        Compute the delay before the attempt following ``attempt``.

        Args:
            attempt: 1-based number of the attempt that just failed

        Returns:
            Delay in seconds, jittered upward from the capped backoff
        """
        backoff = min(self.base_delay * 2.0 ** (attempt - 1), self.max_delay)
        return backoff * (1.0 + self.jitter_ratio * self.jitter_source())

    def run(self, operation: Callable[[], T], operation_name: str = "request", **context: Any) -> T:
        """
        Execute ``operation``, retrying transient failures.

        Args:
            operation: Zero-argument callable to execute
            operation_name: Name used in log and error messages
            **context: Extra fields attached to every retry log record

        Returns:
            Whatever ``operation`` returns

        Raises:
            DataRetrievalError: If every attempt failed with a retryable error
            Exception: Non-retryable errors propagate unchanged
        """
        started = time.monotonic()
        last_exc: BaseException | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation()
            except (Timeout, RequestsConnectionError, HTTPError) as exc:
                if not is_retryable_exception(exc):
                    raise
                last_exc = exc
                if attempt == self.max_attempts:
                    break
                delay = self.delay_for(attempt)
                log_with_context(
                    logger,
                    "WARNING",
                    "retrying after transient failure",
                    operation=operation_name,
                    attempt=attempt,
                    max_attempts=self.max_attempts,
                    delay=round(delay, 3),
                    error=str(exc),
                    **context,
                )
                self.sleep(delay)

        elapsed = time.monotonic() - started
        msg = (
            f"{operation_name} failed after {self.max_attempts} attempt(s) "
            f"in {elapsed:.2f}s: {last_exc}"
        )
        raise DataRetrievalError(msg) from last_exc


def retry_with_backoff(
    policy: RetryPolicy | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorate a function so transient failures are retried.

    Args:
        policy: Policy to use; when omitted one is built from config per call

    Returns:
        Decorator wrapping the target function
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            active = policy if policy is not None else RetryPolicy.from_config()
            return active.run(lambda: func(*args, **kwargs), func.__qualname__)

        return wrapper

    return decorator


@dataclass
class RateLimiter:
    """
    Enforce a minimum interval between successive calls.

    Politeness requirement from AGENTS.md: stay at or below 1-2 requests per
    second against public sources.
    """

    min_interval: float
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    _last_call: float | None = field(default=None, init=False, repr=False)

    def wait(self) -> float:
        """
        Block until the minimum interval since the previous call has elapsed.

        Returns:
            Number of seconds actually slept (0.0 when no wait was needed)
        """
        now = self.monotonic()
        slept = 0.0

        if self._last_call is not None:
            remaining = self.min_interval - (now - self._last_call)
            if remaining > 0:
                self.sleep(remaining)
                slept = remaining

        # Advance from the intended wake-up time rather than re-reading the
        # clock, so an injected fake clock stays consistent.
        self._last_call = now + slept
        return slept
