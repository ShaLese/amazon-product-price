from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from fake_useragent import UserAgent
import logging
import time
import os
import sys
from urllib.parse import quote_plus

# Configure logging for cloud environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

class AmazonScraper:
    def __init__(self, csv_file, region='US'):
        try:
            logging.info(f"Initializing AmazonScraper with CSV file: {csv_file} and region: {region}")
            self.csv_file = csv_file
            self.ua = UserAgent()
            self.region = region.upper()
            
            # Define region-specific settings
            self.region_settings = {
                'US': {'domain': 'com', 'currency': 'USD', 'symbol': '$'},
                'UK': {'domain': 'co.uk', 'currency': 'GBP', 'symbol': '£'},
                'DE': {'domain': 'de', 'currency': 'EUR', 'symbol': '€'},
                'FR': {'domain': 'fr', 'currency': 'EUR', 'symbol': '€'},
                'IT': {'domain': 'it', 'currency': 'EUR', 'symbol': '€'},
                'ES': {'domain': 'es', 'currency': 'EUR', 'symbol': '€'},
            }
            
            if self.region not in self.region_settings:
                logging.warning(f"Unsupported region {region}, defaulting to US")
                self.region = 'US'
                
            region_data = self.region_settings[self.region]
            self.base_url = f"https://www.amazon.{region_data['domain']}/s?k="
            
            try:
                # Set up Chrome options for cloud environment
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-software-rasterizer')
                options.add_argument('--disable-extensions')
                options.add_argument(f'user-agent={self.ua.random}')
                
                # Initialize Chrome WebDriver for cloud
                service = Service('/usr/bin/chromedriver')
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.implicitly_wait(10)
                logging.info("Chrome WebDriver initialized successfully")
                
            except Exception as e:
                logging.error(f"Failed to initialize WebDriver: {str(e)}")
                raise Exception("Failed to initialize WebDriver in cloud environment")

        except Exception as e:
            logging.error(f"Error initializing scraper: {str(e)}", exc_info=True)
            raise

    def get_price(self, item_name):
        try:
            search_url = self.base_url + quote_plus(item_name)
            logging.info(f"Searching for: {item_name}")
            logging.info(f"URL: {search_url}")
            
            self.driver.get(search_url)
            logging.info("Page loaded successfully")
            
            # Wait for price elements to load
            wait = WebDriverWait(self.driver, 10)
            
            # Try different price selectors in order of preference
            price_selectors = [
                "span.a-price span.a-offscreen",  # Full price with decimals
                "span.a-price-whole",  # Just the whole number part
                "span.a-price",  # Full price element
                "span[data-a-color='price'] span.a-offscreen"  # Alternative price format
            ]
            
            for selector in price_selectors:
                try:
                    price_element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    price_text = price_element.get_attribute("textContent").strip()
                    
                    # Clean up the price text
                    price_text = price_text.replace('$', '').replace(',', '').strip()
                    
                    # Extract numeric value
                    import re
                    price_match = re.search(r'(\d+\.?\d*)', price_text)
                    if price_match:
                        price = float(price_match.group(1))
                        currency = self.region_settings[self.region]['currency']
                        logging.info(f"Price found for {item_name}: {self.region_settings[self.region]['symbol']}{price:.2f} ({currency})")
                        return f"{price:.2f}"
                except (TimeoutException, NoSuchElementException, ValueError) as e:
                    logging.debug(f"Failed with selector {selector}: {str(e)}")
                    continue
            
            logging.warning(f"No valid price found for {item_name}")
            return None

        except Exception as e:
            logging.error(f"Error processing {item_name}: {str(e)}", exc_info=True)
            return None

    def scrape_prices(self):
        try:
            logging.info("Starting price scraping process")
            df = pd.read_csv(self.csv_file)
            prices = []
            urls = []
            
            for item in df['item_name']:
                try:
                    search_url = f"https://www.amazon.{self.region_settings[self.region]['domain']}/s?k={quote_plus(item)}"
                    self.driver.get(search_url)
                    time.sleep(2)  # Wait for page load
                    
                    # Try to find the first product link and price
                    try:
                        first_result = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-result-item[data-component-type='s-search-result']"))
                        )
                        
                        # Try different price selectors
                        price_selectors = [
                            "span.a-price span.a-offscreen",
                            "span.a-price-whole",
                            "span.a-price span[aria-hidden='true']",
                            "span.a-price"
                        ]
                        
                        price = None
                        for selector in price_selectors:
                            try:
                                price_element = first_result.find_element(By.CSS_SELECTOR, selector)
                                price_text = price_element.text.strip()
                                if selector == "span.a-price span.a-offscreen":
                                    price_text = price_element.get_attribute("textContent").strip()
                                
                                # Clean up price text and extract numeric value
                                price_text = price_text.replace(',', '').replace('$', '').replace('£', '').replace('€', '')
                                import re
                                price_match = re.search(r'\d+\.?\d*', price_text)
                                if price_match:
                                    price = price_match.group()
                                    break
                            except:
                                continue
                        
                        if price is None:
                            raise NoSuchElementException("No price found with any selector")
                        
                        # Get the product URL
                        product_link = first_result.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline").get_attribute('href')
                        
                        prices.append(price)
                        urls.append(product_link)
                        logging.info(f"Scraped price for {item}: {self.region_settings[self.region]['symbol']}{price} ({self.region_settings[self.region]['currency']})")
                        
                    except (TimeoutException, NoSuchElementException) as e:
                        logging.warning(f"Could not find price for {item}: {str(e)}")
                        prices.append("Not found")
                        urls.append(search_url)
                    
                    except Exception as e:
                        logging.error(f"Error processing item {item}: {str(e)}")
                        prices.append("Error")
                        urls.append(search_url)
                        
                except Exception as e:
                    logging.error(f"Error processing item {item}: {str(e)}")
                    prices.append("Error")
                    urls.append(search_url)
            
            # Update the DataFrame with all information
            df['item_price'] = prices
            df['item_url'] = urls
            
            # Set currency information for successful price fetches
            df.loc[~df['item_price'].isin(["Error", "Not found"]), 'currency'] = self.region_settings[self.region]['currency']
            df.loc[~df['item_price'].isin(["Error", "Not found"]), 'currency_symbol'] = self.region_settings[self.region]['symbol']
            
            # Clear currency info for failed fetches
            df.loc[df['item_price'].isin(["Error", "Not found"]), ['currency', 'currency_symbol']] = ""
            
            df.to_csv(self.csv_file, index=False)
            logging.info("Price scraping completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error in scrape_prices: {str(e)}")
            return False

    def update_prices(self):
        try:
            logging.info("Starting price update process")
            
            # Verify CSV file exists
            if not os.path.exists(self.csv_file):
                logging.error(f"CSV file not found: {self.csv_file}")
                return False
                
            # Read the CSV file
            logging.info(f"Reading CSV file: {self.csv_file}")
            df = pd.read_csv(self.csv_file)
            
            if 'item_name' not in df.columns:
                logging.error("CSV file must contain 'item_name' column")
                return False

            logging.info(f"Found {len(df)} items to process")

            # Process each item
            for index, row in df.iterrows():
                item_name = row['item_name']
                logging.info(f"Processing item {index + 1}/{len(df)}: {item_name}")
                price = self.get_price(item_name)
                df.at[index, 'item_price'] = price
                logging.info(f"Updated price for {item_name}: {price}")
                time.sleep(2)  # Be nice to Amazon's servers

            # Save updated DataFrame back to CSV
            logging.info("Saving updated prices to CSV file")
            df.to_csv(self.csv_file, index=False)
            logging.info(f"CSV file updated successfully with prices in {self.region_settings[self.region]['currency']}")
            return True

        except Exception as e:
            logging.error(f"Error updating prices: {str(e)}", exc_info=True)
            return False
            
    def __del__(self):
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
                logging.info("WebDriver closed successfully")
        except Exception as e:
            logging.error(f"Error closing WebDriver: {str(e)}")

if __name__ == "__main__":
    try:
        logging.info("Starting Amazon Price Scraper")
        csv_file = "products.csv"
        
        # Verify CSV file exists
        if not os.path.exists(csv_file):
            logging.error(f"CSV file not found: {csv_file}")
            sys.exit(1)
            
        scraper = AmazonScraper(csv_file, region='US')
        success = scraper.scrape_prices()
        
        if success:
            logging.info("Scraping process completed successfully")
        else:
            logging.error("Scraping process completed with errors")
            
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure the WebDriver is closed
        if 'scraper' in locals():
            del scraper
