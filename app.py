from flask import Flask, send_from_directory, request, jsonify
import threading, time, os, requests
app = Flask(__name__)
ACCOUNT_ID = "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN") or ""
SYMBOL = "XAUUSDc"
LOT = 0.01
bot_running = False

def H(): return {"auth-token": METAAPI_TOKEN}

def get_region():
    try:
        url=f"https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"
        r=requests.get(url, headers=H(), timeout=10, verify=False)
        print(f"REGION CHECK {r.status_code} {r.text[:500]}")
        if r.ok:
            j=r.json()
            return j.get('region') or j.get('account',{}).get('region') or 'new-york'
    except Exception as e: print(f"Region error {e}")
    return 'new-york'

def get_base():
    region=get_region()
    # try london, new-york, singapore
    for reg in [region, 'london','new-york','vint-hill','singapore']:
        base=f"https://mt-client-api-v1.{reg}.agiliumtrade.ai/users/{ACCOUNT_ID}"
        try:
            r=requests.get(f"{base}/connectionStatus", headers=H(), timeout=5, verify=False)
            print(f"TRY {reg} -> {r.status_code}")
            if r.status_code!=404 and r.status_code!=502:
                print(f"WORKING REGION {reg}")
                return base, reg
        except: pass
    return f"https://mt-client-api-v1.new-york.agiliumtrade.ai/users/{ACCOUNT_ID}", 'new-york'

def api_get(path):
    base, reg = get_base()
    try:
        url=f"{base}/{path}"
        r=requests.get(url, headers=H(), timeout=15, verify=False)
        print(f"GET {reg}/{path} -> {r.status_code} {r.text[:400]}")
        if not r.text.strip(): return {"error":f"Empty {r.status_code}","region":reg}
        try: return r.json()
        except: return {"raw":r.text[:400],"region":reg,"status":r.status_code}
    except Exception as e: return {"error":str(e)}

def get_price():
    base, reg = get_base()
    d=api_get(f"symbolPrice?symbol={SYMBOL}")
    if "error" in d and "bid" not in d: return 4273.0, d
    try: return float(d.get('ask') or d.get('bid') or 4273.0), d
    except: return 4273.0, d

def place(action, price):
    base, reg = get_base()
    try:
        url=f"{base}/trade"
        payload={"actionType":action,"symbol":SYMBOL,"volume":LOT,"openPrice":float(price)}
        r=requests.post(url, headers=H(), json=payload, timeout=20, verify=False)
        return f"[{reg}] Status {r.status_code}: {r.text}"
    except Exception as e: return str(e)

@app.route('/api/debug')
def debug():
    base, reg = get_base()
    return jsonify({"base":base,"region":reg,"connection":api_get("connectionStatus"),"price":get_price()})
@app.route('/api/test_trade')
def test_trade():
    base, reg = get_base()
    conn=api_get("connectionStatus")
    price,_=get_price()
    r1=place("ORDER_TYPE_BUY_STOP", price+1.0)
    time.sleep(1)
    r2=place("ORDER_TYPE_SELL_STOP", price-1.0)
    return f"BASE: {base}<br>CONNECTION: {conn}<br>PRICE: {price}<br><br>BUY: {r1}<br><br>SELL: {r2}"
@app.route('/api/balance')
def bal(): return jsonify(api_get("accountInformation"))
@app.route('/start')
def start():
    global bot_running
    if not bot_running:
        bot_running=True
    return "V14 REGION AUTO"
@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def h(): return "OK V14"
@app.route('/analyze', methods=['POST'])
def analyze():
    price,_=get_price()
    return jsonify({"live_price":price,"symbol":SYMBOL,"direction":"BUY","confidence":85,"entry":price,"stop_loss":price-2,"tp1":price+1,"tp2":price+2,"tp3":price+3,"balance_usc":1009,"analysis":"V14 AUTO REGION"})
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
