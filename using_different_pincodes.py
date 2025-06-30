from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time

# Setup
options = Options()
# Comment this to see the browser
# options.add_argument("--headless")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)

# Step 1: Go to Amazon homepage
driver.get("https://www.amazon.ca/")

try:
    # 🛡️ Step 1.5: If "Continue shopping" screen appears, click it
    try:
        continue_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@value='Continue shopping']"))
        )
        print("Found bot check screen. Clicking continue...")
        continue_btn.click()
        time.sleep(2)
    except:
        print("No bot check screen, continuing normally...")

    # Step 2: Click the "Deliver to" location box
    update_loc = wait.until(EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link")))
    update_loc.click()

    # Step 3: Enter postal code (M5V 3L)
    postal_input1 = wait.until(EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_0")))
    postal_input2 = wait.until(EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput_1")))

    postal_input1.clear()
    postal_input1.send_keys("M5V")
    postal_input2.clear()
    postal_input2.send_keys("3L9")

    # Step 4: Click Apply
    apply_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "span#GLUXZipUpdate .a-button-input")))
    apply_btn.click()

    time.sleep(3)
    driver.refresh()

    # Step 5: Enter search term
    search_box = wait.until(EC.presence_of_element_located((By.ID, "twotabsearchtextbox")))
    search_box.clear()
    search_box.send_keys("Kids Superhero T Shirts")
    search_box.send_keys(Keys.RETURN)

    print("✅ Search completed. URL:", driver.current_url)

except Exception as e:
    print("❌ Error occurred:", e)

# driver.quit()  # Uncomment when you're done
