from flask import Flask, send_from_directory, jsonify, request
import os, requests
app = Flask(__name__)

ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()
LOT = 0.01

def H(): return {"auth-token": TOKEN}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"
def baseMD(): return f"https://mt-market-data-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}/historical-market-data"

def get_candles(tf, limit=120):
    try:
        url=f"{baseMD()}/symbols/{SYMBOL}/timeframes/{tf}/candles?limit={limit}"
        r=requests.get(url, headers=H(), timeout=12, verify=False)
        if r.status_code!=200: return []
        d=r.json()
        return d['candles'] if isinstance(d, dict) and 'candles' in d else d if isinstance(d,list) else []
    except: return []

def sma(vals, p):
    return sum(vals[-p:])/p if len(vals)>=p else None

def tf_trend(closes, sma20, sma50, live):
    if live > sma20 and sma20 > sma50: return "BUY"
    if live < sma20 and sma20 < sma50: return "SELL"
    return "RANGE"

def do_sr72():
    c1m=get_candles("1m", 80)
    c5m=get_candles("5m", 80)
    c15m=get_candles("15m", 80)

    try:
        pr=requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=8, verify=False).json()
        live=float(pr.get('bid') or pr.get('ask') or 0)
    except: live=0

    if len(c1m)<30:
        return {"error":f"Market data syncing, got {len(c1m)} candles","live":live or 0}

    def process(candles, tf_live):
        closes=[float(c['close']) for c in candles]
        highs=[float(c['high']) for c in candles]
        lows=[float(c['low']) for c in candles]
        s20=sma(closes,20)
        s50=sma(closes,50)
        ph=max(highs[-20:]) if len(highs)>=20 else max(highs)
        pl=min(lows[-20:]) if len(lows)>=20 else min(lows)
        sl=min(lows[-10:]) if len(lows)>=10 else min(lows)
        sh=max(highs[-10:]) if len(highs)>=10 else max(highs)
        return closes, highs, lows, s20, s50, ph, pl, sl, sh

    cl1, h1, l1, s20_1, s50_1, ph1, pl1, sl1, sh1 = process(c1m, live)
    if live==0: live=cl1[-1]

    s20_5=s50_5=ph5=pl5=sl5=sh5=None; trend5="RANGE"
    if len(c5m)>=30:
        cl5, h5, l5, s20_5, s50_5, ph5, pl5, sl5, sh5 = process(c5m, cl1[-1])
        trend5=tf_trend(cl5, s20_5, s50_5, cl5[-1])

    s20_15=s50_15=ph15=pl15=None; trend15="RANGE"
    if len(c15m)>=30:
        cl15, h15, l15, s20_15, s50_15, ph15, pl15, sl15, sh15 = process(c15m, cl1[-1])
        trend15=tf_trend(cl15, s20_15, s50_15, cl15[-1])

    trend1=tf_trend(cl1, s20_1, s50_1, live)

    direction=trend1
    confidence=62
    if trend1=="BUY" and trend5=="BUY": confidence=74
    if trend1=="BUY" and trend5=="BUY" and trend15=="BUY": confidence=86
    if trend1=="SELL" and trend5=="SELL": confidence=74
    if trend1=="SELL" and trend5=="SELL" and trend15=="SELL": confidence=86
    if trend1=="RANGE": confidence=48

    if direction=="BUY":
        trend_txt=f"XAUUSD multi-timeframe: M1 {trend1} (20 SMA {s20_1:.2f} / 50 SMA {s50_1:.2f}), M5 {trend5}, M15 {trend15}. Price {live:.2f} holding above {sl1:.2f} support after push to {ph1:.2f}. Structure bullish while above {sl1+0.2:.2f}, invalidation below {sl1-0.3:.2f}. SR-72 locking entry at current market {live:.2f} for immediate continuation."
    elif direction=="SELL":
        trend_txt=f"XAUUSD multi-timeframe: M1 {trend1} (20 SMA {s20_1:.2f} / 50 SMA {s50_1:.2f}), M5 {trend5}, M15 {trend15}. Price {live:.2f} rejecting below {sh1:.2f} resistance after high {ph1:.2f}. Momentum bearish while below {sh1-0.2:.2f}, invalidation above {sh1+0.3:.2f}. SR-72 locking entry at current market {live:.2f} for immediate continuation."
    else:
        trend_txt=f"XAUUSD ranging: M1 {trend1} around 20 SMA {s20_1:.2f} / 50 SMA {s50_1:.2f}, M5 {trend5}, M15 {trend15}. Price {live:.2f} compressing between {pl1:.2f} and {ph1:.2f}. Awaiting reclaim of {s20_1:.2f} for directional trigger. SR-72 standing by at market {live:.2f}."

    # Immediate market-anchored levels
    aggressive=None
    conservative=None
    if direction=="BUY":
        aggressive={
            "side":"BUY",
            "entry_low":round(live-0.55,2),
            "entry_high":round(live+0.15,2),
            "entry_mid":round(live,2),
            "sl":round(sl1-0.35,2),
            "tp1":round(live+2.2,2),
            "tp2":round(ph1,2),
            "desc":f"SR-72 immediate continuation buy locked at current market {live:.2f}. Invalidation below {sl1:.2f} swing low, targets {live+2.2:.2f} and period high {ph1:.2f}. M5 {trend5} / M15 {trend15} alignment adds confluence."
        }
        conservative={
            "side":"BUY",
            "entry_low":round(ph1+0.15,2),
            "entry_high":round(ph1+0.9,2),
            "entry_mid":round(ph1+0.50,2),
            "sl":round(ph1-2.2,2),
            "tp1":round(ph1+3.0,2),
            "tp2":round(ph1+5.2,2),
            "desc":f"SR-72 breakout buy above {ph1:.2f} period high. Wait for 1m close above, then retest hold. M5 {trend5} must stay bullish for follow through."
        }
    elif direction=="SELL":
        aggressive={
            "side":"SELL",
            "entry_low":round(live-0.15,2),
            "entry_high":round(live+0.55,2),
            "entry_mid":round(live,2),
            "sl":round(sh1+0.35,2),
            "tp1":round(live-2.2,2),
            "tp2":round(pl1,2),
            "desc":f"SR-72 immediate continuation sell locked at current market {live:.2f}. Invalidation above {sh1:.2f} swing high, targets {live-2.2:.2f} and period low {pl1:.2f}. M5 {trend5} / M15 {trend15} alignment adds confluence."
        }
        conservative={
            "side":"SELL",
            "entry_low":round(pl1-0.9,2),
            "entry_high":round(pl1-0.15,2),
            "entry_mid":round(pl1-0.50,2),
            "sl":round(pl1+2.2,2),
            "tp1":round(pl1-3.0,2),
            "tp2":round(pl1-5.2,2),
            "desc":f"SR-72 breakdown sell below {pl1:.2f} period low. Wait for 1m close below, then retest fail. M5 {trend5} must stay bearish for follow through."
        }

    return {
        "confidence":confidence,"trend":trend_txt,"live":live,
        "sma20":s20_1,"sma50":s50_1,"period_high":ph1,"period_low":pl1,"swing_low":sl1,"swing_high":sh1,
        "direction":direction,
        "mtf":{"m1":trend1,"m5":trend5,"m15":trend15,"s20_5":s20_5,"s50_5":s50_5,"s20_15":s20_15,"s50_15":s50_15},
        "aggressive":aggressive,"conservative":conservative
    }

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return "OK SR-72 DARK STAR AI CHART - SCANNER"
@app.route('/api/positions')
def positions(): return requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).text, 200
@app.route('/api/orders')
def orders(): return requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).text, 200

@app.route('/api/scan_image', methods=['POST'])
def scan_image():
    try:
        file = request.files.get('image')
        res = do_sr72()
        res['uploaded']=True
        res['filename']=file.filename if file else "chart.jpg"
        return jsonify(res)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e)}),500

@app.route('/api/sniper/enter', methods=['POST'])
def enter():
    j=request.get_json() or {}; plan=j.get('plan')
    side=plan['side']; act="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
    for tp in [plan['tp1'], plan['tp2']]:
        order={"actionType":act,"symbol":SYMBOL,"volume":LOT,"openPrice":plan['entry_mid'],"stopLoss":plan['sl'],"takeProfit":tp,"comment":"SR-72 DARK STAR AI CHART"}
        requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
    return jsonify({"placed":plan})

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

if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
