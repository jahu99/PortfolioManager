"""
Valuation Assessment — Shadow Mode

Provides valuation telemetry and a provisional valuation classification.

This module does NOT change:

- Technical Score
- Quality Score
- Growth Score
- Investment Score
- Recommendation
- Candidate ranking
- Portfolio decisions
- Capital allocation
- Learning / weight optimisation

Valuation is deliberately isolated so that its classification
can be calibrated against realised outcomes before becoming
decision-relevant.
"""

VALUATION_MODE = "SHADOW"


def _safe_float(value):
    """
    Convert a value to float where possible.

    Returns None for missing, invalid, NaN or infinite values.
    """

    try:

        if value is None:
            return None

        result = float(value)

        if result != result:
            return None

        if result in (
            float("inf"),
            float("-inf")
        ):
            return None

        return result

    except (
        TypeError,
        ValueError
    ):
        return None


def classify_valuation(
    pe_ratio,
    forward_pe,
    peg_ratio,
    price_to_sales,
    ev_to_ebitda
):
    """
    Provisional valuation classification.

    Classification is intentionally conservative.

    A stock is only classified as OVERVALUED when there is
    sufficient evidence from multiple valuation metrics.

    Missing valuation data results in UNKNOWN.

    This classification is SHADOW ONLY and currently has
    no effect on ranking or portfolio decisions.
    """

    metrics = {
        "PE Ratio": pe_ratio,
        "Forward PE": forward_pe,
        "PEG Ratio": peg_ratio,
        "Price to Sales": price_to_sales,
        "EV to EBITDA": ev_to_ebitda,
    }

    available = [
        value
        for value in metrics.values()
        if value is not None
    ]

    if len(available) < 2:
        return "UNKNOWN"

    expensive_votes = 0
    attractive_votes = 0

    # ---------------------------------
    # Earnings valuation
    # ---------------------------------

    if pe_ratio is not None:

        if pe_ratio > 40:
            expensive_votes += 1

        elif pe_ratio < 20:
            attractive_votes += 1

    if forward_pe is not None:

        if forward_pe > 30:
            expensive_votes += 1

        elif forward_pe < 18:
            attractive_votes += 1

    # ---------------------------------
    # Growth-adjusted valuation
    # ---------------------------------

    if peg_ratio is not None:

        if peg_ratio > 2.0:
            expensive_votes += 1

        elif peg_ratio < 1.0:
            attractive_votes += 1

    # ---------------------------------
    # Sales valuation
    # ---------------------------------

    if price_to_sales is not None:

        if price_to_sales > 10:
            expensive_votes += 1

        elif price_to_sales < 5:
            attractive_votes += 1

    # ---------------------------------
    # Enterprise valuation
    # ---------------------------------

    if ev_to_ebitda is not None:

        if ev_to_ebitda > 30:
            expensive_votes += 1

        elif ev_to_ebitda < 15:
            attractive_votes += 1

    # ---------------------------------
    # Classification
    # ---------------------------------

    if expensive_votes >= 2:
        return "OVERVALUED"

    if attractive_votes >= 2:
        return "UNDERVALUED"

    return "WELL VALUED"


def assess_valuation(fundamentals):
    """
    Assess valuation using available fundamental telemetry.

    Classification remains SHADOW ONLY.
    """

    if not isinstance(
        fundamentals,
        dict
    ):
        fundamentals = {}

    pe_ratio = _safe_float(
        fundamentals.get(
            "PE Ratio"
        )
    )

    forward_pe = _safe_float(
        fundamentals.get(
            "Forward PE"
        )
    )

    peg_ratio = _safe_float(
        fundamentals.get(
            "PEG Ratio"
        )
    )

    price_to_sales = _safe_float(
        fundamentals.get(
            "Price to Sales"
        )
    )

    ev_to_ebitda = _safe_float(
        fundamentals.get(
            "EV to EBITDA"
        )
    )

    free_cash_flow = _safe_float(
        fundamentals.get(
            "Free Cash Flow"
        )
    )

    valuation = classify_valuation(
        pe_ratio,
        forward_pe,
        peg_ratio,
        price_to_sales,
        ev_to_ebitda
    )

    return {
        "PE Ratio": pe_ratio,
        "Forward PE": forward_pe,
        "PEG Ratio": peg_ratio,
        "Price to Sales": price_to_sales,
        "EV to EBITDA": ev_to_ebitda,
        "Free Cash Flow": free_cash_flow,
        "Valuation": valuation,
        "Valuation Mode": VALUATION_MODE
    }

def summarise_valuation(results):
    """
    Summarise provisional valuation classifications.

    Diagnostic / calibration only.

    Does NOT change:
    - scores
    - recommendations
    - rankings
    - portfolio decisions
    - capital allocation
    """

    if not results:
        return {
            "Total": 0,
            "UNDERVALUED": 0,
            "WELL VALUED": 0,
            "OVERVALUED": 0,
            "UNKNOWN": 0,
        }

    counts = {
        "UNDERVALUED": 0,
        "WELL VALUED": 0,
        "OVERVALUED": 0,
        "UNKNOWN": 0,
    }

    for result in results:

        if not isinstance(
            result,
            dict
        ):
            continue

        valuation = result.get(
            "Valuation",
            "UNKNOWN"
        )

        if valuation not in counts:
            valuation = "UNKNOWN"

        counts[valuation] += 1

    total = sum(
        counts.values()
    )

    return {
        "Total": total,
        **counts
    }

def valuation_diagnostics(results):
    """
    Return valuation classification diagnostics and
    universe-level valuation distributions.

    Diagnostic / calibration only.

    Does NOT change:
    - scores
    - recommendations
    - rankings
    - portfolio decisions
    - capital allocation
    """

    metrics = {
        "PE Ratio": [],
        "Forward PE": [],
        "PEG Ratio": [],
        "Price to Sales": [],
        "EV to EBITDA": [],
    }

    classifications = []

    for result in results:

        if not isinstance(
            result,
            dict
        ):
            continue

        classifications.append(
            {
                "Ticker":
                    result.get(
                        "Ticker"
                    ),

                "Sector":
                    result.get(
                        "Sector"
                    ),

                "Valuation":
                    result.get(
                        "Valuation",
                        "UNKNOWN"
                    ),
            }
        )

        for metric in metrics:

            value = _safe_float(
                result.get(
                    metric
                )
            )

            if value is not None:
                metrics[metric].append(
                    value
                )

    distributions = {}

    for metric, values in metrics.items():

        if not values:
            distributions[metric] = {
                "Count": 0,
                "Median": None,
                "P75": None,
                "P90": None,
                "P95": None,
            }
            continue

        values = sorted(
            values
        )

        def percentile(
            percentile_value
        ):
            index = (
                (len(values) - 1)
                * percentile_value
            )

            lower = int(index)
            upper = min(
                lower + 1,
                len(values) - 1
            )

            weight = index - lower

            return (
                values[lower]
                + (
                    values[upper]
                    - values[lower]
                )
                * weight
            )

        distributions[metric] = {
            "Count":
                len(values),

            "Median":
                percentile(0.50),

            "P75":
                percentile(0.75),

            "P90":
                percentile(0.90),

            "P95":
                percentile(0.95),
        }

    return {
        "Classifications":
            classifications,

        "Distributions":
            distributions,
    }



def valuation_threshold_diagnostics(results):
    """
    Measure how frequently each provisional valuation
    threshold is triggered across the universe.

    Diagnostic / calibration only.
    """

    counts = {
        "PE > 40": 0,
        "Forward PE > 30": 0,
        "PEG > 2": 0,
        "Price to Sales > 10": 0,
        "Price to Sales > 15": 0,
        "EV to EBITDA > 30": 0,

        "PE < 20": 0,
        "Forward PE < 18": 0,
        "PEG < 1": 0,
        "Price to Sales < 5": 0,
        "EV to EBITDA < 15": 0,
    }

    for result in results:
        if not isinstance(result, dict):
            continue

        pe = _safe_float(result.get("PE Ratio"))
        forward_pe = _safe_float(result.get("Forward PE"))
        peg = _safe_float(result.get("PEG Ratio"))
        price_to_sales = _safe_float(result.get("Price to Sales"))
        ev_to_ebitda = _safe_float(result.get("EV to EBITDA"))

        if pe is not None:
            if pe > 40:
                counts["PE > 40"] += 1
            if pe < 20:
                counts["PE < 20"] += 1

        if forward_pe is not None:
            if forward_pe > 30:
                counts["Forward PE > 30"] += 1
            if forward_pe < 18:
                counts["Forward PE < 18"] += 1

        if peg is not None:
            if peg > 2:
                counts["PEG > 2"] += 1
            if peg < 1:
                counts["PEG < 1"] += 1

        if price_to_sales is not None:
            if price_to_sales > 10:
                counts["Price to Sales > 10"] += 1
            if price_to_sales < 5:
                counts["Price to Sales < 5"] += 1

        if ev_to_ebitda is not None:
            if ev_to_ebitda > 30:
                counts["EV to EBITDA > 30"] += 1
            if ev_to_ebitda < 15:
                counts["EV to EBITDA < 15"] += 1

    return counts

def valuation_evidence_diagnostics(results):
    """
    Show the valuation evidence contributing to each
    provisional OVERVALUED classification.

    Diagnostic / calibration only.
    Does NOT change classification or decision logic.
    """

    diagnostics = []

    for result in results:
        if not isinstance(result, dict):
            continue

        if result.get("Valuation") != "OVERVALUED":
            continue

        pe = _safe_float(result.get("PE Ratio"))
        forward_pe = _safe_float(result.get("Forward PE"))
        peg = _safe_float(result.get("PEG Ratio"))
        price_to_sales = _safe_float(result.get("Price to Sales"))
        ev_to_ebitda = _safe_float(result.get("EV to EBITDA"))

        earnings_expensive = (
            (pe is not None and pe > 40)
            or
            (forward_pe is not None and forward_pe > 30)
        )

        growth_expensive = (
            peg is not None and peg > 2
        )

        enterprise_expensive = (
            (
                ev_to_ebitda is not None
                and ev_to_ebitda > 30
                and ev_to_ebitda > 0
            )
            or
            (
                price_to_sales is not None
                and price_to_sales > 10
            )
        )

        diagnostics.append({
            "Ticker": result.get("Ticker"),
            "Sector": result.get("Sector"),
            "Earnings Expensive": earnings_expensive,
            "Growth Expensive": growth_expensive,
            "Enterprise/Revenue Expensive": enterprise_expensive,
            "PE Ratio": pe,
            "Forward PE": forward_pe,
            "PEG Ratio": peg,
            "Price to Sales": price_to_sales,
            "EV to EBITDA": ev_to_ebitda,
        })

    return diagnostics

def valuation_metric_diagnostics(results):
    """
    Analyse the valuation metrics of the current universe
    and the OVERVALUED subset.

    Diagnostic / calibration only.
    Does NOT change valuation classification or decision logic.
    """

    metrics = [
        "PE Ratio",
        "Forward PE",
        "PEG Ratio",
        "Price to Sales",
        "EV to EBITDA",
    ]

    groups = {
        "FULL UNIVERSE": results,
        "OVERVALUED": [
            result
            for result in results
            if isinstance(result, dict)
            and result.get("Valuation") == "OVERVALUED"
        ],
    }

    diagnostics = {}

    for group_name, group_results in groups.items():

        diagnostics[group_name] = {}

        for metric in metrics:

            values = []

            for result in group_results:

                value = _safe_float(
                    result.get(metric)
                )

                if value is None:
                    continue

                # Exclude non-positive multiples from
                # distribution statistics.
                if value <= 0:
                    continue

                values.append(value)

            values.sort()

            if not values:
                diagnostics[group_name][metric] = {
                    "Count": 0,
                    "Median": None,
                    "P75": None,
                    "P90": None,
                    "P95": None,
                }
                continue

            def percentile(values, percentile):
                index = int(
                    round(
                        (percentile / 100)
                        * (len(values) - 1)
                    )
                )
                return values[index]

            diagnostics[group_name][metric] = {
                "Count": len(values),
                "Median": percentile(values, 50),
                "P75": percentile(values, 75),
                "P90": percentile(values, 90),
                "P95": percentile(values, 95),
            }

    return diagnostics

def valuation_threshold_sensitivity(results):
    """
    Test how sensitive valuation evidence is to alternative
    expensive-metric thresholds.

    Diagnostic / calibration only.
    Does NOT change valuation classification or decision logic.
    """

    thresholds = {
        "PE Ratio": [30, 40, 50, 60, 75],
        "Forward PE": [20, 25, 30, 35, 40],
        "PEG Ratio": [1.5, 2.0, 2.5, 3.0],
        "Price to Sales": [7.5, 10, 15, 20],
        "EV to EBITDA": [20, 25, 30, 40, 50],
    }

    diagnostics = {}

    for metric, threshold_values in thresholds.items():

        diagnostics[metric] = {}

        valid_values = []

        for result in results:

            if not isinstance(result, dict):
                continue

            value = _safe_float(
                result.get(metric)
            )

            if value is None or value <= 0:
                continue

            valid_values.append(value)

        for threshold in threshold_values:

            full_count = sum(
                value > threshold
                for value in valid_values
            )

            overvalued_count = 0

            for result in results:

                if not isinstance(result, dict):
                    continue

                if result.get("Valuation") != "OVERVALUED":
                    continue

                value = _safe_float(
                    result.get(metric)
                )

                if value is None or value <= 0:
                    continue

                if value > threshold:
                    overvalued_count += 1

            diagnostics[metric][threshold] = {
                "Full Universe Count": full_count,
                "Full Universe %": (
                    full_count / len(valid_values) * 100
                    if valid_values
                    else 0
                ),
                "OVERVALUED Count": overvalued_count,
                "OVERVALUED %": (
                    overvalued_count / 295 * 100
                    if overvalued_count
                    else 0
                ),
            }

    return diagnostics
