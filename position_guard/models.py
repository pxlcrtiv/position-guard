"""Position models: raw reserve amounts parsed from subgraph payloads, and
normalized USD positions ready for health-factor math."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssetPosition:
    """One reserve leg of a position (collateral or debt)."""

    symbol: str
    amount: float  # token units (18-decimals-normalized by the client)
    usd_value: float
    is_collateral: bool
    # Aave v3: liquidation threshold (0..1); Compound v3: borrow collateralization (0..1)
    weight: float | None = None


@dataclass
class Position:
    address: str
    protocol: str
    collateral: list[AssetPosition] = field(default_factory=list)
    debt: list[AssetPosition] = field(default_factory=list)
    source: str = "live"  # "live" | "fixture"
    fetched_at: float | None = None

    @property
    def collateral_usd(self) -> float:
        return sum(a.usd_value for a in self.collateral)

    @property
    def debt_usd(self) -> float:
        return sum(a.usd_value for a in self.debt)

    @property
    def dominant_symbol(self) -> str:
        """Symbol of the largest (by USD) collateral leg — used by alert text."""
        if not self.collateral:
            return "your position"
        return max(self.collateral, key=lambda a: a.usd_value).symbol

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "protocol": self.protocol,
            "source": self.source,
            "collateral_usd": self.collateral_usd,
            "debt_usd": self.debt_usd,
            "collateral": [a.__dict__ for a in self.collateral],
            "debt": [a.__dict__ for a in self.debt],
        }