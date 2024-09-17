# AlgorithmicTradingBot

This repository contains a fully functional automated trading bot that uses the MetaTrader5 platform to execute trades based on Bollinger Bands and standard deviation analysis. The bot is optimized for high-frequency trading with robust error handling, logging, and stop-out logic.

## Features

- **Bollinger Bands Strategy**: The bot uses Bollinger Bands to determine buy and sell signals.
- **Standard Deviation Analysis**: Compares the standard deviation of the last 10 price windows against the previous 50 windows to predict market trends.
- **Stop-Out Logic**: Detects rapid price movements and closes positions if necessary.
- **Time-Based Closing**: Automatically closes trades that have been open for more than 15 minutes.
- **Customizable Parameters**: Adjust the Bollinger Bands window size, standard deviation threshold, and volume for each trade.
- **Multiple Orders Management**: The bot will only open up to 5 simultaneous orders at any given time, pausing new orders until some are closed.
- **Secure Credentials**: MetaTrader5 credentials are handled using environment variables for security.

## Requirements

Before running the bot, make sure you have installed the required Python packages:

```bash
pip install numpy<2 MetaTrader5
pip pip install colorama

