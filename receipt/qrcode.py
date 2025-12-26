import logging
from typing import List, Dict, Any
from pathlib import Path

# Third-party imports
from selenium.webdriver.support import expected_conditions as EC
import cv2
from pyzbar.pyzbar import decode

logger = logging.getLogger(__name__)
class QRCodeProcessor:
    """Handle QR code detection and decoding"""
    
    @staticmethod
    def detect_qr_codes(image_path: str) -> List[Dict]:
        """Detect and decode QR codes from image"""
        try:
            image = cv2.imread(image_path)
            if image is None:
                return []
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            decoded_objects = decode(gray)
            
            qr_codes = []
            for obj in decoded_objects:
                qr_data = obj.data.decode('utf-8')
                qr_codes.append({
                    'data': qr_data,
                    'type': obj.type,
                    'is_url': QRCodeProcessor._is_valid_url(qr_data)
                })
            
            return qr_codes
        except Exception as e:
            logger.error(f"QR code detection error: {e}")
            return []
    
    @staticmethod
    def _is_valid_url(data: str) -> bool:
        """Check if data is a valid URL"""
        try:
            from urllib.parse import urlparse
            result = urlparse(data)
            return all([result.scheme, result.netloc])
        except:
            return False