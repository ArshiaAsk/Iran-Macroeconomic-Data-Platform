"""
Unit tests for the Silver -> Gold transformation.

Gold is where provenance has to hold up: every published number keeps the value
the source actually reported, and only rows that were genuinely rescaled claim
to be chain-linked. The synthetic series used here has a *known* rebase -- a
factor of exactly 2.0 applied from 2005 -- so the recovered scale factor and the
preserved growth rates can be asserted rather than inspected.

Persistence goes through :class:`tests.conftest.FakeSession`; the real
delete-and-reinsert against the hypertable is covered by the integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
import pytest

from src.chain_linking.splice import (
    CONFIDENCE_OVERLAP_FLOOR,
    DETECTED_BY_METADATA,
    LINKING_METHOD_LEVEL_SHIFT,
    ChainLinkResult,
)
from src.database.schema import (
    ChainLinkingLog,
    GoldAnalytical,
    IndicatorCatalog,
    SilverCleaned,
    TransformationLog,
)
from src.etl.gold import (
    DEFAULT_DOMAIN,
    DERIVED_MA30_METHOD,
    DERIVED_METHOD,
    DERIVED_RET1D_METHOD,
    DERIVED_YOY_UNIT,
    BaseYearSegment,
    _resolve_domain,
    _write_chain_linking_log,
    base_year_from_indicator_id,
    derived_growth_indicator_id,
    derived_ma30_indicator_id,
    derived_ret1d_indicator_id,
    gold_indicator_ids,
    load_base_year_segments,
    load_gold_series,
    order_base_year_segments,
    silver_to_gold,
)
from src.etl.lineage import LAYER_GOLD, LAYER_SILVER, STATUS_SUCCESS
from src.etl.silver import SilverSeries
from src.utils.exceptions import ChainLinkingError
from src.utils.periods import month_period_end
from tests.conftest import FakeSession, compiled_sql

GDP = "NY.GDP.MKTP.CD"
GDP_YOY = "WB.NY.GDP.MKTP.CD.YOY"
BRONZE_ID = UUID("11111111-1111-1111-1111-111111111111")

UNIT = "current US$"
FREQUENCY = "annual"

# A 5%-a-year series, rebased from 2005 onto a base exactly twice as high.
GROWTH_RATE = 1.05
REBASE_FACTOR = 2.0
REBASE_YEAR = 2005
FIRST_YEAR = 2000
SERIES_YEARS = 10
# 1.05 * 2.0: the junction ratio folds one year of real growth into the rebase.
EXPECTED_SCALE = GROWTH_RATE * REBASE_FACTOR
YEARS_ON_OLD_BASE = REBASE_YEAR - FIRST_YEAR
ANNUAL_PERCENT = 5.0


def true_levels() -> list[float]:
    """The underlying series, before any rebasing."""
    return [100.0 * GROWTH_RATE**offset for offset in range(SERIES_YEARS)]


def rebased_levels() -> list[float]:
    """What the source publishes: old base to 2004, new base from 2005."""
    levels = true_levels()
    return [
        *levels[:YEARS_ON_OLD_BASE],
        *[value * REBASE_FACTOR for value in levels[YEARS_ON_OLD_BASE:]],
    ]


def seed_silver(
    session: FakeSession,
    values: list[float],
    indicator_id: str = GDP,
    start_year: int = FIRST_YEAR,
) -> list[SilverCleaned]:
    """Put an annual Silver history into the session and return its rows."""
    rows: list[SilverCleaned] = []
    for offset, value in enumerate(values):
        row = SilverCleaned(
            indicator_id=indicator_id,
            timestamp=datetime(start_year + offset, 12, 31, tzinfo=UTC),
            value=value,
            unit=UNIT,
            frequency=FREQUENCY,
            source_name="world_bank",
            bronze_id=BRONZE_ID,
        )
        row.id = uuid4()
        rows.append(row)
    session.seed(SilverCleaned, rows)
    return rows


def published(session: FakeSession, indicator_id: str) -> list[dict[str, Any]]:
    """Gold rows submitted for one indicator id, in insertion order."""
    return [
        record
        for record in session.inserted(GoldAnalytical)
        if record["indicator_id"] == indicator_id
    ]


def derived_daily(session: FakeSession, suffix: str) -> list[dict[str, Any]]:
    """Gold rows submitted for one daily derived series, in insertion order."""
    return [
        record
        for record in session.inserted(GoldAnalytical)
        if record["indicator_id"].endswith(f".{suffix}")
    ]


def catalog_entry(domain: str, base_years: list[int] | None = None) -> IndicatorCatalog:
    """A seeded catalog row for the indicator under test."""
    return IndicatorCatalog(
        indicator_id=GDP,
        name="GDP (current US$)",
        frequency=FREQUENCY,
        domain=domain,
        source_name="world_bank",
        base_years=base_years,
    )


# ------------------------------------------------------------- derived naming


def test_derived_growth_indicator_id_is_namespaced() -> None:
    """``WB.`` prefixing means a derived series can never collide with a source code."""
    assert derived_growth_indicator_id(GDP) == GDP_YOY


def test_daily_derived_ids_do_not_double_prefix_a_namespaced_source() -> None:
    """A ``TGJU.`` source id already carries its namespace; do not add it twice."""
    assert derived_ret1d_indicator_id("TGJU.USD.FREE", "TGJU") == "TGJU.USD.FREE.RET1D"
    assert derived_ma30_indicator_id("TGJU.USD.FREE", "TGJU") == "TGJU.USD.FREE.MA30"


def test_growth_derived_id_is_idempotent_about_its_namespace() -> None:
    """A pre-namespaced source id is not prefixed a second time."""
    assert derived_growth_indicator_id("IMF.NGDPD", "IMF") == "IMF.NGDPD.YOY"
    assert derived_growth_indicator_id("NGDPD", "IMF") == "IMF.NGDPD.YOY"


def test_gold_indicator_ids_covers_both_published_series() -> None:
    """Callers need both ids to clear an indicator out of Gold."""
    assert gold_indicator_ids(GDP) == (GDP, GDP_YOY)


# ------------------------------------------------------------ domain tagging


def test_resolve_domain_prefers_an_explicit_domain() -> None:
    """An explicit argument outranks the catalog, which may be stale."""
    assert _resolve_domain(catalog_entry("gdp"), GDP, "trade") == "trade"


def test_resolve_domain_falls_back_to_the_catalog() -> None:
    """Without an argument, the seeded catalog decides."""
    assert _resolve_domain(catalog_entry("gdp"), GDP, None) == "gdp"


def test_resolve_domain_labels_an_unknown_indicator_unclassified() -> None:
    """An unclassifiable indicator is labelled as such, never guessed at."""
    assert _resolve_domain(None, "NOT.A.REAL.CODE", None) == DEFAULT_DOMAIN


def test_silver_to_gold_tags_rows_from_the_catalog_domain(fake_session: FakeSession) -> None:
    """The resolved domain reaches every published row, derived ones included."""
    seed_silver(fake_session, [100.0, 105.0, 110.25])
    fake_session.seed(IndicatorCatalog, [catalog_entry("gdp")], primary_key="indicator_id")

    result = silver_to_gold(fake_session, GDP)  # type: ignore[arg-type]

    assert result.details["domain"] == "gdp"
    assert {record["domain"] for record in fake_session.inserted(GoldAnalytical)} == {"gdp"}


# --------------------------------------------------------------- level rows


def test_silver_to_gold_publishes_a_level_row_per_observation(fake_session: FakeSession) -> None:
    """A series with no rebase passes through untouched -- but fully attributed."""
    rows = seed_silver(fake_session, [100.0, 105.0, 110.25])

    result = silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    levels = published(fake_session, GDP)
    assert len(levels) == len(rows)
    assert [record["value"] for record in levels] == [100.0, 105.0, 110.25]
    # original_value is populated whether or not a link happened, so any
    # published number can be traced back to what the source said.
    assert [record["original_value"] for record in levels] == [100.0, 105.0, 110.25]
    assert {record["unit"] for record in levels} == {UNIT}
    assert {record["frequency"] for record in levels} == {FREQUENCY}
    assert result.records_processed == len(rows)
    assert result.records_failed == 0


def test_level_rows_carry_the_silver_lineage_pointer(fake_session: FakeSession) -> None:
    """``silver_id`` is NOT NULL: every Gold row names the observation behind it."""
    rows = seed_silver(fake_session, [100.0, 105.0, 110.25])

    silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    levels = published(fake_session, GDP)
    assert [record["silver_id"] for record in levels] == [row.id for row in rows]


def test_unlinked_rows_claim_no_confidence(fake_session: FakeSession) -> None:
    """No break means no link: a fabricated score would look like verification."""
    seed_silver(fake_session, [100.0, 105.0, 110.25])

    result = silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    levels = published(fake_session, GDP)
    assert [record["is_chain_linked"] for record in levels] == [False, False, False]
    assert {record["chain_linking_confidence"] for record in levels} == {None}
    assert {record["record_metadata"] for record in levels} == {None}
    assert result.details["is_chain_linked"] is False
    assert result.details["linking_method"] is None


def test_silver_to_gold_rescales_only_the_older_base_years(fake_session: FakeSession) -> None:
    """The known 2.0 rebase is recovered as 2.1 -- the ratio at the junction."""
    seed_silver(fake_session, rebased_levels())

    result = silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        base_years=[FIRST_YEAR, REBASE_YEAR],
    )

    levels = published(fake_session, GDP)
    linked = [record for record in levels if record["is_chain_linked"]]
    assert len(linked) == YEARS_ON_OLD_BASE
    assert {record["timestamp"].year for record in linked} == set(range(FIRST_YEAR, REBASE_YEAR))
    assert [record["value"] for record in linked] == pytest.approx(
        [value * EXPECTED_SCALE for value in true_levels()[:YEARS_ON_OLD_BASE]]
    )
    # The pre-link level survives alongside the rescaled one.
    assert [record["original_value"] for record in linked] == pytest.approx(
        true_levels()[:YEARS_ON_OLD_BASE]
    )
    assert result.details["records_linked"] == YEARS_ON_OLD_BASE


def test_linked_rows_record_how_they_were_rescaled(fake_session: FakeSession) -> None:
    """The scale factor and the base years it bridges travel with the row."""
    seed_silver(fake_session, rebased_levels())

    silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        base_years=[FIRST_YEAR, REBASE_YEAR],
    )

    first = published(fake_session, GDP)[0]
    assert first["chain_linking_confidence"] == CONFIDENCE_OVERLAP_FLOOR
    assert first["record_metadata"]["linking_method"] == LINKING_METHOD_LEVEL_SHIFT
    assert first["record_metadata"]["scale_factor"] == pytest.approx(EXPECTED_SCALE)
    assert first["record_metadata"]["base_year_from"] == FIRST_YEAR
    assert first["record_metadata"]["base_year_to"] == REBASE_YEAR


def test_rows_already_on_the_current_base_are_not_marked(fake_session: FakeSession) -> None:
    """Only rescaled observations are flagged; the newest base was left alone."""
    seed_silver(fake_session, rebased_levels())

    silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        base_years=[FIRST_YEAR, REBASE_YEAR],
    )

    current_base = [
        record for record in published(fake_session, GDP) if record["timestamp"].year >= REBASE_YEAR
    ]
    assert len(current_base) == SERIES_YEARS - YEARS_ON_OLD_BASE
    assert not any(record["is_chain_linked"] for record in current_base)
    assert {record["chain_linking_confidence"] for record in current_base} == {None}


# -------------------------------------------------------------- growth rows


def test_silver_to_gold_derives_a_year_over_year_series(fake_session: FakeSession) -> None:
    """Growth is published as its own namespaced series, one rate per gap."""
    rows = seed_silver(fake_session, true_levels())

    result = silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    growth = published(fake_session, GDP_YOY)
    assert len(growth) == len(rows) - 1
    assert {record["unit"] for record in growth} == {DERIVED_YOY_UNIT}
    assert {record["frequency"] for record in growth} == {FREQUENCY}
    assert [record["value"] for record in growth] == pytest.approx(
        [ANNUAL_PERCENT] * (len(rows) - 1)
    )
    assert result.details["growth_rows"] == len(rows) - 1
    assert result.details["level_rows"] == len(rows)


def test_growth_rows_attribute_the_rate_to_the_later_period(fake_session: FakeSession) -> None:
    """``silver_id`` is NOT NULL, so a rate is booked to the period completing it."""
    rows = seed_silver(fake_session, true_levels())

    silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    growth = published(fake_session, GDP_YOY)
    assert all(record["silver_id"] is not None for record in growth)
    assert [record["silver_id"] for record in growth] == [row.id for row in rows[1:]]
    assert growth[0]["timestamp"] == datetime(FIRST_YEAR + 1, 12, 31, tzinfo=UTC)
    assert growth[0]["record_metadata"]["from_period"] == f"{FIRST_YEAR}-12-31"
    assert growth[0]["record_metadata"]["to_period"] == f"{FIRST_YEAR + 1}-12-31"
    assert growth[0]["record_metadata"]["derived_from"] == GDP
    assert growth[0]["record_metadata"]["method"] == DERIVED_METHOD


def test_growth_survives_chain_linking_unchanged(fake_session: FakeSession) -> None:
    """The point of linking: away from the junction, rates are the real 5%."""
    seed_silver(fake_session, rebased_levels())

    silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        base_years=[FIRST_YEAR, REBASE_YEAR],
    )

    growth = published(fake_session, GDP_YOY)
    away_from_junction = [
        record["value"] for record in growth if record["timestamp"].year != REBASE_YEAR
    ]
    assert away_from_junction == pytest.approx([ANNUAL_PERCENT] * len(away_from_junction))


def test_growth_rows_withhold_the_junction_rate_they_cannot_know(
    fake_session: FakeSession,
) -> None:
    """Across a rebase the unlinked rate is meaningless, so it is left NULL."""
    seed_silver(fake_session, rebased_levels())

    silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        base_years=[FIRST_YEAR, REBASE_YEAR],
    )

    growth = published(fake_session, GDP_YOY)
    junction = next(record for record in growth if record["timestamp"].year == REBASE_YEAR)
    assert junction["original_value"] is None
    assert junction["record_metadata"]["spans_base_year_break"] is True
    assert [
        record["record_metadata"]["spans_base_year_break"]
        for record in growth
        if record["timestamp"].year != REBASE_YEAR
    ] == [False] * (len(growth) - 1)
    # Elsewhere the unlinked rate is real and is kept for comparison.
    assert all(
        record["original_value"] is not None
        for record in growth
        if record["timestamp"].year != REBASE_YEAR
    )


def test_growth_rows_score_confidence_per_row(fake_session: FakeSession) -> None:
    """A rate computed wholly on the current base was never linked, so scores NULL."""
    seed_silver(fake_session, rebased_levels())

    silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        base_years=[FIRST_YEAR, REBASE_YEAR],
    )

    growth = published(fake_session, GDP_YOY)
    scored = {
        record["timestamp"].year: record["chain_linking_confidence"]
        for record in growth
        if record["is_chain_linked"]
    }
    unscored = [
        record["chain_linking_confidence"] for record in growth if not record["is_chain_linked"]
    ]
    # 2001-2004 span a rescaled period; 2005 spans the junction itself.
    assert set(scored) == set(range(FIRST_YEAR + 1, REBASE_YEAR + 1))
    assert set(scored.values()) == {CONFIDENCE_OVERLAP_FLOOR}
    assert unscored == [None] * len(unscored)


def test_silver_to_gold_can_publish_levels_only(fake_session: FakeSession) -> None:
    """Growth derivation is opt-out for callers that only want the level series."""
    rows = seed_silver(fake_session, true_levels())

    result = silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        include_growth=False,
    )

    assert published(fake_session, GDP_YOY) == []
    assert result.records_written == len(rows)
    assert result.details["growth_rows"] == 0


# ------------------------------------------------------------- periodic growth


def seed_periodic_silver(
    session: FakeSession,
    indicator_id: str,
    timestamps: list[datetime],
    values: list[float],
    frequency: str,
) -> None:
    """Seed a non-annual series whose timestamps are already period ends."""
    rows: list[SilverCleaned] = []
    for timestamp, value in zip(timestamps, values, strict=True):
        row = SilverCleaned(
            indicator_id=indicator_id,
            timestamp=timestamp,
            value=value,
            unit="index",
            frequency=frequency,
            source_name="test",
            bronze_id=BRONZE_ID,
        )
        row.id = uuid4()
        rows.append(row)
    session.seed(SilverCleaned, rows)


def test_monthly_yoy_compares_the_same_month_one_year_earlier(
    fake_session: FakeSession,
) -> None:
    """A positional lag would publish MoM as YoY on monthly series."""
    indicator_id = "TEST.MONTHLY"
    months = [(2024, month) for month in range(1, 13)] + [(2025, month) for month in range(1, 7)]
    timestamps = [month_period_end(year, month) for year, month in months]
    values = [100.0 + 10 * offset for offset in range(len(months))]
    seed_periodic_silver(fake_session, indicator_id, timestamps, values, "monthly")

    silver_to_gold(fake_session, indicator_id, domain="test", derived_prefix="TEST")

    growth = published(fake_session, f"{indicator_id}.YOY")
    assert len(growth) == 6  # only the 2025 months have a prior-year period
    assert [record["timestamp"] for record in growth] == timestamps[12:]
    first = growth[0]
    assert first["timestamp"] == datetime(2025, 1, 31, tzinfo=UTC)
    assert first["value"] == pytest.approx((220.0 / 100.0 - 1) * 100)
    assert first["frequency"] == "monthly"


def test_monthly_yoy_withholds_a_rate_when_the_prior_year_is_missing(
    fake_session: FakeSession,
) -> None:
    """No prior-year period means no rate -- and the next month still aligns."""
    indicator_id = "TEST.GAPPY"
    full_months = [(2024, month) for month in range(1, 13)] + [
        (2025, month) for month in range(1, 8)
    ]
    values_by_month = {
        year_month: 100.0 + 10 * offset for offset, year_month in enumerate(full_months)
    }
    months = [year_month for year_month in full_months if year_month != (2024, 6)]
    timestamps = [month_period_end(year, month) for year, month in months]
    values = [values_by_month[year_month] for year_month in months]
    seed_periodic_silver(fake_session, indicator_id, timestamps, values, "monthly")

    silver_to_gold(fake_session, indicator_id, domain="test", derived_prefix="TEST")

    growth = {
        record["timestamp"]: record for record in published(fake_session, f"{indicator_id}.YOY")
    }
    assert datetime(2025, 6, 30, tzinfo=UTC) not in growth
    july = growth[datetime(2025, 7, 31, tzinfo=UTC)]
    assert july["record_metadata"]["from_period"] == "2024-07-31"


def test_quarterly_yoy_compares_the_same_quarter_one_year_earlier(
    fake_session: FakeSession,
) -> None:
    """Quarterly period ends are month ends; the same alignment applies."""
    indicator_id = "TEST.QUARTERLY"
    quarters = [
        (2023, 3),
        (2023, 6),
        (2023, 9),
        (2023, 12),
        (2024, 3),
        (2024, 6),
        (2024, 9),
        (2024, 12),
    ]
    timestamps = [month_period_end(year, month) for year, month in quarters]
    values = [100.0 + 10 * offset for offset in range(len(quarters))]
    seed_periodic_silver(fake_session, indicator_id, timestamps, values, "quarterly")

    silver_to_gold(fake_session, indicator_id, domain="test", derived_prefix="TEST")

    growth = published(fake_session, f"{indicator_id}.YOY")
    assert len(growth) == 4
    assert growth[0]["timestamp"] == datetime(2024, 3, 31, tzinfo=UTC)
    assert growth[0]["value"] == pytest.approx((140.0 / 100.0 - 1) * 100)
    assert growth[0]["frequency"] == "quarterly"


# ------------------------------------------------------- refresh & audit rows


def test_silver_to_gold_deletes_both_series_before_reinserting(
    fake_session: FakeSession,
) -> None:
    """Gold is a refresh: the hypertable's composite key rules out an upsert."""
    seed_silver(fake_session, true_levels())

    silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    assert fake_session.statement_kinds(GoldAnalytical) == ["delete", "insert"]
    statement, _ = fake_session.executed[0]
    assert "DELETE FROM gold.gold_analytical" in compiled_sql(statement)
    # Both the level series and its derived rows are cleared, or the derived
    # rows would survive as orphans after a re-run.
    bound = statement.compile().params
    assert set(next(iter(bound.values()))) == {GDP, GDP_YOY}


def test_silver_to_gold_writes_a_transformation_log(fake_session: FakeSession) -> None:
    """Lineage: one audit row per hop, carrying the counts it produced."""
    rows = seed_silver(fake_session, true_levels())

    result = silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    logs = fake_session.added_of(TransformationLog)
    assert len(logs) == 1
    assert logs[0].source_layer == LAYER_SILVER
    assert logs[0].target_layer == LAYER_GOLD
    assert logs[0].status == STATUS_SUCCESS
    assert logs[0].records_processed == len(rows)
    assert logs[0].record_metadata["level_rows"] == len(rows)
    assert logs[0].record_metadata["growth_rows"] == len(rows) - 1
    assert logs[0].record_metadata["idempotency"].startswith("delete-and-reinsert")
    assert result.log_id == logs[0].id


def test_silver_to_gold_writes_a_chain_linking_log(fake_session: FakeSession) -> None:
    """A performed link is auditable: the break, its ratio, and how it was found."""
    seed_silver(fake_session, rebased_levels())

    silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        GDP,
        domain="gdp",
        base_years=[FIRST_YEAR, REBASE_YEAR],
    )

    logs = fake_session.added_of(ChainLinkingLog)
    assert len(logs) == 1
    assert logs[0].indicator_id == GDP
    assert logs[0].base_year_from == FIRST_YEAR
    assert logs[0].base_year_to == REBASE_YEAR
    assert logs[0].records_linked == YEARS_ON_OLD_BASE
    assert logs[0].avg_confidence_score == CONFIDENCE_OVERLAP_FLOOR
    assert logs[0].status == STATUS_SUCCESS
    # ``linking_method`` names the splice mechanism; ``detected_by`` records that
    # the catalog -- not a statistical guess -- located the break.
    assert logs[0].linking_method == LINKING_METHOD_LEVEL_SHIFT
    assert logs[0].record_metadata["breaks"] == [
        {
            "timestamp": f"{REBASE_YEAR}-12-31",
            "base_year_from": FIRST_YEAR,
            "base_year_to": REBASE_YEAR,
            "detected_by": DETECTED_BY_METADATA,
            "level_ratio": pytest.approx(EXPECTED_SCALE),
        }
    ]


def test_silver_to_gold_writes_no_chain_linking_log_when_nothing_linked(
    fake_session: FakeSession,
) -> None:
    """A log row for an unperformed link would imply a correction that never happened."""
    seed_silver(fake_session, true_levels())

    silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    assert fake_session.added_of(ChainLinkingLog) == []


def test_chain_linking_log_skipped_when_base_years_are_unidentifiable(
    fake_session: FakeSession,
) -> None:
    """``base_year_from`` is NOT NULL, so an unattributable link is logged, not stored."""
    result = ChainLinkResult(
        frame=pd.DataFrame(),
        is_chain_linked=True,
        linking_method=LINKING_METHOD_LEVEL_SHIFT,
        records_linked=3,
        base_year_from=None,
        base_year_to=None,
    )

    _write_chain_linking_log(fake_session, GDP, result)  # type: ignore[arg-type]

    assert fake_session.added_of(ChainLinkingLog) == []


def test_silver_to_gold_handles_an_indicator_with_no_silver_rows(
    fake_session: FakeSession,
) -> None:
    """An indicator that never reached Silver publishes nothing, and is not an error."""
    result = silver_to_gold(fake_session, GDP, domain="gdp")  # type: ignore[arg-type]

    assert result.records_processed == 0
    assert result.records_written == 0
    assert result.records_failed == 0
    assert result.status == STATUS_SUCCESS
    assert fake_session.inserted(GoldAnalytical) == []
    # The delete still runs, so a series that lost all its data is cleared out.
    assert fake_session.statement_kinds(GoldAnalytical) == ["delete"]


# --------------------------------------------------------- load_gold_series


def test_load_gold_series_returns_the_published_columns(fake_session: FakeSession) -> None:
    """The dashboard reads Gold here, provenance columns included."""
    rows = []
    for offset in range(3):
        row = GoldAnalytical(
            indicator_id=GDP,
            timestamp=datetime(FIRST_YEAR + offset, 12, 31, tzinfo=UTC),
            value=210.0 + offset,
            original_value=100.0 + offset,
            is_chain_linked=True,
            chain_linking_confidence=CONFIDENCE_OVERLAP_FLOOR,
            unit=UNIT,
            frequency=FREQUENCY,
            domain="gdp",
            silver_id=uuid4(),
        )
        row.id = uuid4()
        rows.append(row)
    fake_session.seed(GoldAnalytical, rows)

    frame = load_gold_series(fake_session, GDP)  # type: ignore[arg-type]

    assert list(frame["value"]) == [210.0, 211.0, 212.0]
    assert list(frame["original_value"]) == [100.0, 101.0, 102.0]
    assert list(frame["is_chain_linked"]) == [True, True, True]
    assert set(frame["chain_linking_confidence"]) == {CONFIDENCE_OVERLAP_FLOOR}
    assert set(frame["domain"]) == {"gdp"}
    assert frame["timestamp"].is_monotonic_increasing


def test_load_gold_series_is_empty_for_an_unpublished_indicator(
    fake_session: FakeSession,
) -> None:
    """An indicator with no Gold rows yields an empty frame, not an error."""
    assert load_gold_series(fake_session, GDP).empty  # type: ignore[arg-type]


# ---------------------------------------------------------------- daily metrics derivation


def catalog_entry_daily(
    session: FakeSession,
    indicator_id: str,
    domain: str = "fx",
    frequency: str = "daily",
) -> IndicatorCatalog:
    """Create and add a catalog entry for daily indicators."""
    catalog = IndicatorCatalog(
        indicator_id=indicator_id,
        name=f"{indicator_id} Test",
        frequency=frequency,
        domain=domain,
        source_name="tgju",
        base_years=None,
    )
    session.seed(IndicatorCatalog, [catalog], primary_key="indicator_id")
    return catalog


def seed_daily_silver(
    session: FakeSession,
    indicator_id: str = "TGJU.USD.FREE",
    days: int = 40,
) -> list[SilverCleaned]:
    """Seed a daily price series for testing daily metrics."""
    rows: list[SilverCleaned] = []
    base_value = 1000.0

    for day_offset in range(days):
        # Simple growth pattern: 1% daily growth
        value = base_value * (1.01**day_offset)
        row = SilverCleaned(
            indicator_id=indicator_id,
            timestamp=datetime(2026, 9, 1, tzinfo=UTC) + pd.Timedelta(days=day_offset),
            value=value,
            unit="IRR",
            frequency="daily",
            source_name="tgju",
            bronze_id=BRONZE_ID,
        )
        row.id = uuid4()
        rows.append(row)

    session.seed(SilverCleaned, rows)
    return rows


def test_silver_to_gold_daily_strategy_derives_ret1d() -> None:
    """Daily strategy derives RET1D (daily return percentage)."""
    session = FakeSession()
    rows = seed_daily_silver(session, days=10)
    catalog_entry_daily(session, rows[0].indicator_id, domain="fx")

    silver_to_gold(
        session,
        rows[0].indicator_id,
        derivation_strategy="daily",
        derived_prefix="TGJU",
    )

    # Find RET1D rows
    ret1d_rows = derived_daily(session, "RET1D")

    # Should have 9 RET1D rows (first day has no prior value)
    assert len(ret1d_rows) == 9

    # All RET1D rows should have method = "daily_return"
    assert all(r["record_metadata"]["method"] == DERIVED_RET1D_METHOD for r in ret1d_rows)

    # Unit should be "%" for returns
    assert all(r["unit"] == "%" for r in ret1d_rows)

    # is_chain_linked should be False (passthrough)
    assert all(r["is_chain_linked"] is False for r in ret1d_rows)

    # confidence should be None (not chain-linked)
    assert all(r["chain_linking_confidence"] is None for r in ret1d_rows)


def test_silver_to_gold_daily_strategy_derives_ma30() -> None:
    """Daily strategy derives MA30 (30-day moving average)."""
    session = FakeSession()
    rows = seed_daily_silver(session, days=40)
    catalog_entry_daily(session, rows[0].indicator_id, domain="fx", frequency="daily")

    silver_to_gold(
        session,
        rows[0].indicator_id,
        derivation_strategy="daily",
        derived_prefix="TGJU",
    )

    # Find MA30 rows
    ma30_rows = derived_daily(session, "MA30")

    # Should have 11 MA30 rows (first 29 days have insufficient data)
    assert len(ma30_rows) == 11

    # All MA30 rows should have method = "30day_moving_average"
    assert all(r["record_metadata"]["method"] == DERIVED_MA30_METHOD for r in ma30_rows)

    # is_chain_linked should be False (passthrough)
    assert all(r["is_chain_linked"] is False for r in ma30_rows)


def test_daily_ret1d_values_are_correct() -> None:
    """RET1D values match manual pct_change calculation."""
    session = FakeSession()
    # Use simple values for easy verification
    simple_rows = []
    values = [100.0, 105.0, 110.0, 104.5]  # +5%, +4.76%, -5%
    for i, val in enumerate(values):
        row = SilverCleaned(
            indicator_id="TEST.PRICE",
            timestamp=datetime(2026, 9, 1 + i, tzinfo=UTC),
            value=val,
            unit="IRR",
            frequency="daily",
            source_name="test",
            bronze_id=BRONZE_ID,
        )
        row.id = uuid4()
        simple_rows.append(row)

    session.seed(SilverCleaned, simple_rows)
    catalog_entry_daily(session, "TEST.PRICE", domain="test", frequency="daily")

    silver_to_gold(session, "TEST.PRICE", derivation_strategy="daily", derived_prefix="TEST")

    ret1d_rows = sorted(derived_daily(session, "RET1D"), key=lambda r: r["timestamp"])

    # Should have 3 returns (skip first day)
    assert len(ret1d_rows) == 3

    # Verify values: (105-100)/100*100 = 5.0%, (110-105)/105*100 = 4.76%, (104.5-110)/110*100 = -5.0%
    assert abs(ret1d_rows[0]["value"] - 5.0) < 0.01
    assert abs(ret1d_rows[1]["value"] - 4.76) < 0.01
    assert abs(ret1d_rows[2]["value"] - (-5.0)) < 0.01


def test_daily_ma30_values_are_correct() -> None:
    """MA30 values match manual rolling mean calculation."""
    session = FakeSession()
    # 35 days of constant value = 100, MA30 should also be 100
    constant_rows = []
    for i in range(35):
        row = SilverCleaned(
            indicator_id="TEST.CONSTANT",
            timestamp=datetime(2026, 9, 1, tzinfo=UTC) + pd.Timedelta(days=i),
            value=100.0,
            unit="IRR",
            frequency="daily",
            source_name="test",
            bronze_id=BRONZE_ID,
        )
        row.id = uuid4()
        constant_rows.append(row)

    session.seed(SilverCleaned, constant_rows)
    catalog_entry_daily(session, "TEST.CONSTANT", domain="test", frequency="daily")

    silver_to_gold(session, "TEST.CONSTANT", derivation_strategy="daily", derived_prefix="TEST")

    ma30_rows = derived_daily(session, "MA30")

    # Should have 6 MA rows (days 30-35)
    assert len(ma30_rows) == 6

    # All should be exactly 100.0
    assert all(abs(r["value"] - 100.0) < 0.01 for r in ma30_rows)


def test_daily_strategy_skips_first_return() -> None:
    """First day has no RET1D (no prior value to compare)."""
    session = FakeSession()
    rows = seed_daily_silver(session, days=5)
    catalog_entry_daily(session, rows[0].indicator_id, domain="fx", frequency="daily")

    silver_to_gold(
        session, rows[0].indicator_id, derivation_strategy="daily", derived_prefix="TGJU"
    )

    ret1d_rows = sorted(derived_daily(session, "RET1D"), key=lambda r: r["timestamp"])

    # First timestamp should be day 2 (skip day 1)
    assert ret1d_rows[0]["timestamp"] == datetime(2026, 9, 2, tzinfo=UTC)
    assert len(ret1d_rows) == 4  # 5 days - 1 skipped


def test_daily_strategy_skips_first_29_ma() -> None:
    """First 29 days have no MA30 (insufficient window)."""
    session = FakeSession()
    rows = seed_daily_silver(session, days=32)
    catalog_entry_daily(session, rows[0].indicator_id, domain="fx", frequency="daily")

    silver_to_gold(
        session, rows[0].indicator_id, derivation_strategy="daily", derived_prefix="TGJU"
    )

    ma30_rows = sorted(derived_daily(session, "MA30"), key=lambda r: r["timestamp"])

    # First timestamp should be day 30
    assert ma30_rows[0]["timestamp"] == datetime(2026, 9, 30, tzinfo=UTC)
    assert len(ma30_rows) == 3  # Days 30, 31, 32


def test_daily_derived_series_have_correct_indicator_ids() -> None:
    """Daily derived series use derived_ret1d_indicator_id and derived_ma30_indicator_id."""
    session = FakeSession()
    seed_daily_silver(session, indicator_id="TGJU.USD.FREE", days=35)
    catalog_entry_daily(session, "TGJU.USD.FREE", domain="fx", frequency="daily")

    silver_to_gold(session, "TGJU.USD.FREE", derivation_strategy="daily", derived_prefix="TGJU")

    added_indicators = {r["indicator_id"] for r in session.inserted(GoldAnalytical)}

    # Should have base, RET1D, and MA30
    assert "TGJU.USD.FREE" in added_indicators
    assert "TGJU.USD.FREE.RET1D" in added_indicators
    assert "TGJU.USD.FREE.MA30" in added_indicators


def test_daily_strategy_preserves_silver_id_lineage() -> None:
    """RET1D and MA30 rows carry silver_id pointing to the current day's Silver row."""
    session = FakeSession()
    rows = seed_daily_silver(session, days=35)
    catalog_entry_daily(session, rows[0].indicator_id, domain="fx", frequency="daily")

    silver_to_gold(
        session, rows[0].indicator_id, derivation_strategy="daily", derived_prefix="TGJU"
    )

    ret1d_rows = derived_daily(session, "RET1D")
    ma30_rows = derived_daily(session, "MA30")

    # All derived rows should have a non-null silver_id
    assert all(r["silver_id"] is not None for r in ret1d_rows)
    assert all(r["silver_id"] is not None for r in ma30_rows)

    # silver_id should point to actual Silver rows
    silver_ids = {r.id for r in rows}
    assert all(r["silver_id"] in silver_ids for r in ret1d_rows)
    assert all(r["silver_id"] in silver_ids for r in ma30_rows)


def test_daily_strategy_does_not_publish_yoy() -> None:
    """derivation_strategy='daily' does not emit YOY growth series."""
    session = FakeSession()
    rows = seed_daily_silver(session, days=400)  # More than a year of data
    catalog_entry_daily(session, rows[0].indicator_id, domain="fx", frequency="daily")

    silver_to_gold(
        session, rows[0].indicator_id, derivation_strategy="daily", derived_prefix="TGJU"
    )

    added_indicators = {r["indicator_id"] for r in session.inserted(GoldAnalytical)}

    # Should NOT have YOY
    assert not any("YOY" in ind for ind in added_indicators)


def test_yoy_strategy_does_not_publish_daily_metrics() -> None:
    """derivation_strategy='yoy' does not emit RET1D or MA30."""
    session = FakeSession()
    seed_silver(session, rebased_levels())
    session.add(catalog_entry("gdp", base_years=[2000, 2005]))

    silver_to_gold(session, GDP, derivation_strategy="yoy", derived_prefix="WB")

    added_indicators = {r["indicator_id"] for r in session.inserted(GoldAnalytical)}

    # Should have YOY but not RET1D or MA30
    assert any("YOY" in ind for ind in added_indicators)
    assert not any("RET1D" in ind for ind in added_indicators)
    assert not any("MA30" in ind for ind in added_indicators)


def test_daily_strategy_with_custom_prefix() -> None:
    """Daily strategy respects derived_prefix parameter."""
    session = FakeSession()
    seed_daily_silver(session, indicator_id="CUSTOM.INDICATOR", days=35)
    catalog_entry_daily(session, "CUSTOM.INDICATOR", domain="test", frequency="daily")

    silver_to_gold(
        session, "CUSTOM.INDICATOR", derivation_strategy="daily", derived_prefix="CUSTOM"
    )

    added_indicators = {r["indicator_id"] for r in session.inserted(GoldAnalytical)}

    # IDs should start with CUSTOM prefix
    assert "CUSTOM.INDICATOR" in added_indicators
    assert "CUSTOM.INDICATOR.RET1D" in added_indicators
    assert "CUSTOM.INDICATOR.MA30" in added_indicators


def test_daily_metrics_metadata_in_gold() -> None:
    """RET1D and MA30 rows have correct metadata fields."""
    session = FakeSession()
    rows = seed_daily_silver(session, days=35)
    catalog_entry_daily(session, rows[0].indicator_id, domain="fx", frequency="daily")

    silver_to_gold(
        session, rows[0].indicator_id, derivation_strategy="daily", derived_prefix="TGJU"
    )

    ret1d_rows = derived_daily(session, "RET1D")

    # Check one RET1D row in detail
    sample = ret1d_rows[0]
    assert sample["unit"] == "%"
    assert sample["frequency"] == "daily"
    assert sample["domain"] == "fx"
    assert sample["record_metadata"]["method"] == DERIVED_RET1D_METHOD
    assert sample["is_chain_linked"] is False
    assert sample["chain_linking_confidence"] is None
    assert sample["original_value"] is not None  # The actual return value
    assert sample["silver_id"] is not None


# ------------------------------------------------- multi-segment base-year links

CANONICAL = "SCI.CPI.URBAN"
SEG_OLD = "SCI.CPI.URBAN.B2000"
SEG_NEW = "SCI.CPI.URBAN.B2005"
ANNUAL_YEARS = 12
SEGMENT_REBASE = 2.0


def _segment(frame_years: list[int], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [datetime(year, 12, 31, tzinfo=UTC) for year in frame_years]
            ),
            "value": values,
        }
    )


def _base_year_segment(indicator_id: str, frame: pd.DataFrame, base_year: int) -> BaseYearSegment:
    silver_ids = {ts.to_pydatetime(): uuid4() for ts in frame["timestamp"]}
    series = SilverSeries(
        indicator_id=indicator_id,
        frame=frame,
        unit=UNIT,
        frequency=FREQUENCY,
        silver_ids=silver_ids,
    )
    return BaseYearSegment(indicator_id=indicator_id, series=series, base_year=base_year)


def synthetic_segments() -> tuple[BaseYearSegment, BaseYearSegment]:
    """Two annual segments rebased by exactly 2.0, overlapping 2005-2007."""
    levels = {year: 100.0 * GROWTH_RATE ** (year - FIRST_YEAR) for year in range(2000, 2005)}
    levels.update({year: 100.0 * GROWTH_RATE ** (year - FIRST_YEAR) for year in range(2005, 2011)})
    old_years = list(range(2000, 2008))
    new_years = list(range(2005, 2011))
    old_frame = _segment(old_years, [levels[year] for year in old_years])
    new_frame = _segment(new_years, [levels[year] * SEGMENT_REBASE for year in new_years])
    return (
        _base_year_segment(SEG_OLD, old_frame, 2000),
        _base_year_segment(SEG_NEW, new_frame, 2005),
    )


def seed_canonical_catalog(session: FakeSession) -> None:
    session.seed(
        IndicatorCatalog,
        [
            IndicatorCatalog(
                indicator_id=CANONICAL,
                name="CPI - urban",
                frequency=FREQUENCY,
                domain="inflation",
                source_name="sci",
                has_base_year_changes=True,
                base_years=[2000, 2005],
            )
        ],
        primary_key="indicator_id",
    )


def test_base_year_from_indicator_id_reads_the_suffix() -> None:
    assert base_year_from_indicator_id("SCI.CPI.URBAN.B2016") == 2016
    assert base_year_from_indicator_id("SCI.CPI.URBAN") is None
    assert base_year_from_indicator_id("SCI.CPI.URBAN.YOY") is None


def test_order_base_year_segments_oldest_first() -> None:
    old, new = synthetic_segments()

    ordered = order_base_year_segments([new, old])

    assert [segment.indicator_id for segment in ordered] == [SEG_OLD, SEG_NEW]


def test_order_base_year_segments_falls_back_when_base_year_unknown() -> None:
    old, new = synthetic_segments()
    unknown = BaseYearSegment(indicator_id="X.UNKNOWN", series=old.series, base_year=None)

    ordered = order_base_year_segments([new, unknown])

    assert [segment.indicator_id for segment in ordered] == [SEG_NEW, "X.UNKNOWN"]


def test_silver_to_gold_links_segments_under_the_canonical_id(
    fake_session: FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Published segments roll up into one canonical, chain-linked series."""
    old, new = synthetic_segments()
    seed_canonical_catalog(fake_session)
    monkeypatch.setattr("src.etl.gold.load_base_year_segments", lambda session, ids: [old, new])

    result = silver_to_gold(  # type: ignore[arg-type]
        fake_session,
        CANONICAL,
        derived_prefix="SCI",
        derivation_strategy="yoy",
        segment_indicator_ids=[SEG_OLD, SEG_NEW],
    )

    levels = published(fake_session, CANONICAL)
    assert len(levels) == 11  # 2000-2004 rescaled + 2005-2010 on the new base
    linked_years = {row["timestamp"].year for row in levels if row["is_chain_linked"]}
    assert linked_years == {2000, 2001, 2002, 2003, 2004}
    # Segments themselves are never published to Gold.
    assert published(fake_session, SEG_OLD) == []
    assert published(fake_session, SEG_NEW) == []

    assert result.details["is_chain_linked"] is True
    assert result.details["segments"] == [SEG_OLD, SEG_NEW]
    assert published(fake_session, "SCI.CPI.URBAN.YOY")


def test_silver_to_gold_writes_a_chain_linking_log_for_segments(
    fake_session: FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    old, new = synthetic_segments()
    seed_canonical_catalog(fake_session)
    monkeypatch.setattr("src.etl.gold.load_base_year_segments", lambda session, ids: [old, new])

    silver_to_gold(  # type: ignore[arg-type]
        fake_session, CANONICAL, segment_indicator_ids=[SEG_OLD, SEG_NEW]
    )

    logs = fake_session.added_of(ChainLinkingLog)
    assert len(logs) == 1
    assert logs[0].indicator_id == CANONICAL
    assert logs[0].linking_method == "overlap"


def test_silver_to_gold_keeps_segment_lineage(
    fake_session: FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every canonical row points back at the Silver row it came from."""
    old, new = synthetic_segments()
    seed_canonical_catalog(fake_session)
    monkeypatch.setattr("src.etl.gold.load_base_year_segments", lambda session, ids: [old, new])
    all_silver_ids = set(old.series.silver_ids.values()) | set(new.series.silver_ids.values())

    silver_to_gold(  # type: ignore[arg-type]
        fake_session, CANONICAL, segment_indicator_ids=[SEG_OLD, SEG_NEW]
    )

    for row in published(fake_session, CANONICAL):
        assert row["silver_id"] in all_silver_ids


def test_silver_to_gold_raises_on_empty_segment(
    fake_session: FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    old, _ = synthetic_segments()
    empty = BaseYearSegment(
        indicator_id=SEG_NEW,
        series=SilverSeries(indicator_id=SEG_NEW, frame=old.series.frame.iloc[0:0]),
        base_year=2005,
    )
    seed_canonical_catalog(fake_session)
    monkeypatch.setattr("src.etl.gold.load_base_year_segments", lambda session, ids: [old, empty])

    with pytest.raises(ChainLinkingError, match="no Silver observations"):
        silver_to_gold(  # type: ignore[arg-type]
            fake_session, CANONICAL, segment_indicator_ids=[SEG_OLD, SEG_NEW]
        )


def test_silver_to_gold_raises_when_no_segments_loaded(
    fake_session: FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_canonical_catalog(fake_session)
    monkeypatch.setattr("src.etl.gold.load_base_year_segments", lambda session, ids: [])

    with pytest.raises(ChainLinkingError, match="no base-year segments"):
        silver_to_gold(  # type: ignore[arg-type]
            fake_session, CANONICAL, segment_indicator_ids=[SEG_OLD]
        )


def test_load_base_year_segments_orders_and_reads_ids(
    fake_session: FakeSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loader composes ordering with Silver loading (filters are DB-tested)."""
    old, new = synthetic_segments()
    frames = {SEG_OLD: old.series, SEG_NEW: new.series}

    def fake_load(session: FakeSession, indicator_id: str) -> SilverSeries:
        return frames[indicator_id]

    def fake_base_year(session: FakeSession, indicator_id: str) -> int:
        return {SEG_OLD: 2000, SEG_NEW: 2005}[indicator_id]

    monkeypatch.setattr("src.etl.gold.load_silver_series", fake_load)
    monkeypatch.setattr("src.etl.gold._segment_base_year", fake_base_year)

    loaded = load_base_year_segments(fake_session, [SEG_NEW, SEG_OLD])  # type: ignore[arg-type]

    assert [segment.indicator_id for segment in loaded] == [SEG_OLD, SEG_NEW]
