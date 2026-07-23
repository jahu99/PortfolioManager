import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os
import glob
import numpy as np



def get_price_history(ticker, start, end):

    try:

        data = yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True
        )


        if data.empty:
            return None


        if isinstance(data.columns, pd.MultiIndex):

            data.columns = (
                data.columns
                .get_level_values(0)
            )


        return data


    except Exception as e:

        print(
            f"Download error {ticker}: {e}"
        )

        return None




def find_latest_report():

    files = glob.glob(
        "reports/daily_report_*.xlsx"
    )


    if not files:

        raise Exception(
            "No reports found"
        )


    return max(
        files,
        key=os.path.getmtime
    )




def calculate_metrics(returns):

    total_return = (
        (1 + returns).prod()
        - 1
    ) * 100


    years = len(returns) / 252


    annualised_return = (
        (1 + returns.mean()) ** 252
        - 1
    ) * 100


    volatility = (
        returns.std()
        *
        np.sqrt(252)
        *
        100
    )


    cumulative = (
        1 + returns
    ).cumprod()


    running_max = (
        cumulative
        .cummax()
    )


    drawdown = (
        cumulative
        /
        running_max
        -
        1
    )


    max_drawdown = (
        drawdown.min()
        *
        100
    )


    sharpe = (
        returns.mean()
        /
        returns.std()
        *
        np.sqrt(252)
    )


    return {

        "Total Return %":
            round(
                total_return,
                2
            ),

        "Annualised Return %":
            round(
                annualised_return,
                2
            ),

        "Volatility %":
            round(
                volatility,
                2
            ),

        "Maximum Drawdown %":
            round(
                max_drawdown,
                2
            ),

        "Sharpe Ratio":
            round(
                sharpe,
                2
            )
    }




def run_backtest():

    print(
        "=============================="
    )

    print(
        "BACKTEST VERSION 2"
    )

    print(
        "=============================="
    )


    years = 5

    portfolio_size = 20


    end_date = datetime.today()


    start_date = (
        end_date
        -
        timedelta(
            days=365 * years
        )
    )


    report = find_latest_report()


    print(
        f"Using report: {report}"
    )


    rankings = pd.read_excel(
        report,
        sheet_name="Stock Rankings"
    )


    rankings = rankings.sort_values(
        "Investment Score",
        ascending=False
    )


    selected = rankings.head(
        portfolio_size
    )


    tickers = list(
        selected["Ticker"]
    )


    print(
        "Testing:"
    )

    print(
        tickers
    )


    daily_prices = {}


    for ticker in tickers:


        data = get_price_history(
            ticker,
            start_date,
            end_date
        )


        if data is not None:

            daily_prices[ticker] = (
                data["Close"]
            )



    prices = pd.DataFrame(
        daily_prices
    )


    prices = prices.dropna()


    returns = (
        prices
        .pct_change()
        .dropna()
    )


    # Equal weighted portfolio

    portfolio_returns = (
        returns.mean(axis=1)
    )


    strategy_metrics = calculate_metrics(
        portfolio_returns
    )


    # Benchmark

    benchmark = get_price_history(
        "^GSPC",
        start_date,
        end_date
    )


    benchmark_returns = (
        benchmark["Close"]
        .pct_change()
        .dropna()
    )


    benchmark_metrics = calculate_metrics(
        benchmark_returns
    )



    summary = pd.DataFrame(
        [
            {
                "Strategy":
                    "Momentum Model",
                **strategy_metrics
            },

            {
                "Strategy":
                    "S&P 500",
                **benchmark_metrics
            }
        ]
    )



    print(
        "\nRESULTS"
    )

    print(
        summary
    )



    output = (
        "reports/backtest_v2_results.xlsx"
    )


    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:


        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False
        )


        selected.to_excel(
            writer,
            sheet_name="Selected Stocks",
            index=False
        )



    print(
        f"\nSaved {output}"
    )



if __name__ == "__main__":

    run_backtest()