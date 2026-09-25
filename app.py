from flask import Flask, send_from_directory, request, jsonify
import os, requests
app = Flask(__name__)

ACCOUNT_ID = "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"

# === TOKEN MERGED FIX ===
# 1. Try ENV first
RAW_TOKEN = os.getenv("METAAPI_TOKEN") or os.getenv("METAAP_TOKEN") or ""

# 2. HARDCODED FALLBACK - PASTE YOUR TOKEN HERE IF ENV FAILS
HARDCODED_TOKEN = ""  # <-- PASTE eyJ... HERE FOR QUICK TEST, leave "" if using ENV

if HARDCODED_TOKEN and len(HARDCODED_TOKEN) > 100:
    TOKEN = HARDCODED_TOKEN.strip()
    TOKEN_SOURCE = "HARDCODED"
else:
    TOKEN = RAW_TOKEN.strip().replace("\n","").replace("\r","").replace(" ","")
    TOKEN_SOURCE = "ENV METAAPI_TOKEN"

def H(): return {"auth-token": TOKEN, "Content-Type": "application/json"}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"

@app.route('/api/test_trade')
def test_trade():
    b = base()
    log = f"<b>V16 MERGED</b><br>"
    log += f"TOKEN SOURCE: {TOKEN_SOURCE}<br>"
    log += f"TOKEN SET: {bool(TOKEN)} LEN: {len(TOKEN)} STARTS: {TOKEN[:20]}...<br>"
    log += f"ALL META KEYS: {[k for k in os.environ.keys() if 'META' in k.upper()]}<br><br>"
    log += f"Using: {b}<br><br>"
    
    if not TOKEN or len(TOKEN) < 50:
        return log + "<b style='color:red'>TOKEN EMPTY! Add METAAPI_TOKEN in Render Service ENV or paste in HARDCODED_TOKEN line and re-deploy</b>"

    try:
        r = requests.get(f"{b}/accountInformation", headers=H(), timeout=15, verify=False)
        log += f"AccountInfo {r.status_code}: {r.text[:1500]}<br><br>"
    except Exception as e:
        log += f"AccountInfo ERR {e}<br><br>"

    try:
        r = requests.get(f"{b}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False)
        log += f"Current-Price {r.status_code}: {r.text[:1000]}<br><br>"
    except Exception as e:
        log += f"Price ERR {e}<br><br>"

    try:
        payload = {"actionType":"ORDER_TYPE_BUY","symbol":SYMBOL,"volume":0.01}
        r = requests.post(f"{b}/trade", headers=H(), json=payload, timeout=20, verify=False)
        log += f"BUY {r.status_code}: {r.text}<br><br>"
    except Exception as e:
        log += f"BUY ERR {e}<br><br>"

    return log

@app.route('/api/balance')
def bal():
    r = requests.get(f"{base()}/accountInformation", headers=H(), timeout=15, verify=False)
    return r.text, r.status_code

@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def h(): return f"OK V16 MERGED source={TOKEN_SOURCE} len={len(TOKEN)}"
@app.route('/analyze', methods=['POST'])
def analyze(): return jsonify({"live_price":4273,"symbol":SYMBOL,"direction":"BUY","confidence":85,"entry":4273,"stop_loss":4271,"tp1":4274,"tp2":4275,"tp3":4276})

if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
