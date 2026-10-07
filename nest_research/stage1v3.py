import json
from datetime import date
from engine import run, BASE_A, BASE_B, BASE_C

def variations(tag):
    out = [("base", {}), ("period from 01.01.2024", dict(start=date(2024, 1, 1)))]
    if tag == "A":
        out += [(f"threshold ${x/1e6:.0f}M", dict(fixed=x)) for x in (30e6, 35e6, 45e6)]
        out += [("net revenue", dict(basis="net"))]
        out += [(f"share {int(x*100)}%", dict(share=x)) for x in (0.25, 0.75, 1.0)]
    else:
        out += [("expenses: staking+general", dict(exp="staking+shared")), ("expenses: staking only", dict(exp="staking"))]
        out += [(f"expenses ×{x}", dict(mult=x)) for x in (0.9, 0.8, 0.7)]
        out += [("expenses ×0.8, but the cut did not happen", dict(mult=0.8, cuts_real="no"))]
        out += [("revenue as NEST", dict(basis="as NEST"))]
        out += [(f"share {int(x*100)}%", dict(share=x)) for x in (0.25, 0.5, 0.75)]
    out += [("no daily cap", dict(dcap=0)), ("yearly cap $15M", dict(acap=15e6)), ("no yearly cap", dict(acap=0))]
    out += [("debt: 30-day floor", dict(deficit="floor N days", ndays=30)), ("debt: 90-day floor", dict(deficit="floor N days", ndays=90)),
            ("debt: does not accumulate", dict(deficit="does not accumulate")),
            ("debt: decay 0.5%/day", dict(deficit="decay", decay=0.005)),
            ("debt: decay 1%/day", dict(deficit="decay", decay=0.01)),
            ("debt: decay 2%/day", dict(deficit="decay", decay=0.02)),
            ("debt: quarterly reset", dict(deficit="reset by period", reset="quarter")),
            ("debt: yearly reset", dict(deficit="reset by period", reset="year")),
            ("debt: 90-day window", dict(deficit="rolling window", ndays=90)),
            ("debt: 180-day window", dict(deficit="rolling window", ndays=180)),
            ("debt: 365-day window", dict(deficit="rolling window", ndays=365))]
    j = 0.5 if tag == "A" else 1.0
    out += [("tier scale 25/50/75%, bounds $5M/$15M", dict(scale="progressive", share=0.25, s2=0.5, s3=0.75, b1=5e6, b2=15e6, sneg=j)),
            ("tier scale 25/50/75%, bounds $2.5M/$10M", dict(scale="progressive", share=0.25, s2=0.5, s3=0.75, b1=2.5e6, b2=10e6, sneg=j)),
            ("tier scale 50/75/100%, bounds $5M/$15M", dict(scale="progressive", share=0.5, s2=0.75, s3=1.0, b1=5e6, b2=15e6, sneg=j)),
            ("tier scale 25/50/75%, deficit at 1st-tier share", dict(scale="progressive", share=0.25, s2=0.5, s3=0.75, b1=5e6, b2=15e6, sneg=0.25))]
    out += [("profit measure: staking balance", dict(measure="staking balance")), ("profit measure: total incl. one-offs", dict(measure="summary incl. one-offs"))]
    return out

NAMES = {"A": "Base A: current NEST", "B": "Base B: threshold = all expenses (actual, retrospective), net, 100%, accumulates",
         "C": "Base C: threshold = all expenses (known as of date), net, 100%, accumulates"}
BASES = {"A": BASE_A, "B": BASE_B, "C": BASE_C}
rows = []
for tag in ("A", "B", "C"):
    base_res = None
    for label, ch in variations(tag):
        p = dict(BASES[tag], **ch); p["name"] = f"{tag}: {label}"
        r = run(p)
        if label == "base": base_res = r
        rows.append(dict(tag=tag, base=NAMES[tag], label=label,
                         params={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in p.items()},
                         res={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()},
                         delta=r["total"] - base_res["total"]))
json.dump(rows, open("stage1_results.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    for x in rows:
        r = x["res"]
        print(f"{x['tag']} {x['label'][:40]:40s} buybacks {r['total']/1e6:6.2f}M Δ{x['delta']/1e6:+6.2f} days {r['days']:4d} profit {r['profit']/1e6:+6.2f} "
              f"in loss periods {r['over_period']/1e6:5.2f} not covered {r['uncovered']/1e6:5.2f} end {r['end']/1e6:+6.2f}")
    print(len(rows), "variants")
