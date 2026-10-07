"""Recompute Summary, LDO and Stage5 sheets on the current engine and the same assumptions as the document (points 15–18):
start 01.10.2026, start budget -$542,451 for every rule, cap window from 10.08.2026, CSM rebate in DAO profit (version B), ETH+LDO paths calibrated as before."""
import sys, math, random, statistics, json
from datetime import date, timedelta
from p15 import *
calib=json.load(open('stage4_results.json'))['calibration']
SB=-542451.0; OUT=883.14e6; DC=4.76e6; DA=4.96e6
W=lambda r: dict(r, with_oneoffs=True)
TUr=dict(family="threshold", trueup=True, prov_basis="budget", prov_share=0.5, full_share=1.0, deficit="accumulates")
R4=[("Current NEST",dict(family="threshold",type="fixed",fixed=40e6,share=0.5,basis="as NEST",deficit="accumulates")),
 ("Aksusarya proposal: $30M, 100%",dict(family="threshold",type="fixed",fixed=30e6,share=1.0,basis="as NEST",deficit="accumulates")),
 ("NEST + quarterly debt reset",dict(family="threshold",type="fixed",fixed=40e6,share=0.5,basis="as NEST",deficit="quarterly reset")),
 ("Known expenses, net, 100%, quarterly reset, no true-up",dict(family="threshold",type="known",share=1.0,basis="net",deficit="quarterly reset")),
 ("True-up: approved budget $43.8M",dict(TUr)),("True-up: $41M base from H1 report (alternative)",dict(TUr,prov_basis="budget 41")),
 ("True-up $43.8M, prelim. 100%, 90-day floor",dict(TUr,prov_share=1.0,deficit="floor",ndays=90)),
 ("True-up $43.8M + buy only if LDO ≤ MA90",dict(TUr,price_k=1.0)),("True-up $43.8M with expenses −20% (actual)",dict(TUr,mult=0.8)),
 ("10% of net staking revenue",dict(family="revshare",pct=0.10)),("20% of net staking revenue",dict(family="revshare",pct=0.20))]
R5=[("Current NEST",W(R4[0][1])),("Aksusarya proposal: $30M, 100%",W(R4[1][1])),("NEST + quarterly debt reset",W(R4[2][1])),
 ("Known expenses, net, 100%, quarterly reset, no true-up",W(R4[3][1])),("Final share 100%",dict(TUr)),("Final share 75%",dict(TUr,full_share=0.75)),
 ("Final share 50%",dict(TUr,full_share=0.5)),("Base $41M, summary 100%",dict(TUr,prov_basis="budget 41")),
 ("+ liquid treasury protection 18 mo",dict(TUr,guard_liquid_months=18,haircut=0.3)),("+ buy only if LDO ≤ MA90",dict(TUr,price_k=1.0)),
 ("10% of net revenue",W(dict(family="revshare",pct=0.10)))]
def q(v,p): return statistics.quantiles(v,n=100)[p-1]
def S(r,d): return sim(r,d,start_budget=SB,cap_anchor=date(2026,8,10),forward=True)
def summ(a,N):
    net=[(DC-x)/OUT for x in a['ldo']]
    return dict(mean=statistics.mean(a['t']),p10=q(a['t'],10),p50=statistics.median(a['t']),p90=q(a['t'],90),p_any=a['buy']/N,p_joint=a['lb']/N,
                p_cond=(a['lb']/a['buy']) if a['buy'] else None,peak_mean=statistics.mean(a['pk']),p_peak_1m=sum(p>1e6 for p in a['pk'])/N,
                end_mean=statistics.mean(a['end']),guard_share=a['gb']/N,ldo_p10=q(a['ldo'],10),ldo_p50=statistics.median(a['ldo']),ldo_p90=q(a['ldo'],90),
                net_p10=q(net,10),net_p50=statistics.median(net),net_p90=q(net,90),p_reduce=sum(x>DC for x in a['ldo'])/N,p_reduce_all=sum(x>DA for x in a['ldo'])/N)
def stress(rules,seed,N,shocked):
    rng=random.Random(seed); acc={n:dict(t=[],pk=[],ldo=[],end=[],buy=0,lb=0,gb=0) for n,_ in rules}
    for i in range(N):
        e,l=paths(rng,calib['eth_vol_annual'],0.0,calib['beta'],calib['ldo_idio_vol_annual'])
        sh=None
        if shocked:
            sq=0.15; em={k:math.exp(-0.5*sq*sq+sq*rng.gauss(0,1)) for k in range(len(REPORTS_FWD))}
            one={}
            if rng.random()<0.25: one[START+timedelta(days=rng.randrange(365))]=rng.choice([3e6,6e6,10e6])
            dl={k:rng.randint(45,120) for k in range(len(REPORTS_FWD))}; sh=(em,one,dl)
        d=build(e,l,1,sh)
        for n,r in rules:
            o=S(r,d); a=acc[n]; a['t'].append(o['total']); a['pk'].append(o['peak']); a['ldo'].append(o['ldo']); a['end'].append(o['end'])
            a['gb']+=o['guard_blocked']>0
            if o['total']>0: a['buy']+=1; a['lb']+=o['profit']<0
    return {n:summ(acc[n],N) for n,_ in rules}
mode=sys.argv[1]
if mode=="summary":
    flat={n:{px:S(r,build([float(px)]*365,[0.4197]*365,1))['total'] for px in (2000,2680,3000,3500)} for n,r in R4}
    json.dump(dict(flat=flat,mc=stress(R4,2026,10000,False)),open('v2_summary.json','w'),ensure_ascii=False)
elif mode=="stage5":
    json.dump(stress(R5,55,10000,True),open('v2_stage5.json','w'),ensure_ascii=False)
elif mode=="grid":
    N=2000; rng=random.Random(77); P=[paths(rng,calib['eth_vol_annual'],0.0,calib['beta'],calib['ldo_idio_vol_annual']) for _ in range(N)]
    import os
    out=json.load(open('v2_grid.json')) if os.path.exists('v2_grid.json') else []
    only=int(sys.argv[2])
    for dl in (only,):
        for am in (0.8,1.0,1.2):
            ds=[build(e,l,1,({k:am for k in range(len(REPORTS_FWD))},{},{k:dl for k in range(len(REPORTS_FWD))})) for e,l in P]
            for pv in (37.7e6,41e6,43.8e6,46.4e6):
                for fs in (0.5,0.75,1.0):
                    r=dict(TUr,prov_rate_annual=pv,full_share=fs); a=dict(t=[],pk=[],ldo=[],end=[],buy=0,lb=0,gb=0)
                    for d in ds:
                        o=S(r,d); a['t'].append(o['total']); a['pk'].append(o['peak']); a['ldo'].append(o['ldo']); a['end'].append(o['end'])
                        if o['total']>0: a['buy']+=1; a['lb']+=o['profit']<0
                    out.append(dict(prov=pv,delay=dl,actual=am,final=fs,**summ(a,N)))
            json.dump(out,open('v2_grid.json','w'))
print("done",mode)
