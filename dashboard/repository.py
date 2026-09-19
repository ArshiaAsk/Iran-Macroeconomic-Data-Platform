"""Read-only database repository for the Streamlit dashboard."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import Integer, and_, asc, func, or_, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import ColumnElement

from src.database.schema import DataCollectionLog, GoldAnalytical, IndicatorCatalog

#: ``series_kind`` values. ``base`` is a level series; ``derived`` is a
#: platform-computed series carrying ``record_metadata["derived_from"]``.
SERIES_KIND_BASE = "base"
SERIES_KIND_DERIVED = "derived"

#: Columns resolved from the catalog: the observation's own row when it exists,
#: otherwise the parent catalog row named by ``derived_from``.
_CATALOG_RESOLVED_COLUMNS = ("name", "source_name", "source_url")

#: Extra frame columns produced by :meth:`DashboardRepository.load_series`.
SERIES_CLASSIFICATION_COLUMNS = ("series_kind", "derived_from", "has_catalog_metadata")

#: Columns produced by :meth:`DashboardRepository.series_inventory`.
SERIES_INVENTORY_COLUMNS = (
    "indicator_id",
    "derived_from",
    "series_kind",
    "has_catalog_metadata",
)


def _derived_from(record_metadata: object) -> str | None:
    """Return the parent indicator id recorded in Gold metadata, else ``None``.

    Derivedness is read from the ETL-written ``record_metadata["derived_from"]``
    key only; indicator ids are never parsed. A missing, non-mapping, non-string
    or blank value is not a usable parent reference, so the row stays a base
    series and no parent catalog row is attached to it.

    Examples:
        >>> _derived_from({"derived_from": "WB.NY.GDP.MKTP.CD"})
        'WB.NY.GDP.MKTP.CD'
        >>> _derived_from({"method": "yoy_growth"}) is None
        True
        >>> _derived_from(None) is None
        True
    """
    if not isinstance(record_metadata, Mapping):
        return None
    return _parent_id(record_metadata.get("derived_from"))


def _parent_id(value: object) -> str | None:
    """Return a usable parent indicator id from a raw ``derived_from`` value.

    Used both for the JSONB mapping (via :func:`_derived_from`) and for the
    already-extracted ``->> 'derived_from'`` text column of ``series_inventory``;
    a missing, non-string or blank value is not a usable parent reference.
    """
    if not isinstance(value, str):
        return None
    return value.strip() or None


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
        """Return Gold observations without interpolation or frequency conversion.

        The query is driven by Gold and LEFT JOINs ``indicator_catalog`` twice:
        once for the observation's own catalog row and once for the parent named
        by ``record_metadata["derived_from"]``. Derived Gold series therefore stay
        visible even though ``connector.discover()`` never emits a catalog row for
        them, and they inherit their parent's ``name``/``source_name``/
        ``source_url``. A genuinely orphan series (no catalog row and no resolvable
        parent) keeps ``NULL`` provenance and is flagged by
        ``has_catalog_metadata`` instead of being dropped or given a guessed
        source.

        Added columns, all derived from Gold metadata rather than from ids:

        ``series_kind``
            ``derived`` when ``record_metadata["derived_from"]`` is a usable
            parent id, otherwise ``base``.
        ``derived_from``
            The parent indicator id recorded in Gold metadata, else ``None``.
        ``has_catalog_metadata``
            Whether the observation's own indicator id has a catalog row.

        Existing columns keep their names and ordering semantics: rows are
        returned in the requested indicator order, then by ascending timestamp.
        """
        if not indicator_ids:
            return self._empty_series()
        conditions: list[ColumnElement[bool]] = [GoldAnalytical.indicator_id.in_(indicator_ids)]
        if start_date is not None:
            conditions.append(GoldAnalytical.timestamp >= start_date)
        if end_date is not None:
            conditions.append(GoldAnalytical.timestamp <= end_date)

        catalog = aliased(IndicatorCatalog, name="catalog")
        parent_catalog = aliased(IndicatorCatalog, name="parent_catalog")
        derived_from = GoldAnalytical.record_metadata["derived_from"].astext

        statement = (
            select(
                GoldAnalytical.indicator_id,
                catalog.name,
                GoldAnalytical.timestamp,
                GoldAnalytical.value,
                GoldAnalytical.original_value,
                GoldAnalytical.is_chain_linked,
                GoldAnalytical.chain_linking_confidence,
                GoldAnalytical.unit,
                GoldAnalytical.frequency,
                GoldAnalytical.domain,
                catalog.source_name,
                catalog.source_url,
                GoldAnalytical.record_metadata,
                catalog.indicator_id.label("catalog_indicator_id"),
                parent_catalog.name.label("parent_name"),
                parent_catalog.source_name.label("parent_source_name"),
                parent_catalog.source_url.label("parent_source_url"),
            )
            .join(
                catalog,
                catalog.indicator_id == GoldAnalytical.indicator_id,
                isouter=True,
            )
            .join(parent_catalog, parent_catalog.indicator_id == derived_from, isouter=True)
            .where(and_(*conditions))
            .order_by(asc(GoldAnalytical.timestamp), asc(GoldAnalytical.indicator_id))
        )
        frame = self._resolve_provenance(
            self._frame(self.session.execute(statement).mappings().all())
        )
        if frame.empty:
            return self._empty_series()
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

    def list_derived_ids(self, parent_ids: list[str]) -> list[str]:
        """Return the derived Gold ids whose parent is in ``parent_ids``.

        Derived series are discovered from Gold's ``record_metadata``
        (``derived_from``), never from a catalog row, an id pattern or a
        hardcoded list, so a new derivation strategy becomes visible without a
        dashboard change. The result is sorted and de-duplicated by the database.
        """
        if not parent_ids:
            return []
        derived_from = GoldAnalytical.record_metadata["derived_from"].astext
        statement = (
            select(GoldAnalytical.indicator_id)
            .where(derived_from.in_(parent_ids))
            .distinct()
            .order_by(asc(GoldAnalytical.indicator_id))
        )
        rows = self.session.execute(statement).mappings().all()
        return [str(row["indicator_id"]) for row in rows]

    def series_inventory(self) -> pd.DataFrame:
        """Classify every distinct Gold indicator id, catalog row or not.

        One row per distinct Gold ``indicator_id`` carrying the same
        metadata-driven classification as :meth:`load_series` --
        ``series_kind`` from ``record_metadata["derived_from"]`` and
        ``has_catalog_metadata`` from whether the id has a catalog row -- so the
        Overview can count the derived and orphan series that never appear in the
        catalog (``connector.discover()`` never emits a derived id). Derivedness is
        never inferred from an id shape.
        """
        catalog = aliased(IndicatorCatalog, name="catalog")
        derived_from = GoldAnalytical.record_metadata["derived_from"].astext
        statement = (
            select(
                GoldAnalytical.indicator_id,
                derived_from.label("derived_from"),
                catalog.indicator_id.label("catalog_indicator_id"),
            )
            .join(catalog, catalog.indicator_id == GoldAnalytical.indicator_id, isouter=True)
            .distinct()
            .order_by(asc(GoldAnalytical.indicator_id))
        )
        frame = self._frame(self.session.execute(statement).mappings().all())
        if frame.empty:
            return self._empty_inventory()
        parents = frame["derived_from"].map(_parent_id)
        frame["derived_from"] = parents
        frame["series_kind"] = [
            SERIES_KIND_DERIVED if parent else SERIES_KIND_BASE for parent in parents
        ]
        frame["has_catalog_metadata"] = frame["catalog_indicator_id"].notna()
        return frame.drop(columns="catalog_indicator_id").reset_index(drop=True)

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
    def _resolve_provenance(frame: pd.DataFrame) -> pd.DataFrame:
        """Classify each Gold row and fill catalog provenance from its parent.

        The query returns the observation's own catalog fields plus the parent
        catalog fields as ``parent_*``; those parent columns are only folded in
        when the observation has no catalog row of its own, and are then dropped
        so the frame contract stays stable. ``has_catalog_metadata`` records
        whether the fold happened, i.e. whether the series is a genuine orphan.
        """
        if frame.empty:
            return frame
        resolved = frame.copy()
        derived_from = resolved["record_metadata"].map(_derived_from)
        resolved["series_kind"] = [
            SERIES_KIND_DERIVED if parent else SERIES_KIND_BASE for parent in derived_from
        ]
        resolved["derived_from"] = derived_from
        resolved["has_catalog_metadata"] = resolved["catalog_indicator_id"].notna()
        for column in _CATALOG_RESOLVED_COLUMNS:
            resolved[column] = resolved[column].where(
                resolved[column].notna(), resolved[f"parent_{column}"]
            )
        helper_columns = [
            "catalog_indicator_id",
            *[f"parent_{c}" for c in _CATALOG_RESOLVED_COLUMNS],
        ]
        return resolved.drop(columns=helper_columns)

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
                *SERIES_CLASSIFICATION_COLUMNS,
            ]
        )

    @staticmethod
    def _empty_inventory() -> pd.DataFrame:
        return pd.DataFrame(columns=list(SERIES_INVENTORY_COLUMNS))
