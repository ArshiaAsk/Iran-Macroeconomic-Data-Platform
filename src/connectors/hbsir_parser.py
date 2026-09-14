"""
Pure, weighted statistics for the Iran Household Budget Survey (HBSIR).

The ``hbsir`` package is only a *loader*: it fetches standardized survey tables
(income, expenditure, sampling weights) but computes neither a Gini nor a
poverty line. This module owns every statistical decision so the numbers are
unit-testable without the package, the network, or a database, and so the
connector stays a thin transport/registry layer.

Methodology (explicit, by design)
---------------------------------
* **Unit of analysis is the household**, not the individual or the
  equivalized household. Weights are the survey sampling weights and are
  **mandatory**: without them the statistics are not representative.
* **Income basis** is ``Total_Income`` (annual household income, Rial). It can
  be negative (net business losses), so the few negative incomes are kept.
* **Weighted median**: the first income at which the cumulative weight reaches
  50% (no interpolation).
* **Gini**: the weighted Lorenz/Brown formula
  ``1 - Σ pᵢ (Lᵢ₋₁ + Lᵢ)`` where ``pᵢ = wᵢ/Σw`` and ``L`` is the cumulative
  share of total weighted income.
* **Relative poverty rate**: the weighted share of households below
  ``k * weighted median income`` (default ``k = 0.5``). This is an explicitly
  **relative** measure -- it is *not* the official Iranian (calorie-based)
  poverty line, and must never be presented as one.
* **Income decile shares**: households are ordered by income and assigned to a
  decile by their cumulative weight position; each decile's share is its
  weighted income as a percentage of the weighted total.

Weighted helpers raise :class:`ParsingError` on missing, mismatched,
non-finite, negative, or all-zero weights so a silent unweighted result is
impossible.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from src.database.schema import utc_now
from src.utils.exceptions import ParsingError
from src.utils.persian import iranian_year_end

FRAME_COLUMNS = ("timestamp", "value", "indicator_id", "unit", "obs_status")

ArrayLike = Sequence[float] | npt.NDArray[np.float64]

GINI_INDICATOR = "HBSIR.GINI"
POVERTY_INDICATOR = "HBSIR.POVERTY.RATE"
DECILE_INDICATOR_PREFIX = "HBSIR.INCOME.DECILE.D"
DECILE_COUNT = 10
DECILE_INDICATORS = tuple(
    f"{DECILE_INDICATOR_PREFIX}{index}" for index in range(1, DECILE_COUNT + 1)
)
DEFAULT_INDICATORS = (GINI_INDICATOR, POVERTY_INDICATOR, *DECILE_INDICATORS)

UNIT_GINI = "index (0-1)"
UNIT_PERCENT = "percent"
INDICATOR_UNITS: Mapping[str, str] = {
    GINI_INDICATOR: UNIT_GINI,
    POVERTY_INDICATOR: UNIT_PERCENT,
    **{indicator: UNIT_PERCENT for indicator in DECILE_INDICATORS},
}

YEAR_COLUMN = "Year"
ID_COLUMN = "ID"
INCOME_COLUMN = "Income"
WEIGHT_COLUMN = "Weight"
EXTRA_COLUMNS = ("record_metadata",)

DEFAULT_POVERTY_LINE_K = 0.5
POVERTY_LINE_RULE = "50% of weighted median household income"
DECILE_SHARE_TOLERANCE_PCT = 0.5

MIN_GINI = 0.0
MAX_GINI = 1.0
MIN_PERCENT = 0.0
MAX_PERCENT = 100.0


@dataclass(frozen=True)
class YearMetrics:
    """Weighted distributional metrics for one survey year."""

    jalali_year: int
    gini: float
    poverty_rate: float
    poverty_line_rial: float
    decile_shares: tuple[float, ...]
    n_households: int
    weighted_households: float


def empty_frame() -> pd.DataFrame:
    """An empty series frame with the Silver column contract."""
    return pd.DataFrame(
        {
            "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
            "value": pd.Series(dtype="float64"),
            "indicator_id": pd.Series(dtype="object"),
            "unit": pd.Series(dtype="object"),
            "obs_status": pd.Series(dtype="object"),
        }
    )


# --------------------------------------------------------------- weighted maths


def _validated_arrays(
    values: ArrayLike,
    weights: ArrayLike,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Coerce and validate an (income, weight) pair.

    Non-finite pairs are dropped; everything after that must be present and
    well-formed, or the caller gets a :class:`ParsingError`.

    Args:
        values: Income (or other value) observations
        weights: Sampling weights, one per value

    Returns:
        Two aligned float64 arrays

    Raises:
        ParsingError: If the inputs are empty, mismatched, or have unusable weights
    """
    incomes = np.asarray(values, dtype="float64").reshape(-1)
    sample_weights = np.asarray(weights, dtype="float64").reshape(-1)
    if incomes.shape != sample_weights.shape:
        msg = (
            "HBSIR values and weights must have the same length "
            f"({incomes.size} vs {sample_weights.size})"
        )
        raise ParsingError(msg)

    finite = np.isfinite(incomes) & np.isfinite(sample_weights)
    incomes = incomes[finite]
    sample_weights = sample_weights[finite]
    if incomes.size == 0:
        msg = "HBSIR has no usable observations after dropping non-finite values/weights"
        raise ParsingError(msg)
    if (sample_weights < 0).any():
        msg = "HBSIR weights must be non-negative"
        raise ParsingError(msg)
    if sample_weights.sum() <= 0:
        msg = "HBSIR weights must sum to a positive value"
        raise ParsingError(msg)
    return incomes, sample_weights


def _ordered(
    values: npt.NDArray[np.float64], weights: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Sort incomes ascending (stable) with their weights."""
    order = np.argsort(values, kind="mergesort")
    return values[order], weights[order]


def weighted_median(
    values: ArrayLike,
    weights: ArrayLike,
) -> float:
    """
    Weighted median: the first value where cumulative weight reaches 50%.

    Args:
        values: Income observations
        weights: Sampling weights

    Returns:
        Weighted median income

    Raises:
        ParsingError: If the inputs or weights are invalid
    """
    return weighted_quantile(values, weights, 0.5)


def weighted_quantile(
    values: ArrayLike,
    weights: ArrayLike,
    quantile: float,
) -> float:
    """
    Weighted quantile using the cumulative-weight (no interpolation) rule.

    Args:
        values: Income observations
        weights: Sampling weights
        quantile: Target quantile in ``[0, 1]``

    Returns:
        The first value at which the cumulative weight reaches ``quantile``

    Raises:
        ParsingError: If the inputs or weights are invalid, or the quantile is out of range
    """
    if not 0.0 <= quantile <= 1.0:
        msg = f"HBSIR quantile must be between 0 and 1, got {quantile!r}"
        raise ParsingError(msg)
    incomes, sample_weights = _validated_arrays(values, weights)
    incomes, sample_weights = _ordered(incomes, sample_weights)
    cumulative = np.cumsum(sample_weights) / sample_weights.sum()
    index = int(np.searchsorted(cumulative, quantile))
    return float(incomes[min(index, incomes.size - 1)])


def gini(
    values: ArrayLike,
    weights: ArrayLike,
) -> float:
    """
    Household-weighted Gini coefficient via the Lorenz/Brown formula.

    Args:
        values: Income observations
        weights: Sampling weights

    Returns:
        Gini coefficient (0 = perfect equality; higher = more unequal)

    Raises:
        ParsingError: If the inputs or weights are invalid, or total weighted income is not positive
    """
    incomes, sample_weights = _validated_arrays(values, weights)
    incomes, sample_weights = _ordered(incomes, sample_weights)
    total_weight = sample_weights.sum()
    weighted_income = sample_weights * incomes
    total_income = weighted_income.sum()
    if total_income <= 0:
        msg = "HBSIR Gini requires a positive total weighted income"
        raise ParsingError(msg)

    shares = sample_weights / total_weight
    cumulative = np.cumsum(weighted_income) / total_income
    previous = np.concatenate(([0.0], cumulative[:-1]))
    return float(1.0 - np.sum(shares * (previous + cumulative)))


def poverty_line(
    values: ArrayLike,
    weights: ArrayLike,
    line_k: float = DEFAULT_POVERTY_LINE_K,
) -> float:
    """
    Relative poverty line: ``line_k * weighted median income``.

    Args:
        values: Income observations
        weights: Sampling weights
        line_k: Multiple of the weighted median (default 0.5)

    Returns:
        Poverty line in Rial

    Raises:
        ParsingError: If ``line_k`` is negative or the inputs are invalid
    """
    if line_k < 0:
        msg = f"HBSIR poverty line multiplier must be non-negative, got {line_k!r}"
        raise ParsingError(msg)
    return line_k * weighted_median(values, weights)


def poverty_rate(
    values: ArrayLike,
    weights: ArrayLike,
    poverty_line_rial: float | None = None,
    line_k: float = DEFAULT_POVERTY_LINE_K,
    *,
    percent: bool = True,
) -> float:
    """
    Weighted share of households below the (relative) poverty line.

    Args:
        values: Income observations
        weights: Sampling weights
        poverty_line_rial: Explicit line; computed from ``line_k`` when omitted
        line_k: Multiple of the weighted median when the line is omitted
        percent: Return a percentage (default) or a fraction

    Returns:
        Poverty rate as a percentage (or fraction when ``percent=False``)

    Raises:
        ParsingError: If the inputs or weights are invalid
    """
    incomes, sample_weights = _validated_arrays(values, weights)
    line = (
        poverty_line_rial
        if poverty_line_rial is not None
        else poverty_line(incomes, sample_weights, line_k=line_k)
    )
    share = float(sample_weights[incomes < line].sum() / sample_weights.sum())
    return share * (100.0 if percent else 1.0)


def income_decile_shares(
    values: ArrayLike,
    weights: ArrayLike,
) -> tuple[float, ...]:
    """
    Weighted income share of each decile, in percent.

    Households are ordered by income and assigned to a decile by their
    cumulative weight position; a decile's share is its weighted income divided
    by the weighted total. The ten shares sum to 100 (negative incomes, rare,
    can make the bottom share negative).

    Args:
        values: Income observations
        weights: Sampling weights

    Returns:
        Ten shares (D1..D10) in percent

    Raises:
        ParsingError: If the inputs or weights are invalid, or total weighted income is not positive
    """
    incomes, sample_weights = _validated_arrays(values, weights)
    incomes, sample_weights = _ordered(incomes, sample_weights)
    total_income = float((incomes * sample_weights).sum())
    if total_income <= 0:
        msg = "HBSIR decile shares require a positive total weighted income"
        raise ParsingError(msg)

    cumulative = np.cumsum(sample_weights) / sample_weights.sum()
    # A household belongs to the decile its cumulative weight position crosses,
    # so the household that lands exactly on a decile boundary closes that
    # decile (``ceil``) rather than opening the next one.
    decile = np.clip(np.ceil(cumulative * DECILE_COUNT).astype(int) - 1, 0, DECILE_COUNT - 1)
    shares = [
        float(
            (incomes[decile == index] * sample_weights[decile == index]).sum()
            / total_income
            * 100.0
        )
        for index in range(DECILE_COUNT)
    ]
    return tuple(shares)


def extract_checksum(extract: pd.DataFrame) -> str:
    """
    Deterministic SHA-256 digest of the income/weight extract.

    Binds a published observation to the exact microdata that produced it
    without persisting the microdata itself. Rows are sorted by
    ``(Year, ID)`` so the digest is independent of load order.

    Args:
        extract: Merged extract with Year, ID, Income, and Weight columns

    Returns:
        Hex-encoded SHA-256 digest

    Raises:
        ParsingError: If required columns are missing
    """
    _require_columns(extract, (YEAR_COLUMN, ID_COLUMN, INCOME_COLUMN, WEIGHT_COLUMN))
    ordered = extract.sort_values([YEAR_COLUMN, ID_COLUMN], kind="mergesort")
    digest = hashlib.sha256()
    digest.update(ordered[YEAR_COLUMN].to_numpy(dtype="int64").tobytes())
    digest.update(ordered[INCOME_COLUMN].to_numpy(dtype="float64").tobytes())
    digest.update(ordered[WEIGHT_COLUMN].to_numpy(dtype="float64").tobytes())
    return digest.hexdigest()


def merge_extract(
    income: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    income_column: str = INCOME_COLUMN,
    weight_column: str = WEIGHT_COLUMN,
) -> pd.DataFrame:
    """
    Join the income and sampling-weight tables on ``(Year, ID)``.

    Weights are mandatory: a missing weight table/column, or a join that yields
    no rows, is a hard failure rather than a silently unweighted statistic.

    Args:
        income: ``Total_Income``-shaped table with Year, ID, and income columns
        weights: ``Weight``-shaped table with Year, ID, and a weight column
        income_column: Income column name
        weight_column: Weight column name

    Returns:
        Merged extract with Year, ID, income, and weight columns

    Raises:
        ParsingError: If a required column is missing or the join is empty
    """
    _require_columns(income, (YEAR_COLUMN, ID_COLUMN, income_column))
    _require_columns(weights, (YEAR_COLUMN, ID_COLUMN, weight_column))
    merged = income[[YEAR_COLUMN, ID_COLUMN, income_column]].merge(
        weights[[YEAR_COLUMN, ID_COLUMN, weight_column]],
        on=[YEAR_COLUMN, ID_COLUMN],
        how="inner",
    )
    if merged.empty:
        msg = "HBSIR income and weight tables produced no overlapping households"
        raise ParsingError(msg)
    return merged


# --------------------------------------------------------------- annual frames


def year_metrics(
    extract: pd.DataFrame,
    *,
    line_k: float = DEFAULT_POVERTY_LINE_K,
    income_column: str = INCOME_COLUMN,
    weight_column: str = WEIGHT_COLUMN,
) -> YearMetrics:
    """
    Compute every weighted metric for one survey year's extract.

    Args:
        extract: Rows for a single survey year
        line_k: Relative poverty line multiplier
        income_column: Income column name
        weight_column: Weight column name (mandatory)

    Returns:
        The year's metrics

    Raises:
        ParsingError: If weights are missing/invalid or the year is not uniform
    """
    _require_columns(extract, (YEAR_COLUMN, income_column, weight_column))
    years = extract[YEAR_COLUMN].dropna().unique()
    if len(years) != 1:
        msg = f"HBSIR year_metrics expects exactly one survey year, got {sorted(years)}"
        raise ParsingError(msg)
    jalali_year = int(years[0])

    incomes = extract[income_column].to_numpy(dtype="float64")
    weights = extract[weight_column].to_numpy(dtype="float64")
    line = poverty_line(incomes, weights, line_k=line_k)
    return YearMetrics(
        jalali_year=jalali_year,
        gini=gini(incomes, weights),
        poverty_rate=poverty_rate(incomes, weights, line, percent=True),
        poverty_line_rial=line,
        decile_shares=income_decile_shares(incomes, weights),
        n_households=int(len(extract)),
        weighted_households=float(np.nansum(weights)),
    )


def aggregate_metrics(
    extract: pd.DataFrame,
    *,
    indicator_ids: Sequence[str] = DEFAULT_INDICATORS,
    line_k: float = DEFAULT_POVERTY_LINE_K,
    income_column: str = INCOME_COLUMN,
    weight_column: str = WEIGHT_COLUMN,
) -> pd.DataFrame:
    """
    Turn a merged survey extract into a tidy annual frame for the indicators.

    The output is the Bronze row shape (no timestamps, so it is JSON-safe);
    :func:`hbsir_parser` converts it to the Silver frame.

    Args:
        extract: Merged extract with Year, Income, and Weight columns
        indicator_ids: Indicators to emit (default: all 12)
        line_k: Relative poverty line multiplier
        income_column: Income column name
        weight_column: Weight column name (mandatory)

    Returns:
        DataFrame with columns Year, indicator_id, value, unit, record_metadata

    Raises:
        ParsingError: If weights are missing/invalid or no survey years are present
    """
    _require_columns(extract, (YEAR_COLUMN, income_column, weight_column))
    if extract.empty:
        msg = "HBSIR extract is empty; no survey years to aggregate"
        raise ParsingError(msg)

    requested = set(indicator_ids)
    records: list[dict[str, Any]] = []
    for year in sorted(extract[YEAR_COLUMN].dropna().unique()):
        year_extract = extract[extract[YEAR_COLUMN] == year]
        metrics = year_metrics(
            year_extract, line_k=line_k, income_column=income_column, weight_column=weight_column
        )
        base_metadata: dict[str, Any] = {
            "jalali_year": metrics.jalali_year,
            "n_households": metrics.n_households,
            "weighted_households": metrics.weighted_households,
            "income_basis": income_column,
        }
        if GINI_INDICATOR in requested:
            records.append(
                _record(
                    metrics.jalali_year,
                    GINI_INDICATOR,
                    metrics.gini,
                    UNIT_GINI,
                    base_metadata,
                )
            )
        if POVERTY_INDICATOR in requested:
            poverty_metadata = {
                **base_metadata,
                "poverty_line_rial": metrics.poverty_line_rial,
                "poverty_line_rule": POVERTY_LINE_RULE,
                "poverty_line_k": line_k,
                "is_official_poverty_line": False,
            }
            records.append(
                _record(
                    metrics.jalali_year,
                    POVERTY_INDICATOR,
                    metrics.poverty_rate,
                    UNIT_PERCENT,
                    poverty_metadata,
                )
            )
        for index, indicator_id in enumerate(DECILE_INDICATORS, start=1):
            if indicator_id not in requested:
                continue
            records.append(
                _record(
                    metrics.jalali_year,
                    indicator_id,
                    metrics.decile_shares[index - 1],
                    UNIT_PERCENT,
                    {**base_metadata, "decile": index},
                )
            )

    return pd.DataFrame.from_records(
        records,
        columns=[YEAR_COLUMN, "indicator_id", "value", "unit", "record_metadata"],
    ).sort_values([YEAR_COLUMN, "indicator_id"], kind="mergesort", ignore_index=True)


def validate_decile_sums(
    aggregate: pd.DataFrame,
    *,
    tolerance: float = DECILE_SHARE_TOLERANCE_PCT,
) -> list[str]:
    """
    Check that each survey year's ten decile shares sum to 100.

    Args:
        aggregate: Tidy frame from :func:`aggregate_metrics`
        tolerance: Acceptable absolute deviation from 100 (percentage points)

    Returns:
        One message per year whose shares do not sum to ``100 ± tolerance``
    """
    if aggregate.empty:
        return []
    deciles = aggregate[aggregate["indicator_id"].isin(DECILE_INDICATORS)]
    problems: list[str] = []
    for year, group in deciles.groupby(YEAR_COLUMN):
        if group["indicator_id"].nunique() != DECILE_COUNT:
            continue
        total = float(group["value"].sum())
        if abs(total - 100.0) > tolerance:
            problems.append(f"HBSIR decile shares for {year} sum to {total:.4f}, expected 100")
    return problems


def hbsir_parser(
    rows: Sequence[Mapping[str, Any]],
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,
) -> pd.DataFrame:
    """
    Convert stored annual metric rows into the Silver input frame.

    Args:
        rows: Bronze rows for one indicator (Year + value + record_metadata)
        indicator_id: Platform indicator id these rows belong to
        unit: Resolved unit; falls back to the row's unit or the registry default
        now: Clock override for the future-year cutoff

    Returns:
        DataFrame with columns timestamp, value, indicator_id, unit, obs_status,
        record_metadata, sorted ascending

    Raises:
        ParsingError: If a survey year cannot be converted to a Gregorian year-end
    """
    if not rows:
        return empty_frame()

    cutoff = now or utc_now()
    fallback_unit = unit or INDICATOR_UNITS.get(indicator_id)
    records = []
    for row in rows:
        if row.get("indicator_id") not in (None, indicator_id):
            continue
        jalali_year = int(row[YEAR_COLUMN])
        metadata = dict(row.get("record_metadata") or {})
        metadata.setdefault("jalali_year", jalali_year)
        records.append(
            {
                "timestamp": iranian_year_end(jalali_year),
                "value": _coerce_value(row.get("value")),
                "indicator_id": indicator_id,
                "unit": row.get("unit") or fallback_unit,
                "obs_status": None,
                "record_metadata": metadata,
            }
        )

    if not records:
        return empty_frame()

    columns = [*FRAME_COLUMNS, *EXTRA_COLUMNS]
    frame = pd.DataFrame.from_records(records, columns=columns)
    frame["value"] = frame["value"].astype("float64")
    frame = frame[frame["timestamp"] <= cutoff]
    return frame.sort_values("timestamp").reset_index(drop=True)


def _require_columns(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    """Raise a clear error when a required survey column is absent."""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        msg = f"HBSIR extract is missing required column(s): {', '.join(missing)}"
        raise ParsingError(msg)


def _record(
    jalali_year: int,
    indicator_id: str,
    value: float,
    unit: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """One Bronze row for an indicator in a survey year."""
    return {
        YEAR_COLUMN: int(jalali_year),
        "indicator_id": indicator_id,
        "value": float(value),
        "unit": unit,
        "record_metadata": dict(metadata),
    }


def _coerce_value(raw_value: Any) -> float | None:
    """Convert a stored value to float, preserving blank/null as None."""
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and not raw_value.strip():
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        msg = f"non-numeric HBSIR metric value {raw_value!r}"
        raise ParsingError(msg) from exc
