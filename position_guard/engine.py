"""Monitor engine — wires clients, prices, health math, state machine, alert
writer, storage, and (optionally) Telegram into one snapshot() call used by
both `check` and `watch`."""

from __future__ import annotations

import time
from pathlib import Path

from . import DEMO_ADDRESS, PROTOCOL_AAVE_V3
from .alerts import AlertWriter
from .client import OFFLINE_TRANSPORT, AaveV3Client, CompoundV3Client, PriceClient
from .health import aave_v3_health_factor, compound_v3_health_factor, margin_left_usd
from .models import Position
from .state import Level, classify, is_downgrade, is_upgrade
from .storage import Storage, alert_dedupe_key
from .telegram import TelegramSender

# Unreachable endpoint used to force the fixture path deterministically
# (connection refused on localhost:1, instant, offline). The public endpoints
# are the defaults for live mode.
_CLOSED = "http://127.0.0.1:1"


class Monitor:
    def __init__(
        self,
        db_path: str | Path = "~/.position-guard/position-guard.db",
        protocol: str = PROTOCOL_AAVE_V3,
        live: bool = True,
        alert_backend: str | None = None,
    ) -> None:
        self.db_path = Path(db_path).expanduser()
        self.protocol = protocol
        self.live = live
        self.storage = Storage(self.db_path)
        self.writer = AlertWriter(backend=alert_backend)
        self.telegram = TelegramSender()

    # -- clients -------------------------------------------------------------

    def _subgraph(self) -> AaveV3Client | CompoundV3Client:
        if self.protocol == PROTOCOL_AAVE_V3:
            if self.live:
                return AaveV3Client()
            return AaveV3Client(endpoint=_CLOSED, silent_fallback=True)  # instant refusal -> fixture
        if self.live:
            return CompoundV3Client()
        return CompoundV3Client(endpoint=_CLOSED, silent_fallback=True)

    def _prices(self) -> PriceClient:
        if self.live:
            return PriceClient()
        return PriceClient(transport=OFFLINE_TRANSPORT)  # force bundled prices too

    # -- one snapshot --------------------------------------------------------

    def snapshot(self, address: str) -> dict:
        """Fetch, compute, alert, persist. Returns the full snapshot dict (also
        stored in sqlite) — the single source of truth for CLI + preview."""
        addr = address.lower()
        fetched_at = time.time()

        if self.protocol == PROTOCOL_AAVE_V3:
            eth_usd = self._prices().usd_prices(["ETH"]).get("ETH") or 3400.0
            position: Position = self._subgraph().query_position(addr, eth_usd)
            hf = aave_v3_health_factor(position)
        else:
            position = self._subgraph().query_position(addr)
            hf = compound_v3_health_factor(position)

        level = classify(hf)
        alert = self.writer.write(position, hf, level)
        margin = margin_left_usd(position)

        snapshot = {
            "address": addr,
            "protocol": position.protocol,
            "source": position.source,
            "ts": fetched_at,
            "hf": hf,
            "state": level.value,
            "collateral_usd": position.collateral_usd,
            "debt_usd": position.debt_usd,
            "margin_usd": margin,
            "collateral": [
                {"symbol": a.symbol, "amount": a.amount, "usd_value": a.usd_value, "weight": a.weight}
                for a in position.collateral
            ],
            "debt": [
                {"symbol": a.symbol, "amount": a.amount, "usd_value": a.usd_value, "weight": None}
                for a in position.debt
            ],
            "alert": alert.to_dict(),
        }

        self.storage.save_snapshot(
            addr, snapshot["protocol"], level.value, hf,
            snapshot["collateral_usd"], snapshot["debt_usd"], margin, position.to_dict(),
        )
        return snapshot

    # -- watch plumbing ------------------------------------------------------

    def handle_tick(
        self,
        address: str,
        previous: Level | None,
        telegram: bool = False,
        notify_all: bool = False,
    ) -> tuple[dict, Level | None, str | None]:
        """One watch tick. Returns (snapshot, previous_level, alert_message).
        Alerting policy: first sighting in a risk state, any downgrade, and
        (with notify_all) every change — duplicates are additionally blocked
        by the storage dedupe key."""
        snap = self.snapshot(address)
        level = Level(snap["state"])
        msg: str = snap["alert"]["message"]

        alert_msg: str | None = None
        changed = previous is None or is_downgrade(previous, level) or (
            notify_all and (is_upgrade(previous, level) or previous != level)
        )
        if changed and self.storage.save_alert(
            address, snap["protocol"], level.value, msg,
            alert_dedupe_key(address, snap["protocol"], level.value),
        ):
            alert_msg = msg
            if telegram:
                if self.telegram.enabled:
                    self.telegram.send(alert_msg)
                else:
                    alert_msg = alert_msg + "\n(Telegram skipped: TELEGRAM_BOT_TOKEN not set)"
        return snap, previous, alert_msg


def demo_address() -> str:
    return DEMO_ADDRESS