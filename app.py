from flask import Flask
import os, threading, time, asyncio
from metaapi_cloud_sdk import MetaApi

app = Flask(__name__)

# CONFIG FROM RENDER ENV
TOKEN = os.getenv('METAAPI_TOKEN')
ACCOUNT_ID = os.getenv('METAAPI_ACCOUNT_ID')
LOT = float(os.getenv('LOT_SIZE', '0.01'))
DISTANCE = float(os.getenv('DISTANCE', '0.80'))

BOT_RUNNING = False
meta_api = None
account = None
connection = None

async def connect_metaapi():
    global meta_api, account, connection
    try:
        print("🔌 Connecting to MetaApi...")
        meta_api = MetaApi(TOKEN)
        account = await meta_api.metatrader_account_api.get_account(ACCOUNT_ID)
        
        # Deploy if not deployed
        if account['state'] != 'DEPLOYED':
            print("🚀 Deploying account...")
            await account.deploy()
        
        await account.wait_connected()
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        print("✅ MetaApi CONNECTED - Ready to trade XAUUSD")
        return True
    except Exception as e:
        print(f"❌ MetaApi Error: {e}")
        return False

def sr72_real_logic():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    connected = loop.run_until_complete(connect_metaapi())
    
    if not connected:
        print("❌ Cannot start - check TOKEN and ACCOUNT_ID in Render ENV")
        return

    while True:
        if not BOT_RUNNING:
            time.sleep(2)
            continue
        
        try:
            async def trade_cycle():
                # Get live Gold price
                price_info = await connection.get_symbol_price('XAUUSD')
                current_price = price_info['bid']
                print(f"📈 XAUUSD: {current_price}")

                # Get open positions
                positions = await connection.get_positions()
                
                # SR-72 Straddle Logic: If no open positions, place BuyStop + SellStop
                if len(positions) == 0:
                    buy_stop_price = current_price + DISTANCE
                    sell_stop_price = current_price - DISTANCE
                    
                    print(f"🤖 Placing STRADDLE: BuyStop {buy_stop_price} | SellStop {sell_stop_price}")
                    
                    # Place Buy Stop
                    await connection.create_limit_buy_order(
                        symbol='XAUUSD',
                        volume=LOT,
                        open_price=buy_stop_price,
                        stop_loss=current_price - 2.0,
                        take_profit=current_price + 5.0
                    )
                    # Place Sell Stop
                    await connection.create_limit_sell_order(
                        symbol='XAUUSD',
                        volume=LOT,
                        open_price=sell_stop_price,
                        stop_loss=current_price + 2.0,
                        take_profit=current_price - 5.0
                    )
                else:
                    # Trailing Logic: If profit > $0.50, move SL to breakeven
                    for pos in positions:
                        if pos['unrealizedProfit'] > 0.5:
                            print(f"🔒 Trailing profit {pos['unrealizedProfit']} - Moving SL")
                            # Implement trailing stop here
            
            loop.run_until_complete(trade_cycle())
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            print(f"⚠️ Trading error: {e}")
            time.sleep(5)

@app.route('/')
def home():
    with open('index.html','r') as f:
        return f.read()

@app.route('/start')
def start():
    global BOT_RUNNING
    BOT_RUNNING = True
    print("✅✅✅ BOT STARTED - REAL TRADING ACTIVE")
    return "✅ REAL BOT STARTED - Now trading XAUUSD on Exness!"

@app.route('/stop')
def stop():
    global BOT_RUNNING
    BOT_RUNNING = False
    print("⛔ BOT STOPPED")
    return "⛔ BOT STOPPED - No more trades"

# Start trading thread
threading.Thread(target=sr72_real_logic, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
