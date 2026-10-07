import json
from datetime import date
from stage1 import run, BASE_A, BASE_B, S0, S1
import csv

# forward drivers (same as Forward sheet): recent treasury stETH/day, CoR H1 rate, FY expenses and scope ratios
rows_in = list(csv.DictReader(open("base/treasury_fee_inflows.csv")))
STETH_DAY = sum(float(r["steth"]) for r in rows_in[-30:]) / 30
ETH_NOW = float(rows_in[-1]["eth_usd"])
from openpyxl import load_workbook
_e = load_workbook("../nest_model.xlsx", data_only=True)["Expenses"]
COR = _e["B16"].value; FY = _e["B13"].value
SCOPE = {"all": 1.0, "staking+shared": _e["B14"].value + _e["B15"].value, "staking": _e["B14"].value}
CAP = 10e6

def forward(p, price):
    rev = STETH_DAY * 365 * price
    if p["basis"] == "net": rev *= (1 - COR)
    base = p["fixed"] if p["type"] == "fixed" else FY * SCOPE[p["exp"]] * p["mult"]
    s = rev - base
    if s <= 0: return 0.0, rev, base
    if p["scale"] == "progressive":
        R, S = p["b1"], p["b2"]
        amt = p["share"] * min(s, R) + p["s2"] * min(max(s - R, 0), max(S - R, 0)) + p["s3"] * max(s - S, 0)
    else:
        amt = p["share"] * s
    return min(CAP, amt), rev, base

def breakeven(p):
    per_price = STETH_DAY * 365 * ((1 - COR) if p["basis"] == "net" else 1)
    base = p["fixed"] if p["type"] == "fixed" else FY * SCOPE[p["exp"]] * p["mult"]
    return base / per_price

A = dict(BASE_A); B = dict(BASE_B, deficit="accumulates")
combos = []
def add(group, name, **ch):
    base = A if ch.pop("_base", "B") == "A" else B
    p = dict(base, **ch); p["name"] = name
    combos.append((group, p))

# 1. reference points
add("Benchmarks", "Current NEST", _base="A")
add("Benchmarks", "Aksusarya proposal: 30M / 100%", _base="A", fixed=30e6, share=1.0, s2=1.0, s3=1.0, sneg=1.0)
# 2. minimal fixes of current NEST
add("Minimal NEST fix", "NEST + quarterly debt reset", _base="A", deficit="reset by period", reset="quarter")
add("Minimal NEST fix", "NEST + 90-day window", _base="A", deficit="rolling window", ndays=90)
add("Minimal NEST fix", "NEST + deficit does not accumulate", _base="A", deficit="does not accumulate")
# 3. profit-based structures (mult 1.0)
for exp in ("all", "staking+shared"):
    for share in (1.0, 0.75):
        for pol, extra in (("quarterly reset", dict(deficit="reset by period", reset="quarter")),
                           ("90-day window", dict(deficit="rolling window", ndays=90))):
            add("Buybacks from profit", f"Threshold = {exp}, share {int(share*100)}%, {pol}", exp=exp, share=share,
                s2=share, s3=share, sneg=share, **extra)
# 4. cost-cut scenarios on share 100%
for exp in ("all", "staking+shared"):
    for pol, extra in (("quarterly reset", dict(deficit="reset by period", reset="quarter")),
                       ("90-day window", dict(deficit="rolling window", ndays=90))):
        for m in (0.9, 0.8, 0.7):
            add("Expense cut", f"Threshold = {exp} ×{m}, share 100%, {pol}", exp=exp, mult=m, **extra)
# 5. dynamic scale on best structures
for exp in ("all", "staking+shared"):
    add("Dynamic scale", f"Threshold = {exp}, tier scale 50/75/100%, quarterly reset", exp=exp, scale="progressive",
        share=0.5, s2=0.75, s3=1.0, b1=5e6, b2=15e6, sneg=0.5, deficit="reset by period", reset="quarter")

out = []
for group, p in combos:
    r = run(p)
    fw = {pr: forward(p, pr)[0] for pr in (2000, 2680, 3500)}
    out.append(dict(group=group, params={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in p.items()},
                    res={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()},
                    from_profit=r["total"] - r["over"], over_share=(r["over"] / r["total"]) if r["total"] > 0 else None,
                    breakeven=breakeven(p), fw2000=fw[2000], fw2680=fw[2680], fw3500=fw[3500]))
json.dump(out, open("stage2_results.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    print(f"stETH/day {STETH_DAY:.2f}, ETH now {ETH_NOW:.0f}, CoR {COR:.4f}, FY {FY:,.0f}")
    for o in out:
        r = o["res"]; p = o["params"]
        print(f"{o['group'][:18]:18s} {p['name'][:60]:60s} buybacks {r['total']/1e6:6.2f}M from profit {o['from_profit']/1e6:5.2f}M "
              f"overspend {r['over']/1e6:5.2f}M LDO {r['ldo_m']:5.2f}M days {r['days']:4d} | break-even ETH ${o['breakeven']:,.0f} "
              f"| 12m @2000 {o['fw2000']/1e6:5.2f} @2680 {o['fw2680']/1e6:5.2f} @3500 {o['fw3500']/1e6:5.2f}")
    print(len(out), "combos")
