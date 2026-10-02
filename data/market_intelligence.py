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

    company_identifiers = []

    if ticker:
        ticker_identifier = str(
            ticker
        ).strip().lower()

        if ticker_identifier:
            company_identifiers.append(
                ticker_identifier
            )

    if company_name:
        company_identifier = str(
            company_name
        ).strip().lower()

        corporate_suffixes = [
            " corporation",
            " corp.",
            " corp",
            " incorporated",
            " inc.",
            " inc",
            " limited",
            " ltd.",
            " ltd",
            " plc",
        ]

        for suffix in corporate_suffixes:
            if company_identifier.endswith(
                suffix
            ):
                company_identifier = (
                    company_identifier[
                        :-len(suffix)
                    ].strip()
                )
                break

        if company_identifier:
            company_identifiers.append(
                company_identifier
            )

    # ========================================================
    # PROCESS ALL RESULTS
    #
    # Search().news returns flat article dictionaries.
    # Do not apply the limit before filtering/parsing.
    # ========================================================

    for item in news:

        try:

            if not isinstance(
                item,
                dict
            ):
                continue

            # ====================================================
            # SUPPORT CURRENT yf.Search().news STRUCTURE
            # ====================================================

            title = item.get(
                "title"
            )

            description = (
                item.get(
                    "summary"
                )
                or item.get(
                    "description"
                )
            )

            publisher = item.get(
                "publisher"
            )

            published_at = item.get(
                "pubDate"
            )

            link = item.get(
                "link"
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

            # ====================================================
            # SUPPORT LEGACY NESTED STRUCTURE
            # ====================================================

            if not title:

                content = (
                    item.get(
                        "content",
                        {}
                    )
                    or {}
                )

                title = content.get(
                    "title"
                )

                description = (
                    content.get(
                        "summary"
                    )
                    or content.get(
                        "description"
                    )
                    or description
                )

                provider = (
                    content.get(
                        "provider",
                        {}
                    )
                    or {}
                )

                publisher = (
                    provider.get(
                        "displayName"
                    )
                    or publisher
                )

                published_at = (
                    content.get(
                        "pubDate"
                    )
                    or published_at
                )

                canonical_url = (
                    content.get(
                        "canonicalUrl",
                        {}
                    )
                    or content.get(
                        "clickThroughUrl",
                        {}
                    )
                    or {}
                )

                link = (
                    canonical_url.get(
                        "url"
                    )
                    or link
                )

            if not title:
                continue

            # ====================================================
            # RELEVANCE
            #
            # yf.Search() is already ticker-scoped.
            #
            # If relatedTickers are supplied, use them.
            # If Yahoo supplies an empty relatedTickers list,
            # do not reject the article because of that.
            # ====================================================

            related_tickers = item.get(
                "relatedTickers"
            )

            if related_tickers:

                related_tickers = {
                    str(
                        value
                    ).strip().lower()
                    for value in related_tickers
                }

                ticker_identifier = (
                    str(
                        ticker
                    ).strip().lower()
                    if ticker
                    else None
                )

                if (
                    ticker_identifier
                    and ticker_identifier
                    not in related_tickers
                ):
                    searchable_text = " ".join(
                        [
                            str(
                                title
                                or ""
                            ),
                            str(
                                description
                                or ""
                            ),
                        ]
                    ).lower()

                    is_relevant = any(
                        identifier
                        in searchable_text
                        for identifier
                        in company_identifiers
                        if identifier
                    )

                    if not is_relevant:
                        continue

            article = {
                "Title": str(
                    title
                ),

                "Description": (
                    str(
                        description
                    )
                    if description
                    else None
                ),

                "Publisher": (
                    str(
                        publisher
                    )
                    if publisher
                    else None
                ),

                "Published At": (
                    str(
                        published_at
                    )
                    if published_at
                    else None
                ),

                "Link": (
                    str(
                        link
                    )
                    if link
                    else None
                ),
            }

            articles.append(
                article
            )

            if len(
                articles
            ) >= limit:
                break

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

        "News Headlines":
            [],

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

        recommendation = info.get(
            "recommendationKey"
        )

        intelligence[
            "Analyst Recommendation"
        ] = _normalise_recommendation(
            recommendation
        )

        mean_score = info.get(
            "recommendationMean"
        )

        if mean_score is not None:

            intelligence[
                "Analyst Mean Score"
            ] = float(
                mean_score
            )

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

        if (
            current_price is not None
            and target_mean is not None
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

            intelligence[
                "Earnings Status"
            ] = "UNKNOWN"

    except Exception as exc:

        print(
            f"Earnings intelligence unavailable "
            f"for {ticker}: {exc}"
        )

        intelligence[
            "Earnings Status"
        ] = "UNKNOWN"

    # ========================================================
    # NEWS INTELLIGENCE
    # ========================================================

    try:

        news = yf.Search(
            ticker,
            news_count=10
        ).news or []

        recent_news = _extract_news(
            news,
            ticker=ticker,
            company_name=company_name,
            limit=5
        )

        intelligence[
            "Recent News"
        ] = recent_news

        intelligence[
            "News Count"
        ] = len(
            recent_news
        )

        intelligence[
            "News Headlines"
        ] = [
            article.get(
                "Title",
                ""
            )
            for article in recent_news
        ]

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