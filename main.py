#!/usr/bin/env python3
import os
import sys
import signal
import logging
from pathlib import Path

# Add src directory to Python path
#sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.bot import AP701Bot
from src.config import load_config, setup_environment

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\n🛑 Shutting down bot gracefully...")
    sys.exit(0)

def setup_logging():
    """Setup logging configuration"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    """Main function"""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Setup environment
        setup_environment()
        
        # Load configuration
        config = load_config()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Create and run bot
        bot = AP701Bot(
            telegram_token=config['telegram_token'],
            admin_chat_id=config.get('admin_chat_id')
        )
        
        logger.info("🤖 Starting Receipt Bot...")
        print("Receipt Bot Started!")
        print("=" * 50)
        
        # Run the bot
        bot.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"Failed to start bot: {e}", exc_info=True)
        print(f"❌ Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()