import pandas as pd


def enrich_portfolio_holdings(
    portfolio_summary,
    stock_results
):
    """
    Enrich existing portfolio holdings with
    latest recommendation intelligence.
    """

    if portfolio_summary is None:
        return pd.DataFrame()

    if stock_results is None:
        stock_results = []


    results_df = pd.DataFrame(
        stock_results
    )


    if results_df.empty:
        return portfolio_summary


    enriched = portfolio_summary.copy()


    lookup_columns = [
        "Ticker",
        "Signal",
        "Investment Score",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Confidence",
        "Sector",
        "Industry"
    ]


    available_columns = [
        c for c in lookup_columns
        if c in results_df.columns
    ]


    intelligence = (
        results_df[
            available_columns
        ]
        .drop_duplicates(
            subset=["Ticker"]
        )
    )


    enriched = enriched.merge(
        intelligence,
        on="Ticker",
        how="left",
        suffixes=(
            "",
            "_Latest"
        )
    )


    # Missing scores mean not found in scanner

    score_columns = [
        "Investment Score",
        "Technical Score",
        "Quality Score",
        "Growth Score"
    ]


    for col in score_columns:

        if col in enriched.columns:

            enriched[col] = (
                enriched[col]
                .fillna(0)
            )


    if "Signal" in enriched.columns:

        enriched["Signal"] = (
            enriched["Signal"]
            .fillna("NOT IN UNIVERSE")
        )


    return enriched