"""Shared test fixtures — every test runs fully offline."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def aave_demo_payload() -> dict:
    import json

    return json.loads((FIXTURES / "aave_v3_demo.json").read_text(encoding="utf-8"))


@pytest.fixture
def aave_multi_payload() -> dict:
    import json

    return json.loads((FIXTURES / "aave_v3_multi.json").read_text(encoding="utf-8"))


@pytest.fixture
def compound_payload() -> dict:
    import json

    return json.loads((FIXTURES / "compound_v3_demo.json").read_text(encoding="utf-8"))


@pytest.fixture
def tmp_db(tmp_path) -> str:
    return str(tmp_path / "test.db")