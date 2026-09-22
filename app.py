from flask import Flask, send_from_directory
import threading, time, os, requests

app = Flask(__name__)

# YOUR REAL ACCOUNT - SAVED FROM 2 DAYS AGO
ACCOUNT_ID = "72d36c7c-bb20-4120-80cd-922cd0497bfc"
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN") or os.getenv("TOKEN")
# Backup - your long token you gave me
if not METAAPI_TOKEN:
    METAAPI_TOKEN = "REPLACE_WITH_YOUR_TOKEN_FROM_ENV"  # Set in Render

SYMBOLS_TO_TRY = ["XAUUSD", "XAUUSDc", "XAUUSD.a", "GOLD", "XAUUSDm"]
LOT = 0.01
STRADDLE = 0.8
bot_running = False
CURRENT_SYMBOL = "XAUUSD"

def real_loop():
    global bot_running, CURRENT_SYMBOL
    headers = {"auth-token": METAAPI_TOKEN}
    base = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}"
    print(f"🔥 REAL CENT BOT STARTED • Account {ACCOUNT_ID}")

    # Auto-detect correct Gold symbol for Cent
    for sym in SYMBOLS_TO_TRY:
        try:
            r = requests.get(f"{base}/symbolPrice?symbol={sym}", headers=headers, timeout=10)
            if r.status_code == 200:
                CURRENT_SYMBOL = sym
                print(f"✅ REAL SYMBOL FOUND: {sym}")
                break
        except: pass

    while bot_running:
        try:
            # Real price
            price_resp = requests.get(f"{base}/symbolPrice?symbol={CURRENT_SYMBOL}", headers=headers, timeout=15).json()
            ask = price_resp.get('ask') or price_resp.get('bid')
            if not ask:
                time.sleep(5)
                continue

            print(f"REAL CENT: {CURRENT_SYMBOL} {ask} -> Straddle ${STRADDLE}")

            # BUY STOP REAL
            requests.post(f"{base}/trade", headers=headers, json={
                "actionType": "ORDER_TYPE_BUY_STOP",
                "symbol": CURRENT_SYMBOL,
                "volume": LOT,
                "openPrice": ask + STRADDLE,
                "stopLoss": ask - 2,
                "takeProfit": ask + 5
            })
            # SELL STOP REAL
            requests.post(f"{base}/trade", headers=headers, json={
                "actionType": "ORDER_TYPE_SELL_STOP",
                "symbol": CURRENT_SYMBOL,
                "volume": LOT,
                "openPrice": ask - STRADDLE,
                "stopLoss": ask + 2,
                "takeProfit": ask - 5
            })

            time.sleep(60)
        except Exception as e:
            print(f"REAL ERROR: {e}")
            time.sleep(10)

@app.route('/')
def index(): return send_from_directory('.', 'index.html')
@app.route('/start')
def start():
    global bot_running
    if not bot_running:
        bot_running = True
        threading.Thread(target=real_loop, daemon=True).start()
    return f"REAL CENT BOT STARTED • {CURRENT_SYMBOL} • Lot {LOT} • Straddle ${STRADDLE}"
@app.route('/stop')
def stop():
    global bot_running
    bot_running = False
    return "REAL BOT STOPPED"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
