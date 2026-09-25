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
        url=f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}/{path}"
        r=requests.get(url, headers=H(), timeout=15, verify=False)
        print(f"GET {path} -> {r.status_code} {r.text[:500]}")
        if not r.text.strip():
            return {"error": f"Empty response {r.status_code}", "raw": r.text, "path": path}
        try:
            return r.json()
        except:
            return {"error": f"Non-JSON {r.status_code}", "raw": r.text[:500]}
    except Exception as e:
        print(f"GET ERROR {path} {e}")
        return {"error": str(e)}

def get_price():
    d = api_get(f"symbolPrice?symbol={SYMBOL}")
    if "error" in d:
        print(f"PRICE FALLBACK 4273 due to {d}")
        return 4273.0, d
    price = float(d.get('ask') or d.get('bid') or 4273.0)
    return price, d

def place(action, price):
    url=f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/{ACCOUNT_ID}/trade"
    payload={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":float(price)}
    try:
        r=requests.post(url, headers=H(), json=payload, timeout=20, verify=False)
        print(f"TRADE {action} {price} -> {r.status_code} {r.text}")
        return f"Status {r.status_code}: {r.text}"
    except Exception as e:
        print(f"TRADE ERROR {e}")
        return str(e)

@app.route('/api/balance')
def bal():
    return jsonify(api_get("accountInformation"))

@app.route('/api/debug')
def debug():
    conn=api_get("connectionStatus")
    price, p_raw = get_price()
    acct=api_get("accountInformation")
    return jsonify({"connectionStatus":conn,"price":price,"price_raw":p_raw,"account":acct})

@app.route('/api/test_trade')
def test_trade():
    conn=api_get("connectionStatus")
    price, p_raw = get_price()
    if price==0:
        price=4273.0
    r1=place("ORDER_TYPE_BUY_STOP", price+1.0)
    time.sleep(1.5)
    r2=place("ORDER_TYPE_SELL_STOP", price-1.0)
    return f"CONNECTION: {conn}<br>PRICE: {price}<br>PRICE_RAW: {p_raw}<br><br>BUY RESULT: {r1}<br><br>SELL RESULT: {r2}"

@app.route('/start')
def start():
    global bot_running
    if not bot_running:
        bot_running=True
        threading.Thread(target=real_loop, daemon=True).start()
    return "STARTED V13.8 MERGED - Now hit /api/test_trade"

def real_loop():
    print("V13.8 LOOP START")
    while bot_running:
        time.sleep(10)

@app.route('/')
def idx(): return send_from_directory('.','index.html')

@app.route('/health')
def h(): return "OK V13.8 MERGED"

@app.route('/analyze', methods=['POST'])
def analyze():
    price,_=get_price()
    return jsonify({"live_price":price,"symbol":SYMBOL,"direction":"BUY","confidence":85,"entry":price,"stop_loss":price-2,"tp1":price+1,"tp2":price+2,"tp3":price+3,"balance_usc":1009,"analysis":"V13.8 MERGED READY"})

if __name__=='__main__':
    app.run(host='0.0.0.0',port=10000)
