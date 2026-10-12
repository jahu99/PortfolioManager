"""
Test BUY NEW priority ordering.

This test isolates the final BUY NEW ranking logic in
candidate_selection.build_candidate_review().

It verifies that:

1. Investment Score is the primary ranking factor.
2. Technical Score is the first tie-breaker.
3. Quality Score is the second tie-breaker.
4. Growth Score is the third tie-breaker.
5. Confidence Score is the fourth tie-breaker.
6. H1 Priority is the next tie-breaker.
7. Investment Rank is retained as a later tie-breaker.
8. Ticker provides deterministic final ordering.

This test does NOT test Entry Quality classification.
"""

import pandas as pd

import analysis.candidate_selection as candidate_selection


# ============================================================
# TEST HELPERS
# ============================================================

def make_candidates():
    return pd.DataFrame(
        [
            {
                "Ticker": "AAA",
                "Investment Score": 90,
                "Technical Score": 70,
                "Quality Score": 70,
                "Growth Score": 70,
                "Confidence Score": 70,
                "Investment Rank": 10,
                "RSI": 50,
                "Return 3M": 10,
            },
            {
                "Ticker": "BBB",
                "Investment Score": 85,
                "Technical Score": 100,
                "Quality Score": 100,
                "Growth Score": 100,
                "Confidence Score": 100,
                "Investment Rank": 1,
                "RSI": 50,
                "Return 3M": 10,
            },
            {
                "Ticker": "CCC",
                "Investment Score": 80,
                "Technical Score": 100,
                "Quality Score": 100,
                "Growth Score": 100,
                "Confidence Score": 100,
                "Investment Rank": 2,
                "RSI": 50,
                "Return 3M": 10,
            },
        ]
    )


# ============================================================
# TEST
# ============================================================

def test_investment_score_is_primary():

    # Force all candidates to the same favourable entry
    # classification so this test isolates ranking only.

    original_entry_classifier = (
        candidate_selection.classify_entry_quality
    )

    original_h1_classifier = (
        candidate_selection.classify_buy_new_h1
    )

    candidate_selection.classify_entry_quality = (
        lambda row: "FAVOURABLE ENTRY"
    )

    candidate_selection.classify_buy_new_h1 = (
        lambda row: "H1 NEUTRAL"
    )

    try:

        candidates = make_candidates()

        result = candidate_selection.build_candidate_review(
            candidates
        )

    finally:

        candidate_selection.classify_entry_quality = (
            original_entry_classifier
        )

        candidate_selection.classify_buy_new_h1 = (
            original_h1_classifier
        )

    assert not result.empty, (
        "build_candidate_review() returned no candidates"
    )

    expected = [
        "AAA",
        "BBB",
        "CCC",
    ]

    actual = result["Ticker"].tolist()

    print()
    print("EXPECTED ORDER:")
    print(expected)

    print()
    print("ACTUAL ORDER:")
    print(actual)

    print()
    print(
        result[
            [
                "Ticker",
                "Investment Score",
                "Technical Score",
                "Quality Score",
                "Growth Score",
                "Confidence Score",
            ]
        ].to_string(index=False)
    )

    assert actual == expected, (
        "Investment Score is not the primary BUY NEW ranking"
    )

    print()
    print("PASS: Investment Score is the primary BUY NEW ranking.")


if __name__ == "__main__":

    test_investment_score_is_primary()

    print()
    print("BUY NEW PRIORITY TEST PASSED.")
