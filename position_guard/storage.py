"""SQLite persistence: position snapshots + alert history (stdlib sqlite3)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    address       TEXT NOT NULL,
    protocol      TEXT NOT NULL,
    ts            REAL NOT NULL,
    state         TEXT NOT NULL,
    hf            REAL,
    collateral_usd REAL NOT NULL,
    debt_usd      REAL NOT NULL,
    margin_usd    REAL NOT NULL,
    payload       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_addr_ts ON snapshots(address, ts);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    address    TEXT NOT NULL,
    protocol   TEXT NOT NULL,
    ts         REAL NOT NULL,
    level      TEXT NOT NULL,
    message    TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE
);
"""


class Storage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save_snapshot(self, address, protocol, state, hf, collateral_usd, debt_usd, margin_usd, payload: dict) -> int:
        cur = self._conn.execute(
            "INSERT INTO snapshots (address, protocol, ts, state, hf, collateral_usd, debt_usd, margin_usd, payload)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                address.lower(),
                protocol,
                time.time(),
                state,
                hf,
                collateral_usd,
                debt_usd,
                margin_usd,
                json.dumps(payload),
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def save_alert(self, address, protocol, level, message, dedupe_key: str) -> bool:
        """Insert an alert; returns False when a duplicate (same key) exists."""
        try:
            cur = self._conn.execute(
                "INSERT INTO alerts (address, protocol, ts, level, message, dedupe_key)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (address.lower(), protocol, time.time(), level, message, dedupe_key),
            )
            self._conn.commit()
            return cur.rowcount == 1
        except sqlite3.IntegrityError:
            return False

    def latest_snapshot(self, address: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM snapshots WHERE address = ? ORDER BY ts DESC LIMIT 1", (address.lower(),)
        ).fetchone()
        return dict(row) if row else None

    def history(self, address: str | None = None, limit: int = 50) -> list[dict]:
        if address:
            rows = self._conn.execute(
                "SELECT * FROM alerts WHERE address = ? ORDER BY ts DESC LIMIT ?",
                (address.lower(), limit),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def alert_dedupe_key(address: str, protocol: str, level: str, window_hours: int = 12) -> str:
    """Alerts are deduped per level per ~window — a position stuck in CRITICAL
    fires once, not on every poll. The day-bucket keeps it deterministic
    (time.time() // bucket)."""
    bucket = int(time.time()) // (window_hours * 3600)
    return f"{address.lower()}:{protocol}:{level}:{bucket}"