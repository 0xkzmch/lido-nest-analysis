import json, urllib.request, time, os, sys
RPC="https://eth.drpc.org"
ETHUSD="0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
STETHETH="0x86392dC19c0b719886221c78AB11eb8Cf5c52812"
SEL="0xfeaf968c"
def call(to,b):
    p={"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":to,"data":SEL},hex(b)]}
    for a in range(3):
        try:
            r=json.loads(urllib.request.urlopen(urllib.request.Request(RPC,json.dumps(p).encode(),{"Content-Type":"application/json","User-Agent":"curl/8"}),timeout=15).read())
            return r.get('result')
        except Exception: time.sleep(1)
def ans(h,dec):
    if not h or len(h)<130: return None
    v=int(h[66:130],16); return v/10**dec
if not os.path.exists('inflows_state.json'):
    mints=json.load(open('agent_mints.json'))
    dist=[r for r in json.load(open('dist_transfers.json')) if r['to']=="0x3e40d73eb977dc6a537af587d48316fee66e9c8c"]
    ev=[{"ts":m['ts'],"block":m['block'],"steth":m['steth'],"src":"mint"} for m in mints]+[{"ts":d['ts'],"block":d['block'],"steth":d['steth'],"src":"distributor"} for d in dist]
    ev.sort(key=lambda e:e['block'])
else:
    ev=json.load(open('inflows_state.json'))
t0=time.time(); done=0
for e in ev:
    if e.get('eth_usd') is not None: continue
    if time.time()-t0>240: break
    e['eth_usd']=ans(call(ETHUSD,e['block']),8)
    e['steth_eth']=ans(call(STETHETH,e['block']),18)
    done+=1
json.dump(ev,open('inflows_state.json','w'))
left=sum(1 for e in ev if e.get('eth_usd') is None)
print("priced this run:",done,"| remaining:",left,"| total:",len(ev))
