from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
import logging

# Third-party imports
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from consts import UNDEFINED
from receipt.product import Product

logger = logging.getLogger(__name__)
class WebScraper:
    """Handle web scraping with Selenium"""
    
    def __init__(self):
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def scrape_receipt_items(self, url: str, user_id=None) -> List[Dict[str, str]]:
        """Scrape receipt items from website with table ID 'myTable'"""
        try:
            logger.info(f"Scraping URL: {url}")
            self.driver.get(url)
            
            # Wait for table to load
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.ID, "myTable")))
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Find div with div "accordion"
            table = soup.find('div', {'id': 'accordion'})
            if not table:
                logger.error("Table with div 'accordion' not found")
                return []
            
            owner = UNDEFINED
            shop = UNDEFINED
            date = UNDEFINED
            
            """
            owner: fica no primeiro div class="panel panel-default" 
            shop: fica no quarto div class="panel panel-default"
            date: fica no quarto div class="panel panel-default"
            """
            sub_table = table.find_all('table', {'class': 'table table-hover'})
            if len(sub_table) >= 8:
                try:
                    owner = sub_table[0].find('tbody').find('td').get_text(strip=True)
                    shop = sub_table[3].find('tbody').find('td').get_text(strip=True)
                    date = sub_table[5].find('tbody').find_all('td')[3].get_text(strip=True)
                except IndexError:
                    pass
                
            if owner == '':
                owner = user_id
                            
            # Find table with ID "myTable"
            table = soup.find('tbody', {'id': 'myTable'})
            if not table:
                logger.error("Table with ID 'myTable' not found")
                return []
            
            items = []
            # Iterate through table rows
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 4:  # Assuming at least 4 columns
                    # product_name, quantity, unity, price, owner, shop,code=None, date=None, formatted=False
                    items.append(Product(product_name = tds[0].get_text(strip=True),
                                          quantity = tds[1].get_text(strip=True),
                                          unity = tds[2].get_text(strip=True),
                                          price = tds[3].get_text(strip=True),
                                          owner = owner,
                                          shop = shop,
                                          date = date))
     
            
            #logger.info(f"Found {len(items)} items")
            return items
            
        except TimeoutException:
            logger.error("Timeout waiting for table to load")
            return []
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()