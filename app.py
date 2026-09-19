from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>SR72 VPS is LIVE! ✅</h1>
    <p>Your bot is running 24/7</p>
    <p>Status: Online</p>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
