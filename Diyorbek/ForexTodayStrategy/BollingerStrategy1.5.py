import time
import MetaTrader5 as mt5
import numpy as np
from colorama import Fore, Style, init


# Initialize colorama for colored text in the console
init()

# Helper function to print colorful messages
def print_message(msg, color=Fore.WHITE):
    print(f"{color}{msg}{Style.RESET_ALL}")

# Function to create a nice ASCII separator
def print_separator():
    print(f"{Fore.YELLOW}---|||----------------------------------------------------------|||---{Style.RESET_ALL}")

# Function to print price information in a table-like format
def print_price_info(current_price, upper_band, lower_band, std_50, std_10):
    print_separator()
    print_message(f"Price Information", Fore.CYAN)
    print(f"{Fore.CYAN}Current Price:{Style.RESET_ALL} {current_price:.5f} | {Fore.CYAN}Upper Band:{Style.RESET_ALL} {upper_band:.5f} | {Fore.CYAN}Lower Band:{Style.RESET_ALL} {lower_band:.5f}")
    print(f"{Fore.CYAN}Standard Deviation (50):{Style.RESET_ALL} {std_50:.5f} | {Fore.CYAN}Standard Deviation (10):{Style.RESET_ALL} {std_10:.5f}")
    print_separator()

# Initialize and log in to MetaTrader5
if not mt5.initialize():
    print("Failed to initialize MT5")
    quit()

account = 160506438  # Replace with your account number
password = "Dbk1991200104$"
server = "ForexTimeFXTM-Demo01"  # Replace with your broker's server

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


# Function to submit a trade order in MetaTrader5 and track its open time
def submit_order(symbol, volume, is_buy):
    price = mt5.symbol_info_tick(symbol).ask if is_buy else mt5.symbol_info_tick(symbol).bid
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

    stop_loss_diff = 0.150  # Fixed stop loss
    take_profit_diff = 0.015  # Fixed take profit

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
        "type_filling": mt5.ORDER_FILLING_FOK,  # Try FOK or another filling type
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.comment}")
    else:
        action = "Buying" if is_buy else "Selling"
        print(f"{action} {volume} units of {symbol} at price {price}. Stop Loss: {sl}, Take Profit: {tp}")

    return time.time()  # Return the order open time


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
        "type_filling": mt5.ORDER_FILLING_FOK,
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


# Function to close orders that have been open for more than 15 minutes
def close_orders_older_than(duration_minutes):
    positions = mt5.positions_get()
    if not positions:
        return

    current_time = time.time()
    duration_seconds = duration_minutes * 60

    for position in positions:
        order_open_time = position.time  # This gives the order opening time in Unix timestamp
        if current_time - order_open_time > duration_seconds:
            print(f"Order {position.ticket} has been open for more than {duration_minutes} minutes. Closing order.")
            close_order(position.ticket)


# Main function to trade Bollinger Bands and implement stop-out and time-based closing logic
# Updated trade function with colored messages and table-like outputs
def trade_bollinger_live(symbol, window, num_std_dev, volume):
    prices = []
    prev_price = None  # Store the previous price to detect rapid movement
    threshold = 0.002  # Define the price change threshold for stop-out activation

    print_message(f"Starting Bollinger Bands Live Trading on {symbol} with window={window}, num_std_dev={num_std_dev}", Fore.GREEN)

    while True:
        bid_price, ask_price = get_current_price(symbol)
        if bid_price is None or ask_price is None:
            print_message("Failed to get price, retrying...", Fore.RED)
            time.sleep(12)
            continue

        current_price = (bid_price + ask_price) / 2
        prices.append(current_price)

        if len(prices) > 60:  # Ensure there are at least 60 price points
            prices.pop(0)

            # Calculate Bollinger Bands for the last 10 windows
            upper_band, lower_band = calculate_bollinger_bands(prices[-10:], window, num_std_dev)

            # Calculate standard deviation for the last 50 windows
            std_50 = np.std(prices[-50:])
            std_10 = np.std(prices[-10:])

            if upper_band is None or lower_band is None:
                print_message("Not enough data to calculate Bollinger Bands", Fore.RED)
                continue

            # Print price information in a table-like structure
            print_price_info(current_price, upper_band, lower_band, std_50, std_10)

            # Check the number of active orders
            active_orders = get_active_orders_count()
            if active_orders >= 5:
                print_message("Maximum 5 active orders reached, waiting for an order to close.", Fore.YELLOW)
                time.sleep(10)
                continue

            # Buy logic based on Bollinger Bands and volatility comparison
            if current_price < lower_band and std_10 < std_50:
                submit_order(symbol, volume, is_buy=True)
                print_message(f"Opening Buy order at price {current_price:.5f}", Fore.GREEN)

            # Sell logic based on Bollinger Bands and volatility comparison
            elif current_price > upper_band and std_10 > std_50:
                submit_order(symbol, volume, is_buy=False)
                print_message(f"Opening Sell order at price {current_price:.5f}", Fore.GREEN)

            # Apply stop-out logic if rapid price movement is detected
            if prev_price is not None:
                stop_out_logic(symbol, prev_price, current_price, threshold)

            # Close orders that have been open for more than 15 minutes
            close_orders_older_than(15)

            # Update the previous price
            prev_price = current_price

        time.sleep(5)

    print_message("Shutting down trading...", Fore.RED)

# Example usage
symbol = "USDJPY"
trade_bollinger_live(symbol, window=10, num_std_dev=2, volume=0.50)

# Shutdown MetaTrader5
mt5.shutdown()