"""Storage: snapshot roundtrip, alert dedupe, history (stdlib sqlite3)."""

from __future__ import annotations

from position_guard.storage import Storage, alert_dedupe_key


def test_snapshot_roundtrip(tmp_db):
    storage = Storage(tmp_db)
    storage.save_snapshot("0xabc", "aave-v3", "critical", 1.122, 8500, 6250, 762.5, {"legs": 2})
    latest = storage.latest_snapshot("0xABC")  # address normalized to lowercase
    assert latest is not None
    assert latest["address"] == "0xabc"
    assert latest["hf"] == 1.122
    assert latest["state"] == "critical"
    assert latest["margin_usd"] == 762.5
    storage.close()


def test_alert_dedupe_via_unique_key(tmp_db):
    storage = Storage(tmp_db)
    key = alert_dedupe_key("0xabc", "aave-v3", "critical")
    assert storage.save_alert("0xabc", "aave-v3", "critical", "msg one", key) is True
    assert storage.save_alert("0xabc", "aave-v3", "critical", "msg two", key) is False
    rows = storage.history("0xabc")
    assert len(rows) == 1
    assert rows[0]["message"] == "msg one"
    storage.close()


def test_history_empty_and_limit(tmp_db):
    storage = Storage(tmp_db)
    assert storage.history() == []
    for i in range(3):
        storage.save_alert("0xabc", "aave-v3", "watch", f"msg {i}", f"key-{i}")
    assert len(storage.history(limit=2)) == 2
    assert len(storage.history("0xabc")) == 3
    assert storage.history("0xdead") == []
    storage.close()