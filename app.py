from flask import Flask, send_from_directory, jsonify
import os, requests, threading, time, math
app = Flask(__name__)

ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()

LOT = 0.01
BASE_STRADDLE = 2.50
SL_DIST = 2.50
TRAIL_START = 1.20
TRAIL_STEP = 0.40
BE_TRIGGER = 1.00
MAX_SPREAD = 0.60

def H(): return {"auth-token": TOKEN, "Content-Type":"application/json"}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"

trailing_active = False
def get_atr_straddle():
    try:
        # get last 14 M1 candles for volatility
        r = requests.get(f"{base()}/symbols/{SYMBOL}/candles?timeframe=M1&limit=14", headers=H(), timeout=10, verify=False).json()
        ranges = [c['high']-c['low'] for c in r]
        atr = sum(ranges)/len(ranges)
        # dynamic: 1.5x ATR, min 1.5 max 3.5
        dyn = round(max(1.5, min(3.5, atr*1.5)), 2)
        return dyn
    except: return BASE_STRADDLE

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return "OK V27 ADV FIXED 0.01 ATR+BE+TRAIL"

@app.route('/api/balance')
def bal():
    r = requests.get(f"{base()}/accountInformation", headers=H(), timeout=15, verify=False)
    return r.text, r.status_code
@app.route('/api/price')
def price():
    r = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code
@app.route('/api/positions')
def positions():
    r = requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code
@app.route('/api/orders')
def orders():
    r = requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code

@app.route('/api/start_straddle', methods=['POST'])
def start_straddle():
    global trailing_active
    pr = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
    if pr['ask']-pr['bid'] > MAX_SPREAD:
        return jsonify({"error": f"Spread too high {pr['ask']-pr['bid']:.2f} > {MAX_SPREAD}, wait"}), 400
    dyn = get_atr_straddle()
    buy_p = round(pr['ask'] + dyn, 2)
    sell_p = round(pr['bid'] - dyn, 2)
    b1 = {"actionType":"ORDER_TYPE_BUY_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":buy_p,"stopLoss":round(buy_p-SL_DIST,2)}
    s1 = {"actionType":"ORDER_TYPE_SELL_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":sell_p,"stopLoss":round(sell_p+SL_DIST,2)}
    r1 = requests.post(f"{base()}/trade", headers=H(), json=b1, timeout=15, verify=False)
    r2 = requests.post(f"{base()}/trade", headers=H(), json=s1, timeout=15, verify=False)
    trailing_active = True
    threading.Thread(target=trailing_loop, daemon=True).start()
    return jsonify({"buy":buy_p,"sell":sell_p,"atr_straddle":dyn,"mode":"ADV FIXED 0.01 BE+TRAIL+HEDGE"})

def trailing_loop():
    while trailing_active:
        try:
            pos_r = requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
            pr = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
            bid, ask = pr['bid'], pr['ask']
            # hedge close if both sides in profit combined
            if len(pos_r)>=2:
                total_pnl = sum([p.get('profit',0) for p in pos_r if p['symbol']==SYMBOL])
                if total_pnl >= 2.0:  # close hedge at +$2
                    for p in pos_r:
                        side = "SELL" if p['type']=='POSITION_TYPE_BUY' else "BUY"
                        requests.post(f"{base()}/trade", headers=H(), json={"actionType":f"ORDER_TYPE_{side}","symbol":p['symbol'],"volume":p['volume'],"positionId":p['id']}, timeout=10, verify=False)
                    continue
            for pos in pos_r:
                if pos['symbol']!=SYMBOL: continue
                entry = pos['openPrice']
                sl = pos.get('stopLoss',0)
                if pos['type']=='POSITION_TYPE_BUY':
                    prof = ask - entry
                    if prof >= BE_TRIGGER and sl < entry:  # move to breakeven
                        requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_BUY","symbol":SYMBOL,"volume":pos['volume'],"positionId":pos['id'],"stopLoss":round(entry+0.10,2)}, timeout=10, verify=False)
                    elif prof >= TRAIL_START:
                        new_sl = round(ask - TRAIL_STEP,2)
                        if new_sl > sl:
                            requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_BUY","symbol":SYMBOL,"volume":pos['volume'],"positionId":pos['id'],"stopLoss":new_sl}, timeout=10, verify=False)
                else:
                    prof = entry - bid
                    if prof >= BE_TRIGGER and (sl==0 or sl > entry):
                        requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_SELL","symbol":SYMBOL,"volume":pos['volume'],"positionId":pos['id'],"stopLoss":round(entry-0.10,2)}, timeout=10, verify=False)
                    elif prof >= TRAIL_START:
                        new_sl = round(bid + TRAIL_STEP,2)
                        if sl==0 or new_sl < sl:
                            requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_SELL","symbol":SYMBOL,"volume":pos['volume'],"positionId":pos['id'],"stopLoss":new_sl}, timeout=10, verify=False)
        except: pass
        time.sleep(1.5)

@app.route('/api/close_all', methods=['POST'])
def close_all():
    global trailing_active
    trailing_active=False
    try:
        o = requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
        for od in o: requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_CANCEL","orderId":od['id']}, timeout=10, verify=False)
    except: pass
    try:
        p = requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
        for pos in p:
            side="SELL" if pos['type']=='POSITION_TYPE_BUY' else "BUY"
            requests.post(f"{base()}/trade", headers=H(), json={"actionType":f"ORDER_TYPE_{side}","symbol":pos['symbol'],"volume":pos['volume'],"positionId":pos['id']}, timeout=10, verify=False)
    except: pass
    return jsonify({"closed":True})

if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
