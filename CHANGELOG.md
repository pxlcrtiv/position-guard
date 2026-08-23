# Changelog

All notable changes to position-guard are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Additional protocols: Spark, Morpho, Aave v2.
- Multi-address `watch` (config file with several positions).
- Webhook notifications (generic HTTP POST) alongside Telegram.
- Fees/slippage awareness in liquidation-price estimates (currently the
  liquidation price ignores liquidation bonuses and fee-on-transfer &mdash;
  documented approximation).
- Live demo mode backed by a real testnet position.

## [0.1.0] - 2026-08-23

### Added

- **Subgraph clients** for Aave v3 (`aave/protocol-v3`) and Compound v3
  (`mason/compound-v3`) via the public The Graph hosted service, with a
  bundled GraphQL fixture fallback when the endpoint is unreachable; `--offline`
  force-fixture mode; fixture data always labeled in output.
- **Health-factor math** (`position_guard/health.py`): Aave v3
  (per-asset liquidation thresholds) and Compound v3 (per-asset borrow
  collateralization), margin-to-liquidation in USD, and per-asset
  liquidation price. All hand-computed golden tests.
- **Threshold state machine** (`position_guard/state.py`): healthy / watch /
  warning / critical / liquidation with configurable thresholds; downgrade
  alerting with per-level, time-bucketed dedupe.
- **Alert writer** (`position_guard/alerts.py`): deterministic template
  backend (default) and optional OpenAI-compatible LLM backend with graceful
  fallback; alerts in the shape of the project one-liner
  ("…at 1.12 HF, ~$763 of margin left…").
- **CLI** (`position-guard`): `check`, `watch` (interval + `--once`),
  `demo` (keyless, offline), `preview`, `history`, `--json-out`.
- **Web preview** (`position_guard/preview.py`): standalone dark-themed HTML
  page with HF bar, per-leg tables and the alert; `demo --serve` hosts it.
- **SQLite storage**: snapshot + alert history with dedupe (stdlib sqlite3).
- **Telegram sender** (optional, Bot API over plain HTTPS, no extra deps).
- **Daily Green automation**: `scripts/daily_update.py` +
  `scripts/tips_pool.json` (22 curated DeFi risk tips), idempotent, dated
  commits, launchd + Actions fallback.
- **CI**: pytest × Python 3.11/3.12, ruff, and a demo smoke test.
- **Docs**: README with real demo transcript + generated SVG screenshot,
  CONTRIBUTING, CHANGELOG, MIT license.
- **Tests**: 52 offline tests, including golden health-factor fixtures,
  mocked-transport client tests, CLI end-to-end, and alert-wording checks.