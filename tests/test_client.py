"""Subgraph client: live path (mocked transport), offline fallback path,
parsing into Position, source labeling."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from position_guard.client import AaveV3Client, CompoundV3Client, PriceClient

FIXTURES = Path(__file__).parent / "fixtures"
ETH_USD = 3400.0


def test_aave_client_live_path_with_mock_transport(aave_demo_payload):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "query Position" in body["query"]
        assert body["variables"]["id"] == "0xd3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3"
        return httpx.Response(200, json=aave_demo_payload)

    client = AaveV3Client(
        endpoint="https://example.test/graphql",
        transport=httpx.MockTransport(handler),
    )
    pos = client.query_position("0xD3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3", ETH_USD)
    assert client.using_live is True
    assert pos.source == "live"
    assert pos.protocol == "aave-v3"
    assert pos.collateral[0].symbol == "ETH"
    assert pos.collateral[0].amount == pytest.approx(2.5)
    assert pos.collateral[0].weight == pytest.approx(0.825)
    assert pos.debt[0].usd_value == pytest.approx(6250.0, rel=1e-6)


def test_aave_client_falls_back_to_fixture_when_offline():
    client = AaveV3Client(endpoint="http://127.0.0.1:1", fixture=FIXTURES / "aave_v3_demo.json", timeout=0.5)
    pos = client.query_position("0x" + "d3" * 20, ETH_USD)
    assert client.using_live is False
    assert pos.source == "fixture"
    assert pos.collateral_usd == pytest.approx(8500.0, rel=1e-9)


def test_subgraph_error_triggers_fixture_fallback():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "subgraph not found"}]})

    client = AaveV3Client(endpoint="https://example.test/graphql", transport=httpx.MockTransport(handler))
    pos = client.query_position("0x" + "d3" * 20, ETH_USD)
    assert client.using_live is False
    assert pos.source == "fixture"


def test_compound_client_parses_amounts_and_bcp(compound_payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=compound_payload)

    client = CompoundV3Client(endpoint="https://example.test/graphql", transport=httpx.MockTransport(handler))
    pos = client.query_position("0x" + "d3" * 20)
    assert client.using_live is True
    assert pos.collateral[0].symbol == "ETH"
    assert pos.collateral[0].amount == pytest.approx(3.0)
    assert pos.collateral[0].weight == pytest.approx(0.80)
    assert pos.debt[0].usd_value == pytest.approx(6000.0)
    assert CompoundV3Client._borrow_col_pct("WBTC") == pytest.approx(0.70)


def test_price_client_live_and_fallback():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "ethereum" in request.url.params["ids"]
        return httpx.Response(200, json={"ethereum": {"usd": 3400.0}, "usd-coin": {"usd": 1.0}})

    prices = PriceClient(
        fallback=FIXTURES / "coingecko_prices_demo.json",
        transport=httpx.MockTransport(handler),
    )
    got = prices.usd_prices(["ETH", "USDC", "NOTAGOING"])
    assert got["ETH"] == pytest.approx(3400.0)
    assert got["USDC"] == pytest.approx(1.0)
    assert prices.using_live is True
    # unmapped symbols are skipped, not fatal
    assert "NOTAGOING" not in got


def test_price_client_fallback_when_offline():
    prices = PriceClient(
        fallback=FIXTURES / "coingecko_prices_demo.json",
        timeout=0.5,
        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused"))),
    )
    got = prices.usd_prices(["ETH"])
    assert got["ETH"] == pytest.approx(3400.0)
    assert prices.using_live is False