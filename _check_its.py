#!/usr/bin/env python3
"""Проверка ИТС: сколько страниц в каждой категории."""
import requests, time, re
from bs4 import BeautifulSoup

s = requests.Session()
s.get('https://its.1c.ru/', timeout=10)
resp = s.get('https://its.1c.ru/user/auth', timeout=10)
token_match = re.search(r'name="_token".*?value="([^"]+)"', resp.text, re.DOTALL)
csrf_token = token_match.group(1) if token_match else ''
login_data = {'login': '08782-03', 'password': 'Sdt090985', '_token': csrf_token}
resp = s.post('https://its.1c.ru/user/login', data=login_data, timeout=15, allow_redirects=True)
print(f'Auth: {resp.url}')

cats = [
    ('language', 'https://its.1c.ru/db/v8327doc/browse/13/-1/3'),
    ('concept', 'https://its.1c.ru/db/v8327doc/browse/13/-1/1'),
    ('config', 'https://its.1c.ru/db/v8327doc/browse/13/-1/2'),
    ('cmdinterface', 'https://its.1c.ru/db/v8327doc/browse/13/-1/4'),
    ('extension', 'https://its.1c.ru/db/v8327doc/browse/13/-1/5'),
]

for name, url in cats:
    print(f'\n[{name}] {url}')
    resp = s.get(url, timeout=15)
    if resp.status_code != 200:
        print(f'  ERROR {resp.status_code}')
        continue
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = [a for a in soup.find_all('a', href=True) 
             if '/db/v8327doc/content/' in a['href'] and a['href'].endswith('/hdoc')]
    print(f'  HDOC links: {len(links)}')
    for l in links[:5]:
        title = l.get_text().strip()[:40]
        print(f'    {l["href"]} | {title}')
    time.sleep(1)

print('\nDone!')
