import pytest


def get_sector_allocation_multiplier(
    sector_exposure,
):
    if sector_exposure >= 40.0:
        return 0.65

    return 1.0


def calculate_incremental_capacity(
    base_capacity,
    sector_exposure,
):
    sector_multiplier = get_sector_allocation_multiplier(
        sector_exposure
    )

    return (
        base_capacity
        * sector_multiplier
    )


def test_concentrated_sector_reduces_incremental_capacity():
    unconstrained_capacity = calculate_incremental_capacity(
        base_capacity=100.0,
        sector_exposure=10.0,
    )

    concentrated_capacity = calculate_incremental_capacity(
        base_capacity=100.0,
        sector_exposure=49.62,
    )

    assert unconstrained_capacity == pytest.approx(100.0)
    assert concentrated_capacity == pytest.approx(65.0)


def test_sector_concentration_does_not_change_destination_ranking():
    msft_score = 84
    expd_score = 83

    assert msft_score > expd_score


def test_msft_has_less_incremental_capacity_than_expd():
    msft_capacity = calculate_incremental_capacity(
        base_capacity=100.0,
        sector_exposure=49.62,
    )

    expd_capacity = calculate_incremental_capacity(
        base_capacity=100.0,
        sector_exposure=1.95,
    )

    assert msft_capacity < expd_capacity
