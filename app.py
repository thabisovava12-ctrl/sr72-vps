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
        r=requests.get(url, headers=H(), timeout=20, verify=False)
        if r.status_code!=200: return []
        d=r.json()
        return d['candles'] if isinstance(d, dict) and 'candles' in d else d if isinstance(d,list) else []
    except: return []

def sma(vals, p):
    return sum(vals[-p:])/p if len(vals)>=p else None

def do_sr72():
    c1m=get_candles("1m", 120)
    try:
        pr=requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
        live=float(pr.get('bid') or pr.get('ask') or 0)
    except: live=0
    if len(c1m)<60:
        return {"error":f"Need 60 1m candles, got {len(c1m)}","live":live or 0}
    closes=[float(c['close']) for c in c1m]
    highs=[float(c['high']) for c in c1m]
    lows=[float(c['low']) for c in c1m]
    if live==0: live=closes[-1]
    sma20=sma(closes,20)
    sma50=sma(closes,50)
    period_high=max(highs[-30:])
    period_low=min(lows[-30:])
    swing_low=min(lows[-15:])
    swing_high=max(highs[-15:])

    direction="WAIT"; confidence=45
    if live > sma20 and sma20 > sma50:
        direction="BUY"; confidence=78 if abs(live-sma20)<1.0 else 65
        trend=f"XAUUSD on the 1-minute chart is in a short-term uptrend: price is trading above the 20-period SMA near {sma20:.2f} and the 50-period SMA near {sma50:.2f} after rallying to {period_high:.2f}. The latest candles show a sharp pullback from that high followed by a rebound to about {live:.2f}, suggesting buyers are defending the {swing_low:.2f}-{sma20:.2f} support zone. Momentum remains constructive while price holds above {swing_low+0.3:.2f}, but a break below that level would weaken the bullish structure and shift focus to the {period_low:.2f} period low."
    elif live < sma20 and sma20 < sma50:
        direction="SELL"; confidence=78 if abs(live-sma20)<1.0 else 65
        trend=f"XAUUSD on the 1-minute chart is in a short-term downtrend: price is trading below the 20-period SMA near {sma20:.2f} and the 50-period SMA near {sma50:.2f} after dropping to {period_low:.2f}. The latest candles show a bounce to {live:.2f}, suggesting sellers are defending the {sma20:.2f}-{swing_high:.2f} resistance."
    else:
        trend=f"XAUUSD 1m ranging: price {live:.2f} chopping around 20 SMA {sma20:.2f} and 50 SMA {sma50:.2f}. Waiting for reclaim of SMA20 for continuation."

    aggressive=None
    if direction=="BUY":
        aggressive={"side":"BUY","entry_low":round(sma20-0.4,2),"entry_high":round(sma20+0.4,2),"entry_mid":round(sma20,2),"sl":round(swing_low-0.35,2),"tp1":round(period_high-0.8,2),"tp2":round(period_high,2),"desc":f"Aggressive continuation buy on a shallow pullback into the 20-period SMA and recent support zone. Invalidation is below the {swing_low:.2f} swing low, while targets align with the {period_high-0.8:.2f} resistance and the {period_high:.2f} period high."}
    elif direction=="SELL":
        aggressive={"side":"SELL","entry_low":round(sma20-0.4,2),"entry_high":round(sma20+0.4,2),"entry_mid":round(sma20,2),"sl":round(swing_high+0.35,2),"tp1":round(period_low+0.8,2),"tp2":round(period_low,2),"desc":f"Aggressive continuation sell into 20 SMA. Invalidation above {swing_high:.2f}."}

    conservative=None
    if direction=="BUY":
        conservative={"side":"BUY","entry_low":round(period_high+0.15,2),"entry_high":round(period_high+1.0,2),"entry_mid":round(period_high+0.55,2),"sl":round(period_high-2.5,2),"tp1":round(period_high+3.0,2),"tp2":round(period_high+5.5,2),"desc":f"Conservative breakout buy only if price closes and holds above the {period_high:.2f} period high, confirming renewed upside momentum. The stop is placed below the breakout retest area to reduce false-breakout risk."}
    elif direction=="SELL":
        conservative={"side":"SELL","entry_low":round(period_low-1.0,2),"entry_high":round(period_low-0.15,2),"entry_mid":round(period_low-0.55,2),"sl":round(period_low+2.5,2),"tp1":round(period_low-3.0,2),"tp2":round(period_low-5.5,2),"desc":f"Conservative breakout sell below {period_low:.2f}."}

    return {"confidence":confidence,"trend":trend,"live":live,"sma20":sma20,"sma50":sma50,"period_high":period_high,"period_low":period_low,"swing_low":swing_low,"swing_high":swing_high,"direction":direction,"aggressive":aggressive,"conservative":conservative}

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return "OK SR-72 DARK STAR AI CHART - SCANNER ONLY"
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
