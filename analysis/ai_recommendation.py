from typing import Dict, List


def generate_ai_recommendation(stock: Dict) -> Dict:

    investment_score = stock.get("Investment Score", 0)
    technical_score = stock.get("Technical Score", 0)
    quality_score = stock.get("Quality Score", 0)
    growth_score = stock.get("Growth Score", 0)
    confidence_score = stock.get("Confidence Score", 50)

    rsi = stock.get("RSI", 50)
    revenue_growth = stock.get("Revenue Growth", 0)
    roe = stock.get("Return on Equity", 0)
    debt = stock.get("Debt to Equity", 0)

    sector = stock.get("Sector", "Unknown")

    thesis = []
    strengths = []
    risks = []
    catalysts = []

    # -------------------------
    # Investment Thesis
    # -------------------------

    if technical_score >= 75:
        thesis.append(
            "Strong long-term technical momentum."
        )

    if quality_score >= 70:
        thesis.append(
            "Business quality is above market average."
        )

    if growth_score >= 70:
        thesis.append(
            "Growth profile supports future earnings expansion."
        )

    if revenue_growth > 0.15:
        thesis.append(
            "Revenue growth remains strong."
        )

    if roe > 0.20:
        thesis.append(
            "High return on equity demonstrates efficient capital allocation."
        )

    # -------------------------
    # Strengths
    # -------------------------

    if technical_score >= 80:
        strengths.append("Strong price trend")

    if quality_score >= 75:
        strengths.append("High-quality business")

    if growth_score >= 75:
        strengths.append("Excellent growth")

    if debt < 0.50:
        strengths.append("Low financial leverage")

    if confidence_score >= 70:
        strengths.append("Historically reliable score")

    # -------------------------
    # Risks
    # -------------------------

    if rsi > 70:
        risks.append("Momentum becoming overbought")

    if technical_score < 50:
        risks.append("Weak technical trend")

    if quality_score < 40:
        risks.append("Business quality below average")

    if debt > 1.5:
        risks.append("High leverage")

    if revenue_growth < 0:
        risks.append("Declining revenue")

    if confidence_score < 55:
        risks.append("Limited historical confidence")

    # -------------------------
    # Catalysts
    # -------------------------

    sector_catalysts = {

        "Technology": [
            "AI demand",
            "Cloud adoption",
            "Next earnings"
        ],

        "Financial Services": [
            "Interest rate changes",
            "Loan growth",
            "Quarterly earnings"
        ],

        "Healthcare": [
            "Drug approvals",
            "Clinical trials",
            "Quarterly earnings"
        ],

        "Industrials": [
            "Infrastructure spending",
            "Economic recovery"
        ],

        "Energy": [
            "Oil prices",
            "Commodity demand"
        ]
    }

    catalysts = sector_catalysts.get(
        sector,
        ["Quarterly earnings"]
    )

    # -------------------------
    # Holding Period
    # -------------------------

    if investment_score >= 85:
        holding = "12–24 months"

    elif investment_score >= 75:
        holding = "6–12 months"

    elif investment_score >= 65:
        holding = "3–6 months"

    else:
        holding = "Watchlist"

    # -------------------------
    # Investor Type
    # -------------------------

    if growth_score >= 75:
        investor = "Growth Investor"

    elif technical_score >= 75:
        investor = "Momentum Investor"

    elif quality_score >= 75:
        investor = "Quality Investor"

    else:
        investor = "Balanced Investor"

    # -------------------------
    # Probability
    # -------------------------

    probability = round(

        investment_score * 0.35 +

        confidence_score * 0.35 +

        quality_score * 0.15 +

        growth_score * 0.15

    )

    probability = max(
        0,
        min(
            100,
            probability
        )
    )

    # -------------------------
    # Summary
    # -------------------------

    if investment_score >= 80:

        summary = (
            "High-conviction opportunity with strong fundamentals and momentum."
        )

    elif investment_score >= 70:

        summary = (
            "Good quality investment with attractive long-term characteristics."
        )

    elif investment_score >= 60:

        summary = (
            "Worth monitoring as fundamentals continue to develop."
        )

    else:

        summary = (
            "Current risk outweighs expected return."
        )

    return {

        "Summary": summary,

        "Investment Thesis": thesis,

        "Strengths": strengths,

        "Risks": risks,

        "Catalysts": catalysts,

        "Holding Period": holding,

        "Investor Type": investor,

        "Probability": probability

    }