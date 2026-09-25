from flask import Flask, send_from_directory, request, jsonify
import os, requests
app = Flask(__name__)
ACCOUNT_ID = "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
TOKEN = os.getenv("METAAPI_TOKEN") or ""
SYMBOL = "XAUUSDc"
REGION = "new-york"

def H(): return {"auth-token": TOKEN}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"

@app.route('/api/test_trade')
def test_trade():
    b=base()
    log=f"Using: {b}<br><br>"
    # 1. account info
    try:
        r=requests.get(f"{b}/accountInformation", headers=H(), timeout=15, verify=False)
        log+=f"AccountInfo {r.status_code}: {r.text[:600]}<br><br>"
    except Exception as e: log+=f"AccountInfo ERR {e}<br><br>"

    # 2. price - correct endpoint
    price=4273.0
    try:
        r=requests.get(f"{b}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False)
        log+=f"Current-Price {r.status_code}: {r.text[:600]}<br><br>"
        if r.ok:
            j=r.json()
            price=float(j.get('ask') or j.get('price') or 4273.0)
    except Exception as e:
        log+=f"Price ERR {e} - using fallback 4273<br><br>"

    # 3. trade - correct endpoint
    try:
        payload={"actionType":"ORDER_TYPE_BUY","symbol":SYMBOL,"volume":0.01}
        r=requests.post(f"{b}/trade", headers=H(), json=payload, timeout=20, verify=False)
        log+=f"BUY TRADE {r.status_code}: {r.text}<br><br>"
    except Exception as e:
        log+=f"BUY ERR {e}<br><br>"

    try:
        payload={"actionType":"ORDER_TYPE_SELL","symbol":SYMBOL,"volume":0.01}
        r=requests.post(f"{b}/trade", headers=H(), json=payload, timeout=20, verify=False)
        log+=f"SELL TRADE {r.status_code}: {r.text}<br><br>"
    except Exception as e:
        log+=f"SELL ERR {e}<br><br>"

    return log

@app.route('/api/balance')
def bal():
    b=base()
    r=requests.get(f"{b}/accountInformation", headers=H(), timeout=15, verify=False)
    return r.text, r.status_code

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def h(): return "OK V15 CORRECT PATH"
@app.route('/analyze', methods=['POST'])
def analyze(): return jsonify({"live_price":4273,"symbol":SYMBOL,"direction":"BUY","confidence":85,"entry":4273,"stop_loss":4271,"tp1":4274,"tp2":4275,"tp3":4276})

if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
