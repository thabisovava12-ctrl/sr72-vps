from flask import Flask, send_from_directory, request, jsonify
import threading, time, os, requests
app = Flask(__name__)
ACCOUNT_ID = "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN") or ""
SYMBOL = "XAUUSDc"
LOT = 0.01
bot_running = False
def H(): return {"auth-token": METAAPI_TOKEN}
def api_get(path):
    try: 
        return requests.get(f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}/{path}", headers=H(), timeout=15, verify=False).json()
    except Exception as e: return {"error":str(e)}
def get_price():
    d=api_get(f"symbolPrice?symbol={SYMBOL}"); return float(d.get('ask') or d.get('bid') or 0), d
def place(action,price):
    url=f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}/trade"
    payload={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":float(price)}
    try:
        r=requests.post(url, headers=H(), json=payload, timeout=20, verify=False)
        print(f"TRADE {action} {price} -> {r.status_code} {r.text}")
        return r.text
    except Exception as e: return str(e)

@app.route('/api/balance')
def bal(): return jsonify(api_get("accountInformation"))
@app.route('/api/debug')
def debug():
    conn=api_get("connectionStatus"); price, p_raw = get_price()
    return jsonify({"connectionStatus":conn,"price":price,"price_raw":p_raw,"account":api_get("accountInformation")})
@app.route('/api/test_trade')
def test_trade():
    conn=api_get("connectionStatus")
    price,_=get_price()
    if price==0: return f"PRICE STILL 0 -> {conn} - WAIT 20 sec after redeploy"
    r1=place("ORDER_TYPE_BUY_STOP", price+1.0)
    time.sleep(1)
    r2=place("ORDER_TYPE_SELL_STOP", price-1.0)
    return f"CONNECTION: {conn}<br>PRICE: {price}<br><br>BUY: {r1}<br><br>SELL: {r2}"
@app.route('/start')
def start():
    global bot_running
    if not bot_running:
        bot_running=True; threading.Thread(target=lambda: real_loop(), daemon=True).start()
    return "STARTED V13.6 FIXED SSL"
def real_loop():
    while bot_running: time.sleep(10)
@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def h(): return "OK V13.6"
@app.route('/analyze', methods=['POST'])
def analyze():
    price,_=get_price(); return jsonify({"live_price":price,"symbol":SYMBOL,"direction":"BUY","confidence":85,"entry":price,"stop_loss":price-2,"tp1":price+1,"tp2":price+2,"tp3":price+3,"balance_usc":1009,"analysis":"V13.6 SSL FIXED"})
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
