import sys
from pathlib import Path
import argparse
from datetime import datetime, timedelta
from pymongo import MongoClient

# Додаємо батьківську директорію до PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import MONGO_CONNECTION_STRING
from utils.logger import logger

def clean_database(hours: int = 6):
    """Очищує базу даних від старих записів."""
    client = MongoClient(MONGO_CONNECTION_STRING)
    db = client.currency_db
    rates_collection = db.rates
    
    try:
        time_ago = datetime.utcnow() - timedelta(hours=hours)
        result = rates_collection.delete_many(
            {"timestamp": {"$lt": time_ago}}
        )
        logger.info(f"Successfully deleted {result.deleted_count} records older than {hours} hours")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Error cleaning old records: {e}")
        return 0
    finally:
        client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean old currency rates from database')
    parser.add_argument(
        '--hours', 
        type=int, 
        default=1000,
        help='Delete records older than specified hours (default: 1)'
    )
    
    args = parser.parse_args()
    clean_database(args.hours) 