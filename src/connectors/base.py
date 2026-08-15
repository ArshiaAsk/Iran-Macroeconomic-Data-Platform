"""
Abstract base class for data connectors.

Defines the protocol that all data source connectors must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.utils.validation import ValidationResult


@dataclass
class IndicatorMetadata:
    """Metadata for an economic indicator."""

    indicator_id: str
    name: str
    description: str | None
    unit: str | None
    frequency: str  # daily, monthly, quarterly, annual
    domain: str  # inflation, gdp, monetary, etc.
    source_name: str
    source_url: str | None
    availability_start: datetime | None
    availability_end: datetime | None
    has_base_year_changes: bool
    base_years: list[int] | None


class DataConnector(ABC):
    """Abstract base class for all data source connectors."""

    def __init__(self, source_name: str) -> None:
        """
        Initialize connector.

        Args:
            source_name: Name of the data source
        """
        self.source_name = source_name

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to data source.

        Returns:
            True if connection successful, False otherwise

        Raises:
            ConnectionError: If connection fails after retries
        """
        pass

    @abstractmethod
    def discover(self) -> list[IndicatorMetadata]:
        """
        Discover available indicators from data source.

        Returns:
            List of available indicators with metadata

        Raises:
            DataRetrievalError: If discovery fails
        """
        pass

    @abstractmethod
    def fetch(
        self, indicator_id: str, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """
        Fetch time-series data for an indicator.

        Args:
            indicator_id: Unique identifier for the indicator
            start_date: Start date for data retrieval
            end_date: End date for data retrieval

        Returns:
            DataFrame with columns: timestamp, value, metadata

        Raises:
            DataRetrievalError: If fetch fails after retries
            ValidationError: If fetched data is invalid
        """
        pass

    @abstractmethod
    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """
        Validate fetched data.

        Args:
            data: DataFrame to validate

        Returns:
            Validation result with errors and warnings

        Raises:
            ValidationError: If validation fails critically
        """
        pass

    def disconnect(self) -> None:
        """
        Close connection to data source.

        Override if cleanup is needed.
        """
        pass

    def __enter__(self) -> "DataConnector":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Context manager exit."""
        self.disconnect()
