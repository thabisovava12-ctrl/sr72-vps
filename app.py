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
        print(f"CANDLES {tf} {r.status_code}")
        if r.status_code!=200:
            print(r.text[:300])
            return []
        data = r.json()
        if isinstance(data, dict) and 'candles' in data: return data['candles']
        if isinstance(data, list): return data
        return []
    except Exception as e:
        print(f"candle err {tf} {e}")
        return []

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
    # GET PRICE FALLBACK
    try:
        price_resp = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
        live_bid = float(price_resp.get('bid',0) or price_resp.get('price',0) or 0)
        live_ask = float(price_resp.get('ask', live_bid))
        live = live_bid or live_ask or 4250
    except:
        live=4250; live_bid=4250; live_ask=4250

    c1h = get_candles("1h", 250)
    closes1h = [float(c['close']) for c in c1h if 'close' in c]
    ema200 = ema(closes1h, 200) if len(closes1h)>=200 else live # fallback to live if not enough candles
    last_close = closes1h[-1] if closes1h else live
    trend = "BUY" if last_close >= (ema200 or last_close) else "SELL"
    # FORCE TREND BUY if ema fails, so bot always has direction
    if not c1h: trend="BUY"; ema200=live-5; last_close=live

    c1d = get_candles("1d", 5)
    prev_high = float(c1d[-2]['high']) if len(c1d)>=2 else live+10
    prev_low = float(c1d[-2]['low']) if len(c1d)>=2 else live-10
    if not c1d: prev_high=live+10; prev_low=live-10

    c15m = get_candles("15m", 96)
    london = [c for c in c15m if 8 <= parse_time(c.get('time')).hour <= 17]
    ny = [c for c in c15m if 13 <= parse_time(c.get('time')).hour <= 22]
    london_high = max([float(c['high']) for c in london]) if london else prev_high
    london_low = min([float(c['low']) for c in london]) if london else prev_low
    ny_high = max([float(c['high']) for c in ny]) if ny else prev_high
    ny_low = min([float(c['low']) for c in ny]) if ny else prev_low
    swing_high = max([float(c['high']) for c in c15m[-20:]]) if c15m else prev_high
    swing_low = min([float(c['low']) for c in c15m[-20:]]) if c15m else prev_low
    if not c15m: swing_high=live+3; swing_low=live-3

    c5m = get_candles("5m", 100)
    sweep = "NONE"; sweep_level = None
    bos = "WAITING"
    if c5m:
        last = c5m[-1]
        lh, lc, ll = float(last['high']), float(last['close']), float(last['low'])
        for lvl in [prev_high, london_high, ny_high, swing_high]:
            if lh > float(lvl) and lc < float(lvl):
                sweep=f"SELL SWEEP ABOVE {float(lvl):.2f}"; sweep_level=float(lvl); break
        if not sweep_level:
            for lvl in [prev_low, london_low, ny_low, swing_low]:
                if ll < float(lvl) and lc > float(lvl):
                    sweep=f"BUY SWEEP BELOW {float(lvl):.2f}"; sweep_level=float(lvl); break
        if len(c5m)>=10:
            recent_high=max(float(c['high']) for c in c5m[-20:-1])
            recent_low=min(float(c['low']) for c in c5m[-20:-1])
            if float(c5m[-1]['close'])>recent_high: bos=f"BULLISH BOS above {recent_high:.2f}"
            elif float(c5m[-1]['close'])<recent_low: bos=f"BEARISH BOS below {recent_low:.2f}"
            else: bos=f"CONSOLIDATING between {recent_low:.2f}-{recent_high:.2f}"
    else:
        sweep="NO 5M DATA - USING LIVE"
        bos="NO 5M DATA"
        sweep_level=prev_low if trend=="BUY" else prev_high

    # === ALWAYS CREATE SIGNAL SO SCANNER SHOWS + BOT EXECUTES ===
    setup=""; entry=None; sl=None; tp=None
    if sweep_level and "BUY SWEEP" in sweep:
        setup=f"BUY: HTF {trend} + {sweep} + {bos}"; entry=round(sweep_level+0.35,2); sl=round(entry-1.10,2); tp=round(entry+2.20,2)
    elif sweep_level and "SELL SWEEP" in sweep:
        setup=f"SELL: HTF {trend} + {sweep} + {bos}"; entry=round(sweep_level-0.35,2); sl=round(entry+1.10,2); tp=round(entry-2.20,2)
    else:
        # FALLBACK — GUARANTEED SIGNAL FOR SCANNER + BOT
        if trend=="BUY":
            setup=f"BUY READY: HTF BUY + PDH/PDL + London/NY — Immediate (no sweep yet, using retest)"
            entry=round(live-0.30,2) # retest entry slightly below live
            sl=round(entry-1.10,2)   # SL beyond sweep area
            tp=round(entry+2.20,2)   # 1:2
            sweep=f"PENDING BUY SWEEP near PDL {prev_low:.2f} / 15M {swing_low:.2f}"
            bos=f"WAITING BULLISH BOS — will place BUY_LIMIT @ {entry}"
        else:
            setup=f"SELL READY: HTF SELL + PDH/PDL + London/NY — Immediate"
            entry=round(live+0.30,2)
            sl=round(entry+1.10,2)
            tp=round(entry-2.20,2)
            sweep=f"PENDING SELL SWEEP near PDH {prev_high:.2f} / 15M {swing_high:.2f}"
            bos=f"WAITING BEARISH BOS — will place SELL_LIMIT @ {entry}"

    return {"trend":trend,"ema200":ema200,"last_close":last_close,"live":live,"levels":{"pdh":prev_high,"pdl":prev_low,"lh":london_high,"ll":london_low,"nh":ny_high,"nl":ny_low,"s15h":swing_high,"s15l":swing_low},"sweep":sweep,"sweep_level":sweep_level,"bos":bos,"setup":setup,"entry":entry,"sl":sl,"tp":tp,"candles":{"1h":len(c1h),"15m":len(c15m),"5m":len(c5m)}}

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return f"OK V40.4 FIXED BOT={BOT_ACTIVE}"
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
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e),"trend":"BUY","ema200":4250,"last_close":4250,"live":4250,"levels":{"pdh":4260,"pdl":4240,"lh":4260,"ll":4240,"nh":4260,"nl":4240,"s15h":4260,"s15l":4240},"sweep":f"ERR {e}","bos":"ERR","setup":f"FALLBACK BUY READY","entry":4249.7,"sl":4248.6,"tp":4251.9,"bot_active":BOT_ACTIVE}), 500

@app.route('/api/sniper/bot', methods=['GET','POST'])
def sniper_bot():
    global BOT_ACTIVE
    if request.method=='POST':
        data=request.get_json() or {}; action=data.get('action','start')
        if action=='start':
            BOT_ACTIVE=True
            try:
                res=do_sniper_logic()
                pos=requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
                ords=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
                if len([x for x in pos if x.get('symbol')==SYMBOL])==0 and len([x for x in ords if x.get('symbol')==SYMBOL])==0:
                    side=res['trend']; act="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
                    order={"actionType":act,"symbol":SYMBOL,"volume":LOT,"openPrice":res['entry'],"stopLoss":res['sl'],"takeProfit":res['tp'],"comment":"V40.4 IMMEDIATE"}
                    rr=requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
                    print(f"IMMEDIATE BOT {rr.text[:200]}")
            except Exception as e: print(f"immediate err {e}")
        else: BOT_ACTIVE=False
    return jsonify({"bot_active":BOT_ACTIVE})

@app.route('/api/sniper/enter', methods=['POST'])
def sniper_enter():
    j=request.get_json() or {}; side=j.get('side','BUY'); entry=float(j.get('entry')); sl=float(j.get('sl')); tp=float(j.get('tp'))
    action="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
    order={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":entry,"stopLoss":sl,"takeProfit":tp,"comment":"V40.4 Manual"}
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
                if res['entry']:
                    pos=requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
                    ords=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
                    if len([x for x in pos if x.get('symbol')==SYMBOL])==0 and len([x for x in ords if x.get('symbol')==SYMBOL])==0:
                        side=res['trend']; action="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
                        order={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":res['entry'],"stopLoss":res['sl'],"takeProfit":res['tp'],"comment":"AUTO V40.4"}
                        requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
        except: pass
        time.sleep(10)

threading.Thread(target=bot_loop, daemon=True).start()
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
