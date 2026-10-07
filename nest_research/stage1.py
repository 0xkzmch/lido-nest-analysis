import csv, json
from datetime import date
from openpyxl import load_workbook

WB = "../nest_model.xlsx"
_e = load_workbook(WB, data_only=True)["Expenses"]
PER = [(_e[f"B{r}"].value.date(), [_e[f"K{r}"].value, _e[f"L{r}"].value, _e[f"M{r}"].value],
        _e[f"J{r}"].value, _e[f"P{r}"].value) for r in range(5, 10)]
REV = [(date.fromisoformat(r["date"]), float(r["revenue_usd"])) for r in csv.DictReader(open("data/revenue_composite.csv"))]
LDO = json.load(open("data/ldo_px.json"))
POL = {"accumulates": 1, "floor N days": 2, "does not accumulate": 3, "decay": 4, "reset by period": 5, "rolling window": 6}
OPT = {"all": 1, "staking+shared": 2, "staking": 3}

def pidx(d):
    k = 0
    for i, p in enumerate(PER):
        if d >= p[0]: k = i
    return k

def run(p):
    start, end = p["start"], p["end"]
    fixed = p["type"] == "fixed"; net = p["basis"] == "net"; scale = p["scale"] == "progressive"
    J, T, U, Vn = p["share"], p["s2"], p["s3"], p["sneg"]; R, S = p["b1"], p["b2"]
    defm = POL[p["deficit"]]; nd = p["ndays"]; dc = p["decay"]; quarter = p["reset"] == "quarter"
    dcap, acap, mins = p["dcap"], p["acap"], p["minspend"]
    b = 0.0; spent = {}; alloc = {}; days = 0; over = 0.0; sw = 0; prevbuy = 0.0; ldo_b = 0.0; econ = 0.0
    cd = []; cb = []; prevkey = None; minb = 0.0; first = None; prev_act = False
    for idx, (d, r) in enumerate(REV):
        _, ex, cor, psur = PER[pidx(d)]
        act = start <= d <= end
        ru = r * (1 - cor) if net else r
        base = p["fixed"] / 365 if fixed else ex[OPT[p["exp"]] - 1] * p["mult"]
        su = ru - base
        if act:
            if scale:
                delta = (J * min(su, R / 365) + T * min(max(su - R / 365, 0), max(S - R, 0) / 365) + U * max(su - S / 365, 0)) if su >= 0 else Vn * su
            else:
                delta = J * su
        else:
            delta = 0.0
        key = (d.year * 10 + (d.month - 1) // 3 + 1) if quarter else d.year
        cd.append((cd[-1] if cd else 0) + delta)
        buy = 0.0
        if act:
            prev = b if prev_act else p["startbudget"]
            if defm == 5 and prevkey is not None and key != prevkey and idx > 0: prev = max(0, prev)
            pre = prev + delta
            ns = Vn if scale else J
            if defm == 1: post = pre
            elif defm == 2: post = max(pre, -nd * base * ns)
            elif defm == 3: post = max(0, pre)
            elif defm == 4: post = pre * (1 - dc) if pre < 0 else pre
            elif defm == 5: post = pre
            else:
                i = len(cd) - 1
                cdn = cd[i - nd] if i - nd >= 0 else 0
                cbp = cb[i - 1] if i >= 1 else 0
                cbn = cb[i - nd] if i - nd >= 0 else 0
                post = (cd[i] - cdn) - (cbp - cbn)
            w = (d - start).days // 365
            if post > mins:
                buy = max(0, min(post, dcap if dcap > 0 else 1e18, (acap - spent.get(w, 0)) if acap > 0 else 1e18))
            if buy > 0:
                spent[w] = spent.get(w, 0) + buy; alloc[d.year] = alloc.get(d.year, 0) + buy; days += 1
                first = first or d
            b = post - buy; minb = min(minb, b)
            if psur < 0: over += buy
            ldo_b += buy / LDO[idx]
            econ += r * (1 - cor) - ex[0]
            if buy > 0 and prevbuy == 0: sw += 1
        cb.append((cb[-1] if cb else 0) + buy)
        prevbuy = buy; prevkey = key; prev_act = act
    tot = sum(alloc.values())
    return {"b2024": alloc.get(2024, 0), "b2025": alloc.get(2025, 0), "b2026": alloc.get(2026, 0), "total": tot,
            "days": days, "first": first, "end": b, "min": minb, "ldo_m": ldo_b / 1e6, "econ": econ,
            "coverage": (tot / econ) if econ > 0 else None, "over": over, "switches": sw}

S0, S1 = date(2025, 1, 1), date(2026, 9, 28)
BASE_A = dict(name="", start=S0, end=S1, type="fixed", fixed=40e6, exp="all", mult=1.0, basis="as NEST", share=0.5,
              dcap=50000, acap=10e6, minspend=1000, deficit="accumulates", ndays=30, startbudget=0.0,
              scale="no", b1=5e6, b2=15e6, s2=0.5, s3=0.5, sneg=0.5, decay=0.0, reset="quarter")
BASE_B = dict(BASE_A, type="expenses", basis="net", share=1.0, s2=1.0, s3=1.0, sneg=1.0)

def variations(base, tag):
    out = [("base", {})]
    out += [("period from 01.01.2024", dict(start=date(2024, 1, 1)))]
    if tag == "A":
        out += [(f"threshold ${x/1e6:.0f}M", dict(fixed=x)) for x in (30e6, 35e6, 45e6)]
        out += [("net revenue", dict(basis="net"))]
        out += [(f"share {int(x*100)}%", dict(share=x)) for x in (0.25, 0.75, 1.0)]
    else:
        out += [("expenses: staking+general", dict(exp="staking+shared")), ("expenses: staking only", dict(exp="staking"))]
        out += [(f"expenses ×{x}", dict(mult=x)) for x in (0.9, 0.8, 0.7)]
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
            ("debt: 180-day window", dict(deficit="rolling window", ndays=180))]
    j = base["share"]
    lo = 0.25 if tag == "A" else 0.5
    out += [("tier scale 25/50/75%, bounds $5M/$15M", dict(scale="progressive", share=0.25, s2=0.5, s3=0.75, b1=5e6, b2=15e6, sneg=j)),
            ("tier scale 25/50/75%, bounds $2.5M/$10M", dict(scale="progressive", share=0.25, s2=0.5, s3=0.75, b1=2.5e6, b2=10e6, sneg=j)),
            ("tier scale 50/75/100%, bounds $5M/$15M", dict(scale="progressive", share=0.5, s2=0.75, s3=1.0, b1=5e6, b2=15e6, sneg=j)),
            ("tier scale 25/50/75%, deficit at 1st-tier share", dict(scale="progressive", share=0.25, s2=0.5, s3=0.75, b1=5e6, b2=15e6, sneg=0.25))]
    if tag == "A":
        out += [("live NEST period from 10.08.2026, excluding the launch glitch", dict(start=date(2026, 8, 10)))]
    return out

rows = []
for tag, base, bname in (("A", BASE_A, "Base A: current NEST"), ("B", BASE_B, "Base B: threshold = all expenses, net, 100%, accumulates")):
    base_res = None
    for label, ch in variations(base, tag):
        p = dict(base, **ch); p["name"] = f"{tag}: {label}"
        res = run(p)
        if label == "base": base_res = res
        rows.append((tag, bname, label, p, res, res["total"] - base_res["total"]))

if __name__ == "__main__":
    for tag, bname, label, p, r, dlt in rows:
        cov = f"{r['coverage']*100:.0f}%" if r["coverage"] is not None else "no profit"
        print(f"{tag} {label[:44]:44s} buybacks {r['total']/1e6:6.2f}M Δ{dlt/1e6:+6.2f}M days {r['days']:4d} overspend {r['over']/1e6:5.2f}M LDO {r['ldo_m']:5.2f}M end {r['end']/1e6:+7.2f}M on {r['switches']}")
    json.dump([dict(tag=t, base=bn, label=l, params={k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in p.items()},
                    res={k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in r.items()}, delta=d)
               for t, bn, l, p, r, d in rows], open("stage1_results.json", "w"), ensure_ascii=False, indent=1)
    print(len(rows), "variants")
