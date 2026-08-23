"""Subgraph + price clients.

Primary sources (free, no key):
  - The Graph hosted service:  https://api.thegraph.com/subgraphs/name/aave/protocol-v3
                               https://api.thegraph.com/subgraphs/name/mason/compound-v3
  - CoinGecko:                 https://api.coingecko.com/api/v3/simple/price

Every network path degrades to a bundled offline fixture, so the tool (and its
demo) works with zero keys and zero network.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from .models import AssetPosition, Position

log = logging.getLogger("position_guard.client")

FIXTURE_DIR = Path(__file__).parent / "fixtures"

# The Graph hosted-service endpoints (free tier, no key). Both are the public
# subgraphs used by Aave v3 and Compound v3 dashboards.
AAVE_V3_ENDPOINT = "https://api.thegraph.com/subgraphs/name/aave/protocol-v3"
COMPOUND_V3_ENDPOINT = "https://api.thegraph.com/subgraphs/name/mason/compound-v3"

COINGECKO_ENDPOINT = "https://api.coingecko.com/api/v3/simple/price"


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("offline mode — network disabled")


# Transport that refuses every connection instantly: used to force every data
# source onto its bundled fixture (deterministic offline demos/tests).
OFFLINE_TRANSPORT = httpx.MockTransport(_refuse)


def _log_fallback(exc: Exception, silent: bool) -> None:
    if silent:
        log.info("subgraph unreachable (%s) — using bundled fixture", exc)
    else:
        log.warning("live subgraph query failed (%s) — using bundled fixture", exc)

_AAVE_V3_QUERY = """
query Position($id: String!) {
  user(id: $id) {
    id
    userReserves {
      usageAsCollateralEnabled
      currentATokenBalance
      currentVariableDebt
      currentStableDebt
      reserve {
        symbol
        decimals
        liquidationThreshold
        price {
          priceInEth
        }
      }
    }
  }
}
"""

_COMPOUND_V3_QUERY = """
query Position($id: String!) {
  account(id: $id) {
    id
    baseBorrowed
    baseSupply
    health {
      liquidationThreshold
    }
    collateral {
      asset {
        symbol
        price {
          priceUsd
        }
      }
      amount
    }
  }
}
"""

# Rough conversion symbols -> CoinGecko ids for the free price API.
SYMBOL_TO_CG_ID = {
    "ETH": "ethereum",
    "WETH": "ethereum",
    "wstETH": "ethereum",
    "WBTC": "wrapped-bitcoin",
    "cbBTC": "bitcoin",
    "USDC": "usd-coin",
    "USDT": "tether",
    "DAI": "dai",
    "LINK": "chainlink",
    "AAVE": "aave",
    "UNI": "uniswap",
    "LDO": "lido-dao",
}


class SourceError(RuntimeError):
    """Raised when both the live source and its fixture are unavailable."""


class SubgraphClient:
    """Minimal GraphQL client for Aave v3 / Compound v3 subgraphs.

    Attributes:
        using_live: True when the last successful query came from the network.
    """

    def __init__(
        self,
        endpoint: str,
        fixture: Path | str,
        timeout: float = 8.0,
        transport: httpx.BaseTransport | None = None,
        silent_fallback: bool = False,
    ) -> None:
        self.endpoint = endpoint
        self.fixture = Path(fixture)
        self.timeout = timeout
        self._transport = transport
        self.silent_fallback = silent_fallback
        self.using_live = False

    def _post(self, query: str, variables: dict) -> dict:
        client_kwargs: dict = {"timeout": self.timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        with httpx.Client(**client_kwargs) as client:
            resp = client.post(
                self.endpoint,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                raise SourceError(f"subgraph error: {data['errors']}")
            return data


class AaveV3Client(SubgraphClient):
    def __init__(
        self,
        fixture: Path | str | None = None,
        *,
        endpoint: str | None = None,
        timeout: float = 8.0,
        transport: httpx.BaseTransport | None = None,
        silent_fallback: bool = False,
    ) -> None:
        super().__init__(
            endpoint or AAVE_V3_ENDPOINT,
            fixture=fixture or FIXTURE_DIR / "aave_v3_demo.json",
            timeout=timeout,
            transport=transport,
            silent_fallback=silent_fallback,
        )

    def raw_query(self, address: str) -> dict:
        try:
            data = self._post(_AAVE_V3_QUERY, {"id": address.lower()})
            self.using_live = True
            return data
        except (httpx.HTTPError, SourceError, ValueError) as exc:
            _log_fallback(exc, self.silent_fallback)
            self.using_live = False
            return json.loads(self.fixture.read_text(encoding="utf-8"))

    def query_position(self, address: str, eth_usd: float) -> Position:
        parse = lambda data, addr: self._parse(data, addr, eth_usd)
        data = self.raw_query(address)
        try:
            pos = parse(data["data"], address)
        except (KeyError, TypeError) as exc:
            raise SourceError(f"malformed subgraph payload: {exc}") from exc
        pos.source = "live" if self.using_live else "fixture"
        return pos

    def _parse(self, data: dict, address: str, eth_usd: float) -> Position:
        """Build a Position from the Aave v3 user payload.

        Weights: liquidationThreshold from the reserve, in basis points
        (e.g. 8250 = 82.5%). Prices arrive ETH-denominated (priceInEth);
        multiply by the ETH/USD price for USD values.
        """
        user = data["user"]
        collateral: list[AssetPosition] = []
        debt: list[AssetPosition] = []
        for ur in user["userReserves"]:
            reserve = ur["reserve"]
            sym = reserve["symbol"]
            usd_per_token = float(reserve["price"]["priceInEth"]) * eth_usd
            threshold = int(reserve.get("liquidationThreshold") or 0) / 10_000
            supplied = float(ur["currentATokenBalance"] or 0)
            borrowed = float(ur["currentVariableDebt"] or 0) + float(ur["currentStableDebt"] or 0)
            collat_enabled = ur.get("usageAsCollateralEnabled", True)
            if supplied > 0 and collat_enabled:
                collateral.append(
                    AssetPosition(sym, supplied, supplied * usd_per_token, True, threshold)
                )
            elif supplied > 0:
                # Supplied but not enabled as collateral — balance exists but
                # contributes nothing to the health factor.
                collateral.append(AssetPosition(sym, supplied, supplied * usd_per_token, True, 0.0))
            if borrowed > 0:
                debt.append(AssetPosition(sym, borrowed, borrowed * usd_per_token, False))

        return Position(address, "aave-v3", collateral, debt)


class CompoundV3Client(SubgraphClient):
    def __init__(
        self,
        fixture: Path | str | None = None,
        *,
        endpoint: str | None = None,
        timeout: float = 8.0,
        transport: httpx.BaseTransport | None = None,
        silent_fallback: bool = False,
    ) -> None:
        super().__init__(
            endpoint or COMPOUND_V3_ENDPOINT,
            fixture=fixture or FIXTURE_DIR / "compound_v3_demo.json",
            timeout=timeout,
            transport=transport,
            silent_fallback=silent_fallback,
        )

    def raw_query(self, address: str) -> dict:
        try:
            data = self._post(_COMPOUND_V3_QUERY, {"id": address.lower()})
            self.using_live = True
            return data
        except (httpx.HTTPError, SourceError, ValueError) as exc:
            _log_fallback(exc, self.silent_fallback)
            self.using_live = False
            return json.loads(self.fixture.read_text(encoding="utf-8"))

    def query_position(self, address: str) -> Position:
        data = self.raw_query(address)
        try:
            account = data["data"]["account"]
        except (KeyError, TypeError) as exc:
            raise SourceError(f"malformed subgraph payload: {exc}") from exc
        borrow = float(account["baseBorrowed"] or 0)
        collateral = [
            AssetPosition(
                c["asset"]["symbol"],
                float(c["amount"]),
                float(c["amount"]) * float(c["asset"]["price"]["priceUsd"]),
                True,
                self._borrow_col_pct(c["asset"]["symbol"]),
            )
            for c in account.get("collateral") or []
        ]
        pos = Position(
            address,
            "compound-v3",
            collateral,
            [AssetPosition("USDC", borrow, borrow, False)] if borrow > 0 else [],
        )
        pos.source = "live" if self.using_live else "fixture"
        return pos

    @staticmethod
    def _borrow_col_pct(symbol: str) -> float:
        """Borrow collateralization per asset on the USDC Comet (mainnet
        config). The subgraph does not expose per-account bcp directly, so
        this ships the documented comet config as of the fixture snapshot.
        Kept as data in one place for easy audits."""
        return {"ETH": 0.80, "WETH": 0.80, "WBTC": 0.70, "LINK": 0.70, "UNI": 0.70}.get(symbol, 0.70)


class PriceClient:
    """CoinGecko simple-price feed with a TTL cache and a bundled fallback."""

    def __init__(
        self,
        fallback: Path | str | None = None,
        ttl: float = 120.0,
        timeout: float = 6.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.fallback_path = Path(fallback) if fallback else FIXTURE_DIR / "coingecko_prices_demo.json"
        self.ttl = ttl
        self.timeout = timeout
        self._transport = transport
        self._cache: dict[str, tuple[float, dict[str, float]]] = {}
        self.using_live = False

    def usd_prices(self, symbols: list[str]) -> dict[str, float]:
        """USD prices for a list of asset symbols (resolved via SYMBOL_TO_CG_ID).
        Missing/unmapped symbols are dropped; if the wire fails entirely the
        fixture prices are returned."""
        now = time.time()
        ids = {s: SYMBOL_TO_CG_ID[s] for s in symbols if s in SYMBOL_TO_CG_ID}
        if not ids:
            return {}
        cache_key = ",".join(sorted(ids))
        if cache_key in self._cache:
            ts, prices = self._cache[cache_key]
            if now - ts < self.ttl:
                return prices

        prices = self._fetch_live(ids)
        if prices:
            self.using_live = True
            self._cache[cache_key] = (now, prices)
            return prices

        self.using_live = False
        fallback = self._load_fallback()
        out: dict[str, float] = {}
        for sym, cg_id in ids.items():
            price = fallback.get(cg_id)
            if price:
                out[sym] = price
        return out

    def _fetch_live(self, ids: dict[str, str]) -> dict[str, float]:
        client_kwargs: dict = {"timeout": self.timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            with httpx.Client(**client_kwargs) as client:
                resp = client.get(
                    COINGECKO_ENDPOINT,
                    params={
                        "ids": ",".join(sorted(set(ids.values()))),
                        "vs_currencies": "usd",
                    },
                )
                resp.raise_for_status()
                raw = resp.json()
            return {
                sym: float(raw[cg_id]["usd"])
                for sym, cg_id in ids.items()
                if raw.get(cg_id, {}).get("usd") is not None
            }
        except (httpx.HTTPError, ValueError, TypeError):
            return {}

    def _load_fallback(self) -> dict[str, float]:
        return json.loads(self.fallback_path.read_text(encoding="utf-8"))