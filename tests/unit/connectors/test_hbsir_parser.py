"""
Unit tests for the pure HBSIR weighted-statistics parser.

All inputs are synthetic except one regression test that replays the committed
200-row real 1400 extract. No test imports ``hbsir`` or touches the network.

The weighted math was validated during development against the four full survey
years captured in ``tests/fixtures/hbsir/metrics_trend.json`` (Gini, poverty
rate, poverty line, and weighted households match exactly).
"""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    DEFAULT_INDICATORS,
    GINI_INDICATOR,
    POVERTY_INDICATOR,
    aggregate_metrics,
    empty_frame,
    extract_checksum,
    gini,
    hbsir_parser,
    income_decile_shares,
    merge_extract,
    poverty_line,
    poverty_rate,
    validate_decile_sums,
    weighted_median,
    weighted_quantile,
    year_metrics,
)
from src.utils.exceptions import ParsingError
from src.utils.persian import iranian_year_end
from tests.conftest import load_hbsir_csv

# Real 1400 reference values for the committed 200-row extract.
SAMPLE_GINI = 0.47445754165296994
SAMPLE_POVERTY = 8.662455899542106
SAMPLE_POVERTY_LINE = 23187194.0
SAMPLE_DECILES = (
    -22.5882,
    8.2993,
    10.4108,
    11.9344,
    12.4717,
    13.8506,
    15.6388,
    15.9381,
    16.7827,
    17.2617,
)


def sample_extract() -> pd.DataFrame:
    """The committed 200-row real 1400 extract, reduced to the parser columns."""
    frame = load_hbsir_csv("income_expenditure_weight_1400_sample")
    return frame[["Year", "ID", "Income", "Weight"]]


def equal_weights(count: int) -> list[float]:
    """A list of ``count`` unit weights."""
    return [1.0] * count


# --------------------------------------------------------------- calendar


def test_iranian_year_end_handles_common_and_leap_esfand() -> None:
    """Esfand is 29 days in common years and 30 in leap years."""
    assert iranian_year_end(1400).date().isoformat() == "2022-03-20"
    assert iranian_year_end(1403).date().isoformat() == "2025-03-20"
    assert iranian_year_end(1403).tzinfo is UTC


# --------------------------------------------------------------- gini


def test_gini_of_a_perfectly_equal_distribution_is_zero() -> None:
    """Everyone with the same income means no inequality."""
    assert gini([100.0, 100.0, 100.0, 100.0], equal_weights(4)) == pytest.approx(0.0)


def test_gini_of_two_equal_groups_is_one_half() -> None:
    """Half the households with nothing, half with everything."""
    assert gini([0.0, 100.0], [1.0, 1.0]) == pytest.approx(0.5)


def test_gini_is_sensitive_to_weights() -> None:
    """Weighting the poor households up raises measured inequality."""
    unweighted = gini([0.0, 100.0], [1.0, 1.0])
    weighted = gini([0.0, 100.0], [3.0, 1.0])

    assert unweighted == pytest.approx(0.5)
    assert weighted == pytest.approx(0.75)


def test_gini_rejects_non_positive_total_income() -> None:
    """Gini is undefined without positive total weighted income."""
    with pytest.raises(ParsingError, match="positive total weighted income"):
        gini([-10.0, -5.0], [1.0, 1.0])


# --------------------------------------------------------------- weights validation


def test_weighted_helpers_require_weights() -> None:
    """Missing weights are a hard failure, not a silent unweighted result."""
    with pytest.raises(ParsingError, match="same length"):
        weighted_median([1.0, 2.0, 3.0], [1.0, 1.0])


def test_weights_must_be_non_negative() -> None:
    """A negative sampling weight is invalid."""
    with pytest.raises(ParsingError, match="non-negative"):
        gini([1.0, 2.0], [1.0, -1.0])


def test_weights_must_sum_to_a_positive_value() -> None:
    """All-zero weights cannot produce a representative statistic."""
    with pytest.raises(ParsingError, match="sum to a positive"):
        weighted_median([1.0, 2.0], [0.0, 0.0])


def test_empty_input_is_rejected() -> None:
    """An empty extract has no usable observations."""
    with pytest.raises(ParsingError, match="no usable observations"):
        gini([], [])


def test_non_finite_pairs_are_dropped() -> None:
    """NaN income/weight pairs are dropped before computing."""
    median = weighted_median([1.0, np.nan, 3.0], [1.0, 1.0, 1.0])

    assert median == pytest.approx(1.0)


# --------------------------------------------------------------- weighted median


def test_weighted_median_uses_cumulative_weight() -> None:
    """The median is the first value whose cumulative weight reaches 50%."""
    assert weighted_median([10.0, 20.0, 30.0, 40.0], equal_weights(4)) == pytest.approx(20.0)
    assert weighted_median([10.0, 20.0, 30.0, 40.0], [1.0, 1.0, 5.0, 1.0]) == pytest.approx(30.0)


def test_weighted_quantile_rejects_out_of_range_targets() -> None:
    """A quantile outside [0, 1] is invalid."""
    with pytest.raises(ParsingError, match="between 0 and 1"):
        weighted_quantile([1.0, 2.0], [1.0, 1.0], 1.5)


# --------------------------------------------------------------- poverty


def test_poverty_rate_uses_half_of_the_weighted_median() -> None:
    """Only households strictly below the line count as poor."""
    values = [0.0, 10.0, 100.0, 1000.0]
    weights = equal_weights(4)

    assert poverty_line(values, weights) == pytest.approx(5.0)
    assert poverty_rate(values, weights) == pytest.approx(25.0)


def test_poverty_line_is_configurable() -> None:
    """The multiplier changes the line and therefore the rate."""
    values = [0.0, 8.0, 12.0, 100.0]
    weights = equal_weights(4)

    assert poverty_rate(values, weights, line_k=0.5) == pytest.approx(25.0)
    assert poverty_rate(values, weights, line_k=1.5) == pytest.approx(50.0)


def test_poverty_rate_is_strictly_below_the_line() -> None:
    """A household exactly on the line is not counted as poor."""
    values = [0.0, 10.0, 20.0, 30.0, 40.0]

    assert poverty_rate(values, equal_weights(5)) == pytest.approx(20.0)


def test_poverty_rate_can_be_returned_as_a_fraction() -> None:
    """``percent=False`` returns the share in [0, 1]."""
    rate = poverty_rate([0.0, 10.0, 100.0, 1000.0], equal_weights(4), percent=False)

    assert rate == pytest.approx(0.25)


def test_poverty_line_rejects_a_negative_multiplier() -> None:
    """A negative multiple of the median is not a poverty line."""
    with pytest.raises(ParsingError, match="non-negative"):
        poverty_line([1.0, 2.0], [1.0, 1.0], line_k=-0.5)


# --------------------------------------------------------------- deciles


def test_decile_shares_of_uniform_incomes_are_proportional() -> None:
    """Ten households with incomes 1..10 split the total 1:2:...:10."""
    shares = income_decile_shares(list(range(1, 11)), equal_weights(10))

    assert sum(shares) == pytest.approx(100.0)
    assert shares[0] == pytest.approx(1.0 / 55.0 * 100.0)
    assert shares[-1] == pytest.approx(10.0 / 55.0 * 100.0)


def test_decile_shares_of_an_equal_distribution_are_equal() -> None:
    """Everyone with the same income means every decile holds 10%."""
    shares = income_decile_shares([50.0] * 20, equal_weights(20))

    assert shares == pytest.approx([10.0] * 10)


def test_decile_shares_sum_to_one_hundred() -> None:
    """The ten shares always reconcile to the total."""
    shares = income_decile_shares([1.0, 2.0, 5.0, 50.0, 500.0], [1.0, 4.0, 2.0, 5.0, 1.0])

    assert sum(shares) == pytest.approx(100.0)


def test_decile_shares_require_positive_total_income() -> None:
    """A net-negative year cannot be split into shares."""
    with pytest.raises(ParsingError, match="positive total weighted income"):
        income_decile_shares([-5.0, -10.0], [1.0, 1.0])


# --------------------------------------------------------------- checksum


def test_extract_checksum_is_deterministic_and_order_independent() -> None:
    """The digest binds the extract but not its row order."""
    extract = sample_extract()
    shuffled = extract.sample(frac=1.0, random_state=7).reset_index(drop=True)

    assert extract_checksum(extract) == extract_checksum(shuffled)
    assert len(extract_checksum(extract)) == 64


def test_extract_checksum_changes_with_the_data() -> None:
    """A different income changes the digest."""
    extract = sample_extract()
    changed = extract.copy()
    changed.loc[changed.index[0], "Income"] = changed["Income"].iloc[0] + 1.0

    assert extract_checksum(extract) != extract_checksum(changed)


def test_extract_checksum_requires_the_weight_column() -> None:
    """A missing weight column fails loudly."""
    with pytest.raises(ParsingError, match="Weight"):
        extract_checksum(sample_extract().drop(columns=["Weight"]))


# --------------------------------------------------------------- merge


def test_merge_extract_requires_weights() -> None:
    """The weight table must carry a Weight column."""
    income = sample_extract()[["Year", "ID", "Income"]]
    weights = sample_extract()[["Year", "ID"]].copy()

    with pytest.raises(ParsingError, match="Weight"):
        merge_extract(income, weights)


def test_merge_extract_requires_income() -> None:
    """The income table must carry an Income column."""
    income = sample_extract()[["Year", "ID"]].copy()
    weights = sample_extract()[["Year", "ID", "Weight"]]

    with pytest.raises(ParsingError, match="Income"):
        merge_extract(income, weights)


def test_merge_extract_rejects_a_disjoint_join() -> None:
    """No overlapping household ids is a hard failure."""
    income = new_extract(1400, {1: 100.0, 2: 200.0})
    weights = new_weight_table(1400, {9: 1.0, 10: 1.0})

    with pytest.raises(ParsingError, match="no overlapping households"):
        merge_extract(income, weights)


def new_extract(year: int, incomes: dict[int, float]) -> pd.DataFrame:
    """An income table for one Jalali year."""
    return pd.DataFrame({"Year": year, "ID": list(incomes), "Income": list(incomes.values())})


def new_weight_table(year: int, weights: dict[int, float]) -> pd.DataFrame:
    """A weight table for one Jalali year."""
    return pd.DataFrame({"Year": year, "ID": list(weights), "Weight": list(weights.values())})


# --------------------------------------------------------------- annual frames


def test_aggregate_metrics_emits_all_indicators_per_year() -> None:
    """Every requested indicator gets one row per survey year."""
    extract = pd.DataFrame(
        {
            "Year": [1400] * 4 + [1403] * 4,
            "ID": [1, 2, 3, 4, 1, 2, 3, 4],
            "Income": [0.0, 10.0, 100.0, 1000.0] * 2,
            "Weight": [1.0] * 8,
        }
    )

    aggregate = aggregate_metrics(extract)

    assert set(aggregate["indicator_id"]) == set(DEFAULT_INDICATORS)
    assert len(aggregate) == 12 * 2
    assert sorted(aggregate["Year"].unique()) == [1400, 1403]


def test_aggregate_metrics_records_the_poverty_methodology() -> None:
    """The relative poverty rule is explicit in every poverty observation."""
    extract = new_with_weight(1400, {1: 0.0, 2: 10.0, 3: 100.0, 4: 1000.0})

    aggregate = aggregate_metrics(extract, indicator_ids=[POVERTY_INDICATOR])
    row = aggregate.iloc[0]

    assert row["value"] == pytest.approx(25.0)
    metadata = row["record_metadata"]
    assert metadata["poverty_line_rule"] == "50% of weighted median household income"
    assert metadata["poverty_line_k"] == 0.5
    assert metadata["is_official_poverty_line"] is False
    assert metadata["jalali_year"] == 1400


def test_aggregate_metrics_requires_the_weight_column() -> None:
    """Aggregation is impossible without sampling weights."""
    extract = new_with_weight(1400, {1: 1.0, 2: 2.0}).drop(columns=["Weight"])

    with pytest.raises(ParsingError, match="Weight"):
        aggregate_metrics(extract)


def test_aggregate_metrics_rejects_an_empty_extract() -> None:
    """An empty extract cannot produce a survey year."""
    empty = pd.DataFrame({"Year": [], "ID": [], "Income": [], "Weight": []})

    with pytest.raises(ParsingError, match="empty"):
        aggregate_metrics(empty)


def test_validate_decile_sums_flags_inconsistent_years() -> None:
    """A year whose shares do not reconcile is reported."""
    good = aggregate_metrics(new_with_weight(1400, {1: 1.0, 2: 2.0, 3: 3.0}))
    assert validate_decile_sums(good) == []

    broken = good.copy()
    broken.loc[broken["indicator_id"] == DECILE_INDICATORS[0], "value"] += 5.0
    problems = validate_decile_sums(broken)
    assert len(problems) == 1
    assert "1400" in problems[0]


def new_with_weight(year: int, incomes: dict[int, float]) -> pd.DataFrame:
    """A merged extract with unit weights."""
    return new_extract(year, incomes).merge(
        new_weight_table(year, {key: 1.0 for key in incomes}), on=["Year", "ID"]
    )


# --------------------------------------------------------------- silver frame


def test_hbsir_parser_converts_the_survey_year_to_a_gregorian_year_end() -> None:
    """The observation timestamp is the survey year's last day in UTC."""
    rows = [
        {"Year": 1400, "indicator_id": GINI_INDICATOR, "value": 0.37, "unit": "index (0-1)"},
        {"Year": 1403, "indicator_id": GINI_INDICATOR, "value": 0.35, "unit": "index (0-1)"},
    ]

    frame = hbsir_parser(rows, GINI_INDICATOR)

    assert [timestamp.date().isoformat() for timestamp in frame["timestamp"]] == [
        "2022-03-20",
        "2025-03-20",
    ]
    assert frame["timestamp"].dt.tz is not None
    assert list(frame["indicator_id"]) == [GINI_INDICATOR, GINI_INDICATOR]


def test_hbsir_parser_keeps_the_jalali_year_in_metadata() -> None:
    """The original survey year is retained for auditability."""
    rows = [{"Year": 1400, "indicator_id": GINI_INDICATOR, "value": 0.37}]

    frame = hbsir_parser(rows, GINI_INDICATOR)

    assert frame["record_metadata"].iloc[0]["jalali_year"] == 1400


def test_hbsir_parser_drops_future_survey_years() -> None:
    """A year-end after ``now`` is not emitted."""
    rows = [
        {"Year": 1400, "indicator_id": GINI_INDICATOR, "value": 0.37},
        {"Year": 1403, "indicator_id": GINI_INDICATOR, "value": 0.35},
    ]

    frame = hbsir_parser(rows, GINI_INDICATOR, now=datetime(2023, 1, 1, tzinfo=UTC))

    assert [row.date().isoformat() for row in frame["timestamp"]] == ["2022-03-20"]


def test_hbsir_parser_returns_the_empty_contract_for_no_rows() -> None:
    """No rows means an empty frame with the shared columns."""
    frame = hbsir_parser([], GINI_INDICATOR)

    assert frame.empty
    assert tuple(frame.columns) == tuple(empty_frame().columns)


def test_hbsir_parser_skips_other_indicators() -> None:
    """Rows belonging to a sibling indicator are ignored."""
    rows = [
        {"Year": 1400, "indicator_id": GINI_INDICATOR, "value": 0.37},
        {"Year": 1400, "indicator_id": POVERTY_INDICATOR, "value": 16.4},
    ]

    frame = hbsir_parser(rows, GINI_INDICATOR)

    assert len(frame) == 1
    assert frame["value"].iloc[0] == pytest.approx(0.37)


def test_hbsir_parser_returns_empty_contract_when_no_rows_match() -> None:
    """A payload with only sibling-indicator rows yields the empty contract."""
    rows = [{"Year": 1400, "indicator_id": POVERTY_INDICATOR, "value": 16.4}]

    frame = hbsir_parser(rows, GINI_INDICATOR)

    assert frame.empty
    assert tuple(frame.columns) == tuple(empty_frame().columns)


# --------------------------------------------------------------- real regression


def test_year_metrics_reproduce_the_captured_1400_sample() -> None:
    """The weighted math matches the reference computed during Task 1."""
    metrics = year_metrics(sample_extract())

    assert metrics.jalali_year == 1400
    assert metrics.gini == pytest.approx(SAMPLE_GINI, abs=1e-9)
    assert metrics.poverty_rate == pytest.approx(SAMPLE_POVERTY, abs=1e-6)
    assert metrics.poverty_line_rial == pytest.approx(SAMPLE_POVERTY_LINE)
    assert metrics.weighted_households == pytest.approx(93253.0)
    assert metrics.decile_shares == pytest.approx(SAMPLE_DECILES, abs=1e-3)


# --------------------------------------------------------- malformed inputs


def test_year_metrics_rejects_a_multi_year_extract() -> None:
    """``year_metrics`` computes one survey year at a time."""
    two_years = pd.concat(
        [new_with_weight(1400, {1: 10.0, 2: 20.0}), new_with_weight(1401, {1: 30.0, 2: 40.0})],
        ignore_index=True,
    )

    with pytest.raises(ParsingError, match="exactly one survey year"):
        year_metrics(two_years)


def test_year_metrics_requires_the_weight_column() -> None:
    """Weights are mandatory; a weightless extract fails loudly."""
    no_weights = new_extract(1400, {1: 10.0, 2: 20.0})

    with pytest.raises(ParsingError, match="Weight"):
        year_metrics(no_weights)


def test_validate_decile_sums_skips_an_incomplete_year() -> None:
    """A year missing some deciles is skipped rather than mis-scored."""
    good = aggregate_metrics(new_with_weight(1400, {index: float(index) for index in range(1, 11)}))
    incomplete = good[good["indicator_id"] != DECILE_INDICATORS[-1]]

    assert validate_decile_sums(incomplete) == []


def test_validate_decile_sums_accepts_the_empty_aggregate() -> None:
    """No aggregate rows means nothing to reconcile."""
    assert validate_decile_sums(empty_frame()) == []


def test_hbsir_parser_preserves_blank_values_as_null() -> None:
    """A blank stored value becomes NaN, matching the Silver null contract."""
    rows = [
        {"Year": 1400, "indicator_id": GINI_INDICATOR, "value": ""},
        {"Year": 1401, "indicator_id": GINI_INDICATOR, "value": None},
        {"Year": 1402, "indicator_id": GINI_INDICATOR, "value": 0.37},
    ]

    frame = hbsir_parser(rows, GINI_INDICATOR)

    assert frame["value"].isna().tolist() == [True, True, False]


def test_hbsir_parser_rejects_non_numeric_values() -> None:
    """A non-numeric stored metric is a parse failure, not silent loss."""
    rows = [{"Year": 1400, "indicator_id": GINI_INDICATOR, "value": "not-a-number"}]

    with pytest.raises(ParsingError, match="non-numeric"):
        hbsir_parser(rows, GINI_INDICATOR)


def test_hbsir_parser_missing_year_raises() -> None:
    """A row without a survey year cannot be timestamped."""
    with pytest.raises(KeyError):
        hbsir_parser([{"indicator_id": GINI_INDICATOR, "value": 0.37}], GINI_INDICATOR)
