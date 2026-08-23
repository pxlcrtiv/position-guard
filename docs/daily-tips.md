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

