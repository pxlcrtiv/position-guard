"""Thresholds + state machine.

Classifies a health factor into one of five states and decides when a
position-change is worth alerting about (downgrades notify; upgrades notify
as recoveries so watchers don't nag on every tick).

Defaults encode the "1.12 HF ~= act now" intuition:
    HF ≤ 1.00        LIQUIDATION — liquidatable right now
    1.00 < HF ≤ 1.15 CRITICAL   — thin margin, act today
    1.15 < HF ≤ 1.30 WARNING    — margin shrinking, plan the top-up
    1.30 < HF ≤ 1.50 WATCH      — monitor, no action yet
    HF >  1.50       HEALTHY
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Level(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"
    LIQUIDATION = "liquidation"


# Order from worst to best — used for transition comparison.
_RANK = {
    Level.LIQUIDATION: 0,
    Level.CRITICAL: 1,
    Level.WARNING: 2,
    Level.WATCH: 3,
    Level.HEALTHY: 4,
}


@dataclass(frozen=True)
class Thresholds:
    critical_max: float = 1.15
    warning_max: float = 1.30
    watch_max: float = 1.50


DEFAULT_THRESHOLDS = Thresholds()


def classify(hf: float | None, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> Level:
    """Map a health factor (None = no debt) to a Level."""
    if hf is None:
        return Level.HEALTHY
    if hf <= 1.0:
        return Level.LIQUIDATION
    if hf <= thresholds.critical_max:
        return Level.CRITICAL
    if hf <= thresholds.warning_max:
        return Level.WARNING
    if hf <= thresholds.watch_max:
        return Level.WATCH
    return Level.HEALTHY


def is_downgrade(previous: Level | None, current: Level) -> bool:
    """True when the position got riskier (or is first seen in a risk state).
    A None previous state (first observation) counts as a downgrade unless the
    position is healthy, so watchers fire on the very first check too."""
    if previous is None:
        return current != Level.HEALTHY
    return _RANK[current] < _RANK[previous]


def is_upgrade(previous: Level | None, current: Level) -> bool:
    if previous is None:
        return False
    return _RANK[current] > _RANK[previous]


def transition_label(current: Level) -> str:
    return {
        Level.LIQUIDATION: "liquidation window",
        Level.CRITICAL: "critical",
        Level.WARNING: "warning",
        Level.WATCH: "watch",
        Level.HEALTHY: "healthy",
    }[current]