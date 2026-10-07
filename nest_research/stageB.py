"""Stage B: (1) final share 50/75/100%; (2) Monte Carlo with financial shocks: quarterly expense noise (lognormal, 15%),
one-off losses (20%/yr chance; $3M/$6M/$10M), random report delays (30/60/90/120 days); (3) liquid-treasury guard (stables + stETH with 30% haircut);
(4) sensitivity matrix for the true-up rule. Price paths calibrated as in stage4 (trailing 365 days to 28.09.2026)."""
import json, math, random, statistics
from datetime import date, timedelta
from gengine import sim_b, forward_days_b
from stage4 import BETA, SIG_E, SIG_I

def price_path(rng):
    ep = [2679.84]; lp = [0.4197]
    de = -0.5 * SIG_E ** 2; dl = -0.5 * (BETA ** 2 * SIG_E ** 2 + SIG_I ** 2)
    for _ in range(364):
        ze = rng.gauss(0, 1); zi = rng.gauss(0, 1)
        ep.append(ep[-1] * math.exp(de + SIG_E * ze)); lp.append(lp[-1] * math.exp(dl + BETA * SIG_E * ze + SIG_I * zi))
    return ep, lp

def shocks(rng):
    exp_q = [math.exp(rng.gauss(-0.5 * 0.15 ** 2, 0.15)) for _ in range(5)]
    delays = [rng.choice([30, 60, 90, 120]) for _ in range(5)]
    oneoffs = {}
    if rng.random() < 0.20:
        oneoffs[date(2026, 9, 29) + timedelta(days=rng.randrange(365))] = rng.choice([3e6, 6e6, 10e6])
    return exp_q, delays, oneoffs

TU = dict(family="threshold", trueup=True, prov_basis="budget", prov_share=0.5, full_share=1.0, deficit="accumulates")
NEST = dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates")
RULES = [
 ("Current NEST", NEST, True),
 ("NEST + quarterly debt reset", dict(NEST, deficit="quarterly reset"), True),
 ("Aksusarya proposal: $30M, 100%", dict(NEST, fixed=30e6, share=1.0), False),
 ("Known expenses, net, 100%, quarterly reset, no true-up", dict(family="threshold", type="known", share=1.0, basis="net", deficit="quarterly reset"), False),
 ("True-up $43.8M, final share 100%", dict(TU), False),
 ("True-up $43.8M, final share 75%", dict(TU, full_share=0.75), False),
 ("True-up $43.8M, final share 50%", dict(TU, full_share=0.5), False),
 ("True-up $41M, final share 100%", dict(TU, prov_basis="budget 41"), False),
 ("True-up $43.8M, 100% + liquid treasury protection 18 mo", dict(TU, liq_guard_months=18), False),
 ("True-up $43.8M, 100% + liquid treasury protection 24 mo", dict(TU, liq_guard_months=24), False),
 ("True-up $43.8M, 100% + LDO ≤ MA90", dict(TU, price_k=1.0), False),
 ("10% of net revenue without threshold", dict(family="revshare", pct=0.10), False),
]
def run(rule, days, is_nest):
    return sim_b(rule, days, start_budget=-548925, cap_anchor=date(2026, 8, 10)) if is_nest else sim_b(rule, days)

N = 10000; rng = random.Random(7)
acc = {n: dict(t=[], pk=[], keep=[], buy=0, lossbuy=0, gh=0, liq=[]) for n, _, _ in RULES}
oneoff_paths = 0
for _ in range(N):
    ep, lp = price_path(rng); exp_q, delays, oneoffs = shocks(rng); oneoff_paths += bool(oneoffs)
    days = forward_days_b(ep, lp, exp_q=exp_q, delays=delays, oneoffs=oneoffs)
    for n, rule, is_nest in RULES:
        o = run(rule, days, is_nest); a = acc[n]
        a["t"].append(o["total"]); a["pk"].append(o["peak"]); a["keep"].append(o["profit"] - o["total"]); a["liq"].append(o["min_liq_months"])
        if o["total"] > 0:
            a["buy"] += 1; a["lossbuy"] += o["profit"] < 0
        a["gh"] += o["guard_hits"] > 0
def q(v, p): return statistics.quantiles(v, n=100)[p - 1]
mc = []
for n, _, _ in RULES:
    a = acc[n]
    mc.append(dict(name=n, mean=statistics.mean(a["t"]), p50=statistics.median(a["t"]), p90=q(a["t"], 90), p_any=a["buy"] / N,
                   p_joint=a["lossbuy"] / N, p_cond=(a["lossbuy"] / a["buy"]) if a["buy"] else None, peak_mean=statistics.mean(a["pk"]),
                   p_peak_1m=sum(p > 1e6 for p in a["pk"]) / N, keep_mean=statistics.mean(a["keep"]), p_guard=a["gh"] / N,
                   liq_p10=q(a["liq"], 10)))

# ---- sensitivity matrix for the true-up rule (1,000 price paths, no expense noise, fixed delay, scaled actual expenses) ----
rng2 = random.Random(11); paths = [price_path(rng2) for _ in range(1000)]
sens = []
for delay in (30, 60, 90, 120):
    for scale in (0.8, 1.0, 1.2):
        dayset = [forward_days_b(ep, lp, exp_scale=scale, delays=[delay] * 5) for ep, lp in paths]
        for prov in (37.7e6, 41e6, 43.8e6, 46.4e6):
            for fs in (0.5, 0.75, 1.0):
                rule = dict(TU, prov_annual=prov, full_share=fs, prov_share=min(0.5, fs))
                t, pk, endb, buy, lb = [], [], [], 0, 0
                for days in dayset:
                    o = sim_b(rule, days); t.append(o["total"]); pk.append(o["peak"]); endb.append(o["end"])
                    if o["total"] > 0:
                        buy += 1; lb += o["profit"] < 0
                sens.append(dict(delay=delay, exp_scale=scale, prov=prov, final=fs, mean=statistics.mean(t), peak=statistics.mean(pk),
                                 p_any=buy / 1000, p_cond=(lb / buy) if buy else None, end_mean=statistics.mean(endb)))
json.dump(dict(n=N, oneoff_share=oneoff_paths / N, shocks=dict(expense_q_vol=0.15, oneoff_prob=0.20, oneoff_sizes=[3e6, 6e6, 10e6], delays=[30, 60, 90, 120]),
               liquid=dict(level1_jun="stables + yield-bearing stables + fiat, DAO + Foundations, 30.06.2026", haircut_steth=0.30),
               mc=mc, sens=sens), open("stageB_results.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    for m in mc:
        print(f"{m['name'][:52]:52s} avg {m['mean']/1e6:5.2f} med {m['p50']/1e6:4.2f} P(buyback) {m['p_any']:.0%} P(loss|buyback) {(m['p_cond'] or 0):.0%} peak {m['peak_mean']/1e6:4.2f} P(peak>1M) {m['p_peak_1m']:.0%} stays in treasury {m['keep_mean']/1e6:+5.2f} protection {m['p_guard']:.0%} liq.P10 {m['liq_p10']:.0f}mo")
