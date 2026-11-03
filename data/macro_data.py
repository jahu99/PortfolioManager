"""
FRED / ALFRED macroeconomic data access.

Scope:
- Retrieve FRED series metadata and observations.
- Retrieve observations as they were known on a historical vintage date.
- Cache responses independently under cache/macro/.
- Preserve source, observation, vintage and retrieval provenance.

This module is data infrastructure only. It does not calculate risk scores,
apply thresholds, make portfolio decisions or change production behaviour.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


FRED_API_BASE_URL = "https://api.stlouisfed.org/fred"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "cache" / "macro"

SCHEMA_VERSION = 1
REQUEST_TIMEOUT_SECONDS = 30
MAX_API_LIMIT = 100_000

SOURCE_NAME = "Federal Reserve Bank of St. Louis"
SOURCE_SYSTEM = "FRED / ALFRED"


class MacroDataError(Exception):
    """Raised when macroeconomic data cannot be retrieved or validated."""


# No thresholds or scoring weights are defined here.
# Series marked with a history note require particular care when used
# for historical analysis.
SERIES_CATALOG: dict[str, dict[str, Any]] = {
    # Interest rates
    "DGS10": {
        "theme": "interest_rates",
        "description": "Market yield on US Treasury securities at 10-year constant maturity",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Nominal 10-year US Treasury yield. A market interest-rate indicator, not a direct measure of the expected policy-rate path.',
    },
    "DGS2": {
        "theme": "interest_rates",
        "description": "Market yield on US Treasury securities at 2-year constant maturity",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Nominal 2-year US Treasury yield. More sensitive than longer maturities to changes in expected near-term monetary policy.',
    },
    "DFII10": {
        "theme": "interest_rates",
        "description": "Market yield on 10-year US Treasury inflation-indexed securities",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": '10-year inflation-indexed Treasury real yield. A market real-yield measure, not expected inflation itself.',
    },
    "T10Y2Y": {
        "theme": "interest_rates",
        "description": "10-year Treasury constant maturity minus 2-year Treasury constant maturity",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": '10-year Treasury yield minus 2-year Treasury yield. A negative spread indicates an inverted yield curve; interpret alongside other growth and credit indicators.',
    },

    # Inflation
    "CPIAUCSL": {
        "theme": "inflation",
        "description": "Consumer Price Index for All Urban Consumers",
        "expected_frequency": "monthly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Headline CPI price index. The index level is not itself an inflation rate; calculate a percentage change over the chosen comparison period.',
    },
    "CPILFESL": {
        "theme": "inflation",
        "description": "Consumer Price Index for All Urban Consumers: All Items Less Food and Energy",
        "expected_frequency": "monthly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Core CPI price index, excluding food and energy. The index level is not itself an inflation rate; calculate a percentage change over the chosen comparison period.',
    },
    "PCEPI": {
        "theme": "inflation",
        "description": "Personal Consumption Expenditures: Chain-type Price Index",
        "expected_frequency": "monthly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Headline PCE price index. The index level is not itself an inflation rate; calculate a percentage change over the chosen comparison period.',
    },
    "PCEPILFE": {
        "theme": "inflation",
        "description": "Personal Consumption Expenditures Excluding Food and Energy",
        "expected_frequency": "monthly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Core PCE price index, excluding food and energy. The index level is not itself an inflation rate; calculate a percentage change over the chosen comparison period.',
    },

    # Growth
    "GDPC1": {
        "theme": "growth",
        "description": "Real Gross Domestic Product",
        "expected_frequency": "quarterly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Real GDP in chained-dollar terms. Quarterly and subject to revision; use the appropriate historical vintage when reconstructing past assessments.',
    },
    "INDPRO": {
        "theme": "growth",
        "description": "Industrial Production: Total Index",
        "expected_frequency": "monthly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Industrial production index. Measures the volume of industrial output and is an activity indicator rather than a broad measure of total economic output.',
    },

    # Employment
    "PAYEMS": {
        "theme": "employment",
        "description": "All Employees: Total Nonfarm",
        "expected_frequency": "monthly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Total nonfarm payroll employment level. Calculate employment growth from changes in the series, rather than inferring it from the level alone.',
    },
    "UNRATE": {
        "theme": "employment",
        "description": "Civilian Unemployment Rate",
        "expected_frequency": "monthly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Civilian unemployment rate. Interpret alongside payroll employment and labour-force participation; it is not a standalone measure of labour-market conditions.',
    },
    "ICSA": {
        "theme": "employment",
        "description": "Initial Claims",
        "expected_frequency": "weekly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Initial unemployment insurance claims. A weekly labour-market indicator; assess its trend and volatility rather than relying on an isolated observation.',
    },

    # Credit
    "BAMLH0A0HYM2": {
        "theme": "credit",
        "description": "ICE BofA US High Yield Index Option-Adjusted Spread",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": 'FRED indicates that from April 2026 only three years of observations are available on a rolling basis. Verify actual observation and vintage-date coverage for each requested historical date.',
        "licensing_note": 'Source: ICE Data Indices. Review applicable ICE licensing and redistribution terms before external distribution; availability through FRED does not itself establish redistribution rights.',
        "interpretation_note": 'US high-yield corporate option-adjusted spread. Wider spreads indicate greater market compensation for credit risk; this is not a default-probability estimate.',
        "history_note": (
            "FRED series notes indicate a limited recent history from April 2026. "
            "Verify available observations before historical analysis."
        ),
    },
    "BAMLC0A0CM": {
        "theme": "credit",
        "description": "ICE BofA US Corporate Index Option-Adjusted Spread",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": 'FRED indicates that from April 2026 only three years of observations are available on a rolling basis. Verify actual observation and vintage-date coverage for each requested historical date.',
        "licensing_note": 'Source: ICE Data Indices. Review applicable ICE licensing and redistribution terms before external distribution; availability through FRED does not itself establish redistribution rights.',
        "interpretation_note": 'US investment-grade corporate option-adjusted spread. Wider spreads indicate greater market compensation for corporate credit risk; this is not a default-probability estimate.',
        "history_note": (
            "FRED series notes indicate a limited recent history from April 2026. "
            "Verify available observations before historical analysis."
        ),
    },

    # Financial conditions
    "NFCI": {
        "theme": "financial_conditions",
        "description": "Chicago Fed National Financial Conditions Index",
        "expected_frequency": "weekly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Positive values indicate tighter-than-average US financial conditions; negative values indicate looser-than-average conditions.',
    },
    "DTWEXBGS": {
        "theme": "financial_conditions",
        "description": "Nominal Broad US Dollar Index",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Broad nominal trade-weighted US dollar index. Treat as a currency-market indicator, not a direct financial-conditions index.',
    },
    "WALCL": {
        "theme": "financial_conditions",
        "description": "Federal Reserve total assets",
        "expected_frequency": "weekly",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'Federal Reserve total assets. A balance-sheet level indicator; it is not, by itself, a complete measure of monetary-policy stance or financial conditions.',
    },

    # Separate commodity risk indicator; not part of the six macro themes.
    "DCOILWTICO": {
        "theme": "commodity_risk",
        "description": "Crude Oil Prices: West Texas Intermediate (WTI) - Cushing, Oklahoma",
        "expected_frequency": "daily",
        "point_in_time_policy": 'ALFRED_VINTAGE_ONLY_RELEASE_DATE_UNVERIFIED',
        "history_constraint": None,
        "licensing_note": None,
        "interpretation_note": 'WTI crude oil spot-price benchmark. A commodity-price indicator, not a comprehensive measure of energy-market conditions.',
    },
}


MACRO_THEMES = (
    "interest_rates",
    "inflation",
    "growth",
    "employment",
    "credit",
    "financial_conditions",
)


def get_series_catalog(theme: str | None = None) -> dict[str, dict[str, Any]]:
    """Return a copy of the series catalogue, optionally filtered by theme."""
    result = {}

    for series_id, metadata in SERIES_CATALOG.items():
        if theme is None or metadata["theme"] == theme:
            result[series_id] = dict(metadata)

    return result


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_timestamp() -> str:
    return _utc_now().isoformat(timespec="seconds")


def _validate_date(value: str, field_name: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field_name} must be a valid YYYY-MM-DD date"
        ) from exc

    if parsed.isoformat() != value:
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format"
        )

    return value


def _validate_series_id(series_id: str) -> str:
    if not isinstance(series_id, str) or not re.fullmatch(
        r"[A-Z0-9_]+", series_id
    ):
        raise ValueError("Invalid FRED series ID")

    if series_id not in SERIES_CATALOG:
        raise ValueError(
            f"Series {series_id!r} is not in the approved macro series catalogue"
        )

    return series_id


def _get_api_key(api_key: str | None = None) -> str:
    key = (
        api_key
        if api_key is not None
        else os.environ.get("FRED_API_KEY")
    )

    if not isinstance(key, str) or not key.strip():
        raise MacroDataError(
            "FRED_API_KEY is not configured in the current environment"
        )

    return key.strip()


def _cache_path(
    cache_dir: Path,
    cache_key: str,
) -> Path:
    digest = hashlib.sha256(
        cache_key.encode("utf-8")
    ).hexdigest()[:20]

    return cache_dir / f"{digest}.json"


def _read_cache(
    path: Path,
    max_age_hours: float,
) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
            return None
        retrieved_at = datetime.fromisoformat(
            payload["provenance"]["retrieved_at_utc"]
        )

        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)

        age = _utc_now() - retrieved_at

        if timedelta(0) <= age < timedelta(hours=max_age_hours):
            return payload

    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

    return None


def _write_cache(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(".tmp")

    temporary_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    temporary_path.replace(path)


def _fred_get(
    endpoint: str,
    params: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    request_params = dict(params)
    request_params["api_key"] = api_key
    request_params["file_type"] = "json"

    url = (
        f"{FRED_API_BASE_URL}/{endpoint}?"
        f"{urllib.parse.urlencode(request_params)}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "StockMomentumAgent/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(
                exc.read().decode("utf-8")
            )
            message = error_payload.get(
                "error_message",
                "FRED returned an HTTP error",
            )
        except (ValueError, UnicodeDecodeError):
            message = "FRED returned an HTTP error"

        raise MacroDataError(
            f"FRED API request failed (HTTP {exc.code}): {message}"
        ) from None

    except urllib.error.URLError as exc:
        raise MacroDataError(
            f"Unable to connect to FRED: {exc.reason}"
        ) from None

    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MacroDataError(
            f"FRED response could not be read: {type(exc).__name__}"
        ) from None

    if not isinstance(payload, dict):
        raise MacroDataError("FRED returned an unexpected response")

    if "error_code" in payload:
        raise MacroDataError(
            f"FRED API error: {payload.get('error_message', 'Unknown error')}"
        )

    return payload


def get_series_metadata(
    series_id: str,
    *,
    api_key: str | None = None,
    cache_dir: Path | str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Retrieve and cache FRED metadata for a catalogue series."""
    series_id = _validate_series_id(series_id)
    key = _get_api_key(api_key)

    cache_root = Path(cache_dir or DEFAULT_CACHE_DIR)
    cache_key = f"metadata:{series_id}:schema:{SCHEMA_VERSION}"
    path = _cache_path(cache_root, cache_key)

    if not force_refresh:
        cached = _read_cache(path, max_age_hours=168)
        if (
            cached is not None
            and isinstance(cached.get("metadata"), dict)
            and isinstance(cached.get("provenance"), dict)
        ):
            cached["catalogue"] = dict(SERIES_CATALOG[series_id])
            cached["provenance"]["cache_status"] = "HIT"
            return cached
    response = _fred_get(
        "series",
        {"series_id": series_id},
        key,
    )

    series_records = response.get("seriess", [])

    if not series_records:
        raise MacroDataError(
            f"FRED returned no metadata for {series_id}"
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "series_id": series_id,
        "catalogue": dict(SERIES_CATALOG[series_id]),
        "metadata": series_records[0],
        "provenance": {
            "source": SOURCE_NAME,
            "source_system": SOURCE_SYSTEM,
            "endpoint": "fred/series",
            "retrieved_at_utc": _utc_timestamp(),
            "retrieval_mode": "CURRENT_METADATA",
            "cache_status": "MISS",
        },
    }

    _write_cache(path, payload)
    return payload


def _normalise_observations(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalised = []
    previous_date = None

    for item in observations:
        if not isinstance(item, dict):
            raise MacroDataError(
                "FRED returned an invalid observation record"
            )

        observation_date = item.get("date")

        try:
            parsed_date = date.fromisoformat(observation_date)
        except (TypeError, ValueError):
            raise MacroDataError(
                f"FRED returned an invalid observation date: {observation_date!r}"
            ) from None

        if parsed_date.isoformat() != observation_date:
            raise MacroDataError(
                f"FRED returned a non-standard observation date: {observation_date!r}"
            )

        if previous_date is not None and observation_date <= previous_date:
            raise MacroDataError(
                "FRED observations are not strictly ascending or contain duplicate dates"
            )

        previous_date = observation_date
        raw_value = item.get("value")

        if raw_value in (None, "", "."):
            numeric_value = None
        else:
            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError):
                raise MacroDataError(
                    f"FRED returned a non-numeric observation value: {raw_value!r}"
                ) from None

            if not math.isfinite(numeric_value):
                raise MacroDataError(
                    f"FRED returned a non-finite observation value: {raw_value!r}"
                )

        normalised.append(
            {
                "observation_date": observation_date,
                "value": numeric_value,
                "value_raw": raw_value,
                "realtime_start": item.get("realtime_start"),
                "realtime_end": item.get("realtime_end"),
            }
        )

    return normalised


def get_series_observations(
    series_id: str,
    *,
    as_of_date: str | None = None,
    observation_start: str | None = None,
    observation_end: str | None = None,
    api_key: str | None = None,
    cache_dir: Path | str | None = None,
    force_refresh: bool = False,
    cache_max_age_hours: float = 24,
) -> dict[str, Any]:
    """
    Retrieve observations for a FRED series.

    If as_of_date is supplied, observations are retrieved using the ALFRED
    vintage mechanism: the values known on that historical date.

    If as_of_date is omitted, observations are retrieved for the current
    FRED real-time period.

    The observation date describes the period measured. The vintage date
    describes when the data version was available. They are not interchangeable.
    """
    series_id = _validate_series_id(series_id)
    key = _get_api_key(api_key)

    if as_of_date is not None:
        as_of_date = _validate_date(as_of_date, "as_of_date")

    if observation_start is not None:
        observation_start = _validate_date(
            observation_start,
            "observation_start",
        )

    if observation_end is not None:
        observation_end = _validate_date(
            observation_end,
            "observation_end",
        )

    if (
        observation_start
        and observation_end
        and observation_start > observation_end
    ):
        raise ValueError(
            "observation_start cannot be later than observation_end"
        )

    retrieval_mode = (
        "AS_OF_VINTAGE" if as_of_date else "CURRENT_REALTIME"
    )

    cache_key = "|".join(
        (
            "observations",
            series_id,
            retrieval_mode,
            as_of_date or "current",
            observation_start or "earliest",
            observation_end or "latest",
            f"schema:{SCHEMA_VERSION}",
        )
    )

    cache_root = Path(cache_dir or DEFAULT_CACHE_DIR)
    path = _cache_path(cache_root, cache_key)

    if not force_refresh:
        cached = _read_cache(
            path,
            max_age_hours=cache_max_age_hours,
        )
        if (
            cached is not None
            and isinstance(cached.get("observations"), list)
            and isinstance(cached.get("provenance"), dict)
            and cached["provenance"].get("observation_count")
            == len(cached["observations"])
        ):
            cached["catalogue"] = dict(SERIES_CATALOG[series_id])
            cached["provenance"]["cache_status"] = "HIT"
            return cached
    params: dict[str, Any] = {
        "series_id": series_id,
        "limit": MAX_API_LIMIT,
        "sort_order": "asc",
    }

    if observation_start:
        params["observation_start"] = observation_start

    if observation_end:
        params["observation_end"] = observation_end

    if as_of_date:
        params["realtime_start"] = as_of_date
        params["realtime_end"] = as_of_date
        params["output_type"] = 1
    else:
        current_date = _utc_now().date().isoformat()
        params["realtime_start"] = current_date
        params["realtime_end"] = current_date
        params["output_type"] = 1

    response = _fred_get(
        "series/observations",
        params,
        key,
    )

    raw_observations = response.get("observations", [])

    if not isinstance(raw_observations, list):
        raise MacroDataError(
            f"FRED returned an invalid observations structure for {series_id}"
        )

    try:
        total_count = int(response.get("count", len(raw_observations)))
    except (TypeError, ValueError):
        raise MacroDataError(
            f"FRED returned an invalid observation count for {series_id}"
        ) from None

    if isinstance(response.get("count"), bool) or total_count < 0:
        raise MacroDataError(
            f"FRED returned an invalid observation count for {series_id}"
        )

    if len(raw_observations) > total_count:
        raise MacroDataError(
            f"FRED returned more observations than its reported count for {series_id}"
        )

    offset = len(raw_observations)

    while offset < total_count:
        page_params = dict(params)
        page_params["offset"] = offset

        page = _fred_get(
            "series/observations",
            page_params,
            key,
        )

        page_observations = page.get("observations", [])

        if not isinstance(page_observations, list) or not page_observations:
            raise MacroDataError(
                f"Incomplete FRED observation pagination for {series_id}: "
                f"retrieved {offset} of {total_count}"
            )

        if len(page_observations) > total_count - offset:
            raise MacroDataError(
                f"FRED returned more observations than its reported count for {series_id}"
            )

        raw_observations.extend(page_observations)
        offset += len(page_observations)

    if len(raw_observations) != total_count:
        raise MacroDataError(
            f"Incomplete FRED observation history for {series_id}: "
            f"retrieved {len(raw_observations)} of {total_count}"
        )

    observations = _normalise_observations(raw_observations)

    valid_values = [
        item for item in observations
        if item["value"] is not None
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "series_id": series_id,
        "catalogue": dict(SERIES_CATALOG[series_id]),
        "retrieval_status": (
            "AVAILABLE" if valid_values else "NO_OBSERVATIONS"
        ),
        "observations": observations,
        "provenance": {
            "source": SOURCE_NAME,
            "source_system": SOURCE_SYSTEM,
            "endpoint": "fred/series/observations",
            "retrieval_mode": retrieval_mode,
            "requested_as_of_date": as_of_date,
            "vintage_date": as_of_date,
            "realtime_period_start": response.get("realtime_start"),
            "realtime_period_end": response.get("realtime_end"),
            "observation_start_filter": observation_start,
            "observation_end_filter": observation_end,
            "observation_count": len(observations),
            "valid_observation_count": len(valid_values),
            "release_date": None,
            "release_date_status": (
                "NOT_RESOLVED_FROM_OBSERVATIONS_ENDPOINT"
            ),
            "retrieved_at_utc": _utc_timestamp(),
            "cache_status": "MISS",
        },
    }

    _write_cache(path, payload)
    return payload


def get_series_vintage_dates(
    series_id: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    api_key: str | None = None,
    cache_dir: Path | str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Retrieve dates on which FRED records new or revised values for a series.

    These are vintage dates, not a substitute for a separately verified
    publication calendar or intraday release timestamp.
    """
    series_id = _validate_series_id(series_id)
    key = _get_api_key(api_key)

    if start_date:
        start_date = _validate_date(start_date, "start_date")

    if end_date:
        end_date = _validate_date(end_date, "end_date")

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be later than end_date")

    cache_key = "|".join(
        (
            "vintage_dates",
            series_id,
            start_date or "earliest",
            end_date or "latest",
            f"schema:{SCHEMA_VERSION}",
        )
    )

    cache_root = Path(cache_dir or DEFAULT_CACHE_DIR)
    path = _cache_path(cache_root, cache_key)

    if not force_refresh:
        cached = _read_cache(path, max_age_hours=168)
        if (
            cached is not None
            and isinstance(cached.get("vintage_dates"), list)
            and isinstance(cached.get("provenance"), dict)
            and cached["provenance"].get("vintage_date_count")
            == len(cached["vintage_dates"])
        ):
            cached["catalogue"] = dict(SERIES_CATALOG[series_id])
            cached["provenance"]["cache_status"] = "HIT"
            return cached
    params: dict[str, Any] = {
        "series_id": series_id,
        "limit": 10_000,
        "sort_order": "asc",
    }

    if start_date:
        params["realtime_start"] = start_date

    if end_date:
        params["realtime_end"] = end_date

    response = _fred_get(
        "series/vintagedates",
        params,
        key,
    )

    vintage_dates = response.get("vintage_dates", [])

    if not isinstance(vintage_dates, list):
        raise MacroDataError(
            f"FRED returned an invalid vintage-date structure for {series_id}"
        )

    try:
        total_count = int(response.get("count", len(vintage_dates)))
    except (TypeError, ValueError):
        raise MacroDataError(
            f"FRED returned an invalid vintage-date count for {series_id}"
        ) from None

    if isinstance(response.get("count"), bool) or total_count < 0:
        raise MacroDataError(
            f"FRED returned an invalid vintage-date count for {series_id}"
        )

    if len(vintage_dates) > total_count:
        raise MacroDataError(
            f"FRED returned more vintage dates than its reported count for {series_id}"
        )

    offset = len(vintage_dates)

    while offset < total_count:
        page_params = dict(params)
        page_params["offset"] = offset

        page = _fred_get(
            "series/vintagedates",
            page_params,
            key,
        )

        page_dates = page.get("vintage_dates", [])

        if not isinstance(page_dates, list) or not page_dates:
            raise MacroDataError(
                f"Incomplete FRED vintage-date pagination for {series_id}: "
                f"retrieved {offset} of {total_count}"
            )

        if len(page_dates) > total_count - offset:
            raise MacroDataError(
                f"FRED returned more vintage dates than its reported count for {series_id}"
            )

        vintage_dates.extend(page_dates)
        offset += len(page_dates)

    if len(vintage_dates) != total_count:
        raise MacroDataError(
            f"Incomplete FRED vintage-date history for {series_id}: "
            f"retrieved {len(vintage_dates)} of {total_count}"
        )

    previous_vintage_date = None
    for vintage_date in vintage_dates:
        try:
            parsed_vintage_date = date.fromisoformat(vintage_date)
        except (TypeError, ValueError):
            raise MacroDataError(
                f"FRED returned an invalid vintage date for {series_id}: "
                f"{vintage_date!r}"
            ) from None

        if parsed_vintage_date.isoformat() != vintage_date:
            raise MacroDataError(
                f"FRED returned a non-standard vintage date for {series_id}: "
                f"{vintage_date!r}"
            )

        if (
            previous_vintage_date is not None
            and vintage_date <= previous_vintage_date
        ):
            raise MacroDataError(
                "FRED vintage dates are not strictly ascending or contain duplicates"
            )

        previous_vintage_date = vintage_date

    payload = {
        "schema_version": SCHEMA_VERSION,
        "series_id": series_id,
        "catalogue": dict(SERIES_CATALOG[series_id]),
        "vintage_dates": vintage_dates,
        "provenance": {
            "source": SOURCE_NAME,
            "source_system": SOURCE_SYSTEM,
            "endpoint": "fred/series/vintagedates",
            "retrieved_at_utc": _utc_timestamp(),
            "start_date_filter": start_date,
            "end_date_filter": end_date,
            "vintage_date_count": len(vintage_dates),
            "cache_status": "MISS",
        },
    }

    _write_cache(path, payload)
    return payload


__all__ = [
    "FRED_API_BASE_URL",
    "MACRO_THEMES",
    "MacroDataError",
    "SERIES_CATALOG",
    "get_series_catalog",
    "get_series_metadata",
    "get_series_observations",
    "get_series_vintage_dates",
]
