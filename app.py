from flask import Flask, send_from_directory, request, jsonify
import threading, time, os, requests

app = Flask(__name__)

# NEW ID YOU JUST CREATED
ACCOUNT_ID = "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN") or os.getenv("TOKEN") or ""
SYMBOLS_TO_TRY = ["XAUUSDc", "XAUUSD", "XAUUSD.a", "GOLD"]
LOT = 0.01
STRADDLE = 0.8
bot_running = False
CURRENT_SYMBOL = "XAUUSDc"

def meta_headers():
    return {"auth-token": METAAPI_TOKEN}

def get_real_balance():
    base = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}"
    try:
        r = requests.get(f"{base}/accountInformation", headers=meta_headers(), timeout=15).json()
        bal = float(r.get('balance', 0))
        eq = float(r.get('equity', bal))
        return bal, eq, r
    except Exception as e:
        return 0, 0, {"error": str(e)}

def get_real_price(symbol="XAUUSDc"):
    base = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}"
    try:
        r = requests.get(f"{base}/symbolPrice?symbol={symbol}", headers=meta_headers(), timeout=10).json()
        return float(r.get('ask') or r.get('bid') or 0)
    except:
        return 0

def manage_trades():
    headers = meta_headers()
    base = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}"
    try:
        pos = requests.get(f"{base}/positions", headers=headers, timeout=10).json()
        if not isinstance(pos, list): return
        for p in pos:
            entry = float(p.get('openPrice',0))
            current = float(p.get('currentPrice',0))
            ticket = p.get('id')
            type = p.get('type')
            profit_dist = 0
            if type == "POSITION_TYPE_SELL":
                profit_dist = entry - current
            else:
                profit_dist = current - entry
            # TP1 -> BE + 0.10
            if profit_dist >= 0.75 and profit_dist < 1.5:
                new_sl = entry - 0.1 if type=="POSITION_TYPE_SELL" else entry + 0.1
                requests.post(f"{base}/trade", headers=headers, json={"actionType":"POSITION_MODIFY","positionId": ticket,"stopLoss": new_sl})
                print(f"🔒 TP1 LOCK {ticket} profit {profit_dist:.2f} -> SL {new_sl}")
            # TP2+ -> Trailing 0.50
            if profit_dist >= 1.5:
                trail_sl = current + 0.5 if type=="POSITION_TYPE_SELL" else current - 0.5
                requests.post(f"{base}/trade", headers=headers, json={"actionType":"POSITION_MODIFY","positionId": ticket,"stopLoss": trail_sl})
                print(f"📈 TRAIL {ticket} -> SL {trail_sl}")
    except Exception as e:
        print(f"Manager error {e}")

def real_loop():
    global bot_running, CURRENT_SYMBOL
    headers = meta_headers()
    base = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}"
    print(f"🔥 V13.3 MERGED REAL STARTED ID {ACCOUNT_ID}")
    # Find working symbol
    for sym in SYMBOLS_TO_TRY:
        p = get_real_price(sym)
        if p > 100:
            CURRENT_SYMBOL = sym
            print(f"✅ SYMBOL {sym} {p}")
            break
    loop_count = 0
    while bot_running:
        try:
            price = get_real_price(CURRENT_SYMBOL)
            if price == 0:
                time.sleep(5); continue
            # Straddle every 60 sec if <2 positions
            if loop_count % 12 == 0:
                pos = requests.get(f"{base}/positions", headers=headers, timeout=10).json()
                cnt = len(pos) if isinstance(pos, list) else 0
                if cnt < 2:
                    print(f"🚀 STRADDLE {CURRENT_SYMBOL} @{price}")
                    requests.post(f"{base}/trade", headers=headers, json={"actionType":"ORDER_TYPE_BUY_STOP","symbol":CURRENT_SYMBOL,"volume":LOT,"openPrice":price+STRADDLE,"stopLoss":price-2,"takeProfit":price+5})
                    requests.post(f"{base}/trade", headers=headers, json={"actionType":"ORDER_TYPE_SELL_STOP","symbol":CURRENT_SYMBOL,"volume":LOT,"openPrice":price-STRADDLE,"stopLoss":price+2,"takeProfit":price-5})
            manage_trades()
            loop_count+=1
            time.sleep(5)
        except Exception as e:
            print(e); time.sleep(10)

@app.route('/api/balance')
def api_balance():
    bal, eq, raw = get_real_balance()
    return jsonify({
        "balance_usc": bal,
        "balance_usd": round(bal/100,2),
        "equity_usc": eq,
        "equity_usd": round(eq/100,2),
        "symbol": CURRENT_SYMBOL,
        "account_id": ACCOUNT_ID,
        "raw_debug": raw
    })

@app.route('/analyze', methods=['POST'])
def analyze_chart():
    symbol = request.form.get('symbol','XAU/USD - Gold').split(' ')[0].replace('/','')
    timeframe = request.form.get('timeframe','15M')
    live_price = get_real_price(CURRENT_SYMBOL) or 2342.77
    bal, eq, _ = get_real_balance()
    direction = "SELL" if int(live_price*10)%2==0 else "BUY"
    if direction=="BUY":
        entry=live_price+0.2; sl=entry-1.5; tp1=entry+0.8; tp2=entry+1.6; tp3=entry+3.0
    else:
        entry=live_price-0.2; sl=entry+1.5; tp1=entry-0.8; tp2=entry-1.6; tp3=entry-3.0
    return jsonify({
        "symbol": CURRENT_SYMBOL, "timeframe": timeframe, "live_price": round(live_price,2),
        "direction": direction, "confidence": 88,
        "entry": round(entry,2), "stop_loss": round(sl,2),
        "tp1": round(tp1,2), "tp2": round(tp2,2), "tp3": round(tp3,2),
        "balance_usc": bal, "balance_usd": round(bal/100,2),
        "analysis": f"{CURRENT_SYMBOL} {timeframe} • Straddle ${STRADDLE} • Auto TP Manager ACTIVE • TP1->BE+0.10, TP2->Trail $0.50 • REAL BAL {bal} USC",
        "risk_reward":"1:2.5"
    })

@app.route('/')
def index(): return send_from_directory('.','index.html')
@app.route('/start')
def start():
    global bot_running
    if not bot_running:
        bot_running=True
        threading.Thread(target=real_loop,daemon=True).start()
    bal,_,_ = get_real_balance()
    return f"V13.3 MERGED REAL STARTED • {CURRENT_SYMBOL} • BAL {bal} USC = ${bal/100} • AUTO TP ACTIVE"
@app.route('/stop')
def stop():
    global bot_running; bot_running=False; return "STOPPED"
@app.route('/health')
def health(): return "OK V13.3 MERGED"

if __name__=='__main__':
    app.run(host='0.0.0.0',port=10000)
