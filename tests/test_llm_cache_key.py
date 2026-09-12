from agents.ai_portfolio_reviewer import _get_cache_key


def build_prompt(
    *,
    price=100.00,
    rsi=55.0,
    investment_score=78.0,
    signal="BUY",
    proposed_action="HOLD",
    evidence_score=70.0,
    collected_at="2026-09-08T09:00:00+00:00",
):
    return f"""
Ticker: TEST

ACTION: {proposed_action}

{{
    "ticker": "TEST",
    "proposed_action": "{proposed_action}",
    "investment_score": {investment_score},
    "technical_score": 80.0,
    "quality_score": 75.0,
    "growth_score": 82.0,
    "signal": "{signal}",
    "current_price": {price},
    "rsi": {rsi},
    "evidence_score": {evidence_score},
    "market_intelligence": {{
        "Ticker": "TEST",
        "Current Price": {price},
        "Collected At": "{collected_at}"
    }}
}}
"""


print("\nTEST 1: Intraday price movement")

prompt_1 = build_prompt(
    price=100.00,
    rsi=55.0,
    collected_at="2026-09-08T09:00:00+00:00",
)

prompt_2 = build_prompt(
    price=102.50,
    rsi=61.0,
    collected_at="2026-09-08T14:00:00+00:00",
)

key_1 = _get_cache_key(prompt_1)
key_2 = _get_cache_key(prompt_2)

print(f"PROMPT 1 KEY: {key_1}")
print(f"PROMPT 2 KEY: {key_2}")

assert key_1 == key_2

print(
    "PASS: Intraday price, RSI and collection timestamp "
    "do NOT change the cache key."
)


print("\nTEST 2: Signal change")

prompt_3 = build_prompt(
    price=102.50,
    rsi=61.0,
    signal="SELL",
)

key_3 = _get_cache_key(prompt_3)

print(f"PROMPT 3 KEY: {key_3}")

assert key_3 != key_1

print(
    "PASS: Material signal change DOES change the cache key."
)


print("\nTEST 3: Proposed action change")

prompt_4 = build_prompt(
    proposed_action="REDUCE 25%",
)

key_4 = _get_cache_key(prompt_4)

print(f"PROMPT 4 KEY: {key_4}")

assert key_4 != key_1

print(
    "PASS: Proposed action change DOES change the cache key."
)


print("\nTEST 4: Score movement within same bucket")

prompt_5 = build_prompt(
    investment_score=79.0,
)

key_5 = _get_cache_key(prompt_5)

print(f"PROMPT 5 KEY: {key_5}")

assert key_5 == key_1

print(
    "PASS: Score movement within the same bucket "
    "does NOT change the cache key."
)


print("\nTEST 5: Score crosses decision bucket")

prompt_6 = build_prompt(
    investment_score=86.0,
)

key_6 = _get_cache_key(prompt_6)

print(f"PROMPT 6 KEY: {key_6}")

assert key_6 != key_1

print(
    "PASS: Material score bucket change "
    "DOES change the cache key."
)


print("\nALL LLM CACHE KEY TESTS PASSED")