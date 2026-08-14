
import pandas as pd
import numpy as np


# ==========================================================
# CONFIGURATION
# ==========================================================

MIN_RELIABLE_OBSERVATIONS = 20

SIGNALS = [
    "BUY",
    "STRONG BUY",
    "HOLD",
    "SELL",
    "STRONG SELL",
    "WATCH",
]


SCORE_BUCKETS = [
    ("<40", 0, 39),
    ("40-54", 40, 54),
    ("55-69", 55, 69),
    ("70-84", 70, 84),
    ("85-100", 85, 100),
]


COMPONENTS = [
    ("Technical Score", "technical_score"),
    ("Quality Score", "quality_score"),
    ("Growth Score", "growth_score"),
    ("Confidence Score", "confidence_score"),
    ("Investment Score", "investment_score"),
]


# ==========================================================
# BASIC HELPERS
# ==========================================================

def safe_numeric(series):

    return pd.to_numeric(
        series,
        errors="coerce"
    )


def reliability_label(count):

    if count >= MIN_RELIABLE_OBSERVATIONS:
        return "VALID"

    if count > 0:
        return "INSUFFICIENT DATA"

    return "NO DATA"


def safe_mean(series):

    values = pd.Series(series).dropna()

    if values.empty:
        return 0.0

    return round(
        float(values.mean()),
        2
    )


def safe_median(series):

    values = pd.Series(series).dropna()

    if values.empty:
        return 0.0

    return round(
        float(values.median()),
        2
    )


def calculate_win_rate(values):

    values = pd.Series(values).dropna()

    if values.empty:
        return 0.0

    return round(
        float(
            (values > 0).mean() * 100
        ),
        2
    )


def safe_correlation(
    df,
    x,
    y
):

    if x not in df.columns:
        return 0.0

    if y not in df.columns:
        return 0.0

    temp = df[
        [x, y]
    ].copy()

    temp[x] = safe_numeric(
        temp[x]
    )

    temp[y] = safe_numeric(
        temp[y]
    )

    temp = temp.dropna()

    if len(temp) < 5:
        return 0.0

    if temp[x].nunique() <= 1:
        return 0.0

    if temp[y].nunique() <= 1:
        return 0.0

    correlation = temp[x].corr(
        temp[y]
    )

    if pd.isna(correlation):
        return 0.0

    return round(
        float(correlation),
        3
    )


# ==========================================================
# DIRECTION-AWARE RETURN
# ==========================================================

def calculate_directional_return(
    signal,
    stock_return
):
    """
    Convert the underlying stock return into the return
    relevant to the recommendation.

    BUY / STRONG BUY
        Stock +10%  -> recommendation +10%

    SELL / STRONG SELL
        Stock +10%  -> recommendation -10%

    HOLD / WATCH
        Retain the underlying stock return.

    The important point is that a SELL recommendation
    followed by a rising stock is a LOSS, not a WIN.
    """

    if pd.isna(stock_return):
        return np.nan

    signal = str(
        signal
    ).strip().upper()

    stock_return = float(
        stock_return
    )

    if signal in (
        "SELL",
        "STRONG SELL"
    ):
        return -stock_return

    return stock_return


# ==========================================================
# SUCCESS / FAILURE
# ==========================================================

def calculate_success(
    signal,
    directional_return
):
    """
    Return:

        1 = successful recommendation
        0 = unsuccessful recommendation
        NaN = insufficient information

    For BUY / SELL recommendations this represents
    directional trading success.

    For HOLD / WATCH it represents whether the underlying
    position performed positively.
    """

    if pd.isna(directional_return):
        return np.nan

    return (
        1
        if float(directional_return) > 0
        else 0
    )


# ==========================================================
# NORMALISE HISTORY
# ==========================================================

def prepare_learning_data(history):

    if history is None:
        return pd.DataFrame()

    if not isinstance(
        history,
        pd.DataFrame
    ):
        history = pd.DataFrame(
            history
        )

    if history.empty:
        return pd.DataFrame()

    df = history.copy()

    # ------------------------------------------------------
    # Normalise column names
    # ------------------------------------------------------

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    # ------------------------------------------------------
    # Map current database-query names to internal names
    # ------------------------------------------------------

    aliases = {

        "Ticker":
            "ticker",

        "Recommendation Date":
            "recommendation_date",

        "Date":
            "recommendation_date",

        "Signal":
            "signal",

        "Investment Score":
            "investment_score",

        "Technical Score":
            "technical_score",

        "Quality Score":
            "quality_score",

        "Growth Score":
            "growth_score",

        "Confidence":
            "confidence",

        "Confidence Score":
            "confidence_score",

        "Evaluation Date":
            "evaluation_date",

        "Days After":
            "days_after",

        "Evaluation Price":
            "evaluation_price",

        "Price":
            "evaluation_price",

        "Return %":
            "return_percent",

        "Return Percent":
            "return_percent",

        "Outcome":
            "outcome",
    }

    for source, target in aliases.items():

        if (
            source in df.columns
            and target not in df.columns
        ):

            df[target] = df[source]

    # ------------------------------------------------------
    # Lowercase aliases if already supplied
    # ------------------------------------------------------

    lower_aliases = {

        "Ticker":
            "ticker",

        "Signal":
            "signal",

        "Investment Score":
            "investment_score",

        "Technical Score":
            "technical_score",

        "Quality Score":
            "quality_score",

        "Growth Score":
            "growth_score",

        "Confidence Score":
            "confidence_score",

        "Days After":
            "days_after",

        "Return %":
            "return_percent",
    }

    for source, target in lower_aliases.items():

        if source in df.columns:
            df[target] = df[source]

    # ------------------------------------------------------
    # Numeric columns
    # ------------------------------------------------------

    numeric_columns = [

        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "return_percent",
        "days_after",
        "evaluation_price",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = safe_numeric(
                df[column]
            )

    # ------------------------------------------------------
    # Signal
    # ------------------------------------------------------

    if "signal" in df.columns:

        df["signal"] = (
            df["signal"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    else:

        df["signal"] = "UNKNOWN"

    # ------------------------------------------------------
    # Required fields
    # ------------------------------------------------------

    if "return_percent" not in df.columns:

        df["return_percent"] = np.nan

    if "days_after" not in df.columns:

        df["days_after"] = np.nan

    # ------------------------------------------------------
    # Directional return
    # ------------------------------------------------------

    df["directional_return"] = [

        calculate_directional_return(
            signal,
            stock_return
        )

        for signal, stock_return
        in zip(
            df["signal"],
            df["return_percent"]
        )

    ]

    # ------------------------------------------------------
    # Learning success
    # ------------------------------------------------------

    df["learning_success"] = [

        calculate_success(
            signal,
            directional_return
        )

        for signal, directional_return
        in zip(
            df["signal"],
            df["directional_return"]
        )

    ]

    return df


# ==========================================================
# OVERALL PERFORMANCE
# ==========================================================

def calculate_overall_performance(df):

    if df.empty:
        return {
            "Observations": 0,
            "Average Return %": 0,
            "Median Return %": 0,
            "Win Rate %": 0,
            "Reliability": "NO DATA",
        }

    returns = (
        df["directional_return"]
        .dropna()
    )

    successes = (
        df["learning_success"]
        .dropna()
    )

    count = len(returns)

    return {

        "Observations":
            count,

        "Average Return %":
            safe_mean(returns),

        "Median Return %":
            safe_median(returns),

        "Win Rate %":
            calculate_win_rate(
                returns
            ),

        "Reliability":
            reliability_label(
                count
            ),
    }


# ==========================================================
# HORIZON PERFORMANCE
# ==========================================================

def calculate_horizon_performance(df):

    columns = [
        "Horizon",
        "Recommendations",
        "Average Return %",
        "Median Return %",
        "Win Rate %",
        "Reliability",
    ]

    if (
        df.empty
        or "days_after" not in df.columns
    ):

        return pd.DataFrame(
            columns=columns
        )

    rows = []

    working = df.dropna(
        subset=["days_after"]
    )

    for horizon, group in working.groupby(
        "days_after"
    ):

        returns = (
            group["directional_return"]
            .dropna()
        )

        count = len(returns)

        rows.append(
            {
                "Horizon":
                    int(horizon),

                "Recommendations":
                    count,

                "Average Return %":
                    safe_mean(returns),

                "Median Return %":
                    safe_median(returns),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=columns
        )

    return (
        pd.DataFrame(rows)
        .sort_values("Horizon")
        .reset_index(drop=True)
    )


# ==========================================================
# SIGNAL PERFORMANCE
# ==========================================================

def calculate_signal_performance(df):

    columns = [
        "Signal",
        "Recommendations",
        "Average Return %",
        "Median Return %",
        "Win Rate %",
        "Reliability",
    ]

    if df.empty:
        return pd.DataFrame(
            columns=columns
        )

    rows = []

    for signal in SIGNALS:

        group = df[
            df["signal"] == signal
        ]

        returns = (
            group["directional_return"]
            .dropna()
        )

        count = len(returns)

        rows.append(
            {
                "Signal":
                    signal,

                "Recommendations":
                    count,

                "Average Return %":
                    safe_mean(returns),

                "Median Return %":
                    safe_median(returns),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    return result.sort_values(
        "Average Return %",
        ascending=False
    ).reset_index(
        drop=True
    )


# ==========================================================
# SIGNAL RELIABILITY
# ==========================================================

def calculate_signal_reliability(df):

    if df.empty:
        return pd.DataFrame()

    rows = []

    for signal in SIGNALS:

        group = df[
            df["signal"] == signal
        ]

        returns = (
            group["directional_return"]
            .dropna()
        )

        count = len(returns)

        rows.append(
            {
                "Signal":
                    signal,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(returns),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return pd.DataFrame(
        rows
    ).sort_values(
        "Average Return %",
        ascending=False
    ).reset_index(
        drop=True
    )


# ==========================================================
# SCORE BUCKET
# ==========================================================

def get_score_bucket(score):

    if pd.isna(score):
        return None

    score = float(score)

    if score < 40:
        return "<40"

    if score < 55:
        return "40-54"

    if score < 70:
        return "55-69"

    if score < 85:
        return "70-84"

    return "85-100"


# ==========================================================
# SCORE BUCKET PERFORMANCE
# ==========================================================

def calculate_score_bucket_performance(df):

    if (
        df.empty
        or "investment_score" not in df.columns
    ):

        return pd.DataFrame()

    temp = df.copy()

    temp["Score Bucket"] = (
        temp["investment_score"]
        .apply(get_score_bucket)
    )

    rows = []

    for bucket, minimum, maximum in SCORE_BUCKETS:

        group = temp[
            temp["Score Bucket"] == bucket
        ]

        returns = (
            group["directional_return"]
            .dropna()
        )

        count = len(returns)

        rows.append(
            {
                "Score Bucket":
                    bucket,

                "Minimum Score":
                    minimum,

                "Maximum Score":
                    maximum,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(returns),

                "Median Return %":
                    safe_median(returns),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# COMPONENT SCORE PERFORMANCE
# ==========================================================

def calculate_component_score_performance(df):

    if df.empty:
        return pd.DataFrame()

    rows = []

    for component_name, column in COMPONENTS:

        if column not in df.columns:
            continue

        temp = df.copy()

        temp["Score Bucket"] = (
            temp[column]
            .apply(get_score_bucket)
        )

        for bucket, minimum, maximum in SCORE_BUCKETS:

            group = temp[
                temp["Score Bucket"] == bucket
            ]

            returns = (
                group["directional_return"]
                .dropna()
            )

            count = len(returns)

            rows.append(
                {
                    "Component":
                        component_name,

                    "Component Score Bucket":
                        bucket,

                    "Minimum Score":
                        minimum,

                    "Maximum Score":
                        maximum,

                    "Observations":
                        count,

                    "Average Return %":
                        safe_mean(returns),

                    "Win Rate %":
                        calculate_win_rate(
                            returns
                        ),

                    "Reliability":
                        reliability_label(
                            count
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# CONFIDENCE PERFORMANCE
# ==========================================================

def get_confidence_bucket(score):

    if pd.isna(score):
        return None

    score = float(score)

    if score < 40:
        return "0-39"

    if score < 60:
        return "40-59"

    if score < 80:
        return "60-79"

    if score < 90:
        return "80-89"

    return "90-100"


def calculate_confidence_performance(df):

    if (
        df.empty
        or "confidence_score" not in df.columns
    ):

        return pd.DataFrame()

    temp = df.copy()

    temp["Confidence Bucket"] = (
        temp["confidence_score"]
        .apply(get_confidence_bucket)
    )

    buckets = [
        ("0-39", 0),
        ("40-59", 40),
        ("60-79", 60),
        ("80-89", 80),
        ("90-100", 90),
    ]

    rows = []

    for bucket, minimum in buckets:

        group = temp[
            temp["Confidence Bucket"] == bucket
        ]

        returns = (
            group["directional_return"]
            .dropna()
        )

        count = len(returns)

        rows.append(
            {
                "Confidence Bucket":
                    bucket,

                "Minimum Score":
                    minimum,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(returns),

                "Median Return %":
                    safe_median(returns),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# SIGNAL + HORIZON
# ==========================================================

def calculate_signal_horizon_performance(df):

    if df.empty:
        return pd.DataFrame()

    rows = []

    for signal in SIGNALS:

        signal_df = df[
            df["signal"] == signal
        ]

        for horizon in sorted(
            signal_df["days_after"]
            .dropna()
            .unique()
        ):

            group = signal_df[
                signal_df["days_after"] == horizon
            ]

            returns = (
                group["directional_return"]
                .dropna()
            )

            count = len(returns)

            rows.append(
                {
                    "Signal":
                        signal,

                    "Days After":
                        int(horizon),

                    "Recommendations":
                        count,

                    "Average Return %":
                        safe_mean(returns),

                    "Win Rate %":
                        calculate_win_rate(
                            returns
                        ),

                    "Reliability":
                        reliability_label(
                            count
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# SCORE + HORIZON
# ==========================================================

def calculate_score_horizon_performance(df):

    if df.empty:
        return pd.DataFrame()

    temp = df.copy()

    temp["Score Bucket"] = (
        temp["investment_score"]
        .apply(get_score_bucket)
    )

    rows = []

    for bucket, minimum, maximum in SCORE_BUCKETS:

        bucket_df = temp[
            temp["Score Bucket"] == bucket
        ]

        for horizon in sorted(
            bucket_df["days_after"]
            .dropna()
            .unique()
        ):

            group = bucket_df[
                bucket_df["days_after"] == horizon
            ]

            returns = (
                group["directional_return"]
                .dropna()
            )

            count = len(returns)

            rows.append(
                {
                    "Score Bucket":
                        bucket,

                    "Days After":
                        int(horizon),

                    "Observations":
                        count,

                    "Average Return %":
                        safe_mean(returns),

                    "Win Rate %":
                        calculate_win_rate(
                            returns
                        ),

                    "Reliability":
                        reliability_label(
                            count
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# CORRELATION ANALYSIS
# ==========================================================

def calculate_score_correlations(df):

    if df.empty:
        return pd.DataFrame()

    rows = []

    for horizon in sorted(
        df["days_after"]
        .dropna()
        .unique()
    ):

        horizon_df = df[
            df["days_after"] == horizon
        ]

        for component_name, column in COMPONENTS:

            if column not in horizon_df.columns:
                continue

            valid = horizon_df[
                [
                    column,
                    "directional_return"
                ]
            ].dropna()

            if len(valid) < 20:

                correlation = None

            else:

                correlation = safe_correlation(
                    horizon_df,
                    column,
                    "directional_return"
                )

            rows.append(
                {
                    "Days After":
                        int(horizon),

                    "Component":
                        column,

                    "Correlation":
                        correlation,

                    "Observations":
                        len(valid),

                    "Reliability":
                        reliability_label(
                            len(valid)
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# COMPONENT CORRELATION SUMMARY
# ==========================================================

def calculate_component_correlations(df):

    if df.empty:
        return pd.DataFrame()

    rows = []

    for component_name, column in COMPONENTS:

        if column not in df.columns:
            continue

        valid = df[
            [
                column,
                "directional_return"
            ]
        ].dropna()

        correlation = safe_correlation(
            df,
            column,
            "directional_return"
        )

        rows.append(
            {
                "Component":
                    column,

                "Correlation":
                    correlation,

                "Observations":
                    len(valid),

                "Reliability":
                    reliability_label(
                        len(valid)
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# DIAGNOSTIC OUTPUT
# ==========================================================

def run_diagnostic(
    history=None,
    print_output=True
):

    if history is None:

        from data.database_queries import (
            get_learning_history
        )

        history = get_learning_history()

    df = prepare_learning_data(
        history
    )

    if df.empty:

        if print_output:
            print(
                "\nNo recommendation learning data available.\n"
            )

        return {}

    horizon = calculate_horizon_performance(
        df
    )

    score = calculate_score_bucket_performance(
        df
    )

    signal = calculate_signal_horizon_performance(
        df
    )

    technical = calculate_component_bucket(
        df,
        "technical_score",
        "Technical Bucket"
    )

    quality = calculate_component_bucket(
        df,
        "quality_score",
        "Quality Bucket"
    )

    growth = calculate_component_bucket(
        df,
        "growth_score",
        "Growth Bucket"
    )

    confidence = calculate_confidence_performance(
        df
    )

    correlations = calculate_score_correlations(
        df
    )

    if print_output:

        print("=" * 90)
        print(
            "RECOMMENDATION LEARNING DIAGNOSTIC"
        )
        print("=" * 90)

        print(
            f"\nTotal evaluations: {len(df):,}"
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "1. PERFORMANCE BY HORIZON"
        )
        print("=" * 90)

        print(
            horizon.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "2. PERFORMANCE BY INVESTMENT SCORE"
        )
        print("=" * 90)

        print(
            score.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "3. PERFORMANCE BY SIGNAL"
        )
        print("=" * 90)

        print(
            calculate_signal_performance(
                df
            ).to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "4. PERFORMANCE BY TECHNICAL SCORE"
        )
        print("=" * 90)

        print(
            technical.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "5. PERFORMANCE BY QUALITY SCORE"
        )
        print("=" * 90)

        print(
            quality.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "6. PERFORMANCE BY GROWTH SCORE"
        )
        print("=" * 90)

        print(
            growth.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "7. PERFORMANCE BY CONFIDENCE SCORE"
        )
        print("=" * 90)

        print(
            confidence.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "8. SCORE CORRELATION WITH DIRECTIONAL RETURN"
        )
        print("=" * 90)

        for horizon_value in sorted(
            correlations["Days After"]
            .dropna()
            .unique()
        ):

            print(
                f"\n{int(horizon_value)}D:"
            )

            temp = correlations[
                correlations["Days After"]
                == horizon_value
            ]

            for _, row in temp.iterrows():

                if pd.isna(
                    row["Correlation"]
                ):

                    print(
                        f"  {row['Component']}: "
                        f"insufficient data"
                    )

                else:

                    print(
                        f"  {row['Component']}: "
                        f"{row['Correlation']:.3f} "
                        f"({int(row['Observations']):,} observations)"
                    )

        print(
            "\n" + "=" * 90
        )
        print(
            "9. SIGNAL RANKING"
        )
        print("=" * 90)

        signal_horizon = (
            calculate_signal_horizon_performance(
                df
            )
        )

        print(
            signal_horizon.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )
        print(
            "10. LEARNING SUMMARY"
        )
        print("=" * 90)

        for _, row in horizon.iterrows():

            print(
                f"\n{int(row['Horizon'])}D observations: "
                f"{int(row['Recommendations']):,}"
            )

            print(
                f"{int(row['Horizon'])}D average "
                f"directional return: "
                f"{row['Average Return %']:.2f}%"
            )

            print(
                f"{int(row['Horizon'])}D win rate: "
                f"{row['Win Rate %']:.1f}%"
            )

        print(
            "\nDIAGNOSTIC COMPLETE"
        )

    return {
        "data": df,
        "Overall": calculate_overall_performance(df),
        "Horizon Learning": horizon,
        "Signal Performance":
            calculate_signal_performance(df),
        "Signal Reliability":
            calculate_signal_reliability(df),
        "Score Bucket Performance":
            score,
        "Score Horizon Performance":
            calculate_score_horizon_performance(df),
        "Signal Horizon Performance":
            calculate_signal_horizon_performance(df),
        "Component Score Performance":
            calculate_component_score_performance(df),
        "Confidence Performance":
            confidence,
        "Technical Performance":
            technical,
        "Quality Performance":
            quality,
        "Growth Performance":
            growth,
        "Score Correlations":
            correlations,
        "Component Correlations":
            calculate_component_correlations(df),
    }


# ==========================================================
# GENERIC COMPONENT BUCKET ANALYSIS
# ==========================================================

def calculate_component_bucket(
    df,
    column,
    bucket_column_name
):

    if (
        df.empty
        or column not in df.columns
    ):

        return pd.DataFrame()

    temp = df.copy()

    temp[bucket_column_name] = (
        temp[column]
        .apply(get_component_bucket)
    )

    bucket_order = [
        "<40",
        "40-54",
        "55-69",
        "70-84",
        "85-100",
    ]

    rows = []

    for bucket in bucket_order:

        group = temp[
            temp[bucket_column_name]
            == bucket
        ]

        returns = (
            group["directional_return"]
            .dropna()
        )

        count = len(returns)

        rows.append(
            {
                bucket_column_name:
                    bucket,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(returns),

                "Median Return %":
                    safe_median(returns),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def get_component_bucket(score):

    if pd.isna(score):
        return None

    score = float(score)

    if score < 40:
        return "<40"

    if score < 55:
        return "40-54"

    if score < 70:
        return "55-69"

    if score < 85:
        return "70-84"

    return "85-100"


# ==========================================================
# MAIN LEARNING FUNCTION
# ==========================================================

def calculate_recommendation_learning(
    history
):
    """
    Main interface used by main.py.

    This function deliberately returns the structure expected
    by the existing Excel reporting layer.
    """

    print(
        "\nRECOMMENDATION LEARNING INPUT:",
        len(history)
        if history is not None
        else 0
    )

    df = prepare_learning_data(
        history
    )

    if df.empty:

        print(
            "RECOMMENDATION LEARNING: NO DATA"
        )

        return {

            "Overall": {
                "Observations": 0,
                "Average Return %": 0,
                "Median Return %": 0,
                "Win Rate %": 0,
                "Reliability": "NO DATA",
            },

            "Horizon Learning":
                pd.DataFrame(),

            "Signal Performance":
                pd.DataFrame(),

            "Signal Reliability":
                pd.DataFrame(),

            "Score Bucket Performance":
                pd.DataFrame(),

            "Score Horizon Performance":
                pd.DataFrame(),

            "Signal Horizon Performance":
                pd.DataFrame(),

            "Component Score Performance":
                pd.DataFrame(),

            "Confidence Performance":
                pd.DataFrame(),

            "Technical Performance":
                pd.DataFrame(),

            "Quality Performance":
                pd.DataFrame(),

            "Growth Performance":
                pd.DataFrame(),

            "Score Correlations":
                pd.DataFrame(),

            "Component Correlations":
                pd.DataFrame(),
        }

    print(
        "RECOMMENDATION LEARNING PREPARED:",
        len(df)
    )

    if "signal" in df.columns:

        print(
            "SIGNAL COUNTS:"
        )

        print(
            df["signal"].value_counts()
        )

    if "days_after" in df.columns:

        print(
            "DAYS AFTER COUNTS:"
        )

        print(
            df["days_after"].value_counts()
        )

    # ------------------------------------------------------
    # Calculate all learning outputs
    # ------------------------------------------------------

    overall = calculate_overall_performance(
        df
    )

    horizon_learning = (
        calculate_horizon_performance(
            df
        )
    )

    signal_performance = (
        calculate_signal_performance(
            df
        )
    )

    signal_reliability = (
        calculate_signal_reliability(
            df
        )
    )

    score_bucket_performance = (
        calculate_score_bucket_performance(
            df
        )
    )

    score_horizon_performance = (
        calculate_score_horizon_performance(
            df
        )
    )

    signal_horizon_performance = (
        calculate_signal_horizon_performance(
            df
        )
    )

    component_score_performance = (
        calculate_component_score_performance(
            df
        )
    )

    confidence_performance = (
        calculate_confidence_performance(
            df
        )
    )

    technical_performance = (
        calculate_component_bucket(
            df,
            "technical_score",
            "Technical Bucket"
        )
    )

    quality_performance = (
        calculate_component_bucket(
            df,
            "quality_score",
            "Quality Bucket"
        )
    )

    growth_performance = (
        calculate_component_bucket(
            df,
            "growth_score",
            "Growth Bucket"
        )
    )

    score_correlations = (
        calculate_score_correlations(
            df
        )
    )

    component_correlations = (
        calculate_component_correlations(
            df
        )
    )

    # ------------------------------------------------------
    # Diagnostic console output
    # ------------------------------------------------------

    print(
        "Overall:",
        overall
    )

    print(
        "Horizon Learning:",
        horizon_learning
    )

    print(
        "Signal Performance:",
        signal_performance
    )

    print(
        "Signal Reliability:",
        signal_reliability
    )

    print(
        "Score Bucket Performance:",
        score_bucket_performance
    )

    print(
        "Score Horizon Performance:",
        score_horizon_performance
    )

    print(
        "Signal Horizon Performance:",
        signal_horizon_performance
    )

    print(
        "Component Score Performance:",
        component_score_performance
    )

    print(
        "Confidence Performance:",
        confidence_performance
    )

    # ------------------------------------------------------
    # Return complete learning model
    # ------------------------------------------------------

    return {

        "Overall":
            overall,

        "Horizon Learning":
            horizon_learning,

        "Signal Performance":
            signal_performance,

        "Signal Reliability":
            signal_reliability,

        "Score Bucket Performance":
            score_bucket_performance,

        "Score Horizon Performance":
            score_horizon_performance,

        "Signal Horizon Performance":
            signal_horizon_performance,

        "Component Score Performance":
            component_score_performance,

        "Confidence Performance":
            confidence_performance,

        "Technical Performance":
            technical_performance,

        "Quality Performance":
            quality_performance,

        "Growth Performance":
            growth_performance,

        "Score Correlations":
            score_correlations,

        "Component Correlations":
            component_correlations,
    }


# ==========================================================
# STANDALONE EXECUTION
# ==========================================================

if __name__ == "__main__":

    from data.database_queries import (
        get_learning_history
    )

    history = get_learning_history()

    print(
        "\nLoaded learning history:",
        len(history)
    )

    run_diagnostic(
        history
    )
