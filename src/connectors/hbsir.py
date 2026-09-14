"""
Household Budget Survey of Iran (HBSIR) connector.

Phase 6's second package-backed source. The ``hbsir`` package is used **only to
load** standardized survey tables (income + sampling weights); every statistic
is computed by :mod:`src.connectors.hbsir_parser`, which keeps the methodology
auditable and unit-testable without the package or the network.

Indicators (Phase 6 gate, see ``docs/phase-6/README.md``)
---------------------------------------------------------
* ``HBSIR.GINI`` -- household-weighted Gini of annual household income.
* ``HBSIR.POVERTY.RATE`` -- **relative** poverty rate: the weighted share of
  households below ``k * weighted median income`` (default ``k = 0.5``). This is
  explicitly **not** the official Iranian poverty line; the rule is recorded in
  each observation's metadata and in the Bronze manifest.
* ``HBSIR.INCOME.DECILE.D1`` .. ``D10`` -- weighted income shares by decile.

Design notes
------------
* **Weights are mandatory.** A missing weight table/column, mismatched lengths,
  or all-zero weights fail loudly (:class:`ParsingError`) instead of producing an
  unweighted statistic.
* **No microdata is persisted.** Bronze stores the derived annual observations
  plus a *manifest* (source tables, survey years, household counts, and a
  SHA-256 checksum binding each observation to the exact income/weight extract).
  The household-level extract itself is never written or redistributed.
* **Survey years are Jalali**, converted to the correct Gregorian Iranian
  year-end (Esfand 29/30) by ``src.utils.persian.iranian_year_end``; the Jalali
  year is retained in ``record_metadata``.
* **No growth derivations:** Gini, the poverty rate, and decile shares are
  already levels/rates/shares, so the source opts out of ``yoy`` growth.
* The package is optional (Poetry extra ``hbsir``) and imported lazily, so the
  default install and unit suite stay package-free.
"""

import argparse
import importlib.metadata
import importlib.util
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from src.connectors.base import DataConnector, IndicatorMetadata
from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    DEFAULT_INDICATORS,
    DEFAULT_POVERTY_LINE_K,
    GINI_INDICATOR,
    INDICATOR_UNITS,
    POVERTY_INDICATOR,
    POVERTY_LINE_RULE,
    YEAR_COLUMN,
    aggregate_metrics,
    extract_checksum,
    hbsir_parser,
    merge_extract,
    validate_decile_sums,
)
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ValidationError
from src.utils.logging import get_logger, log_with_context
from src.utils.periods import FREQUENCY_ANNUAL
from src.utils.validation import ValidationResult, validate_data_quality

logger = get_logger(__name__)

SOURCE_NAME = "hbsir"
SOURCE_TYPE = "package"
DERIVED_PREFIX = "HBSIR"

PACKAGE_DISTRIBUTION = "hbsir"
PACKAGE_IMPORT_NAME = "hbsir"

INCOME_TABLE = "Total_Income"
WEIGHT_TABLE = "Weight"
INCOME_BASIS = "household_income"

UNIT_MAX_LENGTH = 50

SOURCE_URL = "https://github.com/Iran-Open-Data/HBSIR"

MISSING_EXTRA_MESSAGE = (
    "HBSIR requires the optional 'hbsir' package, which is not installed. "
    "Install it with `poetry install -E hbsir` (or `pip install hbsir`)."
)

GINI_MIN = 0.0
GINI_MAX = 1.0
PERCENT_MIN = 0.0
PERCENT_MAX = 100.0


@dataclass(frozen=True)
class HbsirIndicator:
    """Registry entry: how one survey-derived series maps onto the catalog."""

    indicator_id: str
    name: str
    domain: str = "welfare"
    unit: str = "percent"


def _indicator_names() -> dict[str, str]:
    names = {
        GINI_INDICATOR: "Household income Gini coefficient (weighted)",
        POVERTY_INDICATOR: "Relative poverty rate (50% of weighted median income)",
    }
    names.update(
        {
            indicator: f"Household income share, decile {index} (weighted)"
            for index, indicator in enumerate(DECILE_INDICATORS, start=1)
        }
    )
    return names


HBSIR_INDICATORS: Mapping[str, HbsirIndicator] = {
    indicator_id: HbsirIndicator(
        indicator_id=indicator_id,
        name=_indicator_names()[indicator_id],
        unit=INDICATOR_UNITS[indicator_id],
    )
    for indicator_id in DEFAULT_INDICATORS
}


def is_available() -> bool:
    """Report whether the optional ``hbsir`` package can be imported."""
    try:
        return importlib.util.find_spec(PACKAGE_IMPORT_NAME) is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False


def package_version() -> str | None:
    """Installed ``hbsir`` distribution version, or None when absent."""
    try:
        return importlib.metadata.version(PACKAGE_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        return None


@dataclass(frozen=True)
class HbsirConfig:
    """Per-connector configuration (AGENTS.md: no hardcoded values in logic)."""

    data_dir: str = field(default_factory=lambda: get_config().api.hbsir_data_dir)
    indicators: tuple[str, ...] = DEFAULT_INDICATORS
    #: Jalali survey years to load; ``None`` means every year the package offers.
    years: tuple[int, ...] | None = None
    poverty_line_k: float = DEFAULT_POVERTY_LINE_K
    income_table: str = INCOME_TABLE
    weight_table: str = WEIGHT_TABLE
    download_timeout: int = field(default_factory=lambda: get_config().api.hbsir_download_timeout)


@dataclass
class HbsirFetchResult:
    """A computed annual series plus everything Bronze needs for provenance."""

    indicator_id: str
    frame: pd.DataFrame
    raw_envelope: dict[str, Any]
    package_version: str | None
    request_url: str | None = None
    http_status_code: int | None = None

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata`` (no microdata)."""
        meta = self.raw_envelope.get("meta", {})
        return {
            "indicator_id": self.indicator_id,
            "package": PACKAGE_DISTRIBUTION,
            "package_version": self.package_version,
            "source_tables": meta.get("source_tables"),
            "survey_years_jalali": meta.get("survey_years_jalali"),
            "extract_checksum_sha256": meta.get("extract_checksum_sha256"),
            "poverty_line_rule": meta.get("poverty_line_rule"),
            "microdata_persisted": False,
            "envelope_convention": "raw_data = {rows, meta}",
        }


@runtime_checkable
class HbsirLoader(Protocol):
    """The injectable transport seam (the package analogue of ``http_session``)."""

    @property
    def package_version(self) -> str | None:
        """Version of the underlying package, for Bronze provenance."""
        ...

    def is_available(self) -> bool:
        """Whether the underlying package can be imported."""
        ...

    def load_table(self, table_name: str, years: Sequence[int] | str) -> pd.DataFrame:
        """Load one standardized survey table for the given Jalali years."""
        ...


class HbsirPackageLoader:
    """
    Default loader: imports ``hbsir`` lazily and reads standardized tables.

    The package auto-downloads a pre-built cleaned Parquet file per
    (table, year) into its local data directory on first use and then works
    offline. No credentials are required.
    """

    def __init__(self, config: HbsirConfig) -> None:
        """Store the connector configuration."""
        self.config = config
        self._module: ModuleType | None = None

    @property
    def package_version(self) -> str | None:
        """Installed ``hbsir`` version, or None when absent."""
        return package_version()

    def is_available(self) -> bool:
        """Whether ``hbsir`` can be imported."""
        return is_available()

    def _load_module(self) -> ModuleType:
        """Import ``hbsir`` once, or raise one actionable error."""
        if self._module is None:
            try:
                import hbsir
            except ImportError as exc:
                raise PlatformConnectionError(MISSING_EXTRA_MESSAGE) from exc
            self._module = hbsir
        return self._module

    def load_table(self, table_name: str, years: Sequence[int] | str) -> pd.DataFrame:
        """
        Load one survey table, downloading cleaned Parquet when missing.

        Args:
            table_name: HBSIR table name (e.g. ``Total_Income``)
            years: Jalali years, or the package's ``"all"``/``"last"`` tokens

        Returns:
            The requested table

        Raises:
            ConnectionError: If the optional package is missing
            DataRetrievalError: If the package cannot produce the table
        """
        module = self._load_module()
        try:
            table = module.load_table(table_name, years, on_missing="download")
        except Exception as exc:
            msg = f"HBSIR could not load table {table_name!r} for years {years!r}: {exc}"
            raise DataRetrievalError(msg) from exc
        if not isinstance(table, pd.DataFrame):
            msg = f"HBSIR table {table_name!r} did not return a DataFrame"
            raise DataRetrievalError(msg)
        return table


class HbsirConnector(DataConnector):
    """Connector that derives weighted annual welfare indicators from HBSIR."""

    def __init__(
        self,
        config: HbsirConfig | None = None,
        loader: HbsirLoader | None = None,
    ) -> None:
        """
        Initialize the connector.

        Args:
            config: Connector configuration; defaults come from ``AppConfig``
            loader: Injected survey loader (unit tests pass a fake); defaults to
                :class:`HbsirPackageLoader`
        """
        super().__init__(source_name=SOURCE_NAME)
        self.config = config or HbsirConfig()
        self._aggregate: pd.DataFrame | None = None
        self._extract: pd.DataFrame | None = None
        self._owns_loader = loader is None
        self._loader: HbsirLoader = loader or HbsirPackageLoader(self.config)

    @property
    def loader(self) -> HbsirLoader:
        """The active survey loader, exposed for tests and diagnostics."""
        return self._loader

    def connect(self) -> bool:
        """
        Verify the optional package is importable.

        Unlike the HTTP connectors there is no endpoint to probe without
        downloading data, so connectivity means "the package can be imported";
        the first table load happens on the first :meth:`fetch_series`.

        Returns:
            True when the package is importable

        Raises:
            ConnectionError: If the optional extra is missing
        """
        if not self._loader.is_available():
            raise PlatformConnectionError(MISSING_EXTRA_MESSAGE)
        log_with_context(
            logger,
            "INFO",
            "hbsir connectivity check",
            package_version=self._loader.package_version,
            data_dir=self.config.data_dir,
        )
        return True

    def discover(self) -> list[IndicatorMetadata]:
        """
        Describe every configured indicator from the committed registry.

        ``availability_start`` / ``availability_end`` stay None: coverage is
        filled in by the pipeline from the observations it actually stores.

        Returns:
            One :class:`IndicatorMetadata` per configured indicator
        """
        discovered: list[IndicatorMetadata] = []
        for indicator_id in self.config.indicators:
            registry = HBSIR_INDICATORS.get(indicator_id)
            if registry is None:
                logger.warning("Unknown HBSIR indicator %s, skipping", indicator_id)
                continue
            discovered.append(
                IndicatorMetadata(
                    indicator_id=indicator_id,
                    name=registry.name,
                    description=None,
                    unit=registry.unit[:UNIT_MAX_LENGTH],
                    frequency=FREQUENCY_ANNUAL,
                    domain=registry.domain,
                    source_name=self.source_name,
                    source_url=SOURCE_URL,
                    availability_start=None,
                    availability_end=None,
                    has_base_year_changes=False,
                    base_years=None,
                )
            )
        return discovered

    def fetch(self, indicator_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch one indicator's annual series as a DataFrame.

        The full survey history is computed; the ABC's date arguments exist for
        protocol conformance and are ignored.

        Args:
            indicator_id: Platform indicator id
            start_date: Ignored
            end_date: Ignored

        Returns:
            DataFrame with columns timestamp, value, indicator_id, unit, obs_status
        """
        del start_date, end_date
        return self.fetch_series(indicator_id).frame

    def fetch_series(self, indicator_id: str) -> HbsirFetchResult:
        """
        Compute one indicator's annual series from the loaded survey extract.

        Args:
            indicator_id: Platform indicator id

        Returns:
            Annual frame plus the derived-row envelope and manifest

        Raises:
            DataRetrievalError: If the indicator is not registered
            ParsingError: If weights are missing/invalid or the extract is unusable
            ValidationError: If decile shares do not sum to 100 for a year
        """
        registry = HBSIR_INDICATORS.get(indicator_id)
        if registry is None:
            msg = f"HBSIR indicator {indicator_id} is not registered"
            raise DataRetrievalError(msg)

        aggregate = self._ensure_aggregate()
        rows = [
            _json_safe_row(row)
            for row in aggregate[aggregate["indicator_id"] == indicator_id].to_dict("records")
        ]
        frame = hbsir_parser(rows, indicator_id, registry.unit)

        log_with_context(
            logger,
            "INFO",
            "hbsir series computed",
            indicator_id=indicator_id,
            years=len(rows),
            usable=int(len(frame)),
        )
        return HbsirFetchResult(
            indicator_id=indicator_id,
            frame=frame,
            raw_envelope={"rows": rows, "meta": dict(self._manifest or {})},
            package_version=self._loader.package_version,
        )

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """
        Validate one indicator's annual series.

        Runs the shared quality checks and then enforces each indicator's range:
        Gini in ``[0, 1]``, poverty rate and decile shares in ``[0, 100]``.
        Decile-sum consistency is asserted once per run in
        :meth:`_ensure_aggregate`.

        Args:
            data: DataFrame produced by :meth:`fetch`

        Returns:
            Quality report with range errors appended
        """
        result = validate_data_quality(data)
        if data.empty or "value" not in data.columns:
            return result

        values = data["value"].dropna()
        indicator_ids = set(data.get("indicator_id", pd.Series(dtype="object")).dropna())
        out_of_range = 0
        if GINI_INDICATOR in indicator_ids:
            gini_values = values[data["indicator_id"] == GINI_INDICATOR]
            out_of_range += int(((gini_values < GINI_MIN) | (gini_values > GINI_MAX)).sum())
        others = indicator_ids - {GINI_INDICATOR}
        if others:
            percent_values = values[data["indicator_id"].isin(others)]
            out_of_range += int(
                ((percent_values < PERCENT_MIN) | (percent_values > PERCENT_MAX)).sum()
            )
        if out_of_range:
            result.errors.append(f"{out_of_range} HBSIR observation(s) are out of range")
            result.is_valid = False
        return result

    def disconnect(self) -> None:
        """Release the loader if it created one (a no-op for the default loader)."""
        if not self._owns_loader:
            return
        closer = getattr(self._loader, "close", None)
        if callable(closer):
            closer()

    # --------------------------------------------------------------- internals

    def _ensure_aggregate(self) -> pd.DataFrame:
        """Load the extract once and compute every indicator for every year."""
        if self._aggregate is not None:
            return self._aggregate

        years: Sequence[int] | str = self.config.years if self.config.years else "all"
        income = self._loader.load_table(self.config.income_table, years)
        weights = self._loader.load_table(self.config.weight_table, years)
        extract = merge_extract(income, weights)
        aggregate = aggregate_metrics(
            extract,
            indicator_ids=self.config.indicators,
            line_k=self.config.poverty_line_k,
        )
        problems = validate_decile_sums(aggregate)
        if problems:
            raise ValidationError("; ".join(problems))

        self._extract = extract
        self._aggregate = aggregate
        self._manifest = self._build_manifest(extract)
        log_with_context(
            logger,
            "INFO",
            "hbsir extract aggregated",
            years=int(extract[YEAR_COLUMN].nunique()),
            households=int(len(extract)),
            indicators=len(aggregate),
        )
        return aggregate

    def _build_manifest(self, extract: pd.DataFrame) -> dict[str, Any]:
        """Compact, microdata-free provenance for the computation."""
        survey_years = sorted(int(year) for year in extract[YEAR_COLUMN].unique())
        per_year = [
            {
                "jalali_year": int(year),
                "n_households": int(len(extract[extract[YEAR_COLUMN] == year])),
                "weighted_households": float(
                    extract.loc[extract[YEAR_COLUMN] == year, "Weight"].sum()
                ),
            }
            for year in survey_years
        ]
        return {
            "package": PACKAGE_DISTRIBUTION,
            "package_version": self._loader.package_version,
            "income_basis": INCOME_BASIS,
            "source_tables": [self.config.income_table, self.config.weight_table],
            "survey_years_jalali": survey_years,
            "n_years": len(survey_years),
            "years": per_year,
            "n_households": int(len(extract)),
            "extract_columns": [str(column) for column in extract.columns],
            "extract_checksum_sha256": extract_checksum(extract),
            "poverty_line_rule": POVERTY_LINE_RULE,
            "poverty_line_k": self.config.poverty_line_k,
            "is_official_poverty_line": False,
            "microdata_persisted": False,
        }


def _json_safe_row(row: Mapping[Any, Any]) -> dict[str, Any]:
    """Drop non-JSON column types (numpy scalars) from an aggregate row."""
    safe: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, int | float | str | bool) or value is None:
            safe[str(key)] = value
        elif isinstance(value, Mapping):
            safe[str(key)] = dict(value)
        else:
            safe[str(key)] = value.item() if hasattr(value, "item") else str(value)
    return safe


def build_spec() -> Any:
    """Build the pipeline ``SourceSpec`` for HBSIR (local import avoids a cycle)."""
    from src.etl.pipeline import IndicatorDerivation, SourceSpec

    return SourceSpec(
        source_name=SOURCE_NAME,
        source_type=SOURCE_TYPE,
        frequency=FREQUENCY_ANNUAL,
        derived_prefix=DERIVED_PREFIX,
        indicators=DEFAULT_INDICATORS,
        # Gini / poverty / decile shares are already levels, rates, or shares;
        # derived YoY growth would be meaningless, so growth is off by default.
        default_derivation=IndicatorDerivation(
            derivation_strategy="yoy",
            include_growth=False,
            include_monthly=False,
        ),
        parser=hbsir_parser,
    )


def _parse_years(text: str | None) -> tuple[int, ...] | None:
    """Parse ``--years`` (comma list and/or hyphen ranges) into Jalali years."""
    if not text:
        return None
    years: list[int] = []
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, _, end_text = token.partition("-")
            start, end = int(start_text.strip()), int(end_text.strip())
            years.extend(range(start, end + 1))
        else:
            years.append(int(token))
    if not years:
        return None
    return tuple(sorted(set(years)))


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point: run the HBSIR pipeline.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 on success, 1 if any indicator failed)
    """
    from dataclasses import replace

    from src.etl.pipeline import run_cli

    parser = argparse.ArgumentParser(
        prog="python -m src.connectors.hbsir",
        description="Derive HBSIR weighted welfare indicators into Bronze/Silver/Gold.",
    )
    parser.add_argument(
        "--indicators",
        help=f"Comma-separated indicator codes (default: all {len(DEFAULT_INDICATORS)})",
    )
    parser.add_argument(
        "--years",
        default=None,
        help="Jalali survey years, e.g. '1390-1403' or '1395,1400' (default: all available)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and compute without writing to the database",
    )
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    args = parser.parse_args(argv)

    selected = (
        tuple(code.strip() for code in args.indicators.split(",") if code.strip())
        if args.indicators
        else None
    )
    config = HbsirConfig()
    if selected:
        config = replace(config, indicators=selected)
    years = _parse_years(args.years)
    if years is not None:
        config = replace(config, years=years)
    connector = HbsirConnector(config=config)
    return run_cli(
        indicators=selected,
        dry_run=args.dry_run,
        log_level=args.log_level,
        connector=connector,
        spec=build_spec(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
