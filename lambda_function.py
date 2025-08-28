import json
import logging
import sys
import os
from datetime import datetime

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Handle command line arguments before importing config
if __name__ == "__main__":
    # Check for --test argument
    test_mode = '--test' in sys.argv
    
    if test_mode:
        # Set environment variables for test mode BEFORE importing Config
        os.environ['LOCAL_TESTING_MODE'] = 'true'
        os.environ.setdefault('S3_BUCKET_NAME', 'schwab-positions-bucket')
        os.environ.setdefault('POSITIONS_JSON_KEY', 'positions.json')
        os.environ.setdefault('POLYGON_API_KEY', 'vAFV5Hzy2OrTozBZuOFw5EwpZdNQ1leZ')
        os.environ.setdefault('ALERT_THRESHOLD_PERCENT', '5.0')

from src.config import Config
from src.alert_checker import AlertChecker
from src.exceptions import StockAlertError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create console handler if not exists
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def lambda_handler(event, context):
    """
    AWS Lambda handler for stock alert checking
    
    Args:
        event: Lambda event data (not used but required)
        context: Lambda context object
    
    Returns:
        dict: Response with status code and results
    """
    
    try:
        logger.info("=== Stock Alert Check Started ===")
        logger.info(f"⏰ Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"🆔 Request ID: {context.aws_request_id}")
        logger.info(f"⚡ Remaining Time: {context.get_remaining_time_in_millis()}ms")
        
        # Check for local testing mode early
        if Config.LOCAL_TESTING_MODE:
            logger.info("🧪 LOCAL TESTING MODE ENABLED")
        
        # Validate configuration
        try:
            Config.validate()
            logger.info("Configuration validation passed")
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Configuration Error',
                    'message': str(e),
                    'request_id': context.aws_request_id
                })
            }
        
        # Initialize alert checker
        logger.info("Initializing alert checker")
        alert_checker = AlertChecker()
        
        # Run alert check
        logger.info("Running alert check")
        results = alert_checker.check_and_alert()
        
        # Log summary
        logger.info("=== Alert Check Summary ===")
        logger.info(f"Positions checked: {results['positions_checked']}")
        logger.info(f"Snapshots fetched: {results['snapshots_fetched']}")
        logger.info(f"Alerts sent: {results['alerts_sent']}")
        logger.info(f"Skipped (already alerted): {results['skipped_already_alerted']}")
        logger.info(f"Errors: {len(results['errors'])}")
        
        if results['errors']:
            logger.warning("Errors encountered:")
            for error in results['errors']:
                logger.warning(f"  - {error}")
        
        if results['alerts_details']:
            logger.info("🚨 ALERTS SENT:")
            for alert in results['alerts_details']:
                logger.info(f"  📈 {alert['ticker']}: {alert['percent_change']:+.2f}% "
                           f"(📱 Telegram: {'✅' if alert['sms_sent'] else '❌'}, "
                           f"📞 Voice: {'✅' if alert['voice_sent'] else '❌'})")
                logger.info(f"     💰 Price: ${alert['prev_close']:.2f} → ${alert['current_price']:.2f}")
        
        if results.get('skipped_details'):
            logger.info("⏭️  SKIPPED (ALREADY ALERTED):")
            for skipped in results['skipped_details']:
                logger.info(f"  📊 {skipped['ticker']}: Originally alerted at {skipped['timestamp']} "
                           f"({skipped['percent_change']:+.2f}%)")
        
        # Determine success status
        status_code = 200
        if results['errors'] and results['alerts_sent'] == 0:
            status_code = 500  # Complete failure
        elif results['errors']:
            status_code = 207  # Partial success
        
        response = {
            'statusCode': status_code,
            'body': json.dumps({
                'message': 'Alert check completed',
                'request_id': context.aws_request_id,
                'results': {
                    'positions_checked': results['positions_checked'],
                    'snapshots_fetched': results['snapshots_fetched'],
                    'alerts_sent': results['alerts_sent'],
                    'skipped_already_alerted': results['skipped_already_alerted'],
                    'error_count': len(results['errors']),
                    'alerts_details': results['alerts_details'],
                    'skipped_details': results.get('skipped_details', [])
                },
                'errors': results['errors'] if results['errors'] else None
            })
        }
        
        logger.info("=== Stock Alert Check Completed ===")
        return response
        
    except StockAlertError as e:
        logger.error(f"Stock alert error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Stock Alert Error',
                'message': str(e),
                'request_id': context.aws_request_id
            })
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal Error',
                'message': str(e),
                'request_id': context.aws_request_id
            })
        }

# For local testing and production runs
if __name__ == "__main__":
    # test_mode was already determined at the top of the file
    test_mode = '--test' in sys.argv
    
    if test_mode:
        print("🧪 Starting LOCAL TESTING MODE")
        print("=" * 60)
        print("This will:")
        print("• Download positions from S3")
        print("• Fetch real market data from Polygon")
        print("• Print alerts to console (no Telegram/calls sent)")
        print("• Use 5% threshold for upward movement alerts")
        print("=" * 60)
        
        class MockContext:
            aws_request_id = "local-test-123"
            
            def get_remaining_time_in_millis(self):
                return 300000  # 5 minutes for testing
        
        try:
            result = lambda_handler({}, MockContext())
            print("\n" + "=" * 60)
            print("🧪 LOCAL TEST COMPLETED")
            print("=" * 60)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"\n❌ LOCAL TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        # Production mode - use actual environment variables
        print("🚀 Starting PRODUCTION MODE")
        print("=" * 60)
        print("This will:")
        print("• Download positions from S3")
        print("• Fetch real market data from Polygon")
        print("• Send actual Telegram messages and voice calls")
        print("• Use DynamoDB to prevent duplicate alerts")
        print("• Use configured threshold percentage")
        print("=" * 60)
        
        # Verify required environment variables are set
        required_vars = [
            'S3_BUCKET_NAME', 'POSITIONS_FILE_KEY', 'POLYGON_API_KEY',
            'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID',
            'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 
            'TWILIO_VOICE_FROM_NUMBER', 'ALERT_PHONE_NUMBER'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            print(f"\n❌ MISSING ENVIRONMENT VARIABLES:")
            for var in missing_vars:
                print(f"   {var}")
            print("\nPlease set these environment variables before running in production mode.")
            print("Use --test flag for local testing mode.")
            sys.exit(1)
        
        class MockContext:
            aws_request_id = "local-production-run"
            
            def get_remaining_time_in_millis(self):
                return 300000  # 5 minutes for testing
        
        try:
            result = lambda_handler({}, MockContext())
            print("\n" + "=" * 60)
            print("🚀 PRODUCTION RUN COMPLETED")
            print("=" * 60)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"\n❌ PRODUCTION RUN FAILED: {e}")
            import traceback
            traceback.print_exc()
