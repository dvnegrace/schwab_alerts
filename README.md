# Schwab Positions Alerts
> Please pull master locally then **👁️ Focus on the `src/` folder only** - ignore all other files in this repository. Everything important is in `src/`, `lambda_function.py` (the main python file) and `positions.json` (sample file already uploaded in AWS S3 bucket.

## 📁 **Project Structure (What Actually Matters)**

```
src/
├── alert_checker.py          # 🧠 Main alert processing engine  
├── config.py                 # ⚙️  Environment variables & settings
├── json_processor.py         # 📄 Processes positions.json with detailed position info
├── message_formatter.py      # 💬 Formats alert messages with position details
├── s3_client.py               # 🗄️  Downloads positions file from AWS S3
├── alert_state.py             # 📊 DynamoDB alert tracking (prevents spam)
├── calculations.py            # 🧮 Price/volume utility functions
├── exceptions.py              # ❌ Custom error classes
│
├── polygon_api/               # 📈 Market data fetching with 140+ concurrent workers
│   ├── base_client.py         # 🌐 HTTP client for Polygon API
│   ├── custom_bars_ohlc.py    # 📊 OHLC data with concurrent support
│   ├── ticker_processor.py    # ⚡ Concurrent ticker processing (50 workers)
│   └── historical_volume.py   # 📈 Volume data (currently disabled)
│
├── alert_logic/               # 🎯 Alert decision algorithms
│   ├── basic_alerts.py        # 📊 Basic % threshold alerts
│   ├── minutes_alerts.py      # ⏱️  Consecutive minute movement detection
│   └── seconds_alerts.py      # ⚡ Consecutive second movement detection
│
└── services/                  # 📱 Notification channels (5 total)
    ├── telegram_service.py    # 📱 Telegram messages
    ├── twilio_service.py      # 📞 Voice calls
    ├── slack_service.py       # 💼 Slack webhooks
    ├── discord_service.py     # 🎮 Discord webhooks
    └── ifttt_service.py       # 🔗 IFTTT triggers

lambda_function.py             # 🚀 Entry point (AWS Lambda handler)
```

## 🚀 **How `lambda_function.py` Works**

The `lambda_function.py` is your **main entry point** that coordinates everything:

### **For Local Testing - Use `--test` Flag**
```bash
# Local testing with mock alerts (safe, no real notifications)
python lambda_function.py --test
```

When you run with `--test`, here's what happens **step-by-step**:

1. **🧪 Test Mode Setup**: Automatically sets `LOCAL_TESTING_MODE=true` and provides default test configuration
2. **📥 Real Data Download**: Downloads your actual `positions.json` from S3 
3. **🔍 Position Analysis**: Parses JSON to extract your options positions (strikes, expirations, quantities)
4. **⚡ Concurrent Market Data**: Launches **140+ concurrent workers** to fetch live market data:
   - 50 workers for ticker snapshots
   - 30 workers for minute data  
   - 30 workers for second data
   - 30 workers for daily data
5. **🎯 Smart Alert Logic**: Analyzes each ticker against three algorithms:
   - **Basic alerts**: ±5% threshold checks
   - **Minutes alerts**: Consecutive minute movements  
   - **Seconds alerts**: Consecutive second movements
6. **📱 Mock Notifications**: **Prints** what alerts WOULD be sent (doesn't actually send them)
7. **📊 Detailed Output**: Shows exact message format with position details:
   ```
   [BJ] [2025-08-22 10:17 AM] 🚨 -8.35% 🚨 Spike DOWN! $106.16 → $97.30.
   
   We have ONE position at risk: 21 Nov 25 60P || Qty: -5 ||
   ```

### **Production Mode (No Flags)**
```bash
# Production mode with real alerts
python lambda_function.py
```

**Production mode does everything above BUT**:
- ✅ **Sends real notifications** via Telegram, Twilio, Slack, Discord, IFTTT
- ✅ **Uses DynamoDB** to prevent duplicate alerts  
- ✅ **Requires all environment variables** (API keys, tokens, etc.)

## 🎯 **The Alert Flow Narrative**

When `lambda_function.py` runs, here's the **complete story**:

1. **🏁 Startup**: Validates your API keys and configuration
2. **📥 Data Gathering**: Downloads `positions.json` from S3 (your options positions)  
3. **🧠 Position Intelligence**: Extracts ticker symbols and determines alert directions:
   - **CALL positions** → Watch for **upward** moves  
   - **PUT positions** → Watch for **downward** moves
4. **⚡ Concurrent Market Fetch**: Simultaneously fetches live data for all tickers using 140+ workers
5. **🎯 Alert Decision Engine**: For each ticker, runs three parallel checks:
   - Did it move ±5% from open? (basic alert)
   - Did it have 3+ consecutive minutes of movement? (minutes alert)  
   - Did it have 5/10/15 consecutive seconds of movement? (seconds alert)
6. **📊 Position Context**: If alert triggers, formats message with your exact position details
7. **📱 Multi-Channel Blast**: Sends alerts simultaneously to all 5 configured channels
8. **🔒 State Tracking**: Marks ticker as "alerted" in DynamoDB to prevent spam

## 🧪 **Testing vs Production**

| Feature | `--test` Mode | Production Mode |
|---------|---------------|-----------------|
| **Market Data** | ✅ Real live data | ✅ Real live data |
| **Alert Logic** | ✅ Full processing | ✅ Full processing |  
| **Concurrent Workers** | ✅ 140+ workers | ✅ 140+ workers |
| **Notifications** | 🖨️ Prints to console | 📱 Real alerts sent |
| **DynamoDB** | ❌ Bypassed | ✅ Prevents duplicates |
| **Environment Setup** | 🤖 Auto-configured | 👤 Manual setup required |

## 🚨 **Alert Message Format**

Every alert includes **your exact position details**:
```
[TICKER] [TIME] 🚨 ±X.XX% 🚨 Spike UP/DOWN! $XX.XX → $XX.XX.

We have ONE/X position(s) at risk: DD MMM YY STRIKEP/C || Qty: ±X ||
```

**Real Example**:
- Ticker: BJ down 8.35%
- Position: 60 PUT expiring Nov 21, 2025  
- Quantity: Short 5 contracts (-5)

This gives you **instant context** about which of your positions are affected and by how much.

---

**🎯 Start here**: Run `python lambda_function.py --test` to see your positions analyzed in real-time with zero risk!
