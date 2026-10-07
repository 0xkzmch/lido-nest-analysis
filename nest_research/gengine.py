"""Generic NEST rule engine on an arbitrary day series (history, flat forward, Monte Carlo paths). 29.09.2026.
Families: 'threshold' (fixed / known / budget / fact expenses, optional report-based true-up) and 'revshare' (fixed % of revenue, no threshold).
Overlays: treasury guard (keep >= N months of expenses after a buy), LDO price condition (buy only if LDO <= k * MA90).
Validated against engine.run / run_trueup / forward_trueup (see __main__)."""
import csv, json, math, random
from datetime import date, timedelta
import engine as E

S_HOLD = 34531.06 + 6754.33                 # stETH in DAO treasury + reserve fund, 30.06.2026 (H1 report)
S_DAO = 34531.06                             # stETH in DAO treasury only (reserve fund excluded from available liquidity)
L1_0 = 6.38e6 + 1.20e6 + 0.45e6 + 0.68e6 + 7.60e6   # level-1 liquidity 30.06.2026: stablecoins, yield-bearing stables, fiat (DAO + Foundations)
S_HOLD_DEC = 33561.30 + 6672.30             # 31.12.2025
O_DEC, O_JUN, O_AUG = 157.50e6 - S_HOLD_DEC * 2967.7, 88.25e6 - S_HOLD * 1569.0, 121.3e6 - S_HOLD * 2441.0

def _o_hist(d):
    """non-stETH treasury assets (stables, LP, Foundations), linear between report anchors; constant outside (approximation)."""
    if d <= date(2025, 12, 31): return O_DEC
    if d <= date(2026, 6, 30):
        t = (d - date(2025, 12, 31)).days / 181; return O_DEC + (O_JUN - O_DEC) * t
    if d <= date(2026, 8, 25):
        t = (d - date(2026, 6, 30)).days / 56; return O_JUN + (O_AUG - O_JUN) * t
    return O_AUG

def _s_hist(d):
    if d <= date(2025, 12, 31): return S_HOLD_DEC
    if d <= date(2026, 6, 30): return S_HOLD_DEC + (S_HOLD - S_HOLD_DEC) * (d - date(2025, 12, 31)).days / 181
    return S_HOLD

def history_days(start=date(2025, 1, 1), end=date(2026, 9, 28)):
    rows = list(csv.DictReader(open("base/treasury_fee_inflows.csv")))
    ldo = json.load(open("data/ldo_px.json"))
    tu = {t["date"]: t["pi"] for t in E.TRUEUP}
    out = []
    for i, r in enumerate(rows):
        d = date.fromisoformat(r["date"])
        pi = E.pidx(d); per = E.PERIODS[pi]
        out.append(dict(d=d, eth=float(r["eth_usd"]), rev=float(r["usd"]), cor=per["corrate"], exp=per["d_all"],
                        x_earn=per["x_earn"], x_ti=per["x_ti"], x_one=per["x_one"],
                        known=E.KNOWN[E.kidx(d)]["all"], budget=E.BUDGET[E.bidx(d)]["all"], budget41=E.BUDGET_41[E.bidx(d)]["all"],
                        ldo=ldo[i], ma90=sum(ldo[max(0, i - 89):i + 1]) / len(ldo[max(0, i - 89):i + 1]), period=pi, trueup=tu.get(d),
                        treasury_base=_s_hist(d) * float(r["eth_usd"]) + _o_hist(d), active=start <= d <= end))
    return out

REPORTS_FWD = [(date(2026, 7, 1), date(2026, 9, 30), date(2026, 11, 29)), (date(2026, 10, 1), date(2026, 12, 31), date(2027, 3, 1)),
               (date(2027, 1, 1), date(2027, 3, 31), date(2027, 5, 30)), (date(2027, 4, 1), date(2027, 6, 30), date(2027, 8, 29)),
               (date(2027, 7, 1), date(2027, 9, 30), date(2027, 11, 29))]

def forward_days(eth_path, ldo_path=None, start=date(2026, 9, 29), exp_mult_q=None, oneoffs=None, report_delays=None):
    """eth_path: daily ETH prices. Optional stress inputs:
    exp_mult_q: {quarter_index: multiplier} on actual expenses (quarters as in REPORTS_FWD);
    oneoffs: {date: USD} one-off losses; report_delays: {quarter_index: days after quarter end} (default: REPORTS_FWD, ~60)."""
    ldo_hist0 = json.load(open("data/ldo_px.json"))[-90:]
    reps = []
    for k, (s, e, rd) in enumerate(REPORTS_FWD):
        dl = (report_delays or {}).get(k)
        reps.append((s, e, e + timedelta(days=dl) if dl is not None else rd))
    rep_by_date = {}
    for k, (s, e, rd) in enumerate(reps): rep_by_date.setdefault(rd, []).append(k)
    per4 = E.PERIODS[4]; out = []
    hist = list(ldo_hist0)
    for i, px in enumerate(eth_path):
        d = start + timedelta(days=i)
        q = next((k for k, (s, e, rd) in enumerate(reps) if s <= d <= e), None)
        lp = ldo_path[i] if ldo_path else ldo_hist0[-1]
        hist.append(lp)
        if len(hist) > 90: hist.pop(0)
        em = (exp_mult_q or {}).get(q, 1.0)
        out.append(dict(d=d, eth=px, rev=E.STETH_DAY_30 * px, cor=E.COR_FWD, exp=E.fwd_expense_all(d) * em,
                        x_earn=per4["x_earn"], x_ti=per4["x_ti"], x_one=(oneoffs or {}).get(d, 0.0), known=E.KNOWN[-1]["all"],
                        budget=43.8e6 / 365, budget41=41e6 / 365, ldo=lp, ma90=sum(hist) / len(hist),
                        period=q, trueups=rep_by_date.get(d, []), trueup=None, treasury_base=None, active=True))
    return out

def sim(rule, days, start_budget=0.0, cap_anchor=None, forward=False, o0=None):
    r = rule; J = r.get("share", 0.5); meff = r.get("mult", 1.0) if r.get("cuts_real", "yes") == "yes" else 1.0
    mult = r.get("mult", 1.0); fam = r.get("family", "threshold"); typ = r.get("type", "fixed"); basis = r.get("basis", "as NEST")
    defm = r.get("deficit", "accumulates"); nd = r.get("ndays", 30); trueup = r.get("trueup", False)
    dcap, acap, mins = r.get("dcap", 50000), r.get("acap", 10e6), r.get("minspend", 1000)
    guard, pk = r.get("guard_months"), r.get("price_k")
    b = start_budget; spent = {}; tot = 0.0; days_b = 0; first = None; cum_p = 0.0; cum_b = 0.0; peak = 0.0
    prevkey = None; minb = 0.0; ldo_bought = 0.0; guard_blocked = 0; price_blocked = 0
    cd = []; cb = []; base_floor = None; cap_days = 0; ycap_days = 0; by_month = {}
    prov = {}; act = {}; min_runway = 1e18; o_fwd = o0 if o0 is not None else O_AUG; o_start = o_fwd
    anchor = None
    for x in days:
        if not x["active"]: continue
        d = x["d"]; anchor = anchor or (cap_anchor or d)
        net = x["rev"] * (1 - x["cor"]); dcf = net + x["x_earn"] + x["x_ti"]
        oneoff = x.get("x_one", 0.0) if r.get("with_oneoffs") else 0.0
        profit = dcf - x["exp"] * meff - oneoff
        if fam == "revshare":
            delta = r["pct"] * net
        elif trueup:
            if r.get("prov_rate_annual") is not None: rate = r["prov_rate_annual"] / 365 * mult
            else: rate = (x["known"] if r["prov_basis"] == "known" else (x["budget41"] if r["prov_basis"] == "budget 41" else x["budget"])) * mult
            delta = r["prov_share"] * (dcf - rate)
            q = x["period"]
            prov[q] = prov.get(q, 0.0) + delta
            act[q] = act.get(q, 0.0) + (dcf - x["exp"] * meff - oneoff)
        else:
            ru = x["rev"] if basis == "as NEST" else (net if basis == "net" else dcf)
            if typ == "fixed": base = int(r["fixed"] / 365)
            elif typ == "known": base = x["known"] * mult
            elif typ == "budget": base = x["budget"] * mult
            else: base = x["exp"] * mult
            base_floor = base
            s_ = ru - base
            sm = r.get("share_mode")
            if sm == "progressive":
                b1, b2 = r["b1"] / 365, r["b2"] / 365
                delta = (r["s1"] * min(s_, b1) + r["s2"] * min(max(s_ - b1, 0.0), b2 - b1) + r["s3"] * max(s_ - b2, 0.0)) if s_ >= 0 else r["sneg"] * s_
            elif sm == "asym":
                delta = r["s_pos"] * s_ if s_ >= 0 else r["s_neg"] * s_
            elif sm == "ldo":
                rel = x["ldo"] / x["ma90"] if x.get("ma90") else 1.0
                jj = r["s_cheap"] if rel <= r["lo"] else (r["s_dear"] if rel >= r["hi"] else J)
                delta = jj * s_
            else:
                delta = J * s_
        key = (d.year * 10 + (d.month - 1) // 3 + 1) if defm != "yearly reset" else d.year
        prev = b
        if defm in ("quarterly reset", "yearly reset") and prevkey is not None and key != prevkey: prev = max(0.0, prev)
        b = prev + delta
        cd.append((cd[-1] if cd else 0.0) + delta)
        if trueup:
            tq = x.get("trueups") or ([x["trueup"]] if x.get("trueup") is not None else [])
            for q in tq:
                raw = act.get(q, 0.0)
                if r.get("final_tiers") and raw >= 0:
                    (c1, f1), (c2, f2), f3 = r["final_tiers"]
                    tgt = f1 * min(raw, c1) + f2 * min(max(raw - c1, 0.0), c2 - c1) + f3 * max(raw - c2, 0.0)
                else:
                    fs = r["full_share"] if raw >= 0 else r.get("full_share_neg", r["full_share"])
                    tgt = fs * raw
                b += tgt - prov.get(q, 0.0); prov[q] = tgt
        if defm == "does not accumulate": b = max(0.0, b)
        elif defm == "floor":
            fb = x["exp"] * meff * r["full_share"] if trueup else (base_floor if base_floor is not None else x["exp"] * meff) * J
            b = max(b, -nd * fb)
        elif defm == "decay":
            if b < 0: b = b * (1 - r["decay"])
        elif defm == "window":
            i = len(cd) - 1
            b = (cd[i] - (cd[i - nd] if i - nd >= 0 else 0.0)) - ((cb[i - 1] if i >= 1 else 0.0) - (cb[i - nd] if i - nd >= 0 else 0.0)) + (start_budget if i < nd else 0.0)
        # treasury
        if forward:
            o_fwd += dcf - x["exp"] * meff - oneoff
            treasury = S_HOLD * x["eth"] + o_fwd - cum_b
            liquid = L1_0 + (o_fwd - o_start) - cum_b + (1 - r.get("haircut", 0.3)) * S_DAO * x["eth"]
        else:
            treasury = x["treasury_base"] - cum_b
        reserve = (guard or 0) * x["exp"] * meff * 30.4
        min_runway = min(min_runway, treasury / (x["exp"] * meff * 30.4))
        w = (d - anchor).days // 365; buy = 0.0
        if b > mins:
            lim_d = dcap if dcap > 0 else 1e18; lim_y = (acap - spent.get(w, 0.0)) if acap > 0 else 1e18
            buy = max(0.0, min(b, lim_d, lim_y))
            if buy > 0 and lim_d < b and lim_d <= lim_y: cap_days += 1
            if lim_y < b and lim_y <= lim_d: ycap_days += 1
            if buy > 0 and pk is not None:
                if x["ldo"] > pk * x["ma90"]: buy = 0.0; price_blocked += 1
            if buy > 0 and guard is not None:
                room = treasury - reserve
                if room < buy: guard_blocked += 1; buy = max(0.0, room)
            gl = r.get("guard_liquid_months")
            if buy > 0 and gl is not None and forward:
                room = liquid - gl * x["exp"] * meff * 30.4
                if room < buy: guard_blocked += 1; buy = max(0.0, room)
        if buy > 0:
            spent[w] = spent.get(w, 0.0) + buy; tot += buy; days_b += 1; first = first or d; ldo_bought += buy / x["ldo"]
        b -= buy; minb = min(minb, b); prevkey = key
        cb.append((cb[-1] if cb else 0.0) + buy)
        if buy > 0: by_month[d.year * 12 + d.month] = by_month.get(d.year * 12 + d.month, 0.0) + buy
        cum_p += profit; cum_b += buy; peak = max(peak, max(0.0, cum_b - max(cum_p, 0.0)))
    return dict(total=tot, days=days_b, first=first, end=b, min=minb, profit=cum_p, peak=peak, ldo=ldo_bought, cap_days=cap_days, ycap_days=ycap_days, by_month=by_month,
                min_runway=min_runway, guard_blocked=guard_blocked, price_blocked=price_blocked)

if __name__ == "__main__":
    H = history_days()
    a = sim(dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates"), H)
    print("NEST history:", round(a["total"]), a["days"], round(a["peak"]), round(a["profit"]), "| engine.run:", round(E.run(dict(E.BASE_A))["total"]))
    c = sim(dict(family="threshold", type="known", share=1.0, basis="net", deficit="quarterly reset"), H)
    print("known+reset:", round(c["total"]), c["days"], "| engine.run:", round(E.run(dict(E.BASE_C, deficit="reset by period"))["total"]))
    tur = dict(family="threshold", trueup=True, prov_basis="budget", prov_share=0.5, full_share=1.0, deficit="accumulates")
    t = sim(tur, H); tt = E.run_trueup(dict(E.TU if hasattr(E, "TU") else {}, **{}) if False else dict(start=date(2025,1,1), end=date(2026,9,28), prov_basis="budget", prov_share=0.5, full_share=1.0, mult=1.0, cuts_real="yes", floor_days=None, dcap=50000, acap=10e6, minspend=1000, measure="cash flow", startbudget=0.0))
    print("trueup budget 50%:", round(t["total"]), round(t["end"]), "| run_trueup:", round(tt["total"]), round(tt["end"]))
    F = forward_days([3000.0] * 365)
    f = sim(tur, F, forward=True)
    ft = E.forward_trueup(dict(prov_basis="budget", prov_share=0.5, full_share=1.0, mult=1.0, cuts_real="yes", floor_days=None, dcap=50000, acap=10e6, minspend=1000, measure="cash flow", startbudget=0.0), 3000)
    print("forward trueup @3000:", round(f["total"]), round(f["end"]), round(f["peak"]), "| forward_trueup:", round(ft["total"]), round(ft["end"]), round(ft["peak_ahead"]))
    n = sim(dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates"), F, start_budget=-548925, cap_anchor=date(2026,8,10), forward=True)
    nf = E.forward_run(dict(E.BASE_A), 3000, start_budget=-548925, cap_window_start=date(2026, 8, 10))
    print("forward NEST @3000:", round(n["total"]), "| forward_run:", round(nf["total"]))

# ---------------- Stage B: financial stress (expense shocks, one-offs, report delays, liquid-treasury guard) ----------------
QUARTERS_FWD = [(date(2026, 7, 1), date(2026, 9, 30)), (date(2026, 10, 1), date(2026, 12, 31)), (date(2027, 1, 1), date(2027, 3, 31)),
                (date(2027, 4, 1), date(2027, 6, 30)), (date(2027, 7, 1), date(2027, 9, 30))]
L1_JUN = 6.38e6 + 1.20e6 + 0.45e6 + 0.68e6 + 7.60e6   # stablecoins + yield-bearing stables + fiat, DAO + Foundations, 30.06.2026 (H1 report)

def forward_days_b(eth_path, ldo_path=None, exp_scale=1.0, exp_q=None, delays=None, oneoffs=None, start=date(2026, 9, 29)):
    """exp_scale: actual expenses vs forecast; exp_q: per-quarter multipliers (len 5); delays: per-quarter report delay in days;
    oneoffs: dict {date: amount} of one-off losses. Report k is published at quarter end + delay_k."""
    base = forward_days(eth_path, ldo_path, start)
    exp_q = exp_q or [1.0] * 5; delays = delays or [60] * 5; oneoffs = oneoffs or {}
    rep = {}
    for k, (s, e) in enumerate(QUARTERS_FWD):
        rep.setdefault(e + timedelta(days=delays[k]), []).append(k)
    for x in base:
        k = next(i for i, (s, e) in enumerate(QUARTERS_FWD) if s <= x["d"] <= e)
        x["period"] = k; x["exp"] = x["exp"] * exp_scale * exp_q[k]
        x["trueup"] = rep.get(x["d"]); x["oneoff"] = oneoffs.get(x["d"], 0.0)
    return base

def sim_b(rule, days, start_budget=0.0, cap_anchor=None):
    """Forward-only simulator with one-offs, multi-report days and optional liquid-treasury guard.
    Liquid treasury (level 2) = stables/fiat (from 30.06.2026, rolled forward with cash flows) + stETH x ETH x (1 - haircut)."""
    r = rule; J = r.get("share", 0.5); meff = r.get("mult", 1.0) if r.get("cuts_real", "yes") == "yes" else 1.0
    mult = r.get("mult", 1.0); fam = r.get("family", "threshold"); typ = r.get("type", "fixed"); basis = r.get("basis", "as NEST")
    defm = r.get("deficit", "accumulates"); nd = r.get("ndays", 30); trueup = r.get("trueup", False)
    dcap, acap, mins = r.get("dcap", 50000), r.get("acap", 10e6), r.get("minspend", 1000)
    lg, hc = r.get("liq_guard_months"), r.get("haircut", 0.3)
    b = start_budget; spent = {}; tot = 0.0; cum_p = 0.0; cum_b = 0.0; peak = 0.0; prevkey = None; ldo_b = 0.0
    prov = {}; act = {}; l1 = L1_JUN; guard_hits = 0; min_liq_months = 1e18; anchor = None
    for x in days:
        d = x["d"]; anchor = anchor or (cap_anchor or d)
        net = x["rev"] * (1 - x["cor"]); dcf = net + x["x_earn"] + x["x_ti"]; one = x.get("oneoff", 0.0)
        profit = dcf - one - x["exp"] * meff
        if fam == "revshare":
            delta = r["pct"] * net
        elif trueup:
            rate = (r["prov_annual"] / 365 if "prov_annual" in r else (x["known"] if r["prov_basis"] == "known" else
                    (x["budget41"] if r["prov_basis"] == "budget 41" else x["budget"]))) * mult
            delta = r["prov_share"] * (dcf - rate)
            q = x["period"]; prov[q] = prov.get(q, 0.0) + delta
            act[q] = act.get(q, 0.0) + r["full_share"] * (dcf - one - x["exp"] * meff)
        else:
            ru = x["rev"] if basis == "as NEST" else (net if basis == "net" else dcf)
            base = int(r["fixed"] / 365) if typ == "fixed" else (x["known"] * mult if typ == "known" else x["budget"] * mult)
            base_floor = base
            s_ = ru - base
            sm = r.get("share_mode")
            if sm == "progressive":
                b1, b2 = r["b1"] / 365, r["b2"] / 365
                delta = (r["s1"] * min(s_, b1) + r["s2"] * min(max(s_ - b1, 0.0), b2 - b1) + r["s3"] * max(s_ - b2, 0.0)) if s_ >= 0 else r["sneg"] * s_
            elif sm == "asym":
                delta = r["s_pos"] * s_ if s_ >= 0 else r["s_neg"] * s_
            elif sm == "ldo":
                rel = x["ldo"] / x["ma90"] if x.get("ma90") else 1.0
                jj = r["s_cheap"] if rel <= r["lo"] else (r["s_dear"] if rel >= r["hi"] else J)
                delta = jj * s_
            else:
                delta = J * s_
        key = (d.year * 10 + (d.month - 1) // 3 + 1) if defm != "yearly reset" else d.year
        prev = b
        if defm in ("quarterly reset", "yearly reset") and prevkey is not None and key != prevkey: prev = max(0.0, prev)
        b = prev + delta
        cd.append((cd[-1] if cd else 0.0) + delta)
        if trueup and x["trueup"]:
            for q in x["trueup"]:
                b += act.get(q, 0.0) - prov.get(q, 0.0); prov[q] = act.get(q, 0.0)
        if defm == "does not accumulate": b = max(0.0, b)
        elif defm == "floor":
            fb = x["exp"] * meff * r["full_share"] if trueup else (base_floor if base_floor is not None else x["exp"] * meff) * J
            b = max(b, -nd * fb)
        elif defm == "decay":
            if b < 0: b = b * (1 - r["decay"])
        elif defm == "window":
            i = len(cd) - 1
            b = (cd[i] - (cd[i - nd] if i - nd >= 0 else 0.0)) - ((cb[i - 1] if i >= 1 else 0.0) - (cb[i - nd] if i - nd >= 0 else 0.0)) + (start_budget if i < nd else 0.0)
        l1 += dcf - one - x["exp"] * meff
        liq = l1 + S_HOLD * x["eth"] * (1 - hc) - cum_b
        monthly = x["exp"] * meff * 30.4
        min_liq_months = min(min_liq_months, liq / monthly)
        w = (d - anchor).days // 365; buy = 0.0
        if b > mins:
            lim_d = dcap if dcap > 0 else 1e18; lim_y = (acap - spent.get(w, 0.0)) if acap > 0 else 1e18
            buy = max(0.0, min(b, lim_d, lim_y))
            if buy > 0 and lim_d < b and lim_d <= lim_y: cap_days += 1
            if lim_y < b and lim_y <= lim_d: ycap_days += 1
            if buy > 0 and r.get("price_k") is not None and x["ldo"] > r["price_k"] * x["ma90"]: buy = 0.0
            if buy > 0 and lg is not None:
                room = liq - lg * monthly
                if room < buy: guard_hits += 1; buy = max(0.0, room)
        if buy > 0: spent[w] = spent.get(w, 0.0) + buy; tot += buy; ldo_b += buy / x["ldo"]
        b -= buy; prevkey = key
        cum_p += profit; cum_b += buy; peak = max(peak, max(0.0, cum_b - max(cum_p, 0.0)))
    return dict(total=tot, end=b, profit=cum_p, peak=peak, ldo=ldo_b, guard_hits=guard_hits, min_liq_months=min_liq_months)
