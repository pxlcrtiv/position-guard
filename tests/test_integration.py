"""Integration: Monitor engine snapshot (offline), handle_tick alert policy,
WatchLoop scheduling, CLI demo, and the web preview."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from position_guard import DEMO_ADDRESS
from position_guard.cli import main
from position_guard.engine import Monitor
from position_guard.scheduler import WatchLoop
from position_guard.state import Level


def test_monitor_demo_snapshot_golden(tmp_db):
    monitor = Monitor(tmp_db, live=False)
    snap = monitor.snapshot(DEMO_ADDRESS)
    assert snap["protocol"] == "aave-v3"
    assert snap["source"] == "fixture"
    assert snap["hf"] == pytest.approx(1.122, rel=1e-9)
    assert snap["state"] == "critical"
    assert snap["collateral_usd"] == pytest.approx(8500.0, rel=1e-9)
    assert snap["debt_usd"] == pytest.approx(6250.0, rel=1e-6)
    assert "1.12 HF" in snap["alert"]["message"]
    assert snap["alert"]["backend"] == "template"

    # snapshot persisted
    latest = monitor.storage.latest_snapshot(DEMO_ADDRESS)
    assert latest is not None and latest["state"] == "critical"
    monitor.storage.close()


def test_handle_tick_fires_once_per_state_and_bucket(tmp_db):
    monitor = Monitor(tmp_db, live=False)
    _, _, alert = monitor.handle_tick(DEMO_ADDRESS, None)
    assert alert is not None
    assert "1.12 HF" in alert
    # same state, same dedupe bucket -> silent
    _, _, alert2 = monitor.handle_tick(DEMO_ADDRESS, Level.CRITICAL)
    assert alert2 is None
    # unchanged state with notify_all -> still silent (dedupe + no downgrade)
    snap3, _, alert3 = monitor.handle_tick(DEMO_ADDRESS, Level.CRITICAL, notify_all=True)
    assert snap3["state"] == "critical"
    assert alert3 is None
    monitor.storage.close()


def test_watch_loop_counts_ticks_without_sleeping():
    seen = []

    def tick(n: int) -> bool:
        seen.append(n)
        return True

    loop = WatchLoop(interval=0.0, on_tick=tick, sleep=lambda s: seen.append(-1))
    assert loop.run(max_ticks=4) == 4
    assert seen == [1, 2, 3, 4]  # sleep never called with interval 0


def test_watch_loop_stops_on_false():
    calls = []

    def tick(n: int) -> bool:
        calls.append(n)
        return n < 2

    loop = WatchLoop(interval=0.0, on_tick=tick, sleep=lambda s: None)
    assert loop.run(max_ticks=10) == 2  # tick 2 returned False


def test_cli_demo_writes_terminal_and_preview(tmp_path):
    runner = CliRunner()
    db = tmp_path / "demo.db"
    out = tmp_path / "out" / "preview.html"
    result = runner.invoke(main, ["demo", "--db", str(db), "--out", str(out), "--no-browser"])
    assert result.exit_code == 0, result.output
    assert "1.12" in result.output
    assert "web preview written" in result.output
    html_text = out.read_text(encoding="utf-8")
    assert "health factor" in html_text
    assert "CRITICAL" in html_text
    assert "2.5000" in html_text  # ETH collateral amount rendered
    assert "Margin-to-liquidation" in html_text


def test_cli_check_json_output(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["check", "--address", DEMO_ADDRESS, "--offline", "--json-out", "--db", str(tmp_path / "c.db")],
    )
    assert result.exit_code == 0, result.output
    import json

    data = json.loads(result.output)
    assert data["hf"] == pytest.approx(1.122, rel=1e-9)
    assert data["alert"]["level"] == "critical"


def test_cli_history_after_demo(tmp_path):
    runner = CliRunner()
    db = tmp_path / "h.db"
    assert runner.invoke(main, ["demo", "--db", str(db), "--out", str(tmp_path / "p.html"), "--no-browser"]).exit_code == 0
    result = runner.invoke(main, ["history", "--db", str(db)])
    assert result.exit_code == 0
    assert "critical" in result.output


def test_cli_compound_demo_renders(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["demo", "--protocol", "compound-v3", "--db", str(tmp_path / "cd.db"), "--out", str(tmp_path / "cp.html"), "--no-browser"],
    )
    assert result.exit_code == 0, result.output
    assert "1.36" in result.output
    assert Path(tmp_path / "cp.html").exists()