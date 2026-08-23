"""State machine: thresholds, boundaries, transitions."""

from __future__ import annotations

import pytest

from position_guard.state import (
    DEFAULT_THRESHOLDS,
    Level,
    classify,
    is_downgrade,
    is_upgrade,
)


@pytest.mark.parametrize(
    ("hf", "expected"),
    [
        (0.0, Level.LIQUIDATION),
        (0.87, Level.LIQUIDATION),
        (1.0, Level.LIQUIDATION),
        (1.001, Level.CRITICAL),
        (1.12, Level.CRITICAL),
        (1.15, Level.CRITICAL),  # boundary inclusive
        (1.1501, Level.WARNING),
        (1.29, Level.WARNING),
        (1.30, Level.WARNING),
        (1.3001, Level.WATCH),
        (1.5, Level.WATCH),
        (1.5001, Level.HEALTHY),
        (2.4, Level.HEALTHY),
        (None, Level.HEALTHY),  # no debt
    ],
)
def test_classify_boundaries(hf, expected):
    assert classify(hf, DEFAULT_THRESHOLDS) == expected


def test_downgrade_transitions():
    assert is_downgrade(Level.HEALTHY, Level.WATCH) is True
    assert is_downgrade(Level.WATCH, Level.WARNING) is True
    assert is_downgrade(Level.WARNING, Level.CRITICAL) is True
    assert is_downgrade(Level.CRITICAL, Level.LIQUIDATION) is True
    # same state is not a downgrade
    assert is_downgrade(Level.CRITICAL, Level.CRITICAL) is False
    # improving is not a downgrade
    assert is_downgrade(Level.CRITICAL, Level.WARNING) is False


def test_first_sighting_policy():
    # first observation of a risk state counts as alert-worthy…
    assert is_downgrade(None, Level.CRITICAL) is True
    assert is_downgrade(None, Level.WATCH) is True
    # …but a first healthy observation stays silent
    assert is_downgrade(None, Level.HEALTHY) is False


def test_upgrade_transitions():
    assert is_upgrade(Level.CRITICAL, Level.HEALTHY) is True
    assert is_upgrade(Level.CRITICAL, Level.CRITICAL) is False
    assert is_upgrade(None, Level.HEALTHY) is False