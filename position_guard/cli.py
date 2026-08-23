"""position-guard CLI — check, watch, demo, preview, history.

Zero-key path: `position-guard demo` renders a synthetic fixture position to
the terminal AND writes a standalone web preview (docs/preview.html by
default). Everything degrades gracefully with no network and no tokens.
"""

from __future__ import annotations

import json
import logging
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import DEMO_ADDRESS, PROTOCOL_AAVE_V3, SUPPORTED_PROTOCOLS, __version__
from .engine import Monitor
from .preview import render_preview
from .scheduler import WatchLoop
from .storage import Storage, alert_dedupe_key

console = Console()
err_console = Console(stderr=True)

_STATE_STYLE = {
    "healthy": "bold green",
    "watch": "bold yellow",
    "warning": "bold orange3",
    "critical": "bold red",
    "liquidation": "bold white on red",
}

DEFAULT_DB = "~/.position-guard/position-guard.db"
DEFAULT_PREVIEW = "docs/preview.html"


def _state_label(state: str) -> str:
    return {
        "healthy": "HEALTHY",
        "watch": "WATCH",
        "warning": "WARNING",
        "critical": "CRITICAL",
        "liquidation": "LIQUIDATION WINDOW",
    }.get(state, state.upper())


def _print_snapshot(snap: dict, show_alert: bool = True, console: Console = console) -> None:
    style = _STATE_STYLE.get(snap["state"], "bold")
    hf = snap.get("hf")
    hf_txt = "∞" if hf is None else f"{hf:.2f}"

    head = Table.grid(padding=(0, 1))
    head.add_column(justify="left")
    head.add_column(justify="right")
    source = "live subgraph" if snap["source"] == "live" else "bundled fixture"
    if snap["source"] != "live":
        source += " (endpoint unreachable — demo/synthetic data)"
    head.add_row(
        f"[bold]position-guard[/bold] · {snap['protocol']}",
        f"[dim]{source}[/dim]",
    )
    console.print(Panel(head, border_style="dim"))

    console.print(f"address   [cyan]{snap['address']}[/cyan]")
    console.print(
        f"health    [{style}]{hf_txt}[/{style}]  "
        f"[{style}]{_state_label(snap['state'])}[/{style}]"
    )

    table = Table(show_header=True, header_style="dim", box=None, pad_edge=False)
    table.add_column("side")
    table.add_column("asset", justify="right")
    table.add_column("amount", justify="right")
    table.add_column("USD", justify="right")
    table.add_column("factor", justify="right")
    for leg in snap.get("collateral", []):
        weight = leg.get("weight")
        table.add_row(
            "[green]collateral[/green]",
            leg["symbol"],
            f"{leg['amount']:,.4f}",
            f"${leg['usd_value']:,.0f}",
            f"{weight * 100:.1f}%" if weight is not None else "—",
        )
    for leg in snap.get("debt", []):
        table.add_row("[red]debt[/red]", leg["symbol"], f"{leg['amount']:,.4f}", f"${leg['usd_value']:,.0f}", "—")
    console.print(table)
    console.print(
        f"[dim]collateral ${snap['collateral_usd']:,.0f} · debt ${snap['debt_usd']:,.0f} · "
        f"margin to liquidation ${snap['margin_usd']:,.0f}[/dim]"
    )

    if show_alert:
        alert = snap["alert"]
        console.print(
            Panel(
                f"[{style}]{alert['message']}[/{style}]",
                title=f"alert · {alert['backend']} backend · {_state_label(alert['level'])}",
                border_style=_STATE_STYLE.get(alert["level"], "bold"),
            )
        )


@click.group()
@click.version_option(__version__, prog_name="position-guard")
def main() -> None:
    """DeFi health monitor — Aave v3 / Compound v3 positions, plain-English
    alerts. Health factors below 1.00 mean the position is liquidatable."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@main.command()
@click.option("--address", required=True, help="EVM address to check (0x…).")
@click.option("--protocol", type=click.Choice(SUPPORTED_PROTOCOLS), default=PROTOCOL_AAVE_V3)
@click.option("--db", default=DEFAULT_DB, help="SQLite database path.")
@click.option("--json-out", "json_out", is_flag=True, help="Print the snapshot as JSON instead.")
@click.option("--offline", is_flag=True, help="Force the bundled fixture (no network).")
def check(address: str, protocol: str, db: str, json_out: bool, offline: bool) -> None:
    """Fetch one position and print its health factor + alert."""
    monitor = Monitor(db, protocol=protocol, live=not offline)
    snap = monitor.snapshot(address)
    monitor.storage.save_alert(
        address, snap["protocol"], snap["state"], snap["alert"]["message"],
        alert_dedupe_key(address, snap["protocol"], snap["state"]),
    )
    if json_out:
        # plain print, not rich: rich markup would un-escape \n inside the JSON
        print(json.dumps(snap, indent=2))
    else:
        _print_snapshot(snap)
    monitor.storage.close()


@main.command()
@click.option("--address", required=True, help="EVM address to watch (0x…).")
@click.option("--protocol", type=click.Choice(SUPPORTED_PROTOCOLS), default=PROTOCOL_AAVE_V3)
@click.option("--db", default=DEFAULT_DB)
@click.option("--interval", default=60.0, show_default=True, help="Seconds between checks.")
@click.option("--once", is_flag=True, help="Check once and exit.")
@click.option("--telegram", is_flag=True, help="Send state-change alerts via Telegram (needs TELEGRAM_BOT_TOKEN).")
@click.option("--notify-all", is_flag=True, help="Also alert on upgrades/every change (default: downgrades only).")
@click.option("--offline", is_flag=True)
def watch(
    address: str,
    protocol: str,
    db: str,
    interval: float,
    once: bool,
    telegram: bool,
    notify_all: bool,
    offline: bool,
) -> None:
    """Poll a position on an interval and alert on state changes."""
    monitor = Monitor(db, protocol=protocol, live=not offline)
    from .state import Level

    prev: Level | None = None

    def tick(n: int) -> bool:
        nonlocal prev
        snap, prev, alert = monitor.handle_tick(address, prev, telegram=telegram, notify_all=notify_all)
        _print_snapshot(snap, show_alert=alert is not None)
        if alert:
            console.print(f"[bold cyan]▶ tick {n} alert[/bold cyan] {alert}")
        return True

    ticks = WatchLoop(interval, tick).run(max_ticks=1 if once else None)
    monitor.storage.close()
    if once:
        console.print(f"[dim]watch --once: {ticks} tick completed[/dim]")


@main.command()
@click.option("--protocol", type=click.Choice(SUPPORTED_PROTOCOLS), default=PROTOCOL_AAVE_V3)
@click.option("--db", default=DEFAULT_DB)
@click.option("--out", default=DEFAULT_PREVIEW, show_default=True, help="Where to write the web preview.")
@click.option("--serve", is_flag=True, help="Serve the preview dir on localhost after rendering.")
@click.option("--port", default=8000, show_default=True)
@click.option("--no-browser", is_flag=True, help="Do not auto-open the preview.")
def demo(protocol: str, db: str, out: str, serve: bool, port: int, no_browser: bool) -> None:
    """Keyless demo: synthetic fixtures -> terminal alert + web preview.

    Deterministic, offline, ~3 seconds. Renders a bundled Aave v3 (or
    Compound v3) position for the demo address, prints the plain-English
    alert, and writes a standalone HTML preview page.
    """
    monitor = Monitor(db, protocol=protocol, live=False)
    snap = monitor.snapshot(DEMO_ADDRESS)
    monitor.storage.save_alert(
        DEMO_ADDRESS, snap["protocol"], snap["state"], snap["alert"]["message"],
        alert_dedupe_key(DEMO_ADDRESS, snap["protocol"], snap["state"]),
    )
    monitor.storage.close()

    console.rule("[bold]position-guard demo[/bold]")
    _print_snapshot(snap)
    out_path = render_preview(snap, out)
    console.print(f"\n[bold green]✓[/bold green] web preview written: [cyan]{out_path}[/cyan]")

    if serve:
        _serve_folder(out_path.parent, port)
    elif not no_browser:
        url = out_path.resolve().as_uri()
        console.print(f"opening [cyan]{url}[/cyan]")
        try:
            webbrowser.open(url)
        except Exception:
            console.print("[dim]could not auto-open a browser; open the file above.[/dim]")


@main.command()
@click.option("--db", default=DEFAULT_DB)
@click.option("--address", default=None, help="Restrict to one address.")
@click.option("--limit", default=20, show_default=True)
def history(db: str, address: str | None, limit: int) -> None:
    """List previously stored snapshots/alerts from SQLite."""
    monitor_storage = _storage_only(db)
    rows = monitor_storage.history(address, limit=limit)
    if not rows:
        console.print("[dim]no alerts stored yet — run `position-guard check` or `demo` first[/dim]")
        return
    table = Table(header_style="dim", box=None)
    table.add_column("when (utc)")
    table.add_column("address", style="cyan")
    table.add_column("level", style="bold")
    table.add_column("message")
    for r in rows:
        import datetime as dt

        ts = dt.datetime.fromtimestamp(r["ts"], tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
        table.add_row(ts, r["address"][:12] + "…", r["level"], r["message"])
    console.print(table)


@main.command()
@click.option("--db", default=DEFAULT_DB)
@click.option("--address", default=None, help="Which address's latest snapshot to render.")
@click.option("--out", default=DEFAULT_PREVIEW, show_default=True)
@click.option("--serve", is_flag=True)
@click.option("--port", default=8000, show_default=True)
def preview(db: str, address: str | None, out: str, serve: bool, port: int) -> None:
    """Re-render the web preview from the latest stored snapshot."""
    monitor_storage = _storage_only(db)
    latest = monitor_storage.latest_snapshot(address or DEMO_ADDRESS)
    if latest is None:
        raise click.ClickException("no snapshot in db — run `position-guard check` or `demo` first")
    snap = json.loads(latest["payload"])
    snap.update(
        {
            "ts": latest["ts"],
            "hf": latest["hf"],
            "state": latest["state"],
            "collateral_usd": latest["collateral_usd"],
            "debt_usd": latest["debt_usd"],
            "margin_usd": latest["margin_usd"],
        }
    )
    if "alert" not in snap:
        # Older stored payloads (position.to_dict()) lack the alert — synth one.
        from .state import classify

        level = classify(latest["hf"]).value
        snap["alert"] = {
            "level": level,
            "message": f"{_state_label(level)} — position at {latest['hf']:.2f} HF (stored snapshot)",
            "backend": "template",
        }
    out_path = render_preview(snap, out)
    console.print(f"web preview written: [cyan]{out_path}[/cyan]")
    if serve:
        _serve_folder(out_path.parent, port)


def _storage_only(db: str):

    return Storage(Path(db).expanduser())


def _serve_folder(folder: Path, port: int) -> None:
    from functools import partial

    handler = partial(SimpleHTTPRequestHandler, directory=str(folder))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    console.print(f"[bold green]serving[/bold green] http://127.0.0.1:{port}/preview.html — Ctrl-C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        console.print("\n[dim]stopping server[/dim]")
        httpd.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()