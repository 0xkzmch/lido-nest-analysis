import math, random, statistics, json
from datetime import date, timedelta
from gengine import sim, forward_days, REPORTS_FWD
from scen3 import fwd, START_BUDGET, REB_DATES, REB_AMT
START=date(2026,10,1)
NEST=dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates")
NOTU=dict(family="threshold", type="budget", share=0.5, basis="cash flow", deficit="accumulates")
TU=dict(family="threshold", trueup=True, prov_basis="budget", prov_share=0.5, full_share=1.0, deficit="accumulates")
# (label, rule, days-variant, start budget)
C=[("A. Current NEST",NEST,1,START_BUDGET[1]),
   ("B. NEST + launch compensation",NEST,1,START_BUDGET[2]),
   ("C. NEST + CSM rebate as a source from October 1",NEST,3,START_BUDGET[1]),
   ("D. NEST, share 75%",dict(NEST,share=0.75),1,START_BUDGET[1]),
   ("E. NEST, share tiers 50/75/100%",dict(NEST,share_mode="progressive",s1=0.5,s2=0.75,s3=1.0,b1=5e6,b2=15e6,sneg=0.5),1,START_BUDGET[1]),
   ("F. NEST, debt decay 0.5% per day",dict(NEST,deficit="decay",decay=0.005),1,START_BUDGET[1]),
   ("G. EGG threshold $43.8M without true-up, expanded income, 50%",NOTU,1,START_BUDGET[1]),
   ("H. G + true-up, final share 50%",dict(TU,full_share=0.5),1,START_BUDGET[1]),
   ("I. G + true-up, final share 100%",dict(TU),1,START_BUDGET[1]),
   ("J. I + liquid treasury protection 18 mo",dict(TU,guard_liquid_months=18,haircut=0.3),1,START_BUDGET[1]),
   ("K. I + purchases only when LDO ≤ 90-day average",dict(TU,price_k=1.0),1,START_BUDGET[1]),
   ("L. Aksusarya proposal: $30M, 100%",dict(NEST,fixed=30e6,share=1.0),1,START_BUDGET[1])]
def paths(rng, sig_annual, drift_annual, beta, sig_i_annual):
    se=sig_annual/math.sqrt(365); si=sig_i_annual/math.sqrt(365); mu=math.log(1+drift_annual)/365
    e=[2679.84]; l=[0.4197]
    for _ in range(364):
        ze=rng.gauss(0,1); zi=rng.gauss(0,1)
        re=mu-0.5*se*se+se*ze; e.append(e[-1]*math.exp(re))
        l.append(l[-1]*math.exp(beta*(se*ze+mu)-0.5*(beta*beta*se*se+si*si)+si*zi))
    return e,l
def build(e,l,v,shock=None):
    d=fwd(e,v,ldo=l)
    if shock:
        em,one,dl=shock
        d2=forward_days(e,l,start=START,exp_mult_q=em,oneoffs=one,report_delays=dl)
        rd=set(REB_DATES)
        for x in d2:
            if x['d'] in rd:
                usd=REB_AMT*x['eth']
                if v==3: x['rev']+=usd; x['x_ti']+=usd*x['cor']
                else: x['x_ti']+=usd
        d=d2
    return d
