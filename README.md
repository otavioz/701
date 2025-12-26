receipt-bot/
│
├── main.py                    # Main bot file
├── requirements.txt           # Dependencies
├── config.py                  # Configuration
├── .env.example               # Environment variables template
│
├── src/
│   ├── __init__.py
│   ├── bot.py                 # Main bot class
│   ├── qr_processor.py        # QR code processing
│   ├── web_scraper.py         # Web scraping with Selenium
│   ├── html_parser.py         # HTML parsing
│   ├── error_handler.py       # Error handling
│   └── timezone_config.py     # Timezone management
│
├── utils/
│   ├── __init__.py
│   ├── file_utils.py          # File operations
│   ├── text_utils.py          # Text processing utilities
│   └── validation.py          # Input validation
│
├── logs/                      # Log directory (created automatically)
│   └── .gitkeep
│
└── README.md                  # Project documentation