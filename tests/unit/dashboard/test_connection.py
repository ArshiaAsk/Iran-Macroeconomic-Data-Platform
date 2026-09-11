"""Unit tests for the cached dashboard connection."""

from dataclasses import dataclass
from typing import ClassVar

import dashboard.connection as connection_module


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
