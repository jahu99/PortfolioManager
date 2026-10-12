"""
Calibration experiment:
Test whether stocks ranked 201-400 by Technical Score
would produce strong Investment Scores if allowed through
the production scoring pipeline.

IMPORTANT:
- Calibration only.
- Does NOT modify production logic.
- Does NOT change scanner.py.
- Does NOT write to production data.
"""

import sys
from pathlib import Path

import pandas as pd


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORT PRODUCTION COMPONENTS
# ============================================================

from data.universe import get_market_universe

from analysis.scanner import run_market_scan

try:
    from analysis.universe_filter import filter_investable_universe
except ImportError:
    filter_investable_universe = None


# ============================================================
# FIND PRODUCTION SCORING FUNCTIONS
# ============================================================

score_quality = None
score_growth = None
calculate_investment_score = None


# Try likely production modules.
scoring_modules = [
    "analysis.scorer",
    "analysis.scoring",
    "analysis.fundamental_scorer",
    "analysis.investment_scorer",
    "analysis.score_engine",
]


for module_name in scoring_modules:

    try:

        module = __import__(
            module_name,
            fromlist=[
                "score_quality",
                "score_growth",
                "calculate_investment_score",
            ],
        )

        if score_quality is None and hasattr(
            module,
            "score_quality"
        ):
            score_quality = module.score_quality

        if score_growth is None and hasattr(
            module,
            "score_growth"
        ):
            score_growth = module.score_growth

        if calculate_investment_score is None and hasattr(
            module,
            "calculate_investment_score"
        ):
            calculate_investment_score = (
                module.calculate_investment_score
            )

    except ImportError:
        continue


# ============================================================
# VALIDATE IMPORTS
# ============================================================

print()
print("=" * 70)
print("TECHNICAL RANK 201-400 CALIBRATION EXPERIMENT")
print("=" * 70)
print()

print(
    "score_quality:",
    score_quality
)

print(
    "score_growth:",
    score_growth
)

print(
    "calculate_investment_score:",
    calculate_investment_score
)

print()


if calculate_investment_score is None:

    raise RuntimeError(
        "\nCould not locate production "
        "calculate_investment_score().\n"
        "The experiment has NOT run.\n"
        "Check the module containing that function."
    )


# ============================================================
# LOAD UNIVERSE
# ============================================================

print("Loading universe...")

raw_universe = get_market_universe()

print(
    f"Raw universe: {len(raw_universe)}"
)


# ============================================================
# INVESTABILITY FILTER
# ============================================================

if filter_investable_universe is not None:

    print("Applying investability filter...")

    investable = filter_investable_universe(
        raw_universe
    )

else:

    print(
        "WARNING: filter_investable_universe() "
        "could not be imported."
    )

    print(
        "Using raw universe for scanner."
    )

    investable = raw_universe


print(
    f"Investable universe: {len(investable)}"
)

print()


# ============================================================
# COMPLETE TECHNICAL RANKING
# ============================================================

print(
    "Running complete technical ranking..."
)

print(
    "This is deliberately using "
    "limit=len(investable)."
)

technical_candidates = run_market_scan(
    investable,
    limit=len(investable)
)


print()
print(
    f"Technical candidates: "
    f"{len(technical_candidates)}"
)


# ============================================================
# NORMALISE RANKING
# ============================================================

technical_candidates = sorted(
    technical_candidates,
    key=lambda x:
        x.get(
            "Technical Score",
            0
        ),
    reverse=True
)


# ============================================================
# DISPLAY CUTOFF
# ============================================================

if len(technical_candidates) >= 200:

    cutoff_200 = technical_candidates[199]

    print()
    print(
        "CURRENT PRODUCTION TOP-200 CUTOFF"
    )

    print(
        f"Rank 200: "
        f"{cutoff_200.get('Ticker')} "
        f"| Technical Score: "
        f"{cutoff_200.get('Technical Score')}"
    )


# ============================================================
# EXTRACT RANKS 201-400
# ============================================================

lower_bound = 201
upper_bound = min(
    400,
    len(technical_candidates)
)

experiment_candidates = (
    technical_candidates[
        lower_bound - 1:
        upper_bound
    ]
)


print()
print("=" * 70)
print(
    f"EXPERIMENT POPULATION: "
    f"TECHNICAL RANKS {lower_bound}-{upper_bound}"
)
print("=" * 70)
print()

print(
    f"Candidates: "
    f"{len(experiment_candidates)}"
)


# ============================================================
# HELPER: GET FUNDAMENTALS
# ============================================================

def get_fundamentals(candidate):

    ticker = candidate.get(
        "Ticker"
    )

    # Some scanner implementations retain
    # the dataframe only.  The dataframe's latest
    # row may contain the available fundamental data.

    df = candidate.get(
        "df"
    )

    if df is None:
        return {}

    try:

        latest = df.iloc[-1]

        return latest.to_dict()

    except Exception:

        return {}


# ============================================================
# SCORE ONE CANDIDATE
# ============================================================

def score_candidate(candidate):

    ticker = candidate.get(
        "Ticker"
    )

    technical_score = float(
        candidate.get(
            "Technical Score",
            0
        )
        or 0
    )

    fundamentals = get_fundamentals(
        candidate
    )

    quality_score = None
    growth_score = None
    investment_score = None

    quality_error = None
    growth_error = None
    investment_error = None

    # --------------------------------------------------------
    # QUALITY
    # --------------------------------------------------------

    if score_quality is not None:

        try:

            quality_result = score_quality(
                fundamentals
            )

            if isinstance(
                quality_result,
                tuple
            ):

                quality_score = (
                    quality_result[0]
                )

            elif isinstance(
                quality_result,
                dict
            ):

                quality_score = (
                    quality_result.get(
                        "Quality Score"
                    )
                )

                if quality_score is None:

                    quality_score = (
                        quality_result.get(
                            "quality_score"
                        )
                    )

            else:

                quality_score = (
                    quality_result
                )

        except Exception as e:

            quality_error = str(e)

    # --------------------------------------------------------
    # GROWTH
    # --------------------------------------------------------

    if score_growth is not None:

        try:

            growth_result = score_growth(
                fundamentals
            )

            if isinstance(
                growth_result,
                dict
            ):

                growth_score = (
                    growth_result.get(
                        "Growth Score"
                    )
                )

                if growth_score is None:

                    growth_score = (
                        growth_result.get(
                            "growth_score"
                        )
                    )

            elif isinstance(
                growth_result,
                tuple
            ):

                growth_score = (
                    growth_result[0]
                )

            else:

                growth_score = (
                    growth_result
                )

        except Exception as e:

            growth_error = str(e)

    # --------------------------------------------------------
    # INVESTMENT SCORE
    # --------------------------------------------------------

    if (
        quality_score is not None
        and growth_score is not None
    ):

        try:

            investment_score = (
                calculate_investment_score(
                    technical_score,
                    float(quality_score),
                    float(growth_score)
                )
            )

        except Exception as e:

            investment_error = str(e)

    return {
        "Ticker": ticker,
        "Technical Score": technical_score,
        "Quality Score": quality_score,
        "Growth Score": growth_score,
        "Investment Score": investment_score,
        "Quality Error": quality_error,
        "Growth Error": growth_error,
        "Investment Error": investment_error,
    }


# ============================================================
# RUN EXPERIMENT
# ============================================================

results = []

for index, candidate in enumerate(
    experiment_candidates,
    start=lower_bound
):

    ticker = candidate.get(
        "Ticker"
    )

    result = score_candidate(
        candidate
    )

    result["Technical Rank"] = index

    results.append(
        result
    )

    print(
        f"{index:>3} | "
        f"{ticker:<8} | "
        f"T={result['Technical Score']} | "
        f"Q={result['Quality Score']} | "
        f"G={result['Growth Score']} | "
        f"I={result['Investment Score']}"
    )


# ============================================================
# DATAFRAME
# ============================================================

results_df = pd.DataFrame(
    results
)

results_df = results_df[
    [
        "Technical Rank",
        "Ticker",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Investment Score",
        "Quality Error",
        "Growth Error",
        "Investment Error",
    ]
]


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 70)
print("EXPERIMENT SUMMARY")
print("=" * 70)
print()

print(
    f"Technical ranks tested: "
    f"{lower_bound}-{upper_bound}"
)

print(
    f"Candidates tested: "
    f"{len(results_df)}"
)


scored = results_df[
    results_df[
        "Investment Score"
    ].notna()
]


print(
    f"Successfully Investment-scored: "
    f"{len(scored)}"
)


if len(scored) > 0:

    eligible_75 = scored[
        scored[
            "Investment Score"
        ] >= 75
    ]

    print(
        f"Investment Score >= 75: "
        f"{len(eligible_75)}"
    )

    print(
        f"Percentage >= 75: "
        f"{len(eligible_75) / len(scored) * 100:.1f}%"
    )

    print()

    print(
        "Investment Score distribution:"
    )

    print(
        scored[
            "Investment Score"
        ].describe()
    )


# ============================================================
# TOP RESULTS BELOW CURRENT CUTOFF
# ============================================================

print()
print("=" * 70)
print(
    "STRONGEST INVESTMENT SCORES BELOW "
    "CURRENT TECHNICAL CUTOFF"
)
print("=" * 70)
print()


top_results = (
    scored
    .sort_values(
        "Investment Score",
        ascending=False
    )
    .head(20)
)

if len(top_results) > 0:

    print(
        top_results[
            [
                "Technical Rank",
                "Ticker",
                "Technical Score",
                "Quality Score",
                "Growth Score",
                "Investment Score",
            ]
        ].to_string(
            index=False
        )
    )

else:

    print(
        "No successfully scored candidates."
    )


# ============================================================
# MU / NBIS
# ============================================================

print()
print("=" * 70)
print("MU / NBIS")
print("=" * 70)
print()

for ticker in [
    "MU",
    "NBIS",
]:

    row = results_df[
        results_df[
            "Ticker"
        ] == ticker
    ]

    if row.empty:

        print(
            f"{ticker}: NOT IN RANKS "
            f"{lower_bound}-{upper_bound}"
        )

    else:

        print(
            row[
                [
                    "Technical Rank",
                    "Ticker",
                    "Technical Score",
                    "Quality Score",
                    "Growth Score",
                    "Investment Score",
                    "Quality Error",
                    "Growth Error",
                    "Investment Error",
                ]
            ].to_string(
                index=False
            )
        )


# ============================================================
# SAVE CALIBRATION OUTPUT
# ============================================================

output_dir = (
    PROJECT_ROOT
    / "calibration"
    / "output"
)

output_dir.mkdir(
    parents=True,
    exist_ok=True
)

output_file = (
    output_dir
    / "technical_ranks_201_400.csv"
)

results_df.to_csv(
    output_file,
    index=False
)


print()
print(
    f"Output saved to: "
    f"{output_file}"
)

print()
print(
    "PRODUCTION CODE WAS NOT CHANGED."
)

print()
