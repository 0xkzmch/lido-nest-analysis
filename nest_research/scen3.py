"""Three starting scenarios for NEST rules (from point 1-4):
V1 actual budget, NEST-visible revenue; V2 + launch compensation; V3 + rebates since activation, CSM rebate added to NEST revenue.
CSM rebate is real DAO income, so it always enters DAO profit (via x_ti), and enters NEST revenue only in V3."""
import json, csv
from datetime import date, timedelta
from gengine import forward_days, history_days
B_ACT=-542451.22; B_COMP=B_ACT+147658; B_FULL=B_COMP+87208
START=date(2026,10,1)
REB_AMT=34.26
REB_DATES=[date(2026,9,28)+timedelta(days=28*k) for k in range(1,40)]
_px={r['date']:float(r['eth_usd']) for r in csv.DictReader(open('base/treasury_fee_inflows.csv'))}
_inc=json.load(open('base/agent_incoming_steth.json'))
HIST_REB={date.fromisoformat(str(x['ts'])[:10]):int(x['raw'])/1e18 for x in _inc if x['from'].lower()=="0xd99cc66fec647e68294c6477b40fc7e0f6f618d0"}
def fwd(eth, variant, ldo=None, start=START):
    d=forward_days(eth, ldo or [0.4197]*len(eth), start=start)
    rd=set(REB_DATES)
    for x in d:
        if x['d'] in rd:
            usd=REB_AMT*x['eth']
            if variant==3:
                # rebate is NEST-visible revenue; count it exactly once in DAO profit (rev part is haircut by cost of revenue, top up via x_ti)
                x['rev']+=usd; x['x_ti']+=usd*x['cor']
            else:
                x['x_ti']+=usd
    return d
def hist(variant, start=date(2025,1,1), end=date(2026,9,28)):
    d=history_days(start=start,end=end)
    for x in d:
        st=HIST_REB.get(x['d'])
        if st:
            usd=st*x['eth']
            if variant==3: x['rev']+=usd; x['x_ti']+=usd*x['cor']
            else: x['x_ti']+=usd
    return d
START_BUDGET={1:B_ACT,2:B_COMP,3:B_FULL}
