import pandas as pd


def _safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


def _normalise_action(value):

    if value is None:
        return ""

    return str(value).strip().upper()


def _normalise_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):

        if value.strip() == "":
            return []

        return [value]

    return [str(value)]


def _get_value(source, *keys, default=None):

    """
    Safely retrieve the first available value from a dict
    or pandas Series.
    """

    if source is None:
        return default

    for key in keys:

        try:

            if isinstance(source, dict):

                value = source.get(
                    key,
                    None
                )

            elif isinstance(source, pd.Series):

                value = source.get(
                    key,
                    None
                )

            else:

                value = getattr(
                    source,
                    key,
                    None
                )

            if value is not None:

                try:

                    if pd.isna(value):
                        continue

                except Exception:
                    pass

                return value

        except Exception:
            continue

    return default


def generate_final_portfolio_decision(
    ticker,
    investment_decision,
    ai_review,
    portfolio_manager_review,
    portfolio_health=None
):
    """
    Portfolio Decision Consolidator

    Purpose
    -------
    Combines:

        - Investment decision engine
        - AI portfolio review
        - Portfolio manager review
        - Portfolio health

    Produces one final portfolio action.

    IMPORTANT
    ---------
    This function decides WHETHER capital should be deployed.

    It does NOT decide the final monetary allocation.

    Actual capital allocation is handled by:

        capital_allocator.py

    That module determines:

        BUY NEW
        BUY MORE
        REDUCE
        SELL
        HOLD

    using actual ownership from holdings_raw.csv and
    Investment Score ranking.
    """

    # =====================================================
    # DEFAULT DECISION
    # =====================================================

    final_action = "HOLD"

    confidence = "Medium"

    reasons = []
    risks = []
    actions = []

    capital_action = (
        "Maintain existing allocation"
    )

    review_trigger = [
        "Investment score falls below 60",
        "Trend breaks below 200 DMA"
    ]

    # =====================================================
    # INVESTMENT INTELLIGENCE
    # =====================================================

    investment_action = _normalise_action(
        _get_value(
            investment_decision,
            "Action",
            "Final Action",
            default=""
        )
    )

    investment_reason = _get_value(
        investment_decision,
        "Reason",
        "Reasons",
        default=""
    )

    if investment_reason:

        reasons.extend(
            _normalise_list(
                investment_reason
            )
        )

    investment_score = _safe_float(
        _get_value(
            investment_decision,
            "Investment Score",
            "investment_score",
            "Score",
            default=0
        )
    )

    quality_score = _safe_float(
        _get_value(
            investment_decision,
            "Quality Score",
            "quality_score",
            default=0
        )
    )

    growth_score = _safe_float(
        _get_value(
            investment_decision,
            "Growth Score",
            "growth_score",
            default=0
        )
    )

    signal = _normalise_action(
        _get_value(
            investment_decision,
            "Signal",
            "Momentum Signal",
            default=""
        )
    )

    conviction = _normalise_action(
        _get_value(
            investment_decision,
            "AI Conviction",
            "Conviction",
            "Confidence",
            default="MEDIUM"
        )
    )

    allocation = _safe_float(
        _get_value(
            investment_decision,
            "Allocation %",
            default=0
        )
    )

    sector = _get_value(
        investment_decision,
        "Sector",
        default="Unknown"
    )

    sector_allocation = _safe_float(
        _get_value(
            investment_decision,
            "Sector Allocation %",
            default=0
        )
    )

    portfolio_risk = _normalise_action(
        _get_value(
            investment_decision,
            "Portfolio Risk",
            default="NORMAL"
        )
    )

    # =====================================================
    # AI RECOMMENDATION
    # =====================================================

    ai_action = _normalise_action(
        _get_value(
            ai_review,
            "AI Holding Decision",
            "Final Action",
            "Action",
            default=""
        )
    )

    ai_risks = _get_value(
        ai_review,
        "AI Holding Risks",
        "Risks",
        default=[]
    )

    risks.extend(
        _normalise_list(
            ai_risks
        )
    )

    ai_actions = _get_value(
        ai_review,
        "AI Holding Actions",
        "Actions",
        default=[]
    )

    actions.extend(
        _normalise_list(
            ai_actions
        )
    )

    ai_reasons = _get_value(
        ai_review,
        "AI Holding Reasons",
        "Reasons",
        default=[]
    )

    reasons.extend(
        _normalise_list(
            ai_reasons
        )
    )

    # =====================================================
    # PORTFOLIO MANAGER VIEW
    # =====================================================

    manager_risks = _get_value(
        portfolio_manager_review,
        "Key Risks",
        default=[]
    )

    manager_risks = _normalise_list(
        manager_risks
    )

    risks.extend(
        manager_risks
    )

    # =====================================================
    # PORTFOLIO HEALTH
    # =====================================================

    health_score = _safe_float(
        _get_value(
            portfolio_health,
            "Health Score",
            default=100
        ),
        100
    )

    # =====================================================
    # DECISION HIERARCHY
    #
    # HOLD is deliberately the default.
    #
    # This is important for a long-term portfolio:
    #
    # Lack of a strong BUY case does NOT automatically
    # justify selling an existing holding.
    # =====================================================

    # -----------------------------------------------------
    # 1. REDUCE / EXIT
    #
    # Strong negative evidence takes precedence.
    # -----------------------------------------------------

    if (
        investment_action in {
            "REDUCE",
            "SELL",
            "EXIT"
        }
        or
        ai_action in {
            "REDUCE",
            "SELL",
            "EXIT"
        }
    ):

        final_action = "REDUCE"

        confidence = "High"

        capital_action = (
            "Release capital for stronger opportunities"
        )

    # -----------------------------------------------------
    # 2. PORTFOLIO RISK BLOCK
    #
    # Even a good opportunity should not automatically
    # receive additional capital when portfolio-level
    # risks are elevated.
    # -----------------------------------------------------

    elif (
        ai_action == "HOLD"
        and
        len(manager_risks) > 0
    ):

        final_action = "HOLD"

        confidence = "High"

        capital_action = (
            "Do not increase allocation until "
            "portfolio risks improve"
        )

    # -----------------------------------------------------
    # 3. STRONG ADD OPPORTUNITY
    #
    # This authorises the allocator to consider the stock.
    #
    # capital_allocator.py determines whether it becomes
    # BUY NEW or BUY MORE based on actual ownership.
    # -----------------------------------------------------

    elif (
        investment_action in {
            "ADD",
            "BUY",
            "BUY NEW",
            "BUY MORE"
        }
        and
        investment_score >= 75
        and
        health_score >= 70
    ):

        final_action = "ADD"

        confidence = (
            "Very High"
            if investment_score >= 85
            else "High"
        )

        capital_action = (
            "Eligible for additional capital allocation"
        )

    # -----------------------------------------------------
    # 4. MODERATE OPPORTUNITY
    #
    # Do not force capital deployment.
    # -----------------------------------------------------

    elif (
        investment_score >= 65
        and
        health_score >= 70
    ):

        final_action = "HOLD"

        confidence = "Medium"

        capital_action = (
            "Monitor opportunity; deploy capital only "
            "if conviction strengthens"
        )

    # -----------------------------------------------------
    # 5. DEFAULT
    # -----------------------------------------------------

    else:

        final_action = "HOLD"

        confidence = "Medium"

        capital_action = (
            "Maintain existing allocation"
        )

    # =====================================================
    # ADDITIONAL REVIEW TRIGGERS
    # =====================================================

    if investment_score > 0:

        if investment_score < 60:

            review_trigger.append(
                "Investment score below 60"
            )

    if quality_score > 0:

        if quality_score < 50:

            review_trigger.append(
                "Quality score below 50"
            )

    if growth_score > 0:

        if growth_score < 40:

            review_trigger.append(
                "Growth score below 40"
            )

    if signal in {
        "SELL",
        "STRONG SELL"
    }:

        review_trigger.append(
            "Bearish technical signal"
        )

    if allocation >= 40:

        review_trigger.append(
            "Portfolio concentration above 40%"
        )

    if sector_allocation >= 30:

        review_trigger.append(
            "Sector allocation above 30%"
        )

    # =====================================================
    # REMOVE DUPLICATES
    # =====================================================

    reasons = list(
        dict.fromkeys(
            str(x)
            for x in reasons
            if x
        )
    )

    risks = list(
        dict.fromkeys(
            str(x)
            for x in risks
            if x
        )
    )

    actions = list(
        dict.fromkeys(
            str(x)
            for x in actions
            if x
        )
    )

    review_trigger = list(
        dict.fromkeys(
            review_trigger
        )
    )

    # =====================================================
    # RETURN
    #
    # Existing keys are preserved.
    # Additional intelligence fields are included so the
    # capital allocator and reporting layers can use them.
    # =====================================================

    return {

        "Ticker":
            ticker,

        "Final Action":
            final_action,

        "Confidence":
            confidence,

        "Reasons":
            reasons,

        "Risks":
            risks,

        "Actions":
            actions,

        "Capital Allocation Action":
            capital_action,

        "Review Triggers":
            review_trigger,

        "Investment Score":
            investment_score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Signal":
            signal,

        "AI Conviction":
            conviction,

        "Allocation %":
            allocation,

        "Sector":
            sector,

        "Sector Allocation %":
            sector_allocation,

        "Portfolio Risk":
            portfolio_risk,

        "Existing Holding":
            "Yes"
    }