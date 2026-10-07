import math, random, statistics, json
from datetime import date, timedelta
from gengine import sim, forward_days, REPORTS_FWD
from scen3 import REB_DATES, REB_AMT, START_BUDGET
START=date(2026,10,1)
def days(e, rebate=True, exp_mult_q=None, oneoffs=None, delays=None):
    d=forward_days(e,[0.4197]*len(e),start=START,exp_mult_q=exp_mult_q,oneoffs=oneoffs,report_delays=delays)
    if rebate:
        rd=set(REB_DATES)
        for x in d:
            if x['d'] in rd: x['x_ti']+=REB_AMT*x['eth']
    return d
TU=dict(family="threshold", trueup=True, prov_basis="budget", prov_share=0.5, full_share=1.0, deficit="accumulates")
NEST=dict(family="threshold", type="fixed", fixed=40e6, share=0.5, basis="as NEST", deficit="accumulates")
RULES={
 "Current NEST":(NEST,True),
 "Share tiers 50/75/100% (point 5)":(dict(NEST,share_mode="progressive",s1=0.5,s2=0.75,s3=1.0,b1=5e6,b2=15e6,sneg=0.5),True),
 "Published run rate without true-up (points 9–10)":(dict(family="threshold",type="known",share=0.5,basis="cash flow",deficit="accumulates"),False),
 "True-up, prelim. run rate $37.7M":(dict(TU,prov_rate_annual=37.7e6),False),
 "True-up, prelim. run rate $41.0M":(dict(TU,prov_rate_annual=41e6),False),
 "True-up, prelim. run rate $43.8M (EGG base)":(dict(TU),False),
 "True-up, prelim. run rate $46.4M":(dict(TU,prov_rate_annual=46.4e6),False),
 "True-up, prelim. run rate = latest published":(dict(TU,prov_basis="known"),False),
 "True-up $43.8M, final share 75%":(dict(TU,full_share=0.75),False),
 "True-up $43.8M, final share 50%":(dict(TU,full_share=0.5),False),
 "True-up $43.8M, prelim. 100%, 90-day floor":(dict(TU,prov_share=1.0,deficit="floor",ndays=90),False),
 "True-up $43.8M, expenses −20% (cut is real)":(dict(TU,mult=0.8),False),
 "True-up $43.8M, expenses −20% in run rate, but no actual cut":(dict(TU,mult=0.8,cuts_real="no"),False),
}
