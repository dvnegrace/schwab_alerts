# Schwab Positions Alerts

An AWS Lambda-based system that monitors stock positions and sends real-time alerts via multiple channels when stocks move beyond specified thresholds.

## 🎮 Controls & Testing

### Lambda Function Testing
```bash
# Test your deployed Lambda function
aws lambda invoke \
    --function-name SchwabAlerts \
    --payload '{}' \
    response.json && cat response.json
```
**What this triggers:** Downloads your positions.json from S3 → Fetches real-time market data for 147 tickers → Sends alerts for stocks moving ±4% based on your CALL/PUT positions → Updates alert state in DynamoDB

### Clear Alert State (Re-trigger alerts)
```bash
# Clear all previous alerts to re-test
aws dynamodb scan --table-name schwab-alerts --query 'Items[*].ticker_date.S' --output text | tr '\t' '\n' | xargs -I {} aws dynamodb delete-item --table-name schwab-alerts --key '{"ticker_date":{"S":"{}"}}'
```

### Direct IFTTT Testing
```bash
# Test IFTTT phone call directly
curl -X POST https://maker.ifttt.com/trigger/schwab_alert_call/with/key/YOUR_IFTTT_KEY
```

### Local Testing Mode
```bash
# Set local testing mode (bypasses DynamoDB, prints alerts to console)
export LOCAL_TESTING_MODE=true
export S3_BUCKET_NAME="schwab-positions-bucket"
export POLYGON_API_KEY="your_polygon_key"
export POSITIONS_FILE_KEY="positions.json"

# Run locally
python lambda_function.py
```
**What Local Testing Does:**
- ✅ **Gets Real Data:** Downloads actual positions.json from S3, fetches live market data from Polygon
- ✅ **Processes Everything:** Runs full alert logic, calculates percentage changes for all 147 tickers
- ✅ **Prints Mock Alerts:** Shows what alerts WOULD be sent (doesn't actually send notifications)
- ✅ **Bypasses DynamoDB:** Ignores alert state, shows all qualifying alerts regardless of previous sends
- ✅ **Perfect for Testing:** See which stocks would trigger alerts without spamming yourself

## 🚨 Alert Channels (5 Total)

When a stock alert triggers, you receive notifications on ALL configured channels:

1. **📱 Telegram** - Rich formatted messages with price/volume data
2. **💬 Slack** - Same formatted messages via webhook  
3. **🎮 Discord** - Same formatted messages via webhook
4. **📞 Twilio Voice Call** - Automated voice call with spoken alert
5. **☎️ IFTTT Phone Call** - Triggers your IFTTT applet for additional call

## 🎯 Overview

This system automatically:
- Downloads position data from S3 (JSON format with options positions)
- Fetches real-time market data from Polygon.io using concurrent processing (20 req/sec)
- **Directional Alerts**: CALL positions → alerts on +4% moves, PUT positions → alerts on -4% moves
- Sends alerts via 5 channels simultaneously: Telegram, Slack, Discord, Twilio Voice, IFTTT Call
- Tracks alert state in DynamoDB to prevent duplicate notifications
- Supports incremental alerts for additional 5% movements beyond first alert

## 📁 Important Files

**Note**: Only the following files are essential for understanding and using this system:

- **`lambda_function.py`** - Main Lambda handler and entry point
- **`src/`** - All core functionality modules

All other files in the repository are either configuration, dependencies, or auxiliary files.

## 🏗️ Architecture

```
S3 Bucket → Lambda Function → Polygon API
    ↓            ↓              ↓
Positions    Alert Logic    Market Data
    ↓            ↓              ↓
DynamoDB ← Alert Tracking → Telegram/Voice
```


## Application Flow

### High-Level Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   AWS S3    │    │   Lambda    │    │  DynamoDB   │
│positions.json│───▶│Alert Checker│───▶│ Alert State │
│or .csv      │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                           │
                           ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ Polygon API │    │   Twilio    │
                   │ Snapshots   │    │SMS & Voice  │
                   └─────────────┘    └─────────────┘
```

### Detailed Flow

The application follows this step-by-step process (typically runs every 5 minutes during market hours):

#### 1. **Initialization** (`lambda_function.py`)
```
CloudWatch Events/EventBridge → Triggers Lambda → Validates Configuration
```
- Lambda function starts execution
- Validates all required environment variables
- Initializes core components

#### 2. **Position Data Retrieval** (`src/s3_client.py`)
```
S3 Bucket → Downloads positions.json (or .csv) → Returns file content
```
- Downloads positions file from S3 using `POSITIONS_FILE_KEY`
- Supports both JSON and CSV formats
- File type auto-detected by extension

#### 3. **Position Parsing** (`src/json_processor.py` or `src/csv_processor.py`)
```
Raw File Content → Parser → List of Position Objects
```

**For JSON (Options Positions):**
- Parses options positions with fields like `Underlying`, `Option Symbol`, `Strike`, etc.
- Extracts unique underlying tickers (e.g., PANW, RACE, NVO)
- Creates `OptionsPosition` objects

**For CSV (Stock Positions):**
- Parses simple ticker/price pairs
- Creates `Position` objects with ticker and prior close price

#### 4. **Market Data Retrieval** (`src/polygon_client.py`)
```
Unique Tickers → Polygon Snapshot API → Market Data with Custom % Calculation
```
- Extracts unique ticker symbols from positions
- Makes single API call to Polygon snapshot endpoint
- Gets real-time data including:
  - Today's opening price (`day.o`)
  - Current price (priority: `min.c` → `lastTrade.p` → `day.c`)
  - Previous close price (`prevDay.c`)
- **Custom calculation**: `((current_price - todays_open) / todays_open) * 100`

#### 5. **Alert Logic Processing** (`src/alert_checker.py`)
```
For Each Ticker:
├── Check % Change ≥ Threshold (5%) ?
├── Already Alerted Today? → Check DynamoDB
├── If Alert Needed → Send Notifications
└── Mark as Alerted → Update DynamoDB
```

**Per Ticker Process:**
- Calculate percentage change from today's open to current price
- Compare calculated percentage against `ALERT_THRESHOLD_PERCENT` (default 5%)
- Query DynamoDB to check if ticker already alerted today
- If threshold met and not already alerted:
  - Proceed to send alerts
  - Mark ticker as alerted in DynamoDB

#### 6. **Alert State Management** (`src/alert_state.py`)
```
DynamoDB Operations:
├── has_alerted_today(ticker) → Query by ticker#date key
├── mark_alerted(ticker, %) → Store alert record with TTL
└── Automatic cleanup → DynamoDB TTL removes old records
```
- Uses composite key: `ticker#YYYY-MM-DD`
- Prevents duplicate alerts for same ticker on same day
- Automatic cleanup after 7 days via TTL

#### 7. **Notification Delivery** (`src/twilio_client.py`)
```
Alert Triggered → Twilio API Calls:
├── SMS: "ALERT: PANW is up 6.25%!"
└── Voice: "Alert: PANW has moved up 6.2 percent."
```
- Sends both SMS and voice call simultaneously
- Uses TwiML for voice message formatting
- Handles partial failures (e.g., SMS succeeds, voice fails)

#### 8. **Results & Logging** (`lambda_function.py`)
```
Execution Summary:
├── Positions checked: X
├── Snapshots fetched: Y  
├── Alerts sent: Z
├── Errors: Any issues encountered
└── CloudWatch Logs: Detailed execution trace
```

### Key Files to Inspect

| File | Purpose | When to Check |
|------|---------|---------------|
| `lambda_function.py` | **Main entry point** | Check execution logs, configuration validation |
| `src/alert_checker.py` | **Core alert logic** | Debug alert processing, threshold checks |
| `src/json_processor.py` | **JSON parsing** | Issues with positions.json parsing |
| `src/polygon_client.py` | **Market data** | API errors, rate limits, data issues |
| `src/alert_state.py` | **Duplicate prevention** | DynamoDB errors, alert state issues |
| `src/twilio_client.py` | **Notifications** | SMS/voice delivery problems |
| `src/s3_client.py` | **File retrieval** | S3 access issues, file not found |
| `src/config.py` | **Configuration** | Environment variable issues |

### Example Execution Log Flow

```
[INFO] === Stock Alert Check Started ===
[INFO] Configuration validation passed
[INFO] Downloading positions.json from S3
[INFO] Successfully downloaded JSON file with 622KB
[INFO] Parsing positions JSON file
[INFO] Successfully parsed 45 unique underlying positions from JSON (1247 total items)
[INFO] Fetching market snapshots for 45 unique tickers
[INFO] Successfully processed 42 ticker snapshots
[INFO] PANW: +6.25% (open: $186.50 → current: $198.16)
[INFO] Sending alert for PANW: +6.25% change
[INFO] SMS sent successfully. Message SID: SM1234567890
[INFO] Voice call initiated successfully. Call SID: CA0987654321
[INFO] Successfully marked PANW as alerted
[INFO] Alert check completed. Sent 1 alerts for 42 unique tickers
[INFO] === Alert Check Summary ===
[INFO] Positions checked: 45
[INFO] Snapshots fetched: 42
[INFO] Alerts sent: 1
[INFO] Skipped (already alerted): 0
[INFO] Errors: 0
```

### Error Handling Flow

The application gracefully handles various error scenarios:

- **S3 Errors**: File not found, access denied → Logs error, exits gracefully
- **Parse Errors**: Invalid JSON/CSV → Logs details, attempts to continue with valid data
- **API Errors**: Polygon rate limits → Logs warning, continues with available data
- **DynamoDB Errors**: Access issues → Logs error, may allow duplicate alerts
- **Twilio Errors**: SMS/voice failures → Logs error, continues processing other tickers
- **Partial Failures**: Some tickers fail → Continues processing, returns HTTP 207

This robust error handling ensures the system continues operating even when individual components fail.

## Prerequisites

- AWS Account with appropriate permissions
- Polygon API key (free tier available)
- Twilio account with phone number
- Python 3.9+

## Installation & Deployment

### 1. Create AWS Resources

#### S3 Bucket
```bash
# Create S3 bucket for positions CSV
aws s3 mb s3://your-stock-positions-bucket

# Upload your positions file (JSON or CSV)
aws s3 cp positions.json s3://your-stock-positions-bucket/positions.json
# OR for CSV format:
# aws s3 cp positions.csv s3://your-stock-positions-bucket/positions.csv
```

#### DynamoDB Table
```bash
# Create DynamoDB table for alert state tracking
aws dynamodb create-table \
    --table-name AlertState \
    --attribute-definitions \
        AttributeName=ticker_date,AttributeType=S \
    --key-schema \
        AttributeName=ticker_date,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Optional: Enable TTL for automatic cleanup
aws dynamodb update-time-to-live \
    --table-name AlertState \
    --time-to-live-specification \
        Enabled=true,AttributeName=ttl \
    --region us-east-1
```

### 2. Package Lambda Function

```bash
# Create deployment package
pip install -r requirements.txt -t .
zip -r stock-alerts.zip . -x "*.git*" "*.md" "__pycache__/*" "*.pyc"
```

### 3. Deploy Lambda Function

```bash
# Create Lambda function
```

### 4. Update Existing Lambda Function

For subsequent code updates after making changes:

```bash
# Create deployment zip (excluding unnecessary files)
zip -r SchwabAlerts-app.zip . -x "python/*" "__pycache__/*"

# Method 1: Direct Lambda update
aws lambda update-function-code \
  --function-name SchwabAlerts \
  --zip-file fileb://SchwabAlerts-app.zip

# Method 2: Upload to S3 then update Lambda (recommended for larger files)
aws s3 cp SchwabAlerts-app.zip s3://schwab-alerts-code/SchwabAlerts-app.zip
aws lambda update-function-code \
  --function-name SchwabAlerts \
  --s3-bucket schwab-alerts-code \
  --s3-key SchwabAlerts-app.zip

# Test the deployment
aws lambda invoke \
  --function-name SchwabAlerts \
  --payload '{}' \
  response.json && cat response.json

# Clear FND alert records (allows re-alerting):
aws dynamodb scan   --table-name schwab-alerts   --projection-expression 'ticker_date'   --query "Items[?starts_with(ticker_date.S, \`FND\`)].ticker_date.S"   --output text | tr '\t' '\n' | while read -r k; do     aws dynamodb delete-item       --table-name schwab-alerts       --key "{\"ticker_date\":{\"S\":\"$k\"}}";     echo "Deleted $k";   done

# Clear all alert records (allows re-alerting):
aws dynamodb scan --table-name schwab-alerts --projection-expression 'ticker_date' --query "Items[].ticker_date.S" --output text | tr '\t' '\n' | while read -r k; do aws dynamodb delete-item --table-name schwab-alerts --key "{\"ticker_date\":{\"S\":\"$k\"}}"; echo "Deleted $k"; done
```

### 5. Configure Environment Variables

```bash
aws lambda update-function-configuration \
    --function-name stock-position-alerts \
    --environment Variables='{
        "S3_BUCKET_NAME": "your-stock-positions-bucket",
        "POSITIONS_FILE_KEY": "positions.json",
        "DYNAMODB_TABLE_NAME": "AlertState",
        "POLYGON_API_KEY": "your_polygon_api_key",
        "TWILIO_ACCOUNT_SID": "your_twilio_account_sid",
        "TWILIO_AUTH_TOKEN": "your_twilio_auth_token",
        "TWILIO_FROM_NUMBER": "+1234567890",
        "ALERT_PHONE_NUMBER": "+1987654321",
        "ALERT_THRESHOLD_PERCENT": "5.0",
        "AWS_REGION": "us-east-1"
    }'
```

### 6. Create IAM Role

Create a Lambda execution role with these policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-stock-positions-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/AlertState"
    }
  ]
}
```

### 7. Schedule Lambda Execution

Create CloudWatch Events rule to run every 5 minutes during market hours:

```bash
# Create rule
aws events put-rule \
    --name stock-alerts-schedule \
    --schedule-expression "rate(5 minutes)"

# Add Lambda target
aws events put-targets \
    --rule stock-alerts-schedule \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:stock-position-alerts"

# Grant permission for Events to invoke Lambda
aws lambda add-permission \
    --function-name stock-position-alerts \
    --statement-id stock-alerts-schedule \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:us-east-1:YOUR_ACCOUNT_ID:rule/stock-alerts-schedule
```