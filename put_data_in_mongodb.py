import os
import json
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# --- MongoDB Atlas Setup ---
uri = "mongodb+srv://prerkulk:<password>@cluster0.r6nb4lx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi('1'))

# Test connection
try:
    client.admin.command('ping')
    print("✅ Successfully connected to MongoDB Atlas.")
except Exception as e:
    print("❌ Failed to connect to MongoDB Atlas:", e)
    exit(1)

# Database and collection
db = client["amazon_scraped_data"]
collection = db["cities"]  # New collection: one document per city

# --- Directory Setup ---
base_dir = os.path.dirname(os.path.abspath(__file__))
countries = ["Canada", "India", "UK", "USA"]

for country in countries:
    scraped_path = os.path.join(base_dir, country, "scraped_output")
    if not os.path.exists(scraped_path):
        print(f"⚠️ Skipping missing folder: {scraped_path}")
        continue

    country_key = country.lower()

    for filename in os.listdir(scraped_path):
        if filename.endswith(".json"):
            city = filename.replace(".json", "")
            file_path = os.path.join(scraped_path, filename)

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    city_data = json.load(f)

                doc_id = f"{country_key}_{city}"
                document = {
                    "_id": doc_id,
                    "country": country_key,
                    "city": city,
                    "products": city_data
                }

                collection.replace_one({"_id": doc_id}, document, upsert=True)
                print(f"✅ Uploaded: {country}/{city} ({len(city_data)} products)")

            except Exception as e:
                print(f"❌ Error reading {file_path}: {e}")
