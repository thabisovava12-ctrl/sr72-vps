from flask import Flask, send_file
import threading, time
app = Flask(__name__)
BOT=False
def bot_loop():
    while True:
        if BOT: print("SR-72 running... XAUUSD straddle check")
        time.sleep(5)
@app.route('/')
def home(): return send_file('index.html')
@app.route('/start')
def start(): 
    global BOT; BOT=True; return "BOT STARTED"
@app.route('/stop')
def stop():
    global BOT; BOT=False; return "BOT STOPPED"
threading.Thread(target=bot_loop, daemon=True).start()
app.run(host='0.0.0.0', port=10000)
