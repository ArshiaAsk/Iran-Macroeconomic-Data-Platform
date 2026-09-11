"""Read-only database repository for the Streamlit dashboard."""

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import Integer, and_, asc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from src.database.schema import DataCollectionLog, GoldAnalytical, IndicatorCatalog


class DashboardRepository:
    """Provides typed, read-only queries over catalog and Gold data."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_indicators(
        self,
        search: str | None = None,
        domains: list[str] | None = None,
        frequencies: list[str] | None = None,
        sources: list[str] | None = None,
        active_only: bool = True,
    ) -> pd.DataFrame:
        """Return catalog indicators matching the supplied filters."""
        conditions: list[ColumnElement[bool]] = []
        if search:
            needle = f"%{search.strip()}%"
            conditions.append(
                or_(
                    IndicatorCatalog.indicator_id.ilike(needle),
                    IndicatorCatalog.name.ilike(needle),
                    IndicatorCatalog.description.ilike(needle),
                )
            )
        if domains:
            conditions.append(IndicatorCatalog.domain.in_(domains))
        if frequencies:
            conditions.append(IndicatorCatalog.frequency.in_(frequencies))
        if sources:
            conditions.append(IndicatorCatalog.source_name.in_(sources))
        if active_only:
            conditions.append(IndicatorCatalog.is_active.is_(True))

        statement = (
            select(
                IndicatorCatalog.indicator_id,
                IndicatorCatalog.name,
                IndicatorCatalog.description,
                IndicatorCatalog.unit,
                IndicatorCatalog.frequency,
                IndicatorCatalog.domain,
                IndicatorCatalog.source_name,
                IndicatorCatalog.source_url,
                IndicatorCatalog.availability_start,
                IndicatorCatalog.availability_end,
                IndicatorCatalog.has_base_year_changes,
                IndicatorCatalog.base_years,
                IndicatorCatalog.is_active,
            )
            .where(and_(*conditions))
            .order_by(asc(IndicatorCatalog.domain), asc(IndicatorCatalog.name))
        )
        rows = self.session.execute(statement).mappings().all()
        return self._frame(rows)

    def load_series(
        self,
        indicator_ids: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Return Gold observations without interpolation or frequency conversion."""
        if not indicator_ids:
            return self._empty_series()
        conditions: list[ColumnElement[bool]] = [GoldAnalytical.indicator_id.in_(indicator_ids)]
        if start_date is not None:
            conditions.append(GoldAnalytical.timestamp >= start_date)
        if end_date is not None:
            conditions.append(GoldAnalytical.timestamp <= end_date)

        statement = (
            select(
                GoldAnalytical.indicator_id,
                IndicatorCatalog.name,
                GoldAnalytical.timestamp,
                GoldAnalytical.value,
                GoldAnalytical.original_value,
                GoldAnalytical.is_chain_linked,
                GoldAnalytical.chain_linking_confidence,
                GoldAnalytical.unit,
                GoldAnalytical.frequency,
                GoldAnalytical.domain,
                IndicatorCatalog.source_name,
                IndicatorCatalog.source_url,
                GoldAnalytical.record_metadata,
            )
            .join(
                IndicatorCatalog,
                IndicatorCatalog.indicator_id == GoldAnalytical.indicator_id,
            )
            .where(and_(*conditions))
            .order_by(asc(GoldAnalytical.timestamp), asc(GoldAnalytical.indicator_id))
        )
        frame = self._frame(self.session.execute(statement).mappings().all())
        if frame.empty:
            return frame
        order = pd.Categorical(frame["indicator_id"], categories=indicator_ids, ordered=True)
        frame["_indicator_order"] = order
        frame = frame.sort_values(["_indicator_order", "timestamp"], kind="stable")
        return frame.drop(columns="_indicator_order").reset_index(drop=True)

    def coverage_summary(self, indicator_ids: list[str] | None = None) -> pd.DataFrame:
        """Return observed coverage and observation counts for indicators."""
        conditions: list[ColumnElement[bool]] = []
        if indicator_ids:
            conditions.append(GoldAnalytical.indicator_id.in_(indicator_ids))
        statement = (
            select(
                GoldAnalytical.indicator_id,
                func.min(GoldAnalytical.timestamp).label("observed_start"),
                func.max(GoldAnalytical.timestamp).label("observed_end"),
                func.count().label("observation_count"),
                func.sum(GoldAnalytical.is_chain_linked.cast(Integer)).label("chain_linked_count"),
                func.avg(GoldAnalytical.chain_linking_confidence).label("confidence"),
            )
            .where(and_(*conditions))
            .group_by(GoldAnalytical.indicator_id)
        )
        observed = self._frame(self.session.execute(statement).mappings().all())
        catalog_conditions: list[ColumnElement[bool]] = []
        if indicator_ids:
            catalog_conditions.append(IndicatorCatalog.indicator_id.in_(indicator_ids))
        catalog_statement = select(
            IndicatorCatalog.indicator_id,
            IndicatorCatalog.name,
            IndicatorCatalog.unit,
            IndicatorCatalog.frequency,
            IndicatorCatalog.domain,
            IndicatorCatalog.source_name,
            IndicatorCatalog.availability_start,
            IndicatorCatalog.availability_end,
        ).where(and_(*catalog_conditions))
        catalog = self._frame(self.session.execute(catalog_statement).mappings().all())
        if catalog.empty:
            return observed
        return catalog.merge(observed, on="indicator_id", how="left")

    def source_freshness(self) -> pd.DataFrame:
        """Return the latest collection result for each source."""
        ranked = select(
            DataCollectionLog.source_name,
            DataCollectionLog.collection_timestamp,
            DataCollectionLog.status,
            DataCollectionLog.records_collected,
            DataCollectionLog.error_message,
            func.row_number()
            .over(
                partition_by=DataCollectionLog.source_name,
                order_by=DataCollectionLog.collection_timestamp.desc(),
            )
            .label("row_number"),
        ).subquery()
        columns = ranked.c
        statement = (
            select(
                columns.source_name,
                columns.collection_timestamp,
                columns.status,
                columns.records_collected,
                columns.error_message,
            )
            .where(columns.row_number == 1)
            .order_by(asc(columns.source_name))
        )
        return self._frame(self.session.execute(statement).mappings().all())

    def available_domains(self) -> pd.DataFrame:
        """Return active domains and their active indicator counts."""
        statement = (
            select(
                IndicatorCatalog.domain,
                func.count().label("indicator_count"),
            )
            .where(IndicatorCatalog.is_active.is_(True))
            .group_by(IndicatorCatalog.domain)
            .order_by(asc(IndicatorCatalog.domain))
        )
        return self._frame(self.session.execute(statement).mappings().all())

    @staticmethod
    def _frame(rows: Any) -> pd.DataFrame:
        return pd.DataFrame([dict(row) for row in rows])

    @staticmethod
    def _empty_series() -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "indicator_id",
                "name",
                "timestamp",
                "value",
                "original_value",
                "is_chain_linked",
                "chain_linking_confidence",
                "unit",
                "frequency",
                "domain",
                "source_name",
                "source_url",
                "record_metadata",
            ]
        )
