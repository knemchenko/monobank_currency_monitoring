# Monobank Currency Tracker

This is a Python bot that tracks currency exchange rates using the Monobank API. The bot calculates the difference (delta) between the buy and sell rates, analyzes historical data, and sends updates to a specified Telegram channel when significant changes occur.

## Features
- Fetches real-time currency exchange rates from the Monobank API.
- Calculates and compares deltas with historical data (last 30 days).
- Sends formatted alerts to Telegram using Markdown.
- Designed to run as a background service using `systemd`.

## Requirements
- Python 3.6+
- Libraries: `requests`, `telebot`

Install dependencies using:
```bash
pip install -r requirements.txt
```

## Setup

1. **Clone the Repository**:
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Set Up the Bot**:
   - Replace the Telegram bot token in the Python script (`token`) with your own.
   - Update the `TELEGRAM_GROUP_ID` with the target chat ID.

3. **Test the Script**:
   ```bash
   python3 monobank.py
   ```

4. **Create a `systemd` Service**:
 Create the service file:
     ```bash
     sudo nano /etc/systemd/system/mono_currency.service
     ```
    Add the following content:
     ```
     [Unit]
     Description=Monobank Currency Tracker
     After=network.target

     [Service]
     ExecStart=/usr/bin/python3 /root/mono_currency/monobank.py
     WorkingDirectory=/root/mono_currency
     Environment="PYTHONUNBUFFERED=1"
     StandardOutput=journal
     StandardError=journal
     Restart=always
     RestartSec=120

     [Install]
     WantedBy=multi-user.target
     ```

5. **Enable and Start the Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable mono_currency.service
   sudo systemctl start mono_currency.service
   ```

6. **Check the Service Logs**:
   ```bash
   sudo journalctl -u mono_currency.service
   ```

## Notes
- The bot requires network access to fetch data from the Monobank API and send Telegram messages.
- Ensure your Telegram bot token and chat ID are kept secure.

## License
This project is licensed under the MIT License.
