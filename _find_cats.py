#!/usr/bin/env python3
"""Поиск всех категорий документации ИТС."""
import requests, re
from bs4 import BeautifulSoup

s = requests.Session()
s.get('https://its.1c.ru/', timeout=10)
resp = s.get('https://its.1c.ru/user/auth', timeout=10)
token_match = re.search(r'name="_token".*?value="([^"]+)"', resp.text, re.DOTALL)
csrf_token = token_match.group(1) if token_match else ''
login_data = {'login': '08782-03', 'password': 'Sdt090985', '_token': csrf_token}
s.post('https://its.1c.ru/user/login', data=login_data, timeout=15, allow_redirects=True)

resp = s.get('https://its.1c.ru/db/v8327doc/browse/13/-1', timeout=15)
soup = BeautifulSoup(resp.text, 'html.parser')
print("Категории документации:")
for a in soup.find_all('a', href=True):
    if '/browse/13/-1/' in a['href']:
        title = a.get_text().strip()
        print(f"  {title:50} -> https://its.1c.ru{a['href']}")
