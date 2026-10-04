from analysis.structural_risk import assess_structural_risk


def test_us_stock():
    result = assess_structural_risk({
        "Country": "United States",
        "Exchange": "NMS",
        "Quote Type": "EQUITY",
        "Name": "Example Corp",
    })

    assert result["Structural Risk"] == "LOW"
    assert result["Structural Risk Multiplier"] == 1.00


def test_foreign_us_listing():
    result = assess_structural_risk({
        "Country": "Canada",
        "Exchange": "NYQ",
        "Quote Type": "EQUITY",
        "Name": "Example Corp",
    })

    assert result["Structural Risk"] == "MODERATE"
    assert result["Structural Risk Multiplier"] == 0.85


def test_china_issuer():
    result = assess_structural_risk({
        "Country": "China",
        "Exchange": "NYQ",
        "Quote Type": "EQUITY",
        "Name": "Example Education Corp",
    })

    assert result["Structural Risk"] == "HIGH"
    assert result["Structural Risk Multiplier"] == 0.70


def test_adr():
    result = assess_structural_risk({
        "Country": "Canada",
        "Exchange": "NYQ",
        "Quote Type": "ADR",
        "Name": "Example Corp",
    })

    assert result["Structural Risk"] == "HIGH"
    assert result["Structural Risk Multiplier"] == 0.70


def test_missing_metadata_is_neutral():
    result = assess_structural_risk({})

    assert result["Structural Risk"] == "LOW"
    assert result["Structural Risk Multiplier"] == 1.00


if __name__ == "__main__":
    test_us_stock()
    test_foreign_us_listing()
    test_china_issuer()
    test_adr()
    test_missing_metadata_is_neutral()
    print("STRUCTURAL RISK TESTS PASSED")

