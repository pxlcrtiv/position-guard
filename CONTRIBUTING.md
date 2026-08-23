# Contributing

Thanks for considering a contribution to position-guard! Everything here is
open source, tested, and committed to daily — please keep it that way.

## Ground rules

- **Honest engineering.** No empty commits, no exaggerated claims, no fake
  data. Every numeric claim in the README is reproducible by a command in the
  repo (golden fixtures, demo transcript, SVG screenshot).
- **Offline-first.** Tests must never depend on the network. All external data
  paths (The Graph, CoinGecko, Telegram, LLM) are behind mocked transports or
  bundled fixtures.
- **Degrade gracefully.** If the LLM key is missing, if the subgraph is down,
  if Telegram is not configured — the tool still works and says so. Preserve
  that property in every change.

## Development workflow

```bash
git clone https://github.com/pxlcrtiv/position-guard.git
cd position-guard
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # app + pytest + ruff

# run the offline suite (52 tests, golden math included)
python -m pytest tests/ -q

# lint
ruff check .

# regenerate the README demo screenshot (only when terminal output changed)
python scripts/make_demo_svg.py
```

### Conventions

- Python ≥ 3.10, type hints on public APIs, ruff-clean (line length 100).
- New data sources: wrap in a client with a fixture fallback + a mocked
  transport test (see `tests/test_client.py`).
- Health-factor math lives in `position_guard/health.py`; every formula gets
  a hand-computed golden test (see `tests/test_health.py`).
- Alerts: template wording lives in `position_guard/alerts.py`; LLM output is
  *never required* — templates are the contract.
- Commit style: `type: subject` (e.g. `feat:`, `fix:`, `docs:`,
  `test:`, `chore:`). One logical change per commit.

## Sustainable-commit workflow (daily green)

- **Every calendar day** this repo receives one meaningful, dated commit via
  `scripts/daily_update.py` (see the README's Daily Green section). If you
  send a PR, prefer to keep it on a branch; the daily tip file
  (`docs/daily-tips.md`) is append-only to keep day commits conflict-free.
- **Backfill rule:** the automation may backfill up to 14 missed days with
  dated commits; never hand-craft those — let the script do it.
- **Pause** the automation for a day or two with `touch .daily-pause` in the
  repo root — a silent day is better than a filler commit.

## Reviewing

- Every PR: `pytest` green offline, `ruff check` clean, no network in tests,
  README claims reproducible.
- Health-factor changes MUST come with updated golden fixtures and noted
  tolerance changes.
- Docs changes (README, CHANGELOG) are real changes — they get reviewed like
  code.

## Reporting issues

Include: the command you ran, Python version, whether the subgraph endpoint
was reachable (or offline fixture mode), and the full output. For health
factor discrepancies include the protocol UI's own numbers — the math here is
a simplified approximation by design, and "differs from the protocol UI" is
not a bug by itself (but we do want to know about it!).

## Code of conduct

Be direct, be kind, be honest. No harassment, no spam, no bad-faith PRs
("testnet-only, no real funds" is a design constraint, not a suggestion).

MIT-licensed contributions are assumed.