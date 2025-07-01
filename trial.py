import json
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


def scrape_amazon_product(url):
    # --- Setup Headless Chrome ---
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(options=options)

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

    # --- About This Item ---
    product["about_this_item"] = [
        li.get_text(strip=True)
        for li in soup.select("#feature-bullets ul li")
        if li.get_text(strip=True)
    ]

    # --- Specs Table ---
    specs = {}
    for section in ["#productDetails_techSpec_section_1", "#productDetails_detailBullets_sections1"]:
        for row in soup.select(f"{section} tr"):
            key = safe_text(row.select_one("th"))
            value = safe_text(row.select_one("td"))
            if key and value:
                specs[key] = value
    product["specs"] = specs

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

    # --- Images ---
    product["images"] = []
    for img in soup.select("#altImages img"):
        src = img.get("src")
        if src:
            product["images"].append(src)

    driver.quit()
    return product


# --- Example Usage ---
if __name__ == "__main__":
    url = "https://www.amazon.in/boAt-Nirvana-Technology-Detection-Bluetooth/dp/B0BW8TXJJ2"
    data = scrape_amazon_product(url)
    print(json.dumps(data, indent=2, ensure_ascii=False))