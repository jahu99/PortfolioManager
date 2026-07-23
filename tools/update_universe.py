import pandas as pd
import ssl
import urllib.request
import os


PROJECT_FOLDER = "/Users/jameshulin/Documents/stock-momentum-agent"


def update_sp500_csv():

    print("Downloading S&P 500 list...")


    url = (
        "https://raw.githubusercontent.com/"
        "datasets/s-and-p-500-companies/"
        "master/data/constituents.csv"
    )


    ssl_context = ssl._create_unverified_context()


    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )


    response = urllib.request.urlopen(
        request,
        context=ssl_context
    )


    df = pd.read_csv(
        response
    )


    # Rename column to match our scanner
    df = df.rename(
        columns={
            "Symbol": "Ticker"
        }
    )


    df["Ticker"] = (
        df["Ticker"]
        .str.replace(
            ".",
            "-",
            regex=False
        )
    )


    output_file = os.path.join(
        PROJECT_FOLDER,
        "data",
        "sp500.csv"
    )


    df[["Ticker"]].to_csv(
        output_file,
        index=False
    )


    print("--------------------------")
    print(f"Saved: {output_file}")
    print(f"Stocks: {len(df)}")
    print("--------------------------")


if __name__ == "__main__":
    update_sp500_csv()