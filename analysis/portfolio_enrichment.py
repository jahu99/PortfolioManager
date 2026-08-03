# analysis/portfolio_enrichment.py

import pandas as pd


def enrich_portfolio_holdings(
    portfolio_summary,
    stock_results
):
    """
    Enrich portfolio holdings with latest scanner intelligence.
    """

    if portfolio_summary is None:
        return pd.DataFrame()

    if stock_results is None:
        stock_results = []

    enriched = portfolio_summary.copy()

    results_df = pd.DataFrame(stock_results)

    if results_df.empty:

        if "Signal" in enriched.columns:
            enriched["Signal"] = (
                enriched["Signal"]
                .fillna("PORTFOLIO HOLDING")
            )

        return enriched

    # -----------------------------
    # Normalise merge keys
    # -----------------------------

    enriched["Ticker"] = (
        enriched["Ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    results_df["Ticker"] = (
        results_df["Ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    lookup_columns = [
        "Ticker",
        "Signal",
        "Investment Score",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Confidence",
        "Confidence Score",
        "Sector",
        "Industry"
    ]

    available_columns = [
        c for c in lookup_columns
        if c in results_df.columns
    ]

    intelligence = (
        results_df[available_columns]
        .drop_duplicates(subset=["Ticker"])
    )

    enriched = enriched.merge(
        intelligence,
        on="Ticker",
        how="left",
        suffixes=("", "_Scanner")
    )

    # ------------------------------------------------
    # Replace placeholders with scanner values
    # ------------------------------------------------

    replace_map = {
        "Sector": "Sector_Scanner",
        "Industry": "Industry_Scanner",
        "Signal": "Signal_Scanner",
        "Investment Score": "Investment Score_Scanner",
        "Technical Score": "Technical Score_Scanner",
        "Quality Score": "Quality Score_Scanner",
        "Growth Score": "Growth Score_Scanner",
        "Confidence": "Confidence_Scanner",
        "Confidence Score": "Confidence Score_Scanner"
    }

    for target, source in replace_map.items():

        if source not in enriched.columns:
            continue

        # Convert placeholders into NaN
        if target in [
            "Sector",
            "Industry",
            "Signal",
            "Confidence"
        ]:

            enriched[target] = (
                enriched[target]
                .replace(
                    [
                        "Unknown",
                        "NOT IN UNIVERSE",
                        "PORTFOLIO HOLDING",
                        ""
                    ],
                    pd.NA
                )
            )

        else:

            enriched[target] = (
                pd.to_numeric(
                    enriched[target],
                    errors="coerce"
                )
                .replace(0, pd.NA)
            )

        enriched[target] = (
            enriched[target]
            .fillna(enriched[source])
        )

    # -----------------------------
    # Final defaults
    # -----------------------------

    for field in [
        "Investment Score",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Confidence Score"
    ]:

        if field in enriched.columns:

            enriched[field] = (
                pd.to_numeric(
                    enriched[field],
                    errors="coerce"
                )
                .fillna(0)
            )

    if "Signal" in enriched.columns:

        enriched["Signal"] = (
            enriched["Signal"]
            .fillna("PORTFOLIO HOLDING")
        )

    if "Confidence" in enriched.columns:

        enriched["Confidence"] = (
            enriched["Confidence"]
            .fillna("Unknown")
        )

    if "Sector" in enriched.columns:

        enriched["Sector"] = (
            enriched["Sector"]
            .fillna("Unknown")
        )

    if "Industry" in enriched.columns:

        enriched["Industry"] = (
            enriched["Industry"]
            .fillna("Unknown")
        )

    print(
        enriched[
            ["Ticker", "Sector", "Investment Score"]
        ].head(20)
    )

    return enriched