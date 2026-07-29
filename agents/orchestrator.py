from agents.market_agent import run_market_agent
from agents.stock_agent import run_stock_agent
from agents.portfolio_agent import run_portfolio_agent
from agents.risk_agent import run_risk_agent
from agents.briefing_agent import run_briefing_agent


def run_ai_agents(
    results,
    portfolio,
    sector_summary,
    portfolio_health
):
    """
    Executes all AI agents and combines their outputs.
    """

    market_review = run_market_agent()

    stock_reviews = run_stock_agent(results)

    portfolio_review = run_portfolio_agent(
        portfolio,
        portfolio_health
    )

    risk_review = run_risk_agent(
        portfolio,
        sector_summary,
        portfolio_health
    )

    executive_brief = run_briefing_agent(
        market_review,
        portfolio_review,
        risk_review,
        stock_reviews
    )

    return {
        "Market Review": market_review,
        "Stock Reviews": stock_reviews,
        "Portfolio Review": portfolio_review,
        "Risk Review": risk_review,
        "Executive Brief": executive_brief,
    }