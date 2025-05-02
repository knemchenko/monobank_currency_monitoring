import logging
from logging.handlers import RotatingFileHandler
from config.settings import LOG_FORMAT, LOG_FILE, LOG_LEVEL

def setup_logger(name: str) -> logging.Logger:
    """
    Налаштовує і повертає логер з вказаним ім'ям
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Форматування логів
    formatter = logging.Formatter(LOG_FORMAT)

    # Файловий обробник з ротацією (максимум 5 файлів по 5 МБ)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5_000_000,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # Консольний обробник
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Додаємо обробники до логера
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Створюємо основний логер
logger = setup_logger('currency_bot')