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
    DERIVED_METHOD,
    DERIVED_YOY_UNIT,
    _resolve_domain,
    _write_chain_linking_log,
    derived_growth_indicator_id,
    gold_indicator_ids,
    load_gold_series,
    silver_to_gold,
)
from src.etl.lineage import LAYER_GOLD, LAYER_SILVER, STATUS_SUCCESS
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
