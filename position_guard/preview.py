"""Web preview — the keyless demo deliverable.

Renders one position snapshot as a standalone dark-themed HTML page (inline
CSS, zero JS, zero external requests) with the health-factor bar, the asset
legs, the generated alert, and an honest disclaimer.
"""

from __future__ import annotations

import html
import time
from datetime import datetime, timezone
from pathlib import Path

_STATE_COLORS = {
    "healthy": "#2ecc71",
    "watch": "#f1c40f",
    "warning": "#e67e22",
    "critical": "#e74c3c",
    "liquidation": "#ff2d55",
}
_STATE_LABELS = {
    "healthy": "HEALTHY",
    "watch": "WATCH",
    "warning": "WARNING",
    "critical": "CRITICAL",
    "liquidation": "LIQUIDATION WINDOW",
}

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    background: #0b0e14; color: #d7dae0;
    min-height: 100vh; padding: 2rem 1rem; display: flex; justify-content: center;
  }}
  .card {{
    width: min(720px, 100%); background: #12161f; border: 1px solid #232a38;
    border-radius: 14px; padding: 1.6rem;
    box-shadow: 0 12px 40px rgba(0,0,0,.45);
  }}
  .head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; }}
  h1 {{ font-size: 1.05rem; color: #fff; letter-spacing: .04em; }}
  .state-tag {{
    font-size: .72rem; font-weight: 700; padding: 4px 10px; border-radius: 999px;
    letter-spacing: .08em; color: #0b0e14;
  }}
  .addr {{ color: #7f8ea3; font-size: .78rem; word-break: break-all; margin-top: .35rem; }}
  .meta {{ color: #7f8ea3; font-size: .72rem; margin-top: .5rem; display: flex; gap: 1rem; flex-wrap: wrap; }}
  .hf-row {{ margin: 1.6rem 0 1rem; }}
  .hf-num {{ font-size: 2.6rem; font-weight: 700; }}
  .hf-label {{ color: #7f8ea3; font-size: .75rem; text-transform: uppercase; letter-spacing: .1em; margin-top: .2rem; }}
  .bar {{ height: 14px; background: #1c2330; border-radius: 999px; margin-top: .7rem; overflow: hidden; }}
  .bar > div {{ height: 100%; border-radius: 999px; transition: width .6s ease; }}
  .tick {{ display: flex; justify-content: space-between; color: #5a6780; font-size: .68rem; margin-top: .3rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: .82rem; }}
  th {{ text-align: left; color: #7f8ea3; font-weight: 600; font-size: .7rem; text-transform: uppercase;
       letter-spacing: .08em; padding: .45rem .5rem; border-bottom: 1px solid #232a38; }}
  td {{ padding: .5rem; border-bottom: 1px solid #1a202c; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .alert {{ margin-top: 1.4rem; border-radius: 10px; padding: 1rem 1.1rem; font-size: .9rem; line-height: 1.55; }}
  .alert .who {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .1em; opacity: .8; margin-bottom: .35rem; }}
  .foot {{ margin-top: 1.6rem; color: #55617a; font-size: .7rem; line-height: 1.6; border-top: 1px solid #1a202c; padding-top: .9rem; }}
</style>
</head>
<body>
<div class="card">
  <div class="head">
    <div>
      <h1>{title}</h1>
      <div class="addr">{address}</div>
    </div>
    <span class="state-tag" style="background:{state_color}">{state_label}</span>
  </div>
  <div class="meta">
    <span>protocol {protocol}</span>
    <span>source {source}</span>
    <span>{generated}</span>
  </div>

  <div class="hf-row">
    <div class="hf-num" style="color:{state_color}">{hf}</div>
    <div class="hf-label">health factor · liquidation at &lt; 1.00</div>
    <div class="bar"><div style="width:{bar_pct}%; background:{state_color}"></div></div>
    <div class="tick"><span>0</span><span>0.5</span><span>1.0 (liq)</span><span>1.5</span><span>2.5+</span></div>
  </div>

  <table>
    <tr><th>Side</th><th>Asset</th><th class="num">Amount</th><th class="num">Value (USD)</th><th class="num">Weight</th></tr>
    {rows}
  </table>

  <div class="alert" style="background:{alert_bg}; border:1px solid {state_color}">
    <div class="who">alert · {alert_backend} backend</div>
    <div>{alert_msg}</div>
  </div>

  <div class="foot">
    {totals}<br>
    <strong>Disclaimer:</strong> position-guard is a monitoring aid, not financial
    advice, and not a liquidation service. Health factors shown here are
    simplified approximations of the protocol's own math (see README). No real
    funds are ever touched — data comes from public subgraphs / bundled demo
    fixtures. Always confirm against the protocol UI before acting.
  </div>
</div>
</body>
</html>
"""


def render_preview(snapshot: dict, out: str | Path) -> Path:
    out = Path(out)
    level = snapshot["alert"]["level"]
    color = _STATE_COLORS.get(level, "#e74c3c")
    label = _STATE_LABELS.get(level, level.upper())

    hf = snapshot.get("hf")
    hf_display = "∞" if hf is None else f"{hf:.2f}"
    bar_pct = 100.0 if hf is None else min(100.0, max(4.0, hf / 2.5 * 100))

    rows = []
    for leg in snapshot.get("collateral", []):
        rows.append(_row("Collateral", leg, color))
    for leg in snapshot.get("debt", []):
        rows.append(_row("Debt", leg, "#7f8ea3"))
    if not rows:
        rows.append("<tr><td colspan=5 style='color:#55617a'>no open positions</td></tr>")

    collat = snapshot.get("collateral_usd", 0.0)
    debt = snapshot.get("debt_usd", 0.0)
    margin = snapshot.get("margin_usd", 0.0)
    totals = (
        f"Collateral ${collat:,.0f} · Debt ${debt:,.0f} · "
        f"Margin-to-liquidation ${margin:,.0f}"
    )
    ts = snapshot.get("ts") or time.time()
    generated = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    page = _PAGE.format(
        title="position-guard · position health",
        address=html.escape(snapshot.get("address", "")),
        state_color=color,
        state_label=label,
        protocol=html.escape(snapshot.get("protocol", "")),
        source=html.escape(snapshot.get("source", "fixture")),
        generated=generated,
        hf=hf_display,
        bar_pct=f"{bar_pct:.0f}",
        rows="\n    ".join(rows),
        totals=html.escape(totals),
        alert_bg=f"{color}14",
        alert_backend=html.escape(snapshot["alert"].get("backend", "template")),
        alert_msg=html.escape(snapshot["alert"].get("message", "")),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def _row(side: str, leg: dict, color: str) -> str:
    weight = leg.get("weight")
    weight_txt = f"{weight * 100:.1f}%" if weight is not None else "—"
    return (
        f'<tr><td style="color:{color}">{side}</td>'
        f"<td>{html.escape(leg['symbol'])}</td>"
        f'<td class="num">{leg["amount"]:,.4f}</td>'
        f'<td class="num">${leg["usd_value"]:,.0f}</td>'
        f'<td class="num">{weight_txt}</td></tr>'
    )