import os
import logging
import tempfile
from typing import List, Dict, Any
from urllib.parse import urlparse

# Third-party imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from consts import PRODUCT_DIR, UNDEFINED
from receipt.ocr import TesseractOCR
from receipt.pix import Pix
from receipt.product import Product
from receipt.qrcode import QRCodeProcessor
from receipt.webscrapping import WebScraper
from utils import save_img_bkp

logger = logging.getLogger(__name__)

class BillReceiptBot:

    def __init__(self):
        self.user_sessions = {}

    