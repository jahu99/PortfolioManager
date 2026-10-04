"""
Structural risk assessment for portfolio allocation.

Purpose
-------
Provide a deterministic, auditable security-level structural-risk
assessment for portfolio allocation sizing.

This module:
- does NOT change BUY NEW / BUY MORE decisions
- does NOT change Investment Score
- does NOT consume news sentiment or analyst opinion
- does NOT create trade eligibility
- only supplies an allocation multiplier and explanation

The assessment is based only on factual security metadata supplied
by the caller.
"""

US_EXCHANGES = {
    "NMS",
    "NYQ",
    "NGM",
    "NCM",
    "NAS",
    "ASE",
    "BTS",
    "PCX",
    "OEM",
    "OQB",
    "OQX",
    "PNK",
    "YHD",
}

HIGH_JURISDICTION_RISK_COUNTRIES = {
    "CHINA",
}

ADR_INDICATORS = {
    "ADR",
    "AMERICAN DEPOSITARY",
    "AMERICAN DEPOSITARY RECEIPT",
}


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip().upper()


def assess_structural_risk(metadata):
    """
    Return deterministic structural-risk metadata.

    Returns
    -------
    dict
        {
            "Structural Risk": "LOW|MODERATE|HIGH",
            "Structural Risk Multiplier": float,
            "Structural Risk Reason": str
        }
    """

    if not isinstance(metadata, dict):
        metadata = {}

    country = _clean_text(
        metadata.get("Country")
        or metadata.get("country")
    )

    exchange = _clean_text(
        metadata.get("Exchange")
        or metadata.get("exchange")
    )

    quote_type = _clean_text(
        metadata.get("Quote Type")
        or metadata.get("quoteType")
    )

    name = _clean_text(
        metadata.get("Name")
        or metadata.get("name")
    )

    # ------------------------------------------------------------
    # HIGH: explicit ADR/security-structure evidence
    # ------------------------------------------------------------

    if (
        quote_type == "ADR"
        or any(
            indicator in name
            for indicator in ADR_INDICATORS
        )
    ):
        return {
            "Structural Risk": "HIGH",
            "Structural Risk Multiplier": 0.70,
            "Structural Risk Reason": (
                "ADR/security structure introduces additional "
                "cross-border structural risk"
            ),
        }

    # ------------------------------------------------------------
    # HIGH: China-based issuer
    #
    # This is deliberately jurisdiction-based, not ticker-based.
    # ------------------------------------------------------------

    if country in HIGH_JURISDICTION_RISK_COUNTRIES:
        return {
            "Structural Risk": "HIGH",
            "Structural Risk Multiplier": 0.70,
            "Structural Risk Reason": (
                "Issuer jurisdiction is classified as elevated "
                "structural-risk jurisdiction"
            ),
        }

    # ------------------------------------------------------------
    # MODERATE: non-US issuer listed on a US exchange
    # ------------------------------------------------------------

    if (
        country
        and country != "UNITED STATES"
        and exchange in US_EXCHANGES
    ):
        return {
            "Structural Risk": "MODERATE",
            "Structural Risk Multiplier": 0.85,
            "Structural Risk Reason": (
                "Foreign issuer listed on a US exchange creates "
                "additional cross-border structural risk"
            ),
        }

    # ------------------------------------------------------------
    # LOW / unavailable
    #
    # Missing metadata must not create an artificial penalty.
    # ------------------------------------------------------------

    return {
        "Structural Risk": "LOW",
        "Structural Risk Multiplier": 1.00,
        "Structural Risk Reason": (
            "No elevated structural risk identified from "
            "available security metadata"
        ),
    }

