import requests
import json
import telebot
import os
import logging
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
try:
    import systemd.journal
    journal_handler = systemd.journal.JournalHandler()
    journal_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(journal_handler)
    logging.getLogger().setLevel(logging.INFO)
except ImportError:
    logging.basicConfig(
        filename='bot.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )



# Initialize bot with token
token = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(token)
file_path = 'mono_currency.txt'
history_file_path = 'currency_history.csv'

# Configuration
DELTA_LIMIT = 0.4  # Threshold for a good exchange rate
API_URL = 'https://api.monobank.ua/bank/currency'
TELEGRAM_GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID"))

def fetch_currency_rate(currency_code: int):
    """
    Fetch currency rate by currency code from Monobank API.

    :param currency_code: Currency code (e.g., 840 for USD)
    :return: Dictionary with rate details, or None if not found
    """
    try:
        response = requests.get(API_URL, timeout=5)
        if response.status_code == 409:
            logging.warning("API request limit exceeded. Received status code 409.")
            return None
        response.raise_for_status()
        data = response.json()
        rate = next((entry for entry in data if entry.get('currencyCodeA') == currency_code), None)
        if not rate:
            logging.warning(f"Currency code {currency_code} not found in API response.")
        return rate
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching currency data: {e}")
        return None

def send_telegram_message(message_text):
    """
    Send a message to the Telegram group using Markdown formatting.

    :param message_text: Content of the message to send
    """
    try:
        bot.send_message(TELEGRAM_GROUP_ID, message_text, parse_mode='Markdown')
        logging.info("Message sent successfully.")
    except Exception as e:
        logging.error(f"Error sending Telegram message: {e}")

def save_value_to_file(value):
    """
    Save a value to the specified file.

    :param value: Value to save
    """
    try:
        with open(file_path, 'w') as file:
            file.write(str(value))
        logging.info("Value saved to file successfully.")
    except IOError as e:
        logging.error(f"Error writing to file: {e}")

def load_value_from_file():
    """
    Load a value from the specified file.

    :return: Value read from file, or None if file does not exist
    """
    try:
        if not os.path.exists(file_path):
            logging.info("File does not exist. Returning None.")
            return None
        with open(file_path, 'r') as file:
            data = file.read()
        return data
    except IOError as e:
        logging.error(f"Error reading file: {e}")
        return None

def save_to_history(rate_sell, rate_buy):
    """
    Save the current rates to the historical data file if they differ from the last saved rates.

    :param rate_sell: Current sell rate
    :param rate_buy: Current buy rate
    """
    try:
        # Check if history file exists and if the last entry matches the current rates
        if os.path.exists(history_file_path):
            with open(history_file_path, 'r') as csvfile:
                last_row = list(csv.reader(csvfile))[-1]
                last_rate_sell, last_rate_buy = float(last_row[1]), float(last_row[2])
                if rate_sell == last_rate_sell and rate_buy == last_rate_buy:
                    logging.info("Rates are the same as the last entry. Not saving to history.")
                    return

        # Save the new rates to history
        with open(history_file_path, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.now().isoformat(), rate_sell, rate_buy])
        logging.info("Rates saved to history.")
    except IOError as e:
        logging.error(f"Error writing to history file: {e}")
    except IndexError:
        # Handle case where the file exists but is empty
        with open(history_file_path, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.now().isoformat(), rate_sell, rate_buy])
        logging.info("Rates saved to history (first entry).")

def load_history():
    """
    Load historical data from the file.

    :return: List of historical rates within the last 30 days
    """
    try:
        if not os.path.exists(history_file_path):
            logging.info("History file does not exist. Returning empty history.")
            return []
        with open(history_file_path, 'r') as csvfile:
            reader = csv.reader(csvfile)
            cutoff_date = datetime.now() - timedelta(days=30)
            return [row for row in reader if datetime.fromisoformat(row[0]) >= cutoff_date]
    except IOError as e:
        logging.error(f"Error reading history file: {e}")
        return []
    except ValueError as e:
        logging.error(f"Error parsing date in history file: {e}")
        return []

def analyze_history(history):
    """
    Analyze historical data to calculate average, max, and min delta.

    :param history: List of historical rates
    :return: Tuple (average delta, max delta, min delta)
    """
    if not history:
        return None, None, None

    deltas = [float(row[1]) - float(row[2]) for row in history]
    avg_delta = sum(deltas) / len(deltas)
    max_delta = max(deltas)
    min_delta = min(deltas)

    return avg_delta, max_delta, min_delta

if __name__ == "__main__":
    logging.info("Starting currency bot...")

    us_dollar_rate = fetch_currency_rate(840)
    if not us_dollar_rate:
        logging.error("Unable to fetch currency data. Exiting.")
        exit()

    rate_sell = us_dollar_rate.get('rateSell')
    rate_buy = us_dollar_rate.get('rateBuy')

    if rate_sell is None or rate_buy is None:
        logging.error("Missing rate data in API response. Exiting.")
        exit()

    # Save current rates to history
    save_to_history(rate_sell, rate_buy)

    # Load and analyze historical data
    history = load_history()
    avg_delta, max_delta, min_delta = analyze_history(history)

    if avg_delta is not None:
        logging.info(f"Historical average delta: {avg_delta:.2f}, max delta: {max_delta:.2f}, min delta: {min_delta:.2f}")

    delta = rate_sell - rate_buy
    delta = f'{delta:.2f}'
    delta_percentage = f'{100 * float(delta) / rate_buy:.2f}%'

    previous_delta = load_value_from_file()
    if delta != previous_delta:
        symbol = "🟢" if float(delta) < DELTA_LIMIT else "🔴"
        exchange_message = (
            f'Хороший час для обміну. Різниця курсів менша за {DELTA_LIMIT:.2f}.\n'
            if float(delta) < DELTA_LIMIT else f"Поки рекомендуємо притримати грошики, різниця курсів становить {DELTA_LIMIT}.\n"
        )
        detailed_message = (
            f"{symbol} *Поточна різниця курсу $:* `{delta}` (`{rate_sell:.2f} - {rate_buy:.2f}`)\n"
            f"*Різниця у відсотках:* `{delta_percentage}`\n"
            f"{exchange_message}\n"
            f"*Історичні дані (за останні 30 днів):*\n"
            f"- *Середня різниця:* `{avg_delta:.2f}`\n"
            f"- *Максимальна різниця* `{max_delta:.2f}`\n"
            f"- *Мінімальна різниця:* `{min_delta:.2f}`"
        )
        logging.info(f"New delta detected: {delta}. Sending message.")
        send_telegram_message(detailed_message)
        save_value_to_file(delta)
    else:
        logging.info("No significant change in currency delta. No message sent.")
