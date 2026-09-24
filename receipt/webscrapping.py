from datetime import datetime
import time
from typing import List, Dict, Any
from pathlib import Path
import logging

# Third-party imports
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from urllib3 import HTTPConnectionPool

import os
from seleniumbase import SB

from consts import UNDEFINED,EZCAPTCHA_URL
from receipt.product import Product
#sudo dnf install -y xorg-x11-server-Xvfb mesa-libGL liberation-fonts

logger = logging.getLogger(__name__)
class WebScraper:
    """Handle web scraping with Selenium"""
    
    def __init__(self):
        self.driver = None
        #self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver"""
        chrome_options = Options()
        #chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def get_page_with_token(self,target_url, turnstile_token):
        self._setup_driver()
        page_source = ''
        try:
            # 1. Navigate to the website hosting the Cloudflare Turnstile widget
            logger.info(f"Navigating to {target_url}...")
            self.driver.get(target_url)
            
            # Wait a moment for the page elements to load
            time.sleep(5)
            
            self.driver.execute_script(f"""
                // Locate the Turnstile response textareas (Cloudflare creates these automatically)
                var inputElements = document.getElementsByName('cf-turnstile-response');
                if (inputElements.length > 0) {{
                    inputElements[0].value = '{turnstile_token}';
                }} else {{
                    console.error('Turnstile container input field not found.');
                }}
            """)
            
            # Fire native event callbacks (Many frameworks rely on this to activate the submit button)
            logger.driver.execute_script("""
                var inputElements = document.getElementsByName('cf-turnstile-response');
                if (inputElements.length > 0) {
                    var event = new Event('change', { bubbles: true });
                    inputElements[0].dispatchEvent(event);
                }
            """)
            
            # Handle Submission via the <a> element
            button_xpath = "//a[contains(@class, 'btn') and contains(@class, 'btn-primary') and contains(@class, 'center-block')]"
            
            submit_btn = WebDriverWait(self.driver, 7).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            submit_btn.click()
            #logger.info("Successfully clicked the submit button via Selenium.")
 
            # Wait for the new page content to load completely
            time.sleep(5) 
        
            # Extract the protected page source code
            page_source =  self.driver.page_source
        except TimeoutException as e:
            logger.error(f"Timeout error: {e}")
            page_source = ''
        except HTTPConnectionPool as e:
            logger.error(f"Connection error: {e}")
            page_source = ''
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            page_source = ''
        finally:
            # Clean up and close the browser session
            self.driver.quit()
            return page_source

    def get_datakey(self,url):
        self._setup_driver()
        print(url)
        sitekey = ''
        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 10)
            turnstile_element = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".cf-turnstile, [data-sitekey]"))
            )
            sitekey = turnstile_element.get_attribute("data-sitekey")
        except Exception as e:
            if 'ERR_CONNECTION_RESET' in str(e) or 'PR_CONNECT_RESET_ERROR' in str(e):
                logger.error(f"Receita GOV error: {e.args}")
            logger.error(f"Datakey error: {e}")
            sitekey = ''
        finally:
            # Clean up and close the browser session
            self.driver.quit()
            return sitekey

    def get_captcha_token(self,url,datakey):
        try:
            data = {"sitekey": datakey,
                "siteurl":url
                }
            response = requests.post(EZCAPTCHA_URL, json=data)
            
            # Check if the service responded successfully
            if response.status_code == 200:
                # If the service returns JSON text, parse it directly:
                result = response.json() 
                logger.info(f'Got the Captcha Token in {result["elapsed"]}s')
                return result['token']
            logger.error(f'Failed on EZCAPTCHA {response.text}')
            return 0
        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to the service. Is it running?")

        
    @DeprecationWarning
    def scrape_receipt_items(self, target_url: str, user_id=None) -> List[Dict[str, str]]:
        try:
            with SB(uc=True, xvfb=True, test=True) as sb:
                logger.info(f"Scraping URL: {target_url}")
                # 1. Open the portal and let the UC anti-fingerprint engine settle
                sb.uc_open_with_reconnect(target_url, reconnect_time=5)
                
                # 2. Wait for the main document structure to load
                sb.wait_for_element("body")
                
                # 3. Handle the Turnstile Checkbox
                try:
                    sb.uc_gui_click_captcha()
                    #print("[+] Turnstile challenge cleared successfully.")
                except Exception as e:
                    logger.info("Interactive click wasn't required or timed out (it may have passed automatically).")
                    sb.save_screenshot("downloads/scrap_receipt_items.png")

                # 4. Submit the Query form
                visualizar_selector = 'a:contains("Visualizar"), button:contains("Visualizar"), span:contains("Visualizar")'
                sb.wait_for_element_clickable(visualizar_selector, timeout=15)
                
                # 5. Perform a human-simulated click to trigger the JSF form submit
                sb.click(visualizar_selector)
                
                # 6. Wait for the server backend to respond and process the receipt data
                sb.sleep(8)
                page_source = sb.get_page_source()
        
            return self.scrap_items(page_source, user_id)
        except TimeoutException as e:
            logger.error(f"Timeout error: {e}")
            return []
        except HTTPConnectionPool as e:
            logger.error(f"Connection error: {e}")
            return []
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return []

    @DeprecationWarning
    def scrape_receipt_items_old(self, url: str, user_id=None) -> List[Dict[str, str]]:
        """Scrape receipt items from website with table ID 'myTable'"""
        try:
            logger.info(f"Scraping URL: {url}")
            self.driver.get(url)

            #self.driver.uc_open_with_reconnect(url, reconnect_time=5)
            #time.sleep(3) # Allow any background scripts to finish loading

            # Wait for table to load
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.ID, "myTable")))

            return self.scrap_items(self.driver.page_source,user_id)

        except TimeoutException:
            logger.error("Timeout waiting for table to load")

            # Save the HTML currently loaded in the browser
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("downloads")
            output_dir.mkdir(parents=True, exist_ok=True)

            html_path = output_dir / f"timeout_{timestamp}.html"
            screenshot_path = output_dir / f"timeout_{timestamp}.png"

            html_path.write_text(
                self.driver.page_source,
                encoding="utf-8"
            )

            self.driver.save_screenshot(str(screenshot_path))

            logger.error(f"Saved timeout HTML to: {html_path}")
            logger.error(f"Saved timeout screenshot to: {screenshot_path}")
            return []
        except HTTPConnectionPool as e:
            logger.error(f"Connection error: {e}")
            return []
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()

    def scrap_items(self, page_source, user_id):
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')

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
    