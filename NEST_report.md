# NEST: a detailed review with each point checked

For each point: what I claim, what questions the team or a delegate might ask, how I checked it and what came out.

## Point 0. How NEST works

### Description of NEST

NEST is a Lido DAO mechanism that automatically buys back LDO with part of the treasury's staking revenue. It has been running since 10 August 2026.

Two things in it need to be kept apart. The **budget** is a counter in the contract showing how much NEST is allowed to spend; it rises and falls with revenue, can go negative and holds no money itself. The **stETH balance** is real money that the treasury transfers to the allocator in advance and that pays for the buybacks; a negative budget does not touch it. These are the two main necessary conditions for a purchase: a budget above zero and stETH on the allocator. Beyond them, the contract checks that an oracle price exists, that stETH is not below the floor, that the amount is not below the minimum allocation and that it fits within the daily and annual caps.&#32;

Money and decisions pass through a chain of five steps.

1. **Revenue source** (StakingRevenueSource 0x6220…8C38). After each daily rebase, the Lido report dispatcher (TokenRateNotifier 0xbe05…791b) passes it the report data, including the protocol fee; the source calculates the treasury's share of the fee and accumulates it in stETH. A separate call converts the accumulated amount into dollars at the oracle price.
2. **Oracle** (OracleRouter 0x79ef…5a31). Provides the stETH price in dollars from Chainlink: stETH/ETH × ETH/USD.
3. **Allocator top-up: the treasury transfers stETH to the allocator.** This step is not in the NEST code, and it is not automatic. The transfer is made through an Easy Track motion: an authorised participant proposes the transfer, LDO holders have 72 hours to object, and if objections total less than 0.5% of all LDO, the transfer is executed.** The limit for this program is 12,000 stETH per half year, and it is shared with stETH sales for stablecoins, which the DAO uses to pay expenses.**
4. **Allocator** (BuybackAllocator 0xAA56…8D889). Decides how much money can be spent on buybacks and releases it to the executor. Why this is needed: not all staking revenue should go to buybacks, only the part above a threshold set by a DAO vote. So the allocator keeps a counter, the buyback budget. Each day a reserve of $109,589, which is $40M per year, is subtracted from the counted revenue. The reserve is an accounting threshold inside the formula, not money set aside: the contract does not set anything aside and does not compare this threshold with either the treasury balance or the DAO's actual expenses. If revenue for the day is above the reserve, half of the excess is added to the budget; if it is below, half of the shortfall is subtracted. Example: revenue for the day is $120,000, the excess is $10,411, the budget grows by $5,206; revenue is $100,000, the shortfall is $9,589, the budget falls by $4,795. When the budget is above $1,000, the allocator transfers stETH for that amount to the executor from the balance held on the allocator, but no more than $50k per day, $10M per 365 days from activation, and no more than the balance itself. If the budget has gone negative, it stays that way, and buybacks will start only when future good days pay it off.
5. **Executor** (BuybackExecutor 0x6c21…C9B7). Receives stETH and sends it to Stonks, which sells stETH for LDO through CoW Swap. The purchased LDO go to the treasury or, in the second mode, together with the other half of the stETH wrapped into wstETH, into the Curve LDO/wstETH liquidity pool.

**What Stonks is.** It is a Lido contract for swapping treasury tokens through CoW Swap without manual involvement. It is given a token to sell (here stETH), and it places an order to swap it for another token. Stonks calculates the minimum amount to be received by itself, from the Chainlink oracle price minus a margin (currently 1.1%, the MARGIN\_IN\_BASIS\_POINTS = 110 field on Stonks 0xb368…F151), and the trade cannot execute worse than this minimum. This is protection relative to the oracle price, not the current market price: if the oracle price lags the market, the trade may execute worse than the current market, but not worse than the minimum calculated from the oracle. An order lives for 30 minutes (ORDER\_DURATION\_IN\_SECONDS = 1800): if CoW Swap has not found a buyer at that price within this time, the order expires and can be placed again. Stonks sends everything it receives directly to the recipient written in the contract, usually the DAO treasury. Each Stonks has one token pair: the DAO has separate Stonks for stETH → DAI, stETH → USDC, stETH → USDT, and a separate one for stETH → LDO, which NEST uses.&#32;

Below are the allocator parameters as they are recorded in the contract as of 30 September 2026, and what each one controls.

| Parameter | Value | What it determines |
| --- | --- | --- |
| Reserve | $109,589 per day ($40M per year) | the revenue level at which a surplus appears |
| Share | 50% | what part of the excess over the reserve goes to buybacks |
| Negative budget | stored without limit | how many past weak days have to be worked off |
| Minimum allocation | $1,000 | the threshold for triggering a trade |
| Daily cap | $50,000 | the pace of going to market |
| Annual cap | $10M per 365 days | the annual volume |
| Price floor | $0 | the minimum stETH price in dollars below which the allocation is skipped |

### Findings

**The NEST budget is currently at a deficit of $542,451** (recalculation of 30 September 2026), and in a month and a half the mechanism has not released a single dollar for buybacks. The contract stores only a single budget number, but it can be broken down against other reference points to understand where the deficit came from:

| Part of the deficit | Amount | Share | What it is |
| --- | --- | --- | --- |
| Revenue from 11–14 August that the mechanism did not see | about $147,700 | 27% | "artificial" debt: the revenue reached the treasury, but the revenue source had not yet been connected to the mechanism (details in point 1) |
| Reserve for the current day | $54,795 | 10% | not debt but a snapshot timing effect: the reserve for today has already been deducted, while today's revenue will arrive during the day with the rebase and will go into the next recalculation |
| Remainder after the two adjustments above | about $340,000 | 63% | the part that can no longer be explained by either the launch or the snapshot timing: revenue was on average below the reserve of $109,589 per day. At the current amount of staked ETH and the current DAO share of the fee, the treasury's annual revenue reaches the $40M reserve at an ETH price of roughly $2,668 |

This is my analytical breakdown; the contract has no such categories. By this breakdown, roughly a quarter of the debt arose not from economics but from the order in which the mechanism was launched, and another tenth is a quirk of the moment at which the budget is calculated.

**Why the reserve is deducted before the revenue.** The contract itself does not run on a schedule: the budget is recalculated when someone calls allocate(). LIP-36 provides for a bot (keeper) that regularly polls the contracts and makes the necessary calls; according to the observed history, recalculations that open a new day happen around 00:15–00:35 UTC. At that moment the contract immediately deducts the reserve for the whole new day, while that day's revenue arrives only around 12:20 UTC with the rebase and is counted at the next recalculation. This is how the developers intended it: the code explicitly says that the reserve accrues "at the start of the day" and that even for the activation day it "is charged, not forgiven". This is a conservative choice: the mechanism first reserves the DAO's money and only then counts revenue. So in an ordinary snapshot between the nightly recalculation and the next one, the budget already includes the reserve for the new day but not yet its revenue: even if the rebase has happened and the revenue is already sitting in the source, it will reach the budget only at the next recalculation.

**There is no direct historical correction of the budget.** The contract has no function that changes the already accumulated budget, and reactivating the mechanism is impossible, so the missed revenue of 11–14 August cannot be written into the history retroactively. A vote can only create a compensating correction going forward by changing parameters: for example, by temporarily lowering the reserve. Each day with the reserve lowered by X adds exactly half of X to the budget, regardless of revenue, and the reserve can be set to any value, not only zero. So in principle the amount can be matched closely or exactly to $147,658. But the new reserve applies only to days after the vote, and the old one can be restored only by another vote, so the final amount depends on how many days pass between the votes and cannot be fixed precisely in advance. Economically such a correction can be equivalent, but it will not restore the historical record.

**The allocator top-up is manual, and this is the second barrier after the deficit.** The allocator currently holds 41.08 stETH, about $110k; there has been one top-up, on 28 August 2026 (Easy Track motion #1129; the same motion also sent 3 × 1,000 stETH for sale for stablecoins). While the budget is negative, this is no obstacle. But once it turns positive, NEST will be able to buy no more than \~$110k worth until the next motion. For the $10M annual cap at the current stETH price of about $2,700, about 3,700 stETH is needed, while 3,959 stETH remain in the shared limit until 1 January 2027, and the same stETH is needed to pay expenses. In other words, NEST's actual purchases depend on whether someone submits a motion in time and how much of the limit is left.

**Purchased LDO currently go straight to the treasury.** The executor also has a second mode: half of the allocated money goes to LDO, and the purchased LDO together with the other half are deposited into the Curve LDO/wstETH liquidity pool. It is currently switched off.

**The price floor applies to the stETH price, not LDO.** The allocator has no condition on the LDO price, but at the purchase itself the order through Stonks and CoW Swap requires no less than the oracle estimate minus 1.1%.

### Questions I asked

1. Is the formula in the contract really like this, and when exactly is the budget recalculated?
2. What are the parameters right now, rather than as described in the LIP?
3. Who can change the parameters and how quickly do changes take effect?
4. Can the budget be corrected once, for example for the deficit that arose from the launch sequence?
5. How does the mechanism learn about revenue and at what price does it convert it into dollars?
6. What does the price floor apply to, and is there price protection when buying LDO?
7. Where does the mechanism get the money for purchases?
8. Where do the purchased LDO go?
9. Who triggers allocations and orders?

### How I collected the data

- Downloaded the verified source code of all four contracts from Blockscout and read the logic of the budget, allocation, revenue accounting and execution.
- Read the current on-chain state of the contracts at block 26,089,399 (30 September 2026): parameters, budget, cap windows, executor mode, Stonks settings.
- Collected all staking fee receipts to the DAO treasury for every day from 1 January 2024 to 28 September 2026, 1,002 days: until 24 December 2025 this is stETH minted to the treasury at the rebase, after that transfers from the Accounting contract of Lido V3. I valued each receipt in dollars at the same Chainlink prices that NEST uses and reconciled it with the mechanism itself: the amount of stETH matched what NEST had counted to the last digit, and the budget formula reproduced all 32 on-chain recalculations with an error of $0. Details on this base are in point 2.
- Checked the role holders: who can change parameters, withdraw assets and pause the mechanism.
- Traced the stETH and LDO transfers through the allocator, executor, Stonks and CoW Swap orders.
- Analysed the allocator top-up transaction of 28 August: which mechanism it went through (Easy Track motion #1129), from which program and with which limits.
- The source code and the state snapshot are saved in the contracts folder next to the other research files.

Where to check each figure in point 0:

| What | Where | Value |
| --- | --- | --- |
| Parameters, budget, cap windows, executor mode | contract reads at block 26,089,399 (30.09.2026) | budget budgetUSD = −$542,451; stETH balance on the allocator 41.08 |
| Allocator activation | transaction 0xd34730fe6f821e3f05eff51f1606276e10eaf40c5854e2d2793a1cd1373d8aee, block 25,724,759 | 10.08.2026 13:01:23 UTC |
| Connection of the revenue source to rebases | transaction 0x5a7868439de1003dc5f3d7ecf99826410c17883794bcd38ff75dd0e0bcce57c4, block 25,753,465, ObserverAdded event on TokenRateNotifier | 14.08.2026 13:06 UTC |
| Allocator top-up | Easy Track motion #1129, transaction 0x238c01651dae39680b0c8f4b311dda4e9336d39d17c74b8acd65cb8e92ee1772 | 28.08.2026, 41.0 stETH to the allocator and 3 × 1,000 stETH to Stonks for stablecoins |
| Top-up program limit | recipient registry 0x1a7cFA9EFB4D5BfFDE87B0FaEb1fC65d653868C0: getLimitParameters and getPeriodState | 12,000 stETH per 6 months; in the period until 01.01.2027, 8,041 spent, 3,959 left |
| Price protection at purchase | Stonks stETH → LDO 0xb368586CB980895E51e1D82102E63b3F69d3F151: MARGIN\_IN\_BASIS\_POINTS, ORDER\_DURATION\_IN\_SECONDS | 110 (1.1%), 1800 seconds |
| Test trade | transactions 0x55e81ab1ce8c95a9024beff90a720dd7f326371192f813fc8a15ec3132a63bac and 0xf03550dfda19de664573c8b24c8c3206ad0cfb9be22e994a1c2e8c59776659ac | 13.08.2026, 1.001 stETH through Stonks and CoW Swap |

### Results

Below are the answers to each of the nine questions: what the code and contract state showed and where exactly this can be seen.

| Question | Answer | Where it can be seen |
| --- | --- | --- |
| 1. Formula | Yes: budget change = (new revenue − accrued reserve) × share. The reserve for the new day is deducted immediately at recalculation, before the revenue arrives (details above). The budget changes only when allocate() is called or parameters are changed; a deficit is stored and treated as zero for allocation. | functions \_budgetable, \_reserveCurrentUSD, \_checkpoint, \_clampBudget |
| 2. Parameters now | Reserve $109,589 per day, share 50%, daily cap $50,000, annual $10M, minimum allocation $1,000, floor $0. Activation by a transaction on 10.08.2026 at 13:01 UTC; for reserve accrual and cap windows, the activation day is the whole of 10 August from 00:00 UTC, with the annual window until 10.08.2027. Budget −$542,451 after the recalculation of 30 September. Not a single allocation so far: $0 spent. | reading the contract state |
| 3. Who changes parameters | The main role belongs to the Lido voting contract (Aragon Voting 0x2e59…618e), that is, only through a DAO vote. Before a change of share or reserve, the budget is recalculated, and new values apply only going forward. The manager role (withdrawing assets to the treasury, withdrawing liquidity) belongs to the Safe multisig 0xa02F…D647, which per LIP-36 is the Treasury Management Committee. | roles DEFAULT\_ADMIN\_ROLE and MANAGER\_ROLE |
| 4. Direct budget correction | No, there is no such function, and reactivation is impossible. Workarounds are described above. | list of contract functions |
| 5. Revenue accounting | At a rebase, the source takes the treasury's share of the fee according to the current StakingRouter distribution and accumulates it in stETH. The accumulated amount is converted into dollars by a call to convertPendingRevenueToUSD (anyone can make it) at the oracle price at the moment of conversion. This is what I modelled. | StakingRevenueSource.pushTokenRate, convertPendingRevenueToUSD |
| 6. Floor and price protection | The floor applies to the stETH price and is currently 0. There is no condition on the LDO price. Price protection at purchase is on Stonks: no worse than the oracle minus 1.1%. The size of one order on the executor is from 1 to 20 stETH. | \_spendable, Stonks and executor parameters |
| 7. Where the money comes from | Only from the stETH on its own balance, currently 41.08 stETH. The top-up is manual, via an Easy Track motion, and is not in the NEST code (details above). | allocation is limited by the balance; Easy Track motion #1129, transaction 0x238c…, 28.08.2026; recipient registry 0x1a7c…68C0 |
| 8. Where the LDO go | Currently straight to the treasury. The liquidity mode is off; in it, the Curve pool LP tokens stay with the executor, and the manager can withdraw them to the treasury. | lpModeEnabled = false, Stonks.RECEIVER = treasury, onStEthAllocated, addLiquidity |
| 9. Who triggers | Budget recalculation (allocate), order placement (placeOrder) and liquidity deposit (addLiquidity) do not run by themselves; anyone can call them. The LIP-36 specification provides a bot (keeper) for this: an automated script polls the contracts and calls revenue conversion into dollars, allocation, orders and liquidity deposits. Recalculations do in fact run daily around 00:15–00:35 UTC. The executor can be paused by two multisigs with the emergency pause role, which per LIP-36 are Emergency Brakes and the Treasury Management Committee. | function modifiers, EMERGENCY\_ROLE role |

Two details. On 13 August a multisig sent 1.001 stETH to Stonks, and this order was executed through CoW Swap: this was a test trade to check the route, not a buyback from the NEST budget. And according to a comment in the code, the daily cap is counted over a midnight-to-midnight UTC window, so around midnight almost two daily caps can be spent in a row; the annual cap and the budget still limit the total.

### Conclusions for point 0

- **My model correctly reproduces the contract.** The model is the nest\_model.xlsx spreadsheet and Python scripts in which I ran the NEST rule and its variants day by day on real revenue. The contract calculates the budget in exactly the same way, so the model results in the following points can be read as what the real NEST would have done under the same conditions. One exception: the model does not account for the stETH balance on the allocator; more on this below.
- **The contract has no direct historical correction of the starting deficit.** There is no function for changing the accumulated budget. The deficit can only be compensated by changing parameters going forward, and the final amount of such a correction depends on how many days pass between votes.
- **The allocator top-up mechanism is defined, but the rule for its regularity and size is not.** Easy Track sets who can transfer stETH and within what limit, and gives holders 72 hours to object. But neither the NEST contract nor the top-up program requires a certain balance to be kept on the allocator. On top of that, stETH for NEST and stETH for paying expenses come from the same limit of 12,000 stETH per half year. This is a treasury planning issue, not a code issue. A constraint on the stETH balance needs to be added to the model.
- **If the liquidity mode is switched on, half as much LDO will be bought with the same budget.** In this mode the executor sells only half of the received stETH for LDO and keeps the other half to deposit it into the Curve pool together with the purchased LDO. The model currently assumes that the whole allocated amount goes to LDO, so in this mode its figures for the amount of LDO bought will need to be halved; the amount the allocator releases does not change.
- **Any parameter changes go only through a DAO vote and apply only going forward.**

### Open questions

- Who submits motions to top up the allocator and by what rule, will the top-up be regular or automatic, and why does NEST share a limit with stETH sales for paying expenses rather than having its own?
- Is the liquidity mode planned, and under what conditions?
- Who holds the two multisigs with emergency roles, and who runs the bot (keeper), that is, the automated script that regularly polls the contracts and calls budget recalculation and order placement when needed?

### What to check next

- **Point 1, the starting point:** use the transaction logs to check the exact time the revenue source was connected to rebases, and recalculate the starting budget scenarios taking into account that a correction is possible only through a temporary reserve reduction.
- **Allocator top-up:** the mechanism has already been established (Easy Track, a shared limit of 12,000 stETH per half year); next, find in LIP-36 and in the discussion of motion #1129 how the allocator is planned to be topped up and who submits motions, and add a constraint on the stETH balance and the shared limit to the model.
- **Liquidity mode:** check the state of the Curve LDO/wstETH pool and recalculate the effect on LDO supply for both modes.
- **Bot:** find which address the bot (keeper) calls allocate() from and who runs it, and check that the daily recalculations run without gaps.

## Point 1. The starting point: the current deficit and the effect of the launch sequence

### Description

The starting point is the NEST budget at the time of checking and how quickly it can get out of deficit. After the recalculation of 30 September 2026, the budget stands at −$542,451; how it can be broken down is shown in point 0. Part of the deficit arose from the order in which the mechanism was launched. It can only be compensated by a future governance decision. The team may or may not support such a correction, and the DAO makes the final decision, so I calculate the results both with and without compensation.

The launch went in two stages, and this was announced in advance: on 10 August, after vote #204 was executed, the team wrote on the forum that full activation of NEST would follow the execution of Dual Governance proposal #13, and on 14 August it announced that the proposal had been executed and NEST was fully activated. So this is not a proven error but a measurable effect of that sequence.

### Findings

- **The launch sequence created a measurable starting deficit.** The allocator was activated on 10 August at 13:01 UTC, after that day's rebase, so under the rules NEST should not count the revenue of 10 August. The revenue source was connected to rebases only on 14 August: the ObserverAdded event in block 25,753,465 at 13:06 UTC, also after that day's rebase; the team's public announcement of full NEST activation appeared at 13:23 UTC. As a result, NEST did not see the revenue of four rebases, 11–14 August: 156.26 stETH, about $295,300. The reserve for those days, meanwhile, accrued as usual. With a NEST share of 50%, this reduced the budget by **$147,658** compared with a scenario in which the revenue source would have worked right after activation.
- **Separately, I calculate a stronger scenario as a sensitivity check.** If we assume that the reserve should not have accrued at all until the first full day of operation of the fully connected system, 15 August, the starting budget would have been higher by **$273,973** (5 days × $109,589 × 50%). This is not a correction under the rules: the LIP-36 specification explicitly requires the reserve to accrue from the activation day. This scenario is needed only to see how sensitive the result is to the starting point.
- **The starting correction mainly affects timing.** A compensation of +$147,658 shortens the time to the first purchase by about 27%, and the +$273,973 scenario by about half. But at an ETH price slightly above the break-even threshold, getting out of deficit still takes years, and in random price scenarios, in roughly 44–51% of paths depending on the starting budget, NEST does not reach its first purchase within 12 months.

### Questions I asked

1. Was the revenue source really connected after the rebase of 14 August, and how many rebases were missed?
2. What size of compensating correction corresponds to the uncounted revenue under the current NEST parameters?
3. How much does compensation speed up the budget's exit from deficit and increase buybacks?
4. What happens if the compensation is not adopted?

### How I collected the data

- Found on-chain the event connecting the revenue source to the Lido rebase dispatcher (TokenRateNotifier 0xbe05…791b, ObserverAdded event, transaction 0x5a78…57c4) and compared its time with the rebase times from my receipts base.
- Checked on the forum how the team announced the launch stages.
- Ran the model forward for 12 months from 1 October 2026 starting from the actual budget of −$542,451 in three variants: without compensation, with compensation of +$147,658 and with the +$273,973 scenario.
- Calculated in two ways: at a constant ETH price and on 4,000 random ETH price paths with the same calibration as in the main stress test (volatility of 61% per year with no trend); the engine also generates the LDO price, but it does not affect the metrics of this point.

### Results

Table 1. How many days after 1 October NEST makes its first purchase at a constant ETH price, and how much it buys over 12 months.

| ETH price | Without compensation (actual budget) | Compensation +$147,658 | Scenario +$273,973 (sensitivity check) |
| --- | --- | --- | --- |
| $2,680 | after 2,291 days (\~6.3 years); $0 over 12 months | after 1,669 days (\~4.6 years); $0 over 12 months | after 1,136 days (\~3.1 years); $0 over 12 months |
| $2,700 | after 838 days (\~2.3 years); $0 over 12 months | after 610 days (\~1.7 years); $0 over 12 months | after 415 days (\~1.1 years); $0 over 12 months |
| $2,750 | after 324 days, $0.07M | after 236 days, $0.22M | after 160 days, $0.34M |
| $2,800 | after 201 days, $0.44M | after 146 days, $0.59M | after 99 days, $0.72M |
| $3,000 | after 79 days, $1.94M | after 58 days, $2.09M | after 39 days, $2.22M |
| $3,500 | after 31 days, $5.69M | after 23 days, $5.84M | after 15 days, $5.96M |

All values were calculated with the daily engine; for $2,680 and $2,700 the calculation was extended 9 years forward at the same price, with buybacks counted over the first 12 months. At the current stake volume and the current fee structure, the treasury's annual staking revenue reaches the $40M reserve at roughly ETH $2,668, so at a price only slightly above this level the budget grows very slowly. The reduction in time is almost exactly proportional to the starting deficit: compensation gives −27%, the +$273,973 scenario gives −51%.

Table 2. Random ETH price paths, 4,000 paths, 12 months from 1 October.

| Variant | First purchase within 3 months | Within 6 months | Within 12 months | Median day of first purchase (among paths where it happened) | Average buybacks per year |
| --- | --- | --- | --- | --- | --- |
| Without compensation | 25% | 40% | 49% | 89 | $2.30M |
| Compensation +$147,658 | 32% | 44% | 52% | 75 | $2.37M |
| Scenario +$273,973 | 38% | 48% | 56% | 58 | $2.44M |

### Conclusions for point 1

- **The effect of the launch sequence is real, but it is not the main reason NEST is inactive.** The most directly measurable effect of the launch sequence: the actual budget is $147,658 lower than it would have been if NEST had counted the staking revenue for 11–14 August. This is 50% of the uncounted revenue of about $295,300; there is no separate record of this in the contract, it is the difference between the actual budget and the alternative scenario.
- **Compensation noticeably changes timing but barely changes volume.** The time to the first purchase shortens by about 27%, while average annual buybacks in the price stress test rise only from $2.30M to $2.37M, by about $70k. NEST's behaviour is determined much more strongly by future revenue relative to the $40M threshold and by the rule under which the deficit accumulates; these are the next points.
- **From here on I calculate the main results for two starting budget variants:** the actual −$542,451 and with compensation −$394,793. I keep the +$273,973 scenario only as a sensitivity check.
- **If the stETH balance on the allocator stays unchanged,** purchases after the budget turns positive will additionally be limited to roughly 41.08 stETH (about $110k at the price at the time of the snapshot). Before the first purchase, the allocator may be topped up with a new Easy Track motion.

### Open questions

- Will the team support the compensation and will the DAO approve it, and what is the most correct way to carry it out in the current contract?
- Was the gap between activation on 10 August and the connection of the revenue source on 14 August consciously accepted as the price of a two-stage launch, or was its effect on the budget not taken into account?

### What to check next

- **Point 2, data:** go through the checks of the receipts base again, along with the true-up against Lido reports.
- **Model:** add a constraint on the stETH balance on the allocator to the calculation and keep the rule results in two starting budget variants.

## Point 2. Data

### Description

All model calculations rely on several datasets:

1. **Treasury staking revenue by day.** Actual fee receipts to the DAO treasury (Aragon Agent 0x3e40…9C8c) over 1,002 days, from 1 January 2024 to 28 September 2026. Until 24 December 2025 this is stETH minted to the treasury at the rebase, after that transfers from the Accounting contract of Lido V3.
2.
3. **Prices.** Each receipt is valued in dollars via Chainlink (stETH/ETH × ETH/USD) at the receipt block; this is the same oracle route that NEST uses.
4. **Data from NEST itself:** revenue accumulations and conversions, budget recalculations, current contract state.
5. **Data from Lido reports:** Foundations expenses, costs of earning revenue, Earn revenue, treasury income, one-off losses, report publication dates, the approved EGG-2026 budget.
6. **Daily LDO prices** from DefiLlama (needed only to count the amount of LDO bought).

In this point I re-check the first dataset, on which everything else rests, and its link to NEST and to the reports.

### Findings

- **The base is complete and matches NEST.** 1,002 days with no gaps or duplicates, one receipt per rebase. The amount of stETH matches what NEST counted to the last digit, and the budget formula reproduces all 32 early recalculations and the latest one, of 30 September (−$542,451.22), to the cent.
- **On 25 December 2025 the treasury's effective share of the protocol fee rose from 48.3% to 62.0%.** The average amount of fee the protocol accrued at the rebase stayed at about 67.8 stETH per day before and after this date, while treasury receipts jumped by 29%, from \~32.8 to \~42.3 stETH per day. The reason is the change in Curated Module fees (discussion research.lido.fi/t/10876; according to the Lido report, vote #195 was executed on 24 December): the total protocol fee remained 10%, but the Curated Module operators' share was reduced, and most of the fee began to go to the DAO. This is not a duplication in the data but a change in the distribution regime: the history before and after this date falls under different rules.
- **There is revenue that neither NEST nor my series sees: the CSM module rebate.** Once a month the FeeDistributor contract of the CSM module (0xD99C…8D0) transfers to the treasury the part of the module fee that does not go to operators (RebateTransferred event). Since October 2025 this has amounted to 341.8 stETH, about $0.80M, and the amount is growing: from 12.9 stETH in October 2025 to 34.3 stETH in September 2026. At the current annual run rate this is about 1.2 stETH per day, 3% of the main receipts, roughly $1.2M per year at ETH $2,680; the rate is growing and need not stay at the September level. If this flow were connected to NEST as a separate revenue source with the share kept at 50%, the budget would be replenished by roughly $0.6M more per year, before caps and other constraints.
- **One more small income flow also reaches neither NEST nor my series.** In total the treasury received 1,100 stETH transfers: 1,002 are the fee at rebases, 13 are CSM rebates, and 41 are transfers from the CSM module accounting contract (0x4d72…e5Da) totalling 9.84 stETH over a year and a half. The latter are charges deducted from CSM operators' bonds, for example for key removal (BondCharged and KeyRemovalChargeApplied events), that is, minor DAO income. The rest are 25 mints from December 2023 outside my period and one-off transfers from multisigs, which I consider refunds but did not check individually.
- **The dollar valuation is accurate in total but not by day.** In total my valuation differs from the NEST counter by −0.044%, on individual days from −2.9% to +1.1%, on average by 0.30%: NEST converts revenue into dollars later and at a different oracle price.

### Questions I asked

1. Is the series complete: one receipt per day, with no gaps or duplicates?
2. Is this the same revenue that NEST sees?
3. Are the receipts valued correctly in dollars?
4. What did I exclude from the series, and did I lose any revenue?
5. Did anything change in the receipts themselves over the period?
6. Does the series reconcile with Lido reports?

### How I collected the data

- Collected all incoming stETH transfers to the treasury from December 2023 to 28 September 2026 (1,100 transfers) and all TokenRebased rebase events (1,003), and matched them by transaction.
- For each receipt, read the Chainlink prices at the same block, with the round number and the price update time.
- From the rebase events, calculated what fee the protocol accrues at each rebase and what share of it comes to the treasury.
- Identified the senders of all transfers that were not included in the series and analysed the events in the CSM module transactions.
- Reconciled the series with the 45 revenue accumulations and 45 conversions in NEST, with the 32 budget recalculations and with the current state of the allocator.
- Reconciled annual and half-year totals with Lido reports: the GOOSE-2025 Final Report, and the reports for Q1 and H1 2026.

### Results

Below are the results of the checks of the receipts base.

| Check | Result |
| --- | --- |
| One receipt per day | 1,002 days, 0 gaps, 0 duplicates |
| Every receipt in a rebase transaction, one receipt per rebase | 1,002 of 1,002 |
| Amount of stETH vs NEST | matches to the last digit on all 45 days of NEST operation |
| Dollars vs NEST | −0.044% in total; by day from −2.9% to +1.1%, on average 0.30% |
| Price freshness | ETH/USD no older than an hour, except 2 cases that were 24 and 36 seconds over; stETH/ETH no older than 23.8 hours with 24 allowed |
| Budget formula vs on-chain | 32 early recalculations and the recalculation of 30.09.2026 reproduced with an error of $0 |
| Source change on 24/25 December 2025 | no gap or duplicate; the treasury's effective fee share went 48.3% → 62.0% after the change in Curated Module fees; average total fee \~67.8 stETH per day before and after |
| Excluded transfers | 98: 13 CSM rebates (341.8 stETH), 41 charges on CSM operators' bonds (9.84 stETH), 25 mints from December 2023, one-off transfers from multisigs |

True-up against Lido reports:

What the costs of earning revenue are. This is money the DAO gives away from the fee it receives in order to earn that fee; in Lido reports it is subtracted from gross staking revenue (Staking Revenue Deductions) to get the net figure. The main item is referral payouts to partners who bring deposits into staking; under Lido's methodology this also includes rebates of part of the fee to operators. My series and NEST count the fee before these payouts, so my series is larger than the reported net revenue, and the difference shows the size of these deductions.

| Period | My series minus net staking revenue per report | What explains the difference |
| --- | --- | --- |
| 2024 | $3.04M | referral payouts per report $3.1M |
| 2025 | $4.10M | referral payouts per report $4.1M |
| H1 2026 | $1.26M | residual deductions from staking revenue; under Lido's methodology these are primarily referral payouts and rebates to operators, but the report has no breakdown, so the exact composition of these $1.26M cannot be established |

Separately: in 2025 the costs of revenue were 9.9% of my series, and in the first half of 2026 7.4%, and the reports do not show why they differ.

### Conclusions for point 2

- **The base is reliable for the model.** It is complete, reconciles with NEST to the stETH and to the cent of the budget, and agrees with the reports for 2024 and 2025 to within the referral payouts.
- **My series accurately reproduces the revenue that the current NEST measures, but not all of the treasury's staking-related revenue.** Besides the main fee at rebases, the treasury receives the CSM module rebate and small payments from the CSM accounting contract, and both flows arrive as separate transfers that bypass the NEST revenue source. The CSM rebate alone gives about $1.2M per year at the current annual run rate, and that rate is growing. So the current NEST systematically sees less staking revenue than the DAO actually receives. This is no longer a question about data quality but about the design of the NEST revenue source itself.
- **Since 25 December 2025 a different fee distribution regime has applied.** After the change in Curated Module fees, the total protocol fee was preserved, but the operators' share fell and the DAO's effective share rose. So the history before and after this date falls under different rules: calculations on 2024–2025 reflect a smaller treasury share than now, while the model's forecasts rely on the current one.
- **The true-up against the 2026 reports is less transparent** than for 2024–2025: the composition of the costs of revenue is not disclosed.

### Open questions

- Why does NEST not count the CSM module rebate, and is a separate revenue source planned for it?
- How will the treasury share change going forward, including when stake moves from Curated v1 to Curated v2, where the treasury share is lower?
- Does the H1 2026 report include the CSM rebate in net revenue, what do the $1.26M of costs consist of, and why was their share higher in 2025?
- Should charges on CSM operators' bonds be counted as DAO revenue for NEST purposes?

### What to check next

- **CSM rebate:** calculate how much it would have added to the NEST budget since activation and in the forecast.
- **Distribution change in December 2025:** check against the primary source the number, text and execution date of the vote on the change in Curated Module fees.
- **Point 3, methodology:** check how the model turns these data into the calculation of buyback rules.

## Point 3. Calculation methodology

### Description

The model is the nest\_model.xlsx spreadsheet plus Python scripts. They take the revenue series from point 2 and apply the buyback rule to it day by day: they add the share of revenue above the threshold to the budget, apply the rule for the deficit, and release money for buybacks within the caps. This is how I run both the current NEST and all the alternative rules.

The calculation runs over three horizons:

1. **History:** 1 January 2025 – 28 September 2026 on actual revenue; the rule is hypothetically launched on 1 January 2025 with a zero budget, even though NEST did not exist yet at that time.
2. **Constant price:** 12 months from 1 October 2026 at a fixed ETH price, with the actual NEST budget at the start.
3. **Stress tests:** the same 12 months on thousands of random ETH price paths (61% annualised volatility with no trend, based on daily data for the 365 days up to 28 September 2026); the extended version adds random deviations in expenses, one-off losses and report delays.

The main metrics are: buybacks in dollars over the period; the day of the first purchase; the share of scenarios in which any buyback happened at all; the share of loss-making years for the DAO among scenarios with buybacks; and peak overshoot, that is, the maximum over the period of the gap between cumulative buybacks and cumulative DAO profit (if cumulative profit is negative, all buybacks up to that point count as uncovered).

### Findings

- **The engine reproduces the contract logic exactly; differences in the historical run come only from the moment at which revenue is valued in dollars.** There were two checks. If I plug NEST's own dollar conversions into the formula, every onchain recalculation is reproduced to the cent (point 2). If I run the engine on my series, where each inflow is valued via Chainlink at the block of the inflow, the budget at the nightly recalculations differs from the onchain value by no more than $1,900, and by 28 September by $971: that is the accumulated valuation difference of −0.044%. Three recalculations made during the day after a rebase differ by about $49k, exactly the share of that day's revenue that had already reached them.
- **The historical calculation is sensitive to the old fee regime.** The current rule, hypothetically launched on 1 January 2025 with a zero budget, would have bought $1.07M over 2025–2026; if I roughly recalculate 2025 by scaling up treasury inflows before 25 December in the ratio 62.0/48.3 (the average treasury share of the fee after and before the change), the result is about $6.83M. Almost all of the difference arises within 2025 itself: with a larger treasury share, revenue in the months of expensive ETH would more often have exceeded the reserve. Carrying over the deficit from the old regime has almost no effect: by 24 December 2025 the budget in this calculation was only −$0.19M, and starting from zero on 25 December the rule would have bought $0.38M. This is a rough estimate: the real treasury share depends on the module mix, and I scaled it with a single coefficient.
- **The CSM rebate changes the picture sharply around the current price, but this calculation is smoothed.** To gauge the scale, I spread the current annual CSM rebate run rate evenly across days, about 1.22 stETH per day. In this scenario the ETH price at which revenue reaches the reserve moves from \~$2,668 to about $2,590, and the first purchase out of the actual deficit at ETH $2,680 would come after about 290 days instead of 2,291 (at $2,800 after 123 days instead of 201, at $3,000 after 62 instead of 79). In reality the rebate arrives once a month, so once a separate source is connected the exact dates will be different; the estimates of the threshold shift and of the additional \~$0.6M per year to the budget are reliable.
- **The model shows how much NEST is allowed to spend, not how much it can physically spend.** Across 3,000 random price scenarios, the current stETH balance of 41.08 stETH on the allocator, valued at the price on the day of the first purchase, covers only about 3% of the total buyback volume across all scenarios; the remaining \~97% cannot be executed without a top-up through Easy Track.

### Questions I asked

1. Does the engine reproduce the contract on real data, and not just the formula?
2. Do the calculations in the spreadsheet and in Python match?
3. What does each calculation horizon show, and where are its limits?
4. Are any of the metrics misleading?
5. What does the model not account for, and how much does that change the result?

### How I collected the data

- I ran the engine on my revenue for the period NEST has been running (from 10 August 2026 with revenue for 10–14 August excluded, as NEST does) and compared the end-of-day budget with 32 onchain recalculations.
- I had checked earlier, at every stage, that the spreadsheet and Python match: 36 rule variants were recalculated with spreadsheet formulas and matched Python on 9–12 metrics; the shared engine for the stress tests matched the original one to the dollar.
- For three effects that are not in the model, I did separate runs: a historical calculation with the current treasury share of the fee applied to 2025; a forecast with the CSM rebate added; and 3,000 random price scenarios checking what part of the buybacks the 41 stETH balance covers.

### Results

Below are the model assumptions the forecasts rest on, and their limitations.

| What | How it is in the model | What limits it |
| --- | --- | --- |
| Forward revenue | average revenue seen by NEST (main inflows at rebases) over the last 30 days, \~41.07 stETH per day, multiplied by the ETH price; without the CSM rebate | stake volume, market share and the DAO's share of the fee do not change |
| Cost of generating revenue | share for the first half of 2026 at 7.44% | the composition of these costs is not disclosed |
| Foundations expenses | forecast for the second half of 2026; from 2027 onward the 2026 forecast run rate | the 2027 budget is unknown |
| Report timing | \~60 days after quarter end (45–120 in the extended stress test) | actual timing depends on the team |
| ETH price | constant or random, 61% annualised volatility with no trend | price only, no shifts in market regime |
| LDO price | only for counting the number of tokens bought | slippage and liquidity are not accounted for |

What the model does not account for, and how much it matters:

| Not accounted for | How much it changes the result |
| --- | --- |
| stETH balance on the allocator and the top-up rule | strongly: the current balance covers about 3% of the total buyback volume in the stress test |
| CSM rebate and the fee on CSM operator bonds | strongly around the current price: in the smoothed scenario the first purchase at ETH $2,680 comes after \~290 days instead of 2,291 |
| Fee regime change on 25 December 2025 in the history | strongly for the history: $1.07M versus \~$6.83M in a rough recalculation of 2025 with the current treasury share |
| Executor liquidity mode | the number of LDO bought is half as large; dollar amounts do not change |
| Shift in accrual timing and the cap at midnight | little: within one day's reserve |

### Conclusions for point 3

- **The engine can be used as an exact implementation of the NEST logic.** With NEST's own dollar conversions it reproduces the onchain recalculations to the cent; on my historical series the difference is small and is explained solely by the moment at which revenue is valued in dollars.
- **Absolute results depend not only on the rule parameters, but also on the fee distribution regime, the composition of the revenue counted, and the stETH balance on the allocator.** So the model is well suited to comparing rules under identical assumptions, while absolute amounts should be presented together with those assumptions.
- **From here on two different quantities need to be shown:** how much the rule allows to be spent, and how much can be spent given a set stETH balance and top-up rule. Otherwise an aggressive rule may show $10M of buybacks that cannot be executed without a top-up.
- **Forecasts are scenarios under given assumptions, not predictions.** The assumptions about forward revenue and expenses are particularly sensitive.

### Open questions

- Will the CSM rebate keep growing, and how should it be counted in the forecast: at the current run rate or at the expected growth of the module?
- How valid is it to compare rules on the 2025 history, when a different fee regime was in force then, or is it better to compare only from 25 December 2025?

### What to check next

- **Model:** add to the engine the stETH balance on the allocator with a top-up rule, the CSM rebate as a separate revenue stream, and a history variant with the current fee regime, so that the following points are calculated with them.
- **Point 4 onward:** test rule parameters one at a time, in two starting budget variants.

## Point 4. Reserve

### Description

The reserve is the threshold in the budget formula: $109,589 per day, $40M per year. Only 50% of revenue above this threshold goes into the buyback budget, and when revenue is below the threshold, half of the shortfall goes into the deficit. The reserve determines at what revenue, and therefore at what ETH price, the mechanism starts accumulating money for buybacks at all. It can be changed by a DAO vote, and the new value applies only going forward.

For comparison I took six values: $30M (from Aksusarya's proposal), $35M, $37.7M (the Foundations expense forecast for 2026), $40M (as now), $43.8M (the approved EGG-2026 budget) and $45M. All other parameters are as in the contract: 50% share, the deficit accumulates, caps of $50k per day and $10M per year.

This point and all the following ones are calculated in three starting-point variants:

| Variant | Starting budget | Revenue the mechanism sees |
| --- | --- | --- |
| 1. As now | −$542,451 | only the main inflows at rebases |
| 2. With launch compensation | −$394,793 (+$147,658 for 11–14 August) | only the main inflows at rebases |
| 3. Main revenue and CSM rebate, hypothetically from launch | −$307,585 (a further +$87,208 for two CSM rebates after activation) | plus the CSM rebate every 28 days, 34.26 stETH each |

The CSM rebate is real DAO income, so it is included in the DAO profit I compare buybacks against in all three variants; it enters NEST revenue only in the third. A correction found later, in points 15–18: in the calculations for points 4–8 the rebate in variant 3 was counted in DAO profit twice, so the share of loss-making years in the variant 3 columns is understated by 2–3 percentage points (for example, at $40M and a 50% share it is 20%, not 18%); buyback volumes are not affected. Going forward, the rebate is added on its actual schedule, once every 28 days (the next one around 26 October), without accounting for its growth. The third variant is hypothetical: it shows what would have happened if the source for the CSM rebate had been in place since NEST launched. If such a source is connected by a vote now, past rebates will not enter the budget: when a source is connected, the allocator records its current total and from then on counts only the increase. This has little effect on the results: the starting difference of $87,208 is comparable to the launch compensation, and the main effect comes from the future rebate stream. One caveat: Lido may already be accounting for the rebate in its reports as a reduction in payouts to operators; in that case my cost-of-revenue share (7.44%) partly includes it, and adding it separately to DAO profit would be double counting. That is why I give both estimates for risk below. I checked the reports for 2025 as well as for the first quarter and first half of 2026: they contain only a description of the methodology, with no breakdown of deductions into operator payouts and referral payouts, so double counting can be neither confirmed nor ruled out from the published data. This is a question for the team.

### Findings

- **The reserve is one of the main levers of NEST:** it directly determines the ETH price at which the mechanism starts buying. Each $5M reduction moves that price down by about $330 and, in the stress test, adds about $0.6–1.3M of allowed buybacks per year.
- **But together with buybacks, the share of purchases made in years the DAO ends at a loss rises quickly.** In the first variant at $40M, among paths where NEST bought anything, 12% of years turn out loss-making for the DAO; at $35M it is already 30%, at $30M 45% (if the rebate is assumed to be already counted in cost of revenue, 15%, 35% and 49%). The average peak overshoot of buybacks over DAO profit rises from $0.04M to $1.43M.
- **Counting the CSM rebate at its annual run rate is equivalent to lowering the reserve by about $1.2M, but it is real DAO income, not a lower threshold.** In the third variant, at the current $40M and ETH $2,680 the first purchase comes after 165 days, whereas in the first two variants there is none at all. In the stress test, average allowed buybacks rise from $2.51M to $2.90M, the probability of at least one purchase from 51% to 60%, and the share of loss-making years among years with purchases from 12% to 18%. In volume this is slightly more than a $1.2M reserve reduction would give, because of the starting addition and because the rebate arrives in large lump sums.
- **The current $40M sits between the 2026 expense forecast ($37.7M) and the approved budget ($43.8M).** In LIP-36 the $40M is justified as a baseline expense level, but the contract does not tie the reserve to actual expenses in any way: once set, it is a fixed number, and it does not change if expenses rise or fall.
- **On the history, lowering the reserve shows a lot of purchases the DAO could not afford.** At $30M the rule would have bought $7.01M over 2025–2026 but by the end of the period the DAO's cumulative cash flow is negative, so none of this buyback volume would have been covered by the period's profit.
- **Without allocator top-ups, the choice of reserve changes almost nothing in practice.** With the current balance of 41.08 stETH and no top-ups, only $60–110k on average is executable over 12 months, depending on the stETH price at the time of purchases, at any reserve and in any variant.

### Questions I asked

1. At what ETH price does the mechanism start accumulating budget at different reserve values?
2. How much would the rule have bought on the history at each value, with and without the CSM rebate?
3. How much will it allow to be bought over the next 12 months at different ETH prices in each of the three variants?
4. How does the risk of purchases in loss-making years for the DAO grow?
5. How much of what is allowed can be executed without an allocator top-up?

### How I collected the data

- I calculated the break-even price for each reserve based on the current revenue seen by NEST (\~41.07 stETH per day), and with the CSM rebate at the current run rate (34.26 stETH once every 28 days, about 1.22 stETH per day).
- I ran each value on the history over two periods: from 1 January 2025 and only under the new fee regime, from 25 December 2025 (both times with a zero budget, with and without actual CSM rebates in revenue).
- I ran each value 12 months forward from 1 October 2026 at a constant ETH price of $2,680, $3,000 and $3,500 in the three variants.
- I ran each value on 2,500 random ETH price paths (61% annualised volatility with no trend) in the three variants. For each path I separately calculated how much the rule allows to be bought and how much of that the current balance of 41.08 stETH covers at the price on the day of the first purchase.

### Results

Table 1. ETH price at which revenue reaches the reserve. For the column with the rebate, this is the equivalent price based on the average annual stream of 34.26 stETH once every 28 days: in reality the rebate arrives once every 28 days, and the budget grows in steps rather than every day.

| Reserve | Main inflows only (variants 1 and 2) | With CSM rebate (variant 3) |
| --- | --- | --- |
| $30.0M | $2,001 | $1,944 |
| $35.0M | $2,335 | $2,268 |
| $37.7M | $2,515 | $2,442 |
| $40.0M (now) | $2,668 | $2,591 |
| $43.8M | $2,922 | $2,838 |
| $45.0M | $3,002 | $2,915 |

Table 2. History, rule hypothetically launched with a zero budget; in brackets, with actual CSM rebates in revenue.

| Reserve | 01.01.2025–28.09.2026 | New fee regime only, 25.12.2025–28.09.2026 |
| --- | --- | --- |
| $30.0M | $7.01M ($7.34M) | $1.40M ($1.66M) |
| $35.0M | $3.82M ($3.93M) | $0.67M ($0.70M) |
| $37.7M | $2.33M ($2.44M) | $0.51M ($0.54M) |
| $40.0M (now) | $1.07M ($1.18M) | $0.38M ($0.41M) |
| $43.8M | $0.50M ($0.50M) | $0.17M ($0.21M) |
| $45.0M | $0.44M ($0.44M) | $0.11M ($0.14M) |

On the history the rebate changes little, because it only started in October 2025; by the end of both periods the DAO's cumulative cash flow is negative, so none of the buyback volume would have been covered by the period's profit.

Table 3. Next 12 months at a constant ETH price: how many days until the first purchase and how much the rule will allow to be bought, variants 1 / 2 / 3.

| Reserve | ETH $2,680 | ETH $3,000 | ETH $3,500 |
| --- | --- | --- | --- |
| $30.0M | 38 / 28 / 22 days; $4.54M / $4.69M / $5.38M | 26 / 19 / 15 days; $6.94M / $7.09M / $7.85M | 17 / 12 / 10 days; $10.69M / $10.84M / $11.70M |
| $35.0M | 76 / 55 / 37 days; $2.04M / $2.19M / $2.88M | 39 / 28 / 22 days; $4.44M / $4.59M / $5.35M | 22 / 16 / 12 days; $8.19M / $8.34M / $9.20M |
| $37.7M | 160 / 116 / 63 days; $0.69M / $0.84M / $1.53M | 54 / 39 / 25 days; $3.09M / $3.24M / $4.00M | 26 / 19 / 15 days; $6.84M / $6.99M / $7.85M |
| $40.0M (now) | none / none / 165 days; $0 / $0 / $0.38M | 79 / 58 / 37 days; $1.94M / $2.09M / $2.85M | 31 / 23 / 18 days; $5.69M / $5.84M / $6.70M |
| $43.8M | no purchases in any variant | 339 / 246 / 96 days; $0.04M / $0.19M / $0.95M | 45 / 33 / 25 days; $3.79M / $3.94M / $4.80M |
| $45.0M | no purchases in any variant | none / none / 193 days; $0 / $0 / $0.35M | 53 / 38 / 25 days; $3.19M / $3.34M / $4.20M |

Amounts above $10M are possible because the 12 months from 1 October span two annual cap windows (the NEST window starts on 10 August).

Table 4. Stress test, 2,500 ETH price paths, 12 months: average allowed buybacks, probability of at least one purchase, and share of loss-making years for the DAO among paths with a purchase, variants 1 / 2 / 3.

| Reserve | Allowed to buy, average | P(at least one purchase) | P(loss-making year for the DAO given a purchase) | Average peak overshoot, variant 1 |
| --- | --- | --- | --- | --- |
| $30.0M | $4.88M / $5.00M / $5.42M | 88% / 92% / 96% | 45% / 47% / 47% | $1.43M |
| $35.0M | $3.56M / $3.65M / $4.04M | 69% / 73% / 80% | 30% / 34% / 37% | $0.49M |
| $37.7M | $2.96M / $3.04M / $3.39M | 59% / 62% / 68% | 19% / 22% / 26% | $0.17M |
| $40.0M (now) | $2.51M / $2.58M / $2.90M | 51% / 54% / 60% | 12% / 15% / 18% | $0.04M |
| $43.8M | $1.89M / $1.94M / $2.21M | 39% / 41% / 46% | 4% / 6% / 9% | $0.01M |
| $45.0M | $1.72M / $1.77M / $2.02M | 35% / 37% / 42% | 3% / 4% / 6% | $0.00M |

Executable without an allocator top-up: $60–110k on average over 12 months in all rows and variants. The share of loss-making years is calculated with the CSM rebate in DAO profit; if the rebate is assumed to be already counted in cost of revenue, in variant 1 it is 3–5 percentage points higher: 49%, 35%, 24%, 15%, 6% and 4% by row.

### Conclusions for point 4

- **Lowering the reserve is the simplest way to make NEST buy, but at the same time it makes purchases less backed by profit.** Moving from $40M to $30M almost doubles average allowed buybacks, but the share of loss-making years for the DAO among years with purchases rises from 12% to 45%.
- **Adding the CSM rebate as a revenue source is fundamentally not the same as lowering the reserve.** Lowering the reserve creates no new profit; it only allows spending at lower revenue. The rebate is real additional DAO income: at its annual run rate it is equivalent to lowering the reserve by about $1.2M, but it raises the budget together with income. The reserve and revenue accounting are different levers: lowering the reserve loosens the condition under which buybacks are allowed, while connecting a new source changes the very amount of revenue NEST recognises.
- **The reserve does not track DAO expenses.** In LIP-36 the $40M was chosen as a baseline expense level, but once set it is a fixed number that does not follow actual expenses.
- **Lowering the reserve does not solve the execution problem.** Without an allocator top-up rule, the difference between reserves comes down in practice to $60–110k over 12 months.
- **Launch compensation shifts the results only slightly,** counting the CSM rebate is more noticeable, but neither changes the main conclusion about the reserve.

### Open questions

- What was the basis for choosing $40M: expenses, historical revenue or the desired buyback volume?
- How willing is the DAO to allow buybacks in years that later turn out to be loss-making: what share of such years is acceptable?

* Does Lido account for the CSM rebate in its reports as a reduction in payouts to operators? This determines whether it should be added to DAO profit separately.

### What to check next

- **Point 5, surplus share:** how the picture changes at a share of 25, 75 and 100% at the current reserve, in the same three variants.
- **Expense-based threshold (points 9–10):** what if, instead of a fixed reserve, revenue is compared with the DAO's actual expenses.

## Point 5. Surplus share

### Description

The share determines what part of the difference between revenue and the reserve goes into the buyback budget: currently 50%. It works in both directions: on a good day half of the excess goes into the budget, on a bad day half of the shortfall is subtracted from the budget. A deficit that has already accumulated is not recalculated when the share changes; it stays in dollars. The share can be changed by a DAO vote, and the new value applies only going forward.

I compared 25%, 50% (as now), 75% and 100% at the current $40M reserve, with the other parameters as in the contract. I ran the calculations with the same three starting-point variants as in point 4.

### Findings

- **The share does not move the boundary at which new budget growth changes sign.** The ETH price at which revenue reaches the reserve does not depend on the share: at $40M it is still about $2,668. So at ETH $2,680 there are no purchases over the year in the first two variants at any share.
- **The share speeds up the exit from the current deficit.** The deficit is already fixed in dollars, while daily budget growth is proportional to the share. At ETH $3,000 the first purchase comes after 159 days at a 25% share, after 79 at 50%, after 53 at 75%, and after 39 at 100%.
- **Returns from the share diminish.** Moving from 50% to 100% in the stress test increases average permitted buybacks not twofold but by about 1.5 times, from $2.51M to $3.74M: the deficit in bad periods also doubles, and in good periods the mechanism runs into the daily cap.
- **For a comparable buyback volume, raising the share gives a lower frequency of loss-making years than lowering the reserve.** Average buybacks of about $3.7M a year can be reached in two ways: a 100% share with a $40M reserve, or a reserve of about $35M with a 50% share. In the first case 18% of years with purchases turn out to be loss-making for the DAO, in the second 30%. The reason is that the share does not change the accrual threshold: positive budget growth still only appears when revenue is above $40M in annualised terms, while lowering the reserve turns lower revenue into positive growth as well. A purchase is still possible on a day with revenue below the reserve if the budget is already positive by then, because NEST accumulates the budget cumulatively.
- **Without an allocator top-up, the share hardly changes the executable volume in dollars:** at any share, on average about $70–80k out of the current stETH balance of 41.08 stETH is executable over 12 months. But it still changes when that balance will be spent, at what LDO price, and whether a purchase happens at all.

### Questions I asked

1. Does the share change the ETH price at which the mechanism starts accumulating budget?
2. How much would the rule have bought historically at each share?
3. How does the share affect the exit from the current deficit and buybacks over 12 months?
4. How does the risk of purchases in years that are loss-making for the DAO grow compared with changing the reserve?

### How I collected the data

The same way as in point 4: history from 1 January 2025 and only under the new fee regime from 25 December 2025, both times with a zero budget, with and without actual CSM rebates in revenue; 12 months ahead from 1 October 2026 at a constant ETH price of $2,680, $3,000 and $3,500 in three variants; 2,500 random ETH price paths in three variants, on the same paths as for the reserve, so the results can be compared directly.

### Results

Table 1. History, rule hypothetically launched with a zero budget; in brackets, with actual CSM rebates in revenue.

| Share | 01.01.2025–28.09.2026 | New fee regime only, 25.12.2025–28.09.2026 |
| --- | --- | --- |
| 25% | $0.54M ($0.59M) | $0.19M ($0.20M) |
| 50% (now) | $1.07M ($1.18M) | $0.38M ($0.41M) |
| 75% | $1.61M ($1.77M) | $0.57M ($0.61M) |
| 100% | $2.15M ($2.36M) | $0.75M ($0.82M) |

Historically, buybacks grow almost in proportion to the share. By the end of both periods the DAO's cumulative cash flow is negative, so the full buyback volume would not have been covered by the period's profit.

Table 2. Next 12 months at a constant ETH price: days until the first purchase and how much the rule would permit buying, variants 1 / 2 / 3.

| Share | ETH $2,680 | ETH $3,000 | ETH $3,500 |
| --- | --- | --- | --- |
| 25% | none / none / 333 days; $0 / $0 / $0.03M | 159 / 116 / 75 days; $0.70M / $0.85M / $1.27M | 63 / 46 / 32 days; $2.57M / $2.72M / $3.20M |
| 50% (now) | none / none / 165 days; $0 / $0 / $0.38M | 79 / 58 / 37 days; $1.94M / $2.09M / $2.85M | 31 / 23 / 18 days; $5.69M / $5.84M / $6.70M |
| 75% | none / none / 109 days; $0 / $0 / $0.72M | 53 / 38 / 25 days; $3.18M / $3.33M / $4.42M | 21 / 15 / 12 days; $8.81M / $8.95M / $10.21M |
| 100% | none / none / 81 days; $0 / $0 / $1.06M | 39 / 29 / 22 days; $4.43M / $4.58M / $6.00M | 15 / 11 / 9 days; $11.92M / $12.07M / $12.60M |

Amounts above $10M are possible because the 12 months from 1 October span two annual cap windows.

Table 3. Stress test, 2,500 ETH price paths, 12 months, variants 1 / 2 / 3.

| Share | Permitted to buy, average | P(at least one purchase) | P(loss-making year for the DAO, given a purchase) | Average peak overshoot, variant 1 |
| --- | --- | --- | --- | --- |
| 25% | $1.34M / $1.40M / $1.62M | 44% / 48% / 54% | 5% / 8% / 12% | $0.01M |
| 50% (now) | $2.51M / $2.58M / $2.90M | 51% / 54% / 60% | 12% / 15% / 18% | $0.04M |
| 75% | $3.25M / $3.32M / $3.70M | 54% / 57% / 63% | 16% / 19% / 21% | $0.16M |
| 100% | $3.74M / $3.81M / $4.23M | 56% / 58% / 65% | 18% / 20% / 23% | $0.35M |

Executable without an allocator top-up: on average about $70–80k over 12 months in all rows. The share of loss-making years is calculated with CSM rebates in DAO profit; the caveat about possible double counting from point 4 applies here too.

To compare the two levers on the same paths:

| How to get average buybacks of \~$3.7M a year (variant 1) | P(loss-making year for the DAO, given a purchase) | Average peak overshoot |
| --- | --- | --- |
| 100% share with a $40M reserve | 18% | $0.35M |
| $35M reserve with a 50% share (point 4) | 30% | $0.49M |

### Dynamic share

These are experimental variants of my model, not properties of the current NEST. In the contract the share is a single constant value applied to budget growth of either sign, so any variant below would require a new allocator, and the results for them are modelling results, not guarantees of the mechanism. I checked three ways to vary the share depending on circumstances:

1. **Tiers by surplus size**, like a tax scale. The tiers are calculated for each day separately, based on the day's revenue excess over the reserve: the part of the excess up to $13,699 (that is $5M in annualised terms) goes into the budget at the first share, the part from $13,699 to $41,096 ($15M a year) at the second, and everything above $41,096 at the third. There is no accumulation over a window; each day is calculated afresh. Days when revenue is below the reserve go into the deficit at a 50% share, as now.
2. **Separate shares for profit and loss:** the excess over the reserve goes into the budget at one share, and the shortfall goes into the deficit at a smaller one.
3. **Share by LDO price:** 75% when LDO is cheaper than 90% of its 90-day average, 25% when it is more expensive than 110%, and 50% the rest of the time.

All at a $40M reserve, on the same 2,000 ETH price paths for all variants. For the LDO-price share, the LDO price was modelled together with ETH (0.75 of the ETH move plus its own noise of 90% annualised), and in the first months the 90-day average is taken from actual LDO prices for the 90 days before 28 September 2026.

Table 4. Dynamic share, variant 1 (variant 3 in brackets): history with a zero budget and a 12-month stress test.

| Rule | History 2025–2026 | Stress: permitted to buy, average | P(loss-making year for the DAO, given a purchase) | Average peak overshoot | Average LDO purchase price |
| --- | --- | --- | --- | --- | --- |
| Constant 50% (now) | $1.07M ($1.18M) | $2.45M ($2.86M) | 11% (17%) | $0.05M | $0.411 |
| Constant 100% | $2.15M ($2.36M) | $3.73M ($4.22M) | 18% (22%) | $0.36M | $0.382 |
| Tiers 25 / 50 / 75% | $0.67M ($0.72M) | $2.33M ($2.79M) | 8% (15%) | $0.02M | $0.421 |
| Tiers 50 / 75 / 100% | $2.08M ($2.26M) | $3.09M ($3.64M) | 12% (19%) | $0.10M | $0.398 |
| Profit 100%, loss 50% | $4.04M ($4.25M) | $3.87M ($4.40M) | 19% (24%) | $0.42M | $0.378 |
| Profit 50%, loss 25% | $2.02M ($2.13M) | $2.52M ($2.94M) | 12% (18%) | $0.06M | $0.408 |
| By LDO price 75 / 50 / 25% | $0.50M ($0.50M) | $2.24M ($2.63M) | 10% (14%) | $0.04M | $0.361 |

The average LDO purchase price is the ratio of the average buyback amount to the average quantity of LDO bought; it is illustrative because the model does not account for slippage.

What stands out:

- **Tiers 50 / 75 / 100% give more buybacks with almost no increase in risk.** Average buybacks are $3.09M against $2.45M for a constant 50% share, while the share of loss-making years is 12% against 11%. The high tiers only kick in with a large surplus, that is, with expensive ETH, and those are exactly the years that are profitable for the DAO.
- **Separate shares effectively change the debt policy.** If the excess goes into the budget at a 100% share and the shortfall at 50%, then after a good period of +$10M and a bad one of −$10M the budget stays at +$5M, whereas with equal shares it would be at zero. In other words, such a rule systematically forgives part of future shortfalls, and revenue fluctuations by themselves create a positive bias. That is why "Profit 100%, loss 50%" looks like a constant 100% share in buybacks and risk, while "Profit 50%, loss 25%" gives twice as many buybacks historically as the current 50%. I will go through this in detail in point 7.
- **In the chosen LDO price model, the LDO-price share buys fewer dollars' worth, but more cheaply.** Average buybacks are slightly lower than with a constant 50% share ($2.24M against $2.45M), but the average LDO purchase price is 12% lower ($0.361 against $0.411), and the risk is the lowest among the variants with the same threshold. This result is sensitive to the assumptions about the link between LDO and ETH and about LDO volatility, so it is illustrative. Historically the rule would have bought less: in 2025 LDO was falling for a long time, and the 90-day average lagged behind the price.
- **Tiers 25 / 50 / 75%** buy less than the current 50% near the threshold and almost the same with expensive ETH; this is the most cautious variant.

### Conclusions for point 5

- **The share is a speed lever, not a threshold lever.** It does not change the revenue level at which new budget growth turns positive, but it speeds up both budget accumulation and the exit from the deficit.
- **The share and the reserve control different properties of NEST.** The reserve sets the boundary between positive and negative budget growth, while the share scales both movements around that boundary. Raising the share increases activity without widening the range of revenue in which positive growth occurs; lowering the reserve widens that range itself. In my stress tests, for a comparable buyback volume, a 100% share gives a lower frequency of years that are loss-making for the DAO (18% against 30%) and a smaller peak overshoot ($0.35M against $0.49M) than a $35M reserve.
- **Returns from the share diminish:** in the stress test, doubling the share from 50% to 100% gives roughly one and a half times more buybacks, not twice as many. There are two reasons: the share equally increases the deficit in weak periods, and in strong ones the $50k daily cap, which LIP-36 calls the main limiter, kicks in more and more often.
- **Without an allocator top-up, the share hardly changes the executable volume in dollars, but it changes the timing of execution and the quantity of LDO bought.**

* **Of the dynamic rules I checked, tiers 50 / 75 / 100% noticeably increase buybacks at almost the same risk:** average permitted buybacks rise from $2.45M to $3.09M, the share of loss-making years from 11% to 12%, and the average peak overshoot from $0.05M to $0.10M. Which rule is better depends on the goal: more buybacks, less risk or a lower purchase price. All dynamic rules require a new allocator.

- **Once the shares for profit and loss become different, this is no longer a share setting but a change in the debt policy:** bad periods are counted less heavily than good ones. I go through this in detail in point 7.

### Open questions

- Why is the share the same for profit and for loss? Separate shares (for example, higher on good days and lower on bad ones) are not possible in the current contract.

### What to check next

- **Point 6, revenue base:** what changes if the reserve is compared not with revenue before deductions, as now, but with net revenue after the costs of earning it.
- **Point 7, debt policy:** how the picture changes if the deficit is capped, forgiven gradually or reset by period.

## Point 6. Revenue base

### Description

The revenue base is what the mechanism compares with the reserve. Currently it is the treasury's share of the fee on rebases, before the deductions the DAO pays out of that fee (referral payouts and others, point 2). I compared three bases at the current $40M reserve and a 50% share:

1. **As now:** the treasury's share of the fee on rebases, as seen by NEST.
2. **Approximation of reported net staking revenue:** the NEST base minus 7.44%. This share is not measured directly: it is fitted so that the NEST base for the first half of 2026 ($16.97M) matches reported net staking revenue ($15.71M). It is a residual adjustment whose composition the report does not disclose. For history, the same kind of adjustment is used for each reporting period (9.9% in 2025).
3. **Expanded DAO income:** the net revenue approximation plus net Earn revenue and the treasury's income from its own assets. At the run rate of the first half of 2026 this is about $1,270 and $7,700 a day, together about $3.3M a year; Earn is still unstable (for part of the period no fees were charged), and treasury income depends on its composition and yields. This is not an official Lido metric: in the report, Total Net DAO Revenue includes net staking revenue and Earn, while treasury income is shown separately and is not part of the P&L.

For the second and third bases, it matters how Lido accounts for the CSM rebate (point 2). There are two versions:

- **Version A:** the rebate is already included in reported net staking revenue as a reduction in payouts to operators. In that case it is already inside the 7.44% adjustment and must not be added separately.
- **Version B:** the rebate is not included in reported net staking revenue. In that case it has to be added separately, both to DAO profit and to bases 2 and 3.

The bridge for the first half of 2026 shows why the report does not let us tell them apart: the NEST base of $16.97M plus the CSM rebate of about $0.36M plus the fee on CSM operator bonds (less than $0.02M) minus referral payouts and other deductions equals $15.71M. In version A, where the rebate is already inside the reported figure, referral payouts and other deductions come to about $1.62M, and $1.26M is the net adjustment after the rebate ($1.62M − $0.36M); this is exactly what my 7.44% reproduces. In version B, where the rebate is not in the reported figure, the deductions equal $1.26M, and the DAO's economic staking income including the rebate is about $16.07M. The report has no separate figure for referral payouts for the half-year. So below, the results for bases 2 and 3 are given in both versions.

### Findings

- **The NEST base overstates net staking revenue and at the same time does not see the DAO's other regular income, and right now these errors are almost equal.** Relative to the net revenue approximation, the NEST base is higher by about $3.0M a year at ETH $2,680, while Earn and treasury income together are about $3.3M a year. So in version A the break-even price on the NEST base ($2,668) almost matches the price on expanded income ($2,646), and the expanded base gives almost the same buybacks as the current one: $2.43M against $2.51M a year. But this match only holds around a certain ETH price. The current base grows almost entirely with ETH, while the expanded one consists of 92.56% of that revenue plus a relatively constant $3.3M of Earn and treasury income. They are equal at roughly ETH $2,950: below that price the expanded base is larger than the current one, above it smaller. That is why the expanded base has a slightly lower break-even price but slightly smaller average buybacks: large buybacks happen at expensive ETH, where it already falls behind the current base. Besides, if referral payouts grow or treasury income changes, the bases will diverge near the current price too.
- **In version B the expanded base is noticeably wider than the current one.** The CSM rebate of about $1.2M a year is added to it, the break-even price drops to $2,563, buybacks rise to $2.71M, and at ETH $2,680 the first purchase comes after 249 days, whereas on the current base there is none.
- **Around the current $40M level, switching to net revenue is comparable to raising the reserve by about $3M.** The break-even price rises to $2,883, buybacks in the stress test fall to $1.87M a year, and the share of loss-making years among years with purchases drops to 4–6% depending on the version. Historically the rule would have bought $0.43M instead of $1.07M.
- **The current NEST can technically see only the first base.** Deductions, Earn and treasury income do not reach its revenue source; the second base would need a discount parameter or data from reports, and the third would need additional sources or a true-up against reports (points 11–14).

### Questions I asked

1. How much does the NEST base differ from net revenue and other DAO income, and in which direction?
2. How do the break-even price, buybacks and risk change when switching to net revenue or to expanded income?
3. How does the way the CSM rebate is accounted for affect this?
4. Which base can NEST technically see?

### How I collected the data

- I calculated break-even prices from the revenue NEST sees (\~41.07 stETH a day), the 7.44% adjustment and the Earn and treasury income run rates for the first half of 2026, in versions A and B.
- I built a bridge between the NEST base and reported net revenue for the first half of 2026.
- History from 1 January 2025 and only under the new fee regime, with a zero budget, with adjustments and income by reporting period.
- 12 months ahead at a constant ETH price and 2,000 random ETH price paths. Starting-point variants 1 and 2 in both versions; for the current base, variant 3 (the rebate as a separate NEST source) makes sense in both versions, because NEST does not see it in either case; for the second and third bases it only makes sense in version B, because in version A the rebate is already inside reported net revenue. The current base row in tables 3 and 4 is calculated with the rebate in DAO profit, that is, in version B; in version A its share of loss-making years is higher by about 3 percentage points.

### Results

Table 1. ETH price at which the revenue base reaches the $40M reserve.

| Base | Without a separate rebate source for NEST | With a separate rebate source for NEST (variant 3) |
| --- | --- | --- |
| As now | $2,668 | $2,591, the same in versions A and B |
| Net revenue approximation | $2,883 | A: not applicable, rebate already inside the adjustment; B: $2,793 |
| Expanded DAO income | A: $2,646; B: $2,563 | A: not applicable; B: $2,563, rebate already included as treasury income |

For the current base a separate rebate source makes sense under any accounting method: NEST does not see it in either version. For the second and third bases, in version A the rebate is assumed to be already inside reported net revenue and is not added again; in version B it is added separately.

Table 2. History, rule hypothetically launched with a zero budget.

| Base | 01.01.2025–28.09.2026 | New fee regime only, 25.12.2025–28.09.2026 |
| --- | --- | --- |
| As now | $1.07M; with a separate rebate source for NEST $1.18M | $0.38M; with a separate rebate source for NEST $0.41M |
| Net revenue approximation | $0.43M; in version B with a separate rebate source also $0.43M | $0.19M; in version B with a separate rebate source $0.22M |
| Expanded DAO income | version A $0.58M, version B $0.64M | version A $0.37M, version B $0.41M |

Table 3. Next 12 months at a constant ETH price: days until the first purchase and how much the rule would permit buying, variants 1 / 2 (and 3 where it makes sense).

| Base | ETH $2,680 | ETH $3,000 | ETH $3,500 |
| --- | --- | --- | --- |
| As now | none / none / 165 days; $0 / $0 / $0.38M | 79 / 58 / 37 days; $1.94M / $2.09M / $2.85M | 31 / 23 / 18 days; $5.69M / $5.84M / $6.70M |
| Net revenue, A and B | no purchases | 244 / 177 days; $0.27M / $0.42M (B, variant 3: 81 days, $1.12M) | 46 / 33 days; $3.74M / $3.89M (B, variant 3: 25 days, $4.70M) |
| Expanded income, A | no purchases | 80 / 58 days; $1.91M / $2.06M | 33 / 24 days; $5.38M / $5.53M |
| Expanded income, B | 249 / 185 / 137 days; $0.29M / $0.44M / $0.52M | 65 / 51 / 38 days; $2.58M / $2.73M / $2.82M | 29 / 24 / 19 days; $6.16M / $6.31M / $6.40M |

Table 4. Stress test, 2,000 ETH price paths, 12 months, variants 1 / 2 (and 3 where it makes sense).

| Base | Permitted to buy, average | P(at least one purchase) | P(loss-making year for the DAO, given a purchase) | Average peak overshoot, variant 1 |
| --- | --- | --- | --- | --- |
| As now | $2.51M / $2.58M / $2.90M | 50% / 53% / 60% | B: 12% / 15% / 19%; A: about 15% in variant 1 | $0.04M |
| Net revenue, A | $1.87M / $1.93M | 40% / 42% | 6% / 8% | $0.01M |
| Net revenue, B | $1.87M / $1.93M / $2.19M | 40% / 42% / 47% | 4% / 6% / 9% | $0.01M |
| Expanded income, A | $2.43M / $2.50M | 51% / 54% | 15% / 19% | $0.08M |
| Expanded income, B | $2.71M / $2.79M / $2.84M | 56% / 58% / 60% | 16% / 19% / 22% | $0.09M |

In version A the rebate is added neither to the base nor to DAO profit; in version B it is added to both. Executable without an allocator top-up: on average $60–80k over 12 months in all rows.

### Conclusions for point 6

- **The definition of revenue changes the result no less than several million dollars of reserve.** Switching from the NEST base to the net revenue approximation moves the break-even price from $2,668 to $2,883, which around the current level is comparable to raising the reserve by about $3M; this is a local comparison, because the adjustment grows with revenue while the reserve is constant. The 7.44% itself is not an estimate of referral payouts or of the costs of earning revenue, but a residual adjustment that reconciles the NEST base with reported net staking revenue; it cannot be used as an actual expense share.
- **The three bases answer different questions, and none of them is simply the right one.** The current base is the revenue NEST is able to measure on-chain today; net revenue approximates the economic income from staking after deductions; the expanded base also takes in the DAO's other regular inflows. This is a separate design parameter of NEST: the bases react differently to the ETH price, and their closeness near the current price does not mean they are interchangeable.
- **Near the current ETH price, the current NEST base happens to be close to expanded DAO income** (almost identical in version A), because its overstatement from deductions roughly equals the Earn and treasury income it cannot see. But the bases are not equivalent: the current one grows with ETH, while a noticeable part of the expanded one is almost constant, so above roughly ETH $2,950 it gives less, and below it gives more. In version B the expanded base is higher than in version A by about the current annual run rate of the CSM rebate, about $1.2M a year; relative to the current NEST base, the difference still depends on the ETH price.
- **How Lido accounts for the CSM rebate now affects several conclusions at once:** DAO profit in the risk assessment, the second and third bases, and whether to add the rebate as a separate NEST source. This is the main open question of this point.

### Open questions

- Is the CSM rebate included in reported net staking revenue, and how much did referral payouts amount to in the first half of 2026?
- If the $40M is understood as the baseline expense level of the whole DAO, should the revenue base also cover the whole DAO? Currently NEST compares this level only with staking revenue, and LIP-36 says explicitly that the mechanism tracks only that, although the architecture allows new sources.
- Can referral payouts be seen on-chain, or are they known only from reports?

### What to check next

- **Referral payouts on-chain:** try to find the referral payouts for the first half of 2026, to tell versions A and B apart via the bridge.
- **Point 7, debt policy:** how the picture changes if the deficit is capped, forgiven gradually or reset by period, including the separate shares for profit and loss from point 5.

## Point 7. Debt policy

### Description

"Debt" here means a negative NEST budget. It is not an obligation of the DAO and not necessarily an economic loss, but the accumulated shortfall of the revenue NEST sees relative to the $40M reserve, multiplied by the 50% share. The debt policy determines how long this past shortfall affects the future ability to buy. Right now the deficit accumulates without limit: future surplus first restores the budget to zero, and only then becomes available for buybacks. There is no manual reset in the contract.

I compared 14 rules with a $40M reserve and a 50% share: 12 policies from stage 1 (including the current one) and two split shares from point 5.

1. **Accumulates without limit,** as now.
2. **Floor:** the deficit is no deeper than 30 or 90 days of reserve adjusted for the share (about −$1.64M or −$4.93M).
3. **Does not accumulate:** the budget never goes below zero.
4. **Decay:** each day 0.5%, 1% or 2% of the accumulated deficit is forgiven.
5. **Quarterly or annual reset:** at the quarter or year boundary the deficit is zeroed, while a positive balance is kept. In the model the first reset happens at the first boundary after the new allocator launches, that is, on 1 January 2027; a reset on the launch day itself is equivalent to starting from zero (see below).
6. **Rolling window of 90, 180 or 365 days:** the budget equals the sum of increments over the last N days minus purchases over the same days; everything older than the window is forgotten. I checked with a unit test that a dollar already spent does not become available a second time when the purchase leaves the window: on 300 random paths, total purchases never exceeded the sum of positive increments.
7. **Split shares:** the excess over the reserve goes into the budget with a share of 100% or 50%, and the shortfall goes into the deficit with a share of 50% or 25%.

**Every rule except the current one requires a new allocator, and then a separate decision is needed on what budget it starts with.** The contract does not require carrying over the old deficit. Options: carry over −$542,451; carry over with the launch compensation, −$394,793; start from zero; rebuild the budget under the new rule from NEST history since 10 August. In the main calculations I carry over the actual budget of −$542,451 and then apply the new rule to it; for the windows I additionally compute the history rebuild, and for the current rule and the quarterly reset, a start from zero.

For the windows these two approaches differ. If the old deficit is carried over as a single balance, it ages from the new allocator's launch date and leaves the 90-day window after 90 days. If the daily increments are rebuilt from 10 August, the oldest shortfalls leave the window earlier, already in November.

### Findings

- **Shortening the debt memory speeds up the resumption of buybacks, but raises the frequency of buybacks in years when the DAO's cash flow is negative, and the faster past shortfall is forgotten, the stronger this effect.** On the same 1,500 paths, the current rule gives an average of $2.48M in buybacks and 12% loss-making years among years with purchases; decay of 0.5% per day gives $2.61M and 16%; the 180-day window $2.67–2.77M and 17–18%; the 90-day window and the quarterly reset $2.71–2.87M and 29–31%; "does not accumulate" $2.98M and 50%.
- **On my risk metrics, deficit write-off rules produce a larger increase in the share of loss-making years per additional dollar of buybacks than changes to the share do.** A 75% share on the same paths gives $3.20M and 16%, the 50 / 75 / 100% steps give $3.08M and 13%, that is, more buybacks at lower risk than any of the write-off rules.
- **The current accumulated deficit is itself an important part of the protection.** If the new allocator starts from zero under the current rule, the probability of at least one purchase during the year rises from 50% to 84%, but the share of loss-making years among years with purchases rises from 12% to 44%.
- **The 90-day floor practically never triggers on this horizon, and the 30-day floor triggers only in a small fraction of paths,** so both barely change the average results. The 365-day window over a one-year horizon is almost indistinguishable from the current rule.
- **Rebuilding the window from history makes it slightly more aggressive than carrying over the deficit as a single balance.** For the 90-day window, the median time to the first purchase falls from 90 to 50 days, average buybacks rise from $2.80M to $2.87M, and the share of loss-making years from 29% to 31%.
- **On history, the write-off rules triple buybacks during the period when the DAO's cumulative cash flow is negative.** "Does not accumulate" would have bought $3.01M over 2025–2026, the quarterly reset $2.76M, the 90-day window $2.53M, versus $1.07M under the current rule.
- **Split shares behave almost like constant shares in the first year.** "Profit 50%, loss 25%" going forward is almost indistinguishable from the current rule, because the current deficit has already been accumulated under the old share; the effect builds up over a longer horizon. "Profit 100%, loss 50%" resembles a constant 100% share.

### Questions I asked

1. How much does each rule increase buybacks, and how does the risk change?
2. How does a rule treat the deficit already accumulated, and what does this depend on when moving to a new allocator?
3. How does debt policy compare with the reserve and the share on the same paths?

### How I collected the data

- I moved all debt policies into the shared engine and reconciled the 12 stage 1 policies on history: they match to the hundredth; split shares were added later. The window was checked with a separate unit test.
- History from 1 January 2025 with a zero budget.
- 12 months forward from 1 October 2026 at a constant ETH price and 1,800 random ETH price paths in three starting point variants (tables 1 and 2).
- To compare the levers, I separately ran all the rules being compared, including the share and the reserve, on the same 1,500 paths, with risk under both versions of CSM rebate accounting (table 3). To rebuild the window I took the actual NEST revenue since 10 August (excluding 10–14 August, as NEST does); the rebuilt budget at the end of 30 September is −$491,869, and the difference from the −$542,451 on-chain is almost exactly the share of revenue for 30 September, which had not yet made it into the on-chain snapshot.

### Results

Table 1. Stress test, 1,800 ETH price paths, 12 months, variant 1 (variant 3 in brackets), and history with a zero budget. The old deficit is carried over as a single balance.

| Rule | Allowed to buy, average | P(at least one purchase) | P(loss-making year for the DAO when buying), version B | Average peak front-running | History 2025–2026 |
| --- | --- | --- | --- | --- | --- |
| Accumulates (current) | $2.48M ($2.87M) | 50% (59%) | 12% (18%) | $0.04M | $1.07M |
| Floor of 30 days of reserve | $2.49M ($2.88M) | 51% (60%) | 12% (18%) | $0.05M | $1.07M |
| Floor of 90 days of reserve | $2.48M ($2.87M) | 50% (59%) | 12% (18%) | $0.04M | $1.07M |
| 365-day window | $2.48M ($2.87M) | 50% (59%) | 12% (18%) | $0.04M | $1.39M |
| Profit 50%, loss 25% | $2.54M ($2.95M) | 53% (62%) | 12% (19%) | $0.05M | $2.02M |
| Decay 0.5% per day | $2.60M ($2.95M) | 56% (63%) | 15% (20%) | $0.09M | $1.79M |
| Annual reset | $2.64M ($2.96M) | 60% (65%) | 21% (22%) | $0.14M | $1.21M |
| 180-day window | $2.67M ($3.00M) | 57% (64%) | 17% (21%) | $0.10M | $2.51M |
| Decay 1% per day | $2.68M ($3.01M) | 60% (67%) | 20% (25%) | $0.16M | $2.14M |
| Quarterly reset | $2.71M ($3.04M) | 67% (72%) | 28% (30%) | $0.19M | $2.76M |
| Decay 2% per day | $2.76M ($3.07M) | 64% (71%) | 26% (29%) | $0.24M | $2.46M |
| 90-day window | $2.80M ($3.10M) | 67% (71%) | 28% (28%) | $0.28M | $2.53M |
| Does not accumulate | $2.97M ($3.38M) | 94% (100%) | 49% (49%) | $0.44M | $3.01M |
| Profit 100%, loss 50% | $3.82M ($4.34M) | 58% (68%) | 19% (26%) | $0.40M | $4.04M |

Variant 2 lies between variants 1 and 3 in every row. Risk is shown in version B (CSM rebate counted separately in DAO profit); version A does not change buyback amounts, but it changes which years count as loss-making and gives 3–5 percentage points more (table 3).

Table 2. Next 12 months at a constant ETH price, variant 1: how many days until the first purchase and how much the rule allows to buy.

| Rule | ETH $2,680 | ETH $3,000 | ETH $3,500 |
| --- | --- | --- | --- |
| Accumulates (current), 30 and 90 day floors, 365-day window | no purchases | 79 days, $1.94M | 31 days, $5.69M |
| Decay 0.5% / 1% / 2% per day | none / 320 / 195 days; $0 / $0.01M / $0.04M | 67 / 58 / 47 days; $2.03M / $2.08M / $2.16M | 29 / 27 / 24 days; $5.73M / $5.76M / $5.81M |
| Quarterly or annual reset (first reset on 1 January) | 96 days, $0.06M | 79 days, $1.94M | 31 days, $5.69M |
| 90 / 180 day window, old deficit as a single balance | 90 / 180 days; $0.09M | 79 days, $2.16M | 31 days, $5.85M |
| Does not accumulate | 5 days, $0.09M | 1 day, $2.48M | 1 day, $6.22M |
| Profit 100%, loss 50% | no purchases | 39 days, $4.43M | 15 days, $11.92M |

At a constant price, the difference between the rules is mainly in how quickly they write off the current deficit: there are no more weak days ahead, and the budget increment is the same for all of them.

Table 3. Lever comparison on the same 1,500 paths, variant 1, risk in versions B and A.

| Rule | Allowed to buy, average | P(at least one purchase) | P(loss-making year when buying), B / A | Average peak front-running | Median first purchase, days |
| --- | --- | --- | --- | --- | --- |
| Accumulates (current) | $2.48M | 50% | 12% / 15% | $0.04M | 87 |
| Share steps 50 / 75 / 100% (point 5) | $3.08M | 52% | 13% / 17% | $0.10M | 82 |
| Share 75% (point 5) | $3.20M | 53% | 16% / 20% | $0.16M | 71 |
| Decay 0.5% per day | $2.61M | 55% | 16% / 20% | $0.10M | 82 |
| 180-day window, old deficit as a single balance | $2.67M | 56% | 17% / 22% | $0.10M | 99 |
| 180-day window, rebuilt from 10 August | $2.77M | 58% | 18% / 23% | $0.14M | 95 |
| Reserve $37.7M (point 4) | $2.92M | 57% | 19% / 23% | $0.17M | 71 |
| Quarterly reset | $2.71M | 66% | 29% / 33% | $0.19M | 92 |
| 90-day window, old deficit as a single balance | $2.80M | 66% | 29% / 33% | $0.28M | 90 |
| 90-day window, rebuilt from 10 August | $2.87M | 69% | 31% / 36% | $0.35M | 50 |
| Accumulates, new allocator from zero | $2.77M | 84% | 44% / 47% | $0.27M | 2 |
| Quarterly reset, new allocator from zero | $2.90M | 87% | 46% / 49% | $0.38M | 2 |
| Does not accumulate | $2.98M | 93% | 50% / 53% | $0.44M | 2 |

### Conclusions for point 7

- **The current NEST remembers the entire history of revenue shortfall relative to the reserve:** future surplus first restores the negative budget and only then becomes available. Limiting this memory speeds up the resumption of buybacks, but in my stress tests it also raises the frequency of buybacks over horizons where the DAO's cash flow is negative. The scale of this trade-off depends on how quickly past shortfall is forgotten: the soft options (decay of 0.5% per day, the 180-day window) raise the share of loss-making years to 16–18%, the hard ones (quarterly reset, 90-day window, "does not accumulate") to 29–50%.
- **Debt policy answers a different question than the reserve and the share:** not "how much surplus to direct to buybacks", but "how long past shortfall should affect the future ability to buy". On my risk metrics, write-off rules produce a larger increase in the share of loss-making years per additional dollar of buybacks than changes to the share do.
- **The decision on the new allocator's starting budget matters no less than the choice of policy.** Starting from zero, that is, writing off the entire −$542,451 deficit, under the current rule raises the share of loss-making years among years with purchases from 12% to 44%; the current deficit itself is now acting as a brake. This is not the same as compensating for the four launch days: that writes off only $147,658 and raises this share only from 12% to 15% (variant 2 in point 4). Risk rises sharply when, together with the launch effect, the part of the deficit that arose from a real revenue shortfall in the summer and early autumn is also written off. "Loss-making year" here does not mean a loss from the buybacks themselves, but that NEST buys in a year that the DAO ends with negative cash flow.
- **If the only goal is to fix the launch effect, this calls for a targeted adjustment of $147,658, not a change of debt policy,** because most write-off rules also write off the rest of the deficit along the way.
- **Risk in all the tables depends on the version of CSM rebate accounting:** in version A the share of loss-making years is 3–5 points higher, while the ranking of the rules does not change.

### Open questions

- Does the DAO believe that buybacks should start only after past weak periods have been worked off? The answer determines whether limiting debt memory is acceptable in principle.
- If limited memory is needed, what horizon does the DAO consider reasonable: a quarter, half a year or a year, and with what budget should the new allocator start?

### What to check next

- **Point 8, caps:** whether the daily and annual caps affect the result under different rules.
- **Expense-based threshold (points 9–10):** what if, instead of a fixed reserve, revenue is compared with the DAO's actual expenses.

## Point 8. Caps

### Description

NEST has three limits on allocating money for buybacks: no more than $50,000 per day (a midnight to midnight UTC window), no more than $10M per 365 days from activation (the first window runs until 10 August 2027) and no less than $1,000 per allocation. An important feature: if a cap triggers, the unspent budget does not disappear, it stays and waits for the next day or the next annual window. So caps primarily stretch buybacks over time rather than cancel them. Under LIP-36, the daily cap is the main limiter in case of an error or an attack.

I compared a daily cap of $25k, $50k (as now), $100k and none; an annual cap of $5M, $10M (as now), $15M and none; no caps at all; and a minimum allocation of $10k. First under the current rule (reserve $40M, share 50%), then with a 100% share, where caps trigger more often. To see when a cap triggers, I added counters to the engine for days on which the allocation hit the daily or annual cap.

### Findings

- **On history, the caps never triggered.** Not a single allocation in the historical calculation was limited by the daily or annual cap, so the current rule would have bought $1.07M over 2025–2026 under any caps.
- **Going forward under the current rule, the daily cap triggers at least once in 22% of random scenarios, the annual cap in 4%.** Without caps, average buybacks over 12 months would be $2.96M instead of $2.48M; this difference is not lost, it stays in the budget (about $0.48M on average at year end) and is spent later.
- **Over a 12-month horizon and in these scenarios, caps do not change the set of paths in which at least one purchase happens, so they do not change the share of loss-making years.** Under every cap variant it stays at 12% (18% in variant 3), and the average peak front-running is $0.04M. Caps scale the purchase amount within scenarios where purchases happen anyway.
- **With a 100% share, caps become the main limiter.** The daily cap triggers in 40% of scenarios, the annual cap in 14%; without caps, average buybacks would rise from $3.67M to $6.21M. At ETH $4,500 and a 100% share, the mechanism hits the daily cap on 252 days out of 365, and by year end $14.3M remains unspent in the budget.
- **A daily cap of $25k noticeably cuts buybacks**, by a quarter under the current rule ($1.84M instead of $2.48M); a $100k cap almost removes the limit at the current share.
- **A minimum allocation of $1,000 or $10,000 does not change the total buyback volume or the risk metrics in my runs.**
- **The daily cap and execution.** $50k per day is about 18.7 stETH, so the current stETH balance on the allocator (41 stETH) is enough for roughly two days of purchases at the cap. At the current price this is roughly one maximum-size executor order (20 stETH). For scale: average daily LDO trading volume is about $34M, and LDO order book depth on major exchanges, according to data from the discussion of the market-making mandate on the Lido forum, is measured in tens of thousands of dollars per side within ±2%. The daily cap is of the same order, but a direct comparison is limited: NEST executes through CoW Swap and can draw liquidity from other venues, so these data cannot tell us how its purchases would move the price; the model does not account for this either.

### Questions I asked

1. Did the caps trigger on history, and how often will they trigger going forward?
2. Is money lost when a cap triggers, or is it deferred?
3. Do caps affect the risk of purchases in loss-making years?
4. How do caps interact with more aggressive rules?

### How I collected the data

- I added counters to the engine for days when the allocation hit the daily or annual cap, and for the remaining budget at the end of the period; the engine self-check passed unchanged after this.
- History from 1 January 2025 with a zero budget, 12 months forward at a constant ETH price of $3,000, $3,500 and $4,500, and 1,500 random ETH price paths, under the current rule and with a 100% share. Variants 1 and 3 for the current rule, variant 1 for the 100% share.

### Results

Table 1. Stress test, 1,500 ETH price paths, 12 months, current rule, variant 1 (variant 3 in brackets).

| Caps | Allowed to buy, average | P(loss-making year for the DAO when buying) | P(daily cap triggered) | P(annual cap triggered) | Remaining budget at end, average |
| --- | --- | --- | --- | --- | --- |
| As now: $50k per day, $10M per year | $2.48M ($2.87M) | 12% (18%) | 22% | 4% | $0.48M |
| Daily $25k | $1.84M ($2.17M) | 12% (18%) | 39% | 0% | $1.12M |
| Daily $100k | $2.72M ($3.14M) | 12% (18%) | 8% | 6% | $0.25M |
| No daily cap | $2.86M ($3.32M) | 12% (18%) | 0% | 6% | $0.10M |
| Annual $5M | $2.06M ($2.35M) | 12% (18%) | 23% | 17% | $0.90M |
| Annual $15M or no annual cap | $2.54M ($2.96M) | 12% (18%) | 22% | 0% | $0.42M |
| No caps at all | $2.96M ($3.46M) | 12% (18%) | 0% | 0% | $0 |
| Minimum allocation $10k | $2.48M ($2.87M) | 12% (18%) | 22% | 4% | $0.48M |

The probability of at least one purchase is 50% in all rows (about 59% in variant 3). The average peak front-running is computed on purchases actually executed after caps and is almost the same in all rows, $44.4–44.8k: it arises on paths where purchases start while the DAO's cumulative profit is not yet positive, and these are small amounts below the cap, while caps trigger later, when ETH is expensive and profit has already accumulated. With a 100% share the peak depends noticeably on the caps: from $271k with a $25k daily cap to $377k with no caps.

Table 2. The same with a 100% share, variant 1.

| Caps | Allowed to buy, average | P(loss-making year for the DAO when buying) | P(daily cap triggered) | P(annual cap triggered) | Remaining budget at end, average |
| --- | --- | --- | --- | --- | --- |
| As now | $3.67M | 19% | 40% | 14% | $2.53M |
| Daily $25k | $2.50M | 19% | 52% | 0% | $3.68M |
| Daily $100k | $4.32M | 19% | 23% | 19% | $1.89M |
| No daily cap | $4.97M | 19% | 0% | 19% | $1.24M |
| Annual $5M | $2.72M | 19% | 41% | 28% | $3.47M |
| Annual $15M or no annual cap | $3.96M | 19% | 40% | 0% | $2.25M |
| No caps at all | $6.21M | 19% | 0% | 0% | $0 |

Table 3. 12 months at a constant ETH price of $4,500, variant 1: buybacks, days hitting the daily and annual cap, remaining budget at the end.

| Caps | Current rule | Share 100% |
| --- | --- | --- |
| As now | $12.60M; 52 / 33 days; remaining $0.58M | $12.60M; 252 / 107 days; remaining $14.31M |
| Daily $25k | $8.77M; 350 / 0 days; remaining $4.41M | $8.95M; 358 / 0 days; remaining $17.96M |
| No caps at all | $13.18M; nothing remaining | $26.91M; nothing remaining |

At ETH $3,500 under the current rule, the caps do not trigger at all. Amounts above $10M are possible because the 12 months from 1 October span two annual cap windows.

### Conclusions for point 8

- **Caps do not explain NEST's inactivity, but they are a protective execution limiter.** They do not determine whether a surplus arises, and so they barely change the probability that NEST starts buying at all. What they do limit is the speed at which the accumulated budget can be spent, and the maximum losses in case of an error or a failure in the input data: under LIP-36, the daily cap limits the allocation, computed at the oracle price, to roughly $300k over the \~6 days governance needs to respond. This is not an absolute damage ceiling: if the stETH price in the oracle itself is corrupted, the real value of the stETH allocated can exceed the nominal cap. My metric of the share of loss-making years does not measure this kind of risk, so it barely depends on caps, even though they noticeably limit the actual purchase volume.
- **At the current parameters, caps mainly limit the speed of execution, not the right to buy back.** Over a year they defer about $0.5M to the next period. With a more aggressive reserve or share their importance grows sharply: the allowed budget does not vanish, it piles up in an execution queue; with a 100% share and ETH at $4,500, that queue holds $14.3M by year end.
- **If the share or the reserve is changed, the caps need to be revisited along with them,** otherwise a large part of the allowed buybacks will pile up in the budget. The daily cap should also be weighed against LDO liquidity, which the model does not account for.
- **Without an allocator top-up, purchases at $50k per day cannot be sustained for more than about two days in a row:** a balance of 41 stETH is roughly two days of purchases at $50k.

### Open questions

- What was the basis for choosing the $50k daily cap: LDO liquidity, the risk of error, or the desired annual volume?
- Is there a plan to revisit the caps together with the allocator top-up rule?

### What to check next

- **Points 9–10, expense-based threshold:** what if, instead of a fixed reserve, revenue is compared with the DAO's actual expenses.

## Points 9–10. Expense-based threshold and reporting lag

### Description

In points 4–8 I varied the parameters of the current NEST, where the threshold is a fixed $40M. Here I test a different idea: compare revenue not with a fixed number but with expenses, so that buybacks get whatever remains above actual spending. This means Foundations expenses specifically (the Foundations’ Expenses line in the reports), not all DAO expenses: one-off expenses such as the $6.06M for Kelp in the second quarter of 2026 are not included in it. So even a perfect expense-based threshold ties buybacks to operating profitability, not to the DAO's bottom line.

I compared four thresholds at a 50% share and the current debt policy:

1. **Fixed $40M,** as now.
2. **Actual expenses, a full-information benchmark:** on history the threshold equals actual Foundations expenses for the same period, known in hindsight; going forward it equals a given path of future expenses (see the table below), as if the mechanism knew it in advance. This cannot be implemented; it is a benchmark that shows the value of accurate expense information.
3. **Latest published expense run rate:** the threshold equals the annual run rate from the latest released report, exactly as it was published as of that date. This is an implementable option with no look-ahead.
4. **Budget-based threshold:** in 2026, the base part of EGG-2026, $43.8M (the first-half report later mentions a $41M base; the discrepancy is not explained, see points 0 and 11–14). For 2025 I did not find a comparable approved budget: the DAO approved up to $77M in grants as a maximum amount, which is a different construct. So for 2025 I used a proxy, the 2024 actual of $52.0M, and the historical result of this rule for 2025 does not support strong conclusions.

Since expenses relate to the whole DAO, I tested each threshold on two bases from point 6: the NEST base and expanded income. I ran three starting-point variants; risk is in version B of the CSM rebate accounting.

The expense rates used:

| What | Amount | Annual run rate |
| --- | --- | --- |
| 2024 actual (in the materials I found, first appears in the 17 March 2026 report) | $52.1M | $52.0M |
| 2025 actual (in reports from 17 March 2026) | $45.5M | $45.5M |
| Q1 2026, as published on 4 June | $6.44M | about $26.1M |
| First half of 2026 (in reports from 28 August) | $14.33M | about $28.9M |
| Second half of 2026, derived: Lido's full-year 2026 forecast of $37.7M minus the first-half actual | about $23.4M | about $46.4M |
| 2027 in the model (assumed equal to the 2026 forecast) | $37.7M | $37.7M |
| EGG-2026 base part | $43.8M | $43.8M |

In the first-half report the first quarter was restated to $6.92M (Lido mentioned quarter-close adjustments); for actual expenses in hindsight I use the restated figures, and for the published run rate I use the figure that was available as of the date. I annualise run rates by the number of days in the period. The $46.4M forecast for the second half is my own calculation from Lido's full-year forecast, not a separately published forecast.

### Findings

- **In the full-information benchmark, tying the threshold to Foundations expenses gives roughly the same buyback volume as the fixed $40M, but with noticeably lower risk.** In the stress test it is $2.42M versus $2.48M on the NEST base, the share of loss-making years among years with purchases is 5% versus 12%, and the peak overshoot is $0.01M. This shows the value of up-to-date expense information, but it is not an implementable rule. The figure is 5% rather than zero because the threshold only accounts for Foundations expenses, while the DAO's bottom line also depends on other items.
- **The implementable option based on the latest published run rate is especially vulnerable when expenses change faster than reports come out.** I can reproduce its history without look-ahead only from 17 March 2026: I did not find an earlier comparable published figure for Foundations expenses, and the operating expense data available in 2025 is structured differently. Over the period available for a fair test, from 17 March 2026, none of the implementable rules got as far as making purchases; the published run rate threshold came closest. In 2026 it errs toward excess purchases: the Foundations deliberately cut spending in the first half after the market fell and shifted part of it to later months, so the latest report shows about $28.9M a year, while about $46.4M is expected in the second half. The low first-half run rate stays as the threshold long after expenses have accelerated. Going forward the rule buys a lot and at the wrong time: in the stress test it buys $5.14M a year with 48% loss-making years and a peak overshoot of $1.69M; at ETH $2,680 it would buy $5.10M against a modelled DAO operating result of about $1.78M for the year.
- **Of the four thresholds tested, the EGG base gives the smallest buyback volume and the lowest values on my risk metrics.** $43.8M is above the current reserve and above the expense level assumed in the model for 2027, $37.7M, so it buys the least of all ($1.87M) and with the lowest share of loss-making years (4%).
- **Under the new fee regime the benchmark would have bought more than the current NEST:** $1.52M versus $0.38M since 25 December 2025, because in the first half of 2026 Foundations expenses were low and the DAO was operationally in profit, while the fixed $40M threshold did not see this.
- **Expanded income instead of the NEST base** slightly increases buybacks under all thresholds and slightly raises risk, but does not change the picture.

### Questions I asked

1. How would the mechanism behave if the threshold equalled actual Foundations expenses?
2. What happens to the implementable option, which sees expenses only through released reports?
3. How is the budget-based threshold different?
4. Does switching from the NEST base to expanded income change the picture?

### How I collected the data

- I took expense rates by period and report publication dates from Lido's reports; the run rate known as of a date changes only on the day a report is released and equals the figure published that day.
- During checking I found and fixed an error in the model: for the first quarter of 2026 the published run rate was set to the later restated figure of $6.92M instead of the $6.44M published on 4 June. The fix did not affect the results of these points, but it changes one stage 1 result in the model table (threshold on known expenses with quarterly debt reset: $0.50M instead of $0.19M on history).
- History from 1 January 2025 with a zero budget. During checking it turned out that for the published run rate threshold this is look-ahead: the 2024 expense actual ($52.1M) first appears in the materials I found on 17 March 2026, and from 2025 data I found only year-to-date operating expenses (the progress report of 2 October 2025: $21.5M to 31 August and a target run rate of $31.4M a year), which is a different, non-comparable item. So I count the history of this threshold only from 17 March 2026 and recalculated the other thresholds on the same window.
- 12 months forward from 1 October 2026 at constant ETH prices of $2,680, $3,000 and $3,500 and 1,500 random ETH price paths, in three starting-point variants.

### Results

Table 1. History, with the rule notionally launched with a zero budget.

| Threshold | 01.01.2025–28.09.2026, NEST base | Same, expanded income | Window 17.03–28.09.2026, NEST base | Same, expanded income |
| --- | --- | --- | --- | --- |
| Fixed $40M (now) | $1.07M | $0.64M | $0 (end budget −$2.37M) | $0 (−$2.16M) |
| Full-information expenses (benchmark) | $0.42M | $0.31M | $0.42M (−$2.06M) | $0.48M (−$1.89M) |
| Latest published run rate | not reproducible | not reproducible | $0 (−$0.87M) | $0 (−$0.65M) |
| Budget (2026: EGG base $43.8M) | only with a proxy for 2025 | only with a proxy for 2025 | $0 (−$3.39M) | $0 (−$3.18M) |

The published run rate threshold cannot be reconstructed for 2025: I did not find an earlier comparable published figure for Foundations expenses (the 2024 actual first appears in the materials I reviewed in the 17 March 2026 report), so its history is counted only from 17 March 2026. For a fair comparison, the other thresholds are also calculated on the same window. The modelled DAO operating result (expanded income minus Foundations expenses) for the window is negative, about −$2.84M. None of the implementable rules got as far as purchases in this period. The published run rate threshold came closest to purchases (end budget −$0.87M versus −$2.37M for the fixed $40M), because from June it relied on low first-half expenses. Separately for the benchmark, which by definition has no look-ahead problem: under the new fee regime, since 25 December 2025, it would have bought $1.52M (on expanded income $1.80M) versus $0.38M ($0.41M) for the fixed $40M.

Table 2. Next 12 months at a constant ETH price, NEST base: days until the first purchase and how much the rule allows to buy, variants 1 / 2 / 3.

| Threshold | ETH $2,680 | ETH $3,000 | ETH $3,500 |
| --- | --- | --- | --- |
| Fixed $40M (now) | none / none / 165 days; $0 / $0 / $0.38M | 79 / 58 / 37 days; $1.94M / $2.09M / $2.85M | 31 / 23 / 18 days; $5.69M / $5.84M / $6.70M |
| Full-information expenses (benchmark) | none / none / 277 days; $0 / $0 / $0.43M | 164 / 149 / 119 days; $2.00M / $2.15M / $2.90M | 64 / 47 / 29 days; $5.75M / $5.90M / $6.76M |
| Latest published run rate | 35 / 25 / 19 days; $5.10M / $5.24M / $5.93M | 24 / 17 / 14 days; $7.49M / $7.64M / $8.40M | 16 / 12 / 9 days; $11.24M / $11.39M / $12.26M |
| Approved EGG budget | no purchases | 339 / 246 / 96 days; $0.04M / $0.19M / $0.95M | 45 / 33 / 25 days; $3.79M / $3.94M / $4.80M |

At ETH $2,680 the modelled DAO operating result for 12 months (net staking revenue plus Earn and treasury income with the CSM rebate, minus Foundations expenses; version B) is about $1.78M; the published run rate rule allows $5.10M of buybacks and at its maximum runs ahead of the accumulated result by $3.37M. This is not cash flow in the strict sense: Lido's reporting is on an accrual basis.

Table 3. Stress test, 1,500 ETH price paths, 12 months, variants 1 / 2 / 3.

| Threshold and base | Allowed to buy, average | P(at least one purchase) | P(loss-making year for the DAO when buying) | Average peak overshoot, variant 1 |
| --- | --- | --- | --- | --- |
| $40M, NEST base (now) | $2.48M / $2.55M / $2.87M | 50% / 53% / 59% | 12% / 15% / 18% | $0.04M |
| $40M, expanded income | $2.68M / $2.76M / $2.80M | 55% / 57% / 59% | 16% / 19% / 22% | $0.09M |
| Full information, NEST base | $2.42M / $2.48M / $2.78M | 45% / 46% / 51% | 5% / 6% / 7% | $0.01M |
| Full information, expanded income | $2.61M / $2.68M / $2.72M | 49% / 50% / 51% | 7% / 8% / 9% | $0.02M |
| Published run rate, NEST base | $5.14M / $5.26M / $5.68M | 90% / 94% / 97% | 48% / 50% / 49% | $1.69M |
| Published run rate, expanded income | $5.59M / $5.71M / $5.78M | 95% / 97% / 98% | 50% / 52% / 52% | $2.10M |
| EGG budget, NEST base | $1.87M / $1.92M / $2.19M | 38% / 40% / 45% | 4% / 6% / 9% | $0.01M |
| EGG budget, expanded income | $2.00M / $2.06M / $2.10M | 42% / 44% / 45% | 6% / 9% / 11% | $0.01M |

### Conclusions for points 9–10

- **The problem with an expense-based threshold is not the idea itself but the information.** With full information it aligns budget accumulation well with the DAO's operating result after Foundations expenses: buybacks are about the same as now, and the share of purchases made in loss-making years is noticeably lower. When only the latest published run rate is used, the result can be badly wrong when the spending pattern changes.
- **A threshold based on Foundations expenses ties buybacks to operating profitability but does not guarantee a positive bottom line for the DAO:** it does not see one-off expenses outside the Foundations line.
- **The budget-based threshold works as a conservative fixed threshold:** it does not track actual expenses, but it does not suffer from the lag either.
- **This leaves two paths:** a forecast or budget with update rules, or a provisional accrual based on estimated expenses with a later true-up against the actual report. The second path is covered in points 11–14.

### Open questions

- How reliable is the expense forecast for the second half of 2026 ($46.4M a year), and what budget is expected for 2027?
- Can expense data be obtained faster than once a quarter with a 2–3 month lag?

### What to check next

- **Points 11–14, true-up against reports:** a mechanism that accrues the budget at a provisional expense run rate and corrects it with actual figures once the report is out.

## Points 11–14. True-up against reports

### Description

Points 9–10 showed that tying buybacks to expenses works with full information and breaks down when the mechanism sees expenses with a lag. The true-up works in two steps. Before a report, the budget is topped up every day with a provisional share of the modelled operating result based on estimated expenses. After the report, the provisional accruals for the closed quarter are replaced with a final share of the quarter's result with actual expenses and one-off losses.

For quarter q, the provisional accrual is:

```latex
P_q = \sum_{t \in q} \alpha_{pre} \, (R_t - \hat{E}_t)
```

After the report, the quarter's result, the final value and the adjustment are calculated:

```latex
X_q = R_q - E_q - L_q, \qquad F_q = \alpha_{+} \max(X_q, 0) + \alpha_{-} \min(X_q, 0)
```

```latex
TU_q = F_q - P_q, \qquad \text{budget} \leftarrow \text{budget} + TU_q
```

For a symmetric final share, α+ = α−; for full recognition of losses, α− = 100%. Unless stated otherwise, in the main variant the provisional share is α\_pre = 50%, the final share is α+ = α− = 100%, and the negative budget policy and caps stay as they are now. So the main variant tests two decisions at once: the true-up of expenses against reports, and sending 100% of the trued-up result to the budget instead of 50%. Even with expenses guessed exactly, the adjustment is not zero: with a quarterly result of +$10M, $5M is accrued provisionally and another $5M after the report. To separate the effect of the true-up itself from the choice of share, final shares of 50% and 75% are shown separately.

Here R is the DAO's expanded income (net staking revenue, Earn, treasury income), Ê is the provisional expense run rate, E is actual Foundations expenses, L is one-off DAO expenses and losses taken into account in the true-up, and α are the shares. In the model only expenses and one-off losses are recalculated after the report, while revenue, Earn and treasury income are taken as in the provisional accrual; in reality they would also need to be taken from the report. So in the model the true-up brings the budget to the trued-up modelled result, not to the quarter's fully actual financial result. If the final value comes out negative, the budget goes into deficit, and future purchases are blocked until it recovers.

**The true-up corrects the future budget but does not undo purchases already made.** If before the report the mechanism spent money that, according to the actual figures, it should not have spent, it cannot be returned: the only option is to push the budget into deficit and stop subsequent purchases.

The identity has been verified: if purchases are disabled, the budget after true-ups exactly equals the sum of F over trued-up quarters plus provisional accruals for days not yet trued up; the discrepancy is $0.

What I tested:

- **Provisional run rate (point 12):** $37.7M (Lido's forecast for 2026), $41.0M (the base from the first-half report), $43.8M (the EGG-2026 base), $46.4M (the derived second-half run rate) and the latest published run rate.
- **Final share (point 13):** 50, 75 and 100%. In the engine it applies to a quarterly result of either sign, meaning that at 50% only half of a loss goes into the budget too; so I separately tested variants where the share for profit is 50% or 75% and losses are recognised at 100%.
- **Variant "provisional 100%, deficit no deeper than 90 days".**
- **A 20% expense cut (point 14)** in three scenarios: the cut is real and built into the provisional run rate in advance; real but not built in; built in but did not happen.
- **Report lag:** 30, 60, 90 and 120 days after quarter end.

For comparison, the current NEST, the stepped share from point 5 and the published run rate threshold without true-up from points 9–10 were run on the same paths. Going forward, reports by default come out \~60 days after the quarter; expenses in 2027 are assumed at $37.7M.

**The starting budget of the new rule is a separate decision, and it turned out to be one of the strongest levers.** The current deficit of −$542,451 is calculated on a different measure (relative to $40M on the NEST base), so I tested five variants:

1. **Carry over the current deficit** of −$542,451.
2. **Start from zero.**
3. **Reconstruct under the new methodology from the NEST activation on 10 August 2026:** −$445,449; the rule would not have made any purchases in this period, so this is the balance it would have accumulated.
4. **Retroactively recognise the accrued result from 1 January 2026.** Under the true-up formula with one-off losses this is −$3,980,531: trued-up Q1 +$2.78M, trued-up Q2 +$0.59M before one-off losses and −$6.06M of the one-off Kelp expense, provisional Q3 −$1.29M (as of the transition date Q3 is not yet trued up, so this balance is also partly provisional). If the one-off Kelp expense is not included in the true-up, the result is +$2,079,469, and then the past operating profit immediately becomes available for buybacks.
5. **Counterfactual from 1 January 2026:** the rule runs and buys from the start of the year; it would have bought $2.14M in the first half and on 30 September would stand at −$61,811 excluding Kelp, or about −$6.12M including it. This variant describes a state in which hypothetical purchases have already been made, while in reality there were none, so it is not suitable as a starting budget at transition and is shown for comparison.

### Findings

- **The rule with an expense-based threshold and true-up lowers the risk metrics compared with the current NEST; the final share additionally determines the buyback volume.** The main variant (provisional run rate $43.8M, provisional share 50%, final share 100%) gives $2.80M in the price stress test versus $2.48M for the current NEST, with a share of loss-making years among years with purchases of 7% versus 12%. If the final share is kept at 50%, as in the current NEST, buybacks drop to $2.27M and the share of loss-making years stays at about 6%. But compared with the current NEST several things change here at once: the revenue base, an expense-based threshold instead of $40M, the true-up and the final share. The separate comparison below shows the role of the true-up itself. With all shocks (expenses, one-off losses, report lags) the volume is almost the same, $2.29M versus $2.22M, but the risk is lower: 15% versus 20%, peak overshoot $0.20M versus $0.30M, and a peak above $1M in 7% of paths versus 10%.
- **A higher provisional run rate reduces buyback volume, but reduces risk much more.** From $37.7M to $46.4M, average buybacks fall from $3.26M to $2.63M in the price stress test (by 19%) and from $2.85M to $2.10M with shocks (by 26%), while the share of loss-making years falls from 23% to 5% and from 31% to 12% respectively.
- **A provisional run rate taken from the latest published report does not rescue the true-up.** It is low right now ($28.9M a year), and before each report the mechanism manages to accrue and spend too much, while the true-up corrects the budget only after the purchases. The result is almost the same as without a true-up: $4.28M of buybacks and 50% loss-making years.
- **In the first year the final share has almost no effect on risk, but it is not just a choice between buybacks and the treasury.** With a symmetric share of 100%, 75% and 50%, the share of loss-making years is 7%, 7% and 6%, and buybacks are $2.80M, $2.60M and $2.27M. If losses are recognised at 100% and profits at 75% or 50%, buybacks are slightly lower ($2.53M and $2.15M) with the same risk; over a one-year horizon the difference is small, but over a long horizon a symmetric share systematically forgives part of the losses.
- **A 20% expense cut gives different results depending on whether the mechanism knows about it in advance.** If the cut is real and built into the run rate, buybacks almost double ($5.49M) with 8% loss-making years. If it is real but not built in, the mechanism learns about it only from reports: buybacks are lower ($4.63M), and risk is even lower (2%). If it is built in but does not happen, the true-up corrects the error only partially: $3.51M with 33%.
- **Report lag matters when expenses are above plan.** With expenses on plan it barely changes risk. With a 20% overspend and the EGG base, increasing the lag from 30 to 120 days raises the share of loss-making years from 25% to 32% and the peak overshoot from $0.14M to $0.26M. Once all reports are in, the trued-up quarterly accruals do not depend on the lag, but the final budget differs, because with different lags a different volume of irreversible purchases gets executed before the true-up.
- **The starting budget changes risk more than many of the rule's parameters.** With the current deficit carried over, the share of loss-making years is 7%; reconstructed from 10 August, 9%; starting from zero, 23%; and with retroactive recognition of the result from 1 January excluding the one-off Kelp expense (+$2.08M), as much as 53% with an average peak overshoot of $2.06M. Including Kelp, the same variant gives −$3.98M, the smallest buyback volume ($1.68M) and the lowest value of my risk metric among the starting states tested (0% on 1,500 modelled paths, which does not mean there is no risk).

**What the true-up itself gives.** To isolate its effect, I compared the same rule with and without the true-up: DAO expanded income, a threshold at the EGG base of $43.8M, a 50% share, on the same 1,200 paths, starting from the actual budget.

| Expenses | Without true-up: buybacks / loss-making year / peak | With true-up, final 50% | With true-up, final 100% |
| --- | --- | --- | --- |
| On plan, price only | $2.03M / 6% / $0.01M | $2.31M / 6% / $0.01M | $2.84M / 7% / $0.03M |
| 20% above plan | $2.03M / 30% / $0.42M | $1.52M / 22% / $0.20M | $1.64M / 22% / $0.20M |
| 20% below plan | $2.03M / 0% / $0 | $3.44M / 1% / $0 | $4.68M / 3% / $0.02M |
| Random expense shocks, one-off expenses, report lags | $1.81M / 13% / $0.17M | $1.91M / 13% / $0.14M | $2.29M / 16% / $0.22M |

Conclusions from this comparison: with expenses on plan the true-up does not reduce risk; the risk reduction against the current NEST in the price stress test comes from the expense threshold at the EGG base level together with the expanded base. The true-up works when actual expenses differ from plan: with an overspend it cuts buybacks and lowers the share of loss-making years from 30% to 22%, and halves the peak overshoot; with savings it allows more buybacks with almost no risk. With symmetric random shocks these effects partly cancel each other out.

### Questions I asked

1. Does the true-up mechanics add up, and what exactly can it correct?
2. Which provisional run rate gives the best balance of buybacks and risk?
3. What is the effect of the final share, an expense cut, report lag and the starting budget?
4. How does the true-up compare with the current NEST and the rules from previous points on the same paths and with the same shocks?

### How I collected the data

- I verified the true-up identity on a run without purchases.
- I reconstructed the starting budget under the new methodology on actual data from 10 August 2026 and from 1 January 2026, with true-ups against the reports for the first and second quarters of 2026 on their release dates; for 1 January I calculated both the accrual balance without purchases and the counterfactual with hypothetical purchases.
- 12 months forward from 1 October 2026 at a constant ETH price and on 1,500 random ETH price paths, with risk in versions B and A of the CSM rebate accounting.
- A separate stress test with shocks on 1,500 paths: quarterly expenses are multiplied by a random factor (15% volatility), with a 25% probability per year a one-off loss of $3M, $6M or $10M occurs, and each report comes out after a random 45–120 days; one-off losses enter both the DAO result and the true-up.
- Sensitivity to lag: 800–1,000 paths, a lag of 30–120 days, expenses on plan and 20% higher. To see the fully trued-up budget, each path is extended by 150 days with no new revenue or expenses until all reports are in.
- All 12-month metrics describe the state at the end of the window: with a long lag, the last true-ups arrive after it ends.

### Results

Table 1. Price stress test, 1,500 ETH paths, 12 months, from the actual budget (the last column starts from zero).

| Rule | Allowed to buy, average | P(at least one purchase) | P(loss-making year when buying), B / A | Average peak overshoot | P(loss-making year when buying), start from zero |
| --- | --- | --- | --- | --- | --- |
| Current NEST | $2.48M | 50% | 12% / 15% | $0.04M | 44% |
| Share steps 50 / 75 / 100% (point 5) | $3.08M | 52% | 13% / 17% | $0.10M | 44% |
| Published run rate without true-up (points 9–10) | $5.59M | 95% | 50% / 52% | $2.10M | 53% |
| True-up, prov. run rate $37.7M | $3.26M | 59% | 23% / 22% | $0.24M | 53% |
| True-up, prov. run rate $41.0M | $2.99M | 51% | 13% / 13% | $0.06M | 40% |
| True-up, prov. run rate $43.8M (EGG base) | $2.80M | 47% | 7% / 6% | $0.03M | 23% |
| True-up, prov. run rate $46.4M | $2.63M | 45% | 5% / 4% | $0.02M | 13% |
| True-up, prov. run rate = latest published | $4.28M | 93% | 50% / 51% | $1.29M | 53% |
| True-up $43.8M, final 75% for profit and loss | $2.60M | 46% | 7% / 5% | $0.02M | 23% |
| True-up $43.8M, final 75% for profit, 100% for loss | $2.53M | 45% | 7% | $0.02M | n/a |
| True-up $43.8M, final 50% for profit and loss | $2.27M | 46% | 6% / 5% | $0.01M | 22% |
| True-up $43.8M, final 50% for profit, 100% for loss | $2.15M | 42% | 6% | $0.01M | n/a |
| True-up $43.8M, prov. 100%, 90-day floor | $3.25M | 50% | 11% / 9% | $0.07M | 23% |
| True-up $43.8M, −20% real and built into run rate | $5.49M | 78% | 8% / 8% | $0.08M | 26% |
| True-up $43.8M, −20% real but not built in | $4.63M | 71% | 2% | $0.02M | n/a |
| True-up $43.8M, −20% built in but did not happen | $3.51M | 69% | 33% / 33% | $0.47M | 53% |

Table 2. True-up at the EGG base ($43.8M) with different starting budgets, same stress test.

| Starting budget | Allowed to buy, average | P(at least one purchase) | P(loss-making year when buying) | Average peak overshoot |
| --- | --- | --- | --- | --- |
| Carry over current deficit −$542,451 | $2.80M | 47% | 7% | $0.03M |
| Reconstructed under the new methodology from 10.08.2026: −$445,449 | $2.84M | 48% | 9% | $0.04M |
| Counterfactual: the rule ran and bought from 01.01.2026, −$61,811 | $3.01M | 55% | 19% | $0.10M |
| From zero | $3.04M | 59% | 23% | $0.13M |

Retroactive recognition of the result from 1 January, on the same paths: including the one-off Kelp expense (−$3,980,531), average buybacks are $1.68M, at least one purchase in 34% of paths, 0% loss-making years among years with purchases, peak overshoot close to zero; excluding Kelp (+$2,079,469), buybacks are $4.85M, a purchase in 100% of paths, 53% loss-making years, average peak overshoot $2.06M. Counterfactual including Kelp (about −$6.12M): $1.22M, 27%, 0%. Without the one-off expense, such a start immediately releases the first-half operating profit into buybacks, and it is spent in a year that may turn out to be loss-making.

Table 3. Stress test with expense shocks, one-off losses and random report lag, 1,500 paths, from the actual budget, version B.

| Rule | Allowed to buy, average | P(at least one purchase) | P(loss-making year when buying) | Average peak overshoot | P(peak above $1M) |
| --- | --- | --- | --- | --- | --- |
| Current NEST | $2.22M | 49% | 20% | $0.30M | 10% |
| Share steps 50 / 75 / 100% | $2.79M | 51% | 22% | $0.47M | 16% |
| Published run rate without true-up | $5.36M | 94% | 54% | $2.51M | 70% |
| True-up, prov. run rate $37.7M | $2.85M | 60% | 31% | $0.53M | 19% |
| True-up, prov. run rate $41.0M | $2.52M | 51% | 22% | $0.31M | 11% |
| True-up, prov. run rate $43.8M (EGG base) | $2.29M | 45% | 15% | $0.20M | 7% |
| True-up, prov. run rate $46.4M | $2.10M | 42% | 12% | $0.13M | 5% |
| True-up, prov. run rate = latest published | $4.11M | 93% | 53% | $1.70M | 63% |
| True-up $43.8M, final share 50% | $1.89M | 43% | 12% | $0.13M | 4% |
| True-up $43.8M, prov. 100%, 90-day floor | $2.80M | 48% | 18% | $0.38M | 14% |

Table 4. Sensitivity to report lag, 1,000 paths, from the actual budget: average buybacks over 12 months, share of loss-making years when buying, average peak overshoot.

| Report lag | Expenses on plan, prov. $41.0M | Expenses on plan, prov. $43.8M | Expenses 20% higher, prov. $41.0M | Expenses 20% higher, prov. $43.8M |
| --- | --- | --- | --- | --- |
| 30 days | $2.80M; 14%; $0.09M | $2.67M; 10%; $0.06M | $1.54M; 37%; $0.26M | $1.42M; 25%; $0.14M |
| 60 days | $2.66M; 14%; $0.07M | $2.48M; 8%; $0.04M | $1.54M; 41%; $0.35M | $1.38M; 28%; $0.19M |
| 90 days | $2.42M; 13%; $0.06M | $2.19M; 7%; $0.03M | $1.53M; 42%; $0.42M | $1.32M; 30%; $0.23M |
| 120 days | $2.32M; 14%; $0.06M | $2.06M; 7%; $0.02M | $1.57M; 43%; $0.49M | $1.32M; 32%; $0.26M |

Table 5. Fully trued-up budget after all reports are in (paths extended by 150 days with no new revenue or expenses), 800 paths, EGG base.

| Report lag | Expenses on plan: average budget / P(budget in deficit) | Expenses 20% higher: average budget / P(budget in deficit) |
| --- | --- | --- |
| 30 days | −$2.22M / 61% | −$8.95M / 78% |
| 60 days | −$2.03M / 60% | −$8.92M / 78% |
| 90 days | −$1.75M / 59% | −$8.85M / 78% |
| 120 days | −$1.62M / 59% | −$8.85M / 78% |

Once all reports are in, the trued-up quarterly accruals do not depend on the lag. The final budget still differs (with expenses on plan, from −$2.22M to −$1.62M), because with different lags a different volume of purchases gets executed before the true-up, and those purchases are irreversible. In other words, the lag affects not the final economics of the quarters but how much was bought before the figures were corrected. A negative final budget means future purchases will be blocked until the DAO's result restores it.

Table 6. Next 12 months at a constant ETH price, from the actual budget: days until the first purchase and how much the rule allows to buy; the modelled DAO operating result for the year is $1.78M, $6.37M and $13.53M respectively (with a 20% expense cut, $9.76M, $14.34M and $21.50M).

| Rule | ETH $2,680 | ETH $3,000 | ETH $3,500 |
| --- | --- | --- | --- |
| Current NEST | no purchases | 79 days, $1.94M | 31 days, $5.69M |
| True-up, prov. run rate $41.0M | 332 days, $0.29M | 81 days, $4.20M | 32 days, $9.23M |
| True-up, prov. run rate $43.8M | 333 days, $0.03M | 241 days, $3.62M | 43 days, $8.65M |
| True-up, prov. run rate = latest published | 31 days, $2.08M (overshoot $2.08M) | 24 days, $5.82M | 17 days, $11.72M |
| True-up $43.8M, −20% real and built into run rate | 60 days, $6.40M | 36 days, $9.62M | 23 days, $12.60M |
| True-up $43.8M, −20% built in but did not happen | 60 days, $1.04M (overshoot $0.81M) | 36 days, $5.04M | 23 days, $10.45M |

Amounts above $10M are possible because the 12 months from 1 October span two annual cap windows.

### Conclusions for points 11–14

- **The true-up makes an error in the accounting budget temporary, but not the consequences of execution already done:** after the report the budget is brought to the period's result with actual expenses and one-off losses, and the error is carried into the future budget. But buybacks already made before the report are irreversible, so such a system has two independent protective parameters: how conservative the provisional expense run rate is and how quickly the true-up arrives.
- **In my 12-month tests the rule with an expense threshold at the EGG base level ($43.8M) and a true-up gives lower risk metrics than the current NEST; with expenses on plan the risk reduction comes from the threshold itself, while the true-up protects against actual expenses deviating from plan. Whether buyback volume is around the current NEST level or higher depends on the final share: $2.27M at 50%, $2.80M at 100%**. A run rate that is too low and outdated leads to early purchases that a later true-up can no longer undo.
- **The final share determines at the same time what part of profit goes to buybacks and what part of a loss is carried into the deficit.** In the first year it has almost no effect on risk; if you do not want the rule to forgive part of the losses, losses should be recognised at 100% whatever the profit share.
- **A real reduction in expenses gives the largest buyback increase of all the options tested, without a comparable rise in my risk metrics.** If the cut is built into the run rate in advance and does not happen, risk rises sharply; if it is not built in, the mechanism learns about it from reports and buys later, but more cautiously.
- **The starting budget of the new rule has to be chosen deliberately:** depending on what is treated as the inherited budget, the same rule gives a share of loss-making years from 0% to 53%. The transition rules are not a technical detail but a full economic parameter of the new mechanism; it matters especially whether past one-off expenses are included in the true-up under retroactive recognition. Carrying over the accumulated surplus as spendable budget is especially risky: it immediately releases past profit into buybacks without waiting to see how the current year turns out.

### Open questions

- Which provisional run rate is the DAO ready to fix: the EGG base ($43.8M), the $41M base from the half-year report, or the forecast, and how should it be updated?
- Can quarterly expense figures be published faster, at least provisionally?
- How should report results be fed into the mechanism technically: by vote, through Easy Track, or via a separate data source?
- What starting budget should the new rule launch with?

### What to check next

- **Points 15–18:** a combined stress test of all candidates, sensitivity and treasury protection.
- **Point 19:** what happens to the purchased LDO.

## Points 15–18. Combined stress test, sensitivity and treasury protection

### Description

In these points all candidates are run together, on the same paths and with the same assumptions, so that they can be compared directly. The set is built so that neighbouring rules differ, where possible, by a single decision. For each rule I note what is needed technically: under LIP-36 the current allocator can change the reserve and the share and connect additional revenue sources, but it cannot change the budget that has already accumulated.

| Rule | How it differs | What is needed technically |
| --- | --- | --- |
| A. Current NEST | starting point | nothing |
| B. NEST + launch compensation | A with a start of −$394,793 | direct compensation requires a budget adjustment mechanism or a move to a new allocator; a temporary parameter change can only make up the difference going forward, it does not fix the starting budget retroactively |
| C. NEST + CSM rebate as a source from 1 October | the CSM rebate is added to NEST revenue; past rebates are not credited | a new source contract and a vote, the same allocator |
| D. NEST, share 75% | A with a share of 75% | parameter only |
| E. NEST, share steps 50 / 75 / 100% | stepped share from point 5 | new budget logic |
| F. NEST, debt decay 0.5% per day | soft debt policy from point 7 | new budget logic |
| G. Expanded income, reserve $43.8M | expanded income instead of the NEST base and a reserve of $43.8M instead of $40M, share 50% | the reserve is a parameter; Earn and treasury income have to be connected as sources, if they can be measured onchain |
| H. G + true-up, final share 50% | G with a true-up | new budget logic |
| I. G + true-up, final share 100% | H with a final share of 100% | new budget logic |
| J. I + liquid treasury protection | a purchase is allowed only if after it the liquid treasury still holds at least N months of expenses | new budget logic |
| K. I + LDO price condition | purchases only when LDO is not above its 90-day average | new budget logic |
| L. Parametric part of the Aksusarya proposal | reserve $30M, share 100% | parameters only |

L does not model the other parts of the Aksusarya proposal: the Labs cut, the audit and the move to dynamic buybacks. The starting budget is the current one everywhere (−$542,451), except for B.

### Findings

- **Rule I improves on the current NEST on all main metrics at once, but it does not dominate every alternative.** On the same price paths I gives $2.57M of buybacks with 8% loss-making years versus $2.21M and 14% for the current NEST, and with shocks $2.24M and 16% versus $2.17M and 20%. The peak overshoot in the price-only test is the same ($0.05M), and with shocks it is lower ($0.24M versus $0.31M), as is the tail. But G reduces risk even further at the cost of lower volume, and E gives more buybacks at the cost of higher risk.
- **A higher threshold lowers risk, while expanded income raises it.** The move A → G changes both the revenue base and the reserve at once, so I split it into two steps. The $43.8M reserve alone on the NEST base gives $1.62M and 5% loss-making years; expanded income alone at $40M gives $2.40M and 18%. G ($1.75M and 7%) is the sum of two opposite effects.
- **Clean pairwise comparisons:** a true-up at the same share (G → H) adds about $0.3M without any increase in risk; a final share of 100% instead of 50% (H → I) adds about $0.55M with almost no increase in risk.
- **A small gain in buybacks does not necessarily mean a small increase in risk.** Launch compensation (A → B) adds only $0.06M, the CSM rebate (A → C) $0.26M, debt decay (A → F) $0.11M, yet in all three cases the share of loss-making years rises from 14% to 17%, and with shocks from 20% to 24–25%. A 75% share (A → D) adds about $0.7M with risk up by 4 points; steps (A → E) add about $0.6M with almost no increase in risk.
- **The conclusion on treasury protection depends entirely on how liquidity is defined.** With stETH at a 30% discount and 18 months of expenses, the protection triggers on 2–4% of paths and changes almost nothing. With a 50% discount and 24 months it already triggers on 34–36% of paths, cuts buybacks to $1.86–2.16M and lowers the share of loss-making years to 4–8%. If only stablecoins and fiat count as liquid (about $16.3M, less than 12 months of expenses), it blocks almost all purchases.
- **The LDO price condition should be judged by purchase price, not by my risk metric.** It cuts buybacks from $2.57M to $1.63M without changing the share of loss-making years, but the average model price of the LDO purchases actually made on these paths is $0.269 versus $0.338, 20% lower. Fewer tokens are bought (about 6.1M versus 7.6M), because fewer dollars are spent as well. The result depends on the LDO price model.
- **The $30M and 100% parameters give the largest buyback volume, but also the highest risk metrics** among the rules tested: in the price-only stress test about $6.9M, 53% loss-making years and an average peak overshoot of about $3.9M.
- **In a falling market risk rises for every rule.** At every volatility and ETH trend tested, the share of loss-making years for I is lower than for the current NEST, but the size of the advantage varies from scenario to scenario: for example, with a −30% trend it is 17% versus 26%, or 23% versus 33%.

### Questions I asked

1. Which rule is better than the current NEST on all metrics at once, and where does the trade-off begin?
2. What does each individual decision contribute?
3. Is the result robust to a calm or a nervous market and to ETH falling or rising?
4. What do the effects of treasury protection and the LDO price condition depend on?

### How I collected the data

- 12 rules on the same 1,200 ETH and LDO price paths (ETH volatility 61% annualised with no trend, LDO at 0.75 of ETH plus its own 90% noise), from the current budget, over 12 months from 1 October 2026; risk in version B of the CSM rebate accounting.
- The same rules on the same paths with shocks: quarterly expenses with 15% volatility, a one-off expense of $3M, $6M or $10M with a 25% probability per year, and a reporting delay of 45–120 days.
- The A → G breakdown into two steps and a test of treasury protection in nine variants (12, 18 and 24 months of expenses; stETH at a 30%, 50% and 100% discount, the last meaning stablecoins and fiat only) on the same paths.
- Sensitivity for five key rules: ETH volatility of 40%, 61% and 80% annualised and an average trend of −30%, 0 and +30% per year, with 450 paths per combination.
- While preparing this I found and fixed double counting of the CSM rebate in DAO profit in variant 3 (see the correction in point 4).

### Results

Table 1. Combined stress test, 1,200 identical paths, 12 months: price only and with all shocks.

| Rule | Price only: average buybacks | Price only: P(loss-making year when buying) | Price only: average peak overshoot | With shocks: buybacks | With shocks: P(loss-making year when buying) | With shocks: average peak / P(peak above $1M) |
| --- | --- | --- | --- | --- | --- | --- |
| A. Current NEST | $2.21M | 14% | $0.05M | $2.17M | 20% | $0.31M / 10% |
| B. + launch compensation | $2.27M | 17% | $0.09M | $2.23M | 24% | $0.35M / 12% |
| C. + CSM rebate as a source | $2.47M | 17% | $0.10M | $2.42M | 25% | $0.41M / 14% |
| D. share 75% | $2.90M | 18% | $0.18M | $2.83M | 25% | $0.55M / 17% |
| E. share steps 50 / 75 / 100% | $2.79M | 15% | $0.11M | $2.72M | 23% | $0.48M / 15% |
| F. debt decay 0.5% per day | $2.32M | 17% | $0.10M | $2.29M | 25% | $0.38M / 13% |
| A1. NEST base, reserve $43.8M | $1.62M | 5% | $0.01M | $1.59M | 10% | $0.14M / n/a |
| A2. expanded income, reserve $40M | $2.40M | 18% | $0.10M | $2.36M | 25% | $0.40M / n/a |
| G. expanded income, reserve $43.8M | $1.75M | 7% | $0.02M | $1.72M | 14% | $0.17M / 6% |
| H. G + true-up, final 50% | $2.02M | 7% | $0.02M | $1.85M | 14% | $0.16M / 6% |
| I. G + true-up, final 100% | $2.57M | 8% | $0.05M | $2.24M | 16% | $0.24M / 8% |
| J. I + protection: 18 months, stETH discount 30% | $2.57M | 8% | $0.04M | $2.22M | 15% | $0.22M / 7% |
| K. I + LDO price condition | $1.63M | 8% | $0.04M | $1.41M | 16% | $0.17M / 6% |
| L. Parametric part of the Aksusarya proposal | $6.90M | 53% | $3.92M | $6.75M | 56% | $4.12M / 79% |

The figures in this table differ slightly from the previous points, because here a different set of paths is used and the LDO price is modelled together with ETH; within the table all rules are compared on the same paths.

Table 2. Liquid treasury protection under rule I: buybacks, share of loss-making years when buying, share of paths where the protection triggered (price only / with shocks).

| Liquid treasury and buffer | 12 months of expenses | 18 months | 24 months |
| --- | --- | --- | --- |
| Stablecoins and fiat plus DAO stETH at a 30% discount | $2.57M, 8%, 0% / $2.24M, 16%, 0% | $2.57M, 8%, 2% / $2.22M, 15%, 4% | $2.49M, 6%, 16% / $2.14M, 14%, 20% |
| The same with a 50% stETH discount | $2.57M, 8%, 0% / $2.24M, 16%, 1% | $2.52M, 7%, 13% / $2.16M, 14%, 18% | $2.16M, 4%, 36% / $1.86M, 8%, 34% |
| Stablecoins and fiat only | $0.30M, 0%, 44% / $0.36M, 0%, 44% | $0.04M, 0%, 44% / $0.04M, 0%, 44% | $0.01M, 0%, 44% / $0.01M, 0%, 44% |

The 44% in the last row is the share of paths where the rule would get to a purchase at all; on all of them the protection blocks it.

Table 3. Market sensitivity: average buybacks over 12 months and the share of loss-making years among years with purchases, 450 paths per combination.

| ETH volatility and trend | A. Current NEST | E. Share steps | G. Expanded income, $43.8M | I. G + true-up, final 100% | L. $30M, 100% |
| --- | --- | --- | --- | --- | --- |
| 40%, −30% | $0.5M / 18% | $0.7M / 18% | $0.3M / 6% | $0.7M / 6% | $4.9M / 74% |
| 40%, no trend | $1.7M / 3% | $2.2M / 4% | $1.2M / 1% | $2.1M / 1% | $7.8M / 45% |
| 40%, +30% | $3.2M / 2% | $4.1M / 2% | $2.5M / 0% | $3.7M / 0% | $9.9M / 25% |
| 61%, −30% | $1.2M / 26% | $1.5M / 29% | $0.9M / 18% | $1.4M / 17% | $5.0M / 71% |
| 61%, no trend | $2.3M / 11% | $2.9M / 11% | $1.8M / 7% | $2.6M / 6% | $7.0M / 49% |
| 61%, +30% | $3.5M / 5% | $4.2M / 8% | $2.9M / 2% | $3.9M / 3% | $8.6M / 37% |
| 80%, −30% | $1.6M / 33% | $2.0M / 35% | $1.3M / 23% | $1.8M / 23% | $5.0M / 68% |
| 80%, no trend | $2.6M / 16% | $3.2M / 17% | $2.2M / 10% | $2.9M / 10% | $6.5M / 50% |
| 80%, +30% | $3.6M / 9% | $4.2M / 11% | $3.1M / 5% | $3.9M / 5% | $7.7M / 41% |

### Targeted combinations

A full search over all combinations would produce hundreds of variants that are hard to explain. So I additionally tested five combinations that answer open questions from the previous points, on the same 1,200 paths: an asymmetric final share with the full set of shocks; rule I with different starting budgets; treasury protection together with the LDO price condition; a simple variant without new budget logic (reserve $43.8M plus the CSM rebate); and a structural error in expenses of −30%, −10%, +10% and +30%.

Table 4. Targeted combinations: buybacks, share of loss-making years when buying, average peak overshoot, P(peak above $1M), average model price of LDO bought.

| Rule | Price only | With shocks |
| --- | --- | --- |
| I, profit 75%, loss 100% | $2.30M, 7%, $0.02M, 1%, $0.355 | $2.00M, 14%, $0.18M, 6% |
| I, profit 50%, loss 100% | $1.91M, 6%, $0.01M, 0%, $0.382 | $1.71M, 14%, $0.15M, 5% |
| I, start restored from 10.08: −$445,449 | $2.61M, 9%, $0.05M, 2% | $2.28M, 18%, $0.26M, 9% |
| I, start from zero | $2.81M, 26%, $0.15M, 3% | $2.48M, 33%, $0.38M, 12% |
| I + protection 24 months, stETH discount 50% | $2.16M, 4%, $0.01M, 0%, $0.385 | $1.86M, 8%, $0.11M, 4% |
| I + protection 18 months / 30% + LDO price | $1.62M, 7%, $0.04M, 1%, $0.269 | $1.38M, 15%, $0.15M, 5% |
| I + protection 24 months / 50% + LDO price | $1.22M, 3%, $0.01M, 0%, $0.304 | $1.05M, 7%, $0.06M, 2% |
| A1 + CSM rebate as a source | $1.83M, 7%, $0.02M, 1%, $0.406 | $1.80M, 14%, $0.19M, 6% |

Table 5. Structural expense error: actual expenses in every quarter deviate from plan in the same direction, price only, 900 paths; buybacks, share of loss-making years when buying, average peak overshoot.

| Actual expenses | G. No true-up | H. True-up, final 50% | I. True-up, final 100% |
| --- | --- | --- | --- |
| 30% below plan | $1.69M, 0%, $0 | $3.79M, 0%, $0 | $5.61M, 2%, $0.01M |
| 10% below | $1.69M, 3%, $0 | $2.47M, 3%, $0 | $3.36M, 5%, $0.04M |
| on plan | $1.69M, 8%, $0.02M | $1.96M, 7%, $0.02M | $2.51M, 8%, $0.05M |
| 10% above | $1.69M, 16%, $0.10M | $1.56M, 15%, $0.08M | $1.86M, 15%, $0.10M |
| 30% above | $1.69M, 54%, $0.70M | $1.01M, 41%, $0.29M | $1.07M, 42%, $0.28M |

Without a true-up the buyback volume does not respond to actual expenses at all, and risk rises steeply with overspending. With a true-up savings turn into buybacks, while overspending cuts buybacks, and the peak overshoot at +30% is 2.5 times lower. Even 10% overspending roughly doubles the share of loss-making years under any rule.

Table 6. Which variants remain on the efficient frontier: no other tested variant gives more buybacks with a lower share of loss-making years. Buybacks and the share of loss-making years, price only / with shocks; implementation complexity.

| Variant | Price only | With shocks | On the frontier | What is needed technically |
| --- | --- | --- | --- | --- |
| I + protection 24 months / 50% + LDO price | $1.22M, 3% | $1.05M, 7% | yes / yes | new budget logic |
| I + protection 24 months / 50% | $2.16M, 4% | $1.86M, 8% | yes / yes | new budget logic and a definition of the liquid treasury |
| I, profit 75%, loss 100% | $2.30M, 7% | $2.00M, 14% | yes / yes | new budget logic |
| I. True-up, final 100% | $2.57M, 8% | $2.24M, 16% | yes / yes | new budget logic |
| E. Share steps | $2.79M, 15% | $2.72M, 23% | yes / yes | new budget logic |
| D. Share 75% | $2.90M, 18% | $2.83M, 25% | yes / yes | parameter only |
| L. $30M, 100% | $6.90M, 53% | $6.75M, 56% | yes / yes | parameters only |
| A1. Reserve $43.8M | $1.62M, 5% | $1.59M, 10% | no / no | parameter only |
| A1 + CSM rebate | $1.83M, 7% | $1.80M, 14% | no / no | new revenue source |
| H, G, I with a 50% share for profit | $1.75–2.02M, 6–7% | $1.71–1.85M, 14% | no / no | new budget logic or sources |
| A. Current NEST | $2.21M, 14% | $2.17M, 20% | no / no | nothing |

The current NEST is not on the frontier: there are variants that give more buybacks at lower risk. Among the variants that can be implemented with parameters only, D and L are on the frontier, but both carry higher risk than today; A1 lowers risk, but volume as well.

### Conclusions for points 15–18

- **On identical paths rule I (expanded income, a $43.8M threshold, a true-up, a final share of 100%) improves the main modelled metrics compared with the current NEST:** more buybacks, a lower share of loss-making years at every volatility and ETH trend tested, and a peak overshoot that is no higher in the price-only test and lower in the test with shocks. But it does not dominate every alternative: G lowers risk more at the cost of lower volume, and E gives more buybacks at the cost of higher risk. The choice between them depends on which trade-off the DAO wants to lock in.
- **The step-by-step comparison shows that the components play different roles:** raising the reserve from $40M to $43.8M lowers risk the most, but cuts buybacks ($2.21M and 14% → $1.62M and 5%); expanded income partly restores volume with a small rise in risk ($1.75M and 7%); the true-up then adds volume without a noticeable rise in the share of loss-making years on these paths ($2.02M and 7%); a final share of 100% mainly increases volume ($2.57M and 8%).
- **Within the parameters of the current contract,** without new logic or new revenue sources, the current allocator allows the share and the reserve to be changed: of those tested, that means D (share 75%), L ($30M, 100%) and A1 (reserve $43.8M, share 50%). D and L noticeably raise risk, while A1, on the contrary, lowers both risk and volume. The other candidates require new revenue sources or new budget logic.
- **Treasury protection can be either almost useless or the main constraint,** depending on which assets are counted as available and at what discount. This decision has to be made explicitly.
- **The LDO price condition** works as a purchase price tool (20% cheaper in the model), not as protection against loss-making years.

* **The variant with a true-up and a final share of "profit 75%, loss 100%" stays on the efficient frontier:** in its combination of volume and risk ($2.30M and 7% price only) it sits between the more cautious variants and rule I ($2.57M and 8%).
* **Treasury protection at 24 months with a 50% stETH discount noticeably lowers the risk metrics while keeping most of the volume ($2.16M and 4% price only, $1.86M and 8% with shocks);** adding the LDO price condition lowers risk a little further (3% and 7%), but cuts buybacks to $1.22M price only and $1.05M with shocks. Whether that is acceptable is for the DAO to decide.
* **The structural expense error shows the main difference the true-up makes to how the mechanism works:** without it the buyback volume does not respond to the actual deviation in expenses at all, while with it savings increase the future budget and overspending reduces it. With 30% overspending the average peak overshoot is $0.70M without a true-up and about $0.28–0.29M with one.
* **The current NEST is not on the efficient frontier,** and of the variants that can be implemented with parameters only, just the 75% share and $30M/100% are on it, both with higher risk than today.

### Open questions

- Is the DAO ready for new budget logic, or should the RFC be limited to the parameters of the current contract and new revenue sources?
- Which DAO assets should count as liquid for treasury protection, and at what discount?
- Which market scenario does the DAO consider the base case when choosing parameters?

### What to check next

- **Point 19:** what happens to the LDO bought and how this affects holders.
## Point 19. What happens to the LDO bought

### Description

In the current executor mode all LDO bought goes straight to the DAO treasury (Aragon Agent). In liquidity mode half of the allocated stETH goes to LDO, the other half is wrapped into wstETH, the pair is deposited into a Curve pool, and the LP tokens stay with the executor and can later be withdrawn back to the treasury (point 0). In neither mode is LDO burned automatically.

To assess the effect of buybacks on the supply available to the market, I look at the amount of LDO outside DAO and Foundations holdings. The report for the first half of 2026 puts DAO and Foundations holdings at about 116.9M LDO, so out of the 1B supply about 883.1M sits outside their holdings. This is not the same as the market metric of "circulating supply", which is calculated using different methodologies. At the same time the DAO distributes LDO from its holdings to contributors: the report for the first half of 2026 shows 2.38M LDO under employee compensation programmes and another 0.10M to delegates. Annualising the payouts to employees gives about 4.76M LDO per year; this is a model run rate, not a guaranteed volume of future distributions. Distribution increases the amount of LDO outside holdings and buybacks reduce it, so what matters is whether purchases offset distribution. This is a measure of pressure on the supply available to the market, not a direct measure of benefit to holders: it does not measure price, voting weight or yield.

Separately from NEST there is a one-off DAO mandate to accumulate LDO for stETH, of up to 10,000 stETH, which the thread itself (11358, March 2026) separates from NEST and describes as an initiative to take advantage of a market opportunity. The Lido report for the first half of 2026 attributes the first two tranches to it, together 10.03M LDO for $2.99M at an average price of about $0.30; according to the reports in the thread, the same two tranches produced 12.69M LDO, apparently because the half-year report only counted the second tranche up to 30 June. This is an intermediate data point, not the programme's final result. According to the thread data as of 25 September, the five completed executions (the first tranche and its remainder, the second tranche, the third tranche and its second phase) spent 3,000 stETH out of 10,000 and bought about 19.42M LDO, roughly $6.2M at the average prices from the Growth Committee reports; a fourth tranche of 1,000 stETH is running with a window until 24 November. It is this cumulative volume that is used below to compare the scale of the mandate with NEST.

### Findings

- **In a typical modelled year NEST does not offset the distribution of LDO to contributors.** For all rules tested except the $30M/100% parameters, the median path has no or almost no purchases over 12 months (for the 75% share and the steps the median is 0.1–0.4M LDO), and the amount of LDO outside DAO and Foundations holdings grows by 0.50–0.54% at the assumed distribution rate.
- **The mean and the median diverge sharply:** buybacks are concentrated in scenarios that are favourable for ETH. The rule with a true-up and a final share of 100% averages 7.6M LDO per year, the stepped share 7.1M, the current NEST 5.5M; the change in LDO outside holdings averages from −0.32% to +0.09% per year. The probability of an annual reduction for realistic candidates is 20–33%.
- **Only $30M/100% gives a noticeable reduction:** on average 20M LDO per year, a median of −1.14%, a reduction on 76% of paths, but with the highest risk metrics for the DAO (points 15–18).
- **In scale the one-off mandate is comparable to NEST or larger.** By 25 September about 19.42M LDO had been bought under the mandate for roughly $6.2M. This is substantially more than the average volume that most realistic NEST variants allow to be bought over a full 12 months (about 4–8M LDO), and almost matches the average annual volume of the most aggressive variant, $30M/100% (about 20M LDO).
- **All these amounts are what the rule would allow to be bought.** Without an allocator top-up, only the current stETH balance of about 41 stETH can physically be executed (points 0 and 3).

* **My metric does not see unlocks and sales by other holders.** It only counts what the DAO takes off the market through buybacks and returns through distribution to contributors. Tokens that already sit outside DAO and Foundations holdings do not change in it, neither when they are unlocked nor when they are sold. Example: the vesting contract 0x58a7…ceea, which had received 10,000,000 LDO back in December 2020 and on 26 November 2025 distributed them to three multisigs (3.65M, 2.7M and 3.65M). 8.1M LDO had been withdrawn from them by early October 2026; at least 5.4M of that went, through chains of transfers, to be sold via CoW Swap, the fate of 2.7M is unknown, and 1.9M remains on the multisig 0x3053…40fC and continues to be withdrawn in parts. This is comparable to the mandate's purchases over the same period (19.42M LDO by 25 September), meaning a noticeable part of the DAO's purchases was matched by volume that holders of early allocations were selling. To assess price pressure, rather than just the DAO's position, a metric of free float that accounts for unlocks and sales is needed; I did not build one.

### Questions I asked

1. Where does the LDO bought end up in each executor mode?
2. Do buybacks reduce the amount of LDO outside DAO and Foundations holdings once distribution to contributors is taken into account?
3. How does this compare with the one-off LDO accumulation mandate?
4. What options are there for handling the LDO bought?

### How I collected the data

- I took the LDO holdings of the DAO and Foundations, the distribution to contributors and the results of the first tranches of the mandate from the Lido report for the first half of 2026 and the mandate thread.
- For 10 rules from points 15–18 I calculated, on the same 1,200 paths, the amount of LDO bought at the model's daily LDO price and the change in LDO outside holdings over 12 months: distribution of 4.76M minus purchases, divided by 883.1M.

### Results

Table 1. LDO bought over 12 months and the change in the amount of LDO outside DAO and Foundations holdings at a distribution rate of 4.76M LDO per year.

| Rule | Average LDO | Median | 90th percentile | LDO outside holdings, median | LDO outside holdings, average | P(reduction over the year) |
| --- | --- | --- | --- | --- | --- | --- |
| A. Current NEST | 5.5M | 0 | 17.0M | +0.54% | −0.08% | 28% |
| A1. Reserve $43.8M | 4.0M | 0 | 12.5M | +0.54% | +0.09% | 20% |
| D. Share 75% | 7.4M | 0.4M | 22.2M | +0.50% | −0.30% | 33% |
| E. Share steps | 7.1M | 0.1M | 21.9M | +0.53% | −0.26% | 32% |
| H. True-up, final 50% | 5.3M | 0 | 17.2M | +0.54% | −0.06% | 27% |
| I. True-up, final 100% | 7.6M | 0 | 24.2M | +0.54% | −0.32% | 33% |
| I, profit 75%, loss 100% | 6.5M | 0 | 20.9M | +0.54% | −0.19% | 30% |
| I + protection 24 months / 50% | 5.6M | 0 | 19.0M | +0.54% | −0.10% | 26% |
| I + protection 24 months / 50% + LDO price | 4.0M | 0 | 12.9M | +0.54% | +0.09% | 20% |
| L. $30M, 100% | 20.0M | 14.8M | 44.0M | −1.14% | −1.73% | 76% |

Table 2. Options for handling the LDO bought.

| Option | What happens to LDO outside holdings | What else matters |
| --- | --- | --- |
| Hold in the treasury (as now) | decreases, until the treasury distributes or sells it | it can later be used to pay contributors, and then the effect disappears |
| Burn or otherwise remove from the available supply by a separate DAO decision | decreases | reduces the current token supply; the specific procedure and the possibility of future issuance of new LDO need to be checked separately |
| Lock for a period | decreases for the lock period | keeps flexibility for the future |
| Liquidity mode | does not decrease by the full amount bought | the LDO becomes DAO liquidity in the pool and stays available to the market; the DAO owns a position in the pool rather than a fixed amount of LDO; only half of the amount goes to LDO |
| Distribute to holders who have staked LDO | does not decrease | this is direct income to holders, essentially a separate revenue distribution model (discussed in thread 10195) |

### Conclusions for point 19

- **Under most of the rules tested, NEST does not deliver a sustained reduction in LDO outside DAO and Foundations holdings at a contributor distribution rate of about 4.76M LDO per year.** Some rules show a reduction on average, but on the median path the amount of LDO outside holdings grows, and the probability of an annual reduction is 20–33%. Only $30M/100% gives a stable reduction, at the cost of high risk for the DAO.
- **For holders it is not only the size of buybacks that matters, but also what happens to the LDO bought:** as long as it can be distributed again, the effect is temporary, and in liquidity mode it stays available to the market through the pool.
- **In scale the one-off LDO accumulation mandate is comparable to NEST or larger:** by 25 September about 19.42M LDO had been bought under it, substantially more than the average 12-month volume of most realistic NEST variants and almost as much as the most aggressive variant, $30M/100%, gives on average, so the two should be considered together.

* **NEST on its own does not guarantee a sustained reduction in LDO outside DAO and Foundations holdings:** the effect depends simultaneously on the buyback volume, subsequent distribution of LDO from the treasury and how the tokens bought are used.

### Open questions

- What does the DAO plan to do with the LDO bought by NEST: hold it, burn it, lock it or use it to pay contributors?
- How will NEST fit together with the continuation of the LDO accumulation mandate?
- Is there a plan to enable liquidity mode?

### What to check next

- **Summary:** bring the conclusions of all points and the draft ideas together into an overall conclusion for the RFC.
## Summary

### In short

1. **Changing the parameters of the current NEST on their own is not worth it.** A lower threshold or a higher share produces more buybacks, but in my tests it also increases the share of purchases made in years the DAO ends at a loss.
2. **Without weakening the mechanism's protection, buybacks can only be increased sustainably by growing the DAO's income or cutting expenses.** So the call to cut expenses is justified, but in the current NEST savings have no effect on buybacks at all, because the threshold is hardcoded as a fixed $40M. Savings turn into buybacks only if the threshold is tied to the approved budget.
3. **NEST does not see all of the DAO's income,** only the staking fee. It misses the treasury's income from its own assets, Earn revenue and CSM module rebates, together about $4.5M a year.
4. **The main changes can be made without a new contract,** through votes: cut the budget, set the threshold equal to the budget, and introduce NEST top-ups. The remaining income can be connected to the current NEST as new revenue sources. A new contract is needed only for a true-up against actual expenses, and that can wait.

### Why NEST is not buying right now

The buyback budget receives 50% of the amount by which the staking fee exceeds $40M a year, and the shortfall of every weak day accumulates as a deficit. The threshold is only covered with ETH above roughly $2,668, the price has been at or below that the whole time, and the deficit is already −$542,451. The launch glitch added $147,658 to it, but that is a secondary factor. And even once the budget turns positive, there is almost nothing to execute with: the contract holds about 41 stETH (roughly $110k, two days of purchases), and there is no top-up rule.

### What I propose, step by step

**Step 1. Now, through votes only, with no contract changes.**

1. **Cut the Foundations expense budget and, in the same vote, set the NEST threshold equal to the new budget.** I suggest a target of about $30M a year, roughly 30% below the current $43.8M; with that budget the model gives about $4.3M of buybacks a year instead of $2.15M, and DAO profit before buybacks of about $13M instead of $1M. A noticeable effect on buybacks starts at a cut of about 20%; at 10% buybacks barely change. From then on, every time a budget is approved, the threshold is updated in the same vote and only going forward; the threshold is never lowered separately from the budget. If Foundations need more money, for example for legal work, they justify it in the budget request and the threshold rises with it. That way a cut to the approved budget automatically lowers the NEST threshold, and savings can turn into additional buybacks without a separate weakening of the threshold. If actual expenses exceed the approved budget, the current contract will not notice, so any overspend should go through a separate vote that raises the threshold.
2. **Keep the share of the excess that goes to buybacks at 50%.** Sending the entire excess over the budget to buybacks seems natural, since it is profit, but the current contract compares revenue only with the approved budget and cannot see when actual expenses turn out higher or revenue falls during the year. With a 100% share there is no buffer left for such deviations, and the share of purchases made in years the DAO ends at a loss grows two to three times. With a budget of about $30M this means about $5.63M of buybacks a year instead of $4.28M, but a share of purchases in loss-making years of 11% instead of 5%, and at current expenses 17% instead of 5%. Sending almost all profit to buybacks makes sense after moving to a true-up against the actual quarterly result (step 3). There is no need to speed up the purchases themselves: NEST already buys every day as soon as its budget is positive.
3. **Submit the budget request broken down by main line items, together with a calculation of how much NEST would buy back at that level of spending.** When the threshold equals the budget, both treasury protection and buyback volume depend on the quality of the budget, so delegates need to see where the money goes. Quarterly expense reports should also be published faster and with the same breakdown.
4. **Introduce a NEST top-up rule:** a separate Easy Track program with a starting limit of about 2,000 stETH for six months; once a month, bring the allocator balance up to the smaller of two amounts, the positive NEST budget or 30 daily limits (about $1.5M).
5. **Adopt a policy for purchased LDO:** burn or lock it and do not use it to pay contributors, otherwise distributions (about 4.76M LDO a year) eat up the buybacks. Do not enable liquidity mode until the DAO decides whether it needs liquidity instead of supply reduction.
6. **Align NEST with the LDO accumulation mandate** (up to 10,000 stETH) and look at the DAO's total LDO position across all channels. By 25 September, about 19.42M LDO had been bought under the mandate for roughly $6.2M. That is substantially more than most NEST variants allow buying on average over 12 months (about 4–8M LDO), and almost as much as the most aggressive variant, $30M/100%, gives on average, and that variant makes more than half of its purchases in years that are loss-making for the DAO. In other words, the DAO technically can buy a lot of LDO and is already doing so outside NEST, through a one-off decision. But that does not prove such a volume can safely become a permanent automatic rule: the constraint on NEST is how many purchases can be sustainably paid for out of the DAO's real profit. So there is no need to scale NEST parameters up to the size of the mandate.

Leave the allocation limits ($50k a day, $10M a year) unchanged at this step.

**Step 2. In parallel, in development: teach the current NEST to see all income.** The allocator can connect additional revenue sources by vote, without being replaced. It needs sources for CSM rebates (about $1.2M a year), Earn revenue (about $0.5M) and the treasury's income from its assets (about $2.8M), provided these flows are measurable on-chain; that needs to be checked separately. An important detail: NEST counts the staking fee before some deductions, above all payouts to partners for deposits (referral payouts). If Earn and treasury income are added to that base, the threshold has to be raised by the amount of those deductions; otherwise the mechanism will compare an overstated income with expenses, and in my model the share of purchases in loss-making years roughly triples. The model estimates this adjustment at about $3M a year, but the deductions vary from year to year (in 2025 referral payouts were $4.1M), so their exact composition and size need to be determined before implementation.

**Step 3. Later, if the DAO decides so: a new allocator with a true-up.** Each day the mechanism accrues 50% of the excess of income over the budget, and after the quarterly report it replaces that with the actual result for the quarter: 75% of a profit goes to buybacks, and a loss goes into the deficit in full. This protects against actual expenses diverging from the budget, which the current contract cannot see. Starting budget: recalculated under the new rule from 10 August, −$445,449 (revenue for 11–14 August is already included in it). Expenses for the true-up should be taken from the reports or, to avoid depending on reporting quality, from total treasury outflows without a breakdown; the second option needs to be modelled separately. A new contract also requires a procedure for submitting and challenging data, and metrics for a review after 6 and 12 months.

### What this gives

Average buybacks per year and, in brackets, the share of purchases made in years the DAO ends at a loss; 1,000 ETH price scenarios over the next 12 months.

| Expenses | Now ($40M threshold) | Step 1: threshold = budget | Steps 1 + 2: all income, threshold = budget + deductions | Step 3: new contract with true-up | DAO profit for the year before buybacks (income minus expenses) |
| --- | --- | --- | --- | --- | --- |
| as now ($43.8M) | $2.15M (15%) | $1.58M (5%) | $1.83M (9%) | $2.27M (9%) | about +$1M |
| −10% | $2.15M (5%) | $2.25M (6%) | $2.57M (9%) | $3.34M (11%) | about +$5M |
| −20% | $2.15M (1%) | $3.14M (8%) | $3.52M (10%) | $4.71M (12%) | about +$9M |
| −30% (about $30M) | $2.15M (0%) | $4.28M (5%) | $4.71M (6%) | $6.31M (9%) | about +$13M |

**What cutting expenses shows.** In the current NEST a cut does not increase buybacks by itself: the threshold is fixed at $40M and does not depend on the DAO budget, so with any cut the average buybacks in the model stay around $2.15M a year. Only their safety changes: the share of purchases in loss-making years falls from 15% at current expenses to 5% with a 10% cut, 1% with 20% and practically zero with 30%.

For savings to turn into buybacks, the threshold has to be linked to the approved budget (step 1). Buybacks then grow not because NEST splits the surplus differently, but because the DAO has more real profit left after expenses: it rises from $1M a year at current expenses to $5M, $9M and $13M with cuts of 10%, 20% and 30%. Counting the income NEST currently does not see, and adding a true-up, add more on top: with a 20% cut this is $3.14M with a simple threshold link, $3.52M with additional sources and $4.71M with a true-up.

The model does not identify a single correct size of cut. With a 10% cut DAO profit grows noticeably, but buybacks are barely different from today ($2.25M versus $2.15M), because the threshold is still about $39M. Around 20% is the first of the tested points where a noticeable profit buffer appears (about $9M a year) and buybacks become substantially larger without weakening the threshold. A 30% cut strengthens the effect further, but that is already a very large budget reduction. What level is justified has to be decided separately, based on how useful the DAO's specific expenses are.

Lowering the threshold separately from expenses, on the other hand, is not a good idea: the mechanism then buys more LDO, but no profit appears to pay for it, and the share of purchases made in years the DAO ends at a loss grows. For example, a $30M threshold with a 100% share at current expenses means about $6.9M of buybacks a year with DAO profit of about $1.3M, and more than half of the purchases would fall in loss-making years.

At the current ETH price no variant will make NEST buy much right now: buybacks will come in the years when the DAO actually earns more than it spends.

### What I do not recommend

- **Lowering the threshold separately from expenses,** including to $30M with a 100% share at current expenses.
- **Writing off or "forgetting" the deficit.** It adds a few buybacks, but of all the changes I tested it raises the share of purchases in loss-making years the most.
- **Comparing revenue with the latest published expense report.** Reports come out late, and the mechanism would buy at the wrong time.
- **Expecting buybacks by themselves to reduce LDO supply.** On average NEST buys about as much LDO as the DAO distributes to contributors, and in the median scenario it buys nothing over the year.

### Main findings

1. **The current NEST can be improved on buyback volume and risk at the same time, but not by changing the numbers in the current contract.** A lower threshold or a higher share always means a trade-off: more buybacks and more risk, or the reverse.
2. **The threshold is the main risk lever, the share is the main volume lever, and the deficit protects the treasury.** Lowering the threshold increases purchases in loss-making years the most; raising the share increases volume with a smaller rise in risk; a deficit write-off gives the worst ratio of all the changes tested.
3. **Which revenue to count is a separate decision.** The current base has the advantage of being measurable on-chain, but it leaves out part of the income and does not deduct payouts to partners.
4. **Tying buybacks to expenses makes sense,** but the expenses must be up to date: a true-up corrects the calculation after the report, but does not undo purchases already made.
5. **Foundations expenses are not all of the DAO's expenses:** one-off spending, for example $6.06M on the aftermath of the Kelp incident, is accounted for separately.
6. **The starting budget for the new rule is a separate decision:** carrying over the current deficit or recalculating from 10 August gives 7–9% of purchases in loss-making years, starting from zero gives 23%.
7. **The daily and annual limits are needed to protect against data errors,** not to calculate the budget.
8. **A buyback does not create profit and does not give holders a direct claim on it.** LDO has no claim on revenue; buybacks amount to about 0.6% of LDO outside holdings per year (about 1.7% with expenses 30% lower), and the model cannot say how this will affect the price.
9. **NEST distributes what is left over; it does not decide how much to spend.** The model does not assess whether expenses pay off; the DAO has to justify the size of the budget separately, and once the threshold is tied to it, the quality of the budget becomes part of the mechanism's protection.

### Questions for the Lido team

1. Why does NEST not count CSM rebates and other treasury income, and are revenue sources planned for them?
2. Are CSM rebates included in the reported net revenue, and how much were the referral payouts?
3. How is NEST planned to be topped up, and why does it share an Easy Track limit with expense payments?
4. What is planned for the purchased LDO, and will liquidity mode be enabled?
5. At launch, was it taken into account that the mechanism would accumulate a deficit for four days with no revenue?
6. Can quarterly expenses be published faster and broken down by main line items?

### Limitations

All figures come from a model looking 12 months ahead under the revenue, expense and market assumptions from points 2–3; these are scenarios, not a forecast. The model does not account for the effect of purchases on the LDO price. The metric for LDO outside DAO and Foundations holdings accounts only for buybacks and distributions to contributors, not for unlocks and sales by other holders; for example, of the 10M LDO of early vesting unlocked in November 2025, 8.1M had been withdrawn by October 2026, of which at least 5.4M went to sale via CoW Swap (point 19). Partner payouts in step 2 are estimated at roughly $3M a year. How CSM rebates are accounted for in Lido's reports is not confirmed; this shifts the risk metrics by 3–5 points, but does not change the comparison between variants. Detailed calculations for each step, checks and tables are in points 0–19.
