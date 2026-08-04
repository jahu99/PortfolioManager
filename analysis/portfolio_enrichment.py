import pandas as pd


def enrich_portfolio_holdings(
    portfolio_summary,
    results
):
    """
    Enrich portfolio holdings with stock intelligence
    from the market scanner results.

    Inputs:
        portfolio_summary:
            DataFrame created by analyse_portfolio()

        results:
            List of analysed stocks

    Returns:
        enriched portfolio_summary DataFrame
    """

    try:

        if portfolio_summary is None:
            return pd.DataFrame()


        if not isinstance(
            portfolio_summary,
            pd.DataFrame
        ):
            portfolio_summary = pd.DataFrame(
                portfolio_summary
            )


        if not results:
            return portfolio_summary


        results_df = pd.DataFrame(results)


        if results_df.empty:
            return portfolio_summary


        # Ensure ticker matching works
        portfolio_summary["Ticker"] = (
            portfolio_summary["Ticker"]
            .astype(str)
            .str.upper()
        )


        results_df["Ticker"] = (
            results_df["Ticker"]
            .astype(str)
            .str.upper()
        )


        # Fields to bring into portfolio
        enrichment_columns = [

            "Ticker",

            "Signal",

            "Technical Score",

            "Quality Score",

            "Growth Score",

            "Investment Score",

            "Confidence",

            "Confidence Score",

            "AI Decision",

            "AI Conviction",

            "AI Conviction Score",

            "AI Action",

            "AI Investment Thesis",

            "AI Decision Thesis",

            "Recommendation Reasons",

            "Recommendation Risks",

            "AI Summary",

            "AI Analysis",

            "Price",

            "RSI",

            "Sector",

            "Industry"
        ]


        # Only use columns that exist
        available_columns = [
            c for c in enrichment_columns
            if c in results_df.columns
        ]


        enrichment = results_df[
            available_columns
        ]


        # Remove duplicate tickers
        enrichment = (
            enrichment
            .drop_duplicates(
                subset=["Ticker"],
                keep="first"
            )
        )


        # Merge intelligence
        portfolio_summary = portfolio_summary.merge(
            enrichment,
            on="Ticker",
            how="left",
            suffixes=(
                "",
                "_Scanner"
            )
        )


        # Fill missing values
        default_values = {

            "Signal": "HOLD",

            "Technical Score": 0,

            "Quality Score": 0,

            "Growth Score": 0,

            "Investment Score": 0,

            "Confidence": "LOW",

            "Confidence Score": 0,

            "AI Decision": "NO REVIEW",

            "AI Conviction": "LOW",

            "AI Conviction Score": 0,

            "AI Action": "MONITOR",

            "Recommendation Reasons": [],

            "Recommendation Risks": []

        }


        for column, default in default_values.items():

            if column in portfolio_summary.columns:

                portfolio_summary[column] = (
                    portfolio_summary[column]
                    .apply(
                        lambda x:
                        default
                        if pd.isna(x)
                        else x
                    )
                )


        print(
            "Portfolio enrichment complete:",
            portfolio_summary.shape
        )


        return portfolio_summary


    except Exception as e:

        print(
            "Portfolio enrichment failed:",
            e
        )

        return portfolio_summary