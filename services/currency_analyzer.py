from dataclasses import dataclass
from typing import Dict, Optional, List, Union
from datetime import datetime, timedelta
from config.settings import DELTA_PERCENTAGE_LIMIT, HISTORY_DAYS, CROSS_RATE_PERCENTAGE_LIMIT
from services.currency_providers import Currency, CurrencyRate
from database.db_manager import DatabaseManager
from utils.logger import logger


@dataclass
class DeltaAnalysis:
    delta: float
    rate_sell: float
    rate_buy: float
    avg_delta: Optional[float]
    min_delta: Optional[float]
    max_delta: Optional[float]
    is_favorable: bool
    provider_name: str
    percentage: float
    has_changed: bool  # Додаємо флаг зміни

@dataclass
class CrossRateAnalysis:
    usd_buy: float
    eur_sell: float
    delta: float
    percentage: float
    provider_name: str
    has_changed: bool
    is_favorable: bool
    avg_delta: Optional[float] = None
    min_delta: Optional[float] = None
    max_delta: Optional[float] = None

class CurrencyAnalyzer:
    def __init__(self, base_rate: CurrencyRate, db_manager: DatabaseManager):
        self.base_rate = base_rate
        self.db_manager = db_manager
        self.delta_limit = self.base_rate.buy * (DELTA_PERCENTAGE_LIMIT / 100)

    def _has_delta_changed(self, provider_name: str, current_delta: float, currency: Currency) -> bool:
        """Перевіряє чи змінилась дельта відносно попереднього значення."""
        try:
            # Отримуємо останній запис для обох банків
            last_provider_rate = self.db_manager.get_last_rate(provider_name, currency)
            last_mono_rate = self.db_manager.get_last_rate("Моно", currency)
            
            if not last_provider_rate or not last_mono_rate:
                return True  # Якщо немає попередніх записів, вважаємо що змінилось
            
            # Рахуємо попередню дельту так само як і поточну - між банком і Моно
            last_delta = last_provider_rate['sell'] - last_mono_rate['buy']
            
            # Перевіряємо чи зміна більше ніж на 0.01
            return abs(current_delta - last_delta) >= 0.01
            
        except Exception as e:
            logger.error(f"Error checking delta change for {provider_name}: {e}")
            return True  # У разі помилки краще показати курс
            
    def analyze_rate(self, provider_name: str, rate: CurrencyRate) -> Optional[DeltaAnalysis]:
        """Аналізує курс конкретного банку."""
        if not rate or not self.base_rate:
            logger.error(f"Missing rate data for {provider_name}")
            return None

        try:
            delta = rate.sell - self.base_rate.buy
            percentage = (delta / self.base_rate.buy) * 100
            
            # Перевіряємо зміну дельти
            has_changed = self._has_delta_changed(provider_name, delta, rate.currency)
            
            stats = self.db_manager.get_statistics(
                currency=rate.currency,
                bank_name=provider_name,
                start_date=datetime.utcnow() - timedelta(days=HISTORY_DAYS)
            )
            
            return DeltaAnalysis(
                delta=delta,
                rate_sell=rate.sell,
                rate_buy=self.base_rate.buy,
                avg_delta=stats.get('avg_delta'),
                min_delta=stats.get('min_delta'),
                max_delta=stats.get('max_delta'),
                is_favorable=delta < self.delta_limit,
                provider_name=provider_name,
                percentage=percentage,
                has_changed=has_changed  # Додаємо інформацію про зміну
            )
        except Exception as e:
            logger.error(f"Error analyzing rate for {provider_name}: {e}")
            return None

    def format_analysis_message(self, analysis: Union[DeltaAnalysis, CrossRateAnalysis]) -> str:
        """Форматує повідомлення про аналіз курсів."""
        try:
            # Визначаємо значення для обох типів аналізу
            sell_rate = analysis.rate_sell if isinstance(analysis, DeltaAnalysis) else analysis.eur_sell
            buy_rate = analysis.rate_buy if isinstance(analysis, DeltaAnalysis) else analysis.usd_buy
            
            # Спільний формат для обох типів
            mark = "🟢" if analysis.is_favorable else "🔴"
            stats = ""
            if analysis.avg_delta is not None and analysis.min_delta is not None:
                stats = (f"\nСереднє за весь час: `{analysis.avg_delta:.2f}`\n"
                         f"Мінімальне: `{analysis.min_delta:.2f}`\n"
                         f"Максимальне: `{analysis.max_delta:.2f}`\n")
            
            return (
                f"{mark} {analysis.provider_name}:\n"
                f"Різниця: `{analysis.delta:.2f}` {analysis.percentage:.2f}% "
                f"Курс: ({sell_rate:.2f} - {buy_rate:.2f})"
                f"{stats}"
            )
            
        except Exception as e:
            logger.error(f"Error formatting analysis message: {e}")
            return "Error formatting message"

    def analyze_all_rates(self, rates: Dict[str, Dict[Currency, CurrencyRate]]) -> list[DeltaAnalysis]:
        """Аналізує курси всіх банків."""
        return [
            self.analyze_rate(provider_name, rate[self.base_rate.currency])
            for provider_name, rate in rates.items()
            if self.base_rate.currency in rate
        ]

    def _has_cross_rate_changed(self, provider_name: str, current_delta: float) -> bool:
        """Перевіряє чи змінилась різниця між USD та EUR."""
        try:
            # Отримуємо останні записи для обох валют
            last_mono_usd = self.db_manager.get_last_rate("Моно", Currency.USD)
            last_provider_eur = self.db_manager.get_last_rate(provider_name, Currency.EUR)
            
            if not last_mono_usd or not last_provider_eur:
                return True
            
            # Рахуємо попередню дельту
            last_delta = last_provider_eur['sell'] - last_mono_usd['buy']
            
            # Перевіряємо чи зміна більше ніж на 0.01
            return abs(current_delta - last_delta) >= 0.01
            
        except Exception as e:
            logger.error(f"Error checking cross rate change for {provider_name}: {e}")
            return True

    def analyze_cross_rates(self, rates: Dict[str, Dict[Currency, CurrencyRate]]) -> List[CrossRateAnalysis]:
        """Аналізує крос-курси всіх банків."""
        analyses = []
        for provider_name, provider_rates in rates.items():
            analysis = self.analyze_cross_rate(provider_name, provider_rates)
            if analysis:
                analyses.append(analysis)
        return analyses

    def analyze_cross_rate(self, provider_name: str, provider_rates: dict) -> Optional[CrossRateAnalysis]:
        """Аналізує можливість конвертації USD->EUR через банк."""
        try:
            if not (Currency.EUR in provider_rates):
                return None
                
            eur_sell = provider_rates[Currency.EUR].sell
            delta = eur_sell - self.base_rate.buy
            percentage = (delta / self.base_rate.buy) * 100
            
            has_changed = self._has_cross_rate_changed(provider_name, delta)
            
            # Отримуємо статистику за останні 7 днів
            stats = self.db_manager.get_statistics(
                currency=Currency.EUR,  # Для крос-курсу використовуємо EUR
                bank_name=provider_name,
                start_date=datetime.utcnow() - timedelta(days=HISTORY_DAYS),
                cross_rate=True  # Додаємо параметр для позначення крос-курсу
            )
            
            # Вважаємо курс вигідним, якщо відсоток менший за ліміт
            is_favorable = percentage <= CROSS_RATE_PERCENTAGE_LIMIT
            
            return CrossRateAnalysis(
                usd_buy=self.base_rate.buy,
                eur_sell=eur_sell,
                delta=round(delta, 2),
                percentage=round(percentage, 2),
                provider_name=provider_name,
                has_changed=has_changed,
                is_favorable=is_favorable,
                avg_delta=stats.get('avg_delta'),
                min_delta=stats.get('min_delta'),
                max_delta=stats.get('max_delta')
            )
            
        except Exception as e:
            logger.error(f"Error analyzing cross rate for {provider_name}: {e}")
            return None

    def _get_cross_rate_stats(self, provider_name: str) -> Dict[str, Optional[float]]:
        """Отримує статистику по крос-курсу за останні 7 днів."""
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            # Отримуємо історію курсів
            mono_usd_rates = self.db_manager.get_rates_history("Моно", Currency.USD, week_ago)
            provider_eur_rates = self.db_manager.get_rates_history(provider_name, Currency.EUR, week_ago)
            
            if not mono_usd_rates or not provider_eur_rates:
                return {'avg': None, 'min': None, 'max': None}
            
            # Рахуємо дельти для кожної пари курсів
            deltas = []
            for mono_rate in mono_usd_rates:
                for provider_rate in provider_eur_rates:
                    if abs((mono_rate['timestamp'] - provider_rate['timestamp']).total_seconds()) < 3600:  # курси в межах години
                        delta = provider_rate['sell'] - mono_rate['buy']
                        deltas.append(delta)
            
            if not deltas:
                return {'avg': None, 'min': None, 'max': None}
            
            return {
                'avg': round(sum(deltas) / len(deltas), 2),
                'min': round(min(deltas), 2),
                'max': round(max(deltas), 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting cross rate stats for {provider_name}: {e}")
            return {'avg': None, 'min': None, 'max': None} 