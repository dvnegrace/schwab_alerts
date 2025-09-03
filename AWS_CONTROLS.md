# AWS Controls & Deployment

## 🎮 Lambda Function Testing

### Test Deployed Function
```bash
# Test your deployed Lambda function
aws lambda invoke \
    --function-name SchwabAlerts \
    --payload '{}' \
    response.json && cat response.json
```
**What this triggers:** Downloads your positions.json from S3 → Fetches real-time market data for tickers → Sends alerts for stocks moving ±4% based on your CALL/PUT positions → Updates alert state in DynamoDB

### Clear Alert State (Re-trigger alerts)
```bash
# Clear all previous alerts to re-test
aws dynamodb scan --table-name schwab-alerts --query 'Items[*].ticker_date.S' --output text | tr '\t' '\n' | xargs -I {} aws dynamodb delete-item --table-name schwab-alerts --key '{"ticker_date":{"S":"{}"}}'
```

## 🏗️ AWS Architecture

```
S3 Bucket → Lambda Function → Polygon API
    ↓            ↓              ↓
Positions    Alert Logic    Market Data
    ↓            ↓              ↓
DynamoDB ← Alert Tracking → Notifications
```

### Detailed AWS Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   AWS S3    │    │   Lambda    │    │  DynamoDB   │
│positions.json│───▶│Alert Checker│───▶│ Alert State │
│             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                           │
                           ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ Polygon API │    │Notifications│
                   │ Market Data │    │Multi-channel│
                   └─────────────┘    └─────────────┘
```

## 📁 AWS Resource Setup

### 1. Create S3 Bucket
```bash
# Create S3 bucket for positions file
aws s3 mb s3://your-stock-positions-bucket

# Upload your positions file
aws s3 cp positions.json s3://your-stock-positions-bucket/positions.json
```

### 2. Create DynamoDB Table
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

# Enable TTL for automatic cleanup
aws dynamodb update-time-to-live \
    --table-name AlertState \
    --time-to-live-specification \
        Enabled=true,AttributeName=ttl \
    --region us-east-1
```

### 3. Package & Deploy Lambda Function
```bash
# Create deployment package
pip install -r requirements.txt -t .
zip -r stock-alerts.zip . -x "*.git*" "*.md" "__pycache__/*" "*.pyc"

# Create Lambda function (replace with your details)
aws lambda create-function \
    --function-name SchwabAlerts \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://stock-alerts.zip \
    --timeout 300 \
    --memory-size 256
```

### 4. Update Existing Lambda Function
```bash
# Create deployment zip (excluding unnecessary files)
zip -r SchwabAlerts-app.zip . -x "python/*" "__pycache__/*"

# Upload to S3 then update Lambda (recommended for larger files)
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
```

### 5. Configure Environment Variables
```bash
aws lambda update-function-configuration \
    --function-name SchwabAlerts \
    --environment Variables='{
        "S3_BUCKET_NAME": "your-stock-positions-bucket",
        "POSITIONS_FILE_KEY": "positions.json",
        "DYNAMODB_TABLE_NAME": "AlertState",
        "POLYGON_API_KEY": "your_polygon_api_key",
        "TELEGRAM_BOT_TOKEN": "your_telegram_token",
        "TELEGRAM_CHAT_ID": "your_chat_id",
        "TWILIO_ACCOUNT_SID": "your_twilio_account_sid",
        "TWILIO_AUTH_TOKEN": "your_twilio_auth_token",
        "TWILIO_FROM_NUMBER": "+1234567890",
        "ALERT_PHONE_NUMBER": "+1987654321",
        "SLACK_WEBHOOK_URL": "your_slack_webhook",
        "DISCORD_WEBHOOK_URL": "your_discord_webhook",
        "IFTTT_WEBHOOK_KEY": "your_ifttt_key",
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
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:SchwabAlerts"

# Grant permission for Events to invoke Lambda
aws lambda add-permission \
    --function-name SchwabAlerts \
    --statement-id stock-alerts-schedule \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:us-east-1:YOUR_ACCOUNT_ID:rule/stock-alerts-schedule
```

## 🔧 Alert State Management

### Clear Specific Ticker Alerts
```bash
# Clear alerts for specific stock (replace AAPL with your ticker)
aws dynamodb scan --table-name AlertState --filter-expression "begins_with(ticker_date, :ticker)" --expression-attribute-values '{":ticker":{"S":"AAPL#"}}' --projection-expression 'ticker_date' --query "Items[].ticker_date.S" --output text | tr '\t' '\n' | xargs -I {} aws dynamodb delete-item --table-name AlertState --key '{"ticker_date":{"S":"{}"}}'

# Clear all today's alerts (approximate - clears recent records)
aws dynamodb scan --table-name AlertState --projection-expression 'ticker_date' --query "Items[].ticker_date.S" --output text | tr '\t' '\n' | xargs -I {} aws dynamodb delete-item --table-name AlertState --key '{"ticker_date":{"S":"{}"}}'
```

### Clear All Alert Records
```bash
# Clear all alert records (allows re-alerting for all tickers)
aws dynamodb scan \
  --table-name schwab-alerts \
  --projection-expression 'ticker_date' \
  --query "Items[].ticker_date.S" \
  --output text | tr '\t' '\n' | while read -r k; do \
    aws dynamodb delete-item \
      --table-name schwab-alerts \
      --key "{\"ticker_date\":{\"S\":\"$k\"}}"; \
    echo "Deleted $k"; \
  done
```

## 📊 Monitoring & Logs

### View Lambda Logs
```bash
# Get recent log streams
aws logs describe-log-streams \
    --log-group-name /aws/lambda/SchwabAlerts \
    --order-by LastEventTime \
    --descending \
    --max-items 5

# View specific log stream
aws logs get-log-events \
    --log-group-name /aws/lambda/SchwabAlerts \
    --log-stream-name "YYYY/MM/DD/[log-stream-id]"
```

### Monitor DynamoDB Usage
```bash
# Check table status
aws dynamodb describe-table --table-name schwab-alerts

# Scan current alert records
aws dynamodb scan --table-name schwab-alerts
```

This AWS setup provides a robust, scalable alert system that runs automatically and handles failures gracefully.