import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import time
import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Telegram Bot Token (Read from environment variable)
TELEGRAM_BOT_TOKEN = os.getenv("7782537963:AAHWYAHErQAaVzHC5StwpcUsYgvk6Q2l0jY")

# Telegram Chat ID (Optional, bot responds to user dynamically)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6865264153")

# Nifty 50 tickers (partial list, expand as needed)
NIFTY_50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "ASIANPAINT.NS"
]

# Function to fetch stock data
def fetch_stock_data(ticker, period="60d", interval="1d"):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period, interval=interval)
        if data.empty:
            logger.warning(f"No data fetched for {ticker}")
            return None
        return data
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None

# Function to calculate technical indicators
def calculate_indicators(data):
    try:
        # Moving Averages
        data['SMA20'] = ta.sma(data['Close'], length=20)
        data['SMA50'] = ta.sma(data['Close'], length=50)
        
        # RSI
        data['RSI'] = ta.rsi(data['Close'], length=14)
        
        # Volume Moving Average
        data['Volume_MA20'] = ta.sma(data['Volume'], length=20)
        
        # Resistance (highest high in last 30 days)
        data['Resistance'] = data['High'].rolling(window=30).max()
        
        return data
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return None

# Function to detect bullish breakout
def detect_breakout(ticker, data):
    breakout_signals = []
    try:
        for i in range(1, len(data)):
            # Breakout conditions
            if (data['Close'].iloc[i] > data['Resistance'].iloc[i-1] and
                data['Volume'].iloc[i] > 1.5 * data['Volume_MA20'].iloc[i] and
                50 <= data['RSI'].iloc[i] <= 70 and
                data['SMA20'].iloc[i] > data['SMA50'].iloc[i]):  # Golden Cross
                signal = {
                    'Ticker': ticker,
                    'Date': data.index[i].strftime('%Y-%m-%d'),
                    'Close': round(data['Close'].iloc[i], 2),
                    'Volume': int(data['Volume'].iloc[i]),
                    'Volume_MA20': int(data['Volume_MA20'].iloc[i]),
                    'RSI': round(data['RSI'].iloc[i], 2),
                    'Resistance': round(data['Resistance'].iloc[i-1], 2)
                }
                breakout_signals.append(signal)
        return breakout_signals
    except Exception as e:
        logger.error(f"Error detecting breakout for {ticker}: {e}")
        return []

# Function to scan for breakouts and return results as a string
def scan_breakouts(tickers, period="60d", interval="1d"):
    all_breakouts = []
    invalid_tickers = []

    for ticker in tickers:
        logger.info(f"Scanning {ticker} for bullish breakouts...")
        data = fetch_stock_data(ticker, period, interval)
        if data is None:
            invalid_tickers.append(ticker)
            continue
        
        data = calculate_indicators(data)
        if data is None:
            continue
        
        breakouts = detect_breakout(ticker, data)
        if breakouts:
            all_breakouts.extend(breakouts)
        
        time.sleep(1)  # Avoid hitting API rate limits
    
    if invalid_tickers:
        logger.warning(f"Invalid tickers: {invalid_tickers}")
    
    if not all_breakouts:
        result = "No breakouts detected."
        if invalid_tickers:
            result += f"\nNote: Could not fetch data for the following tickers: {', '.join(invalid_tickers)}"
        return result
    
    # Format the results as a string
    result = "🚀 Bullish Breakout Results:\n\n"
    for signal in all_breakouts:
        message = (
            f"Ticker: {signal['Ticker']}\n"
            f"Date: {signal['Date']}\n"
            f"Close: ₹{signal['Close']}\n"
            f"Volume: {signal['Volume']} (vs {signal['Volume_MA20']} MA)\n"
            f"RSI: {signal['RSI']}\n"
            f"Resistance Broken: ₹{signal['Resistance']}\n"
            f"Action: Consider buying above ₹{signal['Close']}, "
            f"Stop Loss: ₹{round(signal['Close'] * 0.98, 2)}, "
            f"Target: ₹{round(signal['Close'] * 1.05, 2)}\n\n"
        )
        result += message
    
    if invalid_tickers:
        result += f"Note: Could not fetch data for the following tickers: {', '.join(invalid_tickers)}"
    
    return result

# Telegram bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    await update.message.reply_text(
        "Hello! I am your Bullish Breakout Scanner Bot. 🎉\n"
        "Use /scan to scan Nifty 50 stocks for bullish breakouts.\n"
        "You can also specify tickers, e.g., /scan RELIANCE.NS TCS.NS\n"
        "Use /help for more information."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the command /help is issued."""
    await update.message.reply_text(
        "Here’s how to use me:\n"
        "/start - Start the bot and get a welcome message.\n"
        "/scan - Scan Nifty 50 stocks for bullish breakouts.\n"
        "/scan <ticker1> <ticker2> - Scan specific tickers, e.g., /scan RELIANCE.NS TCS.NS\n"
        "/help - Show this help message.\n\n"
        "I’ll notify you of any bullish breakouts with suggested actions!"
    )

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run the breakout scanner when the command /scan is issued."""
    tickers = context.args if context.args else NIFTY_50_TICKERS
    await update.message.reply_text(f"Scanning {', '.join(tickers)} for bullish breakouts... Please wait.")
    result = scan_breakouts(tickers)
    await update.message.reply_text(result)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")
    await update.message.reply_text("An error occurred. Please try again later.")

# Main function to set up and run the Telegram bot
def main():
    # Initialize the Application with your bot token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("scan", scan_command))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Bot started. Listening for commands...")
    application.run_polling()

if __name__ == "__main__":
    main()