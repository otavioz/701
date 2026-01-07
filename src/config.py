"""
Configuration management for Receipt Bot
"""
import json
import os
from typing import Dict, Any
from pathlib import Path
import pytz

from consts import USER_DATA

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables
    """
    # Required configuration
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not telegram_token:
        raise ValueError(
            "❌ TELEGRAM_BOT_TOKEN environment variable is required\n"
            "Set it in .env file or export TELEGRAM_BOT_TOKEN='your_token'"
        )
    
    # Optional configuration with defaults
    config = {
        'telegram_token': telegram_token,
        'admin_chat_id': os.getenv('ADMIN_CHAT_ID'),
        'timezone': os.getenv('BOT_TIMEZONE', 'America/Sao_Paulo'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'max_retries': int(os.getenv('MAX_RETRIES', '3')),
        'session_timeout': int(os.getenv('SESSION_TIMEOUT', '3600')),
        'chrome_driver_path': os.getenv('CHROME_DRIVER_PATH'),
        'download_dir': os.getenv('DOWNLOAD_DIR', 'downloads')
    }
    
    # Validate timezone
    try:
        pytz.timezone(config['timezone'])
    except pytz.exceptions.UnknownTimeZoneError:
        print(f"⚠️  Unknown timezone: {config['timezone']}, using UTC")
        config['timezone'] = 'UTC'
    
    # Create necessary directories
    Path(config['download_dir']).mkdir(exist_ok=True)
    
    return config

def setup_environment():
    """Setup environment variables from .env file if exists"""
    env_file = Path('.env')
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✅ Loaded environment variables from .env file")
        except ImportError:
            print("⚠️  python-dotenv not installed, skipping .env file")
    else:
        print("ℹ️  .env file not found, using system environment variables")

def get_supported_timezones() -> Dict[str, str]:
    """Get dictionary of supported timezones"""
    return {
        'BR': 'America/Sao_Paulo',      # Brazil (Brasília)
        'BR_AC': 'America/Rio_Branco',  # Brazil (Acre)
        'BR_AM': 'America/Manaus',      # Brazil (Amazonas)
        'US_ET': 'America/New_York',    # US Eastern
        'US_CT': 'America/Chicago',     # US Central
        'US_MT': 'America/Denver',      # US Mountain
        'US_PT': 'America/Los_Angeles', # US Pacific
        'UK': 'Europe/London',          # United Kingdom
        'EU': 'Europe/Berlin',          # Central Europe
        'UTC': 'UTC',
        'JP': 'Asia/Tokyo',             # Japan
        'AU': 'Australia/Sydney',       # Australia
        'IN': 'Asia/Kolkata',           # India
    }

def get_permitted_users() -> list[int]:
    with open(USER_DATA, "r") as json_file:
        data_read = json.load(json_file)
    return data_read['permitted']

def set_permitted_user(user_id):
    # 1. Read the existing data
    with open(USER_DATA, 'r') as f:
        # Use json.load() to convert JSON data into a Python list
        data_list = json.load(f)

    # 2. Append the new data to the Python list
    data_list['permitted'].append(user_id)

    # 3. Write the entire updated list back to the file
    with open(USER_DATA, 'w') as f:
        # Use json.dump() to write the updated list as JSON
        json.dump(data_list, f, indent=2) # Using indent for readability