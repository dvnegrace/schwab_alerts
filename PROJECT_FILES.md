# Essential Project Files

## Core Application Files (Required)

### Main Application
- **`src/alert_checker.py`** - Main alert processing engine with concurrent data fetching
- **`src/config.py`** - Configuration settings and environment variables
- **`src/json_processor.py`** - Processes positions.json with detailed position information
- **`src/message_formatter.py`** - Formats alert messages with position details
- **`src/exceptions.py`** - Custom exception classes
- **`src/calculations.py`** - Utility functions for price/volume calculations
- **`src/__init__.py`** - Package initialization

### Alert Logic
- **`src/alert_logic/__init__.py`** - Alert logic package initialization  
- **`src/alert_logic/basic_alerts.py`** - Basic percentage threshold alerts
- **`src/alert_logic/minutes_alerts.py`** - Consecutive minute movement alerts
- **`src/alert_logic/seconds_alerts.py`** - Consecutive second movement alerts

### Data Services
- **`src/polygon_api/__init__.py`** - Polygon API package initialization
- **`src/polygon_api/base_client.py`** - Base HTTP client for Polygon API
- **`src/polygon_api/custom_bars_ohlc.py`** - OHLC data fetching with concurrent support
- **`src/polygon_api/ticker_processor.py`** - Concurrent ticker snapshot processing
- **`src/polygon_api/historical_volume.py`** - Historical volume data (currently commented out)

### AWS Services
- **`src/s3_client.py`** - S3 client for positions file download
- **`src/alert_state.py`** - DynamoDB client for alert state management

### Notification Services
- **`src/services/__init__.py`** - Services package initialization
- **`src/services/telegram_service.py`** - Telegram message sending
- **`src/services/twilio_service.py`** - Voice alert service  
- **`src/services/slack_service.py`** - Slack notifications
- **`src/services/discord_service.py`** - Discord notifications
- **`src/services/ifttt_service.py`** - IFTTT webhook service

## Configuration Files
- **`requirements.txt`** - Python package dependencies
- **`positions.json`** - Your positions data (user-provided)
- **`lambda_function.py`** - AWS Lambda entry point (if deploying to Lambda)

## Optional Files  
- **`src/polygon_api/market_snapshot.py`** - Alternative market data fetching (unused)
- **`src/polygon_api/indices_snapshot.py`** - Index data fetching (unused)
- **`src/concurrent_alert_processor.py`** - Alternative concurrent processor (unused)
- **`src/alert_checker.py.backup`** - Backup file (can be deleted)

## Data Files (User-Provided)
- **`positions.json`** - JSON file with your options positions
- **Environment variables** - AWS credentials, API keys, notification tokens

## Total Essential Files: ~25 Python files

The system is modular - you can disable notification services you don't use by not providing their API keys/tokens in the configuration.