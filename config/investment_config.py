"""
Portfolio Manager Configuration
"""

# ==========================================
# CASH CONTRIBUTIONS
# ==========================================



MIN_TRADE_VALUE = 5

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
# CAPITAL ALLOCATION
# ==========================================

# Maximum new investment added each cycle
# Used by capital allocator
DISCRETIONARY_SPEND_LIMIT = 15

# Legacy compatibility
AVAILABLE_CASH = DISCRETIONARY_SPEND_LIMIT

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