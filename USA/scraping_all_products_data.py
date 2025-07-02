import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from scraper import scrape_amazon_product  # Make sure this exists and works
import random
import time

# ---------- SETTINGS ----------
INPUT_FILE = "amazon_usa_products.json"
OUTPUT_FOLDER = "scraped_output"
MAX_WORKERS = 3  # Number of threads in parallel
# ------------------------------

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def scrape_url_safe(url):
    try:
        return scrape_amazon_product(url)
    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return None

def scrape_city(city_data):
    city_name = city_data["location"]
    print(f"\n📍 Starting scrape for: {city_name}")
    city_result = {}
    scrape_log = []
    sc = 0
    fc = 0

    for category, category_data in city_data["categories"].items():
        print(f"\n  🧵 Scraping category: {category}")
        urls = category_data["urls"]
        category_results = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(scrape_url_safe, url): url for url in urls}
            for i, future in enumerate(as_completed(future_to_url), 1):
                url = future_to_url[future]
                result = future.result()
                main_fields = [
                    result.get('title') if isinstance(result, dict) else None,
                    result.get('price') if isinstance(result, dict) else None
                ]
                if result and any(field not in [None, '', []] for field in main_fields):
                    category_results.append(result)
                    print(f"    [{i}/{len(urls)}] SUCCESS: {url[:80]}...")
                    scrape_log.append(f"{i}. SUCCESS: {url}")
                    sc += 1
                else:
                    print(f"    [{i}/{len(urls)}] FAILED: {url[:80]}... | All main fields None or Empty")
                    scrape_log.append(f"{i}. FAILED: {url}")
                    fc += 1
                    # Rate limit avoidance system cuz we are cool like that
                time.sleep(random.uniform(2, 7))

        city_result[category] = category_results
        print(f"  ✅ Finished {category}: {len(category_results)}/{len(urls)} successfully scraped.")

    # Save per-city JSON file
    output_path = os.path.join(OUTPUT_FOLDER, f"{city_name.lower()}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(city_result, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Done with {city_name}. Saved to {output_path}\n")
    # Log file with results
    log_path = os.path.join(OUTPUT_FOLDER, f"{city_name.lower()}_scrape_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        for line in scrape_log:
            f.write(line + "\n")
        f.write(f"\nTotal URLs: {len(scrape_log)}\n")
        f.write(f"Total succeeded: {sc}\n")
        f.write(f"Total failed: {fc}\n")
    print(f"Scrape log saved to {log_path}")

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Only process the entry for New York, Washington DC, San Francisco, Austin
    for city_data in data:
        if city_data["location"].lower() == "new york":
            scrape_city(city_data)
            break

if __name__ == "__main__":
    main()
