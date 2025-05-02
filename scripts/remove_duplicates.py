import sys
from pathlib import Path
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
from pymongo import MongoClient

# Додаємо батьківську директорію до PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import MONGO_CONNECTION_STRING, MONGO_DB_NAME
from utils.logger import logger

def remove_duplicates():
    """Видаляє дублікати записів з бази даних."""
    client = MongoClient(MONGO_CONNECTION_STRING)
    db = client[MONGO_DB_NAME]
    rates_collection = db.currency_rates

    try:
        # Отримуємо всі записи, сортовані за часом
        records = list(rates_collection.find().sort("timestamp", 1))
        
        if not records:
            logger.info("No records found in database")
            return
            
        logger.info(f"Found {len(records)} total records")
        
        # Зберігаємо унікальні записи
        unique_records = []
        duplicates = 0
        previous_rates = None
        
        for record in records:
            current_rates = record['rates']
            
            # Порівнюємо з попереднім записом
            if previous_rates and _compare_rates(previous_rates, current_rates):
                duplicates += 1
                # Видаляємо дублікат
                rates_collection.delete_one({"_id": record["_id"]})
            else:
                unique_records.append(record)
                previous_rates = current_rates
        
        logger.info(f"Removed {duplicates} duplicate records")
        logger.info(f"Remaining unique records: {len(unique_records)}")
        
    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
    finally:
        client.close()

def _compare_rates(old_rates: dict, new_rates: dict) -> bool:
    """
    Порівнює два набори курсів валют.
    
    Returns:
        bool: True якщо курси ідентичні, False якщо є відмінності
    """
    try:
        if set(old_rates.keys()) != set(new_rates.keys()):
            return False
            
        for bank_name in new_rates:
            old_bank_rates = old_rates.get(bank_name, {})
            new_bank_rates = new_rates[bank_name]
            
            if set(old_bank_rates.keys()) != set(new_bank_rates.keys()):
                return False
                
            for currency in new_bank_rates:
                old_rate = old_bank_rates.get(currency, {})
                new_rate = new_bank_rates[currency]
                
                # Перевіряємо курси з невеликою похибкою
                if (abs(float(old_rate.get('buy', 0)) - float(new_rate.get('buy', 0))) > 0.0001 or
                    abs(float(old_rate.get('sell', 0)) - float(new_rate.get('sell', 0))) > 0.0001):
                    return False
                    
        return True
        
    except Exception as e:
        logger.error(f"Error comparing rates: {e}")
        return False

def analyze_duplicates():
    """Аналізує дублікати без їх видалення."""
    client = MongoClient(MONGO_CONNECTION_STRING)
    db = client[MONGO_DB_NAME]
    rates_collection = db.currency_rates
    
    try:
        records = list(rates_collection.find().sort("timestamp", 1))
        
        if not records:
            logger.info("No records found in database")
            return
            
        duplicates_count = 0
        previous_rates = None
        duplicate_groups = []
        current_group = []
        previous_timestamp = None
        
        for record in records:
            current_rates = record['rates']
            timestamp = record['timestamp']
            
            if previous_rates and _compare_rates(previous_rates, current_rates):
                duplicates_count += 1
                if not current_group:
                    current_group.append(previous_timestamp)
                current_group.append(timestamp)
            else:
                if current_group:
                    duplicate_groups.append(current_group)
                    current_group = []
                    
            previous_rates = current_rates
            previous_timestamp = timestamp
            
        if current_group:
            duplicate_groups.append(current_group)
            
        logger.info(f"Found {duplicates_count} potential duplicates")
        logger.info(f"Found {len(duplicate_groups)} groups of duplicates")
        
        for i, group in enumerate(duplicate_groups, 1):
            logger.info(f"Group {i}: {len(group)} duplicates")
            logger.info(f"First record: {group[0]}")
            logger.info(f"Last record: {group[-1]}")
            logger.info("---")
            
    except Exception as e:
        logger.error(f"Error analyzing duplicates: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Remove duplicate currency rates from database')
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Only analyze duplicates without removing them'
    )
    
    args = parser.parse_args()
    remove_duplicates()

    # if args.analyze:
    #     logger.info("Analyzing duplicates...")
    #     analyze_duplicates()
    # else:
    #     logger.info("Removing duplicates...")
    #     remove_duplicates()