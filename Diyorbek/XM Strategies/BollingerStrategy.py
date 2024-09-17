import time
import MetaTrader5 as mt5
import numpy as np

# Initialize and log in to MetaTrader5
if not mt5.initialize():
    print("Failed to initialize MT5")
    quit()

account = 165186298  # Replace with your account number
password = "Dbk1991200104$"
server = "XMGlobal-MT5 2"  # Replace with your broker's server

if not mt5.login(account, password, server):
    print(f"Login failed: {mt5.last_error()}")
    mt5.shutdown()
    quit()
else:
    print(f"Logged in to account {account}")

# Function to get the current price from MetaTrader5
def get_current_price(symbol):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Symbol {symbol} not found")
        return None, None
    return tick.bid, tick.ask

# Function to calculate Bollinger Bands
def calculate_bollinger_bands(prices, window, num_std_dev):
    if len(prices) < window:
        return None, None
    sma = np.mean(prices)
    std_dev = np.std(prices)
    upper_band = sma + num_std_dev * std_dev
    lower_band = sma - num_std_dev * std_dev
    return upper_band, lower_band

# Function to submit a trade order in MetaTrader5
def submit_order(symbol, volume, is_buy):
    # Get the price depending on the type of order (buy/sell)
    price = mt5.symbol_info_tick(symbol).ask if is_buy else mt5.symbol_info_tick(symbol).bid
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

    # Define fixed stop loss and take profit differences
    stop_loss_diff = 0.300
    take_profit_diff = 0.019

    # Set Stop Loss and Take Profit based on the price and fixed difference
    sl = price - stop_loss_diff if is_buy else price + stop_loss_diff
    tp = price + take_profit_diff if is_buy else price - take_profit_diff

    # Prepare the order request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": 234000,
        "comment": "Bollinger Bands trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Send the order and handle the result
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.comment}")
    else:
        action = "Buying" if is_buy else "Selling"
        print(f"{action} {volume} units of {symbol} at price {price}. Stop Loss: {sl}, Take Profit: {tp}")

# Function to trade Bollinger Bands with MetaTrader5
def trade_bollinger_live(symbol, window, num_std_dev, volume):
    prices = []
    positions = []
    balance = 0

    while True:
        # Get current price
        bid_price, ask_price = get_current_price(symbol)
        if bid_price is None or ask_price is None:
            time.sleep(12)  # Adjusted to 12 seconds for high-frequency trading
            continue
        current_price = (bid_price + ask_price) / 2
        prices.append(current_price)

        if len(prices) > window:
            prices.pop(0)
            upper_band, lower_band = calculate_bollinger_bands(prices, window, num_std_dev)

            if upper_band is None or lower_band is None:
                print("Not enough data to calculate Bollinger Bands")
                continue

            print(f"Current price: {current_price}, Upper band: {upper_band}, Lower band: {lower_band}")

            # Buy logic
            if current_price < lower_band and not positions:
                submit_order(symbol, volume, is_buy=True)
                positions.append(current_price)
                print(f"Opening Buy order at price {current_price}")

            # Sell logic
            elif current_price > upper_band and positions:
                buy_price = positions.pop(0)
                submit_order(symbol, volume, is_buy=False)
                profit = (current_price - buy_price) * volume
                balance += profit
                print(f"Order Closed Take Profit at price {current_price}. Profit: {profit:.2f}, Balance: {balance:.2f}")

        time.sleep(5)  # Adjusted to 3 seconds for high-frequency trading

# Example usage
symbol = "USDJPY"
trade_bollinger_live(symbol, window=10, num_std_dev=2, volume=0.05)


# Shutdown MetaTrader5
mt5.shutdown()
