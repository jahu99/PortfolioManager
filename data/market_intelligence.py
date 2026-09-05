"""
External Market & Event Intelligence data collection.

Collects:

- Analyst recommendation
- Analyst price targets
- Analyst target upside/downside
- Next earnings date
- Recent news headlines

Results are cached locally to avoid repeated external API calls.

This module does NOT make portfolio decisions.
It is a data collection layer only.
"""

import json
import os

from datetime import date, datetime, timedelta, timezone

import yfinance as yf


# ============================================================
# CONFIGURATION
# ============================================================

CACHE_DIR = "data/cache/market_intelligence"

CACHE_TTL_HOURS = 24


# ============================================================
# CACHE HELPERS
# ============================================================

def _get_cache_file(ticker):

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )

    return os.path.join(
        CACHE_DIR,
        f"{ticker}.json"
    )


def _load_cached_intelligence(ticker):

    cache_file = _get_cache_file(
        ticker
    )

    if not os.path.exists(
        cache_file
    ):

        return None


    try:

        with open(
            cache_file,
            "r"
        ) as f:

            cached = json.load(
                f
            )


        collected_at = cached.get(
            "Collected At"
        )

        if not collected_at:

            return None


        collected_time = datetime.fromisoformat(
            collected_at
        )

        if collected_time.tzinfo is None:

            collected_time = (
                collected_time.replace(
                    tzinfo=timezone.utc
                )
            )


        expiry_time = (

            collected_time

            + timedelta(
                hours=CACHE_TTL_HOURS
            )

        )


        if datetime.now(
            timezone.utc
        ) < expiry_time:

            return cached


        return None


    except Exception as exc:

        print(

            f"Market intelligence cache "
            f"read failed for {ticker}: {exc}"

        )

        return None


def _save_cached_intelligence(

    ticker,

    intelligence

):

    cache_file = _get_cache_file(
        ticker
    )


    try:

        with open(
            cache_file,
            "w"
        ) as f:

            json.dump(

                intelligence,

                f,

                indent=4,

                default=str

            )


    except Exception as exc:

        print(

            f"Market intelligence cache "
            f"write failed for {ticker}: {exc}"

        )


# ============================================================
# ANALYST RECOMMENDATION NORMALISATION
# ============================================================

def _normalise_recommendation(
    recommendation
):

    if recommendation is None:

        return "UNKNOWN"

    value = (
        str(
            recommendation
        )
        .replace(
            "_",
            " "
        )
        .replace(
            "-",
            " "
        )
        .upper()
        .strip()
    )

    if not value:

        return "UNKNOWN"

    null_values = {

        "NONE",
        "NULL",
        "N/A",
        "NA",
        "UNKNOWN",
        "NAN",

    }

    if value in null_values:

        return "UNKNOWN"

    mapping = {

        "STRONG BUY":
            "STRONG BUY",

        "BUY":
            "BUY",

        "MODERATE BUY":
            "BUY",

        "OUTPERFORM":
            "BUY",

        "OVERWEIGHT":
            "BUY",

        "HOLD":
            "HOLD",

        "NEUTRAL":
            "HOLD",

        "UNDERPERFORM":
            "SELL",

        "UNDERWEIGHT":
            "SELL",

        "SELL":
            "SELL",

        "STRONG SELL":
            "STRONG SELL",

    }

    return mapping.get(
        value,
        "UNKNOWN"
    )


# ============================================================
# ANALYST RECOMMENDATION FALLBACK
# ============================================================

def _derive_recommendation_from_summary(
    recommendations
):

    """
    Derive an analyst recommendation and mean score from
    Yahoo Finance recommendations summary data when the
    direct recommendationKey / recommendationMean fields
    are unavailable.
    """

    if recommendations is None:

        return (
            "UNKNOWN",
            None
        )


    try:

        if recommendations.empty:

            return (
                "UNKNOWN",
                None
            )


        # Yahoo normally returns the latest period first.

        latest = recommendations.iloc[0]


        strong_buy = float(
            latest.get(
                "strongBuy",
                0
            ) or 0
        )

        buy = float(
            latest.get(
                "buy",
                0
            ) or 0
        )

        hold = float(
            latest.get(
                "hold",
                0
            ) or 0
        )

        sell = float(
            latest.get(
                "sell",
                0
            ) or 0
        )

        strong_sell = float(
            latest.get(
                "strongSell",
                0
            ) or 0
        )


        total = (

            strong_buy
            + buy
            + hold
            + sell
            + strong_sell

        )


        if total <= 0:

            return (
                "UNKNOWN",
                None
            )


        # Yahoo recommendationMean convention:
        #
        # 1 = Strong Buy
        # 2 = Buy
        # 3 = Hold
        # 4 = Sell
        # 5 = Strong Sell

        mean_score = (

            (
                strong_buy * 1
                + buy * 2
                + hold * 3
                + sell * 4
                + strong_sell * 5
            )

            /

            total

        )


        # Convert the calculated mean into the project's
        # standard recommendation categories.

        if mean_score <= 1.5:

            recommendation = (
                "STRONG BUY"
            )

        elif mean_score <= 2.5:

            recommendation = (
                "BUY"
            )

        elif mean_score <= 3.5:

            recommendation = (
                "HOLD"
            )

        elif mean_score <= 4.5:

            recommendation = (
                "SELL"
            )

        else:

            recommendation = (
                "STRONG SELL"
            )


        return (

            recommendation,

            round(
                mean_score,
                5
            )

        )


    except Exception:

        return (
            "UNKNOWN",
            None
        )
# ============================================================
# EARNINGS HELPERS
# ============================================================

def _extract_earnings_date(calendar):

    if calendar is None:

        return None

    try:

        if isinstance(calendar, dict):

            earnings_date = calendar.get(
                "Earnings Date"
            )

        else:

            earnings_date = None

            if hasattr(calendar, "index"):

                if (
                    "Earnings Date"
                    in calendar.index
                ):

                    earnings_date = (
                        calendar.loc[
                            "Earnings Date"
                        ]
                    )

        if earnings_date is None:

            return None

        # Yahoo Finance may return multiple dates.

        if isinstance(
            earnings_date,
            (list, tuple)
        ):

            if not earnings_date:

                return None

            earnings_date = earnings_date[0]

        # Handle pandas Series / Index-like values.

        if hasattr(
            earnings_date,
            "iloc"
        ):

            if len(earnings_date) == 0:

                return None

            earnings_date = (
                earnings_date.iloc[0]
            )

        if earnings_date is None:

            return None

        # A genuine datetime can be returned directly.

        # Yahoo Finance can return either a datetime.datetime
        # or a datetime.date.

        if isinstance(
            earnings_date,
            datetime
        ):

            return earnings_date.isoformat()


        if isinstance(
            earnings_date,
            date
        ):

            return earnings_date.isoformat()
        # Do not blindly accept arbitrary values such as
        # integers or malformed Yahoo Finance responses.
        #
        # Attempt to parse strings into genuine dates.

        if isinstance(
            earnings_date,
            str
        ):

            value = earnings_date.strip()

            if not value:

                return None

            try:

                parsed_date = (
                    datetime.fromisoformat(
                        value.replace(
                            "Z",
                            "+00:00"
                        )
                    )
                )

                return parsed_date.isoformat()

            except ValueError:

                return None

        return None

    except Exception:

        return None
# ============================================================
# NEWS HELPERS
# ============================================================

def _extract_news(

    news,

    ticker=None,

    company_name=None,

    limit=5

):

    if not news:

        return []


    articles = []


    # ====================================================
    # BUILD COMPANY IDENTIFIERS
    # ====================================================

    company_identifiers = []


    if ticker:

        ticker_identifier = (
            str(ticker)
            .strip()
            .lower()
        )

        if ticker_identifier:

            company_identifiers.append(
                ticker_identifier
            )


    if company_name:

        company_identifier = (
            str(company_name)
            .strip()
            .lower()
        )

        if company_identifier:

            company_identifiers.append(
                company_identifier
            )


    for item in news[:limit]:

        try:

            # ====================================================
            # NEW YAHOO FINANCE STRUCTURE
            # ====================================================

            content = item.get(

                "content",

                {}

            ) or {}


            title = content.get(

                "title"

            )


            description = (

                content.get(

                    "summary"

                )

                or

                content.get(

                    "description"

                )

            )


            provider = content.get(

                "provider",

                {}

            ) or {}


            publisher = provider.get(

                "displayName"

            )


            published_at = content.get(

                "pubDate"

            )


            canonical_url = (

                content.get(

                    "canonicalUrl",

                    {}

                )

                or

                content.get(

                    "clickThroughUrl",

                    {}

                )

                or {}

            )


            link = canonical_url.get(

                "url"

            )


            # ====================================================
            # BACKWARDS COMPATIBILITY
            # ====================================================

            if not title:

                title = item.get(

                    "title"

                )


            if not description:

                description = (

                    item.get(

                        "summary"

                    )

                    or

                    item.get(

                        "description"

                    )

                )


            if not publisher:

                publisher = item.get(

                    "publisher"

                )


            if not published_at:

                publish_time = item.get(

                    "providerPublishTime"

                )


                if publish_time:

                    try:

                        published_at = (

                            datetime.fromtimestamp(

                                publish_time,

                                tz=timezone.utc

                            ).isoformat()

                        )

                    except Exception:

                        published_at = None


            if not link:

                link = item.get(

                    "link"

                )


            # ====================================================
            # ONLY KEEP VALID ARTICLES
            # ====================================================

            if not title:

                continue


            # ====================================================
            # COMPANY RELEVANCE FILTER
            #
            # Only retain articles where the company name
            # or ticker is explicitly mentioned in the title
            # or description.
            # ====================================================

            searchable_text = " ".join(

                [

                    str(title or ""),

                    str(description or ""),

                ]

            ).lower()


            is_relevant = any(

                identifier in searchable_text

                for identifier in company_identifiers

                if identifier

            )


            if not is_relevant:

                continue


            # ====================================================
            # BUILD NORMALISED ARTICLE
            # ====================================================

            article = {

                "Title":

                    str(

                        title

                    ),


                "Description":

                    str(

                        description

                    )

                    if description

                    else None,


                "Publisher":

                    str(

                        publisher

                    )

                    if publisher

                    else None,


                "Published At":

                    str(

                        published_at

                    )

                    if published_at

                    else None,


                "Link":

                    str(

                        link

                    )

                    if link

                    else None,

            }


            articles.append(

                article

            )


        except Exception:

            continue


    return articles
# ============================================================
# MAIN COLLECTION FUNCTION
# ============================================================

def collect_market_intelligence(

    ticker,

    company_name=None,

    force_refresh=False

):

    """
    Collect external market and event intelligence.

    Results are cached for CACHE_TTL_HOURS unless
    force_refresh=True.

    This function does not make recommendations or alter
    portfolio decisions.
    """

    ticker = str(
        ticker
    ).upper().strip()


    # ========================================================
    # CACHE
    # ========================================================

    if not force_refresh:

        cached = (
            _load_cached_intelligence(
                ticker
            )
        )


        if cached is not None:

            return cached


    print(

        f"Collecting market intelligence: {ticker}"

    )


    # ========================================================
    # DEFAULT RESULT
    # ========================================================

    intelligence = {

        "Ticker":

            ticker,


        "Collected At":

            datetime.now(
                timezone.utc
            ).isoformat(),


        "Source":

            "Yahoo Finance",


        "Analyst Recommendation":

            "UNKNOWN",


        "Analyst Mean Score":

            None,


        "Analyst Target Mean":

            None,


        "Analyst Target High":

            None,


        "Analyst Target Low":

            None,


        "Current Price":

            None,


        "Analyst Target Upside %":

            None,


        "Next Earnings Date":

            None,


        "Earnings Status":

            "UNKNOWN",


        "News Count":

            0,


        "Recent News":

            [],

    }


    # ========================================================
    # YAHOO FINANCE
    # ========================================================

    try:

        stock = yf.Ticker(
            ticker
        )


    except Exception as exc:

        print(

            f"Unable to initialise Yahoo Finance "
            f"for {ticker}: {exc}"

        )


        intelligence[
            "Source"
        ] = "UNAVAILABLE"


        return intelligence


    # ========================================================
    # ANALYST + PRICE TARGET INTELLIGENCE
    # ========================================================

    try:

        info = stock.info or {}


        # ----------------------------------------------------
        # PRIMARY ANALYST RECOMMENDATION
        # ----------------------------------------------------

        recommendation = info.get(
            "recommendationKey"
        )


        normalised_recommendation = (
            _normalise_recommendation(
                recommendation
            )
        )


        mean_score = info.get(
            "recommendationMean"
        )


        if mean_score is not None:

            try:

                mean_score = float(
                    mean_score
                )

            except (
                TypeError,
                ValueError
            ):

                mean_score = None


        # ----------------------------------------------------
        # FALLBACK ANALYST DATA
        #
        # Yahoo can return:
        #
        # recommendationKey = "none"
        # recommendationMean = None
        #
        # while still providing valid analyst consensus data
        # through stock.recommendations.
        # ----------------------------------------------------

        if (

            normalised_recommendation == "UNKNOWN"

            or

            mean_score is None

        ):

            try:

                recommendations = (
                    stock.recommendations
                )


                if (

                    recommendations is not None

                    and

                    not recommendations.empty

                ):

                    # Latest Yahoo consensus period.

                    latest = (
                        recommendations.iloc[0]
                    )


                    strong_buy = float(

                        latest.get(
                            "strongBuy",
                            0
                        ) or 0

                    )


                    buy = float(

                        latest.get(
                            "buy",
                            0
                        ) or 0

                    )


                    hold = float(

                        latest.get(
                            "hold",
                            0
                        ) or 0

                    )


                    sell = float(

                        latest.get(
                            "sell",
                            0
                        ) or 0

                    )


                    strong_sell = float(

                        latest.get(
                            "strongSell",
                            0
                        ) or 0

                    )


                    total = (

                        strong_buy

                        + buy

                        + hold

                        + sell

                        + strong_sell

                    )


                    if total > 0:

                        # Yahoo convention:
                        #
                        # 1 = Strong Buy
                        # 2 = Buy
                        # 3 = Hold
                        # 4 = Sell
                        # 5 = Strong Sell

                        fallback_mean_score = (

                            (

                                strong_buy * 1

                                + buy * 2

                                + hold * 3

                                + sell * 4

                                + strong_sell * 5

                            )

                            /

                            total

                        )


                        fallback_mean_score = round(

                            fallback_mean_score,

                            5

                        )


                        # Only use the fallback score when
                        # Yahoo's direct score is unavailable.

                        if mean_score is None:

                            mean_score = (
                                fallback_mean_score
                            )


                        # Only derive the recommendation when
                        # Yahoo's direct recommendation is
                        # unavailable.

                        if (

                            normalised_recommendation
                            == "UNKNOWN"

                        ):

                            if fallback_mean_score <= 1.5:

                                normalised_recommendation = (
                                    "STRONG BUY"
                                )


                            elif fallback_mean_score <= 2.5:

                                normalised_recommendation = (
                                    "BUY"
                                )


                            elif fallback_mean_score <= 3.5:

                                normalised_recommendation = (
                                    "HOLD"
                                )


                            elif fallback_mean_score <= 4.5:

                                normalised_recommendation = (
                                    "SELL"
                                )


                            else:

                                normalised_recommendation = (
                                    "STRONG SELL"
                                )


            except Exception as exc:

                print(

                    f"Analyst recommendation fallback "
                    f"unavailable for {ticker}: {exc}"

                )


        # ----------------------------------------------------
        # STORE ANALYST RECOMMENDATION
        # ----------------------------------------------------

        intelligence[
            "Analyst Recommendation"
        ] = (
            normalised_recommendation
        )


        intelligence[
            "Analyst Mean Score"
        ] = (
            mean_score
        )


        # ----------------------------------------------------
        # ANALYST PRICE TARGETS
        # ----------------------------------------------------

        target_mean = info.get(
            "targetMeanPrice"
        )


        target_high = info.get(
            "targetHighPrice"
        )


        target_low = info.get(
            "targetLowPrice"
        )


        if target_mean is not None:

            intelligence[
                "Analyst Target Mean"
            ] = float(
                target_mean
            )


        if target_high is not None:

            intelligence[
                "Analyst Target High"
            ] = float(
                target_high
            )


        if target_low is not None:

            intelligence[
                "Analyst Target Low"
            ] = float(
                target_low
            )


        # ----------------------------------------------------
        # CURRENT PRICE
        # ----------------------------------------------------

        current_price = (

            info.get(
                "currentPrice"
            )

            or

            info.get(
                "regularMarketPrice"
            )

        )


        if current_price is not None:

            intelligence[
                "Current Price"
            ] = float(
                current_price
            )


        # ----------------------------------------------------
        # ANALYST TARGET UPSIDE / DOWNSIDE
        # ----------------------------------------------------

        if (

            current_price is not None

            and

            target_mean is not None

        ):

            current_price = float(
                current_price
            )


            target_mean = float(
                target_mean
            )


            if current_price > 0:

                intelligence[
                    "Analyst Target Upside %"
                ] = round(

                    (

                        (

                            target_mean

                            - current_price

                        )

                        /

                        current_price

                    )

                    * 100,

                    2

                )


    except Exception as exc:

        print(

            f"Analyst intelligence unavailable "
            f"for {ticker}: {exc}"

        )


    # ========================================================
    # EARNINGS INTELLIGENCE
    # ========================================================

    try:

        calendar = stock.calendar


        earnings_date = (
            _extract_earnings_date(
                calendar
            )
        )


        if earnings_date:

            intelligence[
                "Next Earnings Date"
            ] = earnings_date


            intelligence[
                "Earnings Status"
            ] = "SCHEDULED"


        else:

            # Yahoo responded successfully but did not provide
            # a future earnings date.

            intelligence[
                "Earnings Status"
            ] = "NOT AVAILABLE"


    except Exception as exc:

        print(

            f"Earnings intelligence unavailable "
            f"for {ticker}: {exc}"

        )


        intelligence[
            "Earnings Status"
        ] = "UNAVAILABLE"


    # ========================================================
    # NEWS INTELLIGENCE
    # ========================================================

    # ========================================================
    # NEWS INTELLIGENCE
    # ========================================================

    try:

        news = stock.get_news(

            count=5,

            tab="news"

        ) or []


        articles = _extract_news(

            news,

            ticker=ticker,

            company_name=company_name,

            limit=5

        )


        intelligence[
            "News Count"
        ] = len(
            articles
        )


        intelligence[
            "Recent News"
        ] = articles


    except Exception as exc:

        print(

            f"News intelligence unavailable "
            f"for {ticker}: {exc}"

        )

    # ========================================================
    # CACHE RESULT
    # ========================================================

    _save_cached_intelligence(

        ticker,

        intelligence

    )


    return intelligence