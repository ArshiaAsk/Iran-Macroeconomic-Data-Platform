"""
Unit tests for the retry, backoff, and rate-limiting helpers.

Sleeps are injected as no-ops throughout, so the suite exercises the full
backoff logic without spending wall-clock time.
"""

from typing import Any

import pytest
from requests import ConnectionError as RequestsConnectionError
from requests import HTTPError, Timeout

from src.utils.exceptions import DataRetrievalError
from src.utils.retry import (
    RateLimiter,
    RetryPolicy,
    is_retryable_exception,
    is_retryable_status,
    retry_with_backoff,
)


class _Response:
    """Minimal response stub carrying only a status code."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


# Transport failure messages, named so the ``raise`` sites stay one-liners.
TIMED_OUT = "read timed out"
REFUSED = "connection refused"


def _policy(max_attempts: int = 3, **overrides: Any) -> tuple[RetryPolicy, list[float]]:
    """Build a policy whose sleeps are recorded instead of performed."""
    slept: list[float] = []
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=1.0,
        sleep=slept.append,
        jitter_source=lambda: 0.0,
        **overrides,
    )
    return policy, slept


# ------------------------------------------------------------------ predicates


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(429, True), (500, True), (502, True), (599, True), (200, False), (404, False), (400, False)],
)
def test_is_retryable_status(status_code: int, expected: bool) -> None:
    """Only 429 and 5xx justify another attempt."""
    assert is_retryable_status(status_code) is expected


def test_is_retryable_exception_transport_failures() -> None:
    """Timeouts and connection errors are always transient."""
    assert is_retryable_exception(Timeout("read timed out")) is True
    assert is_retryable_exception(RequestsConnectionError("refused")) is True


def test_is_retryable_exception_http_errors_depend_on_status() -> None:
    """An HTTPError is retryable only when its status is."""
    assert is_retryable_exception(HTTPError(response=_Response(503))) is True  # type: ignore[arg-type]
    assert is_retryable_exception(HTTPError(response=_Response(429))) is True  # type: ignore[arg-type]
    assert is_retryable_exception(HTTPError(response=_Response(404))) is False  # type: ignore[arg-type]


def test_is_retryable_exception_http_error_without_response() -> None:
    """An HTTPError with no response carries no evidence of transience."""
    assert is_retryable_exception(HTTPError("no response attached")) is False


def test_is_retryable_exception_ignores_unrelated_errors() -> None:
    """Programming errors are never retried."""
    assert is_retryable_exception(ValueError("bad input")) is False


# ---------------------------------------------------------------------- delays


def test_delay_grows_exponentially() -> None:
    """Each attempt waits twice as long as the previous one."""
    policy, _ = _policy()
    assert policy.delay_for(1) == pytest.approx(1.0)
    assert policy.delay_for(2) == pytest.approx(2.0)
    assert policy.delay_for(3) == pytest.approx(4.0)


def test_delay_is_capped_at_max_delay() -> None:
    """Backoff never exceeds ``max_delay`` before jitter."""
    policy, _ = _policy(max_attempts=20, max_delay=5.0)
    assert policy.delay_for(10) == pytest.approx(5.0)


def test_jitter_stays_within_bounds() -> None:
    """Jitter scales the delay into ``[backoff, backoff * (1 + ratio)]``."""
    lowest = RetryPolicy(max_attempts=3, base_delay=1.0, jitter_source=lambda: 0.0)
    highest = RetryPolicy(max_attempts=3, base_delay=1.0, jitter_source=lambda: 1.0)

    assert lowest.delay_for(2) == pytest.approx(2.0)
    assert highest.delay_for(2) == pytest.approx(2.0 * 1.25)


def test_from_config_floors_attempts_at_one() -> None:
    """A configured retry_max of 0 still permits one attempt."""
    policy = RetryPolicy.from_config()
    assert policy.max_attempts >= 1


def test_from_config_accepts_overrides() -> None:
    """Overrides take precedence over configuration."""
    policy = RetryPolicy.from_config(base_delay=0.25, max_delay=2.0)
    assert policy.base_delay == pytest.approx(0.25)
    assert policy.max_delay == pytest.approx(2.0)


# -------------------------------------------------------------------- run loop


def test_run_returns_immediately_on_success() -> None:
    """A call that works is not retried and nothing sleeps."""
    policy, slept = _policy()
    calls: list[int] = []

    def operation() -> str:
        calls.append(1)
        return "payload"

    assert policy.run(operation) == "payload"
    assert len(calls) == 1
    assert slept == []


def test_run_retries_then_succeeds() -> None:
    """A transient failure is retried and the later success is returned."""
    policy, slept = _policy()
    attempts: list[int] = []

    def operation() -> str:
        attempts.append(len(attempts) + 1)
        if len(attempts) < 2:
            raise Timeout(TIMED_OUT)
        return "payload"

    assert policy.run(operation, "world_bank GET") == "payload"
    assert len(attempts) == 2
    assert slept == [pytest.approx(1.0)]


def test_run_exhausts_attempts_and_raises_data_retrieval_error() -> None:
    """When every attempt fails the transport error is wrapped."""
    policy, slept = _policy(max_attempts=3)

    def operation() -> str:
        raise RequestsConnectionError(REFUSED)

    with pytest.raises(DataRetrievalError, match="failed after 3 attempt"):
        policy.run(operation, "world_bank GET")

    # Sleeps happen between attempts only: three attempts, two waits.
    assert slept == [pytest.approx(1.0), pytest.approx(2.0)]


def test_run_preserves_the_original_exception_as_cause() -> None:
    """The wrapped error keeps the transport failure for debugging."""
    policy, _ = _policy(max_attempts=1)
    failure = Timeout("read timed out")

    def operation() -> str:
        raise failure

    with pytest.raises(DataRetrievalError) as caught:
        policy.run(operation)

    assert caught.value.__cause__ is failure


def test_run_does_not_retry_a_404() -> None:
    """A permanent client error propagates on the first attempt."""
    policy, slept = _policy()
    attempts: list[int] = []

    def operation() -> str:
        attempts.append(1)
        raise HTTPError(response=_Response(404))  # type: ignore[arg-type]

    with pytest.raises(HTTPError):
        policy.run(operation)

    assert len(attempts) == 1
    assert slept == []


@pytest.mark.parametrize("status_code", [429, 503])
def test_run_retries_rate_limits_and_server_errors(status_code: int) -> None:
    """429 and 5xx are retried up to the attempt limit."""
    policy, slept = _policy(max_attempts=2)
    attempts: list[int] = []

    def operation() -> str:
        attempts.append(1)
        raise HTTPError(response=_Response(status_code))  # type: ignore[arg-type]

    with pytest.raises(DataRetrievalError):
        policy.run(operation)

    assert len(attempts) == 2
    assert len(slept) == 1


def test_run_lets_unrelated_exceptions_through() -> None:
    """A bug in the operation must not be disguised as a retrieval failure."""
    policy, _ = _policy()

    def operation() -> str:
        msg = "programming error"
        raise ValueError(msg)

    with pytest.raises(ValueError, match="programming error"):
        policy.run(operation)


# ------------------------------------------------------------------- decorator


def test_retry_with_backoff_decorator_retries() -> None:
    """The decorator applies the same policy to a plain function."""
    policy, slept = _policy()
    attempts: list[int] = []

    @retry_with_backoff(policy)
    def flaky(value: int) -> int:
        attempts.append(value)
        if len(attempts) < 2:
            raise Timeout(TIMED_OUT)
        return value * 2

    assert flaky(21) == 42
    assert len(attempts) == 2
    assert len(slept) == 1


def test_retry_with_backoff_preserves_metadata() -> None:
    """``functools.wraps`` keeps the wrapped function identifiable."""

    @retry_with_backoff(RetryPolicy(max_attempts=1))
    def documented() -> None:
        """Docstring that must survive decoration."""

    assert documented.__name__ == "documented"
    assert documented.__doc__ is not None


def test_retry_with_backoff_builds_a_policy_from_config() -> None:
    """Omitting the policy falls back to configuration."""
    calls: list[int] = []

    @retry_with_backoff()
    def counted() -> str:
        calls.append(1)
        return "ok"

    assert counted() == "ok"
    assert len(calls) == 1


# ----------------------------------------------------------------- rate limits


def test_rate_limiter_does_not_wait_on_the_first_call() -> None:
    """Nothing has been requested yet, so nothing is owed."""
    slept: list[float] = []
    limiter = RateLimiter(min_interval=0.5, sleep=slept.append, monotonic=lambda: 100.0)

    assert limiter.wait() == pytest.approx(0.0)
    assert slept == []


def test_rate_limiter_sleeps_the_remaining_interval() -> None:
    """A back-to-back call waits out the rest of the interval."""
    slept: list[float] = []
    clock = iter([100.0, 100.2])
    limiter = RateLimiter(min_interval=0.5, sleep=slept.append, monotonic=lambda: next(clock))

    limiter.wait()
    waited = limiter.wait()

    assert waited == pytest.approx(0.3)
    assert slept == [pytest.approx(0.3)]


def test_rate_limiter_skips_the_wait_once_the_interval_has_passed() -> None:
    """A caller that was slow anyway is not delayed further."""
    slept: list[float] = []
    clock = iter([100.0, 101.0])
    limiter = RateLimiter(min_interval=0.5, sleep=slept.append, monotonic=lambda: next(clock))

    limiter.wait()

    assert limiter.wait() == pytest.approx(0.0)
    assert slept == []
