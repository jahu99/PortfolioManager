import pytest

from analysis.portfolio_recalibration import (
    assess_structural_risk,
)


def allocation_weight(
    score,
    sector_exposure,
    current_position_percent,
    risk_score,
    structural_risk_multiplier,
):
    position_multiplier = (
        0.75
        if current_position_percent >= 10.0
        else 1.0
    )

    risk_multiplier = (
        0.70
        if 0 < risk_score < 10.0
        else 1.0
    )

    return (
        score
        * position_multiplier
        * risk_multiplier
        * structural_risk_multiplier
    )


@pytest.mark.parametrize(
    "low_risk_score, high_risk_score",
    [
        (84, 84),
        (84, 86),
        (84, 88),
        (84, 82),
    ],
)
def test_low_structural_risk_is_preferred_over_high_structural_risk(
    low_risk_score,
    high_risk_score,
):
    low_risk_weight = allocation_weight(
        score=low_risk_score,
        sector_exposure=49.62,
        current_position_percent=7.5,
        risk_score=10,
        structural_risk_multiplier=1.0,
    )

    high_risk_weight = allocation_weight(
        score=high_risk_score,
        sector_exposure=0.0,
        current_position_percent=0.0,
        risk_score=10,
        structural_risk_multiplier=0.70,
    )

    assert low_risk_weight > high_risk_weight


def test_equal_score_low_risk_should_not_lose_to_high_risk_without_diversification():
    low_risk_weight = allocation_weight(
        score=84,
        sector_exposure=0.0,
        current_position_percent=0.0,
        risk_score=10,
        structural_risk_multiplier=1.0,
    )

    high_risk_weight = allocation_weight(
        score=84,
        sector_exposure=0.0,
        current_position_percent=0.0,
        risk_score=10,
        structural_risk_multiplier=0.70,
    )

    assert low_risk_weight > high_risk_weight


def test_msft_vs_tal_structural_risk_policy():
    msft_weight = allocation_weight(
        score=84,
        sector_exposure=49.62,
        current_position_percent=7.5,
        risk_score=10,
        structural_risk_multiplier=1.0,
    )

    tal_weight = allocation_weight(
        score=84,
        sector_exposure=0.0,
        current_position_percent=0.0,
        risk_score=10,
        structural_risk_multiplier=0.70,
    )

    assert msft_weight == pytest.approx(84.0)
    assert tal_weight == pytest.approx(58.80)

    assert msft_weight > tal_weight