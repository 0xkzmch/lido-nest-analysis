"""NEST buyback rule engine v3 (29.09.2026) — mirrors the Variants/Engine formulas of nest_model.xlsx.

Changes vs v2 (after external review):
- fixed baseline uses the contract literal: floor(annual / 365) -> $109,589/day for $40M;
- threshold types: 'fixed', 'expenses (actual)' (hindsight: actual period expenses), 'expenses (known)'
  (no hindsight: last expense rate published before the day, by report publication dates);
- profit measures for evaluation (DAO level, all Foundations expenses):
    1 'staking balance'      = net staking revenue - expenses
    2 'DAO operating'      = + Earn net revenue            (H1-2026 report "Operating Result")
    3 'cash flow'        = + treasury income              (recurring cash available)
    4 'summary incl. one-offs'       = - one-off losses (Kelp)        (H1-2026 report "Total Result" + treasury income)
- 'cut is real' = yes/no: whether the expense multiplier also applies to the profit measure;
- two overspend metrics: buys in periods that ended in loss (ex post), and buys not covered by profit
  accumulated at the moment of purchase (ex ante).
"""
import csv, json
from datetime import date

REV = [(date.fromisoformat(r["date"]), float(r["revenue_usd"])) for r in csv.DictReader(open("data/revenue_composite.csv"))]
LDO = json.load(open("data/ldo_px.json"))

# ---- period table (accounting periods) ----
# start, end, foundation expenses, staking costs, shared services, cost-of-revenue $, earn net, treasury income, one-offs
H1_ST, H1_SH, H1_EXP = 8.98e6, 3.15e6, 14.33e6
R_ST, R_SH = H1_ST / H1_EXP, H1_SH / H1_EXP
FY26 = 37.7e6
PERIODS = [
    dict(label="2024", s=date(2024,1,1), e=date(2024,12,31), exp=52.1e6, st=52.1e6*R_ST, sh=52.1e6*R_SH, cor=3.1e6, earn=0.0, ti=3.9e6, one=0.0),
    dict(label="2025", s=date(2025,1,1), e=date(2025,12,31), exp=45.5e6, st=45.5e6*R_ST, sh=45.5e6*R_SH, cor=4.1e6, earn=0.3e6, ti=2.7e6, one=0.0),
    dict(label="Q1 2026", s=date(2026,1,1), e=date(2026,3,31), exp=6.92e6, st=4.38e6, sh=1.57e6, cor=None, net=8.63e6, earn=0.20e6, ti=1.4e6*90/181, one=0.0),
    dict(label="Q2 2026", s=date(2026,4,1), e=date(2026,6,30), exp=7.41e6, st=4.60e6, sh=1.58e6, cor=None, net=7.08e6, earn=0.03e6, ti=1.4e6*91/181, one=6.06e6),
    dict(label="H2 2026", s=date(2026,7,1), e=date(2026,12,31), exp=FY26-6.92e6-7.41e6, st=None, sh=None, cor=None, earn=0.23e6/181*184, ti=1.4e6/181*184, one=0.0),
]
PERIODS[4]["st"] = PERIODS[4]["exp"] * R_ST; PERIODS[4]["sh"] = PERIODS[4]["exp"] * R_SH
for p in PERIODS:
    p["days"] = (p["e"] - p["s"]).days + 1
    p["onchain"] = sum(v for d, v in REV if p["s"] <= d <= p["e"])
    p["ndata"] = sum(1 for d, _ in REV if p["s"] <= d <= p["e"])
for p in PERIODS[2:4]:
    p["cor"] = p["onchain"] - p["net"]
h1_on = PERIODS[2]["onchain"] + PERIODS[3]["onchain"]
PERIODS[4]["cor"] = PERIODS[4]["onchain"] * (PERIODS[2]["cor"] + PERIODS[3]["cor"]) / h1_on
for p in PERIODS:
    p["corrate"] = p["cor"] / p["onchain"] if p["onchain"] > 0 else 0
    p["d_all"] = p["exp"] / p["days"]; p["d_stsh"] = (p["st"] + p["sh"]) / p["days"]; p["d_st"] = p["st"] / p["days"]
    p["x_earn"] = p["earn"] / p["days"]; p["x_ti"] = p["ti"] / p["days"]; p["x_one"] = p["one"] / p["days"]

# ---- known expense rates (no hindsight), by report publication date ----
KNOWN = [
    dict(s=date(2024,1,1), all=52.1e6/366, stsh=52.1e6*(R_ST+R_SH)/366, st=52.1e6*R_ST/366, note="2024 actual (no data for 2023, assumption)"),
    dict(s=date(2025,1,1), all=52.1e6/366, stsh=52.1e6*(R_ST+R_SH)/366, st=52.1e6*R_ST/366, note="2024 run rate (2024 report date not found, assumption: known from 01.01.2025)"),
    dict(s=date(2026,3,17), all=45.5e6/365, stsh=45.5e6*(R_ST+R_SH)/365, st=45.5e6*R_ST/365, note="2025 run rate, report t/11304 dated 17.03.2026"),
    dict(s=date(2026,6,4), all=6.44e6/90, stsh=(4.38e6+1.57e6)/90*0.930636, st=4.38e6/90*0.930636, note="Q1 2026 run rate as published in report t/11623 dated 04.06.2026 ($6.44M); the H1 report restated Q1 to $6.92M"),
    dict(s=date(2026,8,28), all=14.33e6/181, stsh=(8.98e6+3.15e6)/181, st=8.98e6/181, note="H1 2026 run rate, report t/11836 dated 28.08.2026"),
]

POL = {"accumulates": 1, "floor N days": 2, "does not accumulate": 3, "decay": 4, "reset by period": 5, "rolling window": 6}
OPT = {"all": "d_all", "staking+shared": "d_stsh", "staking": "d_st"}
KOPT = {"all": "all", "staking+shared": "stsh", "staking": "st"}
MEAS = {"staking balance": 1, "DAO operating": 2, "cash flow": 3, "summary incl. one-offs": 4}

def pidx(d):
    k = 0
    for i, p in enumerate(PERIODS):
        if d >= p["s"]: k = i
    return k

def kidx(d):
    k = 0
    for i, p in enumerate(KNOWN):
        if d >= p["s"]: k = i
    return k

def extra(per, m):
    return [0.0, per["x_earn"], per["x_earn"] + per["x_ti"], per["x_earn"] + per["x_ti"] - per["x_one"]][m - 1]

def run(p):
    start, end = p["start"], p["end"]
    typ = p["type"]; net = p["basis"] == "net"; scale = p["scale"] == "progressive"
    J, T, U, Vn = p["share"], p["s2"], p["s3"], p["sneg"]; R, S = p["b1"], p["b2"]
    defm = POL[p["deficit"]]; nd = p["ndays"]; dc = p["decay"]; quarter = p["reset"] == "quarter"
    dcap, acap, mins = p["dcap"], p["acap"], p["minspend"]
    meas = MEAS[p["measure"]]; meff = p["mult"] if p["cuts_real"] == "yes" else 1.0
    b = 0.0; spent = {}; alloc = {}; days = 0; sw = 0; prevbuy = 0.0; ldo_b = 0.0
    cd = []; cb = []; prevkey = None; minb = 0.0; first = None; prev_act = False
    cum_p = 0.0; uncovered = 0.0; profit_win = 0.0
    per_profit = [0.0] * len(PERIODS); per_buy = [0.0] * len(PERIODS)
    for idx, (d, r) in enumerate(REV):
        pi = pidx(d); per = PERIODS[pi]
        act = start <= d <= end
        ru = r * (1 - per["corrate"]) if net else r
        if typ == "fixed":
            base = int(p["fixed"] / 365)
        elif typ == "expenses (actual)":
            base = per[OPT[p["exp"]]] * p["mult"]
        else:
            base = KNOWN[kidx(d)][KOPT[p["exp"]]] * p["mult"]
        su = ru - base
        if act:
            delta = ((J * min(su, R / 365) + T * min(max(su - R / 365, 0), max(S - R, 0) / 365) + U * max(su - S / 365, 0))
                     if su >= 0 else Vn * su) if scale else J * su
        else:
            delta = 0.0
        key = (d.year * 10 + (d.month - 1) // 3 + 1) if quarter else d.year
        cd.append((cd[-1] if cd else 0) + delta)
        profit = r * (1 - per["corrate"]) + extra(per, meas) - per["d_all"] * meff
        per_profit[pi] += profit
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
                post = (cd[i] - (cd[i - nd] if i - nd >= 0 else 0)) - ((cb[i - 1] if i >= 1 else 0) - (cb[i - nd] if i - nd >= 0 else 0))
            w = (d - start).days // 365
            if post > mins:
                buy = max(0, min(post, dcap if dcap > 0 else 1e18, (acap - spent.get(w, 0)) if acap > 0 else 1e18))
            cum_p = (cum_p if prev_act else 0.0) + profit
            profit_win += profit
            if buy > 0:
                spent[w] = spent.get(w, 0) + buy; alloc[d.year] = alloc.get(d.year, 0) + buy; days += 1
                first = first or d
            cum_b_win = (cb[-1] if cb else 0) + buy
            uncovered = max(uncovered, max(0.0, cum_b_win - max(cum_p, 0.0)))
            b = post - buy; minb = min(minb, b)
            ldo_b += buy / LDO[idx]
            if buy > 0 and prevbuy == 0: sw += 1
            per_buy[pi] += buy
        cb.append((cb[-1] if cb else 0) + buy)
        prevbuy = buy; prevkey = key; prev_act = act
    tot = sum(alloc.values())
    over_period = sum(per_buy[i] for i in range(len(PERIODS)) if per_profit[i] < 0)
    return {"b2024": alloc.get(2024, 0), "b2025": alloc.get(2025, 0), "b2026": alloc.get(2026, 0), "total": tot,
            "days": days, "first": first, "end": b, "min": minb, "ldo_m": ldo_b / 1e6, "profit": profit_win,
            "coverage": (tot / profit_win) if profit_win > 0 else None, "over_period": over_period,
            "uncovered": uncovered, "switches": sw}

S0, S1 = date(2025, 1, 1), date(2026, 9, 28)
BASE_A = dict(name="", start=S0, end=S1, type="fixed", fixed=40e6, exp="all", mult=1.0, basis="as NEST", share=0.5,
              dcap=50000, acap=10e6, minspend=1000, deficit="accumulates", ndays=30, startbudget=0.0,
              scale="no", b1=5e6, b2=15e6, s2=0.5, s3=0.5, sneg=0.5, decay=0.0, reset="quarter",
              measure="cash flow", cuts_real="yes")
BASE_B = dict(BASE_A, type="expenses (actual)", basis="net", share=1.0, s2=1.0, s3=1.0, sneg=1.0)
BASE_C = dict(BASE_B, type="expenses (known)")

if __name__ == "__main__":
    for p in PERIODS:
        print(f"{p['label']:8s} exp {p['exp']/1e6:6.2f} onchain {p['onchain']/1e6:6.2f} cor {p['cor']/1e6:5.2f} ({p['corrate']*100:.2f}%) "
              f"earn {p['earn']/1e6:.2f} ti {p['ti']/1e6:.2f} one {p['one']/1e6:.2f}")
        net = p['onchain'] - p['cor']; nd = p['ndata']
        print(f"          on available days: staking balance {(net - p['d_all']*nd)/1e6:+.2f} | DAO operating {(net + p['x_earn']*nd - p['d_all']*nd)/1e6:+.2f} "
              f"| cash flow {(net + (p['x_earn']+p['x_ti'])*nd - p['d_all']*nd)/1e6:+.2f} | incl. one-offs {(net + (p['x_earn']+p['x_ti']-p['x_one'])*nd - p['d_all']*nd)/1e6:+.2f}")
    r = run(dict(BASE_A)); print("A:", {k: (round(v) if isinstance(v, float) else v) for k, v in r.items()})

# ---------------- forward simulation through the same daily logic ----------------
from datetime import timedelta
_rows = list(csv.DictReader(open("base/treasury_fee_inflows.csv")))
STETH_DAY_30 = sum(float(r["steth"]) for r in _rows[-30:]) / 30
COR_FWD = PERIODS[4]["corrate"]
X_FWD = [0.0, PERIODS[4]["x_earn"], PERIODS[4]["x_earn"] + PERIODS[4]["x_ti"], PERIODS[4]["x_earn"] + PERIODS[4]["x_ti"]]
NEST_CAP_WINDOW_START = date(2026, 8, 10)

def fwd_baseline(p, d):
    if p["type"] == "fixed": return int(p["fixed"] / 365)
    if p["type"] == "expenses (actual)":
        rate = PERIODS[4][OPT[p["exp"]]] if d <= date(2026, 12, 31) else FY26 / 365 * {"d_all": 1, "d_stsh": R_ST + R_SH, "d_st": R_ST}[OPT[p["exp"]]]
        return rate * p["mult"]
    return KNOWN[-1][KOPT[p["exp"]]] * p["mult"]

def fwd_expense_all(d):
    return PERIODS[4]["d_all"] if d <= date(2026, 12, 31) else FY26 / 365

def forward_run(p, price, start=date(2026, 9, 29), days=365, start_budget=0.0, cap_window_start=None, spent_before=0.0):
    """Same daily rules as run(), on a flat revenue path at a constant ETH price.
    cap_window_start: anchor of the 365-day cap window (NEST: activation 10.08.2026); spent_before: already spent in the current window."""
    net = p["basis"] == "net"; scale = p["scale"] == "progressive"
    J, T, U, Vn = p["share"], p["s2"], p["s3"], p["sneg"]; R, S = p["b1"], p["b2"]
    defm = POL[p["deficit"]]; nd = p["ndays"]; dc = p["decay"]; quarter = p["reset"] == "quarter"
    dcap, acap, mins = p["dcap"], p["acap"], p["minspend"]; meas = MEAS[p["measure"]]
    meff = p["mult"] if p["cuts_real"] == "yes" else 1.0
    anchor = cap_window_start or start
    rev_day = STETH_DAY_30 * price
    b = start_budget; spent = {}; tot = 0.0; first = None; cd = []; cb = []; prevkey = None
    cum_p = 0.0; uncovered = 0.0
    w0 = (start - anchor).days // 365
    spent[w0] = spent_before
    for i in range(days):
        d = start + timedelta(days=i)
        ru = rev_day * (1 - COR_FWD) if net else rev_day
        base = fwd_baseline(p, d)
        su = ru - base
        delta = ((J * min(su, R / 365) + T * min(max(su - R / 365, 0), max(S - R, 0) / 365) + U * max(su - S / 365, 0))
                 if su >= 0 else Vn * su) if scale else J * su
        key = (d.year * 10 + (d.month - 1) // 3 + 1) if quarter else d.year
        cd.append((cd[-1] if cd else 0) + delta)
        prev = b
        if defm == 5 and prevkey is not None and key != prevkey: prev = max(0, prev)
        pre = prev + delta; ns = Vn if scale else J
        if defm == 1: post = pre
        elif defm == 2: post = max(pre, -nd * base * ns)
        elif defm == 3: post = max(0, pre)
        elif defm == 4: post = pre * (1 - dc) if pre < 0 else pre
        elif defm == 5: post = pre
        else:
            k = len(cd) - 1
            post = (cd[k] - (cd[k - nd] if k - nd >= 0 else 0)) - ((cb[k - 1] if k >= 1 else 0) - (cb[k - nd] if k - nd >= 0 else 0)) + (start_budget if k < nd else 0)
        w = (d - anchor).days // 365
        buy = 0.0
        if post > mins:
            buy = max(0, min(post, dcap if dcap > 0 else 1e18, (acap - spent.get(w, 0)) if acap > 0 else 1e18))
        profit = rev_day * (1 - COR_FWD) + X_FWD[meas - 1] - fwd_expense_all(d) * meff
        cum_p += profit
        if buy > 0:
            spent[w] = spent.get(w, 0) + buy; tot += buy; first = first if first is not None else i
        uncovered = max(uncovered, max(0.0, (cb[-1] if cb else 0) + buy - max(cum_p, 0.0)))
        b = post - buy
        cb.append((cb[-1] if cb else 0) + buy); prevkey = key
    return {"total": tot, "first_day": first, "end": b, "uncovered": uncovered, "profit": cum_p}

# ---------------- Stage 3: cash-flow rule with quarterly (report-based) true-up ----------------
# Reporting periods and the dates when their actual expenses became public.
TRUEUP = [
    dict(pi=1, date=date(2026, 3, 17), note="2025, GOOSE-2025 Final Report (t/11304)"),
    dict(pi=2, date=date(2026, 6, 4), note="Q1 2026, report t/11623"),
    dict(pi=3, date=date(2026, 8, 28), note="Q2 2026, H1 report (t/11836)"),
]
# Approved budget (EGG) as a provisional expense rate: EGG-2026 approved baseline $43.8M ($26.9M Core + $16.9M Growth,
# t/10951, updated 10.12.2025; discretionary cap $16.2M excluded). H1-2026 report later cites a $41M "baseline" (bridge not explained)
# -> kept as alternative BUDGET_41. 2025 approved baseline not found -> proxy: 2024 actual (assumption).
BUDGET = [dict(s=date(2024, 1, 1), all=52.1e6 / 366, note="2024 actual (assumption)"),
          dict(s=date(2025, 1, 1), all=52.1e6 / 366, note="2025 budget proxy: 2024 actual (approved 2025 budget not found)"),
          dict(s=date(2026, 1, 1), all=43.8e6 / 365, note="EGG-2026 approved baseline $43.8M")]
BUDGET_41 = BUDGET[:2] + [dict(s=date(2026, 1, 1), all=41e6 / 365, note="baseline $41M per the H1 2026 report (alternative)")]

def bidx(d):
    k = 0
    for i, b in enumerate(BUDGET):
        if d >= b["s"]: k = i
    return k

def run_trueup(p):
    """p: start, end, prov_basis ('known'|'budget'), prov_share, full_share, mult, cuts_real, floor_days (None=unlimited),
    dcap, acap, minspend, measure, startbudget.
    Daily: budget += prov_share * (net staking + Earn + treasury income - provisional expense rate*mult).
    On each report date: budget += full_share * actual period surplus (DCF, all days of the period inside the window)
                                    - provisional contributions already booked for those days."""
    start, end = p["start"], p["end"]
    meas = MEAS[p["measure"]]; meff = p["mult"] if p["cuts_real"] == "yes" else 1.0
    b = p["startbudget"]; spent = {}; alloc = {}; days = 0; first = None; tot = 0.0
    prov_by_period = [0.0] * len(PERIODS); act_by_period = [0.0] * len(PERIODS)
    cum_p = 0.0; peak = 0.0; cum_b = 0.0; minb = 0.0; per_buy = [0.0] * len(PERIODS); per_profit = [0.0] * len(PERIODS)
    trueups = {t["date"]: t["pi"] for t in TRUEUP}; applied = []
    for idx, (d, r) in enumerate(REV):
        pi = pidx(d); per = PERIODS[pi]
        profit = r * (1 - per["corrate"]) + extra(per, meas) - per["d_all"] * meff
        per_profit[pi] += profit
        if not (start <= d <= end): continue
        dcf_rev = r * (1 - per["corrate"]) + per["x_earn"] + per["x_ti"]
        prov_rate = (KNOWN[kidx(d)]["all"] if p["prov_basis"] == "known" else (BUDGET_41 if p["prov_basis"] == "budget 41" else BUDGET)[bidx(d)]["all"]) * p["mult"]
        prov = p["prov_share"] * (dcf_rev - prov_rate)
        b += prov; prov_by_period[pi] += prov
        act_by_period[pi] += p["full_share"] * (dcf_rev - per["d_all"] * meff)
        if d in trueups:
            tp = trueups[d]
            adj = act_by_period[tp] - prov_by_period[tp]
            b += adj; applied.append((d.isoformat(), PERIODS[tp]["label"], adj))
            prov_by_period[tp] = act_by_period[tp]
        if p["floor_days"] is not None:
            b = max(b, -p["floor_days"] * PERIODS[pi]["d_all"] * meff * p["full_share"])
        w = (d - start).days // 365; buy = 0.0
        if b > p["minspend"]:
            buy = max(0, min(b, p["dcap"] if p["dcap"] > 0 else 1e18, (p["acap"] - spent.get(w, 0)) if p["acap"] > 0 else 1e18))
        if buy > 0:
            spent[w] = spent.get(w, 0) + buy; alloc[d.year] = alloc.get(d.year, 0) + buy; tot += buy; days += 1; first = first or d
            per_buy[pi] += buy
        b -= buy; minb = min(minb, b)
        cum_p += profit; cum_b += buy; peak = max(peak, max(0.0, cum_b - max(cum_p, 0.0)))
    over_period = sum(per_buy[i] for i in range(len(PERIODS)) if per_profit[i] < 0)
    return {"b2025": alloc.get(2025, 0), "b2026": alloc.get(2026, 0), "total": tot, "days": days, "first": first,
            "end": b, "min": minb, "profit": cum_p, "peak_ahead": peak, "over_period": over_period, "trueups": applied}

def forward_trueup(p, price, start=date(2026, 9, 29), days=365):
    """Forward version of run_trueup on a flat revenue path. Provisional rate: latest known (H1-2026) or budget ($41M EGG-2026;
    2027 budget assumed = 2026 forecast $37.7M). Actual expenses: H2-2026 forecast rate until 31.12.2026, then $37.7M/yr (assumption).
    Report dates assumed ~60 days after quarter end (Q2-2026 report came 59 days after)."""
    reports = [(date(2026, 7, 1), date(2026, 9, 30), date(2026, 11, 29)), (date(2026, 10, 1), date(2026, 12, 31), date(2027, 3, 1)),
               (date(2027, 1, 1), date(2027, 3, 31), date(2027, 5, 30)), (date(2027, 4, 1), date(2027, 6, 30), date(2027, 8, 29)),
               (date(2027, 7, 1), date(2027, 9, 30), date(2027, 11, 29))]
    meas = MEAS[p["measure"]]; meff = p["mult"] if p["cuts_real"] == "yes" else 1.0
    dcf_rev = STETH_DAY_30 * price * (1 - COR_FWD) + PERIODS[4]["x_earn"] + PERIODS[4]["x_ti"]
    b = p["startbudget"]; spent = {}; tot = 0.0; first = None; cum_p = 0.0; cum_b = 0.0; peak = 0.0
    prov = [0.0] * len(reports); act = [0.0] * len(reports)
    for i in range(days):
        d = start + timedelta(days=i)
        act_rate = fwd_expense_all(d)
        prov_rate = (KNOWN[-1]["all"] if p["prov_basis"] == "known" else (41e6 / 365 if p["prov_basis"] == "budget 41" else 43.8e6 / 365)) * p["mult"]
        c = p["prov_share"] * (dcf_rev - prov_rate); b += c
        for k, (s, e, rd) in enumerate(reports):
            if s <= d <= e: prov[k] += c; act[k] += p["full_share"] * (dcf_rev - act_rate * meff)
        for k, (s, e, rd) in enumerate(reports):
            if d == rd: b += act[k] - prov[k]; prov[k] = act[k]
        if p["floor_days"] is not None:
            b = max(b, -p["floor_days"] * act_rate * meff * p["full_share"])
        w = i // 365; buy = 0.0
        if b > p["minspend"]:
            buy = max(0, min(b, p["dcap"] if p["dcap"] > 0 else 1e18, (p["acap"] - spent.get(w, 0)) if p["acap"] > 0 else 1e18))
        if buy > 0: spent[w] = spent.get(w, 0) + buy; tot += buy; first = first if first is not None else i
        b -= buy
        cum_p += STETH_DAY_30 * price * (1 - COR_FWD) + X_FWD[meas - 1] - act_rate * meff
        cum_b += buy; peak = max(peak, max(0.0, cum_b - max(cum_p, 0.0)))
    return {"total": tot, "first_day": first, "end": b, "peak_ahead": peak, "profit": cum_p}
