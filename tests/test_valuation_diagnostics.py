import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from data.universe import get_market_universe
from analysis.universe_filter import filter_investable_universe

from analysis.valuation import (
    assess_valuation,
    valuation_metric_diagnostics,
    valuation_threshold_sensitivity,
)

from data.fundamentals import get_fundamentals


def main():

    print()
    print("=" * 70)
    print("VALUATION METRIC CALIBRATION DIAGNOSTIC")
    print("=" * 70)

    tickers = get_market_universe()

    tickers = filter_investable_universe(
        tickers
    )

    print(
        f"\nUniverse size: {len(tickers)}"
    )

    results = []

    for ticker in tickers:

        try:

            fundamentals = get_fundamentals(
                ticker
            )

            valuation = assess_valuation(
                fundamentals
            )

            result = {
                "Ticker": ticker,

                "PE Ratio": valuation.get(
                    "PE Ratio"
                ),

                "Forward PE": valuation.get(
                    "Forward PE"
                ),

                "PEG Ratio": valuation.get(
                    "PEG Ratio"
                ),

                "Price to Sales": valuation.get(
                    "Price to Sales"
                ),

                "EV to EBITDA": valuation.get(
                    "EV to EBITDA"
                ),

                "Valuation": valuation.get(
                    "Valuation",
                    "UNKNOWN"
                ),
            }

            results.append(result)

        except Exception as exc:

            print(
                f"ERROR | {ticker} | {exc}"
            )

    diagnostics = valuation_metric_diagnostics(
        results
    )

    sensitivity = valuation_threshold_sensitivity(
        results
    )

    print()
    print("=" * 70)
    print("VALUATION THRESHOLD SENSITIVITY")
    print("=" * 70)

    for metric, thresholds in sensitivity.items():

        print()
        print(metric)

        for threshold, stats in thresholds.items():

            print(
                f"  > {threshold}: "
                f"Universe={stats['Full Universe Count']} "
                f"({stats['Full Universe %']:.1f}%) | "
                f"OVERVALUED={stats['OVERVALUED Count']} "
                f"({stats['OVERVALUED %']:.1f}%)"
            )

    for group_name, metrics in diagnostics.items():

        print()
        print("=" * 70)
        print(group_name)
        print("=" * 70)

        for metric, stats in metrics.items():

            print(
                f"\n{metric}"
            )

            print(
                f"  Count : {stats['Count']}"
            )

            print(
                f"  Median: {stats['Median']}"
            )

            print(
                f"  P75   : {stats['P75']}"
            )

            print(
                f"  P90   : {stats['P90']}"
            )

            print(
                f"  P95   : {stats['P95']}"
            )

    print()
    print("=" * 70)
    print("VALUATION METRIC DIAGNOSTIC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()