"""Подсчёт уникальных URL."""
import requests
from bs4 import BeautifulSoup

session = requests.Session()
resp = session.get('https://its.1c.ru/db/metod8dev/browse/13/-1', timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')

all_urls = set()
for link in soup.find_all('a', href=True):
    href = link['href']
    if '/browse/' in href or '/content/' in href:
        full_url = href if href.startswith('http') else f"https://its.1c.ru{href}"
        all_urls.add(full_url)

print(f"Уникальных URL: {len(all_urls)}")
for i, url in enumerate(sorted(all_urls), 1):
    print(f"  {i:3d}. {url}")
