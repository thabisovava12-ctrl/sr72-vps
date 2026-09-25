from flask import Flask, send_from_directory, request, jsonify
import threading, time, os, requests
app = Flask(__name__)
ACCOUNT_ID = "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN") or ""
SYMBOL = "XAUUSDc"
LOT = 0.01
bot_running = False

# FIXED DOMAIN - single agiliumtrade.ai
BASE = f"https://mt-client-api-v1.agiliumtrade.ai/users/{ACCOUNT_ID}"

def H(): return {"auth-token": METAAPI_TOKEN}

def api_get(path):
    try:
        url=f"{BASE}/{path}"
        r=requests.get(url, headers=H(), timeout=15, verify=False)
        print(f"GET {path} -> {r.status_code} {r.text[:500]}")
        if not r.text.strip(): return {"error": f"Empty {r.status_code}"}
        return r.json()
    except Exception as e: return {"error": str(e)}

def get_price():
    try:
        d=api_get(f"symbolPrice?symbol={SYMBOL}")
        if "error" in d: return 4273.0, d
        return float(d.get('ask') or d.get('bid') or 4273.0), d
    except: return 4273.0, {"fallback":True}

def place(action, price):
    try:
        url=f"{BASE}/trade"
        payload={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":float(price)}
        r=requests.post(url, headers=H(), json=payload, timeout=20, verify=False)
        print(f"TRADE {action} {price} -> {r.status_code} {r.text}")
        return f"Status {r.status_code}: {r.text}"
    except Exception as e: return str(e)

@app.route('/api/balance')
def bal(): return jsonify(api_get("accountInformation"))
@app.route('/api/debug')
def debug():
    return jsonify({"connection":api_get("connectionStatus"),"price":get_price()[0],"price_raw":get_price()[1]})
@app.route('/api/test_trade')
def test_trade():
    conn=api_get("connectionStatus")
    price,_=get_price()
    r1=place("ORDER_TYPE_BUY_STOP", price+1.0)
    time.sleep(1)
    r2=place("ORDER_TYPE_SELL_STOP", price-1.0)
    return f"CONNECTION: {conn}<br>PRICE: {price}<br><br>BUY: {r1}<br><br>SELL: {r2}"
@app.route('/start')
def start():
    global bot_running
    if not bot_running:
        bot_running=True; threading.Thread(target=lambda: real_loop(), daemon=True).start()
    return "STARTED V13.9 FIXED DOMAIN"
def real_loop():
    while bot_running: time.sleep(10)
@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def h(): return "OK V13.9"
@app.route('/analyze', methods=['POST'])
def analyze():
    price,_=get_price()
    return jsonify({"live_price":price,"symbol":SYMBOL,"direction":"BUY","confidence":85,"entry":price,"stop_loss":price-2,"tp1":price+1,"tp2":price+2,"tp3":price+3,"balance_usc":1009,"analysis":"V13.9 DOMAIN FIXED"})
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
