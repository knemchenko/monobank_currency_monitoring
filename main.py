import telebot
from datetime import datetime
from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_GROUP_ID_USD,
    TELEGRAM_GROUP_ID_EUR,
    TELEGRAM_GROUP_USD_TO_EUR,
    MONGO_CONNECTION_STRING,
    TELEGRAM_ADMIN_ID
)
from services.currency_providers import (
    MonoBank, PrivatBank, GlobusBank, PUMBBank, BVRBank, UkrgazBank, AccordBank,
    RaiffeisenBank, Currency
)
from services.currency_analyzer import CurrencyAnalyzer
from database.db_manager import DatabaseManager
from utils.logger import logger


class CurrencyBot:
    def __init__(self):
        self.bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        self.db_manager = DatabaseManager(MONGO_CONNECTION_STRING)
        self.providers = [
            MonoBank(),
            PrivatBank(),
            GlobusBank(),
            PUMBBank(),
            BVRBank(),
            UkrgazBank(),
            AccordBank(),
            RaiffeisenBank()
        ]

    def notify_admin(self, message: str):
        """Повідомляє адміна про помилку."""
        error_message = f"Currency Bot Error:\n{message}"
        logger.error(error_message)
        try:
            self.bot.send_message(TELEGRAM_ADMIN_ID, error_message)
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    def send_telegram_message(self, message_text: str, chat_id: int) -> bool:
        """Відправляє повідомлення в Telegram."""
        try:
            self.bot.send_message(chat_id, message_text, parse_mode='Markdown')
            logger.info(f"Message sent successfully to chat {chat_id}")
            return True
        except Exception as e:
            self.notify_admin(f"Error sending Telegram message: {e}")
            return False

    def get_all_rates(self) -> dict:
        """Отримує курси від усіх провайдерів."""
        rates = {}
        for provider in self.providers:
            provider_rates = provider.fetch_rates()
            if provider_rates:
                rates[provider.name] = provider_rates
            else:
                logger.warning(f"Failed to fetch rates from {provider.name}")
        return rates

    def analyze_and_send_currency_report(
            self,
            rates: dict,
            currency: Currency,
            chat_id: int
    ) -> None:
        """Аналізує курси для вказаної валюти і відправляє звіт."""
        if not rates:
            self.notify_admin("No rates available for analysis")
            return

        # Перевіряємо наявність курсу Монобанку (базовий курс)
        mono_rates = rates.get("Моно", {})
        if currency not in mono_rates:
            self.notify_admin(f"No Monobank rate for {currency.value}")
            return

        # Ініціалізуємо аналізатор
        analyzer = CurrencyAnalyzer(
            base_rate=mono_rates[currency],
            db_manager=self.db_manager
        )

        # Аналізуємо курси всіх банків
        analyses = analyzer.analyze_all_rates(rates)
        if not analyses:
            logger.warning(f"No analyses available for {currency.value}")
            return

        # Фільтруємо тільки змінені курси
        changed_analyses = [a for a in analyses if a and a.has_changed]

        if not changed_analyses:
            logger.info(f"No rate changes for {currency.value}")
            return

        # Формуємо повідомлення
        messages = []

        # Додаємо заголовок
        if any(analysis.is_favorable for analysis in changed_analyses):
            messages.append(f"🟢 Є вигідний курс для обміну {currency.value}\n")
        else:
            messages.append(f"🔴 Курс був змінений {currency.value}\n")

        # Додаємо аналіз по кожному банку зі зміненим курсом
        messages.extend(
            analyzer.format_analysis_message(analysis)
            for analysis in changed_analyses
        )

        # Відправляємо повідомлення
        self.send_telegram_message("\n".join(messages), chat_id)

    def analyze_and_send_usd_eur_report(self, rates: dict) -> None:
        """Аналізує можливість конвертації USD->UAH->EUR."""
        if not rates:
            self.notify_admin("No rates available for analysis")
            return

        # Перевіряємо наявність курсу Монобанку
        mono_rates = rates.get("Моно", {})
        if not (Currency.USD in mono_rates and Currency.EUR in mono_rates):
            logger.warning("Missing USD or EUR Monobank rates")
            return

        # Ініціалізуємо аналізатор з базовим курсом USD
        analyzer = CurrencyAnalyzer(
            base_rate=mono_rates[Currency.USD],
            db_manager=self.db_manager
        )

        # Аналізуємо крос-курси всіх банків
        analyses = analyzer.analyze_cross_rates(rates)
        if not analyses:
            logger.warning("No cross rate analyses available")
            return

        # Фільтруємо тільки змінені курси
        changed_analyses = [a for a in analyses if a and a.has_changed]

        if not changed_analyses:
            logger.info("No cross rate changes")
            return

        messages = []
        if any(analysis.is_favorable for analysis in changed_analyses):
            messages.append(f"🟢 Є вигідний курс для обміну\n")
        else:
            messages.append(f"🔴 Курс був змінений\n")
        messages.extend(
            analyzer.format_analysis_message(analysis)
            for analysis in changed_analyses
        )

        self.send_telegram_message("\n".join(messages), TELEGRAM_GROUP_USD_TO_EUR)

    def run(self):
        """Запускає основний цикл бота."""
        logger.info("Starting currency bot...")

        try:
            # Отримуємо курси від усіх банків
            rates = self.get_all_rates()

            if not rates.get('Моно'):
                self.notify_admin("Unable to fetch currency data from Mono")
                return

            # Аналіз і відправка звіту по USD
            self.analyze_and_send_currency_report(
                rates=rates,
                currency=Currency.USD,
                chat_id=TELEGRAM_GROUP_ID_USD
            )

            # Аналіз і відправка звіту по EUR
            self.analyze_and_send_currency_report(
                rates=rates,
                currency=Currency.EUR,
                chat_id=TELEGRAM_GROUP_ID_EUR
            )

            # Аналіз і відправка звіту по USD->EUR
            self.analyze_and_send_usd_eur_report(rates)

            # Зберігаємо історію ПІСЛЯ всіх аналізів
            self.db_manager.save_rates(rates)
            logger.info("Rates saved to database")

        except Exception as e:
            self.notify_admin(f"Critical error in bot execution: {e}")


if __name__ == "__main__":
    bot = CurrencyBot()
    bot.run()