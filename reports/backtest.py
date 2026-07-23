import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os
import glob



def get_price_history(ticker, start, end):

    print(
        f"Downloading prices: {ticker}"
    )

    try:

        data = yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True
        )


        if data.empty:

            print(
                f"No data for {ticker}"
            )

            return None



        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            data.columns = (
                data.columns
                .get_level_values(0)
            )


        return data



    except Exception as e:

        print(
            f"Error downloading {ticker}: {e}"
        )

        return None




def calculate_return(
    start_price,
    end_price
):

    return (
        (
            end_price
            -
            start_price
        )
        /
        start_price
    ) * 100




def find_latest_report():

    print(
        "Searching for latest report..."
    )


    files = glob.glob(
        "reports/daily_report_*.xlsx"
    )


    if not files:

        raise Exception(
            "No daily reports found in reports folder"
        )


    latest = max(
        files,
        key=os.path.getmtime
    )


    return latest




def run_backtest():

    print(
        "=============================="
    )

    print(
        "STARTING BACKTEST"
    )

    print(
        "=============================="
    )



    # ---------------------------------
    # Settings
    # ---------------------------------

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



    print(
        f"Testing period: {start_date.date()} to {end_date.date()}"
    )



    # ---------------------------------
    # Load latest report
    # ---------------------------------

    report = find_latest_report()


    print(
        f"Using report: {report}"
    )



    rankings = pd.read_excel(
        report,
        sheet_name="Stock Rankings"
    )



    print(
        f"Loaded {len(rankings)} stocks"
    )



    if (
        "Investment Score"
        not in rankings.columns
    ):

        raise Exception(
            "Investment Score column not found"
        )



    rankings = rankings.sort_values(
        by="Investment Score",
        ascending=False
    )



    selected = rankings.head(
        portfolio_size
    )



    print(
        "\nSelected stocks:"
    )


    print(
        selected[
            [
                "Ticker",
                "Investment Score"
            ]
        ]
    )



    # ---------------------------------
    # Run test
    # ---------------------------------

    results = []



    for _, row in selected.iterrows():


        ticker = row["Ticker"]


        data = get_price_history(
            ticker,
            start_date,
            end_date
        )



        if data is None:

            continue



        if len(data) < 2:

            continue



        start_price = float(
            data["Close"].iloc[0]
        )


        end_price = float(
            data["Close"].iloc[-1]
        )



        return_pct = calculate_return(
            start_price,
            end_price
        )



        results.append(
            {

                "Ticker":
                    ticker,


                "Investment Score":
                    row[
                        "Investment Score"
                    ],


                "Start Price":
                    round(
                        start_price,
                        2
                    ),


                "End Price":
                    round(
                        end_price,
                        2
                    ),


                "Return %":
                    round(
                        return_pct,
                        2
                    )

            }
        )



    results_df = pd.DataFrame(
        results
    )



    if results_df.empty:

        print(
            "No results generated"
        )

        return



    # ---------------------------------
    # Summary
    # ---------------------------------

    average_return = (
        results_df["Return %"]
        .mean()
    )


    results_df = results_df.sort_values(
        by="Return %",
        ascending=False
    )



    print(
        "\n=============================="
    )

    print(
        "BACKTEST RESULTS"
    )

    print(
        "=============================="
    )


    print(
        results_df
    )



    print(
        "\nAverage return:"
    )


    print(
        f"{average_return:.2f}%"
    )



    # ---------------------------------
    # Save
    # ---------------------------------

    output = (
        "reports/backtest_results.xlsx"
    )


    results_df.to_excel(
        output,
        index=False
    )


    print(
        f"\nSaved: {output}"
    )


    print(
        "\nBACKTEST COMPLETE"
    )



if __name__ == "__main__":

    run_backtest()