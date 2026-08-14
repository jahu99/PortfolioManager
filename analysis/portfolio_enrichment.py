import pandas as pd


def _is_missing_scalar(value):
    """
    Safely determine whether a value is missing.

    Handles scalars, lists, arrays and pandas objects without
    triggering:

        The truth value of an array with more than one element
        is ambiguous
    """

    if value is None:
        return True

    # Lists / arrays / tuples are legitimate values for fields
    # such as Recommendation Reasons and Recommendation Risks.
    if isinstance(
        value,
        (list, tuple, set)
    ):
        return len(value) == 0

    try:

        result = pd.isna(value)

        # pd.isna(array-like) returns an array.
        if hasattr(
            result,
            "__len__"
        ):
            return False

        return bool(result)

    except Exception:

        return False


def _safe_default(value):
    """
    Return a safe copy of a default value.

    Prevents mutable defaults such as [] from being shared
    between rows.
    """

    if isinstance(value, list):
        return list(value)

    if isinstance(value, dict):
        return dict(value)

    if isinstance(value, set):
        return set(value)

    return value


def enrich_portfolio_holdings(
    portfolio_summary,
    results
):
    """
    Enrich portfolio holdings with stock intelligence
    from the market scanner results.

    Inputs
    ------
    portfolio_summary:
        DataFrame created by analyse_portfolio()

    results:
        List of analysed stocks.

    Returns
    -------
    Enriched portfolio_summary DataFrame.

    Notes
    -----
    The portfolio itself remains authoritative.

    This function only adds scanner intelligence.

    If a ticker cannot be enriched, the underlying portfolio
    holding is retained.
    """

    try:

        # ====================================================
        # VALIDATE PORTFOLIO SUMMARY
        # ====================================================

        if portfolio_summary is None:

            return pd.DataFrame()

        if not isinstance(
            portfolio_summary,
            pd.DataFrame
        ):

            portfolio_summary = pd.DataFrame(
                portfolio_summary
            )

        if portfolio_summary.empty:

            return portfolio_summary

        # ====================================================
        # VALIDATE RESULTS
        # ====================================================

        if results is None:

            return portfolio_summary

        # Avoid using:

        #     if not results

        # because results could potentially be a numpy array
        # or pandas object.

        if isinstance(
            results,
            pd.DataFrame
        ):

            results_df = results.copy()

        else:

            try:

                results_df = pd.DataFrame(
                    results
                )

            except Exception as exc:

                print(
                    "Portfolio enrichment skipped:",
                    exc
                )

                return portfolio_summary

        if results_df.empty:

            return portfolio_summary

        # ====================================================
        # TICKER VALIDATION
        # ====================================================

        if "Ticker" not in portfolio_summary.columns:

            print(
                "Portfolio enrichment skipped: "
                "portfolio summary has no Ticker column"
            )

            return portfolio_summary

        if "Ticker" not in results_df.columns:

            print(
                "Portfolio enrichment skipped: "
                "scanner results have no Ticker column"
            )

            return portfolio_summary

        # ====================================================
        # NORMALISE TICKERS
        # ====================================================

        portfolio_summary = (
            portfolio_summary.copy()
        )

        results_df = (
            results_df.copy()
        )

        portfolio_summary["Ticker"] = (
            portfolio_summary["Ticker"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        results_df["Ticker"] = (
            results_df["Ticker"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # ====================================================
        # FIELDS TO BRING INTO PORTFOLIO
        # ====================================================

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

        # ====================================================
        # ONLY USE AVAILABLE COLUMNS
        # ====================================================

        available_columns = [

            column

            for column in enrichment_columns

            if column in results_df.columns

        ]

        if "Ticker" not in available_columns:

            print(
                "Portfolio enrichment skipped: "
                "scanner results contain no usable Ticker"
            )

            return portfolio_summary

        enrichment = (
            results_df[
                available_columns
            ]
            .copy()
        )

        # ====================================================
        # REMOVE DUPLICATE TICKERS
        # ====================================================

        enrichment = (
            enrichment
            .drop_duplicates(
                subset=["Ticker"],
                keep="first"
            )
        )

        # ====================================================
        # MERGE INTELLIGENCE
        # ====================================================

        portfolio_summary = (
            portfolio_summary.merge(
                enrichment,
                on="Ticker",
                how="left",
                suffixes=(
                    "",
                    "_Scanner"
                )
            )
        )

        # ====================================================
        # DEFAULT VALUES
        # ====================================================

        default_values = {

            "Signal":
                "HOLD",

            "Technical Score":
                0,

            "Quality Score":
                0,

            "Growth Score":
                0,

            "Investment Score":
                0,

            "Confidence":
                "LOW",

            "Confidence Score":
                0,

            "AI Decision":
                "NO REVIEW",

            "AI Conviction":
                "LOW",

            "AI Conviction Score":
                0,

            "AI Action":
                "MONITOR",

            "Recommendation Reasons":
                [],

            "Recommendation Risks":
                []
        }

        # ====================================================
        # SAFELY FILL MISSING VALUES
        # ====================================================

        for column, default in default_values.items():

            if column not in portfolio_summary.columns:

                continue

            def replace_missing(value):

                if _is_missing_scalar(
                    value
                ):

                    return _safe_default(
                        default
                    )

                return value

            portfolio_summary[column] = (
                portfolio_summary[column]
                .apply(
                    replace_missing
                )
            )

        # ====================================================
        # COMPLETE
        # ====================================================

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

        # Never allow enrichment failure to destroy the
        # underlying portfolio summary.

        return portfolio_summary