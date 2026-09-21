"""Tests for the shared empty / error / loading states (Task 22).

The states are thin wrappers over the native callout, so most assertions read the
typed ``AppTest`` accessors (``app.info``/``app.error``) that the callout produces.
Two structural properties cannot be seen that way — that every state routes through
the callout component, and that its tone is fixed by the state rather than passed
in — so those are asserted by spying on the callout.
"""

import pytest
from streamlit.testing.v1 import AppTest

from dashboard.components.states import render_empty, render_error, render_loading
from dashboard.i18n import STRING_CATALOG, t


def _run(script: str) -> AppTest:
    app = AppTest.from_string(script)
    app.run()
    return app


def _empty_keys() -> list[str]:
    return sorted(key for key in STRING_CATALOG if key.startswith("empty."))


def test_render_empty_renders_the_native_info_alert() -> None:
    app = _run(
        "from dashboard.components.states import render_empty\n"
        'render_empty("empty.no_observations")\n'
    )

    assert not app.exception
    assert [info.value for info in app.info] == [t("empty.no_observations")]


def test_every_existing_empty_key_still_renders() -> None:
    """The Task 22 helpers must accept every `empty.*` key already in the catalog."""
    keys = _empty_keys()
    assert keys, "the catalog has no empty.* keys"

    app = _run(
        "from dashboard.components.states import render_empty\n"
        f"for key in {keys!r}:\n"
        "    render_empty(key)\n"
    )

    assert not app.exception
    assert [info.value for info in app.info] == [t(key) for key in keys]


def test_render_loading_renders_the_native_info_alert() -> None:
    app = _run("from dashboard.components.states import render_loading\nrender_loading()\n")

    assert not app.exception
    assert [info.value for info in app.info] == [t("state.loading")]


def test_render_error_renders_the_native_error_alert_with_the_retry_hint() -> None:
    app = _run(
        "from dashboard.components.states import render_error\nrender_error('state.error')\n"
    )

    assert not app.exception
    assert not app.info
    assert [error.value for error in app.error] == [
        f"{t('state.error')}\n\n{t('state.retry_hint')}"
    ]


def test_render_error_appends_the_detail_beneath_the_retry_hint() -> None:
    app = _run(
        "from dashboard.components.states import render_error\n"
        "render_error('state.error', detail='relation gold_analytical does not exist')\n"
    )

    assert not app.exception
    assert [error.value for error in app.error] == [
        f"{t('state.error')}\n\n{t('state.retry_hint')}\n\nrelation gold_analytical does not exist"
    ]


def test_states_are_composable_in_one_run() -> None:
    app = _run(
        "from dashboard.components.states import render_empty, render_error, render_loading\n"
        'render_empty("empty.select_indicators")\n'
        "render_loading()\n"
        'render_error("state.error")\n'
    )

    assert not app.exception
    assert len(app.info) == 2
    assert len(app.error) == 1


def test_the_same_state_key_cannot_render_twice_in_one_run() -> None:
    """Documents the callout's container-key rule the states inherit."""
    app = _run(
        "from dashboard.components.states import render_empty\n"
        'render_empty("empty.no_observations")\n'
        'render_empty("empty.no_observations")\n'
    )

    assert app.exception
    assert "multiple elements with the same" in str(app.exception[0].value).lower()


def test_states_route_through_the_native_callout_with_a_fixed_tone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def spy(key: str, *, tone: str = "warn", **kwargs: object) -> None:
        calls.append((key, tone))

    monkeypatch.setattr("dashboard.components.states.render_callout", spy)
    render_empty("empty.no_observations")
    render_error("state.error")
    render_loading()

    # The tone is decided by the state, so no caller can render a failure in the
    # informational tone or an empty state as an error.
    assert calls == [
        ("empty.no_observations", "info"),
        ("state.error", "error"),
        ("state.loading", "info"),
    ]


def test_render_error_hands_the_retry_hint_to_the_callout_as_its_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def spy(key: str, *, tone: str = "warn", detail: str | None = None, **kwargs: object) -> None:
        captured.update(key=key, tone=tone, detail=detail)

    monkeypatch.setattr("dashboard.components.states.render_callout", spy)
    render_error("state.error", detail="boom")

    assert captured["detail"] == f"{t('state.retry_hint')}\n\nboom"
