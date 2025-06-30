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

# Setup Chrome
options = Options()
# Comment this out to see the browser
# options.add_argument("--headless")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)

# Step 1: Go to Amazon homepage
driver.get("https://www.amazon.ca/")

try:
    # Step 1.5: Handle "Continue Shopping" screen (bot check)
    try:
        continue_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@value='Continue shopping']"))
        )
        print("🛡️ Bot check screen detected. Clicking continue...")
        continue_btn.click()
        time.sleep(2)
    except:
        print("✅ No bot check screen. Proceeding...")

    # Step 2: Click the "Deliver to" location box
    update_loc = wait.until(EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link")))
    update_loc.click()

    # Step 3: Enter postal code (M5V 3L9)
    postal_input1 = wait.until(EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_0")))
    postal_input2 = wait.until(EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_1")))

    postal_input1.clear()
    postal_input1.send_keys("M5V")
    postal_input2.clear()
    postal_input2.send_keys("3L9")

    # Step 4: Click Apply
    apply_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "span#GLUXZipUpdate .a-button-input")))
    apply_btn.click()

    # Wait and refresh to update location
    time.sleep(3)
    driver.refresh()

    # Step 5: Enter search term
    search_box = wait.until(EC.presence_of_element_located((By.ID, "twotabsearchtextbox")))
    search_box.clear()
    search_box.send_keys("Kids Superhero T Shirts")
    search_box.send_keys(Keys.RETURN)

    # Step 6: Extract product URLs with pagination
    product_links = set()
    page_num = 1
    max_products = 100
    
    print(f"🔍 Starting to scrape products (target: {max_products} URLs)...")

    while len(product_links) < max_products:
        print(f"📄 Scraping page {page_num}...")
        
        # Wait for products to load
        try:
            product_elements = wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, 'a.a-link-normal.s-no-outline')
            ))
        except:
            print(f"⚠️ No products found on page {page_num}. Ending scrape.")
            break

        # Extract URLs from current page
        page_urls = set()
        for elem in product_elements:
            href = elem.get_attribute("href")
            if href:
                full_url = "https://www.amazon.ca" + href if href.startswith("/") else href

                # Filter out ad URLs
                if "/sspa/" not in full_url and not full_url.startswith("https://aax-"):
                    page_urls.add(full_url)

        # Add new URLs to our collection
        new_urls = page_urls - product_links
        product_links.update(new_urls)
        
        print(f"   Found {len(new_urls)} new products on page {page_num}")
        print(f"   Total products collected: {len(product_links)}")

        # Check if we have enough products
        if len(product_links) >= max_products:
            print(f"🎯 Target reached! Collected {len(product_links)} product URLs")
            break

        # Look for "Next" button
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
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
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
                    page_links = driver.find_elements(By.CSS_SELECTOR, "a.s-pagination-item.s-pagination-button")
                    for link in page_links:
                        if link.is_displayed() and link.get_attribute("aria-label") == str(page_num + 1):
                            next_button = link
                            next_url = link.get_attribute("href")
                            break
                except:
                    pass
            
            if next_button and next_url:
                print(f"   ➡️ Found next page button, moving to page {page_num + 1}...")
                
                # Method 1: Try JavaScript click first
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", next_button)
                    print("   ✅ Clicked next button using JavaScript")
                except Exception as js_error:
                    print(f"   ⚠️ JavaScript click failed: {js_error}")
                    
                    # Method 2: Try direct navigation
                    try:
                        print("   🔄 Trying direct URL navigation...")
                        driver.get(next_url)
                        print("   ✅ Navigated directly to next page")
                    except Exception as nav_error:
                        print(f"   ❌ Direct navigation failed: {nav_error}")
                        
                        # Method 3: Try ActionChains
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            actions = ActionChains(driver)
                            actions.move_to_element(next_button).click().perform()
                            print("   ✅ Clicked using ActionChains")
                        except Exception as action_error:
                            print(f"   ❌ ActionChains failed: {action_error}")
                            break
                
                # Wait for page to load
                time.sleep(4)
                page_num += 1
                
                # Wait for products to load on new page
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a.a-link-normal.s-no-outline'))
                    )
                    print(f"   ✅ Page {page_num} loaded successfully")
                except:
                    print(f"   ⚠️ Page {page_num} didn't load properly, but continuing...")
                    
            else:
                print(f"🔚 No more pages available. Ending scrape at page {page_num}")
                break
                
        except Exception as e:
            print(f"❌ Error finding next button: {e}")
            print(f"🔚 Ending scrape at page {page_num}")
            break

    # Limit to max_products if we have more
    if len(product_links) > max_products:
        product_links = set(list(product_links)[:max_products])

    # Save to JSON
    product_list = list(product_links)
    with open("product_urls.json", "w") as f:
        json.dump(product_list, f, indent=2)

    print(f"\n✅ Done! Extracted {len(product_list)} product URLs and saved to product_urls.json")
    print(f"📊 Scraped {page_num} pages total")

except Exception as e:
    print("❌ Error occurred:", e)
    # Save whatever we have so far
    if 'product_links' in locals() and product_links:
        product_list = list(product_links)
        with open("product_urls_partial.json", "w") as f:
            json.dump(product_list, f, indent=2)
        print(f"💾 Saved {len(product_list)} URLs to product_urls_partial.json")

# Optional: close browser
driver.quit()