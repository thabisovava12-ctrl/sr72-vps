from flask import Flask, send_from_directory, jsonify, request
import os, requests, threading, time
from datetime import datetime, timezone
app = Flask(__name__)

ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()
LOT = 0.01
BOT_ACTIVE = False

def H(): return {"auth-token": TOKEN}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"
def baseMD(): return f"https://mt-market-data-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}/historical-market-data"

def get_candles(tf, limit=200):
    try:
        url = f"{baseMD()}/symbols/{SYMBOL}/timeframes/{tf}/candles?limit={limit}"
        r = requests.get(url, headers=H(), timeout=20, verify=False)
        if r.status_code!=200: return []
        data = r.json()
        if isinstance(data, dict) and 'candles' in data: return data['candles']
        if isinstance(data, list): return data
        return []
    except: return []

def parse_time(t):
    try:
        if isinstance(t, (int,float)): return datetime.fromtimestamp(t, tz=timezone.utc)
        if isinstance(t, str): return datetime.fromisoformat(t.replace('Z','+00:00'))
    except: return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)

def ema(values, period):
    if len(values) < period: return None
    k = 2/(period+1)
    ema_val = sum(values[:period])/period
    for v in values[period:]:
        ema_val = float(v)*k + ema_val*(1-k)
    return float(ema_val)

def do_sniper_logic():
    c1h = get_candles("1h", 250)
    closes1h = [float(c['close']) for c in c1h if 'close' in c]
    ema200 = ema(closes1h, 200) if len(closes1h)>=200 else None
    last_close = closes1h[-1] if closes1h else 0
    trend = "BUY" if ema200 and last_close > ema200 else "SELL" if ema200 else "BUY"

    c1d = get_candles("1d", 5)
    prev_high = float(c1d[-2]['high']) if len(c1d)>=2 else last_close+10
    prev_low = float(c1d[-2]['low']) if len(c1d)>=2 else last_close-10

    c15m = get_candles("15m", 96)
    london = [c for c in c15m if 8 <= parse_time(c.get('time')).hour <= 17]
    ny = [c for c in c15m if 13 <= parse_time(c.get('time')).hour <= 22]
    london_high = max([float(c['high']) for c in london]) if london else prev_high
    london_low = min([float(c['low']) for c in london]) if london else prev_low
    ny_high = max([float(c['high']) for c in ny]) if ny else prev_high
    ny_low = min([float(c['low']) for c in ny]) if ny else prev_low
    swing_high = max([float(c['high']) for c in c15m[-20:]]) if c15m else prev_high
    swing_low = min([float(c['low']) for c in c15m[-20:]]) if c15m else prev_low

    c5m = get_candles("5m", 100)
    sweep = "NONE"; sweep_level = None
    if c5m:
        last = c5m[-1]
        lh, lc, ll = float(last['high']), float(last['close']), float(last['low'])
        for lvl in [prev_high, london_high, ny_high, swing_high]:
            lvl=float(lvl)
            if lh > lvl and lc < lvl:
                sweep=f"SELL SWEEP ABOVE {lvl:.2f}"; sweep_level=lvl; break
        if not sweep_level:
            for lvl in [prev_low, london_low, ny_low, swing_low]:
                lvl=float(lvl)
                if ll < lvl and lc > lvl:
                    sweep=f"BUY SWEEP BELOW {lvl:.2f}"; sweep_level=lvl; break

    bos="WAITING"
    if len(c5m)>=10:
        recent_high=max(float(c['high']) for c in c5m[-20:-1])
        recent_low=min(float(c['low']) for c in c5m[-20:-1])
        if float(c5m[-1]['close'])>recent_high: bos=f"BULLISH BOS above {recent_high:.2f}"
        elif float(c5m[-1]['close'])<recent_low: bos=f"BEARISH BOS below {recent_low:.2f}"

    setup="NO SETUP"; entry=None; sl=None; tp=None
    if sweep_level and "BUY SWEEP" in sweep and "BULLISH" in bos and trend=="BUY":
        setup="BUY: HTF BUY + SWEEP + BOS + RETEST"; entry=round(sweep_level+0.30,2); sl=round(float(c5m[-1]['low'])-0.80,2); risk=entry-sl; tp=round(entry+risk*2,2) if risk>0 else round(entry+1.6,2)
    elif sweep_level and "SELL SWEEP" in sweep and "BEARISH" in bos and trend=="SELL":
        setup="SELL: HTF SELL + SWEEP + BOS + RETEST"; entry=round(sweep_level-0.30,2); sl=round(float(c5m[-1]['high'])+0.80,2); risk=sl-entry; tp=round(entry-risk*2,2) if risk>0 else round(entry-1.6,2)
    else:
        if trend in ["BUY","SELL"]: setup=f"WAITING SWEEP+BOS | Trend {trend} ready"

    return {"trend":trend,"ema200":ema200,"last_close":last_close,"levels":{"pdh":prev_high,"pdl":prev_low,"lh":london_high,"ll":london_low,"nh":ny_high,"nl":ny_low,"s15h":swing_high,"s15l":swing_low},"sweep":sweep,"sweep_level":sweep_level,"bos":bos,"setup":setup,"entry":entry,"sl":sl,"tp":tp}

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return f"OK V40.3 MERGED BOT={BOT_ACTIVE}"
@app.route('/api/balance')
def bal(): return requests.get(f"{base()}/accountInformation", headers=H(), timeout=15, verify=False).text, 200
@app.route('/api/price')
def price(): return requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).text, 200
@app.route('/api/positions')
def positions(): return requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).text, 200
@app.route('/api/orders')
def orders(): return requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).text, 200

@app.route('/api/sniper/scan')
def sniper_scan():
    try:
        res=do_sniper_logic(); res["bot_active"]=BOT_ACTIVE; return jsonify(res)
    except Exception as e: return jsonify({"error":str(e),"trend":"--","levels":{"pdh":0,"pdl":0,"lh":0,"ll":0,"nh":0,"nl":0,"s15h":0,"s15l":0},"sweep":"ERR","bos":"ERR","setup":str(e)}),500

@app.route('/api/sniper/bot', methods=['GET','POST'])
def sniper_bot():
    global BOT_ACTIVE
    if request.method=='POST':
        data=request.get_json() or {}; action=data.get('action','start')
        if action=='start':
            BOT_ACTIVE=True
            try:
                res=do_sniper_logic()
                if res['entry']:
                    pos=requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
                    ords=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
                    if len([x for x in pos if x.get('symbol')==SYMBOL])==0 and len([x for x in ords if x.get('symbol')==SYMBOL])==0:
                        side=res['trend']; act="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
                        order={"actionType":act,"symbol":SYMBOL,"volume":LOT,"openPrice":res['entry'],"stopLoss":res['sl'],"takeProfit":res['tp'],"comment":"IMMEDIATE ON START"}
                        requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
            except Exception as e: print(f"immediate err {e}")
        else: BOT_ACTIVE=False
    return jsonify({"bot_active":BOT_ACTIVE})

@app.route('/api/sniper/enter', methods=['POST'])
def sniper_enter():
    j=request.get_json() or {}; side=j.get('side','BUY'); entry=float(j.get('entry')); sl=float(j.get('sl')); tp=float(j.get('tp'))
    action="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
    order={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":entry,"stopLoss":sl,"takeProfit":tp,"comment":"Sniper V40.3"}
    r=requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
    return jsonify({"placed":order,"resp":r.text[:800]})

@app.route('/api/close_all', methods=['POST'])
def close_all():
    try:
        o=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
        for od in o:
            if od.get('symbol')==SYMBOL: requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json={"actionType":"ORDER_TYPE_CANCEL","orderId":od['id']}, timeout=10, verify=False)
    except: pass
    try:
        p=requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
        for pos in p:
            if pos.get('symbol')!=SYMBOL: continue
            side="SELL" if pos['type']=='POSITION_TYPE_BUY' else "BUY"
            requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json={"actionType":f"ORDER_TYPE_{side}","symbol":pos['symbol'],"volume":pos['volume'],"positionId":pos['id']}, timeout=10, verify=False)
    except: pass
    return jsonify({"closed":True})

def bot_loop():
    global BOT_ACTIVE
    while True:
        try:
            if BOT_ACTIVE:
                res=do_sniper_logic()
                if res['entry'] and res['sl'] and res['tp']:
                    pos=requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
                    ords=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
                    if len([x for x in pos if x.get('symbol')==SYMBOL])==0 and len([x for x in ords if x.get('symbol')==SYMBOL])==0:
                        side=res['trend']; action="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
                        order={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":res['entry'],"stopLoss":res['sl'],"takeProfit":res['tp'],"comment":"AUTO Sniper IMMEDIATE"}
                        requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
        except: pass
        time.sleep(10)

threading.Thread(target=bot_loop, daemon=True).start()
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
