import os
from pathlib import Path
from dotenv import load_dotenv

# Завантажуємо змінні оточення
load_dotenv()

# Базові шляхи
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"

# Створюємо директорію для логів, якщо її немає
LOGS_DIR.mkdir(exist_ok=True)

# MongoDB налаштування
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING", "mongodb://192.168.1.10:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "currency_bot")

# Telegram налаштування
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID_USD = int(os.getenv("TELEGRAM_GROUP_ID_USD", 0))
TELEGRAM_GROUP_ID_EUR = int(os.getenv("TELEGRAM_GROUP_ID_EUR", 0))
TELEGRAM_GROUP_USD_TO_EUR = int(os.getenv("TELEGRAM_GROUP_USD_TO_EUR", 0))
TELEGRAM_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", 0))

# Налаштування логування
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOGS_DIR / "currency_bot.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Налаштування для банків
BANK_REQUEST_TIMEOUT = 5  # секунд

# Налаштування аналізу
DELTA_PERCENTAGE_LIMIT = 1.0
CROSS_RATE_PERCENTAGE_LIMIT = 5.0
HISTORY_DAYS = 30  # кількість днів для аналізу історії

# Налаштування оновлення
UPDATE_INTERVAL = 300  # 5 хвилин між оновленнями