import pandas as pd


raw_file = "data/nasdaq_raw.txt"
output_file = "data/nasdaq.csv"


df = pd.read_csv(
    raw_file,
    sep="|"
)


# Remove footer
df = df[
    df["Symbol"].notna()
]


df = df[
    df["Symbol"] != "File Creation Time"
]


# Keep only normal shares
df = df[
    df["ETF"] == "N"
]


df = df[
    df["Test Issue"] == "N"
]


# Remove obvious derivatives
exclude_words = [
    "Warrant",
    "Right",
    "Unit",
    "Preferred",
    "Depositary",
    "ADR"
]


mask = True

for word in exclude_words:

    mask = mask & (
        ~df["Security Name"]
        .str.contains(
            word,
            case=False,
            na=False
        )
    )


df = df[mask]


output = pd.DataFrame()


output["Ticker"] = (
    df["Symbol"]
    .astype(str)
    .str.strip()
)


output = output[
    output["Ticker"] != ""
]


output.to_csv(
    output_file,
    index=False
)


print(
    f"Created {output_file}: {len(output)} stocks"
)
