# DeFi risk tips of the day

> Maintained by `scripts/daily_update.py` (Daily Green automation) — one
> dated, non-empty liquidity/risk tip per day, rotated from the pool in
> `scripts/tips_pool.json`. Pause by creating a `.daily-pause` file in the
> repo root, or unload the scheduler job (see README, Daily Green).


## 2026-08-21 — DeFi risk tip: The supply rate is paid to suppliers, not to the protocol

When you supply ETH to Aave you earn the supply rate, but your collateral's health contribution ignores interest — while your borrowed balance accrues interest continuously. Every block your HF ticks down silently. Long passive borrowing positions decay without any visible change in balances.

> `position-guard history --address 0xYourAddressHere`


## 2026-08-22 — DeFi risk tip: Unlimited approvals are a permanent backdoor

An approval from 2023 still lets that contract move your tokens. Revoke approvals you no longer use (revoke.cash, or a dedicated revoker). For position management, prefer 'spend limit = position size + buffer'; for monitoring bots, a read-only key or no key at all — position-guard needs only a public address.


## 2026-08-23 — DeFi risk tip: Testnet practice beats mainnet pain — and it is free

Every liquidation that could have happened for $3 of Sepolia ETH can be rehearsed: supply, borrow to the edge, let the HF drift, watch the state machine fire. position-guard's fixtures mimic exactly this shape. No amount of theory replaces one real forced-liquidation rehearsal.

> `position-guard demo --protocol compound-v3`


## 2026-08-24 — DeFi risk tip: Gas spikes change the liquidation surface

At 300 gwei, a $50 top-up costs more in gas than the margin it buys — and liquidators, who batch, still find it profitable. Small positions with thin margins are the most dangerous: the rescue transaction may be economically irrational while the liquidation is not.


## 2026-08-25 — DeFi risk tip: Watch the borrow rate, not just the HF

Utilization above ~90-95% sends borrow APRs parabolic. Your stablecoin debt could go from 4% to 40% APR overnight; the extra interest then erodes HF faster. If the utilization of your borrowed asset is high, price stability depends on everyone else behaving.


## 2026-08-26 — DeFi risk tip: Multi-collateral positions: each leg has its own liquidation price

With ETH + WBTC collateral and a stable debt, the liquidation price of ETH depends on WBTC's current price — they move together in crashes, which is exactly when the calculation gets pessimistic. position-guard computes per-asset liquidation prices holding everything else fixed; remember that 'everything else' rarely holds.

> `position-guard preview`


## 2026-08-27 — DeFi risk tip: The health factor formula hides the liquidation bonus

HF = weighted collateral / debt looks binary, but liquidations execute at a bonus (e.g. 5%), meaning liquidators profit slightly BEFORE HF hits 1.0 in some configurations, and the protocol may also apply close-factor limits (e.g. 50% per liquidation). The smooth HF line is a simplification of a very lumpy process.


## 2026-08-28 — DeFi risk tip: Bridge risk outranks most yield math

If your collateral sits behind a bridge (wrapped asset, L2 position managed from L1), a bridge outage on the day of a crash means you cannot top up. Position risk = protocol risk + bridge risk. Keep rescue paths on the same chain as the position.


## 2026-08-29 — DeFi risk tip: MEV is not a bug in your position — it is a tax on it

Sandwich attacks around your swaps cost you basis points on every rebalance; liquidations are MEV too. Large positions get front-run because the profit is there. If you cannot avoid the swap, at least avoid swapping INTO a thin-margin window: do rebalances when HF has comfortable headroom.

