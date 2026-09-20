from flask import Flask
import os, threading, time

app = Flask(__name__)
BOT_RUNNING = False

def sr72_logic():
    while True:
        if BOT_RUNNING:
            print("SR-72 RUNNING: Checking XAUUSD...")
            # Here it will place real trades via MetaApi using your ENV vars
        time.sleep(3)

@app.route('/')
def home():
    with open('index.html','r') as f:
        return f.read()

@app.route('/start')
def start():
    global BOT_RUNNING
    BOT_RUNNING = True
    return "✅ BOT STARTED - Running 24/7 on VPS!"

@app.route('/stop')
def stop():
    global BOT_RUNNING
    BOT_RUNNING = False
    return "⛔ BOT STOPPED"

threading.Thread(target=sr72_logic, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
