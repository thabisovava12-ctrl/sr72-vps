from flask import Flask, send_from_directory, jsonify, request
import os, requests, math
from datetime import datetime, timezone
app = Flask(__name__)

ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()
LOT = 0.01

def H(): return {"auth-token": TOKEN}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"
def baseMD(): return f"https://mt-market-data-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}/historical-market-data"

def get_candles(tf, limit=200):
    try:
        url = f"{baseMD()}/symbols/{SYMBOL}/timeframes/{tf}/candles?limit={limit}"
        r = requests.get(url, headers=H(), timeout=20, verify=False)
        data = r.json()
        # MetaAPI returns list or dict
        if isinstance(data, list): return data
        if 'candles' in data: return data['candles']
        return data[-limit:] if isinstance(data, dict) else []
    except Exception as e:
        print(f"candle {tf} err {e}"); return []

def ema(values, period):
    if len(values) < period: return None
    k = 2/(period+1)
    ema_val = sum(values[:period])/period
    for v in values[period:]:
        ema_val = v*k + ema_val*(1-k)
    return ema_val

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return "OK V40 GOLD SNIPER 0.01"

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
        # 1. HTF TREND 1H EMA200
        c1h = get_candles("1h", 250)
        closes1h = [c['close'] for c in c1h if 'close' in c]
        ema200 = ema(closes1h, 200) if len(closes1h)>=200 else None
        last_close = closes1h[-1] if closes1h else 0
        trend = "BUY" if ema200 and last_close > ema200 else "SELL" if ema200 else "UNKNOWN"
        
        # 2. KEY LEVELS
        c1d = get_candles("1d", 3)
        prev_high = c1d[-2]['high'] if len(c1d)>=2 else last_close+10
        prev_low = c1d[-2]['low'] if len(c1d)>=2 else last_close-10
        
        c15m = get_candles("15m", 96) # 24h
        # London 08-17 UTC, NY 13-22 UTC - simple filter by hour
        london = [c for c in c15m if 8 <= datetime.fromtimestamp(c['time'], tz=timezone.utc).hour <= 17]
        ny = [c for c in c15m if 13 <= datetime.fromtimestamp(c['time'], tz=timezone.utc).hour <= 22]
        london_high = max([c['high'] for c in london]) if london else prev_high
        london_low = min([c['low'] for c in london]) if london else prev_low
        ny_high = max([c['high'] for c in ny]) if ny else prev_high
        ny_low = min([c['low'] for c in ny]) if ny else prev_low
        
        # 15M S/R = recent swing high/low
        swing_high = max([c['high'] for c in c15m[-20:]]) if c15m else prev_high
        swing_low = min([c['low'] for c in c15m[-20:]]) if c15m else prev_low

        # 3. LIQUIDITY SWEEP on 5M
        c5m = get_candles("5m", 100)
        sweep = "NONE"
        sweep_level = None
        if c5m:
            last = c5m[-1]
            # sweep above prev high then close below
            for level in [prev_high, london_high, ny_high, swing_high]:
                if last['high'] > level and last['close'] < level:
                    sweep = f"SELL SWEEP ABOVE {level:.2f} -> REJECT"
                    sweep_level = level
                    break
            for level in [prev_low, london_low, ny_low, swing_low]:
                if last['low'] < level and last['close'] > level:
                    sweep = f"BUY SWEEP BELOW {level:.2f} -> REJECT"
                    sweep_level = level
                    break

        # 4. BOS on 5M
        bos = "WAITING"
        if len(c5m) >= 10:
            # simple BOS: last close breaks previous 20 high/low
            recent_high = max(c['high'] for c in c5m[-20:-1])
            recent_low = min(c['low'] for c in c5m[-20:-1])
            if c5m[-1]['close'] > recent_high:
                bos = f"BULLISH BOS above {recent_high:.2f}"
            elif c5m[-1]['close'] < recent_low:
                bos = f"BEARISH BOS below {recent_low:.2f}"

        # 5-7 ENTRY, SL, TP logic
        setup = "NO SETUP"
        entry = None; sl = None; tp = None
        if sweep_level and "BUY SWEEP" in sweep and trend=="BUY" and "BULLISH" in bos:
            setup = "BEST BUY SETUP: HTF BUY + SWEEP + 5M BOS + RETEST"
            entry = round(sweep_level + 0.30, 2) # retest
            sl = round(c5m[-1]['low'] - 0.50, 2) # beyond sweep
            risk = entry - sl
            tp = round(entry + risk*2, 2) # 1:2
        elif sweep_level and "SELL SWEEP" in sweep and trend=="SELL" and "BEARISH" in bos:
            setup = "BEST SELL SETUP: HTF SELL + SWEEP + 5M BOS + RETEST"
            entry = round(sweep_level - 0.30, 2)
            sl = round(c5m[-1]['high'] + 0.50, 2)
            risk = sl - entry
            tp = round(entry - risk*2, 2)

        return jsonify({
            "trend": trend, "ema200": ema200, "last_close": last_close,
            "levels": {"pdh": prev_high, "pdl": prev_low, "lh": london_high, "ll": london_low, "nh": ny_high, "nl": ny_low, "s15h": swing_high, "s15l": swing_low},
            "sweep": sweep, "sweep_level": sweep_level,
            "bos": bos,
            "setup": setup, "entry": entry, "sl": sl, "tp": tp,
            "time": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sniper/enter', methods=['POST'])
def sniper_enter():
    j = request.get_json() or {}
    side = j.get('side','BUY') # BUY or SELL
    entry = float(j.get('entry')); sl = float(j.get('sl')); tp = float(j.get('tp'))
    # Place limit order at retest
    action = "ORDER_TYPE_BUY_LIMIT" if side=="BUY" else "ORDER_TYPE_SELL_LIMIT"
    order = {"actionType": action, "symbol": SYMBOL, "volume": LOT, "openPrice": entry, "stopLoss": sl, "takeProfit": tp}
    r = requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json=order, timeout=15, verify=False)
    return jsonify({"placed": order, "resp": r.text[:500]})

@app.route('/api/close_all', methods=['POST'])
def close_all():
    try:
        o=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
        for od in o:
            if od.get('symbol')==SYMBOL:
                requests.post(f"{base()}/trade", headers={"auth-token": TOKEN, "Content-Type":"application/json"}, json={"actionType":"ORDER_TYPE_CANCEL","orderId":od['id']}, timeout=10, verify=False)
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
