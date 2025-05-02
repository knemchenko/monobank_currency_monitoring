from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Union, TypedDict
from services.currency_providers import Currency, CurrencyRate
from utils.logger import logger
from config.settings import MONGO_DB_NAME

class StatisticsResult(TypedDict):
    avg_delta: Optional[float]
    min_delta: Optional[float]
    max_delta: Optional[float]

class DatabaseManager:
    def __init__(self, connection_string: str):
        try:
            self.client = MongoClient(connection_string)
            # Перевіряємо підключення
            self.client.server_info()
            self.db = self.client[MONGO_DB_NAME]
            self.rates_collection = self.db.currency_rates
            
            # Створюємо індекси для оптимізації запитів
            self.rates_collection.create_index([("timestamp", -1)])
            self.rates_collection.create_index([("rates", 1)])
            
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def save_rates(self, rates: Dict[str, Dict[Currency, CurrencyRate]]) -> bool:
        """
        Зберігає курси валют в базу даних, уникаючи дублікатів.
        
        Args:
            rates: Словник курсів валют у форматі {bank_name: {currency: rate}}
        Returns:
            bool: True якщо дані були збережені, False якщо виникла помилка або дані не змінились
        """
        try:
            # Отримуємо останній запис з бази
            last_record = self.rates_collection.find_one(
                sort=[("timestamp", -1)]
            )
            
            # Форматуємо нові дані
            new_rates = {
                bank_name: {
                    currency.value: {
                        "buy": rate.buy,
                        "sell": rate.sell
                    }
                    for currency, rate in bank_rates.items()
                }
                for bank_name, bank_rates in rates.items()
            }
            
            # Перевіряємо, чи змінилися курси
            if last_record and self._compare_rates(last_record['rates'], new_rates):
                logger.debug("Rates haven't changed since last update, skipping save")
                return False
            
            # Зберігаємо нові курси
            document = {
                "timestamp": datetime.utcnow(),
                "rates": new_rates
            }
            
            self.rates_collection.insert_one(document)
            logger.info("New rates saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving rates to MongoDB: {e}")
            return False

    def _compare_rates(self, old_rates: dict, new_rates: dict) -> bool:
        """
        Порівнює старі та нові курси.
        
        Returns:
            bool: True якщо курси ідентичні, False якщо є відмінності
        """
        try:
            # Перевіряємо, чи всі банки присутні в обох записах
            if set(old_rates.keys()) != set(new_rates.keys()):
                return False
            
            for bank_name in new_rates:
                old_bank_rates = old_rates.get(bank_name, {})
                new_bank_rates = new_rates[bank_name]
                
                # Перевіряємо, чи всі валюти присутні
                if set(old_bank_rates.keys()) != set(new_bank_rates.keys()):
                    return False
                
                # Порівнюємо курси для кожної валюти
                for currency in new_bank_rates:
                    old_rate = old_bank_rates.get(currency, {})
                    new_rate = new_bank_rates[currency]
                    
                    # Перевіряємо, чи змінився курс купівлі або продажу
                    if (abs(old_rate.get('buy', 0) - new_rate['buy']) > 0.0001 or
                        abs(old_rate.get('sell', 0) - new_rate['sell']) > 0.0001):
                        return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error comparing rates: {e}")
            return False  # У разі помилки вважаємо, що курси різні

    def get_rates_history(
        self,
        currency: Currency,
        bank_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[dict]:
        """Отримує історію курсів для конкретної валюти."""
        query = {}
        if start_date:
            query["timestamp"] = {"$gte": start_date}
        if end_date:
            query["timestamp"] = {"$lte": end_date}

        pipeline = [
            {"$match": query},
            {"$sort": {"timestamp": -1}},
            {
                "$project": {
                    "timestamp": 1,
                    "rates": {
                        "$objectToArray": f"$rates{f'.{bank_name}' if bank_name else ''}"
                    }
                }
            },
            {"$unwind": "$rates"},
            {"$match": {"rates.k": currency.value}},
            {
                "$project": {
                    "timestamp": 1,
                    "bank": "$rates.k",
                    "buy": "$rates.v.buy",
                    "sell": "$rates.v.sell"
                }
            }
        ]

        return list(self.rates_collection.aggregate(pipeline))

    def get_statistics(
        self, 
        currency: Currency, 
        bank_name: str, 
        start_date: datetime, 
        cross_rate: bool = False,
        base_bank: str = "Моно"
    ) -> StatisticsResult:
        """
        Отримує статистику по курсам за вказаний період.
        
        Args:
            currency: Валюта для аналізу
            bank_name: Назва банку
            start_date: Початкова дата (30 днів тому)
            cross_rate: Чи потрібно аналізувати крос-курс
            base_bank: Банк для порівняння
        """
        try:
            # Встановлюємо часовий діапазон - останні 30 днів
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            
            # Формуємо умови для вибірки
            match_query = {
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }
            
            if cross_rate:
                match_query.update({
                    f"rates.{base_bank}.USD.buy": {"$exists": True},
                    f"rates.{bank_name}.EUR.sell": {"$exists": True}
                })
            else:
                match_query.update({
                    f"rates.{bank_name}.{currency.value}": {"$exists": True},
                    f"rates.{base_bank}.{currency.value}": {"$exists": True}
                })

            # Формуємо pipeline для агрегації
            pipeline = [
                {"$match": match_query},
                {
                    "$project": {
                        "delta": {
                            "$subtract": [
                                f"$rates.{bank_name}.{currency.value}.sell" if not cross_rate 
                                else f"$rates.{bank_name}.EUR.sell",
                                f"$rates.{base_bank}.{currency.value}.buy" if not cross_rate 
                                else f"$rates.{base_bank}.USD.buy"
                            ]
                        },
                        "timestamp": 1
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "avg_delta": {"$avg": "$delta"},
                        "min_delta": {"$min": "$delta"},
                        "max_delta": {"$max": "$delta"},
                        "count": {"$sum": 1}
                    }
                }
            ]

            # Виконуємо агрегацію
            result = list(self.rates_collection.aggregate(pipeline))
            
            # Додаємо логування для діагностики
            logger.debug(f"Statistics query for {bank_name} ({currency})")
            logger.debug(f"Match query: {match_query}")
            logger.debug(f"Found records: {len(result)}")
            if result:
                logger.debug(f"Statistics result: {result[0]}")

            # Форматуємо результат
            if result and result[0].get('count', 0) > 0:
                stats = result[0]
                return {
                    'avg_delta': round(stats['avg_delta'], 2),
                    'min_delta': round(stats['min_delta'], 2),
                    'max_delta': round(stats['max_delta'], 2)
                }
            
            return self._get_empty_result()
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}", exc_info=True)
            return self._get_empty_result()

    def _get_empty_result(self) -> StatisticsResult:
        """Повертає пустий результат статистики."""
        return {
            'avg_delta': None,
            'min_delta': None,
            'max_delta': None
        }

    def get_last_rate(self, bank_name: str, currency: Currency) -> Optional[dict]:
        """Отримує останній запис курсу для конкретного банку та валюти."""
        try:
            result = self.rates_collection.find_one(
                {f"rates.{bank_name}.{currency.value}": {"$exists": True}},
                sort=[("timestamp", -1)]
            )
            if result and bank_name in result['rates']:
                return result['rates'][bank_name][currency.value]
            return None
            
        except Exception as e:
            logger.error(f"Error getting last rate for {bank_name}: {e}")
            return None

if __name__ == '__main__':
    from config.settings import MONGO_CONNECTION_STRING
    mongo_db = DatabaseManager(MONGO_CONNECTION_STRING)
    mongo_db.rates_collection