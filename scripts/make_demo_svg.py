#!/usr/bin/env python3
"""Regenerate docs/preview.svg — the README demo screenshot.

Runs the real offline demo pipeline (Monitor live=False -> bundled fixtures)
through a recording rich console and exports a terminal screenshot SVG, so the
README's demo image is always the true output of the tool, not a mock.

Usage:  python scripts/make_demo_svg.py   (from the repo root)
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from position_guard import DEMO_ADDRESS
from position_guard.cli import _print_snapshot
from position_guard.engine import Monitor


def main() -> int:
    console = Console(record=True, width=94, force_terminal=True)
    monitor = Monitor(Path("/tmp/position-guard-svg.db"), live=False)
    snap = monitor.snapshot(DEMO_ADDRESS)
    console.rule("[bold]position-guard demo[/bold]")
    _print_snapshot(snap, console=console)
    console.print("\n[bold green]✓[/bold green] web preview written: [cyan]docs/preview.html[/cyan]")
    monitor.storage.close()

    out = REPO / "docs" / "preview.svg"
    console.save_svg(str(out), title="position-guard demo")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())