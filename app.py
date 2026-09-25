from flask import Flask, send_from_directory, request, jsonify
import os, requests
app = Flask(__name__)
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"

def find_token():
    # 1. Try exact name
    t = os.getenv("METAAPI_TOKEN")
    if t and len(t.strip()) > 100: return t.strip(), "METAAPI_TOKEN"
    # 2. Search ANY env var that looks like JWT token
    for k,v in os.environ.items():
        if v and v.strip().startswith("eyJ") and len(v) > 500:
            return v.strip(), f"FOUND_IN_{k}"
    return "", "NOT_FOUND"

def H(tok): return {"auth-token": tok, "Content-Type":"application/json"}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"

@app.route('/api/test_trade')
def test_trade():
    tok, src = find_token()
    log = f"<b>V17 ROBUST</b><br>SOURCE: {src}<br>LEN: {len(tok)} START: {tok[:30]}...<br><br>"
    log += f"Using: {base()}<br><br>"
    if len(tok) < 100:
        return log + "TOKEN NOT FOUND - Fix key name to METAAPI_TOKEN"
    try:
        r = requests.get(f"{base()}/accountInformation", headers=H(tok), timeout=15, verify=False)
        log += f"AccountInfo {r.status_code}: {r.text[:2000]}<br><br>"
    except Exception as e: log += f"ERR {e}<br><br>"
    try:
        r = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(tok), timeout=10, verify=False)
        log += f"Price {r.status_code}: {r.text[:1000]}<br><br>"
    except Exception as e: log += f"Price ERR {e}<br><br>"
    try:
        payload={"actionType":"ORDER_TYPE_BUY","symbol":SYMBOL,"volume":0.01}
        r = requests.post(f"{base()}/trade", headers=H(tok), json=payload, timeout=20, verify=False)
        log += f"BUY {r.status_code}: {r.text}<br><br>"
    except Exception as e: log += f"BUY ERR {e}<br><br>"
    return log

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def h():
    tok, src = find_token()
    return f"OK V17 {src} len={len(tok)}"
@app.route('/api/balance')
def bal():
    tok,_ = find_token()
    r = requests.get(f"{base()}/accountInformation", headers=H(tok), timeout=15, verify=False)
    return r.text, r.status_code
@app.route('/analyze', methods=['POST'])
def analyze(): return jsonify({"live_price":4273,"symbol":SYMBOL,"direction":"BUY","confidence":85,"entry":4273,"stop_loss":4271,"tp1":4274,"tp2":4275,"tp3":4276})
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
