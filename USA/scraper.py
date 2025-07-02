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
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def get_domain_info(url):
    """Extract domain information and set appropriate settings"""
    domain_configs = {
        'amazon.com': {'currency': '$', 'lang': 'en-US'},
        'amazon.ca': {'currency': 'CAD', 'lang': 'en-CA'},
        'amazon.co.uk': {'currency': '£', 'lang': 'en-GB'},
        'amazon.de': {'currency': '€', 'lang': 'de-DE'},
        'amazon.fr': {'currency': '€', 'lang': 'fr-FR'},
        'amazon.it': {'currency': '€', 'lang': 'it-IT'},
        'amazon.es': {'currency': '€', 'lang': 'es-ES'},
        'amazon.in': {'currency': '₹', 'lang': 'en-IN'},
        'amazon.com.au': {'currency': 'AUD', 'lang': 'en-AU'},
        'amazon.co.jp': {'currency': '¥', 'lang': 'ja-JP'},
    }
    
    for domain, config in domain_configs.items():
        if domain in url:
            return config
    
    # Default to US if domain not recognized
    return domain_configs['amazon.com']


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
        "#averageCustomerReviews .a-size-base.a-color-base",
        ".a-popover-trigger .a-icon-alt",
        "[data-hook='rating-out-of-text']"
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


def is_valid_price(text, domain_config):
    """Enhanced price validation for multiple currencies and formats"""
    if not text or len(text) < 2:
        return False
    
    # Enhanced currency symbols and price patterns for different domains
    currency_patterns = [
        r'[\$\£\€\₹\¥]',  # Currency symbols
        r'USD|CAD|GBP|EUR|INR|JPY|AUD',  # Currency codes
        r'C\$',  # Canadian dollar format
        r'CDN\$',  # Canadian dollar format
        r'\$\s*CAD',  # Dollar CAD format
        r'CA\$',  # Canadian format
    ]
    
    has_currency = any(re.search(pattern, text, re.IGNORECASE) for pattern in currency_patterns)
    
    # Look for numbers that could be prices (including comma separators)
    number_patterns = [
        r'\d+(?:[\.\,]\d{1,2})?',  # Standard decimal
        r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # Comma thousands separator
        r'\d+(?:\s\d{3})*(?:[\.\,]\d{2})?',  # Space thousands separator
    ]
    
    has_numbers = any(re.search(pattern, text) for pattern in number_patterns)
    
    # Exclude obviously non-price text
    exclusions = ['rating', 'review', 'star', 'delivery', 'shipping', 'tax', 'vat', 'including', 'save', 'off']
    has_exclusions = any(exclusion in text.lower() for exclusion in exclusions)
    
    # Additional validation for price-like content
    price_indicators = ['price', 'cost', 'total', 'amount']
    has_price_context = any(indicator in text.lower() for indicator in price_indicators)
    
    return (has_currency or has_price_context) and has_numbers and not has_exclusions


def try_price(soup, domain_config, debug=False):
    """Enhanced price extraction with support for all Amazon domains"""
    
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
        
        # Canadian specific selectors
        "[data-automation-id='list-price'] .a-offscreen",
        "[data-automation-id='sale-price'] .a-offscreen",
        ".a-price-range .a-offscreen",
        
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
                        if is_valid_price(price_text, domain_config):
                            if debug:
                                found_prices.append(f"Selector: {selector} -> Price: {price_text}")
                            return price_text
                        elif debug:
                            found_prices.append(f"Selector: {selector} -> Invalid: {price_text}")
        
        except Exception as e:
            if debug:
                found_prices.append(f"Selector: {selector} -> Error: {str(e)}")
            continue
    
    # Enhanced regex patterns for different currencies and formats
    page_text = soup.get_text()
    price_patterns = [
        # Canadian dollar patterns
        r'C\$\s*(\d+(?:\.\d{2})?)',
        r'CDN\$\s*(\d+(?:\.\d{2})?)',
        r'CA\$\s*(\d+(?:\.\d{2})?)',
        r'\$\s*(\d+(?:\.\d{2})?)\s*CAD',
        
        # Standard currency patterns
        r'£\s*(\d+(?:\.\d{2})?)',  # UK pounds
        r'\$\s*(\d+(?:\.\d{2})?)',  # US dollars
        r'€\s*(\d+(?:,\d{2})?)',   # Euros
        r'₹\s*(\d+(?:\.\d{2})?)',  # Indian rupees
        r'¥\s*(\d+)',              # Japanese yen
        
        # Context-based patterns
        r'Price:\s*[C\$£€₹¥]*\s*(\d+(?:[\.\,]\d{2})?)',
        r'Our Price:\s*[C\$£€₹¥]*\s*(\d+(?:[\.\,]\d{2})?)',
        r'List Price:\s*[C\$£€₹¥]*\s*(\d+(?:[\.\,]\d{2})?)',
        
        # Number with currency code
        r'(\d+(?:\.\d{2})?)\s*(USD|CAD|GBP|EUR|INR|JPY|AUD)',
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                price_text = f"{match.group(1)} {match.group(2)}"
            else:
                price_text = match.group(0)
            if debug:
                found_prices.append(f"Regex pattern: {pattern} -> Price: {price_text}")
            return clean_text(price_text)
    
    if debug:
        print("DEBUG - All price extraction attempts:")
        for attempt in found_prices:
            print(f"  {attempt}")
    
    return None


def try_deal(soup):
    selectors = [
        ".dealBadge",
        ".savingsPercentage",
        ".a-size-medium.a-color-price.savingPriceOverride.aok-align-center.reinventPriceSavingsPercentageMargin.savingsPercentage",
        ".a-size-medium.a-color-success",
        ".a-size-base.a-color-price",
        "[data-automation-id='discount-percentage']",
        ".a-badge-text"
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
        ("#imgTagWrapperId img", "data-a-dynamic-image"),
        ("#altImages img", "src"),
        (".a-dynamic-image", "src")
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
        ".a-row .a-size-base",
        "[data-automation-id='brand-name']",
        ".author .a-link-normal"
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
        "#title",
        "[data-automation-id='title']"
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
        "#averageCustomerReviews .a-size-base",
        "[data-hook='total-review-count']",
        "#acrCustomerReviewLink"
    ]
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return clean_text(txt)
    return None


def extract_about_this_item(soup):
    """Enhanced extraction of 'About this item' section"""
    about_items = []
    
    # Comprehensive selectors for about this item
    about_selectors = [
        # Primary feature bullets selectors
        "#feature-bullets ul li span.a-list-item",
        "#feature-bullets ul li .a-list-item",
        "#feature-bullets ul li",
        "#feature-bullets .a-list-item",
        
        # Feature bullets variations
        "#featurebullets_feature_div ul li",
        "#featurebullets_feature_div .a-list-item",
        "[data-feature-name='featurebullets'] ul li",
        "[data-feature-name='featurebullets'] .a-list-item",
        
        # Product overview
        "#productOverview_feature_div .a-list-item",
        "#productOverview_feature_div ul li",
        "#productOverview_feature_div .a-row",
        
        # A+ content feature bullets
        "#aplus_feature_div ul li",
        "#aplus_feature_div .a-list-item",
        
        # Alternative layouts
        ".a-unordered-list.a-vertical li",
        ".feature .a-list-item",
        "[data-automation-id='feature-bullets'] ul li",
        "[data-automation-id='feature-bullets'] .a-list-item",
        
        # Fallback selectors
        ".feature-bullets ul li",
        ".product-bullets ul li",
        ".feature-list li"
    ]

    for selector in about_selectors:
        elements = soup.select(selector)
        if elements:
            temp_items = []
            for li in elements:
                # Get text and clean it
                text = clean_text(li.get_text(strip=True))
                
                # Skip empty, very short, or heading-like text
                if not text or len(text) < 5:
                    continue
                    
                # Skip if it's just a bullet point or symbol
                if text in ['•', '▪', '▫', '‣', '-']:
                    continue
                    
                # Skip if it looks like a heading (ends with colon and is short)
                if text.endswith(':') and len(text) < 30:
                    continue
                    
                # Skip navigation or UI elements
                skip_phrases = [
                    'see more', 'show more', 'read more', 'learn more',
                    'click here', 'view details', 'important information',
                    'warning', 'note:', 'disclaimer'
                ]
                if any(phrase in text.lower() for phrase in skip_phrases):
                    continue
                
                # Clean up bullet points and formatting
                text = re.sub(r'^[•▪▫‣\-\*]\s*', '', text)  # Remove leading bullets
                text = re.sub(r'^\d+\.\s*', '', text)  # Remove numbering
                text = text.strip()
                
                if text and len(text) > 10:  # Only keep substantial content
                    temp_items.append(text)
            
            if temp_items:
                about_items = temp_items
                break

    # Fallback: Search for any div with "feature" in the id/class
    if not about_items:
        feature_containers = soup.find_all(['div', 'section'], 
                                         attrs={'id': re.compile(r'.*feature.*', re.I)})
        feature_containers.extend(soup.find_all(['div', 'section'], 
                                               attrs={'class': re.compile(r'.*feature.*', re.I)}))
        
        for container in feature_containers:
            bullets = container.select('ul li, ol li, .a-list-item')
            temp_items = []
            for bullet in bullets:
                text = clean_text(bullet.get_text(strip=True))
                if text and len(text) > 15 and not text.endswith(':'):
                    text = re.sub(r'^[•▪▫‣\-\*]\s*', '', text)
                    if text:
                        temp_items.append(text)
            
            if len(temp_items) >= 2:  # Need at least 2 items to be valid
                about_items = temp_items
                break

    return about_items[:10]  # Limit to 10 items maximum


def extract_from_manufacturer(soup):
    """Extract 'From the Manufacturer' section content"""
    manufacturer_content = {}
    
    # Look for manufacturer section
    manufacturer_selectors = [
        "#aplus_feature_div",
        "#aplusBrandStory_feature_div",
        "#acs_desktop",
        "#aplus",
        "[data-feature-name='aplus']",
        "#productDescription_feature_div",
        "#ProductDescription",
        ".aplus-v2",
        ".premium-aplus",
        ".brand-story"
    ]
    
    manufacturer_section = None
    for selector in manufacturer_selectors:
        manufacturer_section = soup.select_one(selector)
        if manufacturer_section:
            break
    
    if not manufacturer_section:
        return manufacturer_content
    
    # Extract structured content
    content_parts = []
    images = []
    
    # Look for text content
    text_elements = manufacturer_section.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    for elem in text_elements:
        text = clean_text(elem.get_text(strip=True))
        if text and len(text) > 20:  # Only substantial text
            # Skip if it's likely a duplicate or navigation element
            skip_phrases = ['click to expand', 'see more', 'read more', 'show details']
            if not any(phrase in text.lower() for phrase in skip_phrases):
                content_parts.append(text)
    
    # Extract images from manufacturer section
    img_elements = manufacturer_section.find_all('img')
    for img in img_elements:
        src = img.get('src') or img.get('data-src') or img.get('data-lazy')
        if src and 'amazon' in src:
            alt = img.get('alt', '')
            images.append({
                'url': src,
                'alt_text': clean_text(alt) if alt else ''
            })
    
    # Look for specific manufacturer subsections
    subsections = {}
    
    # Try to find headers and organize content
    headers = manufacturer_section.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    current_section = None
    
    for header in headers:
        header_text = clean_text(header.get_text(strip=True))
        if header_text and len(header_text) < 100:  # Reasonable header length
            current_section = header_text
            subsections[current_section] = []
            
            # Get content after this header until next header
            next_elem = header.find_next_sibling()
            while next_elem and next_elem.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if next_elem.name in ['p', 'div', 'span', 'ul', 'ol']:
                    text = clean_text(next_elem.get_text(strip=True))
                    if text and len(text) > 10:
                        subsections[current_section].append(text)
                next_elem = next_elem.find_next_sibling()
    
    # Compile final manufacturer content
    if content_parts:
        manufacturer_content['description'] = content_parts[:5]  # Limit to 5 main paragraphs
    
    if images:
        manufacturer_content['images'] = images[:10]  # Limit to 10 images
    
    if subsections:
        manufacturer_content['sections'] = subsections
    
    # Alternative: Look for A+ content modules
    aplus_modules = manufacturer_section.select('[data-module-name], .aplus-module')
    if aplus_modules:
        modules = []
        for module in aplus_modules[:5]:  # Limit to 5 modules
            module_name = module.get('data-module-name', 'Unknown Module')
            module_text = clean_text(module.get_text(strip=True))
            if module_text and len(module_text) > 20:
                modules.append({
                    'module_name': module_name,
                    'content': module_text[:500]  # Limit length
                })
        if modules:
            manufacturer_content['aplus_modules'] = modules
    
    return manufacturer_content


def extract_product_description(soup):
    """Extract detailed product description"""
    description_content = []
    
    # Look for product description sections
    description_selectors = [
        "#productDescription",
        "#ProductDescription", 
        "#product-description",
        "#productDescription_feature_div",
        "[data-feature-name='productDescription']",
        ".product-description",
        "#bookDescription_feature_div",
        "#editorialReviews_feature_div"
    ]
    
    for selector in description_selectors:
        desc_section = soup.select_one(selector)
        if desc_section:
            # Extract paragraphs and meaningful text blocks
            text_elements = desc_section.find_all(['p', 'div'], recursive=True)
            for elem in text_elements:
                text = clean_text(elem.get_text(strip=True))
                if text and len(text) > 30:  # Only substantial content
                    # Skip if it contains common non-description phrases
                    skip_phrases = ['product dimensions', 'item weight', 'shipping weight', 
                                  'best sellers rank', 'customer reviews', 'date first available']
                    if not any(phrase in text.lower() for phrase in skip_phrases):
                        description_content.append(text)
            
            if description_content:
                break
    
    return description_content[:3]  # Limit to 3 main description paragraphs


def setup_driver(domain_config):
    """Setup Chrome driver with appropriate settings for the domain"""
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Enhanced user agent based on domain
    if 'ca' in domain_config.get('lang', '').lower():
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    else:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    
    options.add_argument(f"--user-agent={user_agent}")
    
    # Set language preference
    options.add_argument(f"--lang={domain_config.get('lang', 'en-US')}")
    
    driver = webdriver.Chrome(options=options)
    
    # Execute script to remove webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def scrape_amazon_product(url):
    # Get domain configuration
    domain_config = get_domain_info(url)
    
    # Setup driver with domain-specific settings
    driver = setup_driver(domain_config)
    wait = WebDriverWait(driver, 15)  # Increased timeout

    try:
        driver.get(url)
        time.sleep(5)  # Wait for page to load

        soup = BeautifulSoup(driver.page_source, "html.parser")

        product = {}
        # ASIN
        try:
            product["asin"] = url.split("/dp/")[1].split("/")[0]
        except Exception:
            product["asin"] = None
        
        product["url"] = url
        product["domain"] = domain_config
        
        # Title
        product["title"] = try_title(soup)
        
        # Brand
        product["brand"] = try_brand(soup)
        
        # Rating
        product["rating"] = try_rating(soup)
        
        # Total Reviews
        product["total_reviews"] = try_total_reviews(soup)
        
        # Price with domain-specific handling
        product["price"] = try_price(soup, domain_config, debug=False)
        
        # Deal
        product["deal"] = try_deal(soup)
        
        # Main Image
        product["main_image"] = try_main_image(soup)

        # Enhanced About This Item
        product["about_this_item"] = extract_about_this_item(soup)
        
        # From the Manufacturer
        product["from_manufacturer"] = extract_from_manufacturer(soup)
        
        # Product Description
        product["product_description"] = extract_product_description(soup)

        # Enhanced Buy Box Info
        buybox = {}
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Enhanced buybox area detection
        buybox_selectors = [
            "#desktop_buyBox",
            "#rightCol", 
            "#buybox",
            "#apex_desktop",
            "#newAccordionCaption_feature_div",
            "[data-automation-id='buybox']",
            "#desktop_qualifiedBuybox"
        ]
        
        buybox_area = None
        for selector in buybox_selectors:
            buybox_area = soup.select_one(selector)
            if buybox_area:
                break

        if buybox_area:
            all_text = buybox_area.get_text(separator='|').split('|')
            for i, text in enumerate(all_text):
                text = clean_text(text)
                if text.lower() in ["ships from", "dispatched from"] and i + 1 < len(all_text):
                    next_text = clean_text(all_text[i + 1])
                    if next_text and next_text.lower() not in ["ships from", "sold by", "payment", "dispatched from"]:
                        buybox["ships_from"] = next_text
                elif text.lower() == "sold by" and i + 1 < len(all_text):
                    next_text = clean_text(all_text[i + 1])
                    if next_text and next_text.lower() not in ["ships from", "sold by", "payment"]:
                        buybox["sold_by"] = next_text

        # Enhanced seller detection with domain-specific patterns
        if not buybox.get("sold_by"):
            seller_patterns = [
                r"sold by\s*:?\s*([^,\n\|]+)",
                r"seller\s*:?\s*([^,\n\|]+)",
                r"merchant\s*:?\s*([^,\n\|]+)",
                r"shipped and sold by\s*:?\s*([^,\n\|]+)"
            ]
            page_text = soup.get_text()
            for pattern in seller_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    sold_by = clean_text(match.group(1))
                    if sold_by and len(sold_by) > 2:
                        buybox["sold_by"] = sold_by
                        break

        # Extract additional buybox information
        if buybox_area:
            # Delivery information
            delivery_selectors = [
                "#mir-layout-DELIVERY_BLOCK",
                "#deliveryBlockMessage",
                "#fast-track-message",
                "#delivery-block",
                ".a-spacing-top-base"
            ]
            
            for selector in delivery_selectors:
                delivery_elem = buybox_area.select_one(selector)
                if delivery_elem:
                    delivery_text = clean_text(delivery_elem.get_text())
                    if delivery_text and len(delivery_text) > 10:
                        buybox["delivery_info"] = delivery_text
                        break
            
            # Stock status
            stock_selectors = [
                "#availability span",
                "#availability .a-color-success",
                "#availability .a-color-state",
                ".a-color-success",
                ".a-color-state"
            ]
            
            for selector in stock_selectors:
                stock_elem = buybox_area.select_one(selector)
                if stock_elem:
                    stock_text = clean_text(stock_elem.get_text())
                    if stock_text and 'stock' in stock_text.lower():
                        buybox["stock_status"] = stock_text
                        break

        product["buybox"] = buybox

        # Enhanced Child SKU Links (Color/Model Variants)
        product["child_skus"] = []
        try:
            # Enhanced variant detection
            variant_selectors = [
                "li[data-asin][data-csa-c-item-id]",
                "[data-automation-id='color-picker'] li",
                "[data-automation-id='size-picker'] li",
                "#variation_color_name li",
                "#variation_style_name li",
                "#variation_size_name li",
                ".swatches li",
                ".a-button-group .a-button"
            ]
            
            for selector in variant_selectors:
                dimension_items = driver.find_elements(By.CSS_SELECTOR, selector)
                for item in dimension_items:
                    try:
                        asin = item.get_attribute("data-asin")
                        if asin and asin != product["asin"]:
                            base_domain = url.split('/dp/')[0]
                            variant_url = f"{base_domain}/dp/{asin}"
                            
                            # Try to get variant name/description
                            variant_name = None
                            try:
                                variant_name = item.get_attribute("title") or item.get_attribute("aria-label")
                                if not variant_name:
                                    variant_name = clean_text(item.text)
                            except:
                                pass
                            
                            variant_info = {
                                "url": variant_url, 
                                "asin": asin,
                                "variant_name": variant_name if variant_name else f"Variant {asin}"
                            }
                            
                            if not any(sku["asin"] == asin for sku in product["child_skus"]):
                                product["child_skus"].append(variant_info)
                    except Exception:
                        continue
                if product["child_skus"]:
                    break
                    
        except Exception as e:
            print(f"Error extracting child SKUs: {e}")

        # Product Specifications
        specs = {}
        
        # Technical details table
        tech_details_selectors = [
            "#productDetails_techSpec_section_1",
            "#technicalSpecifications_section_1", 
            "#productDetails_detailBullets_sections1",
            "#detail-bullets",
            "#productDetails_feature_div"
        ]
        
        for selector in tech_details_selectors:
            tech_section = soup.select_one(selector)
            if tech_section:
                # Extract table rows
                rows = tech_section.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = clean_text(cells[0].get_text(strip=True))
                        value = clean_text(cells[1].get_text(strip=True))
                        if key and value and len(key) < 100 and len(value) < 200:
                            specs[key] = value
                
                # Extract definition lists
                dts = tech_section.find_all('dt')
                for dt in dts:
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        key = clean_text(dt.get_text(strip=True))
                        value = clean_text(dd.get_text(strip=True))
                        if key and value:
                            specs[key] = value
                
                if specs:
                    break
        
        # Additional product details
        detail_bullets = soup.select_one("#detail-bullets")
        if detail_bullets:
            detail_items = detail_bullets.find_all('li')
            for item in detail_items:
                text = clean_text(item.get_text())
                if ':' in text:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        key = clean_text(parts[0])
                        value = clean_text(parts[1])
                        if key and value and len(key) < 50:
                            specs[key] = value

        product["specifications"] = specs

        # Additional Images
        additional_images = []
        
        # Look for image thumbnails
        image_selectors = [
            "#altImages img",
            "#imageBlock_thumb img", 
            ".a-button-thumbnail img",
            ".imageThumb img",
            "[data-action='main-image-click'] img"
        ]
        
        for selector in image_selectors:
            imgs = soup.select(selector)
            for img in imgs:
                src = img.get('src') or img.get('data-src')
                if src and src not in [product.get("main_image")] and 'amazon' in src:
                    # Try to get higher resolution version
                    if '_SS' in src or '_SX' in src or '_SY' in src:
                        # Replace with larger version
                        src = re.sub(r'_S[XY]\d+_', '_SL1600_', src)
                        src = re.sub(r'_SS\d+_', '_SL1600_', src)
                    
                    additional_images.append(src)
        
        # Remove duplicates and limit
        additional_images = list(dict.fromkeys(additional_images))[:10]
        product["additional_images"] = additional_images

        # Q&A Section
        qa_data = []
        try:
            # Scroll to Q&A section
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            qa_section = soup.select_one("#ask-dp-search_feature_div, #customerQA")
            if qa_section:
                qa_items = qa_section.select("[data-hook='pa-answer-display-question']")[:5]  # Limit to 5 Q&As
                
                for qa_item in qa_items:
                    question_elem = qa_item.select_one("[data-hook='pa-answer-display-question-title']")
                    answer_elem = qa_item.select_one("[data-hook='pa-answer-display-answer-body']")
                    
                    if question_elem and answer_elem:
                        question = clean_text(question_elem.get_text())
                        answer = clean_text(answer_elem.get_text())
                        
                        if question and answer:
                            qa_data.append({
                                "question": question,
                                "answer": answer
                            })
            
        except Exception as e:
            print(f"Error extracting Q&A: {e}")
        
        product["qa"] = qa_data

        return product

    finally:
        driver.quit()


# Enhanced Example Usage
if __name__ == "__main__":
    # Test with Canadian URL
    url = "https://www.amazon.ca/DC-Super-Hero-Girls-Wonder/dp/B0756MRF7V/ref=sr_1_53?dib=eyJ2IjoiMSJ9.saWvxQp78FsyBDk86wTZDGDDEnigVtLiyJKF_Iwdz0UF9a3rWjQI69O1dskfBoBdzTdLUBVB27hB4da908-WxIG0SdH7qyQmQxgmqxNheMm3XxDEVRhbd8HMh8L6gTz7kjJpizx6yPAyR4RDaWdN9QM5CUlpsndyaTyMXZoqACQfGGCo7bPKUCPY1EPJyP2nZi8fu85RV2jhbp9aOWo4-tuawwAlbNgzWN4R43Yk1x9mk7atCLnJeV6f_IqBdRBI9pt7XXaOPy66XDdT5xje3p3Cu6NG1DmFVOecCzKIw00.gC3WIaPz8vuXtDAEgoUYlJpExVjcUPFJQVBqb7a754g&dib_tag=se&keywords=Superhero+Pet+Toys&qid=1751297939&sr=8-53"
    
    print("Scraping Amazon product...")
    data = scrape_amazon_product(url)
    
    # Print summary
    print(f"\nProduct Title: {data.get('title', 'N/A')}")
    print(f"Brand: {data.get('brand', 'N/A')}")
    print(f"Price: {data.get('price', 'N/A')}")
    print(f"Rating: {data.get('rating', 'N/A')}")
    print(f"About This Item: {len(data.get('about_this_item', []))} items")
    print(f"From Manufacturer: {'Yes' if data.get('from_manufacturer') else 'No'}")
    print(f"Product Description: {len(data.get('product_description', []))} paragraphs")
    print(f"Specifications: {len(data.get('specifications', {}))} items")
    print(f"Additional Images: {len(data.get('additional_images', []))} images")
    print(f"Q&A Items: {len(data.get('qa', []))} items")
    print(f"Child SKUs: {len(data.get('child_skus', []))} variants")
    
    # Save to JSON file
    with open('enhanced_output.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\nComplete data saved to 'enhanced_output.json'")
    print(f"Total data fields extracted: {len(data)}")
    
    # Display sample of each new section
    if data.get('about_this_item'):
        print(f"\nSample About This Item:")
        for i, item in enumerate(data['about_this_item'][:3], 1):
            print(f"  {i}. {item[:100]}...")
    
    if data.get('from_manufacturer'):
        print(f"\nFrom Manufacturer sections found:")
        for key in data['from_manufacturer'].keys():
            print(f"  - {key}")
    
    if data.get('specifications'):
        print(f"\nSample Specifications:")
        for i, (key, value) in enumerate(list(data['specifications'].items())[:3], 1):
            print(f"  {i}. {key}: {value}")