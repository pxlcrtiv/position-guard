"""Health-factor math for Aave v3 and Compound v3, tested against golden
fixtures in tests/test_health.py.

Aave v3 (simplified, per protocol docs):
    HF = Σ(collateral_usd_i × liquidation_threshold_i) / Σ(debt_usd_j)
    Liquidatable when HF < 1.0. A position is liquidated up to the point
    where HF returns to 1.0.

Compound v3 (Comet, simplified):
    Each collateral asset has a borrow collateralization percent (bcp).
    HF = Σ(collateral_usd_i × bcp_i) / base_borrow_usd
    Liquidatable when HF < 1.0.

Margin left is the dollar distance to liquidation:
    margin = Σ(collateral_usd_i × weight_i) − Σ(debt_usd_j)
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from .models import AssetPosition, Position


def _weighted_collateral(legs: Iterable[AssetPosition], default_weight: float = 1.0) -> float:
    total = 0.0
    for leg in legs:
        weight = leg.weight if leg.weight is not None else default_weight
        total += leg.usd_value * weight
    return total


def health_factor_ratio(weighted_collateral_usd: float, debt_usd: float) -> float | None:
    """HF = weighted collateral / debt. None when there is no debt (no risk of
    liquidation — callers render it as ∞); 0.0 when debt exists with no
    weighted collateral."""
    if debt_usd <= 0:
        return None
    if weighted_collateral_usd <= 0:
        return 0.0
    return weighted_collateral_usd / debt_usd


def aave_v3_health_factor(position: Position) -> float | None:
    """Aave v3 health factor. Each collateral leg's weight is its reserve's
    liquidation threshold (0..1)."""
    weighted = _weighted_collateral(position.collateral, default_weight=1.0)
    return health_factor_ratio(weighted, position.debt_usd)


def compound_v3_health_factor(position: Position) -> float | None:
    """Compound v3 health factor. Each collateral leg's weight is its asset's
    borrow collateralization percent (0..1, e.g. 0.80 for ETH on USDC comet
    mainnet)."""
    weighted = _weighted_collateral(position.collateral, default_weight=0.80)
    return health_factor_ratio(weighted, position.debt_usd)


def margin_left_usd(position: Position) -> float:
    """Dollars of room before the position becomes liquidatable (HF = 1.0)."""
    weighted = 0.0
    for leg in position.collateral:
        weight = leg.weight if leg.weight is not None else 1.0
        weighted += leg.usd_value * weight
    return weighted - position.debt_usd


def liquidation_price(
    position: Position,
    target_symbol: str,
    target_amount: float,
) -> float | None:
    """USD price of `target_symbol` at which the position crosses HF = 1.0,
    holding every other leg at its current value.

    Liquid price for asset x with liquidation threshold t_x:
        P_x = [Σ_debt − Σ_{other collateral}(usd_i × t_i)] / (amount_x × t_x)
    """
    if target_amount <= 0:
        return None
    other_weighted = 0.0
    target_weight: float | None = None
    for leg in position.collateral:
        if leg.symbol == target_symbol:
            target_weight = leg.weight
        else:
            w = leg.weight if leg.weight is not None else 1.0
            other_weighted += leg.usd_value * w
    if target_weight is None or target_weight <= 0:
        return None
    numerator = position.debt_usd - other_weighted
    if numerator <= 0:
        return None  # other collateral alone covers the debt — never liquidated by this leg
    return numerator / (target_amount * target_weight)


def _fmt_hf(hf: float | None) -> str:
    if hf is None:
        return "∞"
    if math.isinf(hf):
        return "∞"
    return f"{hf:.4f}"