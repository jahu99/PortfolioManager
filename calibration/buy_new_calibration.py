"""BUY NEW Calibration V1. Offline only; never imported by production."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

from .benchmark import (
    load_universe,
    load_historical_closes,
    rank_forward_winners,
    realised_forward_return,
)

from .miss_classification import classify
from .replay import db_path, load_recommendations, load_audits, latest_recommendation, latest_audit_action
from .reporting import write_report
from analysis.investment_score import calculate_investment_score


def build_signal_score_analysis(
    population: pd.DataFrame,
    tickers: list[str],
) -> pd.DataFrame:
    """
    Analyse realised 28D performance by Signal × Investment Score band.

    This is an offline A6 calibration analysis only.

    The analysis is restricted to the selected calibration universe
    and does not modify production scoring, signals, thresholds,
    candidate selection, or portfolio decisions.
    """

    analysis = population.copy()

    # ============================================================
    # SELECTED CALIBRATION UNIVERSE
    # ============================================================

    universe = {
        str(ticker).upper()
        for ticker in tickers
    }

    analysis = analysis[
        analysis[
            "ticker"
        ]
        .astype(str)
        .str.upper()
        .isin(universe)
    ].copy()

    # ============================================================
    # INVESTMENT SCORE BANDS
    # ============================================================

    def score_band(
        score,
    ):

        if pd.isna(score):
            return None

        score = float(score)

        if score < 50:
            return "<50"

        if score < 60:
            return "50–59"

        if score < 70:
            return "60–69"

        if score < 75:
            return "70–74"

        return "75+"

    analysis[
        "Investment Score Band"
    ] = (
        analysis[
            "investment_score"
        ]
        .apply(
            score_band
        )
    )

    # ============================================================
    # NORMALISE SIGNAL
    # ============================================================

    analysis[
        "Signal"
    ] = (
        analysis[
            "signal"
        ]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # ============================================================
    # VALID ANALYSIS POPULATION
    # ============================================================

    analysis = analysis[
        analysis[
            "Investment Score Band"
        ].notna()
        &
        analysis[
            "Signal"
        ].notna()
        &
        (
            analysis[
                "Signal"
            ] != ""
        )
        &
        (
            analysis[
                "Signal"
            ] != "NAN"
        )
    ].copy()

    # ============================================================
    # SIGNAL × SCORE ANALYSIS
    # ============================================================

    rows = []

    for (
        signal,
        score_band_value,
    ), group in (
        analysis
        .groupby(
            [
                "Signal",
                "Investment Score Band",
            ],
            dropna=False,
        )
    ):

        returns = pd.to_numeric(
            group["Forward Return %"],
            errors="coerce",
        ).dropna()

        benchmark_winners = (
            group["Benchmark Winner"]
            .fillna(False)
            .astype(bool)
        )

        rows.append(
            {
                "Signal": signal,
                "Investment Score Band": (
                    score_band_value
                ),
                "Recommendation Count": (
                    len(group)
                ),
                "Unique Tickers": (
                    group[
                        "ticker"
                    ]
                    .astype(str)
                    .str.upper()
                    .nunique()
                ),
                "Average 28D Return %": (
                    returns.mean()
                    if not returns.empty
                    else None
                ),
                "Median 28D Return %": (
                    returns.median()
                    if not returns.empty
                    else None
                ),
                "Positive 28D Return %": (
                    (
                        returns > 0
                    ).mean()
                    * 100
                    if not returns.empty
                    else None
                ),
                "Benchmark Winner Count": (
                    int(
                        benchmark_winners.sum()
                    )
                ),
                "Benchmark Winner %": (
                    benchmark_winners.mean()
                    * 100
                    if len(group) > 0
                    else None
                ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    # ============================================================
    # ORDER SCORE BANDS
    # ============================================================

    if not result.empty:

        score_band_order = [
            "<50",
            "50–59",
            "60–69",
            "70–74",
            "75+",
        ]

        result[
            "Investment Score Band"
        ] = pd.Categorical(
            result[
                "Investment Score Band"
            ],
            categories=score_band_order,
            ordered=True,
        )

        result = (
            result
            .sort_values(
                [
                    "Signal",
                    "Investment Score Band",
                ]
            )
            .reset_index(
                drop=True
            )
        )

    return result

def build_benchmark_winner_score_analysis(
    population: pd.DataFrame,
) -> pd.DataFrame:
    """
    Analyse the Investment Scores assigned to benchmark winners.

    This is an offline A6 calibration analysis only.

    The purpose is to determine whether stocks that subsequently
    performed strongly were receiving low Investment Scores and
    therefore being excluded from the BUY NEW pathway.

    This analysis does not modify production scoring, signals,
    thresholds, candidate selection, or portfolio decisions.
    """

    analysis = population.copy()

    # ---------------------------------------------------------
    # Benchmark winners only
    # ---------------------------------------------------------

    analysis = analysis[
        analysis["Benchmark Winner"]
        .fillna(False)
        .astype(bool)
    ].copy()

    # ---------------------------------------------------------
    # Numeric Investment Score
    # ---------------------------------------------------------

    analysis["Investment Score"] = pd.to_numeric(
        analysis["investment_score"],
        errors="coerce",
    )

    analysis = analysis[
        analysis["Investment Score"].notna()
    ].copy()

    # ---------------------------------------------------------
    # Investment Score bands
    # ---------------------------------------------------------

    def score_band(score):

        if score < 50:
            return "<50"

        if score < 60:
            return "50–59"

        if score < 70:
            return "60–69"

        if score < 75:
            return "70–74"

        return "75+"

    analysis["Investment Score Band"] = (
        analysis["Investment Score"].apply(score_band)
    )

    # ---------------------------------------------------------
    # Summary by Investment Score band
    # ---------------------------------------------------------

    rows = []

    for (
        score_band_value,
        group,
    ) in analysis.groupby(
        "Investment Score Band",
        dropna=False,
    ):

        returns = pd.to_numeric(
            group["Forward Return %"],
            errors="coerce",
        ).dropna()

        rows.append(
            {
                "Investment Score Band": score_band_value,
                "Benchmark Winner Count": len(group),
                "Unique Tickers": (
                    group["ticker"]
                    .astype(str)
                    .str.upper()
                    .nunique()
                ),
                "Average 28D Return %": (
                    returns.mean()
                    if not returns.empty
                    else None
                ),
                "Median 28D Return %": (
                    returns.median()
                    if not returns.empty
                    else None
                ),
                "Minimum Investment Score": (
                    group["Investment Score"].min()
                ),
                "Maximum Investment Score": (
                    group["Investment Score"].max()
                ),
            }
        )

    result = pd.DataFrame(rows)

    # ---------------------------------------------------------
    # Explicit score-band ordering
    # ---------------------------------------------------------

    if not result.empty:

        score_band_order = [
            "<50",
            "50–59",
            "60–69",
            "70–74",
            "75+",
        ]

        result["Investment Score Band"] = pd.Categorical(
            result["Investment Score Band"],
            categories=score_band_order,
            ordered=True,
        )

        result = (
            result
            .sort_values(
                "Investment Score Band"
            )
            .reset_index(drop=True)
        )

    return result

def build_buy_component_analysis(
    population: pd.DataFrame,
    tickers: list[str],
) -> pd.DataFrame:
    """
    Analyse realised 28D BUY performance by score components.

    This is an offline A6 calibration analysis only.

    The analysis is restricted to BUY recommendations in the
    selected calibration universe and does not modify production
    scoring, signals, thresholds, candidate selection, or
    portfolio decisions.
    """

    analysis = population.copy()

    # ---------------------------------------------------------
    # Selected calibration universe
    # ---------------------------------------------------------

    universe = {
        str(ticker).upper()
        for ticker in tickers
    }

    analysis = analysis[
        analysis["ticker"]
        .astype(str)
        .str.upper()
        .isin(universe)
    ].copy()

    # ---------------------------------------------------------
    # BUY recommendations only
    # ---------------------------------------------------------

    analysis["Signal"] = (
        analysis["signal"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    analysis = analysis[
        analysis["Signal"] == "BUY"
    ].copy()

    # ---------------------------------------------------------
    # Score bands
    # ---------------------------------------------------------

    def score_band(score):
        if pd.isna(score):
            return None

        score = float(score)

        if score < 50:
            return "<50"
        if score < 60:
            return "50–59"
        if score < 70:
            return "60–69"
        if score < 75:
            return "70–74"

        return "75+"

    analysis["Investment Score Band"] = (
        analysis["investment_score"].apply(score_band)
    )

    analysis["Technical Score"] = pd.to_numeric(
        analysis["technical_score"],
        errors="coerce",
    )

    analysis["Quality Score"] = pd.to_numeric(
        analysis["quality_score"],
        errors="coerce",
    )

    analysis["Growth Score"] = pd.to_numeric(
        analysis["growth_score"],
        errors="coerce",
    )

    analysis["Investment Score"] = pd.to_numeric(
        analysis["investment_score"],
        errors="coerce",
    )

    # ---------------------------------------------------------
    # Valid population
    # ---------------------------------------------------------

    analysis = analysis[
        analysis["Investment Score Band"].notna()
    ].copy()

    # ---------------------------------------------------------
    # Score-component bands
    # ---------------------------------------------------------

    def technical_band(score):
        if pd.isna(score):
            return None
        if score < 25:
            return "<25"
        if score < 50:
            return "25–49"
        if score < 75:
            return "50–74"
        return "75+"

    def quality_band(score):
        if pd.isna(score):
            return None
        if score < 25:
            return "<25"
        if score < 50:
            return "25–49"
        if score < 75:
            return "50–74"
        return "75+"

    def growth_band(score):
        if pd.isna(score):
            return None
        if score < 25:
            return "<25"
        if score < 50:
            return "25–49"
        if score < 75:
            return "50–74"
        return "75+"

    analysis["Technical Score Band"] = (
        analysis["Technical Score"].apply(technical_band)
    )

    analysis["Quality Score Band"] = (
        analysis["Quality Score"].apply(quality_band)
    )

    analysis["Growth Score Band"] = (
        analysis["Growth Score"].apply(growth_band)
    )

    # ---------------------------------------------------------
    # Build grouped summaries
    # ---------------------------------------------------------

    rows = []

    dimensions = [
        ("Investment Score", "Investment Score Band"),
        ("Technical Score", "Technical Score Band"),
        ("Quality Score", "Quality Score Band"),
        ("Growth Score", "Growth Score Band"),
    ]

    for dimension_name, band_column in dimensions:

        grouped = (
            analysis
            .dropna(subset=[band_column])
            .groupby(
                band_column,
                dropna=False,
            )
        )

        for band_value, group in grouped:

            returns = pd.to_numeric(
                group["Forward Return %"],
                errors="coerce",
            ).dropna()

            benchmark_winners = (
                group["Benchmark Winner"]
                .fillna(False)
                .astype(bool)
            )

            rows.append(
                {
                    "Analysis Dimension": dimension_name,
                    "Score Band": band_value,
                    "Recommendation Count": len(group),
                    "Unique Tickers": (
                        group["ticker"]
                        .astype(str)
                        .str.upper()
                        .nunique()
                    ),
                    "Average 28D Return %": (
                        returns.mean()
                        if not returns.empty
                        else None
                    ),
                    "Median 28D Return %": (
                        returns.median()
                        if not returns.empty
                        else None
                    ),
                    "Positive 28D Return %": (
                        (returns > 0).mean() * 100
                        if not returns.empty
                        else None
                    ),
                    "Benchmark Winner Count": (
                        int(benchmark_winners.sum())
                    ),
                    "Benchmark Winner %": (
                        benchmark_winners.mean() * 100
                        if len(group) > 0
                        else None
                    ),
                }
            )

    result = pd.DataFrame(rows)

    # ---------------------------------------------------------
    # Order dimensions and score bands
    # ---------------------------------------------------------

    if not result.empty:

        dimension_order = [
            "Investment Score",
            "Technical Score",
            "Quality Score",
            "Growth Score",
        ]

        score_band_order = [
            "<25",
            "25–49",
            "50–74",
            "75+",
        ]

        investment_score_band_order = [
            "<50",
            "50–59",
            "60–69",
            "70–74",
            "75+",
        ]

        result["Analysis Dimension"] = pd.Categorical(
            result["Analysis Dimension"],
            categories=dimension_order,
            ordered=True,
        )

        # Investment Score uses its own band structure.
        result["_Band Order"] = result["Score Band"].map(
            {
                "<50": 0,
                "50–59": 1,
                "60–69": 2,
                "70–74": 3,
                "75+": 4,
                "<25": 0,
                "25–49": 1,
                "50–74": 2,
            }
        )

        result = (
            result
            .sort_values(
                [
                    "Analysis Dimension",
                    "_Band Order",
                ]
            )
            .drop(
                columns=["_Band Order"]
            )
            .reset_index(drop=True)
        )

    return result


def build_investment_score_diagnostic(
    population: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    str,
]:

    required_columns = [
        "ticker",
        "recommendation_date",
        "recommendation_id",
        "signal",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "Forward Return %",
        "Benchmark Winner",
    ]

    missing = [
        column
        for column in required_columns
        if column not in population.columns
    ]

    if missing:
        raise ValueError(
            "Investment Score diagnostic missing columns: "
            + ", ".join(missing)
        )

    # Convert the actual population column names into the
    # column names used by the diagnostic logic.
    df = population.rename(
        columns={
            "ticker": "Ticker",
            "recommendation_date": "Evaluation Date",
            "recommendation_id": "Recommendation ID",
            "signal": "Signal",
            "investment_score": "Investment Score",
            "technical_score": "Technical Score",
            "quality_score": "Quality Score",
            "growth_score": "Growth Score",
            "confidence_score": "Confidence Score",
        }
    ).copy()

    numeric_columns = [
        "Investment Score",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Confidence Score",
        "Forward Return %",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # ---------------------------------------------------------------
    # 1. WINNER DETAIL
    # ---------------------------------------------------------------

    winners = df[
        df["Benchmark Winner"] == True
    ].copy()

    winners = winners.sort_values(
        ["Forward Return %", "Ticker"],
        ascending=[False, True],
    )

    winner_detail = winners[
        [
            "Ticker",
            "Evaluation Date",
            "Recommendation ID",
            "Signal",
            "Investment Score",
            "Technical Score",
            "Quality Score",
            "Growth Score",
            "Confidence Score",
            "Forward Return %",
        ]
    ].reset_index(drop=True)

    # ---------------------------------------------------------------
    # 2. WINNER VS NON-WINNER
    # ---------------------------------------------------------------

    winner_flag = (
        df["Benchmark Winner"]
        .fillna(False)
        .astype(bool)
    )

    comparison_rows = []

    for label, subset in [
        ("Benchmark Winners", df[winner_flag]),
        ("Non-Winners", df[~winner_flag]),
    ]:

        comparison_rows.append(
            {
                "Population": label,
                "Recommendation Count": len(subset),
                "Unique Tickers": subset["Ticker"].nunique(),
                "Average Investment Score":
                    subset["Investment Score"].mean(),
                "Median Investment Score":
                    subset["Investment Score"].median(),
                "Average Technical Score":
                    subset["Technical Score"].mean(),
                "Average Quality Score":
                    subset["Quality Score"].mean(),
                "Average Growth Score":
                    subset["Growth Score"].mean(),
                "Average Confidence Score":
                    subset["Confidence Score"].mean(),
                "Average 28D Return %":
                    subset["Forward Return %"].mean(),
                "Median 28D Return %":
                    subset["Forward Return %"].median(),
                "Positive 28D Return %":
                    (
                        subset["Forward Return %"] > 0
                    ).mean() * 100
                    if len(subset)
                    else None,
            }
        )

    winner_comparison = pd.DataFrame(
        comparison_rows
    )

    # ---------------------------------------------------------------
    # 3. COMPONENT COMPARISON
    # ---------------------------------------------------------------

    component_rows = []

    for component in [
        "Investment Score",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Confidence Score",
    ]:

        winner_values = df.loc[
            winner_flag,
            component,
        ].dropna()

        non_winner_values = df.loc[
            ~winner_flag,
            component,
        ].dropna()

        component_rows.append(
            {
                "Component": component,
                "Winner Count": len(winner_values),
                "Non-Winner Count": len(non_winner_values),
                "Winner Average": (
                    winner_values.mean()
                    if not winner_values.empty
                    else None
                ),
                "Non-Winner Average": (
                    non_winner_values.mean()
                    if not non_winner_values.empty
                    else None
                ),
                "Winner Median": (
                    winner_values.median()
                    if not winner_values.empty
                    else None
                ),
                "Non-Winner Median": (
                    non_winner_values.median()
                    if not non_winner_values.empty
                    else None
                ),
            }
        )

    component_comparison = pd.DataFrame(
        component_rows
    )

    # ---------------------------------------------------------------
    # 4. SCORE RECONSTRUCTION
    # ---------------------------------------------------------------

    reconstruction_rows = []

    for _, row in df.iterrows():

        technical_score = row["Technical Score"]
        quality_score = row["Quality Score"]
        growth_score = row["Growth Score"]

        if any(
            pd.isna(value)
            for value in [
                technical_score,
                quality_score,
                growth_score,
            ]
        ):
            continue

        reconstructed_score = calculate_investment_score(
            technical_score,
            quality_score,
            growth_score,
        )

        reconstructed_score = round(
            float(reconstructed_score)
        )

        stored_score = row["Investment Score"]

        reconstruction_rows.append(
            {
                "Ticker": row["Ticker"],
                "Evaluation Date": row["Evaluation Date"],
                "Recommendation ID": row["Recommendation ID"],
                "Signal": row["Signal"],
                "Stored Investment Score": stored_score,
                "Reconstructed Investment Score":
                    reconstructed_score,
                "Difference": (
                    reconstructed_score - stored_score
                    if not pd.isna(stored_score)
                    else None
                ),
                "Technical Score":
                    technical_score,
                "Quality Score":
                    quality_score,
                "Growth Score":
                    growth_score,
                "Benchmark Winner":
                    row["Benchmark Winner"],
                "Forward Return %":
                    row["Forward Return %"],
            }
        )

    score_reconstruction = pd.DataFrame(
        reconstruction_rows
    )

    # ---------------------------------------------------------------
    # 5. ASSESSMENT
    # ---------------------------------------------------------------

    assessment = "INSUFFICIENT EVIDENCE"

    winner_row = winner_comparison[
        winner_comparison["Population"]
        == "Benchmark Winners"
    ]

    non_winner_row = winner_comparison[
        winner_comparison["Population"]
        == "Non-Winners"
    ]

    if (
        not winner_row.empty
        and not non_winner_row.empty
    ):

        winner_score = float(
            winner_row.iloc[0]["Average Investment Score"]
        )

        non_winner_score = float(
            non_winner_row.iloc[0]["Average Investment Score"]
        )

        if winner_score < non_winner_score:
            assessment = (
                "INVESTMENT SCORE SUPPRESSION "
                "SUPPORTED FOR INVESTIGATION"
            )

    if not score_reconstruction.empty:

        mismatches = score_reconstruction[
            score_reconstruction["Difference"].abs()
            > 0.01
        ]

        if not mismatches.empty:
            assessment = (
                "PRODUCTION SCORE RECONSTRUCTION "
                "MISMATCH"
            )


        if not score_reconstruction.empty:
            print()
            print("INVESTMENT SCORE RECONSTRUCTION")
            print("=" * 78)

            mismatches = score_reconstruction[
                score_reconstruction["Difference"].abs() > 0.01
            ]

            print(
                f"Total reconstructed: "
                f"{len(score_reconstruction)}"
            )

            print(
                f"Mismatches: "
                f"{len(mismatches)}"
            )

            if not mismatches.empty:
                print()
                print(
                    mismatches[
                        [
                            "Ticker",
                            "Evaluation Date",
                            "Recommendation ID",
                            "Stored Investment Score",
                            "Reconstructed Investment Score",
                            "Difference",
                            "Technical Score",
                            "Quality Score",
                            "Growth Score",
                            "Benchmark Winner",
                        ]
                    ].to_string(index=False)
                )

    return (
        winner_detail,
        winner_comparison,
        component_comparison,
        score_reconstruction,
        assessment,
    )

def main():

    p = argparse.ArgumentParser()

    p.add_argument(
        '--start-date',
        required=True,
    )

    p.add_argument(
        '--end-date',
        required=True,
    )

    p.add_argument(
        '--universe',
        choices=['SP500', 'NASDAQ100', 'BOTH'],
        default='BOTH',
    )

    p.add_argument(
        '--top-n',
        type=int,
        default=10,
    )

    p.add_argument(
        '--forward-days',
        type=int,
        default=28,
    )

    p.add_argument(
        '--db-path',
        default=None,
    )

    a = p.parse_args()

    path = (
        Path(a.db_path)
        if a.db_path
        else db_path()
    )

    history = load_recommendations(path)
    audits = load_audits(path)

    tickers = load_universe(
        a.universe
    )

    price_start = (
        pd.Timestamp(a.start_date)
        - pd.Timedelta(days=10)
    )

    price_end = (
        pd.Timestamp(a.end_date)
        + pd.Timedelta(
            days=a.forward_days + 10
        )
    )

    closes = load_historical_closes(
        tickers,
        price_start,
        price_end,
    )

    rows = []

    # ============================================================
    # BENCHMARK WINNER ANALYSIS
    # ============================================================

    for t0 in pd.date_range(
        a.start_date,
        a.end_date,
        freq='B',
    ):

        winners = rank_forward_winners(
            tickers,
            closes,
            t0,
            a.forward_days,
            a.top_n,
        )

        for _, b in winners.iterrows():

            obs = latest_recommendation(
                history,
                b.Ticker,
                t0,
            )

            action = latest_audit_action(
                audits,
                b.Ticker,
                t0,
            )

            row = {
                'Evaluation Date':
                    t0.date().isoformat(),

                'Universe':
                    a.universe,

                'Ticker':
                    b.Ticker,

                'Forward Return %':
                    round(
                        float(
                            b['Forward Return %']
                        ),
                        4,
                    ),

                'Forward Rank':
                    int(
                        b['Forward Rank']
                    ),

                'Benchmark Top N':
                    True,

                'Recommendation ID':
                    None,

                'Recommendation Date':
                    None,

                'Signal':
                    None,

                'Investment Score':
                    None,

                'Technical Score':
                    None,

                'Quality Score':
                    None,

                'Growth Score':
                    None,

                'Confidence Score':
                    None,

                'Entry Quality':
                    None,

                'Entry Quality Mode':
                    None,

                'Extension SMA50 %':
                    None,

                'Extension SMA200 %':
                    None,

                'Observed Final Action':
                    action,
            }

            if obs is not None:

                for out, col in [
                    (
                        'recommendation_id',
                        'Recommendation ID',
                    ),
                    (
                        'recommendation_date',
                        'Recommendation Date',
                    ),
                    (
                        'signal',
                        'Signal',
                    ),
                    (
                        'investment_score',
                        'Investment Score',
                    ),
                    (
                        'technical_score',
                        'Technical Score',
                    ),
                    (
                        'quality_score',
                        'Quality Score',
                    ),
                    (
                        'growth_score',
                        'Growth Score',
                    ),
                    (
                        'confidence_score',
                        'Confidence Score',
                    ),
                    (
                        'entry_quality',
                        'Entry Quality',
                    ),
                    (
                        'entry_quality_mode',
                        'Entry Quality Mode',
                    ),
                    (
                        'extension_sma50_pct',
                        'Extension SMA50 %',
                    ),
                    (
                        'extension_sma200_pct',
                        'Extension SMA200 %',
                    ),
                ]:

                    value = obs[out]

                    if (
                        col == 'Recommendation Date'
                        and pd.notna(value)
                    ):
                        value = value.date().isoformat()

                    row[col] = value

            cls, detail_text = classify(
                row
            )

            row[
                'Miss Classification'
            ] = cls

            row[
                'Miss Detail'
            ] = detail_text

            rows.append(
                row
            )

    if not rows:

        raise RuntimeError(
            'No benchmark observations produced.'
        )

    detail = pd.DataFrame(
        rows
    )

    # ============================================================
    # BENCHMARK-WINNER SCORE-BAND SUMMARY
    # ============================================================

    score_band_summary = (
        pd.DataFrame()
    )

    working = detail.copy()

    working[
        'Investment Score'
    ] = pd.to_numeric(
        working[
            'Investment Score'
        ],
        errors='coerce',
    )

    working[
        'Forward Return %'
    ] = pd.to_numeric(
        working[
            'Forward Return %'
        ],
        errors='coerce',
    )

    working[
        'Technical Score'
    ] = pd.to_numeric(
        working[
            'Technical Score'
        ],
        errors='coerce',
    )

    working[
        'Quality Score'
    ] = pd.to_numeric(
        working[
            'Quality Score'
        ],
        errors='coerce',
    )

    working[
        'Growth Score'
    ] = pd.to_numeric(
        working[
            'Growth Score'
        ],
        errors='coerce',
    )

    working = working[
        working[
            'Recommendation ID'
        ].notna()
        &
        working[
            'Investment Score'
        ].notna()
    ].copy()

    if not working.empty:

        working = (
            working
            .sort_values(
                [
                    'Recommendation ID',
                    'Evaluation Date',
                ]
            )
            .drop_duplicates(
                subset=[
                    'Recommendation ID'
                ],
                keep='first',
            )
        )

        working[
            '_Score Band'
        ] = pd.cut(
            working[
                'Investment Score'
            ],
            bins=[
                float('-inf'),
                50,
                60,
                70,
                75,
                float('inf'),
            ],
            labels=[
                '<50',
                '50–59',
                '60–69',
                '70–74',
                '75+',
            ],
            right=False,
        )

        summary_rows = []

        for band in [
            '<50',
            '50–59',
            '60–69',
            '70–74',
            '75+',
        ]:

            group = working[
                working[
                    '_Score Band'
                ] == band
            ].copy()

            if group.empty:

                summary_rows.append(
                    {
                        'Investment Score Band':
                            band,

                        'Unique SMA Observations':
                            0,

                        'Average 28D Return %':
                            None,

                        'Median 28D Return %':
                            None,

                        'Positive 28D Return %':
                            None,

                        'Benchmark Winner Count':
                            0,

                        'BUY NEW Captured Count':
                            0,

                        'BUY NEW Capture Rate %':
                            None,

                        'Average Technical Score':
                            None,

                        'Average Quality Score':
                            None,

                        'Average Growth Score':
                            None,
                    }
                )

                continue

            returns = group[
                'Forward Return %'
            ].dropna()

            benchmark_count = len(
                group
            )

            captured = group[
                group[
                    'Observed Final Action'
                ]
                .fillna('')
                .astype(str)
                .str.strip()
                .str.upper()
                == 'BUY NEW'
            ]

            summary_rows.append(
                {
                    'Investment Score Band':
                        band,

                    'Unique SMA Observations':
                        benchmark_count,

                    'Average 28D Return %':
                        round(
                            returns.mean(),
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Median 28D Return %':
                        round(
                            returns.median(),
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Positive 28D Return %':
                        round(
                            (
                                returns > 0
                            ).mean()
                            * 100,
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Benchmark Winner Count':
                        benchmark_count,

                    'BUY NEW Captured Count':
                        len(captured),

                    'BUY NEW Capture Rate %':
                        round(
                            len(captured)
                            / benchmark_count
                            * 100,
                            2,
                        ),

                    'Average Technical Score':
                        round(
                            group[
                                'Technical Score'
                            ].mean(),
                            2,
                        ),

                    'Average Quality Score':
                        round(
                            group[
                                'Quality Score'
                            ].mean(),
                            2,
                        ),

                    'Average Growth Score':
                        round(
                            group[
                                'Growth Score'
                            ].mean(),
                            2,
                        ),
                }
            )

        score_band_summary = (
            pd.DataFrame(
                summary_rows
            )
        )

    # ============================================================
    # FULL SMA RECOMMENDATION POPULATION
    # ============================================================

    population = history.copy()

    population[
        'recommendation_date'
    ] = pd.to_datetime(
        population[
            'recommendation_date'
        ],
        errors='coerce',
    )

    population[
        'investment_score'
    ] = pd.to_numeric(
        population[
            'investment_score'
        ],
        errors='coerce',
    )

    population[
        'technical_score'
    ] = pd.to_numeric(
        population[
            'technical_score'
        ],
        errors='coerce',
    )

    population[
        'quality_score'
    ] = pd.to_numeric(
        population[
            'quality_score'
        ],
        errors='coerce',
    )

    population[
        'growth_score'
    ] = pd.to_numeric(
        population[
            'growth_score'
        ],
        errors='coerce',
    )

    population = population[
        population[
            'recommendation_date'
        ].between(
            pd.Timestamp(
                a.start_date
            ),
            pd.Timestamp(
                a.end_date
            ),
        )
        &
        population[
            'ticker'
        ]
        .astype(str)
        .str.upper()
        .isin(
            [str(t).upper() for t in tickers]
        )
    ].copy()
    
    population = population[
        population[
            'recommendation_id'
        ].notna()
        &
        population[
            'investment_score'
        ].notna()
    ].copy()

    # ------------------------------------------------------------
    # One row per unique SMA recommendation
    # ------------------------------------------------------------

    population = (
        population
        .sort_values(
            [
                'recommendation_id',
                'recommendation_date',
            ]
        )
        .drop_duplicates(
            subset=[
                'recommendation_id'
            ],
            keep='first',
        )
    )

    # ------------------------------------------------------------
    # Calculate realised forward return
    # ------------------------------------------------------------

    forward_returns = []

    for _, recommendation in (
        population.iterrows()
    ):

        return_pct = (
            realised_forward_return(
                closes,
                recommendation[
                    'ticker'
                ],
                recommendation[
                    'recommendation_date'
                ],
                a.forward_days,
            )
        )

        forward_returns.append(
            return_pct
        )

    population[
        'Forward Return %'
    ] = forward_returns

    # ============================================================
    # IDENTIFY BENCHMARK WINNERS
    # ============================================================

    benchmark_keys = set()

    if not detail.empty:

        benchmark_keys = set(
            zip(
                detail[
                    'Evaluation Date'
                ],
                detail[
                    'Ticker'
                ]
                .astype(str)
                .str.upper(),
            )
        )

    population[
        'Benchmark Winner'
    ] = [
        (
            recommendation_date
            .date()
            .isoformat(),
            str(ticker).upper(),
        )
        in benchmark_keys
        for recommendation_date, ticker
        in zip(
            population[
                'recommendation_date'
            ],
            population[
                'ticker'
            ],
        )
    ]

    # ============================================================
    # SCORE-BAND POPULATION SUMMARY
    # ============================================================

    population_score_band_summary = (
        pd.DataFrame()
    )

    if not population.empty:

        population[
            '_Score Band'
        ] = pd.cut(
            population[
                'investment_score'
            ],
            bins=[
                float('-inf'),
                50,
                60,
                70,
                75,
                float('inf'),
            ],
            labels=[
                '<50',
                '50–59',
                '60–69',
                '70–74',
                '75+',
            ],
            right=False,
        )

        population_rows = []

        for band in [
            '<50',
            '50–59',
            '60–69',
            '70–74',
            '75+',
        ]:

            group = population[
                population[
                    '_Score Band'
                ] == band
            ].copy()

            returns = group[
                'Forward Return %'
            ].dropna()

            benchmark_winners = group[
                group[
                    'Benchmark Winner'
                ]
            ]

            population_rows.append(
                {
                    'Investment Score Band':
                        band,

                    'Recommendation Count':
                        len(group),

                    'Unique Tickers':
                        group[
                            'ticker'
                        ]
                        .astype(str)
                        .str.upper()
                        .nunique(),

                    'Average 28D Return %':
                        round(
                            returns.mean(),
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Median 28D Return %':
                        round(
                            returns.median(),
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Positive 28D Return %':
                        round(
                            (
                                returns > 0
                            ).mean()
                            * 100,
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Benchmark Winner Count':
                        len(
                            benchmark_winners
                        ),

                    'Benchmark Winner %':
                        round(
                            len(
                                benchmark_winners
                            )
                            / len(group)
                            * 100,
                            2,
                        )
                        if len(group) > 0
                        else None,

                    'Average Investment Score':
                        round(
                            group[
                                'investment_score'
                            ].mean(),
                            2,
                        ),

                    'Average Technical Score':
                        round(
                            group[
                                'technical_score'
                            ].mean(),
                            2,
                        ),

                    'Average Quality Score':
                        round(
                            group[
                                'quality_score'
                            ].mean(),
                            2,
                        ),

                    'Average Growth Score':
                        round(
                            group[
                                'growth_score'
                            ].mean(),
                            2,
                        ),
                }
            )

        population_score_band_summary = (
            pd.DataFrame(
                population_rows
            )
        )

    # ============================================================
    # INDIVIDUAL INVESTMENT SCORE ANALYSIS
    # ============================================================

    individual_score_summary = (
        pd.DataFrame()
    )

    if not population.empty:

        score_rows = []

        for score in sorted(
            population[
                'investment_score'
            ]
            .dropna()
            .unique()
        ):

            group = population[
                population[
                    'investment_score'
                ] == score
            ].copy()

            returns = group[
                'Forward Return %'
            ].dropna()

            benchmark_winners = group[
                group[
                    'Benchmark Winner'
                ]
            ]

            score_rows.append(
                {
                    'Investment Score':
                        int(score),

                    'Recommendation Count':
                        len(group),

                    'Unique Tickers':
                        group[
                            'ticker'
                        ]
                        .astype(str)
                        .str.upper()
                        .nunique(),

                    'Average 28D Return %':
                        round(
                            returns.mean(),
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Median 28D Return %':
                        round(
                            returns.median(),
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Positive 28D Return %':
                        round(
                            (
                                returns > 0
                            ).mean()
                            * 100,
                            2,
                        )
                        if not returns.empty
                        else None,

                    'Benchmark Winner Count':
                        len(
                            benchmark_winners
                        ),

                    'Benchmark Winner %':
                        round(
                            len(
                                benchmark_winners
                            )
                            / len(group)
                            * 100,
                            2,
                        )
                        if len(group) > 0
                        else None,

                    'Average Technical Score':
                        round(
                            group[
                                'technical_score'
                            ].mean(),
                            2,
                        ),

                    'Average Quality Score':
                        round(
                            group[
                                'quality_score'
                            ].mean(),
                            2,
                        ),

                    'Average Growth Score':
                        round(
                            group[
                                'growth_score'
                            ].mean(),
                            2,
                        ),
                }
            )

        individual_score_summary = (
            pd.DataFrame(
                score_rows
            )
        )

    # ============================================================
    # SIGNAL × INVESTMENT SCORE ANALYSIS
    # ============================================================

    signal_score_summary = (
        build_signal_score_analysis(
            population=population,
            tickers=tickers,
        )
    )

    # ============================================================
    # BUY COMPONENT ANALYSIS
    # ============================================================

    buy_component_summary = (
        build_buy_component_analysis(
            population=population,
            tickers=tickers,
        )
    )

    # ============================================================
    # BENCHMARK WINNER × INVESTMENT SCORE ANALYSIS
    # ============================================================

    benchmark_winner_score_summary = (
        build_benchmark_winner_score_analysis(
            population=population,
        )
    )

    # ============================================================
    # OUTPUT
    # ============================================================

    out = (
        Path(__file__).resolve().parent
        / 'output'
    )

    csv, xlsx = write_report(
        detail,
        out,
        f'buy_new_calibration_'
        f'{a.start_date.replace("-", "")}_'
        f'{a.end_date.replace("-", "")}',
    )

    # ------------------------------------------------------------
    # Benchmark-winner score bands
    # ------------------------------------------------------------

    summary_csv = (
        out
        / f'buy_new_score_band_summary_'
          f'{a.start_date.replace("-", "")}_'
          f'{a.end_date.replace("-", "")}.csv'
    )

    # ------------------------------------------------------------
    # Signal × Investment Score analysis
    # ------------------------------------------------------------

    signal_score_summary_path = (
        out
        / f'buy_new_signal_score_'
          f'{a.start_date.replace("-", "")}_'
          f'{a.end_date.replace("-", "")}.csv'
    )

    buy_component_summary_path = (
        out
        / f'buy_new_component_analysis_'
        f'{a.start_date.replace("-", "")}_'
        f'{a.end_date.replace("-", "")}.csv'
    )

    benchmark_winner_score_summary_path = (
        out
        / f'buy_new_benchmark_winner_score_'
        f'{a.start_date.replace("-", "")}_'
        f'{a.end_date.replace("-", "")}.csv'
    )

    print(
        "Population columns:",
        list(population.columns),
    )

    signal_score_summary.to_csv(
        signal_score_summary_path,
        index=False,
    )

    print(
        f'Signal × Investment Score summary: '
        f'{signal_score_summary_path}'
    )

    buy_component_summary.to_csv(
        buy_component_summary_path,
        index=False,
    )
    
    print(
        f'BUY component analysis: '
        f'{buy_component_summary_path}'
    )

    benchmark_winner_score_summary.to_csv(
        benchmark_winner_score_summary_path,
        index=False,
    )

    print(
        f'Benchmark winner × Investment Score analysis: '
        f'{benchmark_winner_score_summary_path}'
    )

    # ------------------------------------------------------------
    # Benchmark-winner score bands
    # ------------------------------------------------------------

    summary_csv = (
        out
        / f'buy_new_score_band_summary_'
          f'{a.start_date.replace("-", "")}_'
          f'{a.end_date.replace("-", "")}.csv'
    )

    score_band_summary.to_csv(
        summary_csv,
        index=False,
    )

    print(
        f'Score-band summary: '
        f'{summary_csv}'
    )

    

    # ------------------------------------------------------------
    # Full SMA population score bands
    # ------------------------------------------------------------

    population_summary_csv = (
        out
        / f'buy_new_score_band_population_'
          f'{a.start_date.replace("-", "")}_'
          f'{a.end_date.replace("-", "")}.csv'
    )

    population_score_band_summary.to_csv(
        population_summary_csv,
        index=False,
    )

    print(
        f'Population score-band summary: '
        f'{population_summary_csv}'
    )

    print(
        "INVESTMENT SCORE DIAGNOSTIC POPULATION COLUMNS:",
        list(population.columns),
    )

    print(
        "INVESTMENT SCORE DIAGNOSTIC POPULATION SHAPE:",
        population.shape,
    )

    print(
        "INVESTMENT SCORE DIAGNOSTIC SAMPLE:",
        population.head(3).to_dict("records"),
    )



    (
        investment_score_winners,
        investment_score_comparison,
        investment_score_components,
        investment_score_reconstruction,
        investment_score_assessment,
    ) = build_investment_score_diagnostic(
        population
    )
    # ------------------------------------------------------------
    # Individual Investment Score analysis
    # ------------------------------------------------------------

    individual_score_csv = (
        out
        / f'buy_new_score_individual_'
          f'{a.start_date.replace("-", "")}_'
          f'{a.end_date.replace("-", "")}.csv'
    )

    individual_score_summary.to_csv(
        individual_score_csv,
        index=False,
    )

    print(
        f'Individual score summary: '
        f'{individual_score_csv}'
    )


    investment_score_winners.to_csv(
        out
        / f"buy_new_investment_score_winners_"
        f"{a.start_date.replace('-', '')}_"
        f"{a.end_date.replace('-', '')}.csv",
        index=False,
    )

    investment_score_comparison.to_csv(
        out
        / f"buy_new_investment_score_comparison_"
        f"{a.start_date.replace('-', '')}_"
        f"{a.end_date.replace('-', '')}.csv",
        index=False,
    )

    investment_score_components.to_csv(
        out
        / f"buy_new_investment_score_components_"
        f"{a.start_date.replace('-', '')}_"
        f"{a.end_date.replace('-', '')}.csv",
        index=False,
    )

    investment_score_reconstruction.to_csv(
        out
        / f"buy_new_investment_score_reconstruction_"
        f"{a.start_date.replace('-', '')}_"
        f"{a.end_date.replace('-', '')}.csv",
        index=False,
    )

    print()
    print("INVESTMENT SCORE ASSESSMENT")
    print("=" * 78)
    print(investment_score_assessment)

    # ------------------------------------------------------------
    # Final output
    # ------------------------------------------------------------

    print(
        f'Calibration rows: '
        f'{len(detail)}'
    )

    print(
        f'CSV: {csv}'
    )

    print(
        f'Excel: {xlsx}'
    )

if __name__ == '__main__': main()
