from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Setup
options = Options()
# comment next line to see browser
# options.add_argument("--headless")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Load the Amazon URL
url = "https://www.amazon.ca/s?k=kids+superhero+tshirts&crid=3CHBNPS7CLM95&refresh=1&sprefix=kids+superhero+tshir%2Caps%2C317&ref=glow_cls"
driver.get(url)

wait = WebDriverWait(driver, 15)

try:
    # Step 1: Click the "Update location" link
    update_loc = wait.until(EC.element_to_be_clickable((By.ID, "glow-ingress-block")))
    update_loc.click()

    # Step 2: Wait for postal code input to appear
    postal_input1 = wait.until(EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_0")))
    postal_input2 = wait.until(EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_1")))

    # Step 3: Enter postal code (M5V 3L)
    postal_input1.clear()
    postal_input1.send_keys("M5V")

    postal_input2.clear()
    postal_input2.send_keys("3L")

    # Step 4: Click Apply
    apply_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "span#GLUXZipUpdate .a-button-input")))
    apply_btn.click()

    # Optional: Wait to let the page refresh after location change
    wait.until(EC.presence_of_element_located((By.ID, "glow-ingress-line2")))

    print("Postal code updated!")
    print(driver.current_url)
except Exception as e:
    print("Something went wrong:", e)

# Optional: Save HTML or screenshot
# with open("page.html", "w", encoding="utf-8") as f:
#     f.write(driver.page_source)

driver.quit()
