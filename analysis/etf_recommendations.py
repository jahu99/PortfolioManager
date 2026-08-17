
"""
etf_recommendations.py

Purpose
-------
Provides human-readable recommendations for ETFs based on the
authoritative ETF decision produced by etf_decisions.py.

Responsibilities
----------------
1. Convert the ETF decision into a clear recommendation.
2. Provide confidence and supporting reasons.
3. Explain why the decision was made.
4. Provide ETF-specific risks.
5. Keep ETF recommendation presentation separate from the
   existing stock recommendation logic.

Important design principle
--------------------------
This module does NOT decide whether an ETF should be bought,
held, reduced or sold.

That decision belongs to etf_decisions.py.

This module explains the decision produced by the ETF decision
engine.

Supported decisions
-------------------
    BUY
    BUY MORE
    HOLD
    REDUCE
    SELL
"""


# ============================================================
# RECOMMENDATION BUILDER
# ============================================================

def build_etf_recommendation(decision_data):
    """
    Build a human-readable ETF recommendation from the
    authoritative ETF decision.

    The ETF decision engine is the single source of truth for:

        - Decision
        - Confidence
        - Decision reason
        - ETF analysis reasons
        - ETF analysis risks

    This module translates that decision into reporting-friendly
    recommendation fields.

    It does NOT independently decide whether the ETF should be
    bought, held, reduced or sold.
    """

    if decision_data is None:
        decision_data = {}

    # ========================================================
    # AUTHORITATIVE ETF DECISION
    # ========================================================

    decision = str(
        decision_data.get(
            "ETF Decision",
            "HOLD"
        )
    ).upper().strip()

    # --------------------------------------------------------
    # The decision engine calls this:
    #
    #     ETF Decision Confidence
    #
    # Do not independently recalculate confidence here.
    # --------------------------------------------------------

    confidence = decision_data.get(
        "ETF Decision Confidence",
        "LOW"
    )

    # --------------------------------------------------------
    # The decision engine provides one authoritative decision
    # reason.
    # --------------------------------------------------------

    decision_reason = decision_data.get(
        "ETF Decision Reason",
        ""
    )

    if decision_reason is None:
        decision_reason = ""

    decision_reason = str(
        decision_reason
    ).strip()

    # ========================================================
    # ETF ANALYSIS REASONS AND RISKS
    # ========================================================

    reasons = decision_data.get(
        "ETF Reasons",
        []
    )

    risks = decision_data.get(
        "ETF Risks",
        []
    )

    # --------------------------------------------------------
    # Normalise reasons and risks.
    # --------------------------------------------------------

    if reasons is None:
        reasons = []

    if risks is None:
        risks = []

    if isinstance(reasons, str):
        reasons = [reasons]

    if isinstance(risks, str):
        risks = [risks]

    # ========================================================
    # RECOMMENDATION TEXT
    # ========================================================

    recommendation_text = (
        "Maintain the current ETF position unless the "
        "portfolio-level decision engine identifies a strong "
        "reason to change it."
    )

    if decision == "BUY":

        recommendation_text = (
            "Initiate a new ETF position because the ETF "
            "analysis and portfolio context support an "
            "attractive opportunity."
        )

    elif decision == "BUY MORE":

        recommendation_text = (
            "Increase the existing ETF position because the "
            "ETF remains attractive and the portfolio context "
            "supports additional allocation."
        )

    elif decision == "REDUCE":

        recommendation_text = (
            "Reduce the existing ETF position because the "
            "portfolio context or ETF evidence provides a "
            "sufficient reason to lower exposure."
        )

    elif decision == "SELL":

        recommendation_text = (
            "Exit the ETF position because the combined ETF "
            "evidence and portfolio context provide a strong "
            "reason to remove the holding."
        )

    elif decision == "HOLD":

        recommendation_text = (
            "Maintain the existing position. There is not "
            "currently a sufficiently strong reason to change "
            "the allocation."
        )

    # ========================================================
    # PRIMARY REASON
    # ========================================================
    #
    # The decision reason takes precedence because it explains
    # WHY the portfolio decision was made.
    #
    # ETF analysis reasons remain available separately.
    # ========================================================

    if decision_reason:

        primary_reason = decision_reason

    elif reasons:

        primary_reason = reasons[0]

    else:

        primary_reason = (
            "No specific ETF decision reason was provided."
        )

    # ========================================================
    # RETURN STRUCTURE
    # ========================================================

    return {

        "ETF Recommendation":
            decision,

        "ETF Recommendation Text":
            recommendation_text,

        "ETF Confidence":
            confidence,

        "ETF Primary Reason":
            primary_reason,

        "ETF Reasons":
            reasons,

        "ETF Risks":
            risks

    }
# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def generate_etf_recommendation(decision_data):
    """
    Convenience wrapper around build_etf_recommendation().
    """

    return build_etf_recommendation(
        decision_data
    )

