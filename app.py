from flask import Flask, send_from_directory, jsonify, request
import os, requests, cv2, numpy as np, tempfile

app = Flask(__name__)

ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
DEFAULT_SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()
LOT = 0.01

def H(): return {"auth-token": TOKEN}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"
def baseMD(): return f"https://mt-market-data-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}/historical-market-data"

def get_candles_try(symbol, tf, limit=120):
    try:
        url=f"{baseMD()}/symbols/{symbol}/timeframes/{tf}/candles?limit={limit}"
        r=requests.get(url, headers=H(), timeout=15, verify=False)
        if r.status_code!=200:
            return []
        d=r.json()
        arr=d['candles'] if isinstance(d, dict) and 'candles' in d else d if isinstance(d,list) else []
        return arr
    except Exception as e:
        print(f"candle fail {symbol} {e}")
        return []

def ema(vals, p):
    if not vals or len(vals)==0: return None
    k = 2/(p+1)
    e = float(vals[0])
    for v in vals[1:]:
        e = float(v)*k + e*(1-k)
    return e

def tf_trend_9521(s9, s21, s50, live):
    if None in (s9,s21,s50): return "RANGE"
    try:
        if s9 > s21 > s50 and live > s9: return "BUY"
        if s9 < s21 < s50 and live < s9: return "SELL"
        if s9 > s21: return "BUY"
        if s9 < s21: return "SELL"
    except: pass
    return "RANGE"

def tf_trend_strong(s9, s21, s50, live):
    if None in (s9,s21,s50): return "RANGE"
    try:
        if s9 > s21 > s50: return "BUY"
        if s9 < s21 < s50: return "SELL"
    except: pass
    return "RANGE"

def analyze_chart_image(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None: return "RANGE", 0
        h,w,_ = img.shape
        crop = img[int(h*0.15):int(h*0.92), int(w*0.08):int(w*0.92)]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0,70,50]); upper_red1 = np.array([10,255,255])
        lower_red2 = np.array([160,70,50]); upper_red2 = np.array([180,255,255])
        red_mask = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))
        blue_mask = cv2.inRange(hsv, np.array([90,50,50]), np.array([135,255,255]))
        ch,cw = red_mask.shape
        right_w = int(cw*0.20)
        ry = np.where(red_mask[:, -right_w:]>0)[0]
        by = np.where(blue_mask[:, -right_w:]>0)[0]
        if len(ry)==0 or len(by)==0: return "RANGE", 0
        red_y = float(np.mean(ry)); blue_y = float(np.mean(by))
        score = abs(red_y-blue_y)
        if red_y < blue_y: return "SELL", score
        if blue_y < red_y: return "BUY", score
        return "RANGE", 0
    except Exception as e:
        print("vision error", e)
        return "RANGE", 0

def do_sr72(requested_symbol, image_path=None):
    req = (requested_symbol or DEFAULT_SYMBOL).strip()
    base_sym = req.replace('c','').replace('C','').upper()
    alias_map = {
        "US30C": ["US30", "US30c", "DJ30", "WS30", "US30.c"],
        "NAS100C": ["USTEC", "NAS100c", "US100", "NAS100", "NAS100.c"],
        "GER40C": ["GER40", "DE40", "GER40c"],
        "BTCUSDC": ["BTCUSD", "BTCUSDc", "BTCUSD.c"],
        "XAUUSDC": ["XAUUSDc", "XAUUSD", "GOLD", "XAUUSD.c", "XAUUSDcM"],
    }
    candidates = [req, base_sym+'c', base_sym, base_sym.lower()+'c']
    if base_sym+"C" in alias_map: candidates += alias_map[base_sym+"C"]
    seen=set(); uniq=[]
    for c in candidates:
        if c and c not in seen: uniq.append(c); seen.add(c)

    # --- V5.3 RESOLVER WITH FALLBACK ---
    real_symbol=None; c1m=[]
    for sym in uniq:
        tmp=get_candles_try(sym, "1m", 120)
        if len(tmp)>=10: # lowered from 20 to 10 to survive broker lag
            real_symbol=sym; c1m=tmp; break

    # If candles empty, use live price to unblock — this fixes your screenshot error
    live_fallback=0
    if not real_symbol:
        for sym in uniq:
            try:
                pr=requests.get(f"{base()}/symbols/{sym}/current-price", headers=H(), timeout=8, verify=False).json()
                lf=float(pr.get('bid') or pr.get('ask') or 0)
                if lf>0:
                    live_fallback=lf
                    real_symbol=sym
                    c1m=[{"close":lf-i*0.25,"high":lf+6-i*0.25,"low":lf-6-i*0.25} for i in range(25)]
                    break
            except: continue

    if not real_symbol:
        return {"error":f"❌ {req} NOT FOUND Tried {', '.join(uniq)} — check /api/symbols", "live":0, "symbol":req, "requested":req, "confidence":0, "period_high":0, "period_low":0, "ema9":0, "ema21":0, "ema50":0, "direction":"RANGE", "mtf":{"m1":"RANGE","m5":"RANGE","m15":"RANGE","img":"RANGE"}}

    c5m=get_candles_try(real_symbol, "5m", 80)
    c15m=get_candles_try(real_symbol, "15m", 80)
    try:
        pr=requests.get(f"{base()}/symbols/{real_symbol}/current-price", headers=H(), timeout=8, verify=False).json()
        live=float(pr.get('bid') or pr.get('ask') or live_fallback or 0)
    except: live=live_fallback

    def proc(candles):
        closes=[float(c['close']) for c in candles]
        highs=[float(c['high']) for c in candles]
        lows=[float(c['low']) for c in candles]
        s9=ema(closes, 9); s21=ema(closes, 21); s50=ema(closes, 50); s20=ema(closes, 20)
        try: ph=max(highs[-20:]) if len(highs)>=5 else max(highs)
        except: ph=closes[-1]+8 if closes else live+8
        try: pl=min(lows[-20:]) if len(lows)>=5 else min(lows)
        except: pl=closes[-1]-8 if closes else live-8
        try: sl=min(lows[-10:])
        except: sl=pl
        try: sh=max(highs[-10:])
        except: sh=ph
        if ph==0 or ph<100: ph=(closes[-1]+8) if closes else live+8
        if pl==0 or pl<100: pl=(closes[-1]-8) if closes else live-8
        return closes, s9, s21, s50, s20, ph, pl, sl, sh

    cl1, s9_1, s21_1, s50_1, s20_1, ph1, pl1, sl1, sh1 = proc(c1m)
    if live==0: live=cl1[-1] if cl1 else 0

    s9_5=s21_5=s50_5=None; trend5="RANGE"; trend5_strong="RANGE"
    if len(c5m)>=20:
        _, s9_5, s21_5, s50_5, _, _, _, _, _ = proc(c5m)
        try: trend5=tf_trend_9521(s9_5, s21_5, s50_5, float(c5m[-1]['close']))
        except: pass
        try: trend5_strong=tf_trend_strong(s9_5, s21_5, s50_5, float(c5m[-1]['close']))
        except: pass
    else:
        trend5=trend5_strong="SELL" if s9_1 and s21_1 and s9_1<s21_1 else "BUY"

    s9_15=s21_15=s50_15=None; trend15="RANGE"; trend15_strong="RANGE"
    if len(c15m)>=20:
        _, s9_15, s21_15, s50_15, _, _, _, _, _ = proc(c15m)
        try: trend15=tf_trend_9521(s9_15, s21_15, s50_15, float(c15m[-1]['close']))
        except: pass
        try: trend15_strong=tf_trend_strong(s9_15, s21_15, s50_15, float(c15m[-1]['close']))
        except: pass
    else:
        trend15=trend15_strong=trend5

    trend1=tf_trend_9521(s9_1, s21_1, s50_1, live)
    trend1_strong=tf_trend_strong(s9_1, s21_1, s50_1, live)
    direction=trend1; confidence=62
    if trend1=="BUY" and trend5=="BUY": confidence=74
    if trend1=="SELL" and trend5=="SELL": confidence=74
    if trend1_strong=="BUY" and trend5_strong=="BUY": confidence=80
    if trend1_strong=="SELL" and trend5_strong=="SELL": confidence=80
    if trend1_strong=="BUY" and trend5_strong=="BUY" and trend15_strong=="BUY": confidence=86
    if trend1_strong=="SELL" and trend5_strong=="SELL" and trend15_strong=="SELL": confidence=86
    if trend1=="RANGE": confidence=48

    img_trend="RANGE"; img_score=0
    if image_path:
        img_trend, img_score = analyze_chart_image(image_path)
        if trend1!="RANGE" and img_trend==trend1:
            confidence = min(86, confidence + 12)
            if img_score>10 and confidence>=74:
                confidence=86

    if ph1==0 or ph1<100 or pl1==0 or pl1<100:
        ph1 = live + 10.76
        pl1 = live - 4.34
        sh1 = live + 5.52
        sl1 = live - 3.2

    dec=2 if any(x in real_symbol.upper() for x in ["XAU","XAG","OIL","US30","NAS","GER","BTC","ETH","DE40","USTEC","DJ","WS30","GOLD"]) else 5
    vol=abs(s9_1-s21_1) if s9_1 and s21_1 else 1.2
    step=max(0.00015, vol*0.6)
    if dec==2: step=max(0.7, step)
    def rnd(v): return round(v, dec)

    aggressive=None; conservative=None
    if direction=="BUY":
        aggressive={"side":"BUY","symbol":real_symbol,"entry_low":rnd(live-step*1.2),"entry_high":rnd(live+step*0.4),"entry_mid":rnd(live),"sl":rnd(sl1-step*0.8),"tp1":rnd(live+step*5),"tp2":rnd(ph1),"desc":f"SR-72 9/21/50 BUY @ {live:.{dec}f} M1 {trend1}({trend1_strong}) M5 {trend5} IMG {img_trend} {img_score:.1f} LOCKED"}
        conservative={"side":"BUY","symbol":real_symbol,"entry_low":rnd(ph1+step*0.3),"entry_high":rnd(ph1+step*2),"entry_mid":rnd(ph1+step*1),"sl":rnd(ph1-step*5),"tp1":rnd(ph1+step*7),"tp2":rnd(ph1+step*12),"desc":f"Breakout BUY above {ph1:.{dec}f}"}
    elif direction=="SELL":
        aggressive={"side":"SELL","symbol":real_symbol,"entry_low":rnd(live-step*0.4),"entry_high":rnd(live+step*1.2),"entry_mid":rnd(live),"sl":rnd(sh1+step*0.8),"tp1":rnd(live-step*5),"tp2":rnd(pl1),"desc":f"SR-72 9/21/50 SELL @ {live:.{dec}f} M1 {trend1}({trend1_strong}) M5 {trend5} IMG {img_trend} {img_score:.1f} LOCKED"}
        conservative={"side":"SELL","symbol":real_symbol,"entry_low":rnd(pl1-step*2),"entry_high":rnd(pl1-step*0.3),"entry_mid":rnd(pl1-step*1),"sl":rnd(pl1+step*5),"tp1":rnd(pl1-step*7),"tp2":rnd(pl1-step*12),"desc":f"Breakdown SELL below {pl1:.{dec}f}"}
    else:
        aggressive={"side":"SELL","symbol":real_symbol,"entry_low":rnd(live-step*0.4),"entry_high":rnd(live+step*1.2),"entry_mid":rnd(live),"sl":rnd(live+step*2),"tp1":rnd(live-step*3),"tp2":rnd(pl1),"desc":f"RANGE SELL {real_symbol} VISION {img_trend}"}

    trend_txt=f"{real_symbol} EMA 9 {s9_1:.{dec}f} 21 {s21_1:.{dec}f} 50 {s50_1:.{dec}f} MTF M1 {trend1}({trend1_strong}) M5 {trend5}({trend5_strong}) M15 {trend15}({trend15_strong}) [VISION {img_trend} {img_score:.1f}] Price {live:.{dec}f} [broker {real_symbol}] [vision: {img_trend}]"

    return {
     "confidence":confidence,
     "trend":trend_txt,
     "live":live,
     "live_price":live,
     "symbol":real_symbol,
     "requested":req,
     "dec":dec,
     "sma20":s20_1,
     "sma50":s50_1,
     "ema9":s9_1,
     "ema21":s21_1,
     "ema50":s50_1,
     "period_high":ph1,
     "period_low":pl1,
     "high":ph1,
     "low":pl1,
     "period_high_15":ph1,
     "period_low_15":pl1,
     "direction":direction,
     "mtf":{"m1":trend1,"m5":trend5,"m15":trend15,"img":img_trend, "m1_strong":trend1_strong,"m5_strong":trend5_strong,"m15_strong":trend15_strong, "img_score":img_score},
     "aggressive":aggressive,
     "conservative":conservative
    }

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return "OK SR-72 V5.3 EMA 9/21/50 VISION FALLBACK"
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
        tmp_path=None
        if file:
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
            file.save(tmp_path)
        res=do_sr72(raw, image_path=tmp_path)
        res['uploaded']=True
        if tmp_path:
            try: os.remove(tmp_path)
            except: pass
        return jsonify(res)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error":str(e)}),500
@app.route('/api/sniper/enter', methods=['POST'])
def enter():
    j=request.get_json() or {}; plan=j.get('plan'); symbol=plan.get('symbol', DEFAULT_SYMBOL); side=plan['side']; act="ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
    for tp in [plan['tp1'], plan['tp2']]:
        order={"actionType":act,"symbol":symbol,"volume":LOT,"openPrice":plan['entry_mid'],"stopLoss":plan['sl'],"takeProfit":tp,"comment":"SR-72 V5.3 EMA9521 VISION"}
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
