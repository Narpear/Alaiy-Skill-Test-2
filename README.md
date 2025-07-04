# Alaiy-Skill-Test-2
# Amazon Scraper

This project is a robust, multi-country web scraping system for extracting detailed product listings from Amazon across different regions and cities. It is designed to handle 10 product categories, 10 cities, and multiple Amazon domains (India, UK, USA, Canada), capturing rich product metadata such as:

* Titles, prices, ratings, reviews
* Buybox info (seller, shipping, availability)
* Variant SKUs (size, color, style)
* Manufacturer content and A+ descriptions

The scrapers are tailored to Amazon’s regional layout differences and include advanced techniques to resist bot detection. Data is structured hierarchically by country → city → category → product list and stored in a nested MongoDB database for easy querying and analysis.

---
## Navigating the Repository

Each folder (India, UK, USA, Canada) has the same files at first glance, but they are optimized to scrape data off Amazon in their respective regions. 

*   The get_country_product_urls.py files scrape the URLs of products that fall under these ten categories: Kids Superhero T Shirts, Tapes, Adhesives, Lubricants & Chemicals, Camera Accessories, Home Decor, Superhero Toys, Kitchen Gadgets, Bath Fixtures, Laptop Bags, Sleeves, Covers, Projectors, and Superhero Pet Toys -> these URLs are stored in the amazon_country_products.json files.

*   The scraper.py files contain the actual scraping logic for these files and have some region-specific scraping logic.

*   The scraping_all_products_data.py files use the URLs from the .json files (stored earlier) to scrape each product's data and store the final output in the scraped_output folders as city.json files.

*   Finally, the put_data_in_mongogb.py file helps us connect to mongodb (Atlas, in this case) and store our data (each city's data is a document)

---
## To Run this Code

```{bash}
pip install selenium
pip install beautifulsoup4
```

In any of the folders: (replace "country" in these commands with country name)

```{bash}
python get_country_product_urls.py
```

The amazon_country_products.json file is created.
Then use the needed city name at the bottom of scraping_all_products.py like this (in lower case):

```{python}
# Only process the entry for New York, Washington DC, San Francisco, Austin
    for city_data in data:
        if city_data["location"].lower() == "new york":
            scrape_city(city_data)
            break
```

This saves New York's data in scraped_output/new_york.json

Finally, when all the needed data is scraped, run the put_data_in_mongodb.py file (with your password to connect to your database) to transfer all your ata to mongodb for future querying and analytics. 

