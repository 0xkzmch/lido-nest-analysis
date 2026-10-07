"""Stage 4 v2 (after review 3): master comparison. Fixes: approved budget $43.8M (+$41M alternative), correct LDO drift,
joint and conditional loss probabilities, path-wise LDO bought and net outside-treasury supply change, 10,000 paths, calibration disclosed."""
import json, math, random, statistics, csv
from datetime import date
from gengine import sim, history_days, forward_days

# ---- calibration: daily log returns over the trailing 365 days ending 28.09.2026 ----
rows = list(csv.DictReader(open("base/treasury_fee_inflows.csv")))
LDO_ALL = json.load(open("data/ldo_px.json"))
e = [float(r["eth_usd"]) for r in rows][-366:]; l = LDO_ALL[-366:]
re_ = [math.log(e[i] / e[i - 1]) for i in range(1, len(e))]; rl_ = [math.log(l[i] / l[i - 1]) for i in range(1, len(l))]
me, ml = statistics.mean(re_), statistics.mean(rl_)
BETA = sum((a - me) * (b - ml) for a, b in zip(re_, rl_)) / sum((a - me) ** 2 for a in re_)
SIG_E = statistics.pstdev(re_); SIG_I = statistics.pstdev([b - BETA * a for a, b in zip(re_, rl_)])
CALIB = dict(window="365 days to 28.09.2026, daily log returns (ETH: Chainlink at the inflow block; LDO: DefiLlama)",
             eth_vol_annual=SIG_E * math.sqrt(365), beta=BETA, ldo_idio_vol_annual=SIG_I * math.sqrt(365))

OUTSIDE = 1e9 - 116.86e6
D_CONTRIB = 4.76e6; D_ALL = 4.96e6
TU = dict(family="threshold", trueup=True, prov_basis="budget", prov_share=0.5, full_share=1.0, deficit="accumulates")
RULES = [
 ("Benchmark", "Current NEST", dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates"), True),
 ("Benchmark", "Aksusarya proposal: $30M, 100%", dict(family="threshold", type="fixed", fixed=30e6, share=1.0, basis="as NEST", deficit="accumulates"), False),
 ("Minimal fix", "NEST + quarterly debt reset", dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="quarterly reset"), True),
 ("Expense threshold", "Known expenses, net, 100%, quarterly reset, no true-up", dict(family="threshold", type="known", share=1.0, basis="net", deficit="quarterly reset"), False),
 ("Cash flow with true-up (prelim. 50%, final 100%)", "True-up: approved budget $43.8M", dict(TU), False),
 ("Cash flow with true-up (prelim. 50%, final 100%)", "True-up: $41M base from H1 report (alternative)", dict(TU, prov_basis="budget 41"), False),
 ("Cash flow with true-up (prelim. 50%, final 100%)", "True-up $43.8M, prelim. 100%, 90-day floor", dict(TU, prov_share=1.0, deficit="floor", ndays=90), False),
 ("Cash flow with true-up (prelim. 50%, final 100%)", "True-up $43.8M + buy only if LDO ≤ MA90", dict(TU, price_k=1.0), False),
 ("Cash flow with true-up (prelim. 50%, final 100%)", "True-up $43.8M with expenses −20% (actual)", dict(TU, mult=0.8), False),
 ("Revenue share without threshold", "10% of net staking revenue", dict(family="revshare", pct=0.10), False),
 ("Revenue share without threshold", "20% of net staking revenue", dict(family="revshare", pct=0.20), False),
]
def run_rule(rule, days, is_nest, forward):
    if forward and is_nest: return sim(rule, days, start_budget=-548925, cap_anchor=date(2026, 8, 10), forward=True)
    return sim(rule, days, forward=forward)

H = history_days(); res = []
for grp, name, rule, is_nest in RULES:
    res.append(dict(group=grp, name=name, rule=rule, is_nest=is_nest, hist=sim(rule, H),
                    flat={p: run_rule(rule, forward_days([float(p)] * 365, [0.4197] * 365), is_nest, True) for p in (2000, 2680, 3000, 3500)}))

N = 10000; random.seed(2026)
se, si = SIG_E, SIG_I
drift_e = -0.5 * se ** 2; drift_l = -0.5 * (BETA ** 2 * se ** 2 + si ** 2)
acc = {r["name"]: dict(t=[], pk=[], ldo=[], loss_buy=0, buy=0) for r in res}
for n in range(N):
    ep = [2679.84]; lp = [0.4197]
    for _ in range(364):
        ze = random.gauss(0, 1); zi = random.gauss(0, 1)
        re = drift_e + se * ze
        rl = drift_l + BETA * se * ze + si * zi
        ep.append(ep[-1] * math.exp(re)); lp.append(lp[-1] * math.exp(rl))
    days = forward_days(ep, lp)
    for r in res:
        o = run_rule(r["rule"], days, r["is_nest"], True); a = acc[r["name"]]
        a["t"].append(o["total"]); a["pk"].append(o["peak"]); a["ldo"].append(o["ldo"])
        if o["total"] > 0:
            a["buy"] += 1
            if o["profit"] < 0: a["loss_buy"] += 1
def q(v, p): return statistics.quantiles(v, n=100)[p - 1]
for r in res:
    a = acc[r["name"]]
    net = [(D_CONTRIB - x) / OUTSIDE for x in a["ldo"]]
    r["mc"] = dict(mean=statistics.mean(a["t"]), p10=q(a["t"], 10), p50=statistics.median(a["t"]), p90=q(a["t"], 90),
                   p_any=a["buy"] / N, p_joint=a["loss_buy"] / N, p_cond=(a["loss_buy"] / a["buy"]) if a["buy"] else None,
                   peak_mean=statistics.mean(a["pk"]), ldo_p10=q(a["ldo"], 10), ldo_p50=statistics.median(a["ldo"]), ldo_p90=q(a["ldo"], 90),
                   net_p10=q(net, 10), net_p50=statistics.median(net), net_p90=q(net, 90),
                   p_net_reduction=sum(1 for x in a["ldo"] if x > D_CONTRIB) / N,
                   p_net_reduction_all=sum(1 for x in a["ldo"] if x > D_ALL) / N)
def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if hasattr(o, "isoformat"): return o.isoformat()
    return o
json.dump(dict(calibration=CALIB, n_paths=N, seed=2026, outside=OUTSIDE, d_contrib=D_CONTRIB, d_all=D_ALL,
               rules=[dict(group=r["group"], name=r["name"], rule=r["rule"], hist=clean(r["hist"]), flat={str(k): clean(v) for k, v in r["flat"].items()}, mc=r["mc"]) for r in res]),
          open("stage4_results.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in CALIB.items()})
    for r in res:
        m = r["mc"]
        print(f"{r['name'][:48]:48s} avg {m['mean']/1e6:5.2f} med {m['p50']/1e6:4.2f} P(buyback) {m['p_any']:.1%} P(buyback∩loss) {m['p_joint']:.1%} P(loss|buyback) {(m['p_cond'] or 0):.1%} "
              f"LDO P10/50/90 {m['ldo_p10']/1e6:4.1f}/{m['ldo_p50']/1e6:4.1f}/{m['ldo_p90']/1e6:5.1f}M outside treasury med {m['net_p50']:+.2%} P(reduction) {m['p_net_reduction']:.0%}")
