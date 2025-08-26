import boto3
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Set, Dict
from botocore.exceptions import ClientError, NoCredentialsError
from .config import Config
from .exceptions import AlertStateError

logger = logging.getLogger(__name__)

class AlertStateManager:
    def __init__(self):
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=Config.AWS_REGION)
            self.table = self.dynamodb.Table(Config.DYNAMODB_TABLE_NAME)
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise AlertStateError("AWS credentials not configured")
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB client: {e}")
            raise AlertStateError(f"Failed to initialize DynamoDB: {e}")
    
    def _get_session_key(self, prev_close: float) -> str:
        """Get session key based on previous day close price for reset logic"""
        # Use the prevDay.c value as the session identifier
        # When prevDay.c changes, it means a new trading session has started
        return f"session_{prev_close:.2f}"
    
    def get_alert_status(self, ticker: str, prev_close: float) -> Optional[Dict]:
        """Get alert status for ticker in this session - returns None if never alerted, or dict with details"""
        try:
            session_key = self._get_session_key(prev_close)
            composite_key = f"{ticker}#{session_key}"
            
            logger.debug(f"Checking alert status for {composite_key}")
            
            response = self.table.get_item(
                Key={'ticker_date': composite_key}
            )
            
            if 'Item' in response:
                item = response['Item']
                return {
                    'last_alerted_percent': float(item.get('last_alerted_percent', 0)),
                    'alert_count': int(item.get('alert_count', 1)),
                    'timestamp': item.get('timestamp'),
                    'exists': True
                }
            else:
                logger.debug(f"No alert record found for {ticker} in session {session_key}")
                return None
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"DynamoDB table {Config.DYNAMODB_TABLE_NAME} not found")
                raise AlertStateError(f"DynamoDB table {Config.DYNAMODB_TABLE_NAME} does not exist")
            else:
                logger.error(f"DynamoDB error checking alert state for {ticker}: {e}")
                raise AlertStateError(f"Failed to check alert state: {e}")
        except Exception as e:
            logger.error(f"Unexpected error checking alert state for {ticker}: {e}")
            raise AlertStateError(f"Unexpected error checking alert state: {e}")
    
    def get_alert_details(self, ticker: str, prev_close: float) -> Optional[Dict]:
        """Get alert details for a ticker if it was alerted in this session"""
        try:
            session_key = self._get_session_key(prev_close)
            composite_key = f"{ticker}#{session_key}"
            
            logger.debug(f"Getting alert details for {composite_key}")
            
            response = self.table.get_item(
                Key={'ticker_date': composite_key}
            )
            
            if 'Item' in response:
                item = response['Item']
                # Convert the UTC timestamp to AWS local time (depends on region, but commonly EST)
                try:
                    from datetime import datetime, timezone, timedelta
                    utc_timestamp = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                    
                    # Convert to AWS region local time (assuming US East for most Lambda deployments)
                    try:
                        import zoneinfo
                        aws_local = zoneinfo.ZoneInfo("America/New_York")
                        local_timestamp = utc_timestamp.astimezone(aws_local)
                        formatted_time = local_timestamp.strftime("%Y-%m-%d %I:%M:%S %p %Z")
                    except Exception:
                        # Fallback to EST
                        est = timezone(timedelta(hours=-5))
                        local_timestamp = utc_timestamp.astimezone(est)
                        formatted_time = local_timestamp.strftime("%Y-%m-%d %I:%M:%S %p EST")
                    
                    return {
                        'ticker': item['ticker'],
                        'timestamp': formatted_time,
                        'percent_change': float(item['percent_change'])
                    }
                except Exception as e:
                    logger.warning(f"Error formatting timestamp for {ticker}: {e}")
                    return {
                        'ticker': item['ticker'],
                        'timestamp': item['timestamp'],
                        'percent_change': float(item['percent_change'])
                    }
            
            return None
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"DynamoDB table {Config.DYNAMODB_TABLE_NAME} not found")
                raise AlertStateError(f"DynamoDB table {Config.DYNAMODB_TABLE_NAME} does not exist")
            else:
                logger.error(f"DynamoDB error getting alert details for {ticker}: {e}")
                raise AlertStateError(f"Failed to get alert details: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting alert details for {ticker}: {e}")
            raise AlertStateError(f"Unexpected error getting alert details: {e}")
    
    def mark_alerted(self, ticker: str, percent_change: float, prev_close: float, alert_count: int = 1) -> None:
        """Mark ticker as alerted for this trading session or update with new percentage"""
        try:
            session_key = self._get_session_key(prev_close)
            composite_key = f"{ticker}#{session_key}"
            timestamp = datetime.now(timezone.utc).isoformat()
            
            logger.info(f"Marking {ticker} as alerted for {session_key} with {percent_change}% change (alert #{alert_count})")
            
            # Ensure proper Decimal conversion for DynamoDB
            try:
                # Convert float to string first, then to Decimal to avoid float precision issues
                percent_str = f"{percent_change:.6f}"
                decimal_percent_change = Decimal(percent_str)
                logger.debug(f"Converted {percent_change} ({type(percent_change)}) to Decimal: {decimal_percent_change}")
            except Exception as conv_error:
                logger.error(f"Error converting {percent_change} to Decimal: {conv_error}")
                # Fallback - use rounded value
                decimal_percent_change = Decimal(str(round(float(percent_change), 4)))
            
            # Calculate TTL as integer
            ttl_timestamp = int(datetime.now(timezone.utc).timestamp() + 86400 * 7)
            
            item = {
                'ticker_date': composite_key,
                'ticker': ticker,
                'session_key': session_key,
                'prev_close': Decimal(str(prev_close)),
                'last_alerted_percent': decimal_percent_change,
                'percent_change': decimal_percent_change,
                'alert_count': alert_count,
                'timestamp': timestamp,
                'ttl': ttl_timestamp
            }
            
            logger.debug(f"DynamoDB item to save: {item}")
            logger.debug(f"Item types: {[(k, type(v)) for k, v in item.items()]}")
            
            self.table.put_item(Item=item)
            
            logger.info(f"Successfully marked {ticker} as alerted (alert #{alert_count})")
            
        except ClientError as e:
            logger.error(f"DynamoDB error marking {ticker} as alerted: {e}")
            raise AlertStateError(f"Failed to mark {ticker} as alerted: {e}")
        except Exception as e:
            logger.error(f"Unexpected error marking {ticker} as alerted: {e}")
            raise AlertStateError(f"Unexpected error marking ticker as alerted: {e}")
    
    def get_session_alerted_tickers(self, prev_close: float) -> Set[str]:
        """Get set of all tickers that have been alerted in this session"""
        try:
            session_key = self._get_session_key(prev_close)
            
            logger.debug(f"Fetching all alerted tickers for {session_key}")
            
            # Scan for all items with this session key
            response = self.table.scan(
                FilterExpression='#session_key = :session',
                ExpressionAttributeNames={'#session_key': 'session_key'},
                ExpressionAttributeValues={':session': session_key}
            )
            
            tickers = {item['ticker'] for item in response.get('Items', [])}
            
            logger.debug(f"Found {len(tickers)} alerted tickers for session {session_key}: {tickers}")
            return tickers
            
        except ClientError as e:
            logger.error(f"DynamoDB error fetching today's alerts: {e}")
            raise AlertStateError(f"Failed to fetch today's alerts: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching today's alerts: {e}")
            raise AlertStateError(f"Unexpected error fetching today's alerts: {e}")
    
    def cleanup_old_records(self, days_to_keep: int = 7) -> None:
        """Clean up old alert records (optional maintenance function)"""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.timestamp() - (days_to_keep * 86400)
            
            logger.info(f"Cleaning up alert records older than {days_to_keep} days")
            
            # This is handled by TTL, but can be implemented if needed
            logger.info("Cleanup handled by DynamoDB TTL")
            
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
            # Don't raise exception for cleanup failures