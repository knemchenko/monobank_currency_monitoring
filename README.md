# Exchange Watcher

Exchange Watcher is a Python-based Telegram bot that monitors and analyzes currency exchange rates (USD and EUR) from multiple Ukrainian banks, including MonoBank, PrivatBank, GlobusBank, PUMBBank, BVRBank, UkrgazBank, AccordBank, and RaiffeisenBank. The bot calculates rate differences, performs cross-rate analysis (USD → UAH → EUR), and sends detailed reports to designated Telegram channels. It uses MongoDB for storing historical data and provides 30-day statistics to help users identify favorable exchange opportunities.

## Features

- **Real-time Rate Monitoring**: Fetches USD and EUR exchange rates every 5 minutes from multiple Ukrainian banks.
- **Rate Analysis**: Compares each bank’s sell rate to MonoBank’s buy rate, flagging favorable conditions (delta < 1%).
- **Cross-rate Analysis**: Identifies profitable USD → UAH → EUR conversion opportunities (percentage difference < 5%).
- **Historical Statistics**: Stores rates in MongoDB and provides 30-day average, minimum, and maximum delta statistics.
- **Telegram Notifications**: Sends markdown-formatted reports to separate Telegram channels for USD, EUR, and USD→EUR cross-rates when rates change significantly (delta ≥ 0.01) or are favorable.
- **Error Handling**: Logs errors and notifies the admin via Telegram for issues like failed API requests or parsing errors.
- **Database Management**: Includes a script to analyze and remove duplicate rate records.
- **Background Service**: Runs as a `systemd` service for reliable operation.

## Requirements

- **Python**: 3.8 or higher
- **MongoDB**: A running instance (local or cloud-based)
- **Telegram Bot Token**: Obtained from [BotFather](https://t.me/BotFather)
- **Dependencies**:
  - `requests`: For HTTP requests
  - `beautifulsoup4`: For web scraping
  - `pymongo`: For MongoDB interactions
  - `python-telegram-bot`: For Telegram API
  - `python-dotenv`: For environment variables
  - `pytz`: For timezone handling

Install dependencies:
```bash
pip install -r requirements.txt
```

Create a `requirements.txt` file with:
```
requests==2.31.0
beautifulsoup4==4.12.2
pymongo==4.6.0
python-telegram-bot==13.7
python-dotenv==1.0.0
pytz==2023.3
```

## Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/exchange-watcher.git
   cd exchange-watcher
   ```

2. **Configure the Application**:
   Create a `.env` file in the project root with the following variables:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_GROUP_ID_USD=-123456789
   TELEGRAM_GROUP_ID_EUR=-123456789
   TELEGRAM_GROUP_USD_TO_EUR=-123456789
   TELEGRAM_ADMIN_ID=123456789
   MONGO_CONNECTION_STRING=mongodb://localhost:27017/
   MONGO_DB_NAME=currency_bot
   LOG_LEVEL=INFO
   ```
   - Replace `your_bot_token` with the token from BotFather.
   - Replace group IDs with the numeric IDs of your Telegram channels (e.g., `-123456789`).
   - Replace `TELEGRAM_ADMIN_ID` with the admin’s Telegram user ID.
   - Update `MONGO_CONNECTION_STRING` if using a remote MongoDB instance.

3. **Initialize MongoDB**:
   - Ensure MongoDB is running (`mongod` for local instances).
   - The bot automatically creates the `currency_bot` database and `currency_rates` collection with indexes.

4. **Test the Application**:
   Run the bot to verify setup:
   ```bash
   python main.py
   ```
   Check logs in `logs/currency_bot.log` and Telegram channels for output.

5. **Create a `systemd` Service**:
   Create a service file:
   ```bash
   sudo nano /etc/systemd/system/exchange-watcher.service
   ```
   Add:
   ```ini
   [Unit]
   Description=Exchange Watcher Currency Monitoring Bot
   After=network.target mongodb.service

   [Service]
   ExecStart=/usr/bin/python3 /path/to/exchange-watcher/main.py
   WorkingDirectory=/path/to/exchange-watcher
   Environment="PYTHONUNBUFFERED=1"
   StandardOutput=journal
   StandardError=journal
   Restart=always
   RestartSec=60

   [Install]
   WantedBy=multi-user.target
   ```
   Replace `/path/to/exchange-watcher` with the absolute path to your project directory.

6. **Enable and Start the Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable exchange-watcher.service
   sudo systemctl start exchange-watcher.service
   ```

## Bot Logic

1. **Initialization**:
   - Initializes a Telegram client, connects to MongoDB, and loads currency providers.

2. **Rate Fetching**:
   - Queries bank APIs (e.g., MonoBank, PrivatBank) or scrapes websites (e.g., RaiffeisenBank, PUMBBank) every 5 minutes.
   - Validates rates and logs errors for failed requests.

3. **Analysis**:
   - Compares each bank’s sell rate to MonoBank’s buy rate to calculate the delta.
   - Flags rates as favorable if the delta is below 1% of MonoBank’s buy rate.
   - Analyzes USD → UAH → EUR cross-rates, flagging opportunities if the percentage difference is below 5%.
   - Retrieves 30-day statistics (average, min, max delta) from MongoDB.

4. **Notifications**:
   - Sends markdown-formatted reports to Telegram channels when rates change (delta ≥ 0.01) or are favorable.
   - Reports include bank name, delta, percentage change, current rates, and historical statistics.
   - Example report:
     ```
     🟢 Райффайзен:
     Різниця: 0.24 (0.58%)
     Курс: (41.78 - 41.54)
     Середнє за весь час: 0.30
     Мінімальне: 0.20
     Максимальне: 0.50
     ```

5. **Data Storage**:
   - Stores rates in MongoDB if they differ from the previous record.
   - Automatically creates indexes for efficient queries.

## Database Management

To analyze or remove duplicate rate records:
```bash
python remove_duplicates.py --analyze  # Analyze duplicates
python remove_duplicates.py           # Remove duplicates
```

## Available Currency Providers

- MonoBank (API)
- PrivatBank (API)
- GlobusBank (API)
- BVRBank (API)
- PUMBBank (web scraping via uainvest.com.ua)
- UkrgazBank (web scraping via uainvest.com.ua)
- AccordBank (web scraping via uainvest.com.ua)
- RaiffeisenBank (web scraping via raiffeisen.ua)

## Analysis Types

1. **Regular Rate Analysis**:
   - Compares USD and EUR buy/sell rates across banks to MonoBank’s buy rate.
   - Provides delta, percentage change, and 30-day statistics.

2. **Cross-rate Analysis**:
   - Evaluates USD → UAH → EUR conversion opportunities.
   - Compares each bank’s EUR sell rate to MonoBank’s USD buy rate.
   - Flags opportunities with a percentage difference below 5%.

## Telegram Output

The bot sends reports to three Telegram channels:
- **USD Channel**: Updates for USD rate changes or favorable conditions.
- **EUR Channel**: Updates for EUR rate changes or favorable conditions.
- **USD→EUR Channel**: Updates for cross-rate opportunities.

Each report includes:
- Bank name
- Delta and percentage change
- Current buy/sell rates
- 30-day statistics (average, min, max delta)
- Favorable exchange indicators (🟢 for favorable, 🔴 for changes)

## Logging

Logs are stored in `logs/currency_bot.log` with rotation (5 files, 5MB each). View logs via:
```bash
sudo journalctl -u exchange-watcher.service
```

## Development

- **Code Formatting**: Use `black` for consistent style.
- **Type Hints**: Follow Python type hints for better code quality.
- **Testing**: Add unit tests with `pytest` for new functionality.
- **Documentation**: Update this README and inline comments when adding features.

## Troubleshooting

- **No Telegram messages**:
  - Verify `TELEGRAM_BOT_TOKEN` and group IDs in `.env`.
  - Check logs for Telegram API errors.
- **MongoDB errors**:
  - Ensure MongoDB is running and `MONGO_CONNECTION_STRING` is correct.
- **Rate fetching issues**:
  - Verify internet connectivity and bank website/API availability.
  - Check logs for parsing errors (e.g., website structure changes).
- **Service not starting**:
  - Confirm paths in `exchange-watcher.service` are correct.
  - Check `systemctl status exchange-watcher.service` for errors.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

Please include tests and update documentation.

## Contact

For questions or suggestions, open an issue on GitHub or contact the maintainer via Telegram (@your-telegram-handle).