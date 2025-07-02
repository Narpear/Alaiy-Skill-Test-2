import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from scraper import scrape_amazon_product  # Make sure this exists and works

# ---------- SETTINGS ----------
INPUT_FILE = "amazon_india_products.json"
OUTPUT_FOLDER = "scraped_output"
MAX_WORKERS = 12  # Number of threads in parallel
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

    for category, category_data in city_data["categories"].items():
        print(f"\n  🧵 Scraping category: {category}")
        urls = category_data["urls"]
        category_results = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(scrape_url_safe, url): url for url in urls}
            for i, future in enumerate(as_completed(future_to_url), 1):
                url = future_to_url[future]
                result = future.result()
                if result:
                    category_results.append(result)
                print(f"    [{i}/{len(urls)}] Done: {url[:80]}...")

        city_result[category] = category_results
        print(f"  ✅ Finished {category}: {len(category_results)}/{len(urls)} successfully scraped.")

    # Save per-city JSON file
    output_path = os.path.join(OUTPUT_FOLDER, f"{city_name.lower()}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(city_result, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Done with {city_name}. Saved to {output_path}\n")

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Only process the entry for Bangalore
    # Switch between Bangalore, Mumbai, Dehli, Chennai
    for city_data in data:
        if city_data["location"].lower() == "chennai":
            scrape_city(city_data)
            break

if __name__ == "__main__":
    main()
