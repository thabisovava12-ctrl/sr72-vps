from flask import Flask, send_from_directory, jsonify, request
import os, requests
app = Flask(__name__)

ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
DEFAULT_SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()
LOT = 0.01

def H(): return {"auth-token": TOKEN}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"
def baseMD(): return f"https://mt-market-data-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}/historical-market-data"

def get_candles_try(symbol, tf, limit=80):
    try:
        url=f"{baseMD()}/symbols/{symbol}/timeframes/{tf}/candles?limit={limit}"
        r=requests.get(url, headers=H(), timeout=12, verify=False)
        if r.status_code!=200: return []
        d=r.json()
        return d['candles'] if isinstance(d, dict) and 'candles' in d else d if isinstance(d,list) else []
    except: return []

def sma(vals, p): return sum(vals[-p:])/p if len(vals)>=p else None

def tf_trend(closes, s20, s50, live):
    if s20 is None or s50 is None: return "RANGE"
    if live > s20 and s20 > s50: return "BUY"
    if live < s20 and s20 < s50: return "SELL"
    return "RANGE"

def do_sr72(requested_symbol):
    req = requested_symbol.strip()
    if not req: req = DEFAULT_SYMBOL

    # Build variants ONLY for same asset, not cross-asset
    base = req.replace('c','').replace('C','').upper()
    # special maps for brokers that use different names
    alias_map = {
        "US30C": ["US30", "US30c", "DJ30", "DJ30c", "WS30", "WS30c", "US30.c"],
        "NAS100C": ["NAS100", "NAS100c", "USTEC", "USTECc", "US100", "NAS100.c"],
        "GER40C": ["GER40", "GER40c", "DE40", "DE40c", "GER40.c"],
        "US500C": ["US500", "US500c", "SPX500", "SPX500c"],
        "BTCUSDC": ["BTCUSD", "BTCUSDc", "BTCUSD.c", "BTCUSDm"],
        "ETHUSDC": ["ETHUSD", "ETHUSDc"],
        "XAUUSDC": ["XAUUSDc", "XAUUSD", "GOLD", "XAUUSD.c"],
    }
    key = base + "C"
    candidates = [req, base+'c', base, base.lower()+'c']
    if key in alias_map:
        candidates += alias_map[key]
    # dedupe
    seen=set(); uniq=[]
    for c in candidates:
        if c not in seen and c:
            uniq.append(c); seen.add(c)

    real_symbol=None; c1m=[]
    for sym in uniq:
        tmp=get_candles_try(sym, "1m", 80)
        if len(tmp)>=20:
            real_symbol=sym
            c1m=tmp
            break

    if not real_symbol or len(c1m)<20:
        return {"error":f"❌ {req} NOT FOUND on your broker. Tried {', '.join(uniq)}. Got {len(c1m)} candles. Open /api/symbols to see your broker list. For indices try US30, NAS100, GER40, USTEC, DJ30.","live":0,"symbol":req,"requested":req}

    c5m=get_candles_try(real_symbol, "5m", 80)
    c15m=get_candles_try(real_symbol, "15m", 80)

    try:
        pr=requests.get(f"{base()}/symbols/{real_symbol}/current-price", headers=H(), timeout=8, verify=False).json()
        live=float(pr.get('bid') or pr.get('ask') or 0)
    except: live=0

    def proc(candles):
        closes=[float(c['close']) for c in candles]; highs=[float(c['high']) for c in candles]; lows=[float(c['low']) for c in candles]
        s20=sma(closes,20); s50=sma(closes,50)
        ph=max(highs[-20:]); pl=min(lows[-20:]); sl=min(lows[-10:]); sh=max(highs[-10:])
        return closes, highs, lows, s20, s50, ph, pl, sl, sh

    cl1, h1, l1, s20_1, s50_1, ph1, pl1, sl1, sh1 = proc(c1m)
    if live==0: live=cl1[-1]

    trend5="RANGE"; s20_5=s50_5=None
    if len(c5m)>=20:
        cl5, h5, l5, s20_5, s50_5, ph5, pl5, sl5, sh5 = proc(c5m)
        trend5=tf_trend(cl5, s20_5, s50_5, cl5[-1])
    trend15="RANGE"
    if len(c15m)>=20:
        cl15, h15, l15, s20_15, s50_15, ph15, pl15, sl15, sh15 = proc(c15m)
        trend15=tf_trend(cl15, s20_15, s50_15, cl15[-1])

    trend1=tf_trend(cl1, s20_1, s50_1, live)
    direction=trend1; confidence=62
    if trend1=="BUY" and trend5=="BUY": confidence=74
    if trend1=="BUY" and trend5=="BUY" and trend15=="BUY": confidence=86
    if trend1=="SELL" and trend5=="SELL": confidence=74
    if trend1=="SELL" and trend5=="SELL" and trend15=="SELL": confidence=86
    if trend1=="RANGE": confidence=48

    dec=2 if any(x in real_symbol.upper() for x in ["XAU","XAG","OIL","US30","NAS","GER","DE40","USTEC","US500","SPX","DJ","WS30","BTC","ETH","UK100"]) else 5
    vol=abs(s20_1-s50_1) if s20_1 and s50_1 else 0.5
    step=max(0.00015, vol*0.15)
    if dec==2: step=max(0.5, step)

    def rnd(v): return round(v, dec)

    aggressive=None; conservative=None
    if direction=="BUY":
        aggressive={"side":"BUY","symbol":real_symbol,"entry_low":rnd(live-step*1.2),"entry_high":rnd(live+step*0.4),"entry_mid":rnd(live),"sl":rnd(sl1-step*0.8),"tp1":rnd(live+step*5),"tp2":rnd(ph1),"desc":f"SR-72 BUY @ {live:.{dec}f} on {real_symbol} M5 {trend5} M15 {trend15}"}
        conservative={"side":"BUY","symbol":real_symbol,"entry_low":rnd(ph1+step*0.3),"entry_high":rnd(ph1+step*2),"entry_mid":rnd(ph1+step*1),"sl":rnd(ph1-step*5),"tp1":rnd(ph1+step*7),"tp2":rnd(ph1+step*12),"desc":f"Breakout BUY above {ph1:.{dec}f}"}
    elif direction=="SELL":
        aggressive={"side":"SELL","symbol":real_symbol,"entry_low":rnd(live-step*0.4),"entry_high":rnd(live+step*1.2),"entry_mid":rnd(live),"sl":rnd(sh1+step*0.8),"tp1":rnd(live-step*5),"tp2":rnd(pl1),"desc":f"SR-72 SELL @ {live:.{dec}f} on {real_symbol} M5 {trend5} M15 {trend15}"}
        conservative={"side":"SELL","symbol":real_symbol,"entry_low":rnd(pl1-step*2),"entry_high":rnd(pl1-step*0.3),"entry_mid":rnd(pl1-step*1),"sl":rnd(pl1+step*5),"tp1":rnd(pl1-step*7),"tp2":rnd(pl1-step*12),"desc":f"Breakdown SELL below {pl1:.{dec}f}"}

    trend_txt=f"{real_symbol} MTF M1 {trend1} M5 {trend5} M15 {trend15} Price {live:.{dec}f} SMA20 {s20_1:.{dec}f} SMA50 {s50_1:.{dec}f} [broker: {real_symbol} / requested: {req}] Locked at market {live:.{dec}f}"

    return {"confidence":confidence,"trend":trend_txt,"live":live,"symbol":real_symbol,"requested":req,"dec":dec,"sma20":s20_1,"sma50":s50_1,"period_high":ph1,"period_low":pl1,"swing_low":sl1,"swing_high":sh1,"direction":direction,"mtf":{"m1":trend1,"m5":trend5,"m15":trend15},"aggressive":aggressive,"conservative":conservative}

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return "OK SR-72 DARK STAR AI CHART - MERGED UNIVERSAL AUTO"
@app.route('/api/positions')
def positions(): return requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).text, 200
@app.route('/api/orders')
def orders(): return requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).text, 200
@app.route('/api/symbols')
def list_symbols():
    try:
        r=requests.get(f"{base()}/symbols", headers=H(), timeout=15, verify=False)
        return r.text, r.status_code, {'Content-Type':'application/json'}
    except Exception as e:
        return jsonify({"error":str(e)}),500
@app.route('/api/price')
def price():
    sym=request.args.get('symbol', DEFAULT_SYMBOL)
    return requests.get(f"{base()}/symbols/{sym}/current-price", headers=H(), timeout=10, verify=False).text, 200
@app.route('/api/scan_image', methods=['POST'])
def scan_image():
    try:
        raw=(request.form.get('symbol') or DEFAULT_SYMBOL).strip()
        file=request.files.get('image')
        res=do_sr72(raw)
        res['uploaded']=True
        res['filename']=file.filename if file else "chart.jpg"
        return jsonify(res)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e)}),500
@app.route('/api/sniper/enter', methods=['POST'])
def enter():
    j=request.get_json() or {}; plan=j.get('plan'); symbol=plan.get('symbol', DEFAULT_SYMBOL); side=plan['side']; act="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
    for tp in [plan['tp1'], plan['tp2']]:
        order={"actionType":act,"symbol":symbol,"volume":LOT,"openPrice":plan['entry_mid'],"stopLoss":plan['sl'],"takeProfit":tp,"comment":"SR-72 DARK STAR AI CHART"}
        requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
    return jsonify({"placed":plan})
@app.route('/api/close_all', methods=['POST'])
def close_all():
    j=request.get_json(silent=True) or {}; sym=j.get('symbol')
    try:
        o=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
        for od in o:
            if sym and od.get('symbol').upper()!=sym.upper() and od.get('symbol')!=sym: continue
            requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json={"actionType":"ORDER_TYPE_CANCEL","orderId":od['id']}, timeout=10, verify=False)
    except: pass
    try:
        p=requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
        for pos in p:
            if sym and pos.get('symbol').upper()!=sym.upper() and pos.get('symbol')!=sym: continue
            side="SELL" if pos['type']=='POSITION_TYPE_BUY' else "BUY"
            requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json={"actionType":f"ORDER_TYPE_{side}","symbol":pos['symbol'],"volume":pos['volume'],"positionId":pos['id']}, timeout=10, verify=False)
    except: pass
    return jsonify({"closed":True})
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
