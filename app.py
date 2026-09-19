from flask import Flask, send_file
import os, threading, time

app = Flask(__name__)
BOT_RUNNING = False

def sr72_logic():
    while True:
        if not BOT_RUNNING:
            time.sleep(2)
            continue
        print("SR-72: Checking Gold...")
        time.sleep(5)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/start')
def start():
    global BOT_RUNNING
    BOT_RUNNING = True
    return "STARTED"

@app.route('/stop')
def stop():
    global BOT_RUNNING
    BOT_RUNNING = False
    return "STOPPED"

threading.Thread(target=sr72_logic, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
