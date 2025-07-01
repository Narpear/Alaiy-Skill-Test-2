import json
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def scrape_amazon_product(url):
    # --- Setup Headless Chrome ---
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    driver.get(url)
    time.sleep(4)  # Allow JS to load

    soup = BeautifulSoup(driver.page_source, "html.parser")

    def safe_text(selector):
        return selector.get_text(strip=True) if selector else None

    product = {}
    product["asin"] = url.split("/dp/")[1].split("/")[0]
    product["url"] = url
    product["title"] = safe_text(soup.select_one("#productTitle"))
    product["brand"] = safe_text(soup.select_one("#bylineInfo"))
    product["rating"] = safe_text(soup.select_one("span[data-asin-rating]")) or safe_text(soup.select_one("span.a-icon-alt"))
    product["total_reviews"] = safe_text(soup.select_one("#acrCustomerReviewText"))
    product["price"] = safe_text(soup.select_one(".a-price .a-offscreen"))
    product["deal"] = safe_text(soup.select_one(".dealBadge")) or safe_text(soup.select_one(".savingsPercentage"))

    # --- Main Product Image ---
    try:
        # Look for the main product image
        main_image_selectors = [
            "#landingImage",
            "#imgTagWrapperId img",
            "#imageBlock img[data-old-hires]",
            "#main-image-container img"
        ]
        
        main_image_url = None
        for selector in main_image_selectors:
            img_element = soup.select_one(selector)
            if img_element:
                # Try to get high-res version first
                main_image_url = (img_element.get("data-old-hires") or 
                                img_element.get("data-a-dynamic-image") or 
                                img_element.get("src"))
                if main_image_url:
                    break
        
        product["main_image"] = main_image_url
    except Exception as e:
        print(f"Error extracting main image: {e}")
        product["main_image"] = None

    # --- About This Item ---
    product["about_this_item"] = [
        li.get_text(strip=True)
        for li in soup.select("#feature-bullets ul li")
        if li.get_text(strip=True)
    ]

    # --- Buy Box Info (Updated for Amazon India) ---
    buybox = {}
    
    # Debug: Let's add some wait time for buybox to load
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(2)
    
    # Refresh soup after scroll
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Method 1: Look for specific buybox patterns used by Amazon India
    # Pattern: <span>Ships from</span> followed by actual value
    buybox_area = soup.select_one("#desktop_buyBox") or soup.select_one("#rightCol")
    
    if buybox_area:
        # Find all text nodes in buybox area
        all_text = buybox_area.get_text(separator='|').split('|')
        
        for i, text in enumerate(all_text):
            text = text.strip()
            if text.lower() == "ships from" and i + 1 < len(all_text):
                next_text = all_text[i + 1].strip()
                if next_text and next_text.lower() not in ["ships from", "sold by", "payment"]:
                    buybox["ships_from"] = next_text
            elif text.lower() == "sold by" and i + 1 < len(all_text):
                next_text = all_text[i + 1].strip()
                if next_text and next_text.lower() not in ["ships from", "sold by", "payment"]:
                    buybox["sold_by"] = next_text
    
    # Method 2: Alternative approach using table-like structure
    if not buybox.get("ships_from") or not buybox.get("sold_by"):
        # Look for spans that contain the actual values (not labels)
        buybox_spans = soup.select("#desktop_buyBox span, #rightCol span")
        
        prev_text = ""
        for span in buybox_spans:
            current_text = safe_text(span)
            if current_text:
                if prev_text.lower() == "ships from" and current_text.lower() not in ["ships from", "sold by", "payment"]:
                    if len(current_text) > 2:  # Avoid single characters
                        buybox["ships_from"] = current_text
                elif prev_text.lower() == "sold by" and current_text.lower() not in ["ships from", "sold by", "payment"]:
                    if len(current_text) > 2:  # Avoid single characters
                        buybox["sold_by"] = current_text
                prev_text = current_text
    
    # Method 3: Look for seller links specifically
    if not buybox.get("sold_by"):
        seller_link_selectors = [
            "#desktop_buyBox a[href*='/seller/']",
            "#rightCol a[href*='/seller/']",
            "#desktop_buyBox a[href*='/s?merchant=']",
            "#rightCol a[href*='/s?merchant=']"
        ]
        
        for selector in seller_link_selectors:
            seller_link = soup.select_one(selector)
            if seller_link:
                seller_name = safe_text(seller_link)
                if seller_name and len(seller_name) > 2:
                    buybox["sold_by"] = seller_name
                    break
    
    # Method 4: Try to find merchant info in structured data
    if not buybox.get("sold_by"):
        merchant_containers = soup.select("#merchant-info, [data-csa-c-type='element']")
        for container in merchant_containers:
            links = container.select("a")
            for link in links:
                href = link.get("href", "")
                text = safe_text(link)
                if text and ("/seller/" in href or "/s?merchant=" in href):
                    buybox["sold_by"] = text
                    break
            if buybox.get("sold_by"):
                break
    
    # Extract shipping/delivery information
    delivery_selectors = [
        "#mir-layout-DELIVERY_BLOCK",
        "#desktop_buyBox .a-color-success",
        "#rightCol .a-color-success"
    ]
    
    for selector in delivery_selectors:
        delivery_element = soup.select_one(selector)
        if delivery_element:
            delivery_text = safe_text(delivery_element)
            if delivery_text and ("delivery" in delivery_text.lower() or "free" in delivery_text.lower()):
                buybox["shipping_info"] = delivery_text
                break
    
    # Check for Prime eligibility
    prime_indicators = soup.select("#desktop_buyBox i, #rightCol i, #desktop_buyBox .a-icon, #rightCol .a-icon")
    for icon in prime_indicators:
        aria_label = icon.get("aria-label", "")
        class_name = " ".join(icon.get("class", []))
        if "prime" in aria_label.lower() or "prime" in class_name.lower():
            buybox["prime_eligible"] = True
            break
    
    # Set fulfillment info based on ships_from
    if buybox.get("ships_from"):
        if "amazon" in buybox["ships_from"].lower():
            buybox["fulfilled_by"] = "Amazon"
        else:
            buybox["fulfilled_by"] = "Third-party"
    elif buybox.get("sold_by"):
        if "amazon" in buybox["sold_by"].lower():
            buybox["fulfilled_by"] = "Amazon"
        else:
            buybox["fulfilled_by"] = "Third-party"
    
    product["buybox"] = buybox

    # --- Child SKU Links (Color/Model Variants) ---
    product["child_skus"] = []

    try:
        # Method 1: Look for dimension value list items (most common structure)
        dimension_items = driver.find_elements(By.CSS_SELECTOR, "li[data-asin][data-csa-c-item-id]")
        
        for item in dimension_items:
            try:
                asin = item.get_attribute("data-asin")
                if asin and asin != product["asin"]:  # Don't include current product                 
                    # Build URL
                    variant_url = f"https://www.amazon.in/dp/{asin}"
                    
                    variant_info = {
                        "url": variant_url,
                        "asin": asin
                    }
                    
                    product["child_skus"].append(variant_info)
                    
            except Exception as e:
                continue
        
        # Method 2: Fallback - look for any links with /dp/ in variation sections
        if not product["child_skus"]:
            variation_links = driver.find_elements(By.CSS_SELECTOR, "#variation_color_name a, #variation_style_name a, [data-dp-url]")
            
            for link in variation_links:
                try:
                    href = link.get_attribute("href") or link.get_attribute("data-dp-url")
                    if href and "/dp/" in href:
                        asin = href.split("/dp/")[1].split("/")[0]
                        if asin != product["asin"]:
                            variant_name = link.get_attribute("title") or link.get_attribute("aria-label") or ""
                            
                            variant_info = {
                                "url": href,
                                "variant_name": variant_name or f"Variant {asin}",
                                "asin": asin
                            }
                            
                            if not any(sku["asin"] == asin for sku in product["child_skus"]):
                                product["child_skus"].append(variant_info)
                                
                except Exception as e:
                    continue
                    
    except Exception as e:
        print(f"Error extracting child SKUs: {e}")

    # --- Specs Table ---
    specs = {}
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    for section in ["#productDetails_techSpec_section_1", "#productDetails_detailBullets_sections1"]:
        for row in soup.select(f"{section} tr"):
            key = safe_text(row.select_one("th"))
            value = safe_text(row.select_one("td"))
            if key and value:
                specs[key] = value
    product["specs"] = specs

        # --- From the Manufacturer ---
    product["from_manufacturer"] = {}
    
    # Look for A+ content sections
    aplus_selectors = [
        "#aplus_feature_div",
        "[data-aplus-module]",
        "#aplusBrandStory_feature_div"
    ]
    
    for selector in aplus_selectors:
        aplus_section = soup.select_one(selector)
        if aplus_section:
            # Extract headings and content
            headings = aplus_section.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
            for heading in headings:
                heading_text = safe_text(heading)
                if heading_text:
                    # Get content after heading
                    content = []
                    
                    # Look for next paragraphs or divs
                    next_elem = heading.find_next_sibling()
                    while next_elem and next_elem.name not in ['h1', 'h2', 'h3', 'h4', 'h5']:
                        if next_elem.name in ['p', 'div', 'span']:
                            text = safe_text(next_elem)
                            if text and len(text) > 10:  # Avoid short/empty content
                                content.append(text)
                        next_elem = next_elem.find_next_sibling()
                    
                    if content:
                        product["from_manufacturer"][heading_text] = content
            
            break

    driver.quit()
    return product


# --- Example Usage ---
if __name__ == "__main__":
    url = "https://www.amazon.in/boAt-Nirvana-Technology-Detection-Bluetooth/dp/B0BW8TXJJ2"
    data = scrape_amazon_product(url)
    print(json.dumps(data, indent=2, ensure_ascii=False))