"""Stage 5 (step B after review 3): stress test with operating shocks + true-up sensitivity grid.
Shocks per path: quarterly expense multiplier lognormal (sigma 15%, mean 1); one-off loss with prob 25% per year, size $3M/$6M/$10M,
random day; report delay per quarter uniform 45..120 days. One-offs reduce DAO profit and enter the true-up (conservative).
Price paths: same calibration as stage 4 (trailing 365 days to 28.09.2026)."""
import json, math, random, statistics, sys
from datetime import date, timedelta
from gengine import sim, forward_days, REPORTS_FWD
S4 = json.load(open("stage4_results.json")); C = S4["calibration"]
SE = C["eth_vol_annual"] / math.sqrt(365); BETA = C["beta"]; SI = C["ldo_idio_vol_annual"] / math.sqrt(365)
DRIFT_E = -0.5 * SE ** 2; DRIFT_L = -0.5 * (BETA ** 2 * SE ** 2 + SI ** 2)
START = date(2026, 9, 29); OUTSIDE = 1e9 - 116.86e6; D_CONTRIB = 4.76e6

def price_path(rng):
    e = [2679.84]; l = [0.4197]
    for _ in range(364):
        ze = rng.gauss(0, 1); zi = rng.gauss(0, 1)
        e.append(e[-1] * math.exp(DRIFT_E + SE * ze)); l.append(l[-1] * math.exp(DRIFT_L + BETA * SE * ze + SI * zi))
    return e, l

def shocks(rng):
    sq = 0.15
    em = {k: math.exp(-0.5 * sq ** 2 + sq * rng.gauss(0, 1)) for k in range(len(REPORTS_FWD))}
    one = {}
    if rng.random() < 0.25: one[START + timedelta(days=rng.randrange(365))] = rng.choice([3e6, 6e6, 10e6])
    delays = {k: rng.randint(45, 120) for k in range(len(REPORTS_FWD))}
    return em, one, delays

TU = dict(family="threshold", trueup=True, prov_basis="budget", prov_share=0.5, full_share=1.0, deficit="accumulates", with_oneoffs=True)
def W(r): return dict(r, with_oneoffs=True)
RULES = [
 ("Benchmark", "Current NEST", W(dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates")), True),
 ("Benchmark", "Aksusarya proposal: $30M, 100%", W(dict(family="threshold", type="fixed", fixed=30e6, share=1.0, basis="as NEST", deficit="accumulates")), False),
 ("Minimal fix", "NEST + quarterly debt reset", W(dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="quarterly reset")), True),
 ("Expense threshold", "Known expenses, net, 100%, quarterly reset, no true-up", W(dict(family="threshold", type="known", share=1.0, basis="net", deficit="quarterly reset")), False),
 ("True-up $43.8M: final share", "Final share 100%", dict(TU), False),
 ("True-up $43.8M: final share", "Final share 75%", dict(TU, full_share=0.75), False),
 ("True-up $43.8M: final share", "Final share 50%", dict(TU, full_share=0.5), False),
 ("True-up: different preliminary run rate", "Base $41M, summary 100%", dict(TU, prov_basis="budget 41"), False),
 ("True-up $43.8M with safeguards", "+ liquid treasury protection 18 mo", dict(TU, guard_liquid_months=18, haircut=0.3), False),
 ("True-up $43.8M with safeguards", "+ buy only if LDO ≤ MA90", dict(TU, price_k=1.0), False),
 ("Revenue share without threshold", "10% of net revenue", W(dict(family="revshare", pct=0.10)), False),
]
def run_rule(rule, days, is_nest):
    if is_nest: return sim(rule, days, start_budget=-548925, cap_anchor=date(2026, 8, 10), forward=True)
    return sim(rule, days, forward=True)

def q(v, p): return statistics.quantiles(v, n=100)[p - 1]
def summarize(acc, N):
    a = acc; net = [(D_CONTRIB - x) / OUTSIDE for x in a["ldo"]]
    return dict(mean=statistics.mean(a["t"]), p10=q(a["t"], 10), p50=statistics.median(a["t"]), p90=q(a["t"], 90),
                p_any=a["buy"] / N, p_joint=a["lb"] / N, p_cond=(a["lb"] / a["buy"]) if a["buy"] else None,
                peak_mean=statistics.mean(a["pk"]), p_peak_1m=sum(p > 1e6 for p in a["pk"]) / N,
                end_mean=statistics.mean(a["end"]), guard_share=a["gb"] / N,
                ldo_p50=statistics.median(a["ldo"]), net_p50=statistics.median(net), p_reduce=sum(x > D_CONTRIB for x in a["ldo"]) / N)

if __name__ == "__main__" and sys.argv[1] == "stress":
    N = 10000; rng = random.Random(55)
    acc = {r[1]: dict(t=[], pk=[], ldo=[], end=[], buy=0, lb=0, gb=0) for r in RULES}
    for n in range(N):
        e, l = price_path(rng); em, one, dl = shocks(rng)
        days = forward_days(e, l, exp_mult_q=em, oneoffs=one, report_delays=dl)
        for grp, name, rule, is_nest in RULES:
            o = run_rule(rule, days, is_nest); a = acc[name]
            a["t"].append(o["total"]); a["pk"].append(o["peak"]); a["ldo"].append(o["ldo"]); a["end"].append(o["end"])
            if o["guard_blocked"]: a["gb"] += 1
            if o["total"] > 0:
                a["buy"] += 1
                if o["profit"] < 0: a["lb"] += 1
    out = dict(n_paths=N, seed=55, shocks=dict(expense_sigma_q=0.15, oneoff_prob=0.25, oneoff_sizes=[3e6, 6e6, 10e6], report_delay_days=[45, 120]),
               rules=[dict(group=g, name=n, rule=r, mc=summarize(acc[n], N)) for g, n, r, _ in RULES])
    json.dump(out, open("stage5_stress.json", "w"), ensure_ascii=False, indent=1)
    for r in out["rules"]:
        m = r["mc"]
        print(f"{r['name'][:46]:46s} avg {m['mean']/1e6:5.2f} med {m['p50']/1e6:4.2f} P(buyback) {m['p_any']:.1%} P(∩loss) {m['p_joint']:.1%} P(loss|buyback) {(m['p_cond'] or 0):.1%} "
              f"peak {m['peak_mean']/1e6:4.2f} P(peak>1M) {m['p_peak_1m']:.1%} debt avg {m['end_mean']/1e6:+5.2f} protection {m['guard_share']:.0%} LDOout {m['net_p50']:+.2%} P(red.) {m['p_reduce']:.0%}")

if __name__ == "__main__" and sys.argv[1] == "grid":
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 2000; rng = random.Random(77)
    only_delays = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else None
    import os
    done = json.load(open("stage5_grid_parts.json")) if os.path.exists("stage5_grid_parts.json") else []
    paths = [price_path(rng) for _ in range(N)]
    provs = [37.7e6, 41e6, 43.8e6, 46.4e6]; delays = [30, 60, 90, 120]; actuals = [0.8, 1.0, 1.2]; finals = [0.5, 0.75, 1.0]
    res = []
    for dl in delays:
        if only_delays and dl not in only_delays: continue
        for am in actuals:
            if any(x["delay"] == dl and abs(x["actual"] - am) < 1e-9 for x in done): continue
            dayset = [forward_days(e, l, exp_mult_q={k: am for k in range(len(REPORTS_FWD))}, report_delays={k: dl for k in range(len(REPORTS_FWD))}) for e, l in paths]
            for pv in provs:
                for fs in finals:
                    rule = dict(TU, prov_rate_annual=pv, full_share=fs)
                    acc = dict(t=[], pk=[], ldo=[], end=[], buy=0, lb=0, gb=0)
                    for days in dayset:
                        o = sim(rule, days, forward=True)
                        acc["t"].append(o["total"]); acc["pk"].append(o["peak"]); acc["ldo"].append(o["ldo"]); acc["end"].append(o["end"])
                        if o["total"] > 0:
                            acc["buy"] += 1
                            if o["profit"] < 0: acc["lb"] += 1
                    m = summarize(acc, N)
                    done.append(dict(prov=pv, delay=dl, actual=am, final=fs, mean=m["mean"], p_any=m["p_any"], p_cond=m["p_cond"],
                                     peak_mean=m["peak_mean"], p_peak_1m=m["p_peak_1m"], end_mean=m["end_mean"]))
            json.dump(done, open("stage5_grid_parts.json", "w"), ensure_ascii=False)
            print("done delay", dl, "actual", am, "total cells", len(done), flush=True)
    if len(done) == 144:
        json.dump(dict(n_paths=N, seed=77, grid=done), open("stage5_grid.json", "w"), ensure_ascii=False, indent=1)
        print("grid complete", flush=True)
