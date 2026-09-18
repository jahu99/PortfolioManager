import pandas as pd
import os
from datetime import datetime
import sqlite3
import json

# ============================================================
# Final Portfolio Decisions - Executive Report Contract
# ============================================================

FINAL_DECISION_COLUMNS = [
    # Position
    "Ticker",
    "Name",
    "Asset Type",
    "Existing Holding",
    "Sector",
    "Allocation %",

    # Investment
    "Investment Score",
    "Signal",
    "ETF Score",
    "ETF Signal",

    # Decision
    "Proposed Action",
    "Final Decision",
    "Decision Status",

    # Evidence / governance
    "Evidence Score",
    "Evidence Strength",
    "Decision Support",
    "Deterministic Confidence",

    # Independent AI review
    "LLM Assessment",
    "LLM Confidence",
    "LLM Reason",

    # Reconciliation
    "Reconciliation Status",
    "Reconciliation Reason",

    # Capital impact
    "Reduction %",
    "Released Capital",
    "Buy Value",
    "Ticker Horizon Learning Commentary",
]


FINAL_DECISION_HEADERS = {
    "Ticker": "Ticker",
    "Name": "Name",
    "Asset Type": "Asset",
    "Existing Holding": "Held?",
    "Sector": "Sector",
    "Allocation %": "Current Allocation %",
    "Investment Score": "Investment Score",
    "Signal": "Signal",
    "ETF Score": "ETF Score",
    "ETF Signal": "ETF Signal",
    "Proposed Action": "Proposed Action",
    "Final Decision": "Final Decision",
    "Decision Status": "Decision Status",
    "Evidence Score": "Evidence Score",
    "Evidence Strength": "Evidence Strength",
    "Decision Support": "Evidence Support",
    "Deterministic Confidence": "Decision Confidence",
    "LLM Assessment": "LLM Review",
    "LLM Confidence": "LLM Confidence",
    "LLM Reason": "LLM Reason",
    "Reconciliation Status": "Reconciliation",
    "Reconciliation Reason": "Reconciliation Reason",
    "Reduction %": "Reduction %",
    "Released Capital": "Released Capital",
    "Buy Value": "Buy Value",
}

def create_capital_allocation_sheet(
    writer,
    capital_allocation
):
    """
    Create the Capital Allocation worksheet.

    Expected structure from generate_capital_allocation():

        {
            "Capital Summary": DataFrame,
            "Capital Allocation": DataFrame
        }

    The allocation DataFrame contains:
        BUY NEW
        BUY MORE
        REDUCE %
        SELL
        HOLD
    """

    print("Creating Capital Allocation")

    if capital_allocation is None:
        print("No capital allocation data available")
        return

    if not isinstance(capital_allocation, dict):
        print(
            "Capital allocation has unexpected type:",
            type(capital_allocation)
        )
        return

    sheet = "Capital Allocation"
    row = 0

    # =========================================================
    # GET DATA FROM CURRENT CAPITAL ALLOCATOR STRUCTURE
    # =========================================================

    summary_df = capital_allocation.get(
        "Capital Summary",
        pd.DataFrame()
    )

    allocation_df = capital_allocation.get(
        "Capital Allocation",
        pd.DataFrame()
    )

    if summary_df is None:
        summary_df = pd.DataFrame()

    if allocation_df is None:
        allocation_df = pd.DataFrame()

    if not isinstance(summary_df, pd.DataFrame):
        summary_df = pd.DataFrame(summary_df)

    if not isinstance(allocation_df, pd.DataFrame):
        allocation_df = pd.DataFrame(allocation_df)

    # =========================================================
    # HELPER
    # =========================================================

    def write_section(
        title,
        dataframe,
        current_row
    ):

        pd.DataFrame(
            {
                "Section": [title]
            }
        ).to_excel(
            writer,
            sheet_name=sheet,
            startrow=current_row,
            index=False
        )

        current_row += 2

        if (
            dataframe is not None
            and not dataframe.empty
        ):

            dataframe.to_excel(
                writer,
                sheet_name=sheet,
                startrow=current_row,
                index=False
            )

            current_row += len(dataframe) + 3

        else:

            pd.DataFrame(
                {
                    "Information": ["None"]
                }
            ).to_excel(
                writer,
                sheet_name=sheet,
                startrow=current_row,
                index=False
            )

            current_row += 4

        return current_row

    # =========================================================
    # CAPITAL SUMMARY
    # =========================================================

    row = write_section(
        "CAPITAL SUMMARY",
        summary_df,
        row
    )

    # =========================================================
    # SAFELY FILTER ALLOCATIONS
    # =========================================================

    if (
        not allocation_df.empty
        and
        "Action" in allocation_df.columns
    ):

        buy_new_df = allocation_df[
            allocation_df["Action"] == "BUY NEW"
        ].copy()

        buy_more_df = allocation_df[
            allocation_df["Action"] == "BUY MORE"
        ].copy()

        reduce_df = allocation_df[
            allocation_df["Action"].astype(str).str.startswith(
                "REDUCE"
            )
            |
            allocation_df["Action"].isin(
                ["SELL"]
            )
        ].copy()

        hold_df = allocation_df[
            allocation_df["Action"] == "HOLD"
        ].copy()

    else:

        buy_new_df = pd.DataFrame()
        buy_more_df = pd.DataFrame()
        reduce_df = pd.DataFrame()
        hold_df = pd.DataFrame()

    # =========================================================
    # BUY NEW
    # =========================================================

    row = write_section(
        "BUY NEW RECOMMENDATIONS",
        buy_new_df,
        row
    )

    # =========================================================
    # BUY MORE
    # =========================================================

    row = write_section(
        "BUY MORE RECOMMENDATIONS",
        buy_more_df,
        row
    )

    # =========================================================
    # REDUCE / SELL
    # =========================================================

    row = write_section(
        "REDUCE / SELL RECOMMENDATIONS",
        reduce_df,
        row
    )

    # =========================================================
    # HOLD
    # =========================================================

    row = write_section(
        "HOLD POSITIONS",
        hold_df,
        row
    )

    # =========================================================
    # ALL ACTIONS
    # =========================================================

    row = write_section(
        "ALL CAPITAL ALLOCATION ACTIONS",
        allocation_df,
        row
    )

    # =========================================================
    # BASIC FORMATTING
    # =========================================================

    try:

        workbook = writer.book
        worksheet = writer.sheets[sheet]

        # Works with openpyxl
        if hasattr(worksheet, "column_dimensions"):

            widths = {
                "A": 18,
                "B": 16,
                "C": 18,
                "D": 14,
                "E": 14,
                "F": 14,
                "G": 14,
                "H": 18,
                "I": 16,
                "J": 18,
                "K": 14,
                "L": 14,
                "M": 14,
                "N": 20,
                "O": 42,
                "P": 16,
                "Q": 16,
                "R": 16,
            }

            for column, width in widths.items():
                worksheet.column_dimensions[column].width = width

    except Exception as e:

        print(
            f"Capital Allocation formatting warning: {e}"
        )

    print("Capital Allocation sheet created")


def add_article_hyperlinks(

    worksheet,

    news_report,

    first_news_data_row

):

    """
    Convert Article URLs in the news table into
    clickable Excel hyperlinks.
    """

    if news_report.empty:

        return


    if "Article" not in news_report.columns:

        return


    article_column = (

        news_report.columns.get_loc(

            "Article"

        )

        + 1

    )


    for row_number in range(

        first_news_data_row,

        first_news_data_row + len(news_report)

    ):

        article_cell = worksheet.cell(

            row=row_number,

            column=article_column

        )


        article_url = article_cell.value


        if not article_url:

            continue


        article_cell.hyperlink = (

            str(article_url)

        )


        article_cell.value = (

            "Open Article"

        )


        article_cell.style = (

            "Hyperlink"

        )


def build_recommendation_quality_assessment(
    decision_performance,
    recommendation_evaluations=None,
    mi_snapshots=0,
    mi_with_outcomes=0,
):
    """
    Build the A5 Recommendation Quality & Improvement Assessment.

    This is an analytical layer only.

    It does not modify:
        - Investment Score
        - Evidence Score
        - Confidence
        - learning weights
        - thresholds
        - governance
        - final decisions
        - LLM authority

    A5 assesses currently realised outcomes and identifies
    evidence-based areas for further investigation.

    Recommendation-level performance uses the complete
    recommendation evaluation population.

    Final-action and governance analysis uses the
    audit-linked decision-performance population.
    """

    recommendation_quality_rows = []

    output_columns = [
        "Finding",
        "Evidence",
        "Impact",
        "Recommended improvement",
        "Confidence",
    ]

    if decision_performance is None:
        return pd.DataFrame(
            columns=output_columns
        )

    if not isinstance(
        decision_performance,
        pd.DataFrame,
    ):
        return pd.DataFrame(
            columns=output_columns
        )

    if decision_performance.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    if "return_percent" not in decision_performance.columns:
        return pd.DataFrame(
            columns=output_columns
        )

    # ============================================================
    # FINAL-ACTION / GOVERNANCE POPULATION
    # ============================================================

    evaluated = decision_performance[
        decision_performance[
            "return_percent"
        ].notna()
    ].copy()

    # ============================================================
    # OVERALL RECOMMENDATION PERFORMANCE
    # ============================================================
    #
    # Use the complete recommendation evaluation population,
    # not only audit-linked decisions.
    # ============================================================

    if (
        recommendation_evaluations is not None
        and isinstance(
            recommendation_evaluations,
            pd.DataFrame,
        )
        and not recommendation_evaluations.empty
        and "return_percent"
        in recommendation_evaluations.columns
        and "days_after"
        in recommendation_evaluations.columns
    ):

        recommendation_evaluated = (
            recommendation_evaluations[
                recommendation_evaluations[
                    "return_percent"
                ].notna()
                & recommendation_evaluations[
                    "days_after"
                ].eq(5)
            ]
        ).copy()

        if not recommendation_evaluated.empty:

            overall_return = (
                recommendation_evaluated[
                    "return_percent"
                ].mean()
            )

            overall_positive = (
                (
                    recommendation_evaluated[
                        "return_percent"
                    ] > 0
                ).mean()
                * 100
            )

            recommendation_quality_rows.append({
                "Finding":
                    "Overall realised recommendation performance",
                "Evidence":
                    (
                        f"{len(recommendation_evaluated)} "
                        "evaluated 5D recommendation outcomes; "
                        f"average realised return "
                        f"{overall_return:.2f}%; "
                        f"{overall_positive:.2f}% positive."
                    ),
                "Impact":
                    (
                        "This is the current realised-outcome "
                        "baseline for assessing whether the "
                        "recommendation system is generating wealth."
                    ),
                "Recommended improvement":
                    (
                        "Continue monitoring realised outcomes "
                        "across additional horizons before making "
                        "decision-engine changes."
                    ),
                "Confidence":
                    "Medium",
            })

    # ============================================================
    # ACTION-LEVEL PERFORMANCE
    # ============================================================

    if "final_action" in evaluated.columns:

        action_decision_counts = (
            decision_performance
            .groupby("final_action")
            .size()
        )

        for action, group in evaluated.groupby(
            "final_action"
        ):

            if group.empty:
                continue

            average_return = (
                group[
                    "return_percent"
                ].mean()
            )

            positive_return = (
                (
                    group[
                        "return_percent"
                    ] > 0
                ).mean()
                * 100
            )

            decision_count = int(
                action_decision_counts.get(
                    action,
                    0
                )
            )

            evaluated_count = len(group)

            coverage = (
                evaluated_count
                / decision_count
                * 100
                if decision_count
                else 0
            )

            if action in (
                "BUY",
                "BUY MORE",
                "BUY NEW",
                "STRONG BUY",
                "ADD",
            ):

                success_rate = positive_return

            elif action in (
                "SELL",
                "STRONG SELL",
                "REDUCE",
                "REDUCE 25%",
                "REDUCE 50%",
                "REDUCE 75%",
            ):

                success_rate = (
                    (
                        group[
                            "return_percent"
                        ] < 0
                    ).mean()
                    * 100
                )

            else:

                success_rate = (
                    (
                        group[
                            "return_percent"
                        ] >= 0
                    ).mean()
                    * 100
                )

            if evaluated_count >= 100:
                confidence = "High"

            elif evaluated_count >= 30:
                confidence = "Medium"

            else:
                confidence = "Low"

            recommendation_quality_rows.append({
                "Finding":
                    f"{action} outcome quality",
                "Evidence":
                    (
                        f"{evaluated_count} evaluated outcomes "
                        f"from {decision_count} decisions "
                        f"({coverage:.2f}% coverage); "
                        f"average 5D return "
                        f"{average_return:.2f}%; "
                        f"directional success "
                        f"{success_rate:.2f}%."
                    ),
                "Impact":
                    (
                        "Provides action-specific evidence of "
                        "whether the governed action is contributing "
                        "to the wealth-generation objective."
                    ),
                "Recommended improvement":
                    (
                        "Investigate actions with weak realised "
                        "outcomes while accounting for sample size, "
                        "coverage and market conditions before "
                        "changing decision rules."
                    ),
                "Confidence":
                    confidence,
            })

    # ============================================================
    # BUY NEW
    # ============================================================

    if "final_action" in evaluated.columns:

        buy_new = evaluated[
            evaluated[
                "final_action"
            ] == "BUY NEW"
        ]

        if not buy_new.empty:

            buy_new_return = (
                buy_new[
                    "return_percent"
                ].mean()
            )

            buy_new_positive = (
                (
                    buy_new[
                        "return_percent"
                    ] > 0
                ).mean()
                * 100
            )

            recommendation_quality_rows.append({
                "Finding":
                    "BUY NEW requires investigation",
                "Evidence":
                    (
                        f"{len(buy_new)} evaluated BUY NEW "
                        "outcomes; average 5D return "
                        f"{buy_new_return:.2f}%; "
                        f"{buy_new_positive:.2f}% positive."
                    ),
                "Impact":
                    (
                        "The currently realised BUY NEW outcomes "
                        "are weak and warrant investigation of "
                        "candidate selection, entry timing, "
                        "recommendation characteristics and "
                        "governance effects."
                    ),
                "Recommended improvement":
                    (
                        "Decompose BUY NEW outcomes by score, "
                        "confidence, evidence strength, signal, "
                        "candidate-selection rank and market "
                        "context before considering rule or "
                        "threshold changes."
                    ),
                "Confidence":
                    (
                        "Medium"
                        if len(buy_new) >= 30
                        else "Low"
                    ),
            })

    # ============================================================
    # BUY MORE
    # ============================================================

    if "final_action" in evaluated.columns:

        buy_more = evaluated[
            evaluated[
                "final_action"
            ] == "BUY MORE"
        ]

        if not buy_more.empty:

            buy_more_return = (
                buy_more[
                    "return_percent"
                ].mean()
            )

            recommendation_quality_rows.append({
                "Finding":
                    "BUY MORE requires relative-performance analysis",
                "Evidence":
                    (
                        f"{len(buy_more)} evaluated BUY MORE "
                        "outcomes; average 5D return "
                        f"{buy_more_return:.2f}%."
                    ),
                "Impact":
                    (
                        "Absolute return alone does not establish "
                        "whether BUY MORE adds value because the "
                        "relevant comparison is what would have "
                        "happened had the position remained a HOLD."
                    ),
                "Recommended improvement":
                    (
                        "Use matched counterfactual analysis to "
                        "determine whether BUY MORE decisions create "
                        "incremental wealth relative to HOLD."
                    ),
                "Confidence":
                    "Medium",
            })

    # ============================================================
    # HOLD
    # ============================================================

    if "final_action" in evaluated.columns:

        hold = evaluated[
            evaluated[
                "final_action"
            ] == "HOLD"
        ]

        if not hold.empty:

            hold_return = (
                hold[
                    "return_percent"
                ].mean()
            )

            recommendation_quality_rows.append({
                "Finding":
                    "HOLD establishes the decision baseline",
                "Evidence":
                    (
                        f"{len(hold)} evaluated HOLD outcomes; "
                        f"average 5D return "
                        f"{hold_return:.2f}%."
                    ),
                "Impact":
                    (
                        "HOLD provides the reference point against "
                        "which incremental BUY, BUY MORE, REDUCE "
                        "and SELL decisions should ultimately be "
                        "assessed."
                    ),
                "Recommended improvement":
                    (
                        "Use matched decision-level counterfactuals "
                        "rather than treating the aggregate HOLD "
                        "average as a causal benchmark."
                    ),
                "Confidence":
                    "High",
            })

    # ============================================================
    # SELL
    # ============================================================

    if "final_action" in evaluated.columns:

        sell = evaluated[
            evaluated[
                "final_action"
            ] == "SELL"
        ]

        if not sell.empty:

            sell_return = (
                sell[
                    "return_percent"
                ].mean()
            )

            sell_positive = (
                (
                    sell[
                        "return_percent"
                    ] > 0
                ).mean()
                * 100
            )

            recommendation_quality_rows.append({
                "Finding":
                    "SELL outcomes require economic "
                    "counterfactual analysis",
                "Evidence":
                    (
                        f"{len(sell)} evaluated SELL outcomes; "
                        f"average 5D return "
                        f"{sell_return:.2f}%; "
                        f"{sell_positive:.2f}% positive."
                    ),
                "Impact":
                    (
                        "A positive post-SELL return does not by "
                        "itself establish that SELL decisions failed, "
                        "because the economic outcome depends on "
                        "the capital that would otherwise have "
                        "remained invested."
                    ),
                "Recommended improvement":
                    (
                        "Evaluate SELL decisions using matched "
                        "counterfactual returns and released-capital "
                        "outcomes."
                    ),
                "Confidence":
                    "Medium",
            })

    # ============================================================
    # GOVERNANCE TRANSITIONS
    # ============================================================

    if {
        "signal",
        "final_action",
    }.issubset(evaluated.columns):

        transitions = (
            evaluated[
                [
                    "signal",
                    "final_action",
                ]
            ]
            .dropna()
            .groupby(
                [
                    "signal",
                    "final_action",
                ]
            )
            .size()
            .reset_index(
                name="Count"
            )
        )

        changed_transitions = transitions[
            transitions[
                "signal"
            ].astype(str)
            != transitions[
                "final_action"
            ].astype(str)
        ]

        if not changed_transitions.empty:

            transition_text = "; ".join(
                (
                    f"{row['signal']} → "
                    f"{row['final_action']}: "
                    f"{int(row['Count'])}"
                )
                for _, row in (
                    changed_transitions
                    .sort_values(
                        "Count",
                        ascending=False,
                    )
                    .head(10)
                    .iterrows()
                )
            )

            recommendation_quality_rows.append({
                "Finding":
                    "Governance changes recommendations",
                "Evidence":
                    (
                        "Observed recommendation-to-final-action "
                        f"transitions include: {transition_text}."
                    ),
                "Impact":
                    (
                        "Governance is an active part of the "
                        "decision chain, so recommendation quality "
                        "cannot be assessed independently of the "
                        "actions ultimately applied."
                    ),
                "Recommended improvement":
                    (
                        "Measure the realised outcome of changed "
                        "versus unchanged decisions to determine "
                        "whether governance improves or reduces "
                        "economic performance."
                    ),
                "Confidence":
                    "Medium",
            })

    # ============================================================
    # SCORE / CONFIDENCE RELATIONSHIPS
    # ============================================================

    score_columns = {
        "investment_score",
        "evidence_score",
        "confidence_score",
        "return_percent",
    }

    if score_columns.issubset(
        evaluated.columns
    ):

        score_relationships = []

        for metric in (
            "investment_score",
            "evidence_score",
            "confidence_score",
        ):

            valid = evaluated[
                [
                    metric,
                    "return_percent",
                ]
            ].dropna()

            if len(valid) >= 30:

                correlation = valid[
                    metric
                ].corr(
                    valid[
                        "return_percent"
                    ]
                )

                if pd.notna(
                    correlation
                ):

                    score_relationships.append(
                        (
                            metric,
                            correlation,
                        )
                    )

        if score_relationships:

            relationship_text = "; ".join(
                (
                    f"{metric} vs 5D return "
                    f"correlation {correlation:.2f}"
                )
                for metric, correlation
                in score_relationships
            )

            recommendation_quality_rows.append({
                "Finding":
                    "Score and confidence calibration requires validation",
                "Evidence":
                    relationship_text + ".",
                "Impact":
                    (
                        "These relationships indicate whether "
                        "higher internal conviction measures are "
                        "associated with better realised outcomes. "
                        "Correlation alone does not establish "
                        "causation or an appropriate threshold."
                    ),
                "Recommended improvement":
                    (
                        "Use these relationships to guide "
                        "threshold and error analysis rather than "
                        "changing thresholds directly."
                    ),
                "Confidence":
                    "Medium",
            })

    # ============================================================
    # MARKET INTELLIGENCE
    # ============================================================

    if (
        mi_snapshots > 0
        and mi_with_outcomes == 0
    ):

        recommendation_quality_rows.append({
            "Finding":
                "Market Intelligence cannot yet be evaluated economically",
            "Evidence":
                (
                    f"{mi_snapshots} Market Intelligence snapshots "
                    "are present, but none currently has a matched "
                    "5D realised outcome."
                ),
            "Impact":
                (
                    "There is currently no realised-outcome evidence "
                    "with which to determine whether Market "
                    "Intelligence improves decision quality."
                ),
            "Recommended improvement":
                (
                    "Allow the Market Intelligence shadow population "
                    "to mature and then evaluate its relationship "
                    "with realised outcomes."
                ),
            "Confidence":
                "High",
        })

    return pd.DataFrame(
        recommendation_quality_rows,
        columns=output_columns,
    )

def build_buy_new_decomposition(
    decision_performance,
):
    """
    Build descriptive BUY NEW performance decomposition.

    Analytical only.

    This routine does NOT:
        - change scoring
        - change thresholds
        - change governance
        - change decisions
        - modify learning
        - write to the database

    It decomposes realised BUY NEW performance by:
        - Investment Score
        - Evidence Score
        - Confidence Score
        - Original Signal

    Candidate-selection rank is intentionally not included here because
    it is not currently persisted in decision_performance.
    """

    output_columns = [
        "Dimension",
        "Band / Value",
        "Decision Count",
        "Evaluated Count",
        "Coverage %",
        "Average 5D Return %",
        "Median 5D Return %",
        "Positive 5D Return %",
    ]

    if not isinstance(
        decision_performance,
        pd.DataFrame,
    ):
        return pd.DataFrame(
            columns=output_columns
        )

    required_columns = {
        "final_action",
        "return_percent",
    }

    if not required_columns.issubset(
        decision_performance.columns
    ):
        return pd.DataFrame(
            columns=output_columns
        )

    buy_new = decision_performance[
        decision_performance[
            "final_action"
        ]
        .astype(str)
        .str.upper()
        .str.strip()
        .eq("BUY NEW")
    ].copy()

    if buy_new.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    # ------------------------------------------------------------
    # Restrict realised-outcome analysis to 5D
    # ------------------------------------------------------------

    if "days_after" not in buy_new.columns:
        return pd.DataFrame(
            columns=output_columns
        )

    buy_new_5d = buy_new[
        buy_new["days_after"] == 5
    ].copy()

    if buy_new_5d.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    rows = []
    # ============================================================
    # SCORE / CONFIDENCE BANDS
    # ============================================================

    dimensions = [
        (
            "Investment Score",
            "investment_score",
            [
                ("<60", float("-inf"), 60),
                ("60–69", 60, 70),
                ("70–79", 70, 80),
                ("80–89", 80, 90),
                ("90+", 90, float("inf")),
            ],
        ),
        (
            "Evidence Score",
            "evidence_score",
            [
                ("<60", float("-inf"), 60),
                ("60–69", 60, 70),
                ("70–79", 70, 80),
                ("80–89", 80, 90),
                ("90+", 90, float("inf")),
            ],
        ),
        (
            "Confidence Score",
            "confidence_score",
            [
                ("<60", float("-inf"), 60),
                ("60–69", 60, 70),
                ("70–79", 70, 80),
                ("80–89", 80, 90),
                ("90+", 90, float("inf")),
            ],
        ),
    ]

    for dimension, column, bands in dimensions:

        if column not in buy_new.columns:
            continue

        for label, minimum, maximum in bands:

            group = buy_new_5d[
                buy_new_5d[column].notna()
                & (
                    buy_new_5d[column] >= minimum
                )
                & (
                    buy_new_5d[column] < maximum
                )
            ]

            if group.empty:
                continue

            evaluated = group[
                group[
                    "return_percent"
                ].notna()
            ]

            if evaluated.empty:
                continue

            rows.append({
                "Dimension":
                    dimension,

                "Band / Value":
                    label,

                "Decision Count":
                    len(group),

                "Evaluated Count":
                    len(evaluated),

                "Coverage %":
                    round(
                        len(evaluated)
                        / len(group)
                        * 100,
                        2,
                    ),

                "Average 5D Return %":
                    round(
                        evaluated[
                            "return_percent"
                        ].mean(),
                        2,
                    ),

                "Median 5D Return %":
                    round(
                        evaluated[
                            "return_percent"
                        ].median(),
                        2,
                    ),

                "Positive 5D Return %":
                    round(
                        (
                            evaluated[
                                "return_percent"
                            ] > 0
                        ).mean()
                        * 100,
                        2,
                    ),
            })

    # ============================================================
    # ORIGINAL SIGNAL
    # ============================================================

    if "original_signal" in buy_new.columns:

        signal_data = buy_new_5d[
            buy_new_5d[
                "original_signal"
            ].notna()
        ]

        for signal, group in signal_data.groupby(
            "original_signal"
        ):

            evaluated = group[
                group[
                    "return_percent"
                ].notna()
            ]

            if evaluated.empty:
                continue

            rows.append({
                "Dimension":
                    "Original Signal",

                "Band / Value":
                    str(signal),

                "Decision Count":
                    len(group),

                "Evaluated Count":
                    len(evaluated),

                "Coverage %":
                    round(
                        len(evaluated)
                        / len(group)
                        * 100,
                        2,
                    ),

                "Average 5D Return %":
                    round(
                        evaluated[
                            "return_percent"
                        ].mean(),
                        2,
                    ),

                "Median 5D Return %":
                    round(
                        evaluated[
                            "return_percent"
                        ].median(),
                        2,
                    ),

                "Positive 5D Return %":
                    round(
                        (
                            evaluated[
                                "return_percent"
                            ] > 0
                        ).mean()
                        * 100,
                        2,
                    ),
            })

    return pd.DataFrame(
        rows,
        columns=output_columns,
    )

def build_calibration_recommendations(
    decision_performance,
    recommendation_evaluations=None,
    threshold_analysis=None,
    recommendation_quality_assessment=None,
    model_vs_market_intelligence=None,
):
    """
    Build advisory calibration recommendations from realised
    recommendation and governed-decision performance evidence.

    A6 — Calibration Recommendations.

    This routine is analytical and advisory only.

    It does NOT:
        - change scores
        - change score weights
        - change thresholds
        - change governance
        - change decisions
        - modify learning
        - modify portfolio allocation
        - modify the audit database

    Evidence populations are deliberately kept distinct:

        recommendation_evaluations
            Recommendation-level realised outcomes.

        decision_performance
            Governed final-action outcomes.

        threshold_analysis
            Descriptive score / confidence / evidence bands.

        recommendation_quality_assessment
            A5 findings requiring further calibration
            investigation.

        model_vs_market_intelligence
            Comparison of model direction against Market
            Intelligence direction.

    A6 converts observed evidence into explicit candidate
    calibration investigations. It does not implement them.

    Returns:
        DataFrame with the standard A6 output columns.
    """

    output_columns = [
        "Problem",
        "Evidence",
        "Likely Mechanism",
        "Agent Component",
        "Proposed Resolution",
        "Implementation Approach",
        "Validation Required",
        "Expected Effect",
        "Risk/Trade-off",
        "Confidence",
        "Recommendation/Status",
    ]

    rows = []

    # ============================================================
    # SAFETY / INPUT NORMALISATION
    # ============================================================

    if not isinstance(
        decision_performance,
        pd.DataFrame,
    ):
        decision_performance = pd.DataFrame()

    if not isinstance(
        recommendation_evaluations,
        pd.DataFrame,
    ):
        recommendation_evaluations = pd.DataFrame()

    if not isinstance(
        threshold_analysis,
        pd.DataFrame,
    ):
        threshold_analysis = pd.DataFrame()

    if not isinstance(
        recommendation_quality_assessment,
        pd.DataFrame,
    ):
        recommendation_quality_assessment = pd.DataFrame()

    if not isinstance(
        model_vs_market_intelligence,
        pd.DataFrame,
    ):
        model_vs_market_intelligence = pd.DataFrame()

    # ------------------------------------------------------------
    # Normalise recommendation-level outcomes
    # ------------------------------------------------------------

    recommendation_outcomes = (
        recommendation_evaluations.copy()
    )

    if not recommendation_outcomes.empty:

        if "days_after" in recommendation_outcomes.columns:
            recommendation_outcomes = (
                recommendation_outcomes[
                    recommendation_outcomes[
                        "days_after"
                    ].eq(5)
                ]
                .copy()
            )

        if "return_percent" in recommendation_outcomes.columns:
            recommendation_outcomes = (
                recommendation_outcomes[
                    recommendation_outcomes[
                        "return_percent"
                    ].notna()
                ]
                .copy()
            )

    # ------------------------------------------------------------
    # Normalise governed decision outcomes
    # ------------------------------------------------------------

    governed_outcomes = (
        decision_performance.copy()
    )

    if not governed_outcomes.empty:

        if "days_after" in governed_outcomes.columns:
            governed_outcomes = (
                governed_outcomes[
                    governed_outcomes[
                        "days_after"
                    ].eq(5)
                ]
                .copy()
            )

        if "return_percent" in governed_outcomes.columns:
            governed_outcomes = (
                governed_outcomes[
                    governed_outcomes[
                        "return_percent"
                    ].notna()
                ]
                .copy()
            )

    # ============================================================
    # HELPERS
    # ============================================================

    def safe_number(value):
        try:
            value = float(value)
            if pd.isna(value):
                return None
            return value
        except (
            TypeError,
            ValueError,
        ):
            return None

    def fmt(value, decimals=2):
        value = safe_number(value)

        if value is None:
            return "n/a"

        return f"{value:.{decimals}f}"

    def add_recommendation(
        problem,
        evidence,
        mechanism,
        component,
        resolution,
        implementation,
        validation,
        expected_effect,
        risk,
        confidence,
        status="PROPOSED — HUMAN REVIEW REQUIRED",
    ):
        rows.append(
            {
                "Problem": problem,
                "Evidence": evidence,
                "Likely Mechanism": mechanism,
                "Agent Component": component,
                "Proposed Resolution": resolution,
                "Implementation Approach": implementation,
                "Validation Required": validation,
                "Expected Effect": expected_effect,
                "Risk/Trade-off": risk,
                "Confidence": confidence,
                "Recommendation/Status": status,
            }
        )

    def action_stats(action):
        if governed_outcomes.empty:
            return None

        if "final_action" not in governed_outcomes.columns:
            return None

        group = governed_outcomes[
            governed_outcomes[
                "final_action"
            ]
            .astype(str)
            .str.upper()
            .str.strip()
            == action.upper()
        ]

        if group.empty:
            return None

        returns = pd.to_numeric(
            group["return_percent"],
            errors="coerce",
        ).dropna()

        if returns.empty:
            return None

        return {
            "count": len(group),
            "average": returns.mean(),
            "median": returns.median(),
            "positive": (
                returns.gt(0).mean() * 100
            ),
        }

    def find_a5_finding(pattern):
        """
        Find an A5 finding containing the supplied terms.
        """
        if recommendation_quality_assessment.empty:
            return None

        if "Finding" not in (
            recommendation_quality_assessment.columns
        ):
            return None

        findings = (
            recommendation_quality_assessment[
                "Finding"
            ]
            .astype(str)
        )

        mask = pd.Series(
            True,
            index=findings.index,
        )

        for term in pattern:
            mask &= findings.str.contains(
                term,
                case=False,
                na=False,
            )

        matches = recommendation_quality_assessment[
            mask
        ]

        if matches.empty:
            return None

        return matches.iloc[0]

    def threshold_rows(
        dimension=None,
        population=None,
        horizon=5,
    ):
        """
        Return relevant threshold-analysis rows.
        """
        if threshold_analysis.empty:
            return pd.DataFrame()

        working = threshold_analysis.copy()

        if dimension is not None:
            if "Dimension" not in working.columns:
                return pd.DataFrame()

            working = working[
                working["Dimension"]
                .astype(str)
                .str.upper()
                .eq(
                    str(dimension).upper()
                )
            ]

        if population is not None:
            if "Population" not in working.columns:
                return pd.DataFrame()

            working = working[
                working["Population"]
                .astype(str)
                .str.upper()
                .eq(
                    str(population).upper()
                )
            ]

        if "Horizon Days" in working.columns:
            working = working[
                pd.to_numeric(
                    working["Horizon Days"],
                    errors="coerce",
                ).eq(horizon)
            ]

        return working.copy()

    # ============================================================
    # 1. BUY NEW CALIBRATION INVESTIGATION
    # ============================================================

    buy_new = action_stats("BUY NEW")

    if buy_new is not None:

        a5_buy_new = find_a5_finding(
            ["BUY NEW"]
        )

        evidence_parts = [
            (
                f"Governed BUY NEW decisions: "
                f"{buy_new['count']}"
            ),
            (
                f"5D average return: "
                f"{fmt(buy_new['average'])}%"
            ),
            (
                f"5D median return: "
                f"{fmt(buy_new['median'])}%"
            ),
            (
                f"Positive 5D outcomes: "
                f"{fmt(buy_new['positive'])}%"
            ),
        ]

        if (
            a5_buy_new is not None
            and "Evidence"
            in a5_buy_new.index
        ):
            evidence_parts.append(
                f"A5: {a5_buy_new['Evidence']}"
            )

        # Add descriptive threshold evidence where available.
        investment_bands = threshold_rows(
            dimension="Investment Score",
            population="Recommendations",
        )

        if not investment_bands.empty:
            evidence_parts.append(
                "Investment Score band performance is "
                "available in A4 threshold analysis."
            )

        confidence_bands = threshold_rows(
            dimension="Confidence Score",
            population="Recommendations",
        )

        if not confidence_bands.empty:
            evidence_parts.append(
                "Confidence Score band performance is "
                "available in A4 threshold analysis."
            )

        add_recommendation(
            problem=(
                "BUY NEW decisions require calibration "
                "investigation because realised governed "
                "performance is materially weaker than "
                "the decision system intends."
            ),
            evidence="; ".join(evidence_parts),
            mechanism=(
                "The current BUY NEW candidate-selection and "
                "entry process may admit candidates whose "
                "combined evidence does not translate into "
                "sufficient near-term realised performance."
            ),
            component=(
                "BUY NEW candidate selection / decision "
                "eligibility"
            ),
            resolution=(
                "Test a composite BUY NEW eligibility model "
                "rather than relying on a single score or "
                "single signal condition. Candidate inputs "
                "should include Investment Score, Evidence "
                "Score, Confidence Score, candidate rank and "
                "technical / entry-condition information."
            ),
            implementation=(
                "Create candidate BUY NEW rule variants as "
                "offline configurations. Run them against "
                "historical recommendation outcomes and "
                "compare them with the current production "
                "eligibility rule. Do not change production "
                "logic until an out-of-sample candidate "
                "configuration demonstrates improvement."
            ),
            validation=(
                "Require sufficient independent observations, "
                "5D and subsequently longer matured horizons, "
                "improvement in average and median return, "
                "positive-return rate, stability across time "
                "periods and matched comparison against HOLD. "
                "Check that any improvement is not caused by "
                "simply reducing coverage."
            ),
            expected_effect=(
                "Reduce weak BUY NEW entries while preserving "
                "access to candidates that demonstrate a "
                "stronger combination of evidence and entry "
                "conditions."
            ),
            risk=(
                "A stricter composite gate can reduce BUY NEW "
                "coverage and may exclude genuine winners. "
                "Overfitting the historical sample is also a "
                "material risk."
            ),
            confidence="HIGH",
        )

    # ============================================================
    # 2. BUY MORE CALIBRATION INVESTIGATION
    # ============================================================

    buy_more = action_stats("BUY MORE")

    if buy_more is not None:

        hold = action_stats("HOLD")

        evidence = (
            f"BUY MORE decisions: {buy_more['count']}; "
            f"5D average return "
            f"{fmt(buy_more['average'])}%; "
            f"median "
            f"{fmt(buy_more['median'])}%; "
            f"positive "
            f"{fmt(buy_more['positive'])}%."
        )

        if hold is not None:
            evidence += (
                f" HOLD reference: "
                f"{fmt(hold['average'])}% average 5D return."
            )

        add_recommendation(
            problem=(
                "BUY MORE performance requires incremental "
                "value analysis before any threshold or "
                "eligibility change."
            ),
            evidence=evidence,
            mechanism=(
                "Absolute BUY MORE return does not establish "
                "whether increasing an existing position adds "
                "value relative to simply holding it."
            ),
            component=(
                "BUY MORE decision eligibility and governance"
            ),
            resolution=(
                "Use matched BUY MORE versus HOLD "
                "counterfactual analysis to identify the "
                "conditions under which BUY MORE creates "
                "incremental value."
            ),
            implementation=(
                "Construct matched cohorts using score, signal, "
                "sector, volatility, existing-position status "
                "and other relevant decision-state variables. "
                "Analyse incremental outcomes before proposing "
                "a production threshold change."
            ),
            validation=(
                "Require statistically meaningful sample size, "
                "positive incremental performance versus matched "
                "HOLD observations, temporal stability and "
                "acceptable turnover implications."
            ),
            expected_effect=(
                "Identify the circumstances in which BUY MORE "
                "adds genuine portfolio decision value rather "
                "than merely selecting securities that would "
                "have performed similarly if held."
            ),
            risk=(
                "Matching methodology can introduce selection "
                "bias. Insufficient sample size may also delay "
                "a reliable conclusion."
            ),
            confidence="HIGH",
        )

    # ============================================================
    # 3. INVESTMENT SCORE CALIBRATION
    # ============================================================

    investment_bands = threshold_rows(
        dimension="Investment Score",
        population="Recommendations",
    )

    if not investment_bands.empty:

        usable = investment_bands[
            pd.to_numeric(
                investment_bands[
                    "Evaluation Count"
                ],
                errors="coerce",
            ) > 0
        ].copy()

        if len(usable) >= 2:

            returns = pd.to_numeric(
                usable[
                    "Average Return %"
                ],
                errors="coerce",
            )

            scores = pd.to_numeric(
                usable[
                    "Average Score"
                ],
                errors="coerce",
            )

            valid = (
                scores.notna()
                & returns.notna()
            )

            if valid.sum() >= 2:

                correlation = scores[
                    valid
                ].corr(
                    returns[valid]
                )

                add_recommendation(
                    problem=(
                        "Investment Score calibration should "
                        "be tested against realised outcomes "
                        "rather than assuming that a higher "
                        "score necessarily represents a "
                        "proportionally higher expected return."
                    ),
                    evidence=(
                        f"A4 Investment Score band analysis "
                        f"contains {len(usable)} populated "
                        f"5D bands. The correlation across "
                        f"populated score-band averages is "
                        f"{fmt(correlation, 3)}."
                    ),
                    mechanism=(
                        "The Investment Score may be useful as "
                        "a ranking construct without being "
                        "well calibrated as a direct proxy for "
                        "near-term realised return."
                    ),
                    component=(
                        "Investment Score calculation / "
                        "component weighting"
                    ),
                    resolution=(
                        "Investigate recalibration of the "
                        "Investment Score by decomposing its "
                        "underlying components and testing "
                        "alternative weights, transformations "
                        "and action-specific interpretations."
                    ),
                    implementation=(
                        "Build offline score variants using "
                        "historical observations. Compare "
                        "monotonicity, discrimination and "
                        "out-of-sample realised performance "
                        "against the current score."
                    ),
                    validation=(
                        "Require out-of-sample validation, "
                        "stable score-to-outcome relationship "
                        "across time periods and horizons, "
                        "and evidence that any improvement "
                        "survives alternative model "
                        "specifications."
                    ),
                    expected_effect=(
                        "Improve the relationship between "
                        "Investment Score ordering and "
                        "subsequent realised performance."
                    ),
                    risk=(
                        "Reweighting can overfit historical "
                        "market regimes and may damage other "
                        "horizons or decision types."
                    ),
                    confidence="MEDIUM",
                )

    # ============================================================
    # 4. CONFIDENCE CALIBRATION
    # ============================================================

    confidence_bands = threshold_rows(
        dimension="Confidence Score",
        population="Recommendations",
    )

    if not confidence_bands.empty:

        usable = confidence_bands[
            pd.to_numeric(
                confidence_bands[
                    "Evaluation Count"
                ],
                errors="coerce",
            ) > 0
        ].copy()

        if len(usable) >= 2:

            returns = pd.to_numeric(
                usable[
                    "Average Return %"
                ],
                errors="coerce",
            )

            scores = pd.to_numeric(
                usable[
                    "Average Score"
                ],
                errors="coerce",
            )

            valid = (
                scores.notna()
                & returns.notna()
            )

            if valid.sum() >= 2:

                correlation = scores[
                    valid
                ].corr(
                    returns[valid]
                )

                add_recommendation(
                    problem=(
                        "Confidence Score requires calibration "
                        "validation before being given greater "
                        "decision influence."
                    ),
                    evidence=(
                        f"A4 contains {len(usable)} populated "
                        f"Confidence Score bands. The "
                        f"The correlation across populated "
                        f"confidence-band averages is "
                        f"{fmt(correlation, 3)}."
                    ),
                    mechanism=(
                        "Confidence may currently represent "
                        "decision certainty or evidence "
                        "completeness rather than a calibrated "
                        "probability of a successful outcome."
                    ),
                    component=(
                        "Confidence Score definition and "
                        "calibration"
                    ),
                    resolution=(
                        "First establish what Confidence Score "
                        "is intended to measure. If it is "
                        "intended to represent outcome "
                        "probability, recalibrate it against "
                        "realised outcomes. If it represents "
                        "evidence completeness or model "
                        "certainty, retain that semantic "
                        "distinction rather than treating it "
                        "as a probability."
                    ),
                    implementation=(
                        "Analyse confidence calibration curves, "
                        "score monotonicity and realised outcome "
                        "rates. Test recalibration methods "
                        "offline before considering any "
                        "production change."
                    ),
                    validation=(
                        "Require a stable monotonic relationship "
                        "between confidence and realised "
                        "outcomes, calibration error analysis, "
                        "sufficient independent observations "
                        "and out-of-sample confirmation."
                    ),
                    expected_effect=(
                        "Make Confidence Score interpretable "
                        "and ensure its influence on decisions "
                        "matches its actual predictive meaning."
                    ),
                    risk=(
                        "Recalibration can reduce apparent "
                        "confidence scores without improving "
                        "decision quality. Sample scarcity can "
                        "also produce unstable calibration."
                    ),
                    confidence="HIGH",
                )

    # ============================================================
    # 5. EVIDENCE SCORE CALIBRATION
    # ============================================================

    evidence_bands = threshold_rows(
        dimension="Evidence Score",
        population="Governed Decisions",
    )

    if not evidence_bands.empty:

        usable = evidence_bands[
            pd.to_numeric(
                evidence_bands[
                    "Evaluation Count"
                ],
                errors="coerce",
            ) > 0
        ].copy()

        if len(usable) >= 2:

            returns = pd.to_numeric(
                usable[
                    "Average Return %"
                ],
                errors="coerce",
            )

            scores = pd.to_numeric(
                usable[
                    "Average Score"
                ],
                errors="coerce",
            )

            valid = (
                scores.notna()
                & returns.notna()
            )

            if valid.sum() >= 2:

                correlation = scores[
                    valid
                ].corr(
                    returns[valid]
                )

                add_recommendation(
                    problem=(
                        "Evidence Score should be investigated "
                        "as a measure of evidence strength "
                        "separately from evidence predictiveness."
                    ),
                    evidence=(
                        f"A4 contains {len(usable)} populated "
                        f"Evidence Score bands for governed "
                        f"decisions. The correlation across "
                        f"populated evidence-band averages is "
                        f"{fmt(correlation, 3)}."
                    ),
                    mechanism=(
                        "A large quantity or apparent strength "
                        "of evidence does not necessarily mean "
                        "that the evidence is directionally "
                        "predictive of subsequent returns."
                    ),
                    component=(
                        "Evidence Score construction and "
                        "evidence weighting"
                    ),
                    resolution=(
                        "Decompose Evidence Score into its "
                        "underlying evidence categories and "
                        "measure each category's incremental "
                        "predictive contribution."
                    ),
                    implementation=(
                        "Run component-level historical analysis "
                        "and offline score variants. Determine "
                        "whether evidence components add "
                        "predictive information beyond the "
                        "Investment Score and technical model."
                    ),
                    validation=(
                        "Require incremental out-of-sample "
                        "predictive value, stability across "
                        "market regimes and evidence categories, "
                        "and no material degradation of "
                        "decision coverage."
                    ),
                    expected_effect=(
                        "Separate evidence completeness from "
                        "evidence that actually improves "
                        "decision quality."
                    ),
                    risk=(
                        "Removing apparently useful evidence "
                        "components can reduce robustness if "
                        "their value is regime-dependent."
                    ),
                    confidence="MEDIUM",
                )

    # ============================================================
    # 6. HOLD AS THE COUNTERFACTUAL BASELINE
    # ============================================================

    hold = action_stats("HOLD")

    if hold is not None:

        add_recommendation(
            problem=(
                "Unconditional action performance is not "
                "sufficient to calibrate decision rules because "
                "each action operates on a different security "
                "population."
            ),
            evidence=(
                f"The governed 5D HOLD population contains "
                f"{hold['count']} evaluated decisions with "
                f"average return {fmt(hold['average'])}% and "
                f"median return {fmt(hold['median'])}%."
            ),
            mechanism=(
                "Differences in unconditional action returns "
                "can reflect differences in the securities "
                "selected rather than the incremental effect "
                "of the action itself."
            ),
            component=(
                "Decision calibration / counterfactual "
                "evaluation"
            ),
            resolution=(
                "Make matched counterfactual analysis the "
                "primary calibration method for BUY, BUY MORE, "
                "REDUCE and SELL decisions."
            ),
            implementation=(
                "For each governed action, construct matched "
                "alternative-action cohorts using the "
                "decision state available at the time of the "
                "decision."
            ),
            validation=(
                "Require sufficient matched observations, "
                "balance diagnostics, incremental outcome "
                "analysis and stability across time and "
                "market regimes."
            ),
            expected_effect=(
                "Distinguish genuine decision value from "
                "security-selection effects."
            ),
            risk=(
                "Counterfactual matching is methodologically "
                "more complex and can reduce effective sample "
                "size."
            ),
            confidence="HIGH",
        )

    # ============================================================
    # 7. SELL / REDUCE COUNTERFACTUAL
    # ============================================================

    sell = action_stats("SELL")

    reduce_actions = [
        action
        for action in (
            "REDUCE",
            "REDUCE 25%",
            "REDUCE 50%",
            "REDUCE 75%",
        )
        if action_stats(action) is not None
    ]

    if sell is not None or reduce_actions:

        evidence = []

        if sell is not None:
            evidence.append(
                f"SELL has {sell['count']} evaluated "
                f"5D decisions with average post-decision "
                f"return {fmt(sell['average'])}%."
            )

        if reduce_actions:
            evidence.append(
                "Evaluated reduction actions: "
                + ", ".join(reduce_actions)
                + "."
            )

        add_recommendation(
            problem=(
                "SELL and REDUCE cannot be calibrated reliably "
                "from post-action security returns alone."
            ),
            evidence=" ".join(evidence),
            mechanism=(
                "A positive return after a SELL can represent "
                "an opportunity cost rather than a failure of "
                "the decision, because capital may have been "
                "released and redeployed elsewhere."
            ),
            component=(
                "SELL / REDUCE evaluation and capital "
                "reallocation measurement"
            ),
            resolution=(
                "Replace raw post-SELL / post-REDUCE return as "
                "the primary calibration metric with a "
                "retained-position versus released-capital "
                "counterfactual."
            ),
            implementation=(
                "Persist or reconstruct retained-position "
                "return, released capital, subsequent "
                "redeployment return and resulting portfolio "
                "value. Evaluate the action against the "
                "alternative of retaining the original "
                "position."
            ),
            validation=(
                "Demonstrate that the revised metric produces "
                "stable action-level conclusions and captures "
                "economic portfolio impact rather than merely "
                "security-price movement after the decision."
            ),
            expected_effect=(
                "Measure whether SELL and REDUCE decisions "
                "actually improved portfolio outcomes."
            ),
            risk=(
                "This requires additional capital-flow and "
                "portfolio-state data and therefore has greater "
                "implementation complexity."
            ),
            confidence="HIGH",
        )

    # ============================================================
    # 8. GOVERNANCE TRANSITIONS
    # ============================================================

    if not governed_outcomes.empty:

        transition_columns = {
            "original_action",
            "final_action",
            "return_percent",
        }

        if transition_columns.issubset(
            governed_outcomes.columns
        ):

            transitions = (
                governed_outcomes[
                    [
                        "original_action",
                        "final_action",
                        "return_percent",
                    ]
                ]
                .dropna(
                    subset=["return_percent"]
                )
                .copy()
            )

            transitions[
                "transition"
            ] = (
                transitions[
                    "original_action"
                ]
                .astype(str)
                .str.upper()
                .str.strip()
                + " → "
                + transitions[
                    "final_action"
                ]
                .astype(str)
                .str.upper()
                .str.strip()
            )

            transition_counts = (
                transitions[
                    "transition"
                ]
                .value_counts()
            )

            meaningful = transition_counts[
                transition_counts >= 10
            ]

            if not meaningful.empty:

                examples = [
                    f"{name} ({count})"
                    for name, count
                    in meaningful.head(5).items()
                ]

                add_recommendation(
                    problem=(
                        "Governance transitions should be "
                        "evaluated as explicit decision "
                        "experiments before changing "
                        "reconciliation rules."
                    ),
                    evidence=(
                        "Observed governed action transitions "
                        "include: "
                        + "; ".join(examples)
                        + "."
                    ),
                    mechanism=(
                        "A governance override can change the "
                        "economic action independently of the "
                        "underlying recommendation, making "
                        "aggregate recommendation performance "
                        "insufficient to evaluate the override."
                    ),
                    component=(
                        "Governance / reconciliation layer"
                    ),
                    resolution=(
                        "Measure the realised outcome of "
                        "original action versus governed final "
                        "action for each material transition."
                    ),
                    implementation=(
                        "Create transition-level counterfactual "
                        "datasets and evaluate them independently "
                        "from score calibration."
                    ),
                    validation=(
                        "Require adequate observations for each "
                        "transition type and demonstrate that "
                        "any proposed governance change improves "
                        "outcomes without merely shifting action "
                        "frequency."
                    ),
                    expected_effect=(
                        "Make governance overrides empirically "
                        "testable rather than relying on "
                        "aggregate action statistics."
                    ),
                    risk=(
                        "Some transition types may remain too "
                        "rare for statistically reliable "
                        "conclusions."
                    ),
                    confidence="MEDIUM",
                )

    # ============================================================
    # 9. MARKET INTELLIGENCE
    # ============================================================

    mi_available = (
        not model_vs_market_intelligence.empty
    )

    mi_outcome_count = 0

    if mi_available:

        if "5D Outcomes" in (
            model_vs_market_intelligence.columns
        ):
            mi_outcome_count = pd.to_numeric(
                model_vs_market_intelligence[
                    "5D Outcomes"
                ],
                errors="coerce",
            ).fillna(0).sum()

    if not mi_available or mi_outcome_count <= 0:

        add_recommendation(
            problem=(
                "Market Intelligence has not yet demonstrated "
                "matured incremental predictive value."
            ),
            evidence=(
                "The current model-versus-Market Intelligence "
                "dataset does not contain a matured 5D outcome "
                "population sufficient to establish incremental "
                "economic value."
            ),
            mechanism=(
                "Market and event context may contain useful "
                "information, but its independent contribution "
                "cannot be separated from the existing model "
                "without matched matured outcomes."
            ),
            component=(
                "Market & Event Intelligence"
            ),
            resolution=(
                "Keep Market Intelligence in shadow / advisory "
                "mode until it can be evaluated against matured "
                "matched outcomes."
            ),
            implementation=(
                "Continue persisting timestamped intelligence "
                "context and link it to future recommendations "
                "and realised outcomes without allowing it to "
                "alter scores, thresholds or governance."
            ),
            validation=(
                "Require a matured matched cohort and demonstrate "
                "incremental predictive value over the existing "
                "decision model."
            ),
            expected_effect=(
                "Prevent premature integration of contextual "
                "signals that have not demonstrated incremental "
                "economic value."
            ),
            risk=(
                "Potentially useful contextual information will "
                "remain advisory until sufficient outcome data "
                "matures."
            ),
            confidence="HIGH",
            status=(
                "DEFERRED — INSUFFICIENT MATURED EVIDENCE"
            ),
        )

    else:

        mi_outcome_returns = pd.Series(
            dtype=float
        )

        if (
            "Average 5D Return %"
            in model_vs_market_intelligence.columns
        ):
            mi_outcome_returns = pd.to_numeric(
                model_vs_market_intelligence[
                    "Average 5D Return %"
                ],
                errors="coerce",
            ).dropna()

        add_recommendation(
            problem=(
                "Market Intelligence now has matured outcome "
                "evidence and should be tested for incremental "
                "value rather than integrated directly."
            ),
            evidence=(
                f"Model-versus-Market Intelligence analysis "
                f"contains approximately "
                f"{int(mi_outcome_count)} matured 5D outcomes."
            ),
            mechanism=(
                "Market Intelligence may provide information "
                "that overlaps with the existing model or may "
                "add genuinely independent signal."
            ),
            component=(
                "Market & Event Intelligence"
            ),
            resolution=(
                "Test whether Market Intelligence adds "
                "incremental predictive value beyond the "
                "existing decision model."
            ),
            implementation=(
                "Compare matched model-only and model-plus-MI "
                "configurations using identical decision "
                "populations and out-of-sample evaluation."
            ),
            validation=(
                "Require incremental predictive improvement, "
                "economic significance, temporal stability and "
                "no unacceptable increase in false signals or "
                "decision turnover."
            ),
            expected_effect=(
                "Determine whether Market Intelligence merits "
                "a future controlled integration into the "
                "decision layer."
            ),
            risk=(
                "Adding contextual signals can increase model "
                "complexity and may introduce regime-specific "
                "noise."
            ),
            confidence="MEDIUM",
        )

    # ============================================================
    # FINAL OUTPUT
    # ============================================================

    if not rows:
        return pd.DataFrame(
            columns=output_columns
        )

    return pd.DataFrame(
        rows,
        columns=output_columns,
    )


def build_decision_performance_report():

    """
    Build the Decision Performance dataset from persisted audit,
    recommendation, outcome, and Market Intelligence data.

    Reporting / evaluation only.

    This routine does NOT:
        - change decisions
        - change thresholds
        - modify learning
        - modify portfolio allocation
        - write to the database

    The analysis uses two distinct populations:

        1. Recommendation performance
           Full recommendation history with available matured
           evaluation outcomes.

        2. Governed decision performance
           Audit-linked recommendations where the final governed
           action can be evaluated against realised outcomes.

    Returns:
        dict containing:
            summary
            action_performance
            recommendation_performance
            threshold_analysis
            model_vs_market_intelligence
            decision_audit
    """

    database_path = (
        "/Users/jameshulin/Documents/"
        "stock-momentum-agent/data/portfolio_manager.db"
    )

    empty_result = {
        "summary": pd.DataFrame(),
        "action_performance": pd.DataFrame(),
        "recommendation_performance": pd.DataFrame(),
        "threshold_analysis": pd.DataFrame(),
        "model_vs_market_intelligence": pd.DataFrame(),
        "calibration_recommendations":
            pd.DataFrame(),
        "buy_new_decomposition":
            pd.DataFrame(),
        "decision_audit": pd.DataFrame(),
    }

    if not os.path.exists(database_path):
        print(
            "WARNING: Decision Performance database not found"
        )
        return empty_result

    try:
        conn = sqlite3.connect(database_path)

        # ========================================================
        # 1. LOAD GOVERNED AUDIT DECISIONS
        # ========================================================

        audit_decisions = pd.read_sql_query(
            """
            SELECT
                ad.id AS audit_decision_id,
                ad.audit_run_id,
                ar.run_date AS audit_date,
                ad.recommendation_id,
                ad.ticker,
                ad.asset_type,
                ad.final_action,
                ad.proposed_action,
                ad.investment_score,
                ad.technical_score,
                ad.quality_score,
                ad.growth_score,
                ad.confidence_score,
                ad.evidence_score,
                ad.original_signal,
                ad.reconciliation_status
            FROM audit_decisions ad
            INNER JOIN audit_runs ar
                ON ar.id = ad.audit_run_id
            WHERE ar.status = 'COMPLETED'
            ORDER BY
                ar.run_date,
                ad.id
            """,
            conn,
        )

        if audit_decisions.empty:
            conn.close()
            return empty_result

        # ========================================================
        # 2. LOAD RECOMMENDATIONS
        # ========================================================

        recommendations = pd.read_sql_query(
            """
            SELECT
                id AS recommendation_id,
                date AS recommendation_date,
                ticker,
                signal,
                investment_score AS recommendation_investment_score,
                technical_score AS recommendation_technical_score,
                quality_score AS recommendation_quality_score,
                confidence_score AS recommendation_confidence_score,
                price AS recommendation_price
            FROM recommendations
            WHERE ticker IS NOT NULL
            """,
            conn,
        )

        recommendations["recommendation_date"] = (
            pd.to_datetime(
                recommendations["recommendation_date"],
                format="ISO8601",
                errors="coerce",
            ).dt.tz_localize(None)
        )

        audit_decisions["audit_date"] = (
            pd.to_datetime(
                audit_decisions["audit_date"],
                format="ISO8601",
                errors="coerce",
            ).dt.tz_localize(None)
        )

        audit_decisions = audit_decisions.dropna(
            subset=[
                "ticker",
                "audit_date",
            ]
        )

        recommendations = recommendations.dropna(
            subset=[
                "ticker",
                "recommendation_date",
            ]
        )

        # ============================================================
        # RECOMMENDATION LINEAGE
        # ============================================================
        #
        # Use persisted recommendation_id where available.
        # For legacy audit decisions without a recommendation_id,
        # reconstruct lineage using ticker + audit_date.
        # ============================================================

        audit_with_id = audit_decisions[
            audit_decisions["recommendation_id"].notna()
        ].copy()

        audit_without_id = audit_decisions[
            audit_decisions["recommendation_id"].isna()
        ].copy()

        # ------------------------------------------------------------
        # Modern lineage: persisted recommendation_id
        # ------------------------------------------------------------

        decision_with_id = audit_with_id.merge(
            recommendations,
            how="left",
            on="recommendation_id",
        )

        # ------------------------------------------------------------
        # Legacy lineage: reconstruct recommendation from
        # ticker + audit date
        # ------------------------------------------------------------

        if not audit_without_id.empty:
            legacy_audit = audit_without_id.drop(
                columns=["recommendation_id"]
            ).sort_values(
                ["audit_date", "ticker"]
            ).copy()

            legacy_recommendations = recommendations.sort_values(
                ["recommendation_date", "ticker"]
            ).copy()

            decision_without_id = pd.merge_asof(
                legacy_audit,
                legacy_recommendations,
                left_on="audit_date",
                right_on="recommendation_date",
                by="ticker",
                direction="backward",
                allow_exact_matches=True,
            )

            if (
                "confidence_score" in decision_without_id.columns
                and "recommendation_confidence_score" in decision_without_id.columns
            ):
                decision_without_id["confidence_score"] = (
                    decision_without_id["confidence_score"]
                    .combine_first(
                        decision_without_id["recommendation_confidence_score"]
                    )
                )
        else:
            decision_without_id = audit_without_id.copy()

        # ------------------------------------------------------------
        # Combine modern and legacy lineage
        # ------------------------------------------------------------

        decision_performance = pd.concat(
            [
                decision_with_id,
                decision_without_id,
            ],
            ignore_index=True,
        )

        # ========================================================
        # 3. LOAD MATURED OUTCOMES
        # ========================================================

        evaluations = pd.read_sql_query(
            """
            SELECT
                recommendation_id,
                evaluation_date,
                days_after,
                price AS evaluation_price,
                return_percent,
                outcome
            FROM recommendation_evaluations
            WHERE days_after IN (5, 10, 20, 60)
            """,
            conn,
        )

        if not evaluations.empty:

            evaluations["evaluation_date"] = (
                pd.to_datetime(
                    evaluations["evaluation_date"],
                    errors="coerce",
                )
            )

            evaluations = evaluations.sort_values(
                [
                    "recommendation_id",
                    "days_after",
                    "evaluation_date",
                ]
            )

            evaluations = evaluations.drop_duplicates(
                subset=[
                    "recommendation_id",
                    "days_after",
                ],
                keep="last",
            )

        # ========================================================
        # 3A. FULL RECOMMENDATION EVALUATION POPULATION
        # ========================================================

        if evaluations.empty:

            recommendation_evaluations = pd.DataFrame(
                columns=[
                    "recommendation_id",
                    "evaluation_date",
                    "days_after",
                    "evaluation_price",
                    "return_percent",
                    "outcome",
                    "signal",
                    "recommendation_date",
                    "recommendation_price",
                ]
            )

        else:

            recommendation_evaluations = evaluations.merge(
                recommendations[
                    [
                        "recommendation_id",
                        "recommendation_date",
                        "ticker",
                        "signal",
                        "recommendation_price",
                    ]
                ],
                how="left",
                on="recommendation_id",
            )

        # ========================================================
        # 3B. AUDIT-LINKED EVALUATIONS
        # ========================================================

        if not evaluations.empty:

            decision_performance = (
                decision_performance.merge(
                    evaluations,
                    how="left",
                    on="recommendation_id",
                )
            )

        else:

            decision_performance[
                "evaluation_date"
            ] = pd.NaT

            decision_performance[
                "days_after"
            ] = pd.NA

            decision_performance[
                "evaluation_price"
            ] = pd.NA

            decision_performance[
                "return_percent"
            ] = pd.NA

            decision_performance[
                "outcome"
            ] = pd.NA

        # ========================================================
        # 4. LOAD PERSISTED MARKET INTELLIGENCE SNAPSHOTS
        # ========================================================

        market_intelligence = pd.read_sql_query(
            """
            SELECT
                audit_decision_id,
                actual_value
            FROM audit_reasons
            WHERE reason_code =
                'MARKET_INTELLIGENCE_SNAPSHOT'
            """,
            conn,
        )

        conn.close()

        # ========================================================
        # 5. PARSE MARKET INTELLIGENCE
        # ========================================================

        mi_records = []

        for _, row in market_intelligence.iterrows():

            snapshot = {}

            try:
                snapshot = json.loads(
                    row["actual_value"]
                )

            except (
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                snapshot = {}

            if not isinstance(snapshot, dict):
                snapshot = {}

            snapshot["audit_decision_id"] = (
                row["audit_decision_id"]
            )

            mi_records.append(snapshot)

        if mi_records:

            mi_df = pd.DataFrame(
                mi_records
            )

            decision_performance = (
                decision_performance.merge(
                    mi_df,
                    how="left",
                    on="audit_decision_id",
                    suffixes=("", "_mi"),
                )
            )

        # ========================================================
        # 6. NORMALISE MARKET INTELLIGENCE COLUMNS
        # ========================================================

        mi_columns = [
            "Analyst Recommendation",
            "Analyst Mean Score",
            "Analyst Target Upside %",
            "Earnings Status",
            "News Count",
            "Collected At",
            "Source",
        ]

        for column in mi_columns:

            if column not in decision_performance.columns:
                decision_performance[column] = pd.NA

        # ========================================================
        # 7. MODEL DIRECTION
        # ========================================================

        def model_direction(action):

            action = str(
                action
            ).upper().strip()

            if action in {
                "BUY",
                "BUY MORE",
                "BUY NEW",
                "STRONG BUY",
                "ADD",
            }:
                return "POSITIVE"

            if action in {
                "SELL",
                "REDUCE",
                "REDUCE 25%",
                "REDUCE 50%",
                "REDUCE 75%",
                "STRONG SELL",
            }:
                return "NEGATIVE"

            return "NEUTRAL"

        decision_performance[
            "Model Direction"
        ] = (
            decision_performance[
                "final_action"
            ].apply(
                model_direction
            )
        )

        # ========================================================
        # 8. MARKET INTELLIGENCE DIRECTION
        # ========================================================

        def market_intelligence_direction(row):

            recommendation = str(
                row.get(
                    "Analyst Recommendation",
                    "",
                )
            ).upper().strip()

            if recommendation in {
                "BUY",
                "STRONG BUY",
                "OUTPERFORM",
            }:
                return "POSITIVE"

            if recommendation in {
                "SELL",
                "STRONG SELL",
                "UNDERPERFORM",
            }:
                return "NEGATIVE"

            if recommendation in {
                "HOLD",
                "NEUTRAL",
            }:
                return "NEUTRAL"

            try:

                target_upside = float(
                    row.get(
                        "Analyst Target Upside %",
                    )
                )

                if target_upside > 5:
                    return "POSITIVE"

                if target_upside < -5:
                    return "NEGATIVE"

            except (
                TypeError,
                ValueError,
            ):
                pass

            return "NO MI"

        decision_performance[
            "Market Intelligence Direction"
        ] = decision_performance.apply(
            market_intelligence_direction,
            axis=1,
        )

        # ========================================================
        # 9. A3 ECONOMIC PERFORMANCE ANALYSIS
        # ========================================================

        recommendation_evaluations = pd.read_sql_query(
            """
            SELECT
                re.recommendation_id,
                re.ticker,
                re.signal,
                re.evaluation_date,
                re.days_after,
                re.return_percent,
                re.recommendation_return_percent,
                re.recommendation_success,
                r.date AS recommendation_date,
                r.price AS recommendation_price,
                r.investment_score AS recommendation_investment_score,
                r.confidence_score AS recommendation_confidence_score
            FROM recommendation_evaluations re
            INNER JOIN recommendations r
                ON r.id = re.recommendation_id
            WHERE re.days_after IN (5, 10, 20, 60)
            """,
            sqlite3.connect(database_path)
        )

        if not recommendation_evaluations.empty:

            recommendation_evaluations[
                "evaluation_date"
            ] = pd.to_datetime(
                recommendation_evaluations[
                    "evaluation_date"
                ],
                errors="coerce"
            )

            recommendation_evaluations = (
                recommendation_evaluations
                .sort_values(
                    [
                        "recommendation_id",
                        "days_after",
                        "evaluation_date",
                    ]
                )
                .drop_duplicates(
                    subset=[
                        "recommendation_id",
                        "days_after",
                    ],
                    keep="last",
                )
            )

        horizon_rows = []

        for horizon in [5, 10, 20, 60]:

            horizon_df = recommendation_evaluations[
                recommendation_evaluations[
                    "days_after"
                ] == horizon
            ].copy()

            evaluated_horizon = horizon_df[
                horizon_df["return_percent"].notna()
            ].copy()

            if evaluated_horizon.empty:

                horizon_rows.append(
                    {
                        "Horizon": f"{horizon}D",
                        "Recommendation Count":
                            int(
                                horizon_df[
                                    "recommendation_id"
                                ].nunique()
                            ),
                        "Evaluated Count": 0,
                        "Evaluation Coverage %": 0.0,
                        "Average Realised Return %": None,
                        "Median Realised Return %": None,
                        "Positive Return %": None,
                        "Negative Return %": None,
                        "Status": "NO EVIDENCE YET",
                    }
                )

                continue

            recommendation_count = (
                horizon_df[
                    "recommendation_id"
                ].nunique()
            )

            evaluated_count = (
                evaluated_horizon[
                    "recommendation_id"
                ].nunique()
            )

            horizon_rows.append(
                {
                    "Horizon": f"{horizon}D",
                    "Recommendation Count":
                        int(recommendation_count),
                    "Evaluated Count":
                        int(evaluated_count),
                    "Evaluation Coverage %":
                        round(
                            (
                                evaluated_count
                                / recommendation_count
                                * 100
                            )
                            if recommendation_count
                            else 0.0,
                            2,
                        ),
                    "Average Realised Return %":
                        round(
                            evaluated_horizon[
                                "return_percent"
                            ].mean(),
                            2,
                        ),
                    "Median Realised Return %":
                        round(
                            evaluated_horizon[
                                "return_percent"
                            ].median(),
                            2,
                        ),
                    "Positive Return %":
                        round(
                            (
                                evaluated_horizon[
                                    "return_percent"
                                ] > 0
                            ).mean()
                            * 100,
                            2,
                        ),
                    "Negative Return %":
                        round(
                            (
                                evaluated_horizon[
                                    "return_percent"
                                ] < 0
                            ).mean()
                            * 100,
                            2,
                        ),
                    "Status": "MATURED",
                }
            )

        recommendation_performance = pd.DataFrame(
            horizon_rows
        )

        matured_horizons = (
            recommendation_performance[
                recommendation_performance["Evaluated Count"] > 0
            ]
            if not recommendation_performance.empty
            else pd.DataFrame()
        )

        if matured_horizons.empty:

            primary_horizon = None
            primary_horizon_df = pd.DataFrame()

        else:

            primary_horizon = int(
                matured_horizons.iloc[0][
                    "Horizon"
                ].replace("D", "")
            )

            primary_horizon_df = (
                recommendation_evaluations[
                    recommendation_evaluations[
                        "days_after"
                    ] == primary_horizon
                ]
                .copy()
            )

            primary_horizon_df = primary_horizon_df[
                primary_horizon_df[
                    "return_percent"
                ].notna()
            ]

        total_recommendations = (
            int(
                recommendation_evaluations[
                    "recommendation_id"
                ].nunique()
            )
            if not recommendation_evaluations.empty
            else 0
        )

        if primary_horizon is None:

            summary_rows = [
                {
                    "Metric":
                        "Total Recommendations",
                    "Value":
                        total_recommendations,
                },
                {
                    "Metric":
                        "Primary Evaluation Horizon",
                    "Value":
                        "NONE",
                },
                {
                    "Metric":
                        "Primary Horizon Status",
                    "Value":
                        "NO EVIDENCE YET",
                },
            ]

        else:

            primary_count = int(
                primary_horizon_df[
                    "recommendation_id"
                ].nunique()
            )

            summary_rows = [
                {
                    "Metric":
                        "Total Recommendations",
                    "Value":
                        total_recommendations,
                },
                {
                    "Metric":
                        "Primary Evaluation Horizon",
                    "Value":
                        f"{primary_horizon}D",
                },
                {
                    "Metric":
                        "Primary Horizon Evaluated Count",
                    "Value":
                        primary_count,
                },
                {
                    "Metric":
                        "Primary Horizon Average Realised Return %",
                    "Value":
                        round(
                            primary_horizon_df[
                                "return_percent"
                            ].mean(),
                            2,
                        ),
                },
                {
                    "Metric":
                        "Primary Horizon Median Realised Return %",
                    "Value":
                        round(
                            primary_horizon_df[
                                "return_percent"
                            ].median(),
                            2,
                        ),
                },
                {
                    "Metric":
                        "Primary Horizon Positive Return %",
                    "Value":
                        round(
                            (
                                primary_horizon_df[
                                    "return_percent"
                                ] > 0
                            ).mean()
                            * 100,
                            2,
                        ),
                },
            ]

        summary = pd.DataFrame(
            summary_rows
        )

        # ========================================================
        # GOVERNED ACTION PERFORMANCE
        # ========================================================

        action_horizon = 5

        action_evaluated = decision_performance[
            (
                decision_performance[
                    "days_after"
                ] == action_horizon
            )
            &
            decision_performance[
                "return_percent"
            ].notna()
        ].copy()

        action_decision_counts = (
            decision_performance
            .groupby("final_action")
            .size()
            .rename("Decision Count")
        )

        if action_evaluated.empty:

            action_performance = pd.DataFrame(
                columns=[
                    "Final Action",
                    "Decision Count",
                    "Evaluated Count",
                    "Evaluation Coverage %",
                    "Average 5D Return %",
                    "Median 5D Return %",
                    "Positive 5D Return %",
                    "Action-Aware Success %",
                    "Average Confidence",
                    "Average Evidence",
                ]
            )

        else:

            def assess_action_outcome(
                action,
                realised_return,
            ):

                if pd.isna(realised_return):
                    return "NO OUTCOME"

                action = str(
                    action
                ).upper().strip()

                if action in {
                    "BUY",
                    "BUY MORE",
                    "BUY NEW",
                    "STRONG BUY",
                    "ADD",
                }:
                    if realised_return > 0:
                        return "SUCCESS"
                    if realised_return < 0:
                        return "FAILURE"
                    return "FLAT"

                if action == "HOLD":
                    if realised_return >= 0:
                        return "SUCCESS"
                    return "FAILURE"

                if action in {
                    "SELL",
                    "STRONG SELL",
                    "REDUCE",
                    "REDUCE 25%",
                    "REDUCE 50%",
                    "REDUCE 75%",
                }:
                    if realised_return < 0:
                        return "SUCCESS"
                    if realised_return > 0:
                        return "FAILURE"
                    return "FLAT"

                return "NOT DEFINED"

            action_evaluated[
                "Action Outcome"
            ] = action_evaluated.apply(
                lambda row:
                    assess_action_outcome(
                        row["final_action"],
                        row["return_percent"],
                    ),
                axis=1,
            )

            action_rows = []

            for action, group in (
                action_evaluated
                .groupby("final_action")
            ):

                decision_count = int(
                    action_decision_counts.get(
                        action,
                        0,
                    )
                )

                evaluated_count = len(group)

                success_count = (
                    group[
                        "Action Outcome"
                    ] == "SUCCESS"
                ).sum()

                action_rows.append(
                    {
                        "Final Action":
                            action,
                        "Decision Count":
                            decision_count,
                        "Evaluated Count":
                            evaluated_count,
                        "Evaluation Coverage %":
                            round(
                                (
                                    evaluated_count
                                    / decision_count
                                    * 100
                                )
                                if decision_count
                                else 0.0,
                                2,
                            ),
                        "Average 5D Return %":
                            round(
                                group[
                                    "return_percent"
                                ].mean(),
                                2,
                            ),
                        "Median 5D Return %":
                            round(
                                group[
                                    "return_percent"
                                ].median(),
                                2,
                            ),
                        "Positive 5D Return %":
                            round(
                                (
                                    group[
                                        "return_percent"
                                    ] > 0
                                ).mean()
                                * 100,
                                2,
                            ),
                        "Action-Aware Success %":
                            round(
                                (
                                    success_count
                                    / evaluated_count
                                    * 100
                                )
                                if evaluated_count
                                else 0.0,
                                2,
                            ),
                        "Average Confidence":
                            round(
                                group[
                                    "confidence_score"
                                ].mean(),
                                2,
                            ),
                        "Average Evidence":
                            round(
                                group[
                                    "evidence_score"
                                ].mean(),
                                2,
                            ),
                    }
                )

            action_performance = pd.DataFrame(
                action_rows
            )

            if not action_performance.empty:

                action_order = [
                    "BUY NEW",
                    "BUY MORE",
                    "BUY",
                    "HOLD",
                    "REDUCE 25%",
                    "REDUCE 50%",
                    "REDUCE 75%",
                    "REDUCE",
                    "SELL",
                ]

                action_performance[
                    "_order"
                ] = action_performance[
                    "Final Action"
                ].apply(
                    lambda value:
                        action_order.index(value)
                        if value in action_order
                        else 999
                )

                action_performance = (
                    action_performance
                    .sort_values("_order")
                    .drop(columns="_order")
                    .reset_index(drop=True)
                )

        # ========================================================
        # RECOMMENDATION-LEVEL PERFORMANCE
        # ========================================================

        recommendation_evaluated = (
            recommendation_evaluations[
                recommendation_evaluations[
                    "return_percent"
                ].notna()
            ].copy()
        )

        # ========================================================
        # A4. SCORE / THRESHOLD ANALYSIS
        #
        # Descriptive analysis only.
        #
        # These bands are analytical buckets, NOT model
        # thresholds and do not alter any decision logic.
        # ========================================================

        threshold_rows = []

        def build_threshold_rows(
            dataframe,
            dimension,
            value_column,
            bands,
        ):
            """
            Build descriptive performance statistics for a
            score / confidence dimension.
            """

            rows = []

            if dataframe.empty:
                return rows

            required_columns = {
                "recommendation_id",
                "days_after",
                "return_percent",
                value_column,
            }

            if not required_columns.issubset(
                dataframe.columns
            ):
                return rows

            working = dataframe[
                [
                    "recommendation_id",
                    "days_after",
                    "return_percent",
                    value_column,
                ]
            ].copy()

            working = working[
                working[value_column].notna()
                & working["return_percent"].notna()
            ]

            if working.empty:
                return rows

            working["_Band"] = pd.cut(
                working[value_column],
                bins=[
                    bands[0]["min"],
                    *[
                        band["max"]
                        for band in bands
                    ],
                ],
                labels=[
                    band["label"]
                    for band in bands
                ],
                right=False,
                include_lowest=True,
            )

            for (
                horizon,
                horizon_group,
            ) in working.groupby(
                "days_after",
                dropna=False,
                observed=True,
            ):

                for (
                    band,
                    group,
                ) in horizon_group.groupby(
                    "_Band",
                    dropna=False,
                    observed=True,
                ):

                    if group.empty:
                        continue

                    threshold_rows.append(
                        {
                            "Population":
                                "Recommendations",
                            "Dimension":
                                dimension,
                            "Band":
                                str(band),
                            "Horizon Days":
                                int(horizon),
                            "Evaluation Count":
                                len(group),
                            "Recommendation Count":
                                group[
                                    "recommendation_id"
                                ].nunique(),
                            "Average Return %":
                                round(
                                    group[
                                        "return_percent"
                                    ].mean(),
                                    2,
                                ),
                            "Median Return %":
                                round(
                                    group[
                                        "return_percent"
                                    ].median(),
                                    2,
                                ),
                            "Positive Return %":
                                round(
                                    (
                                        group[
                                            "return_percent"
                                        ] > 0
                                    ).mean()
                                    * 100,
                                    2,
                                ),
                            "Negative Return %":
                                round(
                                    (
                                        group[
                                            "return_percent"
                                        ] < 0
                                    ).mean()
                                    * 100,
                                    2,
                                ),
                            "Average Score":
                                round(
                                    group[
                                        value_column
                                    ].mean(),
                                    2,
                                ),
                        }
                    )

            return rows

        # --------------------------------------------------------
        # Investment Score
        # --------------------------------------------------------

        investment_score_bands = [
            {
                "label": "<60",
                "min": float("-inf"),
                "max": 60,
            },
            {
                "label": "60–69",
                "min": 60,
                "max": 70,
            },
            {
                "label": "70–79",
                "min": 70,
                "max": 80,
            },
            {
                "label": "80–89",
                "min": 80,
                "max": 90,
            },
            {
                "label": "90+",
                "min": 90,
                "max": float("inf"),
            },
        ]

        build_threshold_rows(
            recommendation_evaluated,
            "Investment Score",
            "recommendation_investment_score",
            investment_score_bands,
        )

        # --------------------------------------------------------
        # Confidence
        # --------------------------------------------------------

        confidence_bands = [
            {
                "label": "<50",
                "min": float("-inf"),
                "max": 50,
            },
            {
                "label": "50–59",
                "min": 50,
                "max": 60,
            },
            {
                "label": "60–69",
                "min": 60,
                "max": 70,
            },
            {
                "label": "70–79",
                "min": 70,
                "max": 80,
            },
            {
                "label": "80–89",
                "min": 80,
                "max": 90,
            },
            {
                "label": "90+",
                "min": 90,
                "max": float("inf"),
            },
        ]

        build_threshold_rows(
            recommendation_evaluated,
            "Confidence Score",
            "recommendation_confidence_score",
            confidence_bands,
        )

        # --------------------------------------------------------
        # Evidence Score
        #
        # Evidence is a governed-decision attribute, so it is
        # analysed from the audit-linked population.
        # --------------------------------------------------------

        evidence_source = decision_performance[
            [
                "audit_decision_id",
                "days_after",
                "return_percent",
                "evidence_score",
            ]
        ].copy()

        evidence_source = evidence_source[
            evidence_source["return_percent"].notna()
            & evidence_source["evidence_score"].notna()
        ]

        evidence_bands = [
            {
                "label": "<50",
                "min": float("-inf"),
                "max": 50,
            },
            {
                "label": "50–59",
                "min": 50,
                "max": 60,
            },
            {
                "label": "60–69",
                "min": 60,
                "max": 70,
            },
            {
                "label": "70–79",
                "min": 70,
                "max": 80,
            },
            {
                "label": "80–89",
                "min": 80,
                "max": 90,
            },
            {
                "label": "90+",
                "min": 90,
                "max": float("inf"),
            },
        ]

        if not evidence_source.empty:

            evidence_source["_Band"] = pd.cut(
                evidence_source[
                    "evidence_score"
                ],
                bins=[
                    evidence_bands[0]["min"],
                    *[
                        band["max"]
                        for band in evidence_bands
                    ],
                ],
                labels=[
                    band["label"]
                    for band in evidence_bands
                ],
                right=False,
                include_lowest=True,
            )

            for (
                horizon,
                horizon_group,
            ) in evidence_source.groupby(
                "days_after",
                dropna=False,
                observed=True,
            ):

                for (
                    band,
                    group,
                ) in horizon_group.groupby(
                    "_Band",
                    dropna=False,
                    observed=True,
                ):

                    if group.empty:
                        continue

                    threshold_rows.append(
                        {
                            "Population":
                                "Governed Decisions",
                            "Dimension":
                                "Evidence Score",
                            "Band":
                                str(band),
                            "Horizon Days":
                                int(horizon),
                            "Evaluation Count":
                                len(group),
                            "Governed Decision Count":
                                group[
                                    "audit_decision_id"
                                ].nunique(),
                            "Average Return %":
                                round(
                                    group[
                                        "return_percent"
                                    ].mean(),
                                    2,
                                ),
                            "Median Return %":
                                round(
                                    group[
                                        "return_percent"
                                    ].median(),
                                    2,
                                ),
                            "Positive Return %":
                                round(
                                    (
                                        group[
                                            "return_percent"
                                        ] > 0
                                    ).mean()
                                    * 100,
                                    2,
                                ),
                            "Negative Return %":
                                round(
                                    (
                                        group[
                                            "return_percent"
                                        ] < 0
                                    ).mean()
                                    * 100,
                                    2,
                                ),
                            "Average Score":
                                round(
                                    group[
                                        "evidence_score"
                                    ].mean(),
                                    2,
                                ),
                        }
                    )

        threshold_analysis = pd.DataFrame(
            threshold_rows
        )

        if not threshold_analysis.empty:

            threshold_analysis = (
                threshold_analysis
                .sort_values(
                    [
                        "Population",
                        "Dimension",
                        "Horizon Days",
                        "Band",
                    ]
                )
                .reset_index(drop=True)
            )

        # ========================================================
        # KEEP AUDIT POPULATION COUNTS DISTINCT
        # ========================================================

        summary = pd.concat(
            [
                summary,
                pd.DataFrame(
                    [
                        {
                            "Metric":
                                "Governed Audit Decisions",
                            "Value":
                                len(
                                    decision_performance
                                ),
                        },
                        {
                            "Metric":
                                "Governed Decisions With 5D Outcome",
                            "Value":
                                len(
                                    action_evaluated
                                ),
                        },
                    ]
                ),
            ],
            ignore_index=True,
        )

        # ========================================================
        # 11. ACTION-AWARE OUTCOME ASSESSMENT
        # ========================================================

        def assess_action_outcome(row):

            action = str(
                row["final_action"]
            ).upper().strip()

            value = row["return_percent"]

            if pd.isna(value):
                return "NO 5D OUTCOME"

            try:

                value = float(value)

            except (
                TypeError,
                ValueError,
            ):

                return "NO 5D OUTCOME"

            if action in {
                "BUY",
                "BUY MORE",
                "BUY NEW",
                "STRONG BUY",
                "ADD",
            }:

                if value > 0:
                    return "SUCCESS"

                if value < 0:
                    return "FAILURE"

                return "FLAT"

            if action == "HOLD":

                if value >= 0:
                    return "SUCCESS"

                return "FAILURE"

            if action in {
                "SELL",
                "REDUCE",
                "REDUCE 25%",
                "REDUCE 50%",
                "REDUCE 75%",
                "STRONG SELL",
            }:

                if value < 0:
                    return "SUCCESS"

                if value > 0:
                    return "FAILURE"

                return "FLAT"

            return "NOT EVALUATED"

        decision_performance[
            "Action Outcome"
        ] = decision_performance.apply(
            assess_action_outcome,
            axis=1,
        )

        # ========================================================
        # 12. FINAL DECISION AUDIT DATASET
        # ========================================================

        decision_audit_columns = [
            "audit_date",
            "ticker",
            "asset_type",
            "final_action",
            "investment_score",
            "evidence_score",
            "confidence_score",
            "recommendation_date",
            "signal",
            "recommendation_id",
            "return_percent",
            "outcome",
            "Analyst Recommendation",
            "Analyst Mean Score",
            "Analyst Target Upside %",
            "Earnings Status",
            "News Count",
            "Model Direction",
            "Market Intelligence Direction",
            "Model vs Market Intelligence",
            "Action Outcome",
        ]

        decision_audit = decision_performance[
            [
                column
                for column in decision_audit_columns
                if column in decision_performance.columns
            ]
        ].copy()

        if "audit_date" in decision_audit.columns:

            decision_audit = (
                decision_audit
                .sort_values(
                    "audit_date",
                    ascending=False,
                )
                .head(100)
                .reset_index(drop=True)
            )

        decision_audit = decision_audit.rename(
            columns={
                "audit_date":
                    "Audit Date",
                "ticker":
                    "Ticker",
                "asset_type":
                    "Asset Type",
                "final_action":
                    "Final Action",
                "investment_score":
                    "Investment Score",
                "evidence_score":
                    "Evidence Score",
                "confidence_score":
                    "Decision Confidence",
                "recommendation_date":
                    "Recommendation Date",
                "signal":
                    "Recommendation Signal",
                "recommendation_id":
                    "Recommendation ID",
                "return_percent":
                    "5D Return %",
                "outcome":
                    "5D Outcome",
            }
        )

        # ========================================================
        # 13. ACTION PERFORMANCE
        # ========================================================

        action_rows = []

        for action, group in decision_performance.groupby(
            "final_action",
            dropna=False,
        ):

            outcomes = group[
                (group["days_after"] == 5)
                & group["return_percent"].notna()
            ]


            avg_return = (
                outcomes[
                    "return_percent"
                ].mean()
                if not outcomes.empty
                else None
            )

            median_return = (
                outcomes[
                    "return_percent"
                ].median()
                if not outcomes.empty
                else None
            )

            positive_pct = (
                (
                    outcomes[
                        "return_percent"
                    ] > 0
                ).mean()
                * 100
                if not outcomes.empty
                else None
            )

            evaluated_outcomes = outcomes[
                outcomes[
                    "Action Outcome"
                ].isin(
                    [
                        "SUCCESS",
                        "FAILURE",
                    ]
                )
            ]

            success_pct = (
                (
                    evaluated_outcomes[
                        "Action Outcome"
                    ] == "SUCCESS"
                ).mean()
                * 100
                if not evaluated_outcomes.empty
                else None
            )

            average_confidence = (
                group[
                    "confidence_score"
                ].mean()
                if "confidence_score"
                in group.columns
                else None
            )

            average_evidence = (
                group[
                    "evidence_score"
                ].mean()
                if "evidence_score"
                in group.columns
                else None
            )

            action_rows.append(
                {
                    "Final Action":
                        action,
                    "Decisions":
                        len(group),
                    "5D Outcomes":
                        len(outcomes),
                    "5D Coverage %":
                        (
                            len(outcomes)
                            / len(group)
                            * 100
                            if len(group)
                            else None
                        ),
                    "Average 5D Return %":
                        avg_return,
                    "Median 5D Return %":
                        median_return,
                    "Positive 5D %":
                        positive_pct,
                    "Action-Aware Success %":
                        success_pct,
                    "Average Decision Confidence":
                        average_confidence,
                    "Average Evidence Score":
                        average_evidence,
                }
            )

        action_performance = pd.DataFrame(
            action_rows
        )

        # ========================================================
        # 14. COMPARE AGAINST HOLD
        # ========================================================

        hold_rows = decision_performance[
            (
                decision_performance[
                    "final_action"
                ]
                .astype(str)
                .str.upper()
                == "HOLD"
            )
            & decision_performance[
                "return_percent"
            ].notna()
        ]

        hold_average = (
            hold_rows[
                "return_percent"
            ].mean()
            if not hold_rows.empty
            else None
        )

        action_performance[
            "Average 5D Return vs HOLD %"
        ] = (
            action_performance[
                "Average 5D Return %"
            ]
            - hold_average
            if hold_average is not None
            else pd.NA
        )

        # ========================================================
        # 15. MODEL VS MARKET INTELLIGENCE PERFORMANCE
        # ========================================================

        mi_rows = decision_performance[
            decision_performance[
                "Market Intelligence Direction"
            ].isin(
                [
                    "POSITIVE",
                    "NEGATIVE",
                    "NEUTRAL",
                ]
            )
        ].copy()

        if mi_rows.empty:

            model_vs_market_intelligence = pd.DataFrame()

        else:

            def compare_model_vs_market_intelligence(row):

                model = row["Model Direction"]
                market = row[
                    "Market Intelligence Direction"
                ]

                if (
                    model in {"POSITIVE", "NEGATIVE"}
                    and model == market
                ):
                    return "AGREE"

                if (
                    model in {"POSITIVE", "NEGATIVE"}
                    and market in {"POSITIVE", "NEGATIVE"}
                    and model != market
                ):
                    return "DISAGREE"

                if model == "NEUTRAL":
                    return "MODEL NEUTRAL"

                return "MI NEUTRAL"

            mi_rows[
                "Model vs Market Intelligence"
            ] = mi_rows.apply(
                compare_model_vs_market_intelligence,
                axis=1,
            )

            decision_performance[
                "Model vs Market Intelligence"
            ] = pd.NA

            decision_performance.loc[
                mi_rows.index,
                "Model vs Market Intelligence",
            ] = mi_rows[
                "Model vs Market Intelligence"
            ]

            model_vs_market_intelligence_rows = []

            for comparison, group in mi_rows.groupby(
                "Model vs Market Intelligence"
            ):

                outcomes = group[
                    group["return_percent"].notna()
                ]

                model_vs_market_intelligence_rows.append(
                    {
                        "Model vs Market Intelligence":
                            comparison,
                        "Decisions":
                            len(group),
                        "5D Outcomes":
                            len(outcomes),
                        "Average 5D Return %":
                            (
                                outcomes[
                                    "return_percent"
                                ].mean()
                                if not outcomes.empty
                                else None
                            ),
                        "Positive 5D %":
                            (
                                (
                                    outcomes[
                                        "return_percent"
                                    ] > 0
                                ).mean()
                                * 100
                                if not outcomes.empty
                                else None
                            ),
                    }
                )

            model_vs_market_intelligence = pd.DataFrame(
                model_vs_market_intelligence_rows
            )

        # ========================================================
        # 16. SUMMARY
        # ========================================================

        audit_decision_count = len(
            decision_performance
        )

        recommendation_count = (
            len(recommendations)
        )

        evaluated_recommendation_count = (
            recommendation_evaluated[
                "recommendation_id"
            ].nunique()
            if not recommendation_evaluated.empty
            else 0
        )

        recommendation_evaluation_count = (
            len(
                recommendation_evaluated
            )
        )

        recommendation_average_return = (
            recommendation_evaluated[
                "return_percent"
            ].mean()
            if not recommendation_evaluated.empty
            else None
        )

        recommendation_positive_pct = (
            (
                recommendation_evaluated[
                    "return_percent"
                ] > 0
            ).mean()
            * 100
            if not recommendation_evaluated.empty
            else None
        )

        recommendation_matches = (
            decision_performance[
                "recommendation_id"
            ].notna().sum()
        )

        five_day_outcomes = (
            decision_performance[
                "return_percent"
            ].notna().sum()
        )

        mi_snapshots = (
            decision_performance[
                "Analyst Recommendation"
            ].notna()
            | decision_performance[
                "Analyst Mean Score"
            ].notna()
            | decision_performance[
                "Analyst Target Upside %"
            ].notna()
        ).sum()

        mi_with_outcomes = (
            decision_performance[
                "Market Intelligence Direction"
            ].ne("NO MI")
            & decision_performance[
                "return_percent"
            ].notna()
        ).sum()

        summary = pd.DataFrame(
            [
                {
                    "Metric":
                        "Total recommendations",
                    "Value":
                        recommendation_count,
                },
                {
                    "Metric":
                        "Evaluated recommendations",
                    "Value":
                        evaluated_recommendation_count,
                },
                {
                    "Metric":
                        "Recommendation evaluation observations",
                    "Value":
                        recommendation_evaluation_count,
                },
                {
                    "Metric":
                        "Primary Horizon Average Realised Return %",
                    "Value":
                        (
                            round(
                                primary_horizon_df[
                                    "return_percent"
                                ].mean(),
                                2,
                            )
                            if not primary_horizon_df.empty
                            else None
                        ),
                },

                {
                    "Metric":
                        "Primary Horizon Positive Return %",
                    "Value":
                        (
                            round(
                                (
                                    primary_horizon_df[
                                        "return_percent"
                                    ] > 0
                                ).mean()
                                * 100,
                                2,
                            )
                            if not primary_horizon_df.empty
                            else None
                        ),
                },
                {
                    "Metric":
                        "Audit decisions",
                    "Value":
                        audit_decision_count,
                },
                {
                    "Metric":
                        "Recommendation matches",
                    "Value":
                        recommendation_matches,
                },
                {
                    "Metric":
                        "5D audit outcomes",
                    "Value":
                        five_day_outcomes,
                },
                {
                    "Metric":
                        "5D audit outcome coverage %",
                    "Value":
                        (
                            five_day_outcomes
                            / audit_decision_count
                            * 100
                            if audit_decision_count
                            else 0
                        ),
                },
                {
                    "Metric":
                        "Market Intelligence snapshots",
                    "Value":
                        mi_snapshots,
                },
                {
                    "Metric":
                        "Market Intelligence + 5D outcome",
                    "Value":
                        mi_with_outcomes,
                },
                {
                    "Metric":
                        "HOLD average 5D return %",
                    "Value":
                        hold_average,
                },
            ]
        )

        # ========================================================
        # RECOMMENDATION QUALITY & IMPROVEMENT ASSESSMENT
        # ========================================================

        recommendation_quality_assessment = (
            build_recommendation_quality_assessment(
                decision_performance,
                recommendation_evaluations=recommendation_evaluations,
                mi_snapshots=mi_snapshots,
                mi_with_outcomes=mi_with_outcomes,
            )
        )

        # ========================================================
        # A6. CALIBRATION RECOMMENDATIONS
        # ========================================================

        calibration_recommendations = (
            build_calibration_recommendations(
                decision_performance,
                recommendation_evaluations=recommendation_evaluations,
                threshold_analysis=threshold_analysis,
                recommendation_quality_assessment=(
                    recommendation_quality_assessment
                ),
                model_vs_market_intelligence=(
                    model_vs_market_intelligence
                ),
            )
        )

        # ========================================================
        # BUY NEW PERFORMANCE DECOMPOSITION
        # ========================================================

        buy_new_decomposition = (
            build_buy_new_decomposition(
                decision_performance
            )
        )


        # ========================================================
        # 17. CLEAN DISPLAY TYPES
        # ========================================================

        if "Audit Date" in decision_audit.columns:

            decision_audit[
                "Audit Date"
            ] = (
                pd.to_datetime(
                    decision_audit[
                        "Audit Date"
                    ],
                    errors="coerce",
                )
                .dt.strftime(
                    "%Y-%m-%d"
                )
            )

        if "Recommendation Date" in decision_audit.columns:

            decision_audit[
                "Recommendation Date"
            ] = (
                pd.to_datetime(
                    decision_audit[
                        "Recommendation Date"
                    ],
                    errors="coerce",
                )
                .dt.strftime(
                    "%Y-%m-%d"
                )
            )

        print(
            "Decision Performance:"
            f" {audit_decision_count} audit decisions,"
            f" {evaluated_recommendation_count}"
            " evaluated recommendations,"
            f" {recommendation_evaluation_count}"
            " evaluation observations,"
            f" {five_day_outcomes}"
            " audit decisions with 5D outcomes,"
            f" {mi_snapshots}"
            " with Market Intelligence."
        )

        return {
            "summary":
                summary,
            "action_performance":
                action_performance,
            "recommendation_performance":
                recommendation_performance,
            "threshold_analysis":
                threshold_analysis,
            "model_vs_market_intelligence":
                model_vs_market_intelligence,
            "recommendation_quality_assessment":
                recommendation_quality_assessment,
            "calibration_recommendations":
                calibration_recommendations,
            "buy_new_decomposition":
                buy_new_decomposition,
            "decision_audit":
                decision_audit,
        }

    except Exception as exc:

        print(
            "ERROR: Decision Performance analysis failed:"
            f" {exc}"
        )

        return empty_result  

def create_report(
    results,
    portfolio_summary,
    alerts,
    sector_summary,
    portfolio_actions,
    portfolio_optimisation,
    rebalance_recommendations,
    portfolio_health,
    capital_allocation,
    market_intelligence=None,
    portfolio_reallocation=None,
    decisions=None,
    trade_plan=None,
    performance_summary=None,
    signal_performance=None,
    horizon_performance=None,
    score_performance=None,
    score_bucket_performance=None,
    component_score_performance=None,
    signal_horizon_performance=None,
    recommendation_intelligence=None,
    portfolio_ai_review=None,
    portfolio_manager_review=None,
    growth_plan=None,
    final_portfolio_decisions=None,
    recommendation_learning=None
):

    print("STARTING REPORT CREATION")

    # =========================================================
    # DECISION PERFORMANCE
    # =========================================================

    print(
        "Creating Decision Performance"
    )

    decision_performance = (
        build_decision_performance_report()
    )

    # =========================================================
    # SAFETY HANDLING
    # =========================================================

    if results is None:
        results = []

    # Convert None values to safe DataFrames where appropriate
    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()

    if alerts is None:
        alerts = pd.DataFrame()

    if sector_summary is None:
        sector_summary = pd.DataFrame()

    if portfolio_actions is None:
        portfolio_actions = pd.DataFrame()

    if portfolio_optimisation is None:
        portfolio_optimisation = pd.DataFrame()

    if rebalance_recommendations is None:
        rebalance_recommendations = pd.DataFrame()


    if decisions is None:
        decisions = pd.DataFrame()

    if trade_plan is None:
        trade_plan = pd.DataFrame()

    if performance_summary is None:
        performance_summary = pd.DataFrame()

    if signal_performance is None:
        signal_performance = pd.DataFrame()

    if horizon_performance is None:
        horizon_performance = pd.DataFrame()

    if score_performance is None:
        score_performance = pd.DataFrame()

    if score_bucket_performance is None:
        score_bucket_performance = pd.DataFrame()

    if component_score_performance is None:
        component_score_performance = pd.DataFrame()

    if signal_horizon_performance is None:
        signal_horizon_performance = pd.DataFrame()

    if recommendation_intelligence is None:
        recommendation_intelligence = pd.DataFrame()

    if portfolio_ai_review is None:
        portfolio_ai_review = pd.DataFrame()

    if portfolio_manager_review is None:
        portfolio_manager_review = {}

    if growth_plan is None:
        growth_plan = []

    if final_portfolio_decisions is None:
        final_portfolio_decisions = pd.DataFrame()

    if recommendation_learning is None:
        recommendation_learning = {}

    if market_intelligence is None:
        market_intelligence = pd.DataFrame()

    if portfolio_reallocation is None:

        portfolio_reallocation = {

            "reallocation": pd.DataFrame(),

            "summary": {}

        }

    # =========================================================
    # NORMALISE DATAFRAMES
    # =========================================================

    dataframe_names = [
        "portfolio_summary",
        "alerts",
        "sector_summary",
        "portfolio_actions",
        "portfolio_optimisation",
        "rebalance_recommendations",
        "market_intelligence",
        "decisions",
        "trade_plan",
        "performance_summary",
        "signal_performance",
        "horizon_performance",
        "score_performance",
        "score_bucket_performance",
        "component_score_performance",
        "signal_horizon_performance",
        "recommendation_intelligence",
        "portfolio_ai_review",
        "final_portfolio_decisions"
    ]

    for name in dataframe_names:

        value = locals().get(name)

        if not isinstance(value, pd.DataFrame):

            try:
                value = pd.DataFrame(value)
            except Exception:
                value = pd.DataFrame()

            locals()[name] = value

    # Explicit assignments because modifying locals() is unreliable
    if not isinstance(portfolio_summary, pd.DataFrame):
        portfolio_summary = pd.DataFrame(portfolio_summary)

    if not isinstance(alerts, pd.DataFrame):
        alerts = pd.DataFrame(alerts)

    if not isinstance(sector_summary, pd.DataFrame):
        sector_summary = pd.DataFrame(sector_summary)

    if not isinstance(portfolio_actions, pd.DataFrame):
        portfolio_actions = pd.DataFrame(portfolio_actions)

    if not isinstance(portfolio_optimisation, pd.DataFrame):
        portfolio_optimisation = pd.DataFrame(portfolio_optimisation)

    if not isinstance(rebalance_recommendations, pd.DataFrame):
        rebalance_recommendations = pd.DataFrame(
            rebalance_recommendations
        )

    if not isinstance(decisions, pd.DataFrame):
        decisions = pd.DataFrame(decisions)

    if not isinstance(trade_plan, pd.DataFrame):
        trade_plan = pd.DataFrame(trade_plan)

    if not isinstance(performance_summary, pd.DataFrame):
        performance_summary = pd.DataFrame(performance_summary)

    if not isinstance(signal_performance, pd.DataFrame):
        signal_performance = pd.DataFrame(signal_performance)

    if not isinstance(horizon_performance, pd.DataFrame):
        horizon_performance = pd.DataFrame(horizon_performance)

    if not isinstance(score_performance, pd.DataFrame):
        score_performance = pd.DataFrame(score_performance)

    if not isinstance(score_bucket_performance, pd.DataFrame):
        score_bucket_performance = pd.DataFrame(
            score_bucket_performance
        )

    if not isinstance(component_score_performance, pd.DataFrame):
        component_score_performance = pd.DataFrame(
            component_score_performance
        )

    if not isinstance(signal_horizon_performance, pd.DataFrame):
        signal_horizon_performance = pd.DataFrame(
            signal_horizon_performance
        )

    if not isinstance(recommendation_intelligence, pd.DataFrame):
        recommendation_intelligence = pd.DataFrame(
            recommendation_intelligence
        )

    if isinstance(portfolio_ai_review, list):
        portfolio_ai_review = pd.DataFrame(
            portfolio_ai_review
        )

    if not isinstance(portfolio_ai_review, pd.DataFrame):
        portfolio_ai_review = pd.DataFrame(
            portfolio_ai_review
        )

    if not isinstance(final_portfolio_decisions, pd.DataFrame):
        final_portfolio_decisions = pd.DataFrame(
            final_portfolio_decisions
        )

    # =========================================================
    # DEBUG INFORMATION
    # =========================================================

    print(
        "RECOMMENDATION INTELLIGENCE SHAPE:",
        recommendation_intelligence.shape
    )

    print(
        "ALERTS SHAPE:",
        alerts.shape
    )

    print(
        "RECOMMENDATION LEARNING TYPE:",
        type(recommendation_learning)
    )

    if isinstance(
        recommendation_learning,
        dict
    ):

        print(
            "RECOMMENDATION LEARNING KEYS:",
            list(
                recommendation_learning.keys()
            )
        )

    # =========================================================
    # FILENAME
    # =========================================================

    report_path = (
        "/Users/jameshulin/Documents/"
        "stock-momentum-agent/reports/"
    )

    os.makedirs(
        report_path,
        exist_ok=True
    )

    filename = os.path.join(
        report_path,
        f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

    print("CREATING REPORT")

    print(
        "Stocks:",
        len(results)
    )

    print(
        "Portfolio:",
        len(portfolio_summary)
    )

    print(
        "Alerts:",
        len(alerts)
    )

    # =========================================================
    # CREATE WORKBOOK
    # =========================================================

    with pd.ExcelWriter(
        filename,
        engine="openpyxl"
    ) as writer:

        # =====================================================
        # EXECUTIVE SUMMARY
        # =====================================================

        print(
            "Creating Executive Summary"
        )

        summary_rows = [

            [
                "STOCK MOMENTUM AGENT - EXECUTIVE SUMMARY"
            ],

            [
                "Generated",
                datetime.now().strftime(
                    "%d %B %Y %H:%M"
                )
            ],

            [],

            [
                "PORTFOLIO OVERVIEW"
            ],

            [
                "Metric",
                "Value"
            ],

            [
                "Stocks Scanned",
                len(results)
            ],

            [
                "Portfolio Holdings",
                len(portfolio_summary)
            ],

            [
                "Alerts",
                len(alerts)
            ],

            [],

            [
                "PORTFOLIO HEALTH"
            ]

        ]

        # -----------------------------------------------------
        # Portfolio Health
        # -----------------------------------------------------

        if isinstance(
            portfolio_health,
            dict
        ):

            summary_rows.extend([

                [
                    "Health Score",
                    portfolio_health.get(
                        "Health Score",
                        ""
                    )
                ],

                [
                    "Rating",
                    portfolio_health.get(
                        "Rating",
                        ""
                    )
                ]

            ])

        # -----------------------------------------------------
        # Portfolio Manager Intelligence
        # -----------------------------------------------------

        if isinstance(
            portfolio_manager_review,
            dict
        ):

            summary_rows.extend([

                [],

                [
                    "AI PORTFOLIO MANAGER VIEW"
                ],

                [
                    "Market View",
                    portfolio_manager_review.get(
                        "Market View",
                        ""
                    )
                ],

                [
                    "Portfolio Status",
                    portfolio_manager_review.get(
                        "Portfolio Status",
                        ""
                    )
                ],

                [
                    "AI Summary",
                    portfolio_manager_review.get(
                        "AI Summary",
                        ""
                    )
                ]

            ])

            summary_rows.append([])

            summary_rows.append(
                [
                    "KEY STRENGTHS"
                ]
            )

            for item in portfolio_manager_review.get(
                "Key Strengths",
                []
            ):

                summary_rows.append(
                    [
                        item
                    ]
                )

            summary_rows.append([])

            summary_rows.append(
                [
                    "KEY RISKS"
                ]
            )

            for item in portfolio_manager_review.get(
                "Key Risks",
                []
            ):

                summary_rows.append(
                    [
                        item
                    ]
                )

            summary_rows.append([])

            summary_rows.append(
                [
                    "PRIORITY ACTIONS"
                ]
            )

            for item in portfolio_manager_review.get(
                "Priority Actions",
                []
            ):

                summary_rows.append(
                    [
                        item
                    ]
                )

        # -----------------------------------------------------
        # Top Opportunities
        # -----------------------------------------------------

        summary_rows.extend([

            [],

            [
                "TOP OPPORTUNITIES"
            ],

            [
                "Ticker",
                "Signal",
                "Investment Score"
            ]

        ])

        if len(results) > 0:

            results_df = pd.DataFrame(
                results
            )

            if "Investment Score" in results_df.columns:

                opportunities = (
                    results_df
                    .sort_values(
                        "Investment Score",
                        ascending=False
                    )
                    .head(5)
                )

            else:

                opportunities = results_df.head(5)

            for _, stock in opportunities.iterrows():

                summary_rows.append(
                    [

                        stock.get(
                            "Ticker",
                            ""
                        ),

                        stock.get(
                            "Signal",
                            ""
                        ),

                        stock.get(
                            "Investment Score",
                            ""
                        )

                    ]
                )

        pd.DataFrame(
            summary_rows
        ).to_excel(
            writer,
            sheet_name="Executive Summary",
            index=False,
            header=False
        )

        # =====================================================
        # HOW TO USE
        # =====================================================

        print(
            "Creating How To Use"
        )

        pd.DataFrame(
            {
                "Instructions": [

                    "Executive Summary provides portfolio overview",

                    "Stock Rankings shows investment opportunities",

                    "Portfolio Actions shows recommended changes",

                    "Capital Allocation shows suggested buys, reductions, sector avoidance and cash deployment",

                    "Recommendation Intelligence measures historical recommendation quality",

                    "Recommendation Learning measures how recommendation quality changes across horizons, signals, scores and confidence levels"

                ]
            }

        ).to_excel(
            writer,
            sheet_name="How To Use",
            index=False
        )

        # =====================================================
        # CAPITAL ALLOCATION
        # =====================================================

        print(
            "Creating Capital Allocation"
        )

        create_capital_allocation_sheet(
            writer,
            capital_allocation
        )

        # =====================================================
        # MARKET INTELLIGENCE
        # =====================================================

        # =====================================================
        # MARKET INTELLIGENCE
        # =====================================================

        print(
            "Creating Market Intelligence"
        )

        market_intelligence_report = (
            market_intelligence.copy()
        )

        preferred_columns = [
            "Ticker",
            "Name",
            "Current Portfolio Action",
            "Existing Holding",
            "Investment Score",
            "Allocation %",
            "Analyst Recommendation",
            "Analyst Mean Score",
            "Current Price",
            "Analyst Target Mean",
            "Analyst Target High",
            "Analyst Target Low",
            "Analyst Target Upside %",
            "Earnings Status",
            "Next Earnings Date",
            "News Count",
            "News Headlines",
            "Collected At",
            "Source",
        ]

        available_columns = [
            column
            for column in preferred_columns
            if column in market_intelligence_report.columns
        ]

        remaining_columns = [
            column
            for column in market_intelligence_report.columns
            if (
                column not in available_columns
                and column != "Recent News"
            )
        ]

        market_intelligence_report = (
            market_intelligence_report[
                available_columns
                + remaining_columns
            ]
        )

        market_intelligence_sheet_name = (
            "Market Intelligence"
        )

        # -----------------------------------------------------
        # MARKET INTELLIGENCE SUMMARY TABLE
        # -----------------------------------------------------

        market_intelligence_report.to_excel(
            writer,
            sheet_name=market_intelligence_sheet_name,
            index=False
        )

        # -----------------------------------------------------
        # DETAILED MARKET & EVENT NEWS
        # -----------------------------------------------------

        if (
            market_intelligence is not None
            and not market_intelligence.empty
        ):

            print(
                "Adding detailed Market & Event News"
            )

            news_rows = []

            for _, intelligence_row in (
                market_intelligence.iterrows()
            ):

                ticker = intelligence_row.get(
                    "Ticker",
                    ""
                )

                news_items = intelligence_row.get(
                    "Recent News",
                    []
                )

                if not isinstance(
                    news_items,
                    list
                ):
                    continue

                for article in news_items:

                    if not isinstance(
                        article,
                        dict
                    ):
                        continue

                    news_rows.append(
                        {
                            "Ticker": ticker,
                            "Title": article.get(
                                "Title",
                                ""
                            ),
                            "Description": article.get(
                                "Description",
                                ""
                            ),
                            "Publisher": article.get(
                                "Publisher",
                                ""
                            ),
                            "Published At": article.get(
                                "Published At",
                                ""
                            ),
                            "Article": article.get(
                                "Link",
                                ""
                            ),
                        }
                    )

            if news_rows:

                news_report = pd.DataFrame(
                    news_rows
                )

                # Leave two blank rows after the summary table
                news_heading_row = (
                    len(market_intelligence_report)
                    + 4
                )

                worksheet = writer.sheets[
                    market_intelligence_sheet_name
                ]

                worksheet.cell(
                    row=news_heading_row,
                    column=1,
                    value="MARKET & EVENT NEWS"
                )

                news_start_row = (
                    news_heading_row + 2
                )

                news_report.to_excel(
                    writer,
                    sheet_name=market_intelligence_sheet_name,
                    startrow=news_start_row - 1,
                    index=False
                )

                add_article_hyperlinks(

                    worksheet=worksheet,

                    news_report=news_report,

                    first_news_data_row=(
                        news_start_row + 1
                    )

                )

        # =====================================================
        # PORTFOLIO REALLOCATION
        # =====================================================

        print(

            "Creating Portfolio Reallocation"

        )

        # -----------------------------------------------------
        # Extract reallocation detail and summary safely.
        # -----------------------------------------------------

        if isinstance(

            portfolio_reallocation,

            dict

        ):

            reallocation_report = (

                portfolio_reallocation.get(

                    "reallocation",

                    pd.DataFrame()

                )

            )

            reallocation_summary = (

                portfolio_reallocation.get(

                    "summary",

                    {}

                )

            )

        elif isinstance(

            portfolio_reallocation,

            pd.DataFrame

        ):

            reallocation_report = (

                portfolio_reallocation.copy()

            )

            reallocation_summary = {}

        else:

            reallocation_report = pd.DataFrame()

            reallocation_summary = {}

        # -----------------------------------------------------
        # Ensure the detail is always a DataFrame.
        # -----------------------------------------------------

        if reallocation_report is None:

            reallocation_report = pd.DataFrame()

        elif not isinstance(

            reallocation_report,

            pd.DataFrame

        ):

            reallocation_report = pd.DataFrame(

                reallocation_report

            )

        portfolio_reallocation_sheet_name = (

            "Portfolio Reallocation"

        )

        # -----------------------------------------------------
        # Summary section.
        # -----------------------------------------------------

        if isinstance(

            reallocation_summary,

            dict

        ) and reallocation_summary:

            summary_report = pd.DataFrame(

                [

                    reallocation_summary

                ]

            )

        else:

            summary_report = pd.DataFrame(

                [

                    {

                        "Total Released": 0.0,

                        "Total Reallocated": 0.0,

                        "Funding Sources": 0,

                        "Destinations": 0

                    }

                ]

            )

        summary_report.to_excel(

            writer,

            sheet_name=portfolio_reallocation_sheet_name,

            index=False

        )

        # -----------------------------------------------------
        # Reallocation detail section.
        # -----------------------------------------------------

        worksheet = writer.sheets[

            portfolio_reallocation_sheet_name

        ]

        detail_heading_row = (

            len(summary_report)

            + 4

        )

        worksheet.cell(

            row=detail_heading_row,

            column=1,

            value="PORTFOLIO REALLOCATION DETAIL"

        )

        if reallocation_report.empty:

            no_reallocation_report = pd.DataFrame(

                {

                    "Status": [

                        "No portfolio reallocation transactions were generated"

                    ]

                }

            )

            no_reallocation_report.to_excel(

                writer,

                sheet_name=portfolio_reallocation_sheet_name,

                startrow=detail_heading_row,

                index=False

            )

        else:

            reallocation_report.to_excel(

                writer,

                sheet_name=portfolio_reallocation_sheet_name,

                startrow=detail_heading_row,

                index=False

            )

        # =====================================================
        # STOCK RANKINGS
        # =====================================================

        print(
            "Creating Stock Rankings"
        )

        pd.DataFrame(
            results
        ).to_excel(
            writer,
            sheet_name="Stock Rankings",
            index=False
        )

        # =====================================================
        # PORTFOLIO
        # =====================================================

        print(
            "Creating Portfolio"
        )

        portfolio_summary.to_excel(
            writer,
            sheet_name="Portfolio",
            index=False
        )

        # =====================================================
        # PORTFOLIO ACTIONS
        # =====================================================

        print(
            "Creating Portfolio Actions"
        )

        portfolio_actions.to_excel(
            writer,
            sheet_name="Portfolio Actions",
            index=False
        )

        # =====================================================
        # PORTFOLIO OPTIMISATION
        # =====================================================

        print(
            "Creating Portfolio Optimisation"
        )

        portfolio_optimisation.to_excel(
            writer,
            sheet_name="Portfolio Optimisation",
            index=False
        )

        # =====================================================
        # REBALANCE RECOMMENDATIONS
        # =====================================================

        print(
            "Creating Rebalance Recommendations"
        )

        rebalance_recommendations.to_excel(
            writer,
            sheet_name="Rebalance Recommendations",
            index=False
        )

        # =====================================================
        # SECTOR ANALYSIS
        # =====================================================

        print(
            "Creating Sector Analysis"
        )

        sector_summary.to_excel(
            writer,
            sheet_name="Sector Analysis",
            index=False
        )

        # =====================================================
        # PORTFOLIO HEALTH
        # =====================================================

        print(
            "Creating Portfolio Health"
        )

        if isinstance(
            portfolio_health,
            dict
        ):

            pd.DataFrame(
                [
                    portfolio_health
                ]
            ).to_excel(
                writer,
                sheet_name="Portfolio Health",
                index=False
            )

        elif isinstance(
            portfolio_health,
            pd.DataFrame
        ):

            portfolio_health.to_excel(
                writer,
                sheet_name="Portfolio Health",
                index=False
            )

        else:

            pd.DataFrame(
                {
                    "Status": [
                        "No portfolio health data available"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Portfolio Health",
                index=False
            )

        # =====================================================
        # FINAL PORTFOLIO DECISIONS
        # =====================================================

        print(
            "Creating Final Portfolio Decisions"
        )

        final_report = (
            prepare_final_portfolio_decisions_report(
                final_portfolio_decisions,
                results,
            )
        )

        final_report.to_excel(
            writer,
            sheet_name="Final Portfolio Decisions",
            index=False
        )

        # =====================================================
        # INVESTMENT DECISIONS
        # =====================================================

        print(
            "Creating Investment Decisions"
        )

        decisions.to_excel(
            writer,
            sheet_name="Investment Decisions",
            index=False
        )

        # =====================================================
        # TRADE PLAN
        # =====================================================

        print(
            "Creating Trade Plan"
        )

        trade_plan.to_excel(
            writer,
            sheet_name="Trade Plan",
            index=False
        )

        # =====================================================
        # PORTFOLIO GROWTH PLAN
        # =====================================================

        print(
            "Creating Portfolio Growth Plan"
        )

        try:

            growth_plan_df = pd.DataFrame(
                growth_plan
            )

        except Exception:

            growth_plan_df = pd.DataFrame()

        growth_plan_df.to_excel(
            writer,
            sheet_name="Portfolio Growth Plan",
            index=False
        )

        # =====================================================
        # AI PORTFOLIO REVIEW
        # =====================================================

        print(
            "Creating AI Portfolio Review"
        )

        print(
            "AI REVIEW TYPE:",
            type(portfolio_ai_review)
        )

        if not portfolio_ai_review.empty:

            portfolio_ai_review.to_excel(
                writer,
                sheet_name="AI Portfolio Review",
                index=False
            )

        else:

            pd.DataFrame(
                {
                    "Status": [
                        "No AI portfolio review available"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="AI Portfolio Review",
                index=False
            )

        # =====================================================
        # AI PORTFOLIO MANAGER
        # =====================================================

        print(
            "Creating AI Portfolio Manager"
        )

        if isinstance(
            portfolio_manager_review,
            dict
        ):

            pd.DataFrame(
                [
                    portfolio_manager_review
                ]
            ).to_excel(
                writer,
                sheet_name="AI Portfolio Manager",
                index=False
            )

        else:

            pd.DataFrame(
                {
                    "Status": [
                        "No portfolio manager review available"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="AI Portfolio Manager",
                index=False
            )

        # =====================================================
        # RECOMMENDATION LEARNING
        # =====================================================

        print(
            "Creating Recommendation Learning"
        )

        if isinstance(
            recommendation_learning,
            dict
        ):

            # -------------------------------------------------
            # OVERALL SUMMARY
            # -------------------------------------------------

            overall = recommendation_learning.get(
                "Overall",
                {}
            )

            if isinstance(
                overall,
                dict
            ) and overall:

                pd.DataFrame(
                    [
                        overall
                    ]
                ).to_excel(
                    writer,
                    sheet_name="Recommendation Learning Summary",
                    index=False
                )

            else:

                pd.DataFrame(
                    {
                        "Status": [
                            "No recommendation learning summary available"
                        ]
                    }
                ).to_excel(
                    writer,
                    sheet_name="Recommendation Learning Summary",
                    index=False
                )

            # -------------------------------------------------
            # HORIZON LEARNING
            #
            # IMPORTANT:
            # Horizon Learning is now a DataFrame.
            # It is NOT a dictionary keyed by horizon.
            # -------------------------------------------------

            horizons = recommendation_learning.get(
                "Horizon Learning",
                pd.DataFrame()
            )

            if isinstance(
                horizons,
                pd.DataFrame
            ) and not horizons.empty:

                print(
                    "Horizon Learning rows:",
                    len(horizons)
                )

                # One consolidated sheet
                horizons.to_excel(
                    writer,
                    sheet_name="Learning Horizons",
                    index=False
                )

            else:

                pd.DataFrame(
                    {
                        "Status": [
                            "No horizon learning data available"
                        ]
                    }
                ).to_excel(
                    writer,
                    sheet_name="Learning Horizons",
                    index=False
                )

            # -------------------------------------------------
            # SIGNAL PERFORMANCE
            # -------------------------------------------------

            learning_signal = recommendation_learning.get(
                "Signal Performance",
                pd.DataFrame()
            )

            if isinstance(
                learning_signal,
                pd.DataFrame
            ) and not learning_signal.empty:

                learning_signal.to_excel(
                    writer,
                    sheet_name="Learning Signals",
                    index=False
                )

            # -------------------------------------------------
            # SIGNAL RELIABILITY
            # -------------------------------------------------

            signal_reliability = recommendation_learning.get(
                "Signal Reliability",
                pd.DataFrame()
            )

            if isinstance(
                signal_reliability,
                pd.DataFrame
            ) and not signal_reliability.empty:

                signal_reliability.to_excel(
                    writer,
                    sheet_name="Signal Reliability",
                    index=False
                )

            # -------------------------------------------------
            # SCORE BUCKET PERFORMANCE
            # -------------------------------------------------

            learning_score_bucket = (
                recommendation_learning.get(
                    "Score Bucket Performance",
                    pd.DataFrame()
                )
            )

            if isinstance(
                learning_score_bucket,
                pd.DataFrame
            ) and not learning_score_bucket.empty:

                learning_score_bucket.to_excel(
                    writer,
                    sheet_name="Learning Score Buckets",
                    index=False
                )

            # -------------------------------------------------
            # SCORE HORIZON PERFORMANCE
            # -------------------------------------------------

            score_horizon = recommendation_learning.get(
                "Score Horizon Performance",
                pd.DataFrame()
            )

            if isinstance(
                score_horizon,
                pd.DataFrame
            ) and not score_horizon.empty:

                score_horizon.to_excel(
                    writer,
                    sheet_name="Learning Score Horizons",
                    index=False
                )

            # -------------------------------------------------
            # SIGNAL HORIZON PERFORMANCE
            # -------------------------------------------------

            signal_horizon = recommendation_learning.get(
                "Signal Horizon Performance",
                pd.DataFrame()
            )

            if isinstance(
                signal_horizon,
                pd.DataFrame
            ) and not signal_horizon.empty:

                signal_horizon.to_excel(
                    writer,
                    sheet_name="Learning Signal Horizons",
                    index=False
                )

            # -------------------------------------------------
            # COMPONENT SCORE PERFORMANCE
            # -------------------------------------------------

            component_learning = (
                recommendation_learning.get(
                    "Component Score Performance",
                    pd.DataFrame()
                )
            )

            if isinstance(
                component_learning,
                pd.DataFrame
            ) and not component_learning.empty:

                component_learning.to_excel(
                    writer,
                    sheet_name="Learning Components",
                    index=False
                )

            # -------------------------------------------------
            # CONFIDENCE PERFORMANCE
            # -------------------------------------------------

            confidence_learning = (
                recommendation_learning.get(
                    "Confidence Performance",
                    pd.DataFrame()
                )
            )

            if isinstance(
                confidence_learning,
                pd.DataFrame
            ) and not confidence_learning.empty:

                confidence_learning.to_excel(
                    writer,
                    sheet_name="Learning Confidence",
                    index=False
                )

        else:

            pd.DataFrame(
                {
                    "Status": [
                        "No recommendation learning available"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Recommendation Learning Summary",
                index=False
            )

        # =====================================================
        # RECOMMENDATION INTELLIGENCE
        # =====================================================

        # =====================================================
        # RECOMMENDATION INTELLIGENCE
        # =====================================================

        print(
            "Creating Recommendation Intelligence"
        )

        intelligence_sheet = (
            "Recommendation Intelligence"
        )

        # Always create the sheet with a simple report title.
        pd.DataFrame(
            {
                "Status": [
                    "Recommendation Intelligence Report"
                ]
            }
        ).to_excel(
            writer,
            sheet_name=intelligence_sheet,
            index=False
        )

        # -----------------------------------------------------
        # Write the main Recommendation Intelligence table
        # first. This is the primary output of the intelligence
        # engine and should be easy to inspect in Excel.
        # -----------------------------------------------------

        intelligence_row = 2

        if (
            isinstance(
                recommendation_intelligence,
                pd.DataFrame
            )
            and not recommendation_intelligence.empty
        ):
            pd.DataFrame(
                [
                    [
                        "Recommendation Intelligence"
                    ]
                ]
            ).to_excel(
                writer,
                sheet_name=intelligence_sheet,
                startrow=intelligence_row,
                index=False,
                header=False
            )

            intelligence_row += 1

            recommendation_intelligence.to_excel(
                writer,
                sheet_name=intelligence_sheet,
                startrow=intelligence_row,
                index=False
            )

            intelligence_row += (
                len(
                    recommendation_intelligence
                )
                + 3
            )

        # -----------------------------------------------------
        # Additional learning diagnostics
        # -----------------------------------------------------

        intelligence_sections = [
            (
                "Signal Performance",
                signal_performance
            ),
            (
                "Horizon Performance",
                horizon_performance
            ),
            (
                "Score Performance",
                score_performance
            ),
            (
                "Score Bucket Performance",
                score_bucket_performance
            ),
            (
                "Component Score Performance",
                component_score_performance
            ),
            (
                "Signal Horizon Performance",
                signal_horizon_performance
            )
        ]

        for title, dataframe in intelligence_sections:

            if dataframe is None:
                continue

            if not isinstance(
                dataframe,
                pd.DataFrame
            ):
                continue

            if dataframe.empty:
                continue

            pd.DataFrame(
                [
                    [
                        title
                    ]
                ]
            ).to_excel(
                writer,
                sheet_name=intelligence_sheet,
                startrow=intelligence_row,
                index=False,
                header=False
            )

            intelligence_row += 1

            dataframe.to_excel(
                writer,
                sheet_name=intelligence_sheet,
                startrow=intelligence_row,
                index=False
            )

            intelligence_row += (
                len(dataframe) + 4
            )

        # =====================================================
        # DECISION PERFORMANCE
        # =====================================================

        print(
            "DECISION PERFORMANCE SHAPE:",
            decision_performance["summary"].shape
        )

        decision_performance_sheet = (
            "Decision Performance"
        )

        decision_performance_sections = [
            (
                "DECISION PERFORMANCE SUMMARY",
                decision_performance.get(
                    "summary",
                    pd.DataFrame()
                )
            ),
             (
                "RECOMMENDATION PERFORMANCE BY HORIZON",
                decision_performance.get(
                    "recommendation_performance",
                    pd.DataFrame()
                )
            ),
            (
                "ACTION PERFORMANCE",
                decision_performance.get(
                    "action_performance",
                    pd.DataFrame()
                )
            ),
            (
                "MODEL VS MARKET INTELLIGENCE",
                decision_performance.get(
                    "model_vs_market_intelligence",
                    pd.DataFrame()
                )
            ),
            (
                "RECOMMENDATION QUALITY & IMPROVEMENT ASSESSMENT",
                decision_performance.get(
                    "recommendation_quality_assessment",
                    pd.DataFrame()
                )
            ),
            (
                "CALIBRATION RECOMMENDATIONS",
                decision_performance.get(
                    "calibration_recommendations",
                    pd.DataFrame()
                )
            ),
            (
                "BUY NEW PERFORMANCE DECOMPOSITION",
                decision_performance.get(
                    "buy_new_decomposition",
                    pd.DataFrame()
                )
            ),
            (
                "DECISION AUDIT",
                decision_performance.get(
                    "decision_audit",
                    pd.DataFrame()
                )
            ),
        ]

        decision_performance_row = 0

        for title, dataframe in decision_performance_sections:

            if dataframe is None:
                continue

            if not isinstance(
                dataframe,
                pd.DataFrame
            ):
                continue

            if dataframe.empty:
                continue

            pd.DataFrame(
                [
                    [
                        title
                    ]
                ]
            ).to_excel(
                writer,
                sheet_name=decision_performance_sheet,
                startrow=decision_performance_row,
                index=False,
                header=False
            )

            decision_performance_row += 1

            dataframe.to_excel(
                writer,
                sheet_name=decision_performance_sheet,
                startrow=decision_performance_row,
                index=False
            )

            decision_performance_row += (
                len(dataframe) + 4
            )


        # =====================================================
        # ALERTS
        # =====================================================

        print(
            "ALERTS SHAPE:",
            alerts.shape
        )

        print(
            "ALERTS EMPTY:",
            alerts.empty
        )

        print(
            "Creating Alerts"
        )

        alerts.to_excel(
            writer,
            sheet_name="Alerts",
            index=False
        )

    # =========================================================
    # WORKBOOK VERIFICATION
    # =========================================================

    print(
        "Report created:",
        filename
    )

    try:

        from openpyxl import load_workbook

        workbook = load_workbook(
            filename,
            read_only=True
        )

        print(
            "FINAL WORKBOOK SHEETS:",
            workbook.sheetnames
        )

        workbook.close()

    except Exception as e:

        print(
            "Workbook verification failed:",
            e
        )

    return filename

def _load_persisted_audit_reasons_by_ticker():
    """
    Load persisted audit reconciliation reasons for the latest
    completed audit run.

    The audit database is the authoritative source for audit
    reasons. This reporting helper deliberately does not rely on
    in-memory audit state or require audit_run_id to be carried
    inside the final portfolio decision dataframe.

    Returns
    -------
    dict
        Mapping of ticker -> combined persisted audit reason text.
    """

    database_path = (
        "/Users/jameshulin/Documents/"
        "stock-momentum-agent/data/portfolio_manager.db"
    )

    reasons_by_ticker = {}

    try:

        conn = sqlite3.connect(
            database_path
        )

        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                ad.ticker,
                ar.reason_code,
                ar.reason_category,
                ar.reason_description,
                ar.severity,
                ar.source_layer
            FROM audit_runs AS run
            INNER JOIN audit_decisions AS ad
                ON ad.audit_run_id = run.id
            INNER JOIN audit_reasons AS ar
                ON ar.audit_decision_id = ad.id
            WHERE run.id = (
                SELECT id
                FROM audit_runs
                WHERE status = 'COMPLETED'
                ORDER BY id DESC
                LIMIT 1
            )
            ORDER BY
                ad.ticker,
                ar.id
            """
        ).fetchall()

        conn.close()

        grouped_reasons = {}

        for row in rows:

            ticker = str(
                row["ticker"] or ""
            ).strip().upper()

            description = str(
                row["reason_description"] or ""
            ).strip()

            if not ticker or not description:
                continue

            grouped_reasons.setdefault(
                ticker,
                []
            )

            if description not in grouped_reasons[ticker]:

                grouped_reasons[ticker].append(
                    description
                )

        for ticker, reasons in grouped_reasons.items():

            reasons_by_ticker[ticker] = (
                " | ".join(reasons)
            )

    except Exception as exc:

        print(
            "WARNING: Failed to load persisted "
            f"audit reasons: {exc}"
        )

    return reasons_by_ticker

# ============================================================
# Final Portfolio Decisions - Executive Report Preparation
# ============================================================


def prepare_final_portfolio_decisions_report(
    final_portfolio_decisions,
    results,
):
    """
    Prepare the Final Portfolio Decisions dataframe for the
    executive-facing Excel worksheet.

    Responsibilities
    ----------------
    - Preserve the underlying decision output unchanged.
    - Enrich non-owned BUY NEW candidates with Name / Sector.
    - Normalise Existing Holding to True / False.
    - Force non-owned allocation to 0%.
    - Prefer persisted audit reasons when available.
    - Populate missing reconciliation reasons only when no
      persisted audit reason exists.
    - Remove upstream / duplicate columns.
    - Return the final executive-report dataframe.

    This function changes reporting presentation only.
    It does not alter portfolio decision logic.
    """

    if final_portfolio_decisions is None:

        final_report = pd.DataFrame()

    elif isinstance(
        final_portfolio_decisions,
        pd.DataFrame,
    ):

        final_report = (
            final_portfolio_decisions
            .copy()
        )

    else:

        try:

            final_report = pd.DataFrame(
                final_portfolio_decisions
            )

        except Exception:

            final_report = pd.DataFrame()

    # --------------------------------------------------------
    # Ensure required fields exist.
    # --------------------------------------------------------

    required_defaults = {

        "Ticker": "",
        "Name": "",
        "Asset Type": "STOCK",
        "Existing Holding": False,
        "Sector": "",
        "Allocation %": 0.0,
        "Investment Score": 0.0,
        "Signal": "",
        "Proposed Action": "HOLD",
        "Final Decision": "HOLD",
        "Decision Status": "",
        "Evidence Score": 0.0,
        "Evidence Strength": "UNKNOWN",
        "Decision Support": "UNKNOWN",
        "Deterministic Confidence": 0.0,
        "LLM Assessment": "CHALLENGE",
        "LLM Confidence": 0.0,
        "LLM Reason": "",
        "Reconciliation Status": "",
        "Reconciliation Reason": "",
        "Reduction %": 0.0,
        "Released Capital": 0.0,
        "Buy Value": 0.0,
        "Ticker Horizon Learning Commentary": "",
    }

    for column, default_value in required_defaults.items():

        if column not in final_report.columns:

            final_report[
                column
            ] = default_value

    # --------------------------------------------------------
    # Build lookup from stock scan results.
    #
    # BUY NEW candidates will not exist in portfolio_summary,
    # so Name and Sector may need to come from results.
    # --------------------------------------------------------

    try:

        results_df = pd.DataFrame(
            results
        )

    except Exception:

        results_df = pd.DataFrame()

    results_lookup = {}

    if (
        not results_df.empty
        and
        "Ticker" in results_df.columns
    ):

        for _, row in results_df.iterrows():

            ticker = str(
                row.get(
                    "Ticker",
                    ""
                )
            ).strip().upper()

            if not ticker:
                continue

            if ticker not in results_lookup:

                results_lookup[
                    ticker
                ] = row.to_dict()

    # --------------------------------------------------------
    # Load persisted audit reasons.
    #
    # The audit run is created once for the complete daily
    # final-decision population, so the latest completed run
    # represents the same production decision cycle.
    #
    # final_portfolio_decisions does not need to carry the
    # audit_run_id.
    # --------------------------------------------------------

    persisted_audit_reasons = (
        _load_persisted_audit_reasons_by_ticker()
    )

    # --------------------------------------------------------
    # Process each final decision row.
    # --------------------------------------------------------

    for index in final_report.index:

        ticker = str(
            final_report.at[
                index,
                "Ticker"
            ]
        ).strip().upper()

        result_record = results_lookup.get(
            ticker,
            {}
        )

        # ----------------------------------------------------
        # Enrich Name.
        # ----------------------------------------------------

        current_name = final_report.at[
            index,
            "Name"
        ]

        if (
            pd.isna(current_name)
            or
            str(current_name).strip() == ""
        ):

            final_report.at[
                index,
                "Name"
            ] = (
                result_record.get(
                    "Name"
                )
                or
                result_record.get(
                    "Company"
                )
                or
                ""
            )

        # ----------------------------------------------------
        # Enrich Sector.
        # ----------------------------------------------------

        current_sector = final_report.at[
            index,
            "Sector"
        ]

        if (
            pd.isna(current_sector)
            or
            str(current_sector).strip() == ""
        ):

            final_report.at[
                index,
                "Sector"
            ] = (
                result_record.get(
                    "Sector"
                )
                or
                result_record.get(
                    "Sector_Scanner"
                )
                or
                ""
            )

        # ----------------------------------------------------
        # Populate missing reconciliation reason.
        #
        # Priority:
        #
        # 1. Persisted audit reason
        # 2. Existing reconciliation reason
        # 3. Existing deterministic fallback text
        #
        # A persisted audit reason therefore takes precedence
        # over the generic reporting fallback.
        # ----------------------------------------------------

        reconciliation_reason = (
            final_report.at[
                index,
                "Reconciliation Reason"
            ]
        )

        persisted_reason = (
            persisted_audit_reasons.get(
                ticker,
                ""
            )
        )

        if persisted_reason:

            reconciliation_reason = (
                persisted_reason
            )

        else:

            if (
                pd.isna(
                    reconciliation_reason
                )
                or
                str(
                    reconciliation_reason
                ).strip()
                == ""
            ):

                final_decision = str(
                    final_report.at[
                        index,
                        "Final Decision"
                    ]
                ).strip().upper()

                if final_decision == "NO ACTION":

                    reconciliation_reason = (
                        "BUY NEW proposal did not pass the "
                        "governed decision process; no position "
                        "should be established."
                    )

                elif final_decision == "HOLD":

                    reconciliation_reason = (
                        "No sufficiently strong evidence justified "
                        "a change to the existing position."
                    )

                elif final_decision == "REDUCE":

                    reconciliation_reason = (
                        "REDUCE proposal passed the governed "
                        "decision and reconciliation checks."
                    )

                elif final_decision == "SELL":

                    reconciliation_reason = (
                        "SELL proposal passed the governed "
                        "decision and reconciliation checks."
                    )

                elif final_decision == "BUY NEW":

                    reconciliation_reason = (
                        "BUY NEW proposal passed the governed "
                        "decision and reconciliation checks."
                    )

                elif final_decision == "BUY MORE":

                    reconciliation_reason = (
                        "BUY MORE proposal passed the governed "
                        "decision and reconciliation checks."
                    )

                else:

                    reconciliation_reason = ""

        final_report.at[
            index,
            "Reconciliation Reason"
        ] = reconciliation_reason

    # --------------------------------------------------------
    # Numeric normalisation.
    # --------------------------------------------------------

    numeric_columns = [

        "Allocation %",
        "Investment Score",
        "Evidence Score",
        "Deterministic Confidence",
        "LLM Confidence",
        "Reduction %",
        "Released Capital",
        "Buy Value",

    ]

    for column in numeric_columns:

        final_report[
            column
        ] = pd.to_numeric(
            final_report[
                column
            ],
            errors="coerce",
        ).fillna(
            0.0
        )

    # --------------------------------------------------------
    # Select executive columns only.
    # --------------------------------------------------------

    available_columns = [

        column
        for column in FINAL_DECISION_COLUMNS
        if column in final_report.columns

    ]

    final_report = final_report[
        available_columns
    ].copy()

    # --------------------------------------------------------
    # Rename for executive presentation.
    # --------------------------------------------------------

    final_report.rename(
        columns=FINAL_DECISION_HEADERS,
        inplace=True,
    )

    # --------------------------------------------------------
    # Executive presentation values.
    # --------------------------------------------------------

    if "Held?" in final_report.columns:

        final_report[
            "Held?"
        ] = final_report[
            "Held?"
        ].map(
            {
                True: "Yes",
                False: "No",
            }
        ).fillna(
            "No"
        )

    if "Current Allocation %" in final_report.columns:

        final_report[
            "Current Allocation %"
        ] = pd.to_numeric(
            final_report[
                "Current Allocation %"
            ],
            errors="coerce",
        ).fillna(
            0.0
        )

    return final_report

