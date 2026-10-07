#!/usr/bin/env python3
"""Canonical Lido value-capture simulator v2 (merged 2026-09-22).
Data: revenue_composite.csv — fully on-chain treasury staking revenue
(mints to Agent through 2025-12-23, TokenRebased-derived after; validated
against the NEST meter to 0.3%). Accounting layer from GOOSE-2025 Final
Report (thread 11304, verified) and the H1-2026 report; H2-2026 expenses
use the FY forecast remainder, H2 accounting revenue scales the on-chain
series by the H1 accounting/on-chain ratio.
Models: fixed (NEST-style), opex (baseline = modeled daily expenses x margin),
profit (accounting revenue proxy minus modeled expenses). Contract-style
fixed-anchor 365d cap windows; deficit modes unlimited | floor(N days) | zero.
"""
import csv, collections
from dataclasses import dataclass
from datetime import date

ANNUAL = {  # verified vs research.lido.fi/t/11304
    2024: {"total_revenue": 52.4e6, "foundation_expenses": 52.1e6},
    2025: {"total_revenue": 40.5e6, "foundation_expenses": 45.5e6},
}
Q2026 = [   # H1-2026 report split (hub version; totals match forum H1: 15.94 / 14.33)
    (date(2026,1,1), date(2026,3,31), 8.83e6, 6.92e6),
    (date(2026,4,1), date(2026,6,30), 7.11e6, 7.41e6),
]
FY2026_EXPENSE_FORECAST = 37.7e6
OPEX_ANNUAL = {2024: 52.1e6, 2025: 45.5e6, 2026: 37.7e6, 2027: 37.7e6}

@dataclass
class Policy:
    name: str
    model: str = "fixed"              # fixed | opex | profit
    fixed_baseline: float = 40e6
    opex_margin: float = 1.0
    share: float = 0.5
    daily_cap: float = 50_000
    annual_cap: float = 10e6
    min_spend: float = 1_000          # on-chain minSpendPerCallUSD
    deficit_mode: str = "unlimited"   # unlimited | zero | floor
    deficit_floor_days: float = 30
    revenue_multiplier: float = 1.0
    expense_multiplier: float = 1.0

def load_rows(path="data/revenue_composite.csv"):
    rows=[]
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"date": date.fromisoformat(r["date"]),
                         "nest_revenue": float(r["revenue_usd"])})
    by_year=collections.defaultdict(float)
    for r in rows: by_year[r["date"].year]+=r["nest_revenue"]
    q_on={ (s,e): sum(r["nest_revenue"] for r in rows if s<=r["date"]<=e) for s,e,_,_ in Q2026 }
    h1_on=sum(r["nest_revenue"] for r in rows if date(2026,1,1)<=r["date"]<=date(2026,6,30))
    h1_ratio=(Q2026[0][2]+Q2026[1][2])/h1_on
    h2_exp=(FY2026_EXPENSE_FORECAST-(Q2026[0][3]+Q2026[1][3]))/184
    for r in rows:
        d=r["date"]
        if d.year in ANNUAL:
            r["acct_revenue"]=r["nest_revenue"]*(ANNUAL[d.year]["total_revenue"]/by_year[d.year])
            r["expense"]=ANNUAL[d.year]["foundation_expenses"]/(366 if d.year==2024 else 365)
        elif d<=date(2026,6,30):
            for s,e,rev,exp in Q2026:
                if s<=d<=e:
                    r["acct_revenue"]=r["nest_revenue"]*(rev/q_on[(s,e)])
                    r["expense"]=exp/((e-s).days+1); break
        else:
            r["acct_revenue"]=r["nest_revenue"]*h1_ratio
            r["expense"]=h2_exp
    return rows

def simulate(rows, p: Policy, start, end, start_budget=0.0):
    budget=start_budget
    spent=collections.defaultdict(float); alloc=collections.defaultdict(float)
    days_bought=0; first_buy=None
    for r in rows:
        d=r["date"]
        if not (start<=d<=end): continue
        if p.model=="fixed":
            revenue=r["nest_revenue"]*p.revenue_multiplier; baseline=p.fixed_baseline/365
        elif p.model=="opex":
            revenue=r["nest_revenue"]*p.revenue_multiplier
            baseline=r["expense"]*p.expense_multiplier*p.opex_margin
        elif p.model=="profit":
            revenue=r["acct_revenue"]*p.revenue_multiplier
            baseline=r["expense"]*p.expense_multiplier
        else: raise ValueError(p.model)
        budget += p.share*(revenue-baseline)
        if p.deficit_mode=="zero": budget=max(0.0,budget)
        elif p.deficit_mode=="floor": budget=max(budget,-p.deficit_floor_days*baseline*p.share)
        win=(d-start).days//365
        if budget>p.min_spend:
            a=min(budget, p.daily_cap, max(0.0, p.annual_cap-spent[win]))
            if a>0:
                budget-=a; spent[win]+=a; alloc[d.year]+=a
                days_bought+=1; first_buy=first_buy or d
    return {"alloc":dict(alloc), "total":sum(alloc.values()), "end_budget":budget,
            "days_bought":days_bought, "first_buy":first_buy}

SCENARIOS = [
    Policy("Current NEST 40M/50%"),
    Policy("Current + floor0", deficit_mode="zero"),
    Policy("Fixed 35M/50%", fixed_baseline=35e6),
    Policy("Fixed 30M/100% (proposal)", fixed_baseline=30e6, share=1.0),
    Policy("Fixed 30M/100% + floor0", fixed_baseline=30e6, share=1.0, deficit_mode="zero"),
    Policy("OPEX-link 75% + floor0", model="opex", share=0.75, deficit_mode="zero"),
    Policy("OPEX-link 100% + floor0", model="opex", share=1.0, deficit_mode="zero"),
    Policy("OPEX-link 100% f0 + 20% cut", model="opex", share=1.0, deficit_mode="zero", expense_multiplier=0.8),
    Policy("Profit-share 50% zero-deficit", model="profit", deficit_mode="zero"),
    Policy("Profit-share 50% + 20% cut", model="profit", deficit_mode="zero", expense_multiplier=0.8),
]

if __name__=="__main__":
    rows=load_rows()
    for wstart in (date(2024,1,1), date(2025,1,1)):
        print(f"\n=== window {wstart} .. 2026-09-20 ===")
        for p in SCENARIOS:
            r=simulate(rows,p,wstart,date(2026,9,20))
            a=r["alloc"]
            print(f"{p.name:30s} 24:${a.get(2024,0)/1e6:5.2f}M 25:${a.get(2025,0)/1e6:5.2f}M 26:${a.get(2026,0)/1e6:5.2f}M  tot ${r['total']/1e6:6.2f}M  end ${r['end_budget']/1e6:+6.2f}M  d{r['days_bought']}")
