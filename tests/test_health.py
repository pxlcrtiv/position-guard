"""Golden health-factor math tests — hand-computed expectations.

Aave v3 demo  : HF = (2.5 ETH × $3,400 × 0.825) / $6,250 USDC        = 1.122
Aave v3 multi : HF = (ETH 2805 + WBTC 4880) / (3000 + 2000)          = 1.537
Compound v3   : HF = (3.0 ETH × $3,400 × 0.80) / $6,000              = 1.36
"""

from __future__ import annotations

from position_guard.client import AaveV3Client
from position_guard.health import (
    aave_v3_health_factor,
    compound_v3_health_factor,
    liquidation_price,
    margin_left_usd,
)
from position_guard.models import AssetPosition, Position

ETH_USD = 3400.0


def _aave_position_from(payload: dict, address: str = "0x" + "d3" * 20) -> Position:
    return AaveV3Client(endpoint="http://127.0.0.1:1")._parse(payload["data"], address, ETH_USD)


def _compound_position_from(payload: dict, address: str = "0x" + "d3" * 20) -> Position:
    account = payload["data"]["account"]
    collateral = [
        AssetPosition(
            c["asset"]["symbol"],
            float(c["amount"]),
            float(c["amount"]) * float(c["asset"]["price"]["priceUsd"]),
            True,
            0.80,
        )
        for c in account["collateral"]
    ]
    return Position(address, "compound-v3", collateral, [AssetPosition("USDC", 6000, 6000, False)])


def test_aave_v3_health_factor_golden(aave_demo_payload):
    pos = _aave_position_from(aave_demo_payload)
    assert pos.collateral_usd == pytest.approx(8500.0, rel=1e-9)
    assert pos.debt_usd == pytest.approx(6250.0, rel=1e-6)
    assert aave_v3_health_factor(pos) == pytest.approx(7012.5 / 6250.0, rel=1e-9)
    assert margin_left_usd(pos) == pytest.approx(762.5, rel=1e-9)


import pytest


def test_aave_v3_health_factor_multi_asset_golden(aave_multi_payload):
    pos = _aave_position_from(aave_multi_payload)
    # ETH 1.0 × 3400 × 0.825 = 2805 ; WBTC 0.1 × 61000 × 0.80 = 4880
    assert aave_v3_health_factor(pos) == pytest.approx(7685.0 / 5000.0, rel=1e-9)
    assert margin_left_usd(pos) == pytest.approx(2685.0, rel=1e-9)


def test_compound_v3_health_factor_golden(compound_payload):
    pos = _compound_position_from(compound_payload)
    assert compound_v3_health_factor(pos) == pytest.approx(1.36, rel=1e-9)
    assert margin_left_usd(pos) == pytest.approx(8160.0 - 6000.0, rel=1e-9)


def test_no_debt_means_infinite_hf():
    pos = Position("0x1", "aave-v3", [AssetPosition("ETH", 1, 3400, True, 0.825)], [])
    assert aave_v3_health_factor(pos) is None  # rendered as ∞
    assert margin_left_usd(pos) == pytest.approx(2805.0)


def test_debt_with_zero_weighted_collateral_is_zero():
    pos = Position("0x1", "aave-v3", [], [AssetPosition("USDC", 500, 500, False)])
    assert aave_v3_health_factor(pos) == 0.0


def test_liquidation_price_golden(aave_multi_payload):
    """ETH price (holding WBTC + debt fixed) at which HF crosses 1.0:
    (5000 − 4880) / (1.0 × 0.825) = $145.45."""
    pos = _aave_position_from(aave_multi_payload)
    assert liquidation_price(pos, "ETH", 1.0) == pytest.approx(120.0 / 0.825, rel=1e-9)
    # WBTC leg: (5000 − 2805) / (0.1 × 0.80) = $27,437.50
    assert liquidation_price(pos, "WBTC", 0.1) == pytest.approx(2195.0 / 0.08, rel=1e-9)


def test_liquidation_price_none_when_covered_by_other_collateral():
    pos = Position(
        "0x1",
        "aave-v3",
        [AssetPosition("ETH", 1, 3400, True, 0.825), AssetPosition("WBTC", 2, 122000, True, 0.80)],
        [AssetPosition("USDC", 1000, 1000, False)],
    )
    assert liquidation_price(pos, "ETH", 1.0) is None  # WBTC alone already covers the debt