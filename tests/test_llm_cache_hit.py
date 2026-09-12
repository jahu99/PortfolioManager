import os
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from agents.ai_portfolio_reviewer import (
    _get_cache_key,
    _load_llm_cache,
    _save_llm_cache,
    call_llm,
)


PROMPT = """
Test portfolio decision.

Ticker: TEST
Investment Score: 85
Collected At: 2026-09-08T10:00:00
"""


FAKE_RESPONSE = {
    "action": "HOLD",
    "confidence": 80,
    "reason": "Test response loaded from cache."
}


def main():

    print("TESTING LLM CACHE HIT")
    print()

    cache_key = _get_cache_key(
        PROMPT
    )

    print(
        f"Cache key: {cache_key}"
    )

    cache = _load_llm_cache()

    cache[cache_key] = {
        "provider": "gemini",
        "model": "gemini-3.6-flash",
        "response": FAKE_RESPONSE,
    }

    _save_llm_cache(
        cache
    )

    print()
    print(
        "Fake response written to cache."
    )
    print()

    result = call_llm(
        PROMPT
    )

    print()
    print(
        "Returned result:"
    )
    print(
        result
    )

    if result == FAKE_RESPONSE:

        print()
        print(
            "PASS: Cached response returned successfully."
        )
        print(
            "No Gemini API call should have been made."
        )

    else:

        print()
        print(
            "FAIL: Returned response does not match cached response."
        )


if __name__ == "__main__":
    main()
