"""Stage 3: cash-flow rule with report-based quarterly true-up vs current NEST and the no-true-up rule."""
import json
from datetime import date
from engine import run, run_trueup, forward_run, forward_trueup, BASE_A, BASE_C

TU = dict(start=date(2025, 1, 1), end=date(2026, 9, 28), prov_basis="known", prov_share=0.5, full_share=1.0, mult=1.0,
          cuts_real="yes", floor_days=None, dcap=50000, acap=10e6, minspend=1000, measure="cash flow", startbudget=0.0)
rules = [
 ("Benchmarks", "Current NEST", "nest", {}),
 ("Benchmarks", "Threshold = known expenses, quarterly debt reset, no true-up", "nosync", {}),
 ("True-up, preliminary run rate = latest report", "Prelim. 50%, debt accumulates", "tu", dict(prov_basis="known", prov_share=0.5)),
 ("True-up, preliminary run rate = latest report", "Prelim. 50%, 90-day debt floor", "tu", dict(prov_basis="known", prov_share=0.5, floor_days=90)),
 ("True-up, preliminary run rate = latest report", "Prelim. 100%, 90-day debt floor", "tu", dict(prov_basis="known", prov_share=1.0, floor_days=90)),
 ("True-up, preliminary run rate = approved budget $43.8M", "Prelim. 50%, debt accumulates", "tu", dict(prov_basis="budget", prov_share=0.5)),
 ("True-up, preliminary run rate = approved budget $43.8M", "Prelim. 50%, 90-day debt floor", "tu", dict(prov_basis="budget", prov_share=0.5, floor_days=90)),
 ("True-up, preliminary run rate = approved budget $43.8M", "Prelim. 100%, 90-day debt floor", "tu", dict(prov_basis="budget", prov_share=1.0, floor_days=90)),
 ("True-up, preliminary run rate = $41M base from the H1 report", "Prelim. 50%, debt accumulates", "tu", dict(prov_basis="budget 41", prov_share=0.5)),
 ("True-up with a 20% expense cut", "Latest report, prelim. 50%, floor 90, cut is real", "tu", dict(prov_basis="known", prov_share=0.5, floor_days=90, mult=0.8)),
 ("True-up with a 20% expense cut", "Budget, prelim. 50%, floor 90, cut is real", "tu", dict(prov_basis="budget", prov_share=0.5, floor_days=90, mult=0.8)),
 ("True-up with a 20% expense cut", "Budget, prelim. 50%, floor 90, cut did NOT happen", "tu", dict(prov_basis="budget", prov_share=0.5, floor_days=90, mult=0.8, cuts_real="no")),
]
out = []
for group, name, kind, ch in rules:
    if kind == "nest":
        h = run(dict(BASE_A)); h = dict(h, peak_ahead=h["uncovered"])
        f = {pr: forward_run(dict(BASE_A), pr, start_budget=-548925, cap_window_start=date(2026, 8, 10)) for pr in (2680, 3000, 3500)}
        for v in f.values(): v["peak_ahead"] = v["uncovered"]
    elif kind == "nosync":
        p = dict(BASE_C, deficit="reset by period"); h = run(p); h = dict(h, peak_ahead=h["uncovered"])
        f = {pr: forward_run(p, pr) for pr in (2680, 3000, 3500)}
        for v in f.values(): v["peak_ahead"] = v["uncovered"]
    else:
        p = dict(TU, **ch); h = run_trueup(p)
        f = {pr: forward_trueup(p, pr) for pr in (2680, 3000, 3500)}
    out.append(dict(group=group, name=name, hist=dict(total=h["total"], days=h["days"], peak=h["peak_ahead"], over=h["over_period"],
                    profit=h["profit"], end=h["end"]),
                    fwd={str(pr): dict(total=f[pr]["total"], peak=f[pr]["peak_ahead"], profit=f[pr]["profit"], first=f[pr]["first_day"]) for pr in f}))
json.dump(out, open("stage3_results.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    for o in out:
        h = o["hist"]; line = f"{o['name'][:58]:58s} src. {h['total']/1e6:5.2f}M oper.{h['peak']/1e6:5.2f}"
        for pr in ("2680", "3000", "3500"):
            f = o["fwd"][pr]; line += f" | {pr}: {f['total']/1e6:5.2f}M oper.{f['peak']/1e6:4.2f} prof.{f['profit']/1e6:+5.1f}"
        print(line)
