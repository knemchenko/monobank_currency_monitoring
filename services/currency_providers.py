import json
import time
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional, Dict
from enum import Enum
from config.settings import BANK_REQUEST_TIMEOUT
from utils.logger import logger
import pytz


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"


@dataclass
class CurrencyRate:
    currency: Currency
    buy: float
    sell: float


class CurrencyProvider(ABC):
    def __init__(self, name: str, api_url: str):
        self.name = name
        self.api_url = api_url

    @abstractmethod
    def fetch_rates(self) -> Dict[Currency, CurrencyRate]:
        """
        Повертає словник з курсами для різних валют
        """
        pass

    def _make_request(self) -> Optional[requests.Response]:
        try:
            response = requests.get(self.api_url, timeout=BANK_REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching currency data from {self.name}: {e}")
            return None


class RaiffeisenBank(CurrencyProvider):
    def __init__(self):
        super().__init__("Райффайзен", "https://raiffeisen.ua/currency")

    def fetch_rates(self) -> Dict[Currency, CurrencyRate]:
        response = self._make_request()
        if not response:
            return {}

        try:
            rates = {}
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the index-component tag
            index_component = soup.find('index-component')
            if not index_component:
                logger.error("Raiffeisen: index-component tag not found")
                return {}

            # Extract the currencies JSON attribute
            currencies_json = index_component.get(':currencies')
            if not currencies_json:
                logger.error("Raiffeisen: :currencies attribute not found")
                return {}

            # Parse the JSON (removing escaped quotes)
            currencies_data = json.loads(currencies_json.replace('\\"', '"'))

            # Process main currencies (USD and EUR)
            for currency_entry in currencies_data.get('main', []):
                currency_code = currency_entry.get('currency')
                if currency_code not in [Currency.USD, Currency.EUR]:
                    continue

                ro_rates = currency_entry.get('rates', {}).get('ro', {})
                if not ro_rates:
                    logger.warning(f"Raiffeisen: No Raiffeisen Online rates for {currency_code}")
                    continue

                try:
                    buy_rate = float(ro_rates['rate_buy'])
                    sell_rate = float(ro_rates['rate_sell'])
                    if buy_rate == 0 or sell_rate == 0:
                        raise ValueError(f"Invalid rate values for {currency_code}")

                    rates[Currency(currency_code)] = CurrencyRate(
                        currency=Currency(currency_code),
                        buy=buy_rate,
                        sell=sell_rate
                    )
                except (ValueError, KeyError) as e:
                    logger.error(f"Raiffeisen: Error parsing {currency_code} rates: {e}")
                    continue

            return rates
        except Exception as e:
            logger.error(f"Raiffeisen: Error parsing response: {e}")
            return {}


class MonoBank(CurrencyProvider):
    CURRENCY_CODES = {
        840: Currency.USD,
        978: Currency.EUR
    }
    UAH_CODE = 980

    def __init__(self):
        super().__init__("Моно", "https://api.monobank.ua/bank/currency")

    def fetch_rates(self) -> Dict[Currency, CurrencyRate]:
        response = self._make_request()
        if not response:
            return {}

        try:
            rates = {}
            data = response.json()

            for entry in data:
                currency_code = entry.get('currencyCodeA')
                # Перевіряємо що це курс відносно гривні
                if currency_code in self.CURRENCY_CODES and entry.get('currencyCodeB') == self.UAH_CODE:
                    currency = self.CURRENCY_CODES[currency_code]
                    rates[currency] = CurrencyRate(
                        currency=currency,
                        buy=float(entry['rateBuy']),
                        sell=float(entry['rateSell'])
                    )
            return rates
        except Exception as e:
            logger.error(f"Error parsing {self.name} response: {e}")
            return {}


class PrivatBank(CurrencyProvider):
    def __init__(self):
        super().__init__("Приват", "https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=11")

    def fetch_rates(self) -> Dict[Currency, CurrencyRate]:
        response = self._make_request()
        if not response:
            return {}

        try:
            rates = {}
            data = response.json()

            for entry in data:
                try:
                    currency = Currency(entry['ccy'])
                    rates[currency] = CurrencyRate(
                        currency=currency,
                        buy=float(entry['buy']),
                        sell=float(entry['sale'])
                    )
                except ValueError:
                    # Пропускаємо валюти, які нас не цікавлять
                    continue
            return rates
        except Exception as e:
            logger.error(f"Error parsing {self.name} response: {e}")
            return {}


class GlobusBank(CurrencyProvider):
    CURRENCY_CODES = {
        840: Currency.USD,
        978: Currency.EUR
    }
    UAH_CODE = 980

    def __init__(self):
        super().__init__("Глобус", "https://gplus.globusbank.ua/api/v1/currency/exchange/rates")

    def fetch_rates(self) -> Dict[Currency, CurrencyRate]:
        response = self._make_request()
        if not response:
            return {}

        try:
            rates = {}
            data = response.json()

            for entry in data:
                currency_id = entry["Currency"]["Id"]
                equivalent_currency_id = entry["EquivalentCurrency"]["Id"]

                # Перевіряємо що це курс відносно гривні
                if currency_id in self.CURRENCY_CODES and equivalent_currency_id == self.UAH_CODE:
                    currency = self.CURRENCY_CODES[currency_id]
                    rates[currency] = CurrencyRate(
                        currency=currency,
                        buy=float(entry["BuyRate"]),
                        sell=float(entry["SellRate"])
                    )
            return rates
        except Exception as e:
            logger.error(f"Error parsing {self.name} response: {e}")
            return {}


class BVRBank(CurrencyProvider):
    CURRENCY_CODES = {
        "840": Currency.USD,
        "978": Currency.EUR
    }

    def __init__(self):
        super().__init__("БВР", "https://bvr.ua/api/DashBoard/getExchangeRates")

    def fetch_rates(self) -> Dict[Currency, CurrencyRate]:
        response = self._make_request()
        if not response:
            return {}

        try:
            rates = {}
            data = response.json()

            for entry in data["rows"]:
                if entry["code"] in self.CURRENCY_CODES:
                    currency = self.CURRENCY_CODES[entry["code"]]
                    rates[currency] = CurrencyRate(
                        currency=currency,
                        buy=float(entry["currencyRates"][0]["buy"]),
                        sell=float(entry["currencyRates"][0]["sell"])
                    )
            return rates
        except Exception as e:
            logger.error(f"Error parsing {self.name} response: {e}")
            return {}


class ParseFromUAInvest(CurrencyProvider):
    """Базовий клас для парсингу курсів з uainvest.com.ua"""

    def __init__(self, name: str, bank_logo_class: str):
        super().__init__(name, "https://www.uainvest.com.ua/currency-rates")
        self.bank_logo_class = bank_logo_class

    def _parse_datetime(self, date_str: str) -> datetime:
        """Конвертує строку дати в об'єкт datetime."""
        try:
            current_year = datetime.now().year
            day, month = map(int, date_str.split()[0].split('.'))
            hour, minute = map(int, date_str.split()[1].split(':'))

            dt = datetime(current_year, month, day, hour, minute)
            kiev_tz = pytz.timezone('Europe/Kiev')
            return kiev_tz.localize(dt)

        except Exception as e:
            logger.error(f"{self.name}: Error parsing date {date_str}: {e}")
            return None

    def _is_rate_fresh(self, update_time: datetime) -> bool:
        """Перевіряє чи курс оновлено в межах 72 годин."""
        if not update_time:
            return False

        now = datetime.now(pytz.timezone('Europe/Kiev'))
        return (now - update_time) <= timedelta(hours=72)

    def fetch_rates(self) -> Dict[Currency, CurrencyRate]:
        """Отримує курси валют з сайту."""
        response = self._make_request()
        if not response:
            return {}

        try:
            rates = {}
            soup = BeautifulSoup(response.text, 'html.parser')

            # Знаходимо рядок банку за класом логотипу
            bank_row = soup.find('img', class_=f'bank-logo-{self.bank_logo_class}').find_parent('tr')

            if not bank_row:
                logger.error(f"{self.name}: Row not found")
                return {}

            # Отримуємо всі колонки
            columns = bank_row.find_all('td')
            if len(columns) != 6:
                logger.error(f"{self.name}: Invalid columns count")
                return {}

            # Парсимо час оновлення
            update_time = self._parse_datetime(columns[5].find('small').text.strip())
            if not self._is_rate_fresh(update_time):
                logger.warning(f"{self.name}: Rates are outdated")
                return {}

            # Парсимо курси USD
            try:
                usd_buy = float(columns[1].text.strip())
                usd_sell = float(columns[2].text.strip())
                if not usd_buy or not usd_sell: raise ValueError(f'Value is 0 {usd_buy=} {usd_sell=}')
                rates[Currency.USD] = CurrencyRate(
                    currency=Currency.USD,
                    buy=usd_buy,
                    sell=usd_sell
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"{self.name}: Error parsing USD rates: {e}")

            # Парсимо курси EUR
            try:
                eur_buy = float(columns[3].text.strip())
                eur_sell = float(columns[4].text.strip())
                if not eur_buy or not eur_sell: raise ValueError(f'Value is 0 {eur_buy=} {eur_sell=}')
                rates[Currency.EUR] = CurrencyRate(
                    currency=Currency.EUR,
                    buy=eur_buy,
                    sell=eur_sell
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"{self.name}: Error parsing EUR rates: {e}")

            return rates

        except Exception as e:
            logger.error(f"Error fetching {self.name} rates: {e}")
            return {}


class UkrgazBank(ParseFromUAInvest):
    def __init__(self):
        super().__init__("Укргаз", "ukrgaz")


class AccordBank(ParseFromUAInvest):
    def __init__(self):
        super().__init__("Акорд", "accord")


class PUMBBank(ParseFromUAInvest):
    def __init__(self):
        super().__init__("ПУМБ", "pumb")


if __name__ == "__main__":
    bank = PUMBBank()
    print(bank.fetch_rates())