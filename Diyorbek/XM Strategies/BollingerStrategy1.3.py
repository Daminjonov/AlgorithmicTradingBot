import time
import MetaTrader5 as mt5
import numpy as np

# Initialize and log in to MetaTrader5
if not mt5.initialize():
    print("Failed to initialize MT5")
    quit()

account = 300547816  # Replace with your account number
password = "Dbk1991200104$"
server = "XMGlobal-MT5 6"  # Replace with your broker's server

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
    price = mt5.symbol_info_tick(symbol).ask if is_buy else mt5.symbol_info_tick(symbol).bid
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

    stop_loss_diff = 0.200  # Fixed stop loss
    take_profit_diff = 0.019  # Fixed take profit

    sl = price - stop_loss_diff if is_buy else price + stop_loss_diff
    tp = price + take_profit_diff if is_buy else price - take_profit_diff

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

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.comment}")
    else:
        action = "Buying" if is_buy else "Selling"
        print(f"{action} {volume} units of {symbol} at price {price}. Stop Loss: {sl}, Take Profit: {tp}")

# Function to get the number of active orders
def get_active_orders_count():
    positions = mt5.positions_get()
    if positions is None:
        print("Error retrieving active positions")
        return 0
    return len(positions)

# Function to close an order immediately
def close_order(ticket):
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return False

    position = position[0]
    symbol = position.symbol
    volume = position.volume
    order_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY

    price = mt5.symbol_info_tick(symbol).bid if position.type == 0 else mt5.symbol_info_tick(symbol).ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": 10,
        "magic": 234000,
        "comment": "Stop-Out logic trade close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close order {ticket}: {result.comment}")
        return False
    return True

# Function to implement the stop-out logic based on rapid price movement
def stop_out_logic(symbol, prev_price, current_price, threshold):
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return

    price_change = abs(current_price - prev_price)
    if price_change < threshold:
        return  # Skip if price change is not significant

    for position in positions:
        sl_price = position.sl

        # Calculate 50% level between Stop Loss and current price
        stop_out_level = sl_price + 0.5 * (position.price_open - sl_price) if position.type == mt5.ORDER_TYPE_BUY else sl_price - 0.5 * (sl_price - position.price_open)

        # If the price crosses the stop-out level, close the position
        if (position.type == mt5.ORDER_TYPE_BUY and current_price <= stop_out_level) or (position.type == mt5.ORDER_TYPE_SELL and current_price >= stop_out_level):
            print(f"Rapid price movement detected. Stop-out logic triggered for position {position.ticket}. Closing order.")
            close_order(position.ticket)

# Main function to trade Bollinger Bands and implement stop-out logic
def trade_bollinger_live(symbol, window, num_std_dev, volume):
    prices = []
    balance = 0
    prev_price = None  # Store the previous price to detect rapid movement
    threshold = 0.002  # Define the price change threshold for stop-out activation

    while True:
        bid_price, ask_price = get_current_price(symbol)
        if bid_price is None or ask_price is None:
            time.sleep(12)
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

            # Check the number of active orders
            active_orders = get_active_orders_count()
            if active_orders >= 5:
                print("Maximum 5 active orders reached, waiting for an order to close.")
                time.sleep(10)
                continue

            # Buy logic
            if current_price < lower_band:
                submit_order(symbol, volume, is_buy=True)
                print(f"Opening Buy order at price {current_price}")

            # Sell logic
            elif current_price > upper_band:
                submit_order(symbol, volume, is_buy=False)
                print(f"Opening Sell order at price {current_price}")

            # Apply stop-out logic only if rapid price movement is detected
            if prev_price is not None:
                stop_out_logic(symbol, prev_price, current_price, threshold)

            # Update the previous price
            prev_price = current_price

        time.sleep(5)

# Example usage
symbol = "USDJPY"
trade_bollinger_live(symbol, window=10, num_std_dev=2, volume=0.01)

# Shutdown MetaTrader5
mt5.shutdown()
