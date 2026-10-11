"""Follow-up to the NEST forum discussion (October 2026).

1) Budget table: NEST threshold set equal to the approved Foundations budget, share 50%,
   12 months from 1 October 2026, for a range of budgets.
2) Yearly reset of the NEST counter vs the current accumulating deficit, 3 years.

Assumptions as in the report (point 3), with two changes after the DAO Ops reply in the thread:
- CSM rebates are not added to DAO profit separately (they are already in reported revenue);
- DAO profit is shown with treasury income (as in the report) and without it (TI=0).

Run from the nest_research folder:  python3 followup_budget_reset.py
Writes followup_budget_reset_results.json
"""
import math, random, json
from datetime import date
from gengine import sim, forward_days
from scen3 import START_BUDGET, START

B0 = START_BUDGET[1]            # actual NEST budget carried over: -$542,451
ANCHOR = date(2026, 8, 10)      # NEST activation, anchor of the 365-day cap window
NEST = dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates")
N_PATHS = 1000
SEED = 20261011

def path(rng, n):
    """Daily ETH and LDO prices: ETH vol 61%/yr, no drift; LDO 0.75 beta to ETH plus 50% idiosyncratic vol."""
    se = 0.61 / math.sqrt(365); si = 0.5 / math.sqrt(365)
    e = [2679.84]; l = [0.4197]
    for _ in range(n - 1):
        z = rng.gauss(0, 1); zi = rng.gauss(0, 1)
        e.append(e[-1] * math.exp(-0.5 * se * se + se * z))
        l.append(l[-1] * math.exp(0.75 * se * z - 0.5 * (0.5625 * se * se + si * si) + si * zi))
    return e, l

def days_for(e, l, ti):
    d = forward_days(e, l, start=START)
    for x in d: x["x_ti"] *= ti
    return d

def budget_table(ti):
    rng = random.Random(SEED)
    sets = [days_for(*path(rng, 365), ti) for _ in range(N_PATHS)]
    out = {}
    for B in [28e6, 30e6, 32e6, 34e6, 35e6, 36e6, 38e6, 40e6, 42e6, 43.8e6, "current NEST"]:
        r = NEST if B == "current NEST" else dict(NEST, fixed=B, mult=B / 43.8e6)
        tot, prof, ldo, cond = [], [], [], []
        for d in sets:
            res = sim(r, d, start_budget=B0, cap_anchor=ANCHOR, forward=True)
            tot.append(res["total"]); prof.append(res["profit"]); ldo.append(res["ldo"])
            if res["total"] > 0: cond.append(res["profit"] < 0)
        st_ = sorted(tot)
        out[str(B)] = dict(avg_buybacks=sum(tot) / N_PATHS, median_buybacks=(st_[N_PATHS // 2 - 1] + st_[N_PATHS // 2]) / 2, p_any_purchase=sum(t > 0 for t in tot) / N_PATHS,
                           p_loss_year_given_purchase=sum(cond) / max(1, len(cond)),
                           avg_dao_profit_before_buybacks=sum(prof) / N_PATHS, avg_ldo_bought=sum(ldo) / N_PATHS)
    return out

def per_year(d, res, ny):
    out = []
    for y in range(ny):
        seg = d[y * 365:(y + 1) * 365]
        prof = sum(x["rev"] * (1 - x["cor"]) + x["x_earn"] + x["x_ti"] - x["exp"] for x in seg)
        months = {x["d"].year * 12 + x["d"].month for x in seg}
        buy = sum(v for k, v in res["by_month"].items() if k in months)
        out.append((buy, prof))
    return out

def reset_compare(ti, ny=3):
    rng = random.Random(SEED)
    rules = {"accumulates (current)": NEST, "yearly reset": dict(NEST, deficit="yearly reset"),
             "quarterly reset": dict(NEST, deficit="quarterly reset")}
    acc = {k: [] for k in rules}
    for _ in range(N_PATHS):
        d = days_for(*path(rng, 365 * ny), ti)
        for k, r in rules.items():
            acc[k].append(per_year(d, sim(r, d, start_budget=B0, cap_anchor=ANCHOR, forward=True), ny))
    out = {}
    for k, v in acc.items():
        yrs = [y for p in v for y in p]; wb = [y for y in yrs if y[0] > 0]
        out[k] = dict(avg_buybacks_per_year=sum(y[0] for y in yrs) / len(yrs),
                      share_of_years_with_purchases=len(wb) / len(yrs),
                      p_loss_year_given_purchase=sum(y[1] < 0 for y in wb) / max(1, len(wb)),
                      share_of_buyback_usd_in_loss_years=sum(y[0] for y in wb if y[1] < 0) / max(1, sum(y[0] for y in wb)))
    return out

if __name__ == "__main__":
    res = {"budget_table": {"with_treasury_income": budget_table(1.0), "without_treasury_income": budget_table(0.0)},
           "reset_3y": {"with_treasury_income": reset_compare(1.0), "without_treasury_income": reset_compare(0.0)}}
    json.dump(res, open("followup_budget_reset_results.json", "w"), indent=1)
    for k, v in res["budget_table"]["with_treasury_income"].items():
        w = res["budget_table"]["without_treasury_income"][k]
        print(f"{k:>14}  buybacks ${v['avg_buybacks']/1e6:.2f}M  median ${v['median_buybacks']/1e6:.2f}M  any {v['p_any_purchase']:.0%}  profit ${v['avg_dao_profit_before_buybacks']/1e6:.1f}M / ${w['avg_dao_profit_before_buybacks']/1e6:.1f}M  loss-yr {v['p_loss_year_given_purchase']:.0%} / {w['p_loss_year_given_purchase']:.0%}")
    for k, v in res["reset_3y"]["with_treasury_income"].items():
        w = res["reset_3y"]["without_treasury_income"][k]
        print(f"{k:>22}  ${v['avg_buybacks_per_year']/1e6:.2f}M/yr  years with buys {v['share_of_years_with_purchases']:.0%}  loss-yr {v['p_loss_year_given_purchase']:.0%} / {w['p_loss_year_given_purchase']:.0%}")
