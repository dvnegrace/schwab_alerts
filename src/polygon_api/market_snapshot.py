import logging
from typing import Dict, List, Optional
from .base_client import make_polygon_request, BASE_URL
from ..calculations import calculate_percent_change, calculate_volume_ratio

logger = logging.getLogger(__name__)

def get_market_snapshot(tickers: List[str] = None) -> Dict[str, Dict]:
    """Get market snapshot with today's percentage changes for all or specific tickers"""
    url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
    params = {}
    
    logger.info(f"Fetching market snapshot from Polygon API")
    data = make_polygon_request(url, params, timeout=30)
    
    if 'tickers' not in data or not data['tickers']:
        logger.error(f"No ticker data in snapshot response")
        return {}
    
    logger.info(f"📊 Processing {len(data['tickers'])} tickers from Polygon snapshot API")
    
    # Check if there's pagination info in the response
    if 'next_url' in data and data['next_url']:
        logger.warning(f"⚠️ Polygon API has more data available (pagination detected)")
        logger.warning(f"📄 This may explain missing tickers - API returned partial results")
    
    snapshots = {}
    processed_count = 0
    
    for ticker_data in data['tickers']:
        try:
            ticker = ticker_data.get('ticker', '').upper()
            if not ticker:
                continue
            
            # If specific tickers requested, filter to only those
            if tickers and ticker not in [t.upper() for t in tickers]:
                continue
            
            # Get previous close from prevDay.c
            prev_close = None
            if 'prevDay' in ticker_data and ticker_data['prevDay'].get('c'):
                prev_close = float(ticker_data['prevDay']['c'])
            
            # Get current price from min.c
            current_price = None
            if 'min' in ticker_data and ticker_data['min'].get('c'):
                current_price = float(ticker_data['min']['c'])
                logger.debug(f"{ticker}: Using min close ${current_price}")
            
            # Calculate percentage change using: (current_price / previous_close - 1) * 100
            todays_change_perc = None
            if current_price is not None and prev_close is not None and prev_close > 0:
                todays_change_perc = (current_price / prev_close - 1) * 100
                logger.debug(f"{ticker}: Calculated change {todays_change_perc:.2f}% (min.c: ${current_price} / prevDay.c: ${prev_close})")
            
            # Get volume - check min.v only
            volume = None
            min_volume = None
            if 'min' in ticker_data and ticker_data['min'] and ticker_data['min'].get('v'):
                min_volume = ticker_data['min']['v']
                if min_volume is not None and min_volume > 0:
                    volume = int(min_volume)
                    logger.debug(f"{ticker}: Using min volume {volume:,}")
            
            # STRICT CHECK: Skip if any critical data is missing or zero, including min.v
            if (current_price is None or current_price == 0 or 
                prev_close is None or prev_close == 0 or
                min_volume is None or min_volume == 0):
                logger.debug(f"Skipping {ticker} - missing or zero critical data "
                             f"(min.c: {current_price}, prevDay.c: {prev_close}, min.v: {min_volume})")
                continue
            
            # todays_change_perc should always be calculated if we get here, but double-check
            if todays_change_perc is None:
                logger.error(f"Unexpected: Failed to calculate percentage change for {ticker}")
                continue
            
            snapshot = {
                'ticker': ticker,
                'current_price': current_price,
                'prev_close': prev_close,
                'volume': volume,
                'todays_change_perc': todays_change_perc,
                'volume_ratio': calculate_volume_ratio(volume, None)
            }
            
            snapshots[ticker] = snapshot
            processed_count += 1
            
            logger.debug(f"{ticker}: {snapshot['todays_change_perc']:+.2f}% (prev: ${prev_close} → current: ${current_price})")
            
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Error processing ticker data: {e}")
            continue
    
    logger.info(f"Successfully processed {processed_count} ticker snapshots")
    
    # If specific tickers were requested but not found, log warnings
    if tickers:
        missing_tickers = set(t.upper() for t in tickers) - set(snapshots.keys())
        if missing_tickers:
            logger.warning(f"No snapshot data found for tickers: {', '.join(missing_tickers)}")
    
    return snapshots