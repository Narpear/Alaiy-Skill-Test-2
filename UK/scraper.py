import json
import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def clean_text(text):
    """Clean text by removing extra spaces, newlines, normalizing whitespace, and removing Unicode control characters"""
    if not text:
        return text
    
    # Remove Right-to-Left Override and other common problematic Unicode characters
    text = text.replace('\u200F', '')  # Right-to-Left Override
    text = text.replace('\u200E', '')  # Left-to-Right Mark
    text = text.replace('\u202D', '')  # Left-to-Right Override
    text = text.replace('\u202E', '')  # Right-to-Left Override
    text = text.replace('\uFEFF', '')  # Byte Order Mark (BOM)
    
    # Remove newlines and normalize whitespace
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Replace multiple spaces with single space and strip
    import re
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def try_selectors(soup, selectors, attr=None, regex=None, default=None):
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            if attr:
                val = el.get(attr)
            else:
                val = el.get_text(strip=True)
            if val:
                val = clean_text(val)
                if regex:
                    m = re.search(regex, val)
                    if m:
                        return m.group(1)
                else:
                    return val
    return default


def try_rating(soup):
    selectors = [
        "span[data-asin-rating]",
        "span.a-icon-alt",
        "#acrPopover",
        ".reviewCountTextLinkedHistogram",
        "#averageCustomerReviews .a-icon-alt",
        "#averageCustomerReviews .a-size-base.a-color-base"
    ]
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            # Try aria-label first
            aria = el.get('aria-label')
            if aria:
                return clean_text(aria)
            txt = el.get_text(strip=True)
            if txt:
                return clean_text(txt)
    return None


def try_price(soup, debug=False):
    """Enhanced price extraction with comprehensive selectors for all Amazon sites"""
    
    # Comprehensive list of price selectors for different Amazon layouts
    selectors = [
        # Main price selectors (most common)
        ".a-price .a-offscreen",
        ".a-price-whole",
        ".a-price .a-price-whole",
        
        # Core price display (newer Amazon layouts)
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-price-whole",
        "#corePrice_feature_div .a-offscreen",
        "#corePrice_desktop .a-offscreen",
        
        # Apex price display
        ".apexPriceToPay .a-offscreen",
        ".apexPriceToPay .a-price-whole",
        "#apex_desktop .a-price .a-offscreen",
        
        # Legacy price blocks
        "#priceblock_ourprice",
        "#priceblock_dealprice", 
        "#priceblock_saleprice",
        "#priceblock_vatprice",
        "#priceblock_businessprice",
        "#priceblock_pospromoprice",
        "#price_inside_buybox",
        
        # Buybox pricing
        "#desktop_buyBox .a-price .a-offscreen",
        "#desktop_buyBox .a-price-whole",
        "#buybox .a-price .a-offscreen",
        "#rightCol .a-price .a-offscreen",
        
        # Alternative price displays
        ".a-price-current .a-offscreen",
        ".a-price-current",
        ".price .a-offscreen",
        
        # Mobile/responsive selectors
        "#mobile-price .a-offscreen",
        ".a-size-medium.a-color-price",
        
        # Kindle/Digital content
        "#kindle-price .a-offscreen",
        "#ebook-price-value",
        
        # Business/bulk pricing
        "#businessPrice .a-offscreen",
        "#quantityPrice .a-offscreen",
        
        # International/localized
        ".a-price-symbol",
        "[data-a-color='price'] .a-offscreen",
        
        # Fallback selectors
        "*[id*='price'] .a-offscreen",
        "*[class*='price'] .a-offscreen",
        ".a-color-price",
        
        # Last resort - any element with price-like text
        "[aria-label*='price']",
        "[title*='price']"
    ]
    
    found_prices = []  # For debugging
    
    for selector in selectors:
        try:
            elements = soup.select(selector)
            for el in elements:
                if el:
                    # Try different ways to get the price text
                    price_text = None
                    
                    # Method 1: Direct text content
                    txt = el.get_text(strip=True)
                    if txt:
                        price_text = clean_text(txt)
                    
                    # Method 2: aria-label attribute
                    if not price_text:
                        aria_label = el.get('aria-label')
                        if aria_label:
                            price_text = clean_text(aria_label)
                    
                    # Method 3: title attribute
                    if not price_text:
                        title = el.get('title')
                        if title:
                            price_text = clean_text(title)
                    
                    if price_text:
                        # Validate that this looks like a price
                        if is_valid_price(price_text):
                            if debug:
                                found_prices.append(f"Selector: {selector} -> Price: {price_text}")
                            return price_text
                        elif debug:
                            found_prices.append(f"Selector: {selector} -> Invalid: {price_text}")
        
        except Exception as e:
            if debug:
                found_prices.append(f"Selector: {selector} -> Error: {str(e)}")
            continue
    
    # If no price found with standard selectors, try regex patterns on the page
    page_text = soup.get_text()
    price_patterns = [
        r'£\s*(\d+(?:\.\d{2})?)',  # UK pounds
        r'\$\s*(\d+(?:\.\d{2})?)',  # US dollars
        r'€\s*(\d+(?:,\d{2})?)',   # Euros
        r'₹\s*(\d+(?:\.\d{2})?)',  # Indian rupees
        r'Price:\s*[£\$€₹]\s*(\d+(?:[\.\,]\d{2})?)',
        r'Our Price:\s*[£\$€₹]\s*(\d+(?:[\.\,]\d{2})?)',
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, page_text)
        if match:
            price_text = match.group(0)
            if debug:
                found_prices.append(f"Regex pattern: {pattern} -> Price: {price_text}")
            return clean_text(price_text)
    
    if debug:
        print("DEBUG - All price extraction attempts:")
        for attempt in found_prices:
            print(f"  {attempt}")
    
    return None


def is_valid_price(text):
    """Check if text looks like a valid price"""
    if not text or len(text) < 2:
        return False
    
    # Common currency symbols and price patterns
    price_indicators = ['£', '$', '€', '₹', 'USD', 'GBP', 'EUR', 'INR']
    has_currency = any(indicator in text for indicator in price_indicators)
    
    # Look for numbers that could be prices
    has_numbers = re.search(r'\d+(?:[\.\,]\d{1,2})?', text)
    
    # Exclude obviously non-price text
    exclusions = ['rating', 'review', 'star', 'delivery', 'shipping', 'tax', 'vat', 'including']
    has_exclusions = any(exclusion in text.lower() for exclusion in exclusions)
    
    return has_currency and has_numbers and not has_exclusions


def try_deal(soup):
    selectors = [
        ".dealBadge",
        ".savingsPercentage",
        ".a-size-medium.a-color-price.savingPriceOverride.aok-align-center.reinventPriceSavingsPercentageMargin.savingsPercentage",
        ".a-size-medium.a-color-success",
        ".a-size-base.a-color-price"
    ]
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return clean_text(txt)
    return None


def try_main_image(soup):
    selectors = [
        ("#landingImage", "data-old-hires"),
        ("#imgTagWrapperId img", "data-old-hires"),
        ("#imgTagWrapperId img", "src"),
        ("#imageBlock img[data-old-hires]", "data-old-hires"),
        ("#main-image-container img", "src"),
        ("#main-image", "src"),
        ("#imgBlkFront", "src"),
        ("#ebooksImgBlkFront", "src"),
        ("#img-canvas img", "src"),
        ("#ivLargeImage img", "src"),
        ("#imgTagWrapperId img", "data-a-dynamic-image")
    ]
    for selector, attr in selectors:
        el = soup.select_one(selector)
        if el:
            val = el.get(attr)
            if val:
                # If data-a-dynamic-image, extract first URL
                if attr == "data-a-dynamic-image":
                    try:
                        import ast
                        img_dict = ast.literal_eval(val)
                        if isinstance(img_dict, dict):
                            return list(img_dict.keys())[0]
                    except Exception:
                        continue
                else:
                    return val
    return None


def try_brand(soup):
    selectors = [
        "#bylineInfo",
        "#brand",
        ".po-brand .a-span9",
        ".a-row .a-link-normal",
        ".a-row .a-size-base"
    ]
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            txt = el.get_text(strip=True)
            if txt and not txt.lower().startswith("visit the"):
                return clean_text(txt)
    # Try meta tag
    meta = soup.find("meta", {"name": "brand"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])
    return None


def try_title(soup):
    selectors = [
        "#productTitle",
        "#titleSection .a-size-large",
        "#ebooksProductTitle",
        "#item_title",
        ".product-title-word-break",
        "#title"
    ]
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return clean_text(txt)
    return None


def try_total_reviews(soup):
    selectors = [
        "#acrCustomerReviewText",
        "#acrCustomerWriteReviewText",
        "#reviewSummary .a-size-base",
        ".reviewCountTextLinkedHistogram",
        "#averageCustomerReviews .a-size-base"
    ]
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return clean_text(txt)
    return None


def scrape_amazon_product(url):
    # --- Setup Headless Chrome ---
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    driver.get(url)
    time.sleep(3)  # Allow JS to load

    soup = BeautifulSoup(driver.page_source, "html.parser")

    product = {}
    # ASIN
    try:
        product["asin"] = url.split("/dp/")[1].split("/")[0]
    except Exception:
        product["asin"] = None
    product["url"] = url
    # Title
    product["title"] = try_title(soup)
    # Brand
    product["brand"] = try_brand(soup)
    # Rating
    product["rating"] = try_rating(soup)
    # Total Reviews
    product["total_reviews"] = try_total_reviews(soup)
    # Price
    product["price"] = try_price(soup)
    # Deal
    product["deal"] = try_deal(soup)
    # Main Image
    product["main_image"] = try_main_image(soup)

    # --- About This Item ---
    about_items = []
    about_selectors = [
        "#feature-bullets ul li span.a-list-item",
        "#feature-bullets ul li",
        "#feature-bullets .a-list-item",
        "#productOverview_feature_div .a-list-item",
        "#productOverview_feature_div ul li",
        "#productOverview_feature_div .a-row",
        "#aplus_feature_div ul li",
        "#featurebullets_feature_div ul li",
        ".a-unordered-list.a-vertical li",
        "[data-feature-name='featurebullets'] ul li",
        ".feature .a-list-item"
    ]

    for selector in about_selectors:
        elements = soup.select(selector)
        if elements:
            about_items = []
            for li in elements:
                # Skip if it's a heading or contains only symbols
                text = clean_text(li.get_text(strip=True))
                if text and len(text) > 3 and not text.startswith('•') and ':' not in text[:10]:
                    # Remove bullet points and clean up
                    text = text.replace('•', '').strip()
                    if text:
                        about_items.append(text)
            if about_items:
                break

    # Fallback: try to find bullet points in any div with "feature" in the id
    if not about_items:
        feature_divs = soup.find_all('div', id=re.compile(r'.*feature.*', re.I))
        for div in feature_divs:
            bullets = div.select('ul li, .a-list-item')
            if bullets:
                for bullet in bullets:
                    text = clean_text(bullet.get_text(strip=True))
                    if text and len(text) > 10:
                        about_items.append(text.replace('•', '').strip())
                if about_items:
                    break

    product["about_this_item"] = about_items

    # --- Buy Box Info (with backups) ---
    buybox = {}
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Primary buybox area detection
    buybox_area = soup.select_one("#desktop_buyBox") or soup.select_one("#rightCol") or soup.select_one("#buybox") or soup.select_one("#apex_desktop") or soup.select_one("#newAccordionCaption_feature_div")

    if buybox_area:
        all_text = buybox_area.get_text(separator='|').split('|')
        for i, text in enumerate(all_text):
            text = clean_text(text)
            if text.lower() == "ships from" and i + 1 < len(all_text):
                next_text = clean_text(all_text[i + 1])
                if next_text and next_text.lower() not in ["ships from", "sold by", "payment"]:
                    buybox["ships_from"] = next_text
            elif text.lower() == "sold by" and i + 1 < len(all_text):
                next_text = clean_text(all_text[i + 1])
                if next_text and next_text.lower() not in ["ships from", "sold by", "payment"]:
                    buybox["sold_by"] = next_text

    # Backup 1: Enhanced span detection
    if not buybox.get("ships_from") or not buybox.get("sold_by"):
        buybox_spans = soup.select("#desktop_buyBox span, #rightCol span, #buybox span, #apex_desktop span, #newAccordionCaption_feature_div span")
        prev_text = ""
        for span in buybox_spans:
            current_text = clean_text(span.get_text(strip=True)) if span else None
            if current_text:
                if prev_text.lower() == "ships from" and current_text.lower() not in ["ships from", "sold by", "payment"]:
                    if len(current_text) > 2:
                        buybox["ships_from"] = current_text
                elif prev_text.lower() == "sold by" and current_text.lower() not in ["ships from", "sold by", "payment"]:
                    if len(current_text) > 2:
                        buybox["sold_by"] = current_text
                prev_text = current_text

    # Backup 2: Enhanced seller links
    if not buybox.get("sold_by"):
        seller_link_selectors = [
            "#desktop_buyBox a[href*='/seller/']",
            "#rightCol a[href*='/seller/']",
            "#desktop_buyBox a[href*='/s?merchant=']",
            "#rightCol a[href*='/s?merchant=']",
            "#buybox a[href*='/seller/']",
            "#buybox a[href*='/s?merchant=']",
            "#apex_desktop a[href*='/seller/']",
            "#newAccordionCaption_feature_div a[href*='/seller/']",
            "a[href*='/seller/']",
            "a[href*='/s?merchant=']"
        ]
        for selector in seller_link_selectors:
            seller_link = soup.select_one(selector)
            if seller_link:
                seller_name = clean_text(seller_link.get_text(strip=True))
                if seller_name and len(seller_name) > 2:
                    buybox["sold_by"] = seller_name
                    break

    # Backup 3: Enhanced merchant info detection
    if not buybox.get("sold_by"):
        merchant_containers = soup.select("#merchant-info, [data-csa-c-type='element'], #tabular-buybox, #buybox-tabular-content")
        for container in merchant_containers:
            links = container.select("a")
            for link in links:
                href = link.get("href", "")
                text = clean_text(link.get_text(strip=True))
                if text and ("/seller/" in href or "/s?merchant=" in href):
                    buybox["sold_by"] = text
                    break
            if buybox.get("sold_by"):
                break

    # Backup 4: Text pattern matching for ships from
    if not buybox.get("ships_from"):
        ships_patterns = [
            r"ships from\s*:?\s*([^,\n\|]+)",
            r"dispatched from\s*:?\s*([^,\n\|]+)",
            r"fulfilled by\s*:?\s*([^,\n\|]+)"
        ]
        page_text = soup.get_text()
        for pattern in ships_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                ships_from = clean_text(match.group(1))
                if ships_from and len(ships_from) > 2:
                    buybox["ships_from"] = ships_from
                    break

    # Backup 5: Text pattern matching for sold by
    if not buybox.get("sold_by"):
        sold_patterns = [
            r"sold by\s*:?\s*([^,\n\|]+)",
            r"seller\s*:?\s*([^,\n\|]+)",
            r"merchant\s*:?\s*([^,\n\|]+)"
        ]
        page_text = soup.get_text()
        for pattern in sold_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                sold_by = clean_text(match.group(1))
                if sold_by and len(sold_by) > 2 and sold_by.lower() not in ["amazon", "prime"]:
                    buybox["sold_by"] = sold_by
                    break

    # Backup 6: Enhanced shipping/delivery info
    delivery_selectors = [
        "#mir-layout-DELIVERY_BLOCK",
        "#desktop_buyBox .a-color-success",
        "#rightCol .a-color-success",
        "#buybox .a-color-success",
        "#deliveryMessageMirId",
        "#apex_desktop .a-color-success",
        "[data-csa-c-type='element'] .a-color-success",
        ".delivery-message",
        "#delivery-block-container",
        "[id*='delivery']",
        "[class*='delivery']"
    ]
    for selector in delivery_selectors:
        delivery_element = soup.select_one(selector)
        if delivery_element:
            delivery_text = clean_text(delivery_element.get_text(strip=True))
            if delivery_text and ("delivery" in delivery_text.lower() or "free" in delivery_text.lower() or "shipping" in delivery_text.lower()):
                buybox["shipping_info"] = delivery_text
                break

    # Backup 7: Enhanced Prime eligibility detection
    prime_indicators = soup.select("#desktop_buyBox i, #rightCol i, #desktop_buyBox .a-icon, #rightCol .a-icon, #buybox i, #buybox .a-icon, #apex_desktop i, #apex_desktop .a-icon")
    for icon in prime_indicators:
        aria_label = icon.get("aria-label", "")
        class_name = " ".join(icon.get("class", []))
        if "prime" in aria_label.lower() or "prime" in class_name.lower():
            buybox["prime_eligible"] = True
            break

    # Backup 8: Prime detection via text search
    if not buybox.get("prime_eligible"):
        prime_text_indicators = soup.find_all(text=re.compile(r'prime', re.IGNORECASE))
        for text in prime_text_indicators:
            if text and "prime" in text.lower():
                parent = text.parent
                if parent and any(keyword in parent.get_text().lower() for keyword in ["eligible", "free", "delivery", "shipping"]):
                    buybox["prime_eligible"] = True
                    break

    # Backup 9: Enhanced fulfillment detection
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

    # Backup 10: Availability status
    availability_selectors = [
        "#availability span",
        "#desktop_buyBox #availability",
        "#rightCol #availability",
        ".a-color-success",
        ".a-color-state",
        "[data-csa-c-type='element'] span"
    ]
    for selector in availability_selectors:
        availability_element = soup.select_one(selector)
        if availability_element:
            availability_text = clean_text(availability_element.get_text(strip=True))
            if availability_text and any(keyword in availability_text.lower() for keyword in ["in stock", "available", "out of stock", "temporarily unavailable"]):
                buybox["availability"] = availability_text
                break

    # Backup 11: Quantity limits
    quantity_selectors = [
        "#desktop_buyBox select[name='quantity']",
        "#rightCol select[name='quantity']",
        "#quantity option:last-child"
    ]
    for selector in quantity_selectors:
        quantity_element = soup.select_one(selector)
        if quantity_element:
            if quantity_element.name == "select":
                options = quantity_element.select("option")
                if options:
                    max_qty = clean_text(options[-1].get_text(strip=True))
                    if max_qty.isdigit():
                        buybox["max_quantity"] = int(max_qty)
            break

    product["buybox"] = buybox

    # --- Child SKU Links (Color/Model Variants) ---
    product["child_skus"] = []
    try:
        dimension_items = driver.find_elements(By.CSS_SELECTOR, "li[data-asin][data-csa-c-item-id]")
        for item in dimension_items:
            try:
                asin = item.get_attribute("data-asin")
                if asin and asin != product["asin"]:
                    variant_url = f"https://www.amazon.in/dp/{asin}"
                    variant_info = {"url": variant_url, "asin": asin}
                    product["child_skus"].append(variant_info)
            except Exception:
                continue
        # Fallback: links in variation sections
        if not product["child_skus"]:
            variation_links = driver.find_elements(By.CSS_SELECTOR, "#variation_color_name a, #variation_style_name a, [data-dp-url]")
            for link in variation_links:
                try:
                    href = link.get_attribute("href") or link.get_attribute("data-dp-url")
                    if href and "/dp/" in href:
                        asin = href.split("/dp/")[1].split("/")[0]
                        if asin != product["asin"]:
                            variant_name = link.get_attribute("title") or link.get_attribute("aria-label") or ""
                            variant_info = {"url": href, "variant_name": variant_name or f"Variant {asin}", "asin": asin}
                            if not any(sku["asin"] == asin for sku in product["child_skus"]):
                                product["child_skus"].append(variant_info)
                except Exception:
                    continue
    except Exception as e:
        print(f"Error extracting child SKUs: {e}")

    # --- Specs Table ---
    specs = {}
    soup = BeautifulSoup(driver.page_source, "html.parser")
    for section in ["#productDetails_techSpec_section_1", "#productDetails_detailBullets_sections1", "#prodDetails"]:
        for row in soup.select(f"{section} tr"):
            key = try_selectors(row, ["th", ".a-text-bold"])
            value = try_selectors(row, ["td:not(.a-text-bold)", "td"])
            if key and value:
                specs[key] = value
    product["specs"] = specs

    # --- Product Details Table ---
    product["product_details"] = {}
    try:
        details_selectors = [
            "#productDetails_detailBullets_sections1",
            "#detailBullets_feature_div",
            "#productDetails_expanderSummary_div",
            "#prodDetails"
        ]
        for selector in details_selectors:
            details_section = soup.select_one(selector)
            if details_section:
                detail_items = details_section.select("li")
                for item in detail_items:
                    item_text = clean_text(item.get_text(strip=True))
                    if item_text and ":" in item_text:
                        parts = item_text.split(":", 1)
                        if len(parts) == 2:
                            key = clean_text(parts[0])
                            value = clean_text(parts[1])
                            if key and value:
                                product["product_details"][key] = value
                    else:
                        spans = item.select("span")
                        if len(spans) >= 2:
                            key = clean_text(spans[0].get_text(strip=True))
                            value = clean_text(spans[1].get_text(strip=True))
                            if key and value and key != value:
                                product["product_details"][key] = value
                for row in details_section.select("tr"):
                    key_elem = row.select_one("th, .a-text-bold")
                    value_elem = row.select_one("td:not(.a-text-bold), td")
                    if key_elem and value_elem:
                        key = clean_text(key_elem.get_text(strip=True)).replace(":", "")
                        value = clean_text(value_elem.get_text(strip=True))
                        if key and value:
                            product["product_details"][key] = value
                break
    except Exception as e:
        print(f"Error extracting product details: {e}")

    # --- From the Manufacturer ---
    product["from_manufacturer"] = {}
    aplus_selectors = [
        "#aplus_feature_div",
        "[data-aplus-module]",
        "#aplusBrandStory_feature_div",
        "#aplus3p_feature_div"
    ]
    for selector in aplus_selectors:
        aplus_section = soup.select_one(selector)
        if aplus_section:
            headings = aplus_section.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
            for heading in headings:
                heading_text = clean_text(heading.get_text(strip=True))
                if heading_text:
                    content = []
                    next_elem = heading.find_next_sibling()
                    while next_elem and next_elem.name not in ['h1', 'h2', 'h3', 'h4', 'h5']:
                        if next_elem.name in ['p', 'div', 'span']:
                            text = clean_text(next_elem.get_text(strip=True))
                            if text and len(text) > 10:
                                content.append(text)
                        next_elem = next_elem.find_next_sibling()
                    if content:
                        product["from_manufacturer"][heading_text] = content
            break

    driver.quit()
    return product


# --- Example Usage ---
if __name__ == "__main__":
    url = "https://www.amazon.co.uk/Marvel-Spiderman-Superhero-Childrens-Merchandise/dp/B0DB64ZW2H/ref=sr_1_40?dib=eyJ2IjoiMSJ9.2_nOA3dOc-ID0uz-wRIvD2tWvc3gNdmdgAo0odOvmkYanGP9elvmCEUuJhyDkSdJIsmmBMD38SsSb7_XE4VpYLrY7U5XTHCmzzliNSVr4vuJthiWAR5sCpfecoz1Wr6trkM29iHuQxwzHHFcVcQ2IfBJ4FmjAveWs8JXfJXg3krKESezc1xoVTIKTHbhWzVkxqlQOxbWEnhpY8E8KAgeJahX_w-RKYs6hI2Mnmp2xDJ-9boogYO107666odXX0RsSuSz9mMMfepN75CwKeayCfdSkuFhkmUKtR09Fi9z6Uk.MwS2VnNTlFxdd9QS0CtR3oVVW08dwMaIhLhOqlP-FBU&dib_tag=se&keywords=Kids+Superhero+T+Shirts&qid=1751304091&sr=8-40"
    data = scrape_amazon_product(url)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    # Save to JSON file
    with open('output.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)