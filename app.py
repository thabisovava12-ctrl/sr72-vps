from flask import Flask, send_from_directory, request, jsonify
import os, requests
app = Flask(__name__)

ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()

LOT = 0.01
STRADDLE = 0.80
TRAIL = 0.50

def H(): return {"auth-token": TOKEN, "Content-Type":"application/json"}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"

@app.route('/')
def idx(): return send_from_directory('.','index.html')

@app.route('/health')
def health(): return f"OK V20 REAL STRADDLE LIVE LOT={LOT}"

@app.route('/api/balance')
def bal():
    r = requests.get(f"{base()}/accountInformation", headers=H(), timeout=15, verify=False)
    return r.text, r.status_code

@app.route('/api/price')
def price():
    r = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code

@app.route('/api/positions')
def pos():
    r = requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code

@app.route('/api/orders')
def orders():
    r = requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code

@app.route('/api/start_straddle', methods=['POST'])
def start_straddle():
    pr = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
    bid, ask = pr['bid'], pr['ask']
    curr = (bid+ask)/2
    buy_p = round(ask + STRADDLE, 2)
    sell_p = round(bid - STRADDLE, 2)

    b1 = {"actionType":"ORDER_TYPE_BUY_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":buy_p,"stopLoss":round(buy_p-1.10,2),"takeProfit":round(buy_p+3.0,2)}
    s1 = {"actionType":"ORDER_TYPE_SELL_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":sell_p,"stopLoss":round(sell_p+1.10,2),"takeProfit":round(sell_p-3.0,2)}
    
    r1 = requests.post(f"{base()}/trade", headers=H(), json=b1, timeout=15, verify=False)
    r2 = requests.post(f"{base()}/trade", headers=H(), json=s1, timeout=15, verify=False)

    return jsonify({
        "status":"REAL STRADDLE PLACED",
        "current": curr,
        "buy_stop": buy_p,
        "sell_stop": sell_p,
        "buy_resp": r1.json(),
        "sell_resp": r2.json()
    })

@app.route('/api/close_all', methods=['POST'])
def close_all():
    # close orders
    o = requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
    for order in o:
        try: requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_CANCEL","orderId":order['id']}, timeout=10, verify=False)
        except: pass
    return jsonify({"closed_orders": len(o)})

@app.route('/analyze', methods=['POST'])
def analyze():
    pr = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
    return jsonify({"live_price": pr.get('bid'), "symbol": SYMBOL, "direction": "STRADDLE", "confidence": 88})

if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
