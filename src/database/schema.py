"""
Database schema models for Iran Macroeconomic Data Platform.

Implements 4-layer medallion architecture:
- Bronze: Raw data storage
- Silver: Cleaned and validated data
- Gold: Analysis-ready with chain-linking
- Metadata: Indicator catalog and audit logs
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime (column default)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all database models."""


# ============================================================================
# BRONZE LAYER - Raw Data Storage
# ============================================================================


class BronzeRaw(Base):
    """Bronze layer: Raw data from all sources (immutable)."""

    __tablename__ = "bronze_raw"
    __table_args__ = (
        Index("idx_bronze_source_timestamp", "source_name", "collection_timestamp"),
        {"schema": "bronze"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'api', 'scraper', 'file'
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    collection_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


# ============================================================================
# SILVER LAYER - Cleaned Data
# ============================================================================


class SilverCleaned(Base):
    """Silver layer: Cleaned and validated time-series data."""

    __tablename__ = "silver_cleaned"
    __table_args__ = (
        Index("idx_silver_indicator_timestamp", "indicator_id", "timestamp"),
        Index("idx_silver_source", "source_name"),
        {"schema": "silver"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    indicator_id: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # daily, monthly, etc.
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bronze_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bronze.bronze_raw.id"), nullable=False
    )
    validation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="valid"
    )  # valid, flagged, invalid
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_outlier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    bronze_record: Mapped["BronzeRaw"] = relationship("BronzeRaw")


# ============================================================================
# GOLD LAYER - Analysis-Ready Data
# ============================================================================


class GoldAnalytical(Base):
    """Gold layer: Chain-linked, analysis-ready time-series (TimescaleDB hypertable)."""

    __tablename__ = "gold_analytical"
    __table_args__ = (
        Index("idx_gold_indicator_timestamp", "indicator_id", "timestamp"),
        Index("idx_gold_domain", "domain"),
        {"schema": "gold"},
    )

    # Composite primary key: TimescaleDB requires the partitioning column
    # ("timestamp") to be part of every unique index on a hypertable.
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    indicator_id: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    original_value: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Before chain-linking
    is_chain_linked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chain_linking_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)  # inflation, gdp, etc.
    silver_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("silver.silver_cleaned.id"), nullable=False
    )
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    silver_record: Mapped["SilverCleaned"] = relationship("SilverCleaned")


# ============================================================================
# METADATA LAYER - Indicator Catalog and Audit Logs
# ============================================================================


class IndicatorCatalog(Base):
    """Metadata: Catalog of all available indicators."""

    __tablename__ = "indicator_catalog"
    __table_args__ = (
        Index("idx_indicator_domain", "domain"),
        Index("idx_indicator_source", "source_name"),
        {"schema": "metadata"},
    )

    indicator_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    availability_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    availability_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    has_base_year_changes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_years: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)  # List of base years
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class DataCollectionLog(Base):
    """Metadata: Audit log for data collection operations."""

    __tablename__ = "data_collection_log"
    __table_args__ = (
        Index("idx_collection_source_timestamp", "source_name", "collection_timestamp"),
        {"schema": "metadata"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    collection_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, partial, failed
    records_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class TransformationLog(Base):
    """Metadata: Audit log for Bronze → Silver → Gold transformations."""

    __tablename__ = "transformation_log"
    __table_args__ = (
        Index("idx_transformation_layer_timestamp", "target_layer", "transformation_timestamp"),
        {"schema": "metadata"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_layer: Mapped[str] = mapped_column(String(20), nullable=False)  # bronze, silver
    target_layer: Mapped[str] = mapped_column(String(20), nullable=False)  # silver, gold
    transformation_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # cleaning, chain_linking
    transformation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, partial, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ChainLinkingLog(Base):
    """Metadata: Audit log for chain-linking operations."""

    __tablename__ = "chain_linking_log"
    __table_args__ = (
        Index("idx_chain_linking_indicator_timestamp", "indicator_id", "linking_timestamp"),
        {"schema": "metadata"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    indicator_id: Mapped[str] = mapped_column(String(100), nullable=False)
    linking_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    base_year_from: Mapped[int] = mapped_column(Integer, nullable=False)
    base_year_to: Mapped[int] = mapped_column(Integer, nullable=False)
    linking_method: Mapped[str] = mapped_column(String(50), nullable=False)  # splice, overlap
    records_linked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overlap_period_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    growth_rate_variance: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, partial, failed
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
