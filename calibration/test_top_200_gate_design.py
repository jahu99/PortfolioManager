"""
Calibration experiment:
Determine how the technical candidate gate should be constructed.

This compares alternative technical-gating strategies before
fundamental scoring:

A. Current production: top 200 by Technical Score
B. Technical Score >= 80
C. Top 300 by Technical Score
D. Top 400 by Technical Score
E. Technical Score >= 73

IMPORTANT:
- Calibration only.
- Does NOT modify production logic.
- Does NOT change scanner.py.
- Does NOT write to production data.
- Uses the existing production scoring functions.
"""

import sys
from pathlib import Path

import pandas as pd


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PRODUCTION IMPORTS
# ============================================================

from data.universe import get_market_universe
from analysis.scanner import run_market_scan
from data.fundamentals import get_fundamentals
from analysis.quality import score_quality
from analysis.growth import score_growth
from analysis.investment_score import calculate_investment_score


try:
    from analysis.universe_filter import filter_investable_universe
except ImportError:
    filter_investable_universe = None


# ============================================================
# TEST PARAMETERS
# ============================================================

CURRENT_TOP_N = 200

TECHNICAL_FLOOR = 73

TEST_TOP_300 = 300

TEST_TOP_400 = 400


IMPORTANT_TICKERS = [
    "MU",
    "NBIS",
    "PLTR",
    "AAPL",
    "ARM",
    "CRWD",
    "SNDK",
    "LITE",
    "VRTX",
]


# ============================================================
# LOAD UNIVERSE
# ============================================================

print()
print("=" * 80)
print("TOP-200 GATE DESIGN CALIBRATION")
print("=" * 80)
print()

print("Loading universe...")

raw_universe = get_market_universe()

print(
    f"Raw universe: {len(raw_universe)}"
)


# ============================================================
# INVESTABILITY FILTER
# ============================================================

if filter_investable_universe is not None:

    print(
        "Applying production investability filter..."
    )

    investable = filter_investable_universe(
        raw_universe
    )

else:

    print(
        "WARNING: production investability filter "
        "could not be imported."
    )

    investable = raw_universe


print(
    f"Investable universe: {len(investable)}"
)

print()


# ============================================================
# COMPLETE TECHNICAL RANKING
# ============================================================

print("=" * 80)
print("RUNNING COMPLETE TECHNICAL RANKING")
print("=" * 80)
print()

technical_candidates = run_market_scan(
    investable,
    limit=len(investable)
)


technical_candidates = sorted(
    technical_candidates,
    key=lambda x:
        x.get(
            "Technical Score",
            0
        ),
    reverse=True
)


print()

print(
    f"Technical candidates: "
    f"{len(technical_candidates)}"
)


# ============================================================
# CURRENT PRODUCTION CUTOFF
# ============================================================

if len(technical_candidates) >= CURRENT_TOP_N:

    current_cutoff = (
        technical_candidates[
            CURRENT_TOP_N - 1
        ]
    )

    print()

    print(
        "CURRENT PRODUCTION CUTOFF"
    )

    print(
        f"Rank {CURRENT_TOP_N}: "
        f"{current_cutoff.get('Ticker')} "
        f"| Technical Score: "
        f"{current_cutoff.get('Technical Score')}"
    )


# ============================================================
# BUILD TECHNICAL RANKING DATAFRAME
# ============================================================

technical_rows = []

for rank, candidate in enumerate(
    technical_candidates,
    start=1
):

    technical_rows.append(
        {
            "Technical Rank": rank,
            "Ticker": candidate.get(
                "Ticker"
            ),
            "Technical Score": float(
                candidate.get(
                    "Technical Score",
                    0
                ) or 0
            ),
        }
    )


technical_df = pd.DataFrame(
    technical_rows
)


# ============================================================
# FUNDAMENTAL SCORING CACHE
# ============================================================

fundamental_cache = {}


def score_ticker(row):

    ticker = row["Ticker"]

    technical_score = float(
        row["Technical Score"]
    )

    if ticker in fundamental_cache:

        return fundamental_cache[ticker]


    quality_score = None

    growth_score = None

    investment_score = None

    error = None


    try:

        # ----------------------------------------------------
        # PRODUCTION FUNDAMENTALS
        # ----------------------------------------------------

        fundamentals = get_fundamentals(
            ticker
        )


        # ----------------------------------------------------
        # PRODUCTION QUALITY SCORE
        # ----------------------------------------------------

        quality_score, _ = score_quality(
            fundamentals
        )


        # ----------------------------------------------------
        # PRODUCTION GROWTH SCORE
        # ----------------------------------------------------

        growth_results = score_growth(
            fundamentals
        )

        growth_score = (
            growth_results[
                "Growth Score"
            ]
        )


        # ----------------------------------------------------
        # PRODUCTION INVESTMENT SCORE
        # ----------------------------------------------------

        investment_score = (
            calculate_investment_score(
                technical_score,
                quality_score,
                growth_score
            )
        )


        investment_score = round(
            float(
                investment_score
            )
        )


    except Exception as e:

        error = str(e)


    result = {

        "Ticker":
            ticker,

        "Technical Rank":
            row["Technical Rank"],

        "Technical Score":
            technical_score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Investment Score":
            investment_score,

        "Scoring Error":
            error,
    }


    fundamental_cache[
        ticker
    ] = result


    return result


# ============================================================
# BUILD TEST POPULATIONS
# ============================================================

populations = {}


# ------------------------------------------------------------
# A — CURRENT PRODUCTION
# ------------------------------------------------------------

populations[
    "A_Current_Top200"
] = (
    technical_df
    .iloc[:CURRENT_TOP_N]
    .copy()
)


# ------------------------------------------------------------
# B — TECHNICAL SCORE >= 80
# ------------------------------------------------------------

populations[
    "B_Technical_GE_80"
] = (
    technical_df[
        technical_df[
            "Technical Score"
        ] >= 80
    ]
    .copy()
)


# ------------------------------------------------------------
# C — TOP 300
# ------------------------------------------------------------

populations[
    "C_Top300"
] = (
    technical_df
    .iloc[:TEST_TOP_300]
    .copy()
)


# ------------------------------------------------------------
# D — TOP 400
# ------------------------------------------------------------

populations[
    "D_Top400"
] = (
    technical_df
    .iloc[:TEST_TOP_400]
    .copy()
)


# ------------------------------------------------------------
# E — TECHNICAL SCORE >= 73
# ------------------------------------------------------------

populations[
    "E_Technical_GE_73"
] = (
    technical_df[
        technical_df[
            "Technical Score"
        ] >= TECHNICAL_FLOOR
    ]
    .copy()
)


# ============================================================
# COMBINE UNIQUE STOCKS
# ============================================================

all_test_rows = (
    pd.concat(
        populations.values(),
        ignore_index=True
    )
    .drop_duplicates(
        subset=["Ticker"]
    )
)


# ============================================================
# FUNDAMENTAL SCORING
# ============================================================

print()

print("=" * 80)
print("FUNDAMENTAL SCORING")
print("=" * 80)
print()

print(
    "Unique stocks requiring "
    "fundamental scoring: "
    f"{len(all_test_rows)}"
)

print()


scored_rows = []


for counter, (_, row) in enumerate(
    all_test_rows.iterrows(),
    start=1
):

    ticker = row["Ticker"]

    print(
        f"[{counter}/{len(all_test_rows)}] "
        f"Scoring {ticker}"
    )

    scored_rows.append(
        score_ticker(row)
    )


scored_df = pd.DataFrame(
    scored_rows
)


# ============================================================
# POPULATION ANALYSIS
# ============================================================

def analyse_population(
    name,
    population
):

    population_tickers = set(
        population["Ticker"]
    )


    result = scored_df[
        scored_df["Ticker"].isin(
            population_tickers
        )
    ].copy()


    successfully_scored = result[
        result[
            "Investment Score"
        ].notna()
    ]


    ge_75 = successfully_scored[
        successfully_scored[
            "Investment Score"
        ] >= 75
    ]


    ge_80 = successfully_scored[
        successfully_scored[
            "Investment Score"
        ] >= 80
    ]


    ge_85 = successfully_scored[
        successfully_scored[
            "Investment Score"
        ] >= 85
    ]


    return {

        "Method":
            name,

        "Technical Candidates":
            len(population),

        "Successfully Scored":
            len(successfully_scored),

        "Investment >= 75":
            len(ge_75),

        "Investment >= 80":
            len(ge_80),

        "Investment >= 85":
            len(ge_85),

        "Avg Investment":
            (
                successfully_scored[
                    "Investment Score"
                ].mean()
                if len(
                    successfully_scored
                ) > 0
                else None
            ),

        "Max Investment":
            (
                successfully_scored[
                    "Investment Score"
                ].max()
                if len(
                    successfully_scored
                ) > 0
                else None
            ),
    }


# ============================================================
# GATE DESIGN COMPARISON
# ============================================================

summary_rows = []


for name, population in populations.items():

    summary_rows.append(
        analyse_population(
            name,
            population
        )
    )


summary_df = pd.DataFrame(
    summary_rows
)


print()

print("=" * 80)
print("GATE DESIGN COMPARISON")
print("=" * 80)
print()

print(
    summary_df.to_string(
        index=False
    )
)


# ============================================================
# IMPORTANT STOCKS
# ============================================================

print()

print("=" * 80)
print("IMPORTANT STOCKS")
print("=" * 80)
print()


important_df = scored_df[
    scored_df["Ticker"].isin(
        IMPORTANT_TICKERS
    )
].copy()


if not important_df.empty:

    print(
        important_df[
            [
                "Ticker",
                "Technical Rank",
                "Technical Score",
                "Quality Score",
                "Growth Score",
                "Investment Score",
                "Scoring Error",
            ]
        ]
        .sort_values(
            "Technical Rank"
        )
        .to_string(
            index=False
        )
    )

else:

    print(
        "None of the important tickers "
        "were successfully scored."
    )


# ============================================================
# STRONG INVESTMENT CANDIDATES OUTSIDE
# CURRENT TOP 200
# ============================================================

print()

print("=" * 80)
print(
    "STRONG INVESTMENT CANDIDATES "
    "OUTSIDE CURRENT TOP-200"
)
print("=" * 80)
print()


outside_current = scored_df[
    scored_df[
        "Technical Rank"
    ] > CURRENT_TOP_N
].copy()


outside_current = outside_current[
    outside_current[
        "Investment Score"
    ].notna()
]


outside_75 = outside_current[
    outside_current[
        "Investment Score"
    ] >= 75
].sort_values(
    "Investment Score",
    ascending=False
)


print(
    "Stocks outside current top-200 "
    "with Investment Score >=75: "
    f"{len(outside_75)}"
)


if not outside_75.empty:

    print()

    print(
        outside_75[
            [
                "Technical Rank",
                "Ticker",
                "Technical Score",
                "Quality Score",
                "Growth Score",
                "Investment Score",
            ]
        ]
        .head(50)
        .to_string(
            index=False
        )
    )


# ============================================================
# TOP INVESTMENT SCORES BELOW
# CURRENT TOP 200
# ============================================================

print()

print("=" * 80)
print(
    "TOP INVESTMENT SCORES BELOW "
    "CURRENT TOP-200"
)
print("=" * 80)
print()


if not outside_current.empty:

    print(
        outside_current[
            [
                "Technical Rank",
                "Ticker",
                "Technical Score",
                "Quality Score",
                "Growth Score",
                "Investment Score",
            ]
        ]
        .sort_values(
            "Investment Score",
            ascending=False
        )
        .head(30)
        .to_string(
            index=False
        )
    )


# ============================================================
# TECHNICAL SCORE BAND ANALYSIS
# ============================================================

print()

print("=" * 80)
print("TECHNICAL SCORE BAND ANALYSIS")
print("=" * 80)
print()


scored_df[
    "Technical Band"
] = pd.cut(
    scored_df[
        "Technical Score"
    ],
    bins=[
        0,
        64,
        69,
        72,
        74,
        77,
        79,
        80,
        100,
    ],
    labels=[
        "<65",
        "65-69",
        "70-72",
        "73-74",
        "75-77",
        "78-79",
        "80",
        ">80",
    ],
    include_lowest=True,
)


band_summary = (
    scored_df
    .groupby(
        "Technical Band",
        observed=False
    )
    .agg(
        Stocks=(
            "Ticker",
            "count"
        ),

        Investment_75=(
            "Investment Score",
            lambda x:
                (
                    x >= 75
                ).sum()
        ),

        Investment_80=(
            "Investment Score",
            lambda x:
                (
                    x >= 80
                ).sum()
        ),

        Max_Investment=(
            "Investment Score",
            "max"
        ),

        Avg_Investment=(
            "Investment Score",
            "mean"
        ),
    )
    .reset_index()
)


print(
    band_summary.to_string(
        index=False
    )
)


# ============================================================
# OUTPUT
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


summary_file = (
    output_dir
    / "top_200_gate_design_summary.csv"
)


stocks_file = (
    output_dir
    / "top_200_gate_design_stocks.csv"
)


summary_df.to_csv(
    summary_file,
    index=False
)


scored_df.to_csv(
    stocks_file,
    index=False
)


print()

print("=" * 80)
print("OUTPUT")
print("=" * 80)
print()

print(
    f"Summary: {summary_file}"
)

print(
    f"Stocks:  {stocks_file}"
)

print()

print(
    "PRODUCTION CODE WAS NOT CHANGED."
)

print()
