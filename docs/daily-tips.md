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


## 2026-08-30 — DeFi risk tip: Your biggest risk is usually your own key management

Cold wallets, hardware keys, and clear inheritance plans beat every DeFi strategy. A monitored position whose key is lost is a permanent, unmanageable exposure. If an exchange or custody holds your key, your 'self-custody' yield has a counterparty risk line-item you should price in.


## 2026-08-31 — DeFi risk tip: Read the admin keys section, not just the TVL

High TVL is not safety: check whether the protocol has upgradeable contracts, admin keys, or a timelock (Aave has a long timelock; many yield farms have none). A 2-day timelock means a compromised admin can still empty everything, just slowly. position-guard monitors YOUR position, not the protocol's health — do both.


## 2026-09-01 — DeFi risk tip: Keep liquidation math honest: the UI lags the blockchain

Dashboards poll; the chain doesn't. The HF you see on aave.com at 14:00:00 is stale by the time you read it. position-guard labels fixture vs live data and logs every snapshot with a timestamp for exactly this reason — audit your own alerts; trust nothing displayed more than a few seconds old.

> `position-guard history`


## 2026-09-02 — DeFi risk tip: The exit plan is part of the entry plan

Decide BEFORE you lever: what HF triggers a top-up, what triggers a full exit, what price of the collateral kills the thesis. Write it down next to the position (a comment in your own notes, not on-chain). Panic decisions in a red candle are how margin gets destroyed.


## 2026-09-03 — DeFi risk tip: Dust positions accrue real risk

A $50 collateral balance with a $45 debt at 0.5% borrow spread still liquidates at the same mechanics as a whale position — and no one will rescue it economically. Close or merge dust positions; the monitoring cost is the same as for a big one.

> `position-guard history --address 0xYourAddressHere`


## 2026-09-04 — DeFi risk tip: Rebalancing is a trade, not a chore

Every swap you do to 'optimize' the position pays spread + gas + MEV. Over-optimized positions that HODL quietly often beat churned ones. Only rebalance with intent: it should move the liquidation price materially or cut borrow APR — otherwise the fees are the only certain thing.


## 2026-09-05 — DeFi risk tip: The liquidation price of ETH collateral is closer than you think

Roughly: ETH liquidation price = debt / (ETH amount × liq threshold) with other legs ignored. At 0.825 threshold that is about 1.21× the price implied by HF alone — your '30% crash buffer' at HF 1.3 is really ~10% of pure ETH movement once USDC legs and bonuses are counted. Do the arithmetic on your own position.

> `position-guard check --address 0xYourAddressHere --json-out`


## 2026-09-06 — DeFi risk tip: Health factor below 1.0 is not a warning — it is a live auction

At HF < 1.00 your position is immediately liquidatable, and anyone can repay your debt to claim a discount on your collateral. There is no 'grace period'. Monitor HF with a buffer: act at 1.15, not at 1.01. position-guard's critical band starts there on purpose.

> `position-guard check --address 0xYourAddressHere --protocol aave-v3`


## 2026-09-07 — DeFi risk tip: The 1.12 trap: small HF looks fine until the chart gaps

A position at 1.12 HF has ~12% price room before liquidation on paper — but oracles update every block, and a flash-crash can move 12% in seconds. The dollar margin matters more: ~$763 of margin can evaporate in one CEX spike candle. Top up while the top-up is cheap.

> `position-guard check --address 0xYourAddressHere --json-out`


## 2026-09-08 — DeFi risk tip: Stablecoins are not stable — depeg risk is collateral risk

If your debt is in a stablecoin that depegs to $0.90, your dollar debt drops (good for you) — but if you HOLD that stablecoin as collateral and it depegs, your collateral USD value collapses while the protocol's oracle may lag or follow the exchange price (bad for you). Never borrow against a stablecoin's full nominal value.


## 2026-09-09 — DeFi risk tip: Oracle lag is a liquidation weapon

Aave and Compound price assets via oracles that can lag spot markets (especially during volatility and low liquidity). Liquidator bots watch for the moment oracle price crosses your liquidation price — they don't wait for 'fair value'. Assumed oracle = fast is the wrong assumption.


## 2026-09-10 — DeFi risk tip: Liquidation is not full loss — but it is rarely painless

When liquidated you lose up to the liquidation bonus (typically 5-10% of collateral) plus fees, and the remainder of the position survives. The worst outcome is being liquidated at the bottom of a dip: the bonus is taken from your collateral at exactly the worst price. Voluntary close-outs beat forced ones.

> `position-guard watch --address 0xYourAddressHere --interval 300 --telegram`


## 2026-09-11 — DeFi risk tip: APY is not your profit — APR vs APY vs realized

Protocols advertise APY (compounded) while many rewards stream as APR (simple). Realized yield is lower than headline APY once you account for gas to claim and compound, reward token price decay, and the tax event. Model yield before levering into it.


## 2026-09-12 — DeFi risk tip: The supply rate is paid to suppliers, not to the protocol

When you supply ETH to Aave you earn the supply rate, but your collateral's health contribution ignores interest — while your borrowed balance accrues interest continuously. Every block your HF ticks down silently. Long passive borrowing positions decay without any visible change in balances.

> `position-guard history --address 0xYourAddressHere`


## 2026-09-13 — DeFi risk tip: Unlimited approvals are a permanent backdoor

An approval from 2023 still lets that contract move your tokens. Revoke approvals you no longer use (revoke.cash, or a dedicated revoker). For position management, prefer 'spend limit = position size + buffer'; for monitoring bots, a read-only key or no key at all — position-guard needs only a public address.


## 2026-09-14 — DeFi risk tip: Testnet practice beats mainnet pain — and it is free

Every liquidation that could have happened for $3 of Sepolia ETH can be rehearsed: supply, borrow to the edge, let the HF drift, watch the state machine fire. position-guard's fixtures mimic exactly this shape. No amount of theory replaces one real forced-liquidation rehearsal.

> `position-guard demo --protocol compound-v3`

