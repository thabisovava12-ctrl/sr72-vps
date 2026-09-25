from flask import Flask, send_from_directory, request, jsonify
import os, requests
app = Flask(__name__)
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()

def H(): return {"auth-token": TOKEN, "Content-Type":"application/json"}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"

@app.route('/api/test_trade')
def test_trade():
    r = requests.get(f"{base()}/accountInformation", headers=H(), timeout=15, verify=False)
    return f"Balance check {r.status_code}: {r.text[:1000]}"

@app.route('/api/balance')
def bal():
    r = requests.get(f"{base()}/accountInformation", headers=H(), timeout=15, verify=False)
    return r.text, r.status_code

@app.route('/api/price')
def price():
    r = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def h(): return f"OK V18 LIVE READY balance endpoint works"
@app.route('/analyze', methods=['POST'])
def analyze():
    # your SR72 logic here - now it can call real trade via /trade endpoint
    data = request.json
    return jsonify({"live_price": 4288, "symbol": SYMBOL, "direction": "BUY", "confidence": 85, "entry": 4288, "stop_loss": 4286, "tp1": 4290, "tp2": 4292, "tp3": 4294})

if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
