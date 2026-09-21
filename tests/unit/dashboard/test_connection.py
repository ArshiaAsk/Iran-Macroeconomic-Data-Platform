"""Unit tests for the cached dashboard connection."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar

import pytest

import dashboard.connection as connection_module


@pytest.fixture(autouse=True)
def _clear_the_connection_cache() -> Iterator[None]:
    """Keep the fake connection out of the process-wide cache.

    ``get_connection`` is ``st.cache_resource``-cached, so a test that populates it
    with a fake leaves that fake in the cache for every later test in the session —
    including tests that run the real entrypoint, which then fails on the fake's
    missing attributes. ``monkeypatch`` undoes the attribute patches but not the
    cache entry, so the cache is cleared on both sides of each test here.
    """
    connection_module.get_connection.clear()
    yield
    connection_module.get_connection.clear()


@dataclass
class FakeDatabaseConfig:
    url: str


@dataclass
class FakeAppConfig:
    database: FakeDatabaseConfig


class FakeDatabaseConnection:
    instances: ClassVar[list["FakeDatabaseConnection"]] = []

    def __init__(self, database_url: str, echo: bool = False) -> None:
        self.database_url = database_url
        self.echo = echo
        self.instances.append(self)


def test_connection_is_cached_per_process(monkeypatch) -> None:
    FakeDatabaseConnection.instances.clear()
    monkeypatch.setattr(connection_module, "DatabaseConnection", FakeDatabaseConnection)
    monkeypatch.setattr(
        connection_module,
        "get_config",
        lambda: FakeAppConfig(FakeDatabaseConfig("postgresql://cached")),
    )
    connection_module.get_connection.clear()

    first = connection_module.get_connection()
    second = connection_module.get_connection()

    assert first is second
    assert len(FakeDatabaseConnection.instances) == 1
    assert first.database_url == "postgresql://cached"
