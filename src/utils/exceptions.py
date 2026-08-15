"""
Custom exception hierarchy for Iran Macroeconomic Data Platform.

Provides structured error handling for different failure modes.
"""


class DataPlatformError(Exception):
    """Base exception for all platform errors."""

    pass


class ConnectionError(DataPlatformError):
    """Raised when connection to data source fails."""

    pass


class DataRetrievalError(DataPlatformError):
    """Raised when data retrieval fails after retries."""

    pass


class ValidationError(DataPlatformError):
    """Raised when data validation fails."""

    pass


class ParsingError(DataPlatformError):
    """Raised when parsing raw data fails."""

    pass


class ConfigurationError(DataPlatformError):
    """Raised when configuration is invalid or missing."""

    pass


class DatabaseError(DataPlatformError):
    """Raised when database operations fail."""

    pass


class ChainLinkingError(DataPlatformError):
    """Raised when chain-linking operation fails."""

    pass
