import logging
from typing import List, Dict, Tuple, Union
from .config import Config
from .s3_client import S3Client
from .json_processor import JSONProcessor, OptionsPosition, PositionSummary
from .polygon_api.ticker_processor import get_ticker_concurrent
from .polygon_api.historical_volume import get_historical_volume
from .alert_state import AlertStateManager
from .services import telegram_service
from .services import twilio_service
from .services import slack_service
from .services import discord_service
from .services import ifttt_service
from .alert_logic.basic_alerts import should_trigger_basic_alert, should_trigger_incremental_alert
from .alert_logic.seconds_alerts import should_trigger_consecutive_seconds_alert
from .alert_logic.minutes_alerts import should_trigger_consecutive_minutes_alert
from .exceptions import StockAlertError

logger = logging.getLogger(__name__)

class AlertChecker:
    def __init__(self):
        self.s3_client = S3Client()
        self.json_processor = JSONProcessor()
        
        # Only initialize these if not in local testing mode
        if not Config.LOCAL_TESTING_MODE:
            self.alert_state = AlertStateManager()
        else:
            self.alert_state = None
            logger.info("🧪 LOCAL TESTING MODE - Will print alerts instead of sending via Telegram/voice")
    
    def calculate_percent_change(self, current_price: float, prior_close: float) -> float:
        """Calculate percentage change from prior close"""
        if prior_close <= 0:
            raise ValueError(f"Invalid prior close price: {prior_close}")
        
        change = ((current_price - prior_close) / prior_close) * 100
        return round(change, 2)
    
    def _parse_positions_file(self, file_content: str) -> List[PositionSummary]:
        """Parse positions JSON file"""
        logger.info("Parsing positions JSON file")
        return self.json_processor.parse_positions_json(file_content)
    
    def _normalize_ticker_for_polygon(self, ticker: str) -> str:
        """Normalize ticker symbols for Polygon API (convert / to .)"""
        return ticker.replace('/', '.')
    
    def _get_tickers_from_positions(self, positions: List[PositionSummary]) -> List[str]:
        """Extract ticker symbols from positions"""
        tickers = []
        for pos in positions:
            tickers.append(pos.underlying)
        return tickers
    
    def check_and_alert(self) -> Dict:
        """Main function to check positions and send alerts"""
        results = {
            'positions_checked': 0,
            'snapshots_fetched': 0,
            'alerts_sent': 0,
            'skipped_already_alerted': 0,
            'errors': [],
            'alerts_details': [],
            'skipped_details': []
        }
        
        try:
            logger.info("Starting alert check process")
            
            # Step 1: Download and parse positions file
            logger.info("Downloading positions file from S3")
            file_content = self.s3_client.download_positions_file()
            
            positions = self._parse_positions_file(file_content)
            results['positions_checked'] = len(positions)
            
            if not positions:
                logger.warning("No positions found in file")
                return results
            
            logger.info(f"Found {len(positions)} positions to check")
            
            # Step 2: Get market snapshots for all tickers
            tickers = self._get_tickers_from_positions(positions)
            unique_tickers = list(set(tickers))  # Remove duplicates
            
            # Normalize tickers for Polygon API (convert / to .)
            normalized_tickers = [self._normalize_ticker_for_polygon(ticker) for ticker in unique_tickers]
            logger.info(f"Fetching market snapshots for {len(unique_tickers)} unique tickers")
            
            snapshots = get_ticker_concurrent(normalized_tickers)
            results['snapshots_fetched'] = len(snapshots)
            
            if not snapshots:
                error_msg = "Failed to fetch any market snapshots"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                return results
            
            # Step 3: Prepare concurrent data fetching for all unique tickers
            processed_tickers = set()
            tickers_to_process = []
            
            # Collect unique tickers that need processing (normalize for Polygon API, skip index tickers)
            for position in positions:
                ticker = position.underlying
                if ticker not in processed_tickers and not ticker.startswith('$'):
                    processed_tickers.add(ticker)
                    normalized_ticker = self._normalize_ticker_for_polygon(ticker)
                    tickers_to_process.append(normalized_ticker)
            
            logger.info(f"Starting concurrent data fetch for {len(tickers_to_process)} unique tickers")
            
            # Step 4: Fetch all data types concurrently
            from .polygon_api.historical_volume import get_historical_volumes_concurrent
            from .polygon_api.custom_bars_ohlc import (
                get_concurrent_minutes_data, 
                get_concurrent_seconds_data, 
                get_concurrent_days_data
            )
            
            # Concurrent fetching of all data types
            logger.info("🚀 Launching 3 concurrent data fetchers...")
            # volumes_data = get_historical_volumes_concurrent(tickers_to_process, max_workers=25)  # Commented out
            minutes_data = get_concurrent_minutes_data(tickers_to_process)
            seconds_data = get_concurrent_seconds_data(tickers_to_process)
            days_data = get_concurrent_days_data(tickers_to_process)
            logger.info("✅ All concurrent data fetching completed")
            
            # Step 5: Process alerts for each position
            processed_tickers = set()
            
            for position in positions:
                try:
                    ticker = position.underlying
                    position_desc = position.get_position_description()
                    
                    # Skip if we already processed this ticker
                    if ticker in processed_tickers:
                        continue
                    processed_tickers.add(ticker)
                    
                    # Normalize ticker for snapshot lookup
                    normalized_ticker = self._normalize_ticker_for_polygon(ticker)
                    
                    if normalized_ticker not in snapshots:
                        error_msg = f"No market snapshot available for {ticker}"
                        logger.warning(error_msg)
                        results['errors'].append(error_msg)
                        continue
                    
                    snapshot = snapshots[normalized_ticker]
                    percent_change = snapshot['todays_change_perc']
                    current_price = snapshot.get('current_price')
                    prev_close = snapshot.get('prev_close')
                    
                    # Get detailed position description with price data
                    detailed_position_desc = position.get_detailed_position_description(current_price, prev_close)
                    
                    logger.debug(f"{ticker}: {percent_change:+.2f}% (prev: ${snapshot['prev_close']} → current: ${snapshot['current_price']})")
                    
                    # Check if stock movement meets alert criteria
                    if abs(percent_change) >= Config.ALERT_THRESHOLD_PERCENT:
                        
                        # Get historical volume from concurrent fetch (commented out)
                        # avg_volume = volumes_data.get(ticker)
                        avg_volume = None
                        
                        # Get alert directions based on position types (calls = up, puts = down)
                        alert_directions = position.get_alert_directions()
                        
                        # Debug logging for alert direction logic
                        logger.info(f"{ticker} alert_directions: {alert_directions}, percent_change: {percent_change}")
                        
                        # Get last alerted percent and timestamp for this ticker
                        last_alerted_percent = 0
                        last_alert_timestamp = None
                        if not Config.LOCAL_TESTING_MODE and self.alert_state:
                            alert_status = self.alert_state.get_alert_status(ticker, snapshot['prev_close'])
                            if alert_status:
                                last_alerted_percent = alert_status.get('last_alerted_percent', 0)
                                last_alert_timestamp = alert_status.get('timestamp')
                        
                        # Check if basic alert criteria are met
                        should_alert_basic, basic_reason = should_trigger_basic_alert(percent_change, alert_directions, last_alerted_percent, last_alert_timestamp)
                        logger.debug(f"{ticker}: Basic - {basic_reason}")
                        
                        should_alert_this_direction = should_alert_basic
                        alert_trigger_type = "basic"
                        
                        # Skip consecutive checks for index tickers (they don't have minute/second data)
                        if not ticker.startswith('$'):
                            # If basic alert didn't trigger, check consecutive seconds alert
                            if not should_alert_basic:
                                ticker_seconds_data = seconds_data.get(normalized_ticker)
                                should_alert_consecutive, consecutive_reason = should_trigger_consecutive_seconds_alert(ticker, alert_directions, ticker_seconds_data)
                                if should_alert_consecutive:
                                    should_alert_this_direction = True
                                    alert_trigger_type = "consecutive_seconds"
                                    logger.info(f"{ticker}: Consecutive seconds - {consecutive_reason}")
                                else:
                                    logger.debug(f"{ticker}: Consecutive seconds - {consecutive_reason}")
                            
                            # If neither basic nor seconds alert triggered, check consecutive minutes alert
                            if not should_alert_this_direction:
                                ticker_minutes_data = minutes_data.get(normalized_ticker)
                                should_alert_minutes, minutes_reason = should_trigger_consecutive_minutes_alert(ticker, alert_directions, ticker_minutes_data)
                                if should_alert_minutes:
                                    should_alert_this_direction = True
                                    alert_trigger_type = "consecutive_minutes"
                                    logger.info(f"{ticker}: Consecutive minutes - {minutes_reason}")
                                else:
                                    logger.debug(f"{ticker}: Consecutive minutes - {minutes_reason}")
                        
                        # Check if we should send an alert (first time or incremental)
                        should_alert = should_alert_this_direction
                        alert_type = "initial"
                        alert_count = 1
                        last_alerted_percent = 0
                        
                        if not Config.LOCAL_TESTING_MODE:
                            # Production mode - check alert status
                            alert_status = self.alert_state.get_alert_status(ticker, snapshot['prev_close'])
                            
                            if alert_status is None:
                                # Never alerted before
                                should_alert = True
                                alert_type = "initial"
                                alert_count = 1
                                logger.info(f"{ticker}: First alert at {percent_change:.2f}%")
                            else:
                                # Previously alerted - check if should alert again
                                last_alerted_percent = alert_status['last_alerted_percent']
                                alert_count = alert_status['alert_count'] + 1
                                
                                # Retrigger is handled in basic_alerts by resetting last_alerted_percent
                                if "RETRIGGER" in basic_reason:
                                    should_alert = True
                                    alert_type = "retrigger"
                                    logger.info(f"{ticker}: Retrigger alert #{alert_count} after cooldown - {percent_change:.2f}%")
                                else:
                                    # Standard incremental alert check
                                    percent_increase_since_last = percent_change - last_alerted_percent
                                    if percent_increase_since_last >= Config.ALERT_THRESHOLD_PERCENT:
                                        should_alert = True
                                        alert_type = "incremental"
                                        logger.info(f"{ticker}: Incremental alert #{alert_count} - was {last_alerted_percent:.2f}%, now {percent_change:.2f}%")
                                    else:
                                        logger.debug(f"{ticker}: No alert - already alerted at {last_alerted_percent:.2f}%")
                                        results['skipped_already_alerted'] += 1
                                        continue
                        else:
                            # Local testing mode - check direction logic
                            should_alert = False
                            if 'up' in alert_directions and percent_change > 0:
                                should_alert = True  # CALL positions alert on UP moves
                            elif 'down' in alert_directions and percent_change < 0:
                                should_alert = True  # PUT positions alert on DOWN moves
                        
                        if should_alert:
                            # Handle local testing mode
                            if Config.LOCAL_TESTING_MODE:
                                # Print alert to console instead of sending
                                alert_prefix = f"🚨 {'INCREMENTAL' if alert_type == 'incremental' else 'INITIAL'} ALERT #{alert_count}:"
                                print(f"\n{alert_prefix}")
                                print(f"   Ticker: {ticker}")
                                if alert_type == "incremental":
                                    print(f"   Previous Alert: {last_alerted_percent:.2f}%")
                                    print(f"   Current: {percent_change:.2f}%")
                                    print(f"   Increase: +{percent_change - last_alerted_percent:.2f}%")
                                else:
                                    print(f"   Previous Close: ${snapshot['prev_close']:.2f}")
                                    print(f"   Current Price: ${snapshot['current_price']:.2f}")
                                    print(f"   Change: {percent_change:+.2f}%")
                                if position_desc:
                                    print(f"   Positions: {position_desc}")
                                
                                # Add recent minute and second percentage changes (no volume) - skip for index tickers
                                if not ticker.startswith('$'):
                                    try:
                                        # Get most recent minute change from pre-fetched data
                                        ticker_minutes_data = minutes_data.get(normalized_ticker)
                                        if ticker_minutes_data and ticker_minutes_data.get('results') and len(ticker_minutes_data['results']) >= 2:
                                            latest_results = list(reversed(ticker_minutes_data['results']))  # Chronological order
                                            latest_minute = latest_results[-1]
                                            prev_minute = latest_results[-2]
                                            minute_change = ((float(latest_minute['c']) - float(prev_minute['c'])) / float(prev_minute['c'])) * 100
                                            print(f"   📊 Most Recent Minute Change: {minute_change:+.2f}%")
                                        else:
                                            print(f"   📊 Most Recent Minute Change: N/A (insufficient data)")
                                        
                                        # Get most recent second change from pre-fetched data
                                        ticker_seconds_data = seconds_data.get(normalized_ticker)
                                        if ticker_seconds_data and ticker_seconds_data.get('results') and len(ticker_seconds_data['results']) >= 2:
                                            latest_results = list(reversed(ticker_seconds_data['results']))  # Chronological order
                                            latest_second = latest_results[-1]
                                            prev_second = latest_results[-2]
                                            second_change = ((float(latest_second['c']) - float(prev_second['c'])) / float(prev_second['c'])) * 100
                                            print(f"   ⚡ Most Recent Second Change: {second_change:+.2f}%")
                                        else:
                                            print(f"   ⚡ Most Recent Second Change: N/A (insufficient data)")
                                            
                                    except Exception as e:
                                        print(f"   📊 Recent Changes: Error fetching data - {e}")
                                
                                # Show exact messages that would be sent (no volume)
                                from .message_formatter import format_alert_message
                                
                                if alert_type == "incremental":
                                    telegram_msg = format_alert_message(
                                        ticker, percent_change, snapshot['prev_close'], snapshot['current_price'], 
                                        None, None, is_incremental=True, last_percent=last_alerted_percent,
                                        position_details=detailed_position_desc, total_calls=position.calls, total_puts=position.puts
                                    )
                                    voice_msg = f"Alert: {ticker} has increased another {percent_change - last_alerted_percent:.1f} percent, now at {percent_change:.1f} percent total."
                                else:
                                    telegram_msg = format_alert_message(
                                        ticker, percent_change, snapshot['prev_close'], snapshot['current_price'], 
                                        None, None, position_details=detailed_position_desc, total_calls=position.calls, total_puts=position.puts
                                    )
                                    direction = "up" if percent_change > 0 else "down"
                                    voice_msg = f"Alert: {ticker} is {direction} {abs(percent_change):.1f} percent."
                                
                                print(f"   📱 Message: {telegram_msg}")
                                print(f"   📞 Voice: {voice_msg}")
                                print("-" * 50)
                                
                                results['alerts_sent'] += 1
                                results['alerts_details'].append({
                                    'ticker': ticker,
                                    'current_price': snapshot['current_price'],
                                    'prev_close': snapshot['prev_close'],
                                    'percent_change': percent_change,
                                    'sms_sent': True,  # Mock success
                                    'voice_sent': True,  # Mock success
                                    'errors': [],
                                    'alert_type': alert_type,
                                    'alert_count': alert_count
                                })
                                
                                logger.info(f"🧪 LOCAL TEST: {alert_type} alert #{alert_count} printed for {ticker}")
                                continue
                            
                            # Production mode - send alert
                            logger.info(f"Sending {alert_type} alert #{alert_count} for {ticker}: {percent_change:+.2f}% change")
                            
                            try:
                                # Send alerts using separated services
                                alert_result = {
                                    'sms_sent': False,
                                    'voice_sent': False,
                                    'slack_sent': False,
                                    'discord_sent': False,
                                    'ifttt_sent': False,
                                    'errors': []
                                }
                                
                                # Send Telegram alert (no volume)
                                try:
                                    if alert_type == "incremental":
                                        alert_result['sms_sent'] = telegram_service.send_telegram_incremental_alert(
                                            ticker, last_alerted_percent, percent_change, position_desc,
                                            prev_close=snapshot['prev_close'],
                                            current_price=snapshot['current_price'],
                                            volume=None,
                                            avg_volume=None,
                                            detailed_position_desc=detailed_position_desc,
                                            total_calls=position.calls,
                                            total_puts=position.puts
                                        )
                                    else:
                                        alert_result['sms_sent'] = telegram_service.send_telegram_alert(
                                            ticker, percent_change, position_desc,
                                            prev_close=snapshot['prev_close'],
                                            current_price=snapshot['current_price'],
                                            volume=None,
                                            avg_volume=None,
                                            detailed_position_desc=detailed_position_desc,
                                            total_calls=position.calls,
                                            total_puts=position.puts
                                        )
                                except Exception as e:
                                    alert_result['errors'].append(f"Telegram: {e}")
                                    logger.warning(f"Telegram alert failed for {ticker}: {e}")
                                
                                # Send voice alert
                                try:
                                    if alert_type == "incremental":
                                        alert_result['voice_sent'] = twilio_service.send_voice_incremental_alert(
                                            ticker, last_alerted_percent, percent_change
                                        )
                                    else:
                                        alert_result['voice_sent'] = twilio_service.send_voice_alert(
                                            ticker, percent_change
                                        )
                                except Exception as e:
                                    alert_result['errors'].append(f"Voice: {e}")
                                    logger.warning(f"Voice alert failed for {ticker}: {e}")
                                
                                # Send other service alerts (Slack, Discord, IFTTT) - no volume
                                try:
                                    if alert_type == "incremental":
                                        alert_result['slack_sent'] = slack_service.send_slack_incremental_alert(
                                            ticker, last_alerted_percent, percent_change, position_desc,
                                            prev_close=snapshot['prev_close'],
                                            current_price=snapshot['current_price'],
                                            volume=None,
                                            avg_volume=None,
                                            detailed_position_desc=detailed_position_desc,
                                            total_calls=position.calls,
                                            total_puts=position.puts
                                        )
                                    else:
                                        alert_result['slack_sent'] = slack_service.send_slack_alert(
                                            ticker, percent_change, position_desc,
                                            prev_close=snapshot['prev_close'],
                                            current_price=snapshot['current_price'],
                                            volume=None,
                                            avg_volume=None,
                                            detailed_position_desc=detailed_position_desc,
                                            total_calls=position.calls,
                                            total_puts=position.puts
                                        )
                                except Exception as e:
                                    alert_result['errors'].append(f"Slack: {e}")
                                    logger.warning(f"Slack alert failed for {ticker}: {e}")
                                
                                try:
                                    alert_result['ifttt_sent'] = ifttt_service.send_ifttt_call()
                                except Exception as e:
                                    alert_result['errors'].append(f"IFTTT: {e}")
                                    logger.warning(f"IFTTT alert failed for {ticker}: {e}")
                                
                                # Mark as alerted for this session with updated count
                                self.alert_state.mark_alerted(ticker, percent_change, snapshot['prev_close'], alert_count)
                                
                                results['alerts_sent'] += 1
                                results['alerts_details'].append({
                                    'ticker': ticker,
                                    'current_price': snapshot['current_price'],
                                    'prev_close': snapshot['prev_close'],
                                    'percent_change': percent_change,
                                    'sms_sent': alert_result['sms_sent'],
                                    'voice_sent': alert_result['voice_sent'],
                                    'slack_sent': alert_result['slack_sent'],
                                    'discord_sent': alert_result['discord_sent'],
                                    'ifttt_sent': alert_result['ifttt_sent'],
                                    'errors': alert_result['errors'],
                                    'alert_type': alert_type,
                                    'alert_count': alert_count,
                                    'last_alerted_percent': last_alerted_percent if alert_type == "incremental" else None
                                })
                                
                                logger.info(f"Successfully processed {alert_type} alert #{alert_count} for {ticker}")
                                
                            except Exception as e:
                                error_msg = f"Failed to send {alert_type} alert for {ticker}: {e}"
                                logger.error(error_msg)
                                results['errors'].append(error_msg)
                                continue
                    
                    else:
                        logger.debug(f"{ticker} change {percent_change:+.2f}% below threshold")
                
                except Exception as e:
                    ticker_name = getattr(position, 'underlying', 'unknown')
                    error_msg = f"Error processing {ticker_name}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
                    continue
            
            logger.info(f"Alert check completed. Sent {results['alerts_sent']} alerts for {len(processed_tickers)} unique tickers")
            
        except Exception as e:
            error_msg = f"Alert check process failed: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            raise StockAlertError(error_msg)
        
        return results
