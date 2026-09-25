from flask import Flask, send_from_directory, jsonify
import os, requests
app = Flask(__name__)
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID") or "93f7b19b-d414-4302-bec7-86f6bf59a7ea"
SYMBOL = "XAUUSDc"
REGION = "new-york"
TOKEN = (os.getenv("METAAPI_TOKEN") or "").strip()
LOT = 0.01
STRADDLE = 2.00
SL_DIST = 2.50
def H(): return {"auth-token": TOKEN, "Content-Type":"application/json"}
def base(): return f"https://mt-client-api-v1.{REGION}.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}"
@app.route('/')
def idx(): return send_from_directory('.','index.html')
@app.route('/health')
def health(): return "OK V28.1 MERGED ON V13 - VIDEO 0.01"
@app.route('/api/balance')
def bal():
    r = requests.get(f"{base()}/accountInformation", headers=H(), timeout=15, verify=False)
    return r.text, r.status_code
@app.route('/api/price')
def price():
    r = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code
@app.route('/api/positions')
def positions():
    r = requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code
@app.route('/api/orders')
def orders():
    r = requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False)
    return r.text, r.status_code
@app.route('/api/historyOrders')
def historyOrders():
    r = requests.get(f"{base()}/historyOrders", headers=H(), timeout=15, verify=False)
    return r.text, r.status_code
@app.route('/api/deals')
def deals():
    try:
        r = requests.get(f"{base()}/historyOrders?limit=100", headers=H(), timeout=15, verify=False).json()
        # format for your V13 display
        out=[]
        for o in r[-30:]:
            out.append({"time":o.get('doneTime') or o.get('updateTime'),"type":o.get('type'),"profit":o.get('profit',0)})
        return jsonify(out)
    except:
        return jsonify([])
@app.route('/api/start_straddle', methods=['POST'])
def start_straddle():
    pr = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
    bid, ask = pr['bid'], pr['ask']
    buy_p = round(ask + STRADDLE, 2)
    sell_p = round(bid - STRADDLE, 2)
    b1 = {"actionType":"ORDER_TYPE_BUY_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":buy_p,"stopLoss":round(buy_p-SL_DIST,2)}
    s1 = {"actionType":"ORDER_TYPE_SELL_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":sell_p,"stopLoss":round(sell_p+SL_DIST,2)}
    requests.post(f"{base()}/trade", headers=H(), json=b1, timeout=15, verify=False)
    requests.post(f"{base()}/trade", headers=H(), json=s1, timeout=15, verify=False)
    return jsonify({"buy_stop":buy_p,"sell_stop":sell_p,"lot":LOT,"mode":"VIDEO CLONE 0.01"})
@app.route('/api/trail', methods=['POST'])
def trail():
    logs=[]
    try:
        pos_r = requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
        pr = requests.get(f"{base()}/symbols/{SYMBOL}/current-price", headers=H(), timeout=10, verify=False).json()
        bid, ask = pr['bid'], pr['ask']
        orders_r = requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
        for pos in pos_r:
            if pos.get('symbol')!=SYMBOL: continue
            entry=pos['openPrice']; sl=pos.get('stopLoss',0) or 0; pid=pos['id']
            if pos['type']=='POSITION_TYPE_BUY':
                prof=ask-entry
                if prof>=1.00 and sl<entry:
                    ns=round(entry+0.10,2)
                    requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_BUY","symbol":SYMBOL,"volume":pos['volume'],"positionId":pid,"stopLoss":ns}, timeout=10, verify=False)
                    logs.append(f"BUY BE->{ns}")
                elif prof>=1.20:
                    ns=round(ask-0.40,2)
                    if ns>sl:
                        requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_BUY","symbol":SYMBOL,"volume":pos['volume'],"positionId":pid,"stopLoss":ns}, timeout=10, verify=False)
                        logs.append(f"BUY TRAIL->{ns}")
            else:
                prof=entry-bid
                if prof>=1.00 and (sl==0 or sl>entry):
                    ns=round(entry-0.10,2)
                    requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_SELL","symbol":SYMBOL,"volume":pos['volume'],"positionId":pid,"stopLoss":ns}, timeout=10, verify=False)
                    logs.append(f"SELL BE->{ns}")
                elif prof>=1.20:
                    ns=round(bid+0.40,2)
                    if sl==0 or ns<sl:
                        requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_SELL","symbol":SYMBOL,"volume":pos['volume'],"positionId":pid,"stopLoss":ns}, timeout=10, verify=False)
                        logs.append(f"SELL TRAIL->{ns}")
        if len([o for o in orders_r if o.get('symbol')==SYMBOL])==0 and len([p for p in pos_r if p.get('symbol')==SYMBOL])==0:
            buy_p=round(ask+STRADDLE,2); sell_p=round(bid-STRADDLE,2)
            b1={"actionType":"ORDER_TYPE_BUY_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":buy_p,"stopLoss":round(buy_p-SL_DIST,2)}
            s1={"actionType":"ORDER_TYPE_SELL_STOP","symbol":SYMBOL,"volume":LOT,"openPrice":sell_p,"stopLoss":round(sell_p+SL_DIST,2)}
            requests.post(f"{base()}/trade", headers=H(), json=b1, timeout=15, verify=False)
            requests.post(f"{base()}/trade", headers=H(), json=s1, timeout=15, verify=False)
            logs.append(f"AUTO {buy_p}/{sell_p}")
        return jsonify({"logs":logs,"bid":bid,"ask":ask})
    except Exception as e:
        return jsonify({"error":str(e),"logs":logs}),500
@app.route('/api/close_all', methods=['POST'])
def close_all():
    try:
        o=requests.get(f"{base()}/orders", headers=H(), timeout=10, verify=False).json()
        for od in o: requests.post(f"{base()}/trade", headers=H(), json={"actionType":"ORDER_TYPE_CANCEL","orderId":od['id']}, timeout=10, verify=False)
    except: pass
    try:
        p=requests.get(f"{base()}/positions", headers=H(), timeout=10, verify=False).json()
        for pos in p:
            side="SELL" if pos['type']=='POSITION_TYPE_BUY' else "BUY"
            requests.post(f"{base()}/trade", headers=H(), json={"actionType":f"ORDER_TYPE_{side}","symbol":pos['symbol'],"volume":pos['volume'],"positionId":pos['id']}, timeout=10, verify=False)
    except: pass
    return jsonify({"closed":True})
if __name__=='__main__': app.run(host='0.0.0.0',port=10000)
