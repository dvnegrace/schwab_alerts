# Polygon API Data Flow & Usage

## Data Sources from Polygon API

### 1. Stock Snapshots (`/v2/snapshot/locale/us/markets/stocks/tickers`)
**Values Fetched:**
- `min.c` - Current price (latest minute data)
- `prevDay.c` - Previous day close price
- `min.v` - Current volume (latest minute data)
- `lastQuote.p` - Backup price if `min.c` is zero

**Calculated Values:**
- `todays_change_perc` = `((min.c - prevDay.c) / prevDay.c) * 100`

### 2. Index Snapshots (`/v3/snapshot/indices`)
**Values Fetched:**
- `value` - Current index value
- `session.previous_close` - Previous close
- `session.change_percent` - Pre-calculated percentage change

### 3. Historical Volume (`/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}`)
**Values Fetched:**
- `v` - Daily volume for each day (30-day default)

**Calculated Values:**
- `avg_volume` = Average of all daily volumes over the period

## Strict Data Filters

### Critical Data Requirements (All Must Be Present & Non-Zero)
1. `min.c` > 0 (current price)
2. `prevDay.c` > 0 (previous close)  
3. `min.v` > 0 (current volume)

**If ANY of these are missing/zero → ticker is REJECTED entirely**

### Alert Threshold Filters
- Stock movement must be ≥ **5.0%** in the direction we're watching
- Only alert for stocks where we have matching position types:
  - **Calls** → Alert on ≥ +5% moves
  - **Puts** → Alert on ≤ -5% moves

### Duplicate Alert Prevention
- Skip if already alerted for this ticker today
- Only send incremental alert if stock moves another **5%** from last alert

## Alert Data Usage

### Primary Alert Data
```
Ticker: {ticker}
Current Price: ${min.c}
Previous Close: ${prevDay.c}
Change: {todays_change_perc}%
Volume: {min.v:,}
Avg Volume: {avg_volume:,} (30-day)
Position Types: {position_description}
```

### Alert Triggers
1. **Initial Alert** - First time stock hits ±5% threshold
2. **Incremental Alert** - Stock moves another 5% from previous alert level

### Alert Channels
- **Telegram** - Full market data + position details
- **Voice Call** - Simple "{ticker} is up/down {percent}%"  
- **Slack** - Full market data + position details
- **Discord** - Full market data + position details
- **IFTTT** - Trigger only (no data passed)

### Volume Context
- Current volume vs 30-day average shown in alerts
- Used to indicate unusual trading activity
- Not used as a filter criteria

## Processing Flow

```
1. Fetch positions file → Extract tickers
2. Normalize tickers (/ → .) for Polygon API  
3. Concurrent API calls for stock snapshots
4. Sequential calls for any index tickers ($SPX, etc)
5. Filter: Keep only tickers with all required data
6. Check: Does movement match position direction + threshold?
7. Get historical volume for context
8. Check: Already alerted? Need incremental?
9. Send alerts via all configured channels
10. Mark as alerted in DynamoDB
```

## Rate Limiting
- **20 requests/second** maximum to Polygon API
- Uses ThreadPoolExecutor with 20 concurrent workers
- 0.05 second delay between requests