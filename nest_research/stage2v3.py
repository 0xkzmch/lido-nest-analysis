import json, csv
from engine import run, BASE_A, BASE_B, BASE_C, PERIODS, KNOWN, KOPT, OPT, forward_run
from datetime import date as _date
rows_in = list(csv.DictReader(open("base/treasury_fee_inflows.csv")))
STETH_DAY = sum(float(r["steth"]) for r in rows_in[-30:]) / 30
COR = PERIODS[4]["corrate"]; CAP = 10e6
BUDGET_NOW = -548925.0

def base_annual(p):
    if p["type"] == "fixed": return int(p["fixed"] / 365) * 365
    if p["type"] == "expenses (actual)": return PERIODS[4][OPT[p["exp"]]] * 365 * p["mult"]   # H2-2026 forecast rate
    return KNOWN[-1][KOPT[p["exp"]]] * 365 * p["mult"]                                      # latest published rate

def annual_rev(p, price):
    rev = STETH_DAY * 365 * price
    return rev * (1 - COR) if p["basis"] == "net" else rev

def capacity(p, price):
    s = annual_rev(p, price) - base_annual(p)
    if s <= 0: return 0.0
    if p["scale"] == "progressive":
        R, S = p["b1"], p["b2"]
        amt = p["share"] * min(s, R) + p["s2"] * min(max(s - R, 0), max(S - R, 0)) + p["s3"] * max(s - S, 0)
    else:
        amt = p["share"] * s
    return min(p['acap'] if p['acap'] > 0 else 1e18, amt)

def forecast12(p, price, start_budget):
    """flat daily path from today's state: debt first (only for 'accumulates'/'floor'), then buys, capped."""
    cap_yr = capacity(p, price)
    if cap_yr <= 0: return 0.0, None
    daily = cap_yr / 365
    if p["deficit"] in ("accumulates", "floor N days") and start_budget < 0:
        d0 = -start_budget / daily
        if d0 >= 365: return 0.0, None
        return min(CAP, daily * (365 - d0)), d0
    return cap_yr, 0.0

def breakeven(p):
    per_price = STETH_DAY * 365 * ((1 - COR) if p["basis"] == "net" else 1)
    return base_annual(p) / per_price

A, B, C = dict(BASE_A), dict(BASE_B), dict(BASE_C)
combos = []
def add(group, base, name, **ch):
    p = dict(base, **ch); p["name"] = name; combos.append((group, p))

add("Benchmarks", A, "Current NEST")
add("Benchmarks", A, "Aksusarya proposal: 30M / 100%", fixed=30e6, share=1.0, s2=1.0, s3=1.0, sneg=1.0)
for nm, ch in (("NEST + quarterly debt reset", dict(deficit="reset by period", reset="quarter")),
               ("NEST + 90-day window", dict(deficit="rolling window", ndays=90)),
               ("NEST + deficit does not accumulate", dict(deficit="does not accumulate"))):
    add("Minimal NEST fix", A, nm, **ch)
POLS = (("quarterly reset", dict(deficit="reset by period", reset="quarter")), ("90-day window", dict(deficit="rolling window", ndays=90)))
for exp in ("all", "staking+shared"):
    add("From profit: actual in hindsight (benchmark)", B, f"Threshold = {exp} (actual), share 100%, quarterly reset", exp=exp, **POLS[0][1])
for exp in ("all", "staking+shared"):
    for share in (1.0, 0.75):
        for pol, extra in POLS:
            add("From profit: feasible (expenses known as of date)", C, f"Threshold = {exp} (known), share {int(share*100)}%, {pol}",
                exp=exp, share=share, s2=share, s3=share, sneg=share, **extra)
for exp in ("all", "staking+shared"):
    for m in (0.9, 0.8, 0.7):
        add("Expense cut (known as of date)", C, f"Threshold = {exp} (known) ×{m}, share 100%, quarterly reset", exp=exp, mult=m, **POLS[0][1])
    add("Expense cut (known as of date)", C, f"Threshold = {exp} (known) ×0.8, cut did NOT happen", exp=exp, mult=0.8, cuts_real="no", **POLS[0][1])
for exp in ("all", "staking+shared"):
    add("Dynamic scale", C, f"Threshold = {exp} (known), tier scale 50/75/100%, quarterly reset", exp=exp, scale="progressive",
        share=0.5, s2=0.75, s3=1.0, b1=5e6, b2=15e6, sneg=0.5, **POLS[0][1])

out = []
for group, p in combos:
    r = run(p)
    is_live = p["type"] == "fixed" and p["fixed"] == 40e6 and p["share"] == 0.5 and p["scale"] == "no"
    sb = BUDGET_NOW if is_live else 0.0
    anchor = _date(2026, 8, 10) if is_live else None
    fr = {pr: forward_run(p, pr, start_budget=sb, cap_window_start=anchor) for pr in (2000, 2680, 3000, 3500)}
    fc = {pr: (fr[pr]["total"], fr[pr]["first_day"]) for pr in fr}
    out.append(dict(group=group, params={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in p.items()},
                    res={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()},
                    base_annual_fwd=base_annual(p), breakeven=breakeven(p),
                    cap2000=capacity(p, 2000), cap2680=capacity(p, 2680), cap3500=capacity(p, 3500),
                    fc_start_budget=sb, fc2000=fc[2000][0], fc2680=fc[2680][0], fc3000=fc[3000][0], fc3500=fc[3500][0],
                    fc_days_to_first_2680=fc[2680][1], fc_days_to_first_3500=fc[3500][1],
                    fc_uncov_3000=fr[3000]["uncovered"], fc_profit_3000=fr[3000]["profit"]))
json.dump(out, open("stage2_results.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    print(f"stETH/day {STETH_DAY:.2f}, CoR {COR:.4f}, latest known all-expense rate ${KNOWN[-1]['all']*365/1e6:.1f}M/yr, H2 forecast rate ${PERIODS[4]['d_all']*365/1e6:.1f}M/yr")
    for o in out:
        r = o["res"]
        print(f"{o['params']['name'][:62]:62s} buybacks {r['total']/1e6:5.2f} not covered {r['uncovered']/1e6:5.2f} profit {r['profit']/1e6:+6.2f} | forward threshold ${o['base_annual_fwd']/1e6:5.1f}M break-even ${o['breakeven']:,.0f} | capacity@2680 {o['cap2680']/1e6:5.2f} forecast12m@2680 {o['fc2680']/1e6:5.2f} @3500 {o['fc3500']/1e6:5.2f}")
    print(len(out))
