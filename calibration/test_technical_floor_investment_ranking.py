"""
Final calibration experiment:
Determine the appropriate technical eligibility floor before
Investment Score ranking.

This tests whether a broader technical population produces
better Investment Score candidates than the current top-200
technical gate.

Technical floors tested:

    >= 80
    >= 78
    >= 75
    >= 73
    >= 70

For each technical floor:

    Technical eligibility
            ↓
    Fundamental scoring
            ↓
    Investment Score
            ↓
    Rank by Investment Score

IMPORTANT:
- Calibration only.
- Does NOT modify production logic.
- Does NOT change scanner.py.
- Does NOT change candidate_selection.py.
- Does NOT change Investment Score logic.
- Does NOT write to production data.
- Uses existing production scoring functions.
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

TECHNICAL_FLOORS = [
    80,
    78,
    75,
    73,
    70,
]


INVESTMENT_THRESHOLD = 75


TOP_N_VALUES = [
    25,
    50,
    100,
    200,
]


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
    "ANET",
    "CRDO",
    "FTNT",
    "VCTR",
]


# ============================================================
# LOAD UNIVERSE
# ============================================================

print()
print("=" * 80)
print("TECHNICAL FLOOR / INVESTMENT RANKING CALIBRATION")
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
# BUILD TECHNICAL DATAFRAME
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
# SHOW TECHNICAL FLOOR POPULATIONS
# ============================================================

print()

print("=" * 80)
print("TECHNICAL FLOOR POPULATIONS")
print("=" * 80)
print()

for floor in TECHNICAL_FLOORS:

    count = len(
        technical_df[
            technical_df[
                "Technical Score"
            ] >= floor
        ]
    )

    print(
        f"Technical >= {floor}: "
        f"{count} candidates"
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
# BUILD UNION OF STOCKS REQUIRING SCORING
# ============================================================

minimum_floor = min(
    TECHNICAL_FLOORS
)


stocks_to_score = technical_df[
    technical_df[
        "Technical Score"
    ] >= minimum_floor
].copy()


print()

print("=" * 80)
print("FUNDAMENTAL SCORING")
print("=" * 80)
print()

print(
    "Stocks requiring fundamental scoring: "
    f"{len(stocks_to_score)}"
)

print()


# ============================================================
# SCORE ALL STOCKS
# ============================================================

scored_rows = []


for counter, (_, row) in enumerate(
    stocks_to_score.iterrows(),
    start=1
):

    ticker = row["Ticker"]

    print(
        f"[{counter}/{len(stocks_to_score)}] "
        f"Scoring {ticker}"
    )

    scored_rows.append(
        score_ticker(row)
    )


scored_df = pd.DataFrame(
    scored_rows
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
    scored_df[
        "Ticker"
    ].isin(
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
            [
                "Investment Score",
                "Technical Rank",
            ],
            ascending=[
                False,
                True,
            ]
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
# ANALYSE EACH TECHNICAL FLOOR
# ============================================================

summary_rows = []


for floor in TECHNICAL_FLOORS:

    population = scored_df[
        scored_df[
            "Technical Score"
        ] >= floor
    ].copy()


    successfully_scored = population[
        population[
            "Investment Score"
        ].notna()
    ].copy()


    ge_75 = successfully_scored[
        successfully_scored[
            "Investment Score"
        ] >= INVESTMENT_THRESHOLD
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


    summary_rows.append(
        {

            "Technical Floor":
                floor,

            "Technical Candidates":
                len(population),

            "Successfully Scored":
                len(successfully_scored),

            "Investment >=75":
                len(ge_75),

            "Investment >=80":
                len(ge_80),

            "Investment >=85":
                len(ge_85),

            "Avg Investment":
                successfully_scored[
                    "Investment Score"
                ].mean(),

            "Max Investment":
                successfully_scored[
                    "Investment Score"
                ].max(),

        }
    )


summary_df = pd.DataFrame(
    summary_rows
)


# ============================================================
# FLOOR SUMMARY
# ============================================================

print()

print("=" * 80)
print("TECHNICAL FLOOR SUMMARY")
print("=" * 80)
print()

print(
    summary_df.to_string(
        index=False
    )
)


# ============================================================
# TOP INVESTMENT CANDIDATES FOR EACH FLOOR
# ============================================================

for floor in TECHNICAL_FLOORS:

    population = scored_df[
        scored_df[
            "Technical Score"
        ] >= floor
    ].copy()


    population = population[
        population[
            "Investment Score"
        ].notna()
    ]


    ranked = population.sort_values(
        [
            "Investment Score",
            "Technical Score",
            "Quality Score",
            "Growth Score",
        ],
        ascending=[
            False,
            False,
            False,
            False,
        ]
    )


    print()

    print("=" * 80)

    print(
        f"TOP 25 BY INVESTMENT SCORE "
        f"| TECHNICAL >= {floor}"
    )

    print("=" * 80)

    print()


    if ranked.empty:

        print(
            "No successfully scored candidates."
        )

    else:

        print(
            ranked[
                [
                    "Ticker",
                    "Technical Rank",
                    "Technical Score",
                    "Quality Score",
                    "Growth Score",
                    "Investment Score",
                ]
            ]
            .head(25)
            .to_string(
                index=False
            )
        )


# ============================================================
# TOP-N COMPARISON
# ============================================================

comparison_rows = []


for floor in TECHNICAL_FLOORS:

    population = scored_df[
        scored_df[
            "Technical Score"
        ] >= floor
    ].copy()


    population = population[
        population[
            "Investment Score"
        ].notna()
    ]


    ranked = population.sort_values(
        [
            "Investment Score",
            "Technical Score",
            "Quality Score",
            "Growth Score",
        ],
        ascending=[
            False,
            False,
            False,
            False,
        ]
    )


    for top_n in TOP_N_VALUES:

        top_population = (
            ranked
            .head(top_n)
        )


        ge_75 = top_population[
            top_population[
                "Investment Score"
            ] >= 75
        ]


        ge_80 = top_population[
            top_population[
                "Investment Score"
            ] >= 80
        ]


        ge_85 = top_population[
            top_population[
                "Investment Score"
            ] >= 85
        ]


        comparison_rows.append(
            {

                "Technical Floor":
                    floor,

                "Top N":
                    top_n,

                "Candidates":
                    len(top_population),

                "Investment >=75":
                    len(ge_75),

                "Investment >=80":
                    len(ge_80),

                "Investment >=85":
                    len(ge_85),

                "Avg Investment":
                    top_population[
                        "Investment Score"
                    ].mean(),

                "Min Investment":
                    top_population[
                        "Investment Score"
                    ].min(),

            }
        )


comparison_df = pd.DataFrame(
    comparison_rows
)


print()

print("=" * 80)
print("INVESTMENT-RANKED TOP-N COMPARISON")
print("=" * 80)
print()

print(
    comparison_df.to_string(
        index=False
    )
)


# ============================================================
# WHICH STOCKS ARE ADDED AS FLOOR FALLS?
# ============================================================

print()

print("=" * 80)
print("INCREMENTAL STOCKS CREATED BY LOWERING THE FLOOR")
print("=" * 80)
print()


previous_floor = None


for floor in TECHNICAL_FLOORS:

    population = scored_df[
        scored_df[
            "Technical Score"
        ] >= floor
    ].copy()


    population = population[
        population[
            "Investment Score"
        ].notna()
    ]


    ranked = population.sort_values(
        [
            "Investment Score",
            "Technical Score",
        ],
        ascending=[
            False,
            False,
        ]
    )


    if previous_floor is None:

        print(
            f"Technical >= {floor}: "
            f"{len(ranked)} stocks"
        )

    else:

        previous_population = scored_df[
            scored_df[
                "Technical Score"
            ] >= previous_floor
        ]["Ticker"]


        new_stocks = ranked[
            ~ranked[
                "Ticker"
            ].isin(
                previous_population
            )
        ].copy()


        print()

        print(
            f"Stocks added when floor falls "
            f"from {previous_floor} to {floor}: "
            f"{len(new_stocks)}"
        )


        if not new_stocks.empty:

            print(
                new_stocks[
                    [
                        "Ticker",
                        "Technical Rank",
                        "Technical Score",
                        "Quality Score",
                        "Growth Score",
                        "Investment Score",
                    ]
                ]
                .head(30)
                .to_string(
                    index=False
                )
            )


    previous_floor = floor


# ============================================================
# MU / NBIS SPECIFIC ANALYSIS
# ============================================================

print()

print("=" * 80)
print("MU / NBIS GATE ANALYSIS")
print("=" * 80)
print()


for ticker in [
    "MU",
    "NBIS",
]:

    row = scored_df[
        scored_df[
            "Ticker"
        ] == ticker
    ]


    if row.empty:

        print(
            f"{ticker}: not present in tested population"
        )

        continue


    row = row.iloc[0]


    print(
        f"{ticker}: "
        f"Technical Rank={row['Technical Rank']}, "
        f"Technical={row['Technical Score']}, "
        f"Quality={row['Quality Score']}, "
        f"Growth={row['Growth Score']}, "
        f"Investment={row['Investment Score']}"
    )


    for floor in TECHNICAL_FLOORS:

        included = (
            row["Technical Score"]
            >= floor
        )


        print(
            f"    Technical >= {floor}: "
            f"{'INCLUDED' if included else 'EXCLUDED'}"
        )


# ============================================================
# SAVE OUTPUT
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
    / "technical_floor_investment_summary.csv"
)


stocks_file = (
    output_dir
    / "technical_floor_investment_stocks.csv"
)


comparison_file = (
    output_dir
    / "technical_floor_investment_topn.csv"
)


summary_df.to_csv(
    summary_file,
    index=False
)


scored_df.to_csv(
    stocks_file,
    index=False
)


comparison_df.to_csv(
    comparison_file,
    index=False
)


print()

print("=" * 80)
print("OUTPUT")
print("=" * 80)
print()

print(
    f"Summary:     {summary_file}"
)

print(
    f"Stocks:      {stocks_file}"
)

print(
    f"Top-N:       {comparison_file}"
)

print()

print(
    "PRODUCTION CODE WAS NOT CHANGED."
)

print()
