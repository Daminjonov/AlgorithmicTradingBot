import time
import MetaTrader5 as mt5
import numpy as np
from colorama import Fore, Style, init
import logging
import os
from collections import deque
import datetime

"""
CREDENTIALS TO COPY AND PASTE TO TERMINAL
-----------------------------------------
set MT5_ACCOUNT="160506438"
set MT5_PASSWORD="Dbk1991200104$"
set MT5_SERVER="ForexTimeFXTM-Demo01"
-----------------------------------------
"""


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

# Hardcoded credentials
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
    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Symbol {symbol} not found")
            return None, None
        return tick.bid, tick.ask
    except Exception as e:
        logging.exception(f"Exception in get_current_price: {e}")
        return None, None


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
    try:
        price = mt5.symbol_info_tick(symbol).ask if is_buy else mt5.symbol_info_tick(symbol).bid
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

        symbol_info = mt5.symbol_info(symbol)
        point = symbol_info.point

        stop_loss_diff = 0.200  # Fixed stop loss in points
        take_profit_diff = 0.015  # Fixed take profit in points

        sl = price - stop_loss_diff * point if is_buy else price + stop_loss_diff * point
        tp = price + take_profit_diff * point if is_buy else price - take_profit_diff * point

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
            "type_filling": mt5.ORDER_FILLING_FOK,  # Use IOC for better execution
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed: {result.comment}")
        else:
            action = "Buying" if is_buy else "Selling"
            logging.info(f"{action} {volume} units of {symbol} at price {price}. Stop Loss: {sl}, Take Profit: {tp}")

        return time.time()  # Return the order open time
    except Exception as e:
        logging.exception(f"Exception in submit_order: {e}")
        return None


# Function to get the number of active orders
def get_active_orders_count():
    try:
        positions = mt5.positions_get()
        if positions is None:
            logging.error("Error retrieving active positions")
            return 0
        return len(positions)
    except Exception as e:
        logging.exception(f"Exception in get_active_orders_count: {e}")
        return 0


# Function to close an order immediately
def close_order(ticket):
    try:
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
            logging.error(f"Failed to close order {ticket}: {result.comment}")
            return False
        return True
    except Exception as e:
        logging.exception(f"Exception in close_order: {e}")
        return False


# Function to implement the stop-out logic based on rapid price movement
def stop_out_logic(symbol, prev_price, current_price, threshold):
    try:
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return

        price_change = abs(current_price - prev_price)
        if price_change < threshold:
            return  # Skip if price change is not significant

        for position in positions:
            sl_price = position.sl

            # Calculate 50% level between Stop Loss and current price
            if position.type == mt5.ORDER_TYPE_BUY:
                stop_out_level = position.price_open - 0.5 * abs(position.price_open - sl_price)
            else:
                stop_out_level = position.price_open + 0.5 * abs(position.price_open - sl_price)

            # If the price crosses the stop-out level, close the position
            if (position.type == mt5.ORDER_TYPE_BUY and current_price <= stop_out_level) or \
               (position.type == mt5.ORDER_TYPE_SELL and current_price >= stop_out_level):
                logging.info(f"Rapid price movement detected. Stop-out logic triggered for position {position.ticket}. Closing order.")
                close_order(position.ticket)
    except Exception as e:
        logging.exception(f"Exception in stop_out_logic: {e}")


# Function to close orders that have been open for more than 15 minutes
def close_orders_older_than(duration_minutes):
    try:
        positions = mt5.positions_get()
        if not positions:
            return

        current_time = datetime.datetime.now()
        duration = datetime.timedelta(minutes=duration_minutes)

        for position in positions:
            order_open_time = datetime.datetime.fromtimestamp(position.time)
            if current_time - order_open_time > duration:
                logging.info(f"Order {position.ticket} has been open for more than {duration_minutes} minutes. Closing order.")
                close_order(position.ticket)
    except Exception as e:
        logging.exception(f"Exception in close_orders_older_than: {e}")


# Main function to trade Bollinger Bands and implement stop-out and time-based closing logic
def trade_bollinger_live(symbol, window, num_std_dev, volume):
    prices = deque(maxlen=60)  # Efficient handling of price data
    prev_price = None  # Store the previous price to detect rapid movement
    threshold = 0.002  # Define the price change threshold for stop-out activation

    logging.info(f"Starting Bollinger Bands Live Trading on {symbol} with window={window}, num_std_dev={num_std_dev}")

    try:
        while True:
            bid_price, ask_price = get_current_price(symbol)
            if bid_price is None or ask_price is None:
                print_message("Failed to get price, retrying...", Fore.RED)
                time.sleep(12)
                continue

            current_price = (bid_price + ask_price) / 2
            prices.append(current_price)

            if len(prices) >= window:
                upper_band, lower_band = calculate_bollinger_bands(list(prices)[-window:], window, num_std_dev)

                if upper_band and lower_band:
                    std_50 = np.std(list(prices)[-50:])
                    std_10 = np.std(list(prices)[-10:])
                    print_price_info(current_price, upper_band, lower_band, std_50, std_10)

                    # Trading logic
                    if current_price < lower_band and std_10 < std_50 and get_active_orders_count() < 5:
                        submit_order(symbol, volume, True)  # Buy
                    elif current_price > upper_band and std_10 > std_50 and get_active_orders_count() < 5:
                        submit_order(symbol, volume, False)  # Sell

                # Implement stop-out logic based on rapid price movement
                if prev_price is not None:
                    stop_out_logic(symbol, prev_price, current_price, threshold)
                prev_price = current_price

            # Close orders older than 15 minutes
            close_orders_older_than(15)

            time.sleep(5)  # Adjust sleep time based on your trading strategy
    except KeyboardInterrupt:
        print_message("Shutting down trading bot...", Fore.RED)
    finally:
        mt5.shutdown()


# Example usage:
trade_bollinger_live("USDJPY", 10, 2, 0.5)

