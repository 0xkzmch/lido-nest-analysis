# NEST review (Lido DAO): package contents

Version of 6 October 2026.

The report is in the root folder: NEST_report.md and NEST_report.pdf (points 0–19 and the summary).

## What is in the archive

**nest_model.xlsx**: the v2 model spreadsheet (1 October 2026). Live engine formulas, check sheets,
historical and forecast results, sheets with the document's summary figures. For what was fixed in v2, see the Changes sheet.

**Engine and helper modules**
- engine.py: the original engine (history since 2024, expenses by period, expense run rates known as of each date, true-up)
- gengine.py: a shared engine for all rules (threshold, share, debt policies, true-up, limits, treasury protection); self-check `python3 gengine.py`
- scen3.py: three starting-point variants (as now, with launch compensation, with CSM rebate as a source)
- p11.py, p15.py: shared functions for points 11–14 and 15–18 (ETH and LDO price paths, shocks)

**Source data (folders base, data, contracts)**
- base/: daily base of treasury inflows since 1 January 2024, NEST checkpoints, rebase logs, NEST revenue conversions, reconciliation with on-chain data
- contracts/: source code of the NEST contracts (allocator, executor, oracle, revenue source) and the allocator state
- rebase_logs.json, agent_mints.json, dist_transfers.json, inflows_state.json, price_inflows.py: collection of inflows and prices

**Results by report point**
| Points | Files |
| --- | --- |
| 0–2. Audit, data, reconciliation | base/validation_results.json, breakeven_decomp.json, revenue_composite.csv |
| 1. Launch effect | point1_recovery.json |
| 3. Engine and history | stage1*.py/json, stage2*.py/json, results_*.csv |
| 4. Reserve | point4_*.json |
| 5. Surplus share | point5_results.json, point5_dynamic.json |
| 6. Revenue base | point6_results.json, point6_hypA.json |
| 7. Debt policy | point7_results.json, point7_compare.json |
| 8. Caps | point8_results.json |
| 9–10. Expense-based threshold | point9_results.json |
| 11–14. True-up against reports | p11_*.json |
| 15–18. Combined stress test | p15_*.json, stage4/5*.py/json |
| 19. Fate of purchased LDO | p19.json |
| Summary: steps, levers, $30M threshold, proposal checks | p_*.json |
| Recalculation of the Summary, LDO and Stage5 sheets in the spreadsheet | recompute_sheets.py, v2_*.json |

**Spreadsheet build**: build_xlsx*.py (history of build versions); stage1v3.py and stage2v3.py recalculate the Stage1 and Stage2 sheets.


## How to reproduce
Python 3 with the standard library and openpyxl. Engine self-check: `python3 gengine.py`
(current NEST history $1,073,359; forecast at ETH $3,000 $1,936,016). Scripts are run from the nest_research folder. Daily LDO prices used for LDO counts are in nest_research/data/ldo_px.json (DefiLlama, aligned to the rows of base/treasury_fee_inflows.csv).
Network access is needed only to collect source data from the blockchain (RPC eth.drpc.org) and the Lido forum.

## Known limitations
A model looking 12 months ahead under the revenue, expense and market assumptions from points 2–3; these are scenarios, not a forecast.
How CSM rebates are accounted for in Lido's reports is not confirmed. The model does not account for the effect of purchases on the LDO price.
