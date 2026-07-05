import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from scraper.amazon_flipkart_scraper import scrape_flipkart, FK_QUERIES

# 14 is the index of 'macbook pro m3'
remaining_queries = FK_QUERIES[14:]

print(f"Restarting Flipkart from {remaining_queries[0]}...")

results = scrape_flipkart(headless=True, pages=50, queries=remaining_queries)
print(f"Finished remaining queries. Added {len(results)} items.")
