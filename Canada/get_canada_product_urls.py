from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time
import json
import re


class AmazonScraper:
    def __init__(self, headless=False):
        """Initialize the Amazon scraper with Chrome driver"""
        self.options = Options()
        if headless:
            self.options.add_argument("--headless")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=self.options
        )
        self.wait = WebDriverWait(self.driver, 15)
        
    def setup_amazon(self):
        """Navigate to Amazon homepage and handle bot checks"""
        print("-> Starting Amazon scraper...")
        self.driver.get("https://www.amazon.ca/")
        
        # # Handle "Continue Shopping" screen (bot check)
        # try:
        #     continue_btn = WebDriverWait(self.driver, 5).until(
        #         EC.element_to_be_clickable((By.XPATH, "//input[@value='Continue shopping']"))
        #     )
        #     print(" Bot check screen detected. Clicking continue...")
        #     continue_btn.click()
        #     time.sleep(2)
        # except:
        #     print("No bot check screen. Proceeding...")
    
    def set_location(self, postal_code, location_name):
        """Set the delivery location using postal code"""
        print(f"📍 Setting location to {location_name} ({postal_code})...")
        
        try:
            # Click the "Deliver to" location box
            update_loc = self.wait.until(
                EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link"))
            )
            update_loc.click()
            
            # Split postal code (e.g., "M5V 3L9" -> "M5V" and "3L9")
            parts = postal_code.split()
            if len(parts) != 2:
                raise ValueError(f"Invalid postal code format: {postal_code}")
            
            # Enter postal code parts
            postal_input1 = self.wait.until(
                EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_0"))
            )
            postal_input2 = self.wait.until(
                EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_1"))
            )
            
            postal_input1.clear()
            postal_input1.send_keys(parts[0])
            postal_input2.clear()
            postal_input2.send_keys(parts[1])
            
            # Click Apply
            apply_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span#GLUXZipUpdate .a-button-input"))
            )
            apply_btn.click()
            
            # Wait and refresh to update location
            time.sleep(3)
            self.driver.refresh()
            print(f"✅ Location set to {location_name}")
            
        except Exception as e:
            print(f"❌ Error setting location: {e}")
            raise
    
    def search_products(self, search_term):
        """Search for products using the given search term"""
        print(f"🔍 Searching for: {search_term}")
        
        try:
            search_box = self.wait.until(
                EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
            )
            search_box.clear()
            search_box.send_keys(search_term)
            search_box.send_keys(Keys.RETURN)
            
            # Wait for search results to load
            time.sleep(3)
            
        except Exception as e:
            print(f"❌ Error searching for products: {e}")
            raise
    
    def extract_product_urls_from_page(self):
        """Extract product URLs from current page"""
        try:
            product_elements = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.a-link-normal.s-no-outline'))
            )
            
            page_urls = set()
            for elem in product_elements:
                href = elem.get_attribute("href")
                if href:
                    full_url = "https://www.amazon.ca" + href if href.startswith("/") else href
                    
                    # Filter out ad URLs
                    if "/sspa/" not in full_url and not full_url.startswith("https://aax-"):
                        page_urls.add(full_url)
            
            return page_urls
            
        except Exception as e:
            print(f"⚠️ Error extracting URLs from page: {e}")
            return set()
    
    def navigate_to_next_page(self, current_page):
        """Navigate to the next page of search results"""
        try:
            # Try different selectors for the next button
            next_selectors = [
                "a.s-pagination-next",
                "a[aria-label='Next page']", 
                "a[aria-label='Go to next page']",
                ".s-pagination-next",
                "a.s-pagination-item.s-pagination-next.s-pagination-button",
                "a.s-pagination-item.s-pagination-next",
                "span.s-pagination-item.s-pagination-next a"
            ]
            
            next_button = None
            next_url = None
            
            # First try to find a clickable next button
            for selector in next_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            # Check if it's not disabled
                            classes = elem.get_attribute("class") or ""
                            if "s-pagination-disabled" not in classes:
                                next_button = elem
                                next_url = elem.get_attribute("href")
                                break
                    if next_button:
                        break
                except:
                    continue
            
            # Alternative: Look for page number links
            if not next_button:
                try:
                    page_links = self.driver.find_elements(By.CSS_SELECTOR, "a.s-pagination-item.s-pagination-button")
                    for link in page_links:
                        if link.is_displayed() and link.get_attribute("aria-label") == str(current_page + 1):
                            next_button = link
                            next_url = link.get_attribute("href")
                            break
                except:
                    pass
            
            if next_button and next_url:
                print(f"   ➡️ Found next page button, moving to page {current_page + 1}...")
                
                # Method 1: Try JavaScript click first
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", next_button)
                    print("   ✅ Clicked next button using JavaScript")
                except Exception as js_error:
                    print(f"   ⚠️ JavaScript click failed: {js_error}")
                    
                    # Method 2: Try direct navigation
                    try:
                        print("   🔄 Trying direct URL navigation...")
                        self.driver.get(next_url)
                        print("   ✅ Navigated directly to next page")
                    except Exception as nav_error:
                        print(f"   ❌ Direct navigation failed: {nav_error}")
                        
                        # Method 3: Try ActionChains
                        try:
                            actions = ActionChains(self.driver)
                            actions.move_to_element(next_button).click().perform()
                            print("   ✅ Clicked using ActionChains")
                        except Exception as action_error:
                            print(f"   ❌ ActionChains failed: {action_error}")
                            return False
                
                # Wait for page to load
                time.sleep(4)
                
                # Wait for products to load on new page
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a.a-link-normal.s-no-outline'))
                    )
                    print(f"   ✅ Page {current_page + 1} loaded successfully")
                    return True
                except:
                    print(f"   ⚠️ Page {current_page + 1} didn't load properly, but continuing...")
                    return True
                    
            else:
                print(f"🔚 No more pages available. Ending scrape at page {current_page}")
                return False
                
        except Exception as e:
            print(f"❌ Error navigating to next page: {e}")
            return False
    
    def scrape_category(self, search_term, max_products=100):
        """Scrape products for a specific category/search term"""
        print(f"\nStarting scrape for: {search_term}")
        print(f"Target: {max_products} URLs")
        
        # Search for the category
        self.search_products(search_term)
        
        product_links = set()
        page_num = 1
        
        while len(product_links) < max_products:
            print(f" Scraping page {page_num}...")
            
            # Extract URLs from current page
            page_urls = self.extract_product_urls_from_page()
            
            if not page_urls:
                print(f"⚠️ No products found on page {page_num}. Ending scrape.")
                break
            
            # Add new URLs to our collection
            new_urls = page_urls - product_links
            product_links.update(new_urls)
            
            print(f"   Found {len(new_urls)} new products on page {page_num}")
            print(f"   Total products collected: {len(product_links)}")
            
            # Check if we have enough products
            if len(product_links) >= max_products:
                print(f" Target reached! Collected {len(product_links)} product URLs")
                break
            
            # Try to navigate to next page
            if not self.navigate_to_next_page(page_num):
                break
                
            page_num += 1
        
        # Limit to max_products if we have more
        if len(product_links) > max_products:
            product_links = set(list(product_links)[:max_products])
        
        print(f" Completed scraping for '{search_term}': {len(product_links)} URLs")
        return list(product_links)
    
    def close(self):
        """Close the browser"""
        self.driver.quit()


def main():
    """Main function to run the scraping process"""
    
    # Configuration
    locations = [
        {"name": "Toronto", "postal_code": "M5V 3L9"},
        {"name": "Vancouver", "postal_code": "V5H 2K3"}
    ]
    
    search_terms = [
        "Kids Superhero T Shirts",
        "Tapes, Adhesives, Lubricants & Chemicals",
        "Camera Accessories",
        "Home Decor",
        "Superhero Toys",
        "Kitchen Gadgets",
        "Bath Fixtures",
        "Laptop Bags, Sleeves, Covers",
        "Projectors",
        "Superhero Pet Toys"
    ]
    
    max_products_per_category = 100
    
    # Results storage - New structure: location -> pincode -> categories
    results_by_location = []
    
    # Initialize scraper
    scraper = AmazonScraper(headless=False)  # Set to True to run headless
    
    try:
        scraper.setup_amazon()
        
        # Loop through each location
        for location in locations:
            print(f"\n {'='*60}")
            print(f" PROCESSING LOCATION: {location['name']} ({location['postal_code']})")
            print(f" {'='*60}")
            
            # Set location
            scraper.set_location(location['postal_code'], location['name'])
            
            # Initialize location data structure
            location_data = {
                "location": location['name'],
                "pincode": location['postal_code'],
                "categories": {}
            }
            
            # Loop through each search term
            for search_term in search_terms:
                try:
                    # Scrape products for this category
                    urls = scraper.scrape_category(search_term, max_products_per_category)
                    
                    # Store results in the new structure
                    location_data["categories"][search_term] = {
                        "urls": urls,
                        "count": len(urls)
                    }
                    
                    print(f"📊 Added {len(urls)} URLs for '{search_term}' in {location['name']}")
                    
                except Exception as e:
                    print(f"❌ Error scraping '{search_term}' in {location['name']}: {e}")
                    # Store empty result for failed category
                    location_data["categories"][search_term] = {
                        "urls": [],
                        "count": 0,
                        "error": str(e)
                    }
                    continue
            
            # Add location data to results
            results_by_location.append(location_data)
            print(f"\n-> Completed all categories for {location['name']}")
        
        # Save all results to JSON
        output_filename = "amazon_canada_products.json"
        with open(output_filename, "w", encoding='utf-8') as f:
            json.dump(results_by_location, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n {'='*60}")
        print(f" SCRAPING COMPLETED!")
        print(f" {'='*60}")
        print(f"------------ Total categories scraped: {len(search_terms)}")
        print(f"------------ Total locations: {len(locations)}")
        
        # Calculate totals
        total_urls = 0
        for location_data in results_by_location:
            location_urls = sum(cat_data.get('count', 0) for cat_data in location_data['categories'].values())
            total_urls += location_urls
            print(f"   📍 {location_data['location']} ({location_data['pincode']}): {location_urls} URLs across {len(location_data['categories'])} categories")
        
        print(f"📊 Total URLs collected: {total_urls}")
        print(f"💾 Results saved to: {output_filename}")
        
        # Print detailed breakdown
        print(f"\n DETAILED BREAKDOWN:")
        for location_data in results_by_location:
            print(f"\n {location_data['location']} ({location_data['pincode']}):")
            for category, cat_data in location_data['categories'].items():
                status = "✅" if cat_data['count'] > 0 else "❌"
                error_info = f" (Error: {cat_data.get('error', 'Unknown')})" if 'error' in cat_data else ""
                print(f"   {status} {category}: {cat_data['count']} URLs{error_info}")
        
    except Exception as e:
        print(f"❌ Critical error in main process: {e}")
        # Save partial results
        if 'results_by_location' in locals() and results_by_location:
            with open("amazon_scraping_results_partial.json", "w", encoding='utf-8') as f:
                json.dump(results_by_location, f, indent=2, ensure_ascii=False)
            print(f"--------------- Saved partial results to: amazon_scraping_results_partial.json")
    
    finally:
        scraper.close()


if __name__ == "__main__":
    main()