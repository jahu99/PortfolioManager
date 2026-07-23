import yfinance as yf
import pandas as pd


def analyse_sectors(portfolio_summary):

    sector_results = []


    if portfolio_summary is None or portfolio_summary.empty:
        return sector_results


    for _, holding in portfolio_summary.iterrows():

        ticker = holding["Ticker"]

        value = holding["Current Value"]


        try:

            info = yf.Ticker(ticker).info

            sector = info.get(
                "sector",
                "Unknown"
            )


        except Exception:

            sector = "Unknown"



        sector_results.append(
            {
                "Ticker": ticker,
                "Sector": sector,
                "Current Value": value
            }
        )


    sector_df = pd.DataFrame(
        sector_results
    )


    if sector_df.empty:
        return sector_df



    total_value = (
        sector_df["Current Value"]
        .sum()
    )


    sector_summary = (
        sector_df
        .groupby("Sector")
        ["Current Value"]
        .sum()
        .reset_index()
    )


    sector_summary["Allocation %"] = (
        sector_summary["Current Value"]
        /
        total_value
        *
        100
    ).round(2)



    sector_summary["Status"] = (
        sector_summary["Allocation %"]
        .apply(
            lambda x:
            "High Exposure"
            if x > 40
            else "OK"
        )
    )


    return sector_summary