# Lido DAO treasury revenue database (v1, 28 September 2026)

## What this series is

**Actual treasury staking-fee inflows, valued through the NEST oracle route at the inflow block.**

Actual staking fee inflows to the DAO treasury (treasury agent `0x3e40D73EB977Dc6a537aF587D48316feE66E9C8c`), one per daily rebase, from 1 January 2024 to 28 September 2026. The stETH amounts are actual, and the dollar value is calculated using historical Chainlink prices at the inflow block.

What the series is NOT:
- It is not the historical NEST counter. NEST does not track transfers to the treasury: after each rebase, `StakingRevenueSource` computes the treasury share from `sharesMintedAsFees` itself, accumulates it in stETH and converts it to USD in a separate `convertPendingRevenueToUSD()` call at the price at the time of that call. My stETH amount and the NEST amount match exactly (check 7), and the dollar valuation differs only in the timing of the price (check 8).
- It is not reported net revenue. My series is revenue after the node operators' share, but before the cost of revenue (referral payouts, possible operator discounts and so on). To compare it with Foundations expenses, these costs need to be subtracted as a separate layer.

## Files

| File | Contents |
|---|---|
| `treasury_fee_inflows.csv` | 1,002 rows, one per inflow. Transaction hash, log index, sender and recipient, stETH amount (raw and decimal), for each feed the proxy address, roundId, price, updatedAt and price age in seconds, USD total, stale price flag |
| `token_rebased_logs.json` | all `TokenRebased` events of the stETH contract since 31 December 2023 (1,003 in total) |
| `agent_incoming_steth.json` | all incoming stETH transfers to the treasury since 2024, including 73 non-fee transfers from other addresses (excluded, see check 2) |
| `rounds_state.json` | raw `latestRoundData()` responses from both feeds at each block |
| `nest_checkpoints.csv` | all NEST budget checkpoints with transaction hashes |
| `nest_revenue_conversions.csv` | all NEST revenue conversions to USD: stETH, stETH/USD price, USD amount, hash |
| `validation_results.json` | check results |

Derived daily series for the model: `../data/revenue_composite.csv`.

## Sources

| What | Where from |
|---|---|
| Inflows before 24 December 2025 | stETH transfers from the zero address to the treasury agent (fee mint on rebase) |
| Inflows from 25 December 2025 | daily stETH transfers from the Lido V3 Accounting contract (proxy `0x23ed611be0e1a820978875c0122f92260804cddf`) |
| ETH/USD | Chainlink proxy `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419` |
| stETH/ETH | Chainlink proxy `0x86392dC19c0b719886221c78AB11eb8Cf5c52812` |
| NEST route | OracleRouter `0x79ef3a538200Fe4981D67E7e886bfb36D4Cb5a31`: both proxies currently point exactly to the aggregators the router uses (`0x7d4E…6Fb5` and `0xC9c8…825c`) |
| NEST | BuybackAllocator `0xAA568141c051f2D1132b110f8391F18D48E8D889`, StakingRevenueSource `0x6220212a33a87Ed7Cc386B67eB2c393974F28C38` |

Formula: `usd = steth × steth_eth × eth_usd`.

## Checks (all passed)

1. **One inflow per UTC day, with no gaps.** 1,002 rows for 1,002 days.
2. **Every inflow is in a rebase transaction.** 1,002 out of 1,002. None of the 73 transfers from other addresses is in a rebase transaction, so they are not fees.
3. **Every rebase since 2024 has exactly one matching inflow.** One-to-one correspondence.
4. **The ETH/USD price is fresh.** The feed's update interval is 3600 s. Two rows exceed it by 24 and 36 s (the usual delay before an update lands in a block), and they are flagged in `price_flag`. Median age is 1,416 s.
5. **The stETH/ETH price is fresh.** Maximum age is 85,644 s against an interval of 86,400 s.
6. **No prices "from the future".** Every updatedAt is no later than the inflow block.
7. **The stETH amount NEST counted for itself equals the actual inflow to the treasury.** 45 rebases in the same transaction, with a difference of 0 stETH.
8. **Dollar valuation against the NEST counter.** (Aggregate accuracy; for individual NEST conversions the difference ranges from −2.9% to +1.1%, 0.30% on average, and the errors partly cancel each other out.) 44 rebases before the last checkpoint (28 September 2026 00:35 UTC, tx `nest_checkpoints.csv`): NEST converted 1,793.2227 stETH, and the same amount arrived in the treasury. The counter shows $4,381,599.99, my valuation is $4,379,657.84, a difference of −0.044%. The only reason is the timing of the price: I value at the inflow block, NEST at the conversion block.
9. **The NEST budget is reproduced using the contract formula.** `budget = 50% × (revenue per counter − $109,589 × number of daily slots)`, where slots are counted from the activation day, 10 August 2026, inclusive, to the checkpoint day inclusive. All 32 checkpoints match with an error of $0.00. For example, on 21 September 2026 (tx `0x89c2a140…70ebf`): 0.5 × (3,602,980.34 − 43 × 109,589) = −554,673.33.

Note on check 9: earlier, the $54.8k discrepancy in my replication was explained as "half a day". That was wrong. The reserve accrues in discrete daily slots, and the first replication missed one slot: 1 × $109,589 × 50% = $54,794.50. This also explains why at the time of a checkpoint (~00:35 UTC) the budget is one slot lower than an accounting based on completed days: the reserve for the new day has already accrued, while its revenue will come with the rebase at ~12:20 and will be counted by the next checkpoint. This is how the mechanism works by specification, not a loss of revenue.

## NEST launch (corrected 29 September 2026)

The allocator was activated on 10 August 2026 at 13:01 UTC, after that day's rebase (12:21 UTC). By specification, current revenue becomes the starting point at activation, so NEST should not count the revenue of 10 August. The revenue source was connected by Dual Governance proposal #13 on 14 August 2026 at 13:23 UTC, after that day's rebase. The rebases of 11–14 August were not counted: $295,317. Starting budget scenarios (not additive): as in the contract, −$548,925; including the revenue of 11–14 August, −$401,267 (adjustment +$147,658); reserve only from the first full day of operation, 15 August, −$274,953 (adjustment +$273,973). The adjustment of +$184,812 stated earlier was wrong: it included the revenue of 10 August before activation.

## True-up against Lido reports

See `../data/reconciliation_reports.csv` (all report figures with sources).

- 2024 and 2025: my series ($51.54M and $41.50M) minus net staking revenue per the report ($48.5M and $37.4M) = $3.04M and $4.10M, against reported referral payouts of $3.1M and $4.1M. The remainder is within the report's rounding ($0.1M) and the difference in valuation methods (the report uses the end-of-day price, I use the price at the block).
- H1 2026: my series $16.97M minus net revenue $15.71M = $1.26M. This is the remaining cost of revenue. Under Lido's methodology it includes referral payouts and possibly operator discounts; the report has no breakdown for H1, so I do not call the whole remainder referral payouts.
- The comparison uses the H1 2026 report methodology. In the original Q1 2026 report, treasury management income was included in revenue ($9.42M); in the H1 report it was moved to treasury movements, and Q1 is shown as $8.83M.

## Reproducibility

All data is public. Any row can be checked by its transaction hash in an explorer, and the price by reading `latestRoundData()` of the Chainlink proxy at the given block through an archive node. A spot re-check of 8 random blocks through an independent RPC gave 8 out of 8 exact matches.

## Known limitations

- The dollar valuation is calculated and depends on the choice of price timing. For the NEST model it is an approximation accurate to about 0.05%, and for comparison with reports about 0.1–0.3%.
- Since 25 December 2025 the fee goes through a distributor; I take the actual transfer from the distributor to the treasury, not the calculated share.
- The cost of revenue (referral payouts and so on) is not included in the series and must be modelled as a separate layer.
