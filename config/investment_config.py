"""
Portfolio Manager Configuration
"""

# ==========================================
# CASH CONTRIBUTIONS
# ==========================================

AVAILABLE_CASH = 15

MIN_TRADE_VALUE = 1

MAX_TRADE_VALUE = 8


# Keep cash reserve
CASH_RESERVE_PERCENT = 10



# ==========================================
# INVESTMENT STYLE
# ==========================================

INVESTMENT_STYLE = "Growth"



# ==========================================
# SCORING
# ==========================================

INVESTMENT_SCORE_WEIGHT = 0.40

QUALITY_SCORE_WEIGHT = 0.25

SECTOR_NEED_WEIGHT = 0.20

CONFIDENCE_WEIGHT = 0.15



# ==========================================
# BUY RULES
# ==========================================

MIN_BUY_SCORE = 75

MIN_QUALITY_SCORE = 40


# ==========================================
# CAPITAL ALLOCATION RULES
# ==========================================

# Organic growth approach:
# keep turnover low and concentrate capital

DISCRETIONARY_SPEND_LIMIT = 15


# Maximum number of new companies added
MAX_NEW_BUYS = 3


# Maximum number of existing holdings increased
MAX_BUY_MORE = 5


# Minimum conviction thresholds

MIN_NEW_BUY_SCORE = 85

MIN_BUY_MORE_SCORE = 80


# Minimum size for a trade to appear
MIN_ALLOCATION_AMOUNT = 1



# ==========================================
# PORTFOLIO RISK
# ==========================================

MAX_POSITION_PERCENT = 15



TARGET_SECTOR_ALLOCATIONS = {

    "Technology": 40,

    "Healthcare": 15,

    "Financial Services": 15,

    "Industrials": 10,

    "Consumer Defensive": 10,

    "Real Estate": 5,

    "Energy": 5

}