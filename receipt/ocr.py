from PIL import Image
import pytesseract
from pathlib import Path
import os
import logging
from receipt.pix import InterPix, NuPix, Pix

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# If you're on Windows, you might need to specify the tesseract path:
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
#Error opening data file C:\\\\Program Files\\\\Tesseract-OCR/tessdata/por.traineddata Please make sure the TESSDATA_PREFIX environment variable is set to your "tessdata" directory. Failed loading language \\\'por\\\' Tesseract couldn\\\'t load any languages! Could not initialize tesseract.\'

class TesseractOCR:

    @staticmethod
    def extract_from_image(image_path,save_raw=False):
        #try:
        # Open the image file
        img = Image.open(image_path)
        pix = None
        # Use Tesseract to do OCR on the image
        text = pytesseract.image_to_string(img, lang='por')
        if save_raw:
            filename = str(image_path).split('\\')[-1] + '.txt'
            logger.info(f"Saving file... {filename}")
            output_dir = Path("downloads")
            html_path = output_dir / filename
            html_path.write_text(
                text,
                encoding="utf-8"
            )

        match Pix.which_bank(text):
            case 1:
                pix = NuPix(text.split('\n'))
            case 2:
                pix = InterPix(text.split('\n'))

        return pix
        #except Exception as e:
        #    raise e
