#!/usr/bin/env python3
"""Генератор файла _download_its.py"""
code = r'''#!/usr/bin/env python3
"""Скачивание документации 1С с ИТС по категориям."""
import requests, os, re, time, sys
from pathlib import Path
from bs4 import BeautifulSoup

ITS_LOGIN = '08782-03'
ITS_PASSWORD = 'Sdt090985'
OUTPUT_BASE = r'C:\1C_LLM\ckb\docs\its'

categories = [
    ('language', 'Vstroenniy yazyk', 'https://its.1c.ru/db/v8327doc/content/1l/lvl/4159'),
    ('concept', 'Kontseptsiya sistemy', 'https://its.1c.ru/db/v8327doc/content/13/lvl/4160'),
    ('config', 'Rabota s konfiguratsiey', 'https://its.1c.ru/db/v8327doc/content/15/lvl/4161'),
    ('cmdinterface', 'Komandnyy interfeys', 'https://its.1c.ru/db/v8327doc/content/17/lvl/4162'),
    ('extension', 'Mehanizmy rasireniya', 'https://its.1c.ru/db/v8327doc/content/19/lvl/4163'),
]
extra_categories = [
    ('queries', 'Rabota s zaprosami', 'https://its.1c.ru/db/v8327doc/content/21/lvl/4164'),
    ('reporting', 'Otchety i obrabotki', 'https://its.1c.ru/db/v8327doc/content/23/lvl/4165'),
    ('platform', 'Platforma 1C', 'https://its.1c.ru/db/v8327doc/content/25/lvl/4166'),
]

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

print('Auth ITS...')
resp = s.get('https://its.1c.ru/user/auth', timeout=30)
token_match = re.search(r'name="_token".*?value="([^"]+)"', resp.text, re.DOTALL)
if not token_match:
    token_match = re.search(r'value="([^"]+)".*?name="_token"', resp.text, re.DOTALL)
csrf_token = token_match.group(1) if token_match else ''
login_data = {'login': ITS_LOGIN, 'password': ITS_PASSWORD, '_token': csrf_token}
resp = s.post('https://its.1c.ru/user/login', data=login_data, timeout=30, allow_redirects=True)
print(f'Auth URL: {resp.url}')

total_downloaded = 0

def extract_subpages(soup):
    subpages = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/db/v8327doc/content/' in href and ('/lvl/' in href or '/hdoc' in href):
            clean_href = href.split('#')[0].split('?')[0]
            url = f'https://its.1c.ru{clean_href}'
            title = a.get_text().strip()
            if title and len(title) > 2:
                subpages.append((title, url))
    return subpages

def download_page(url, filepath):
    global total_downloaded
    try:
        resp = s.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 500:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            total_downloaded += 1
            return True
    except Exception:
        pass
    return False

def download_category(cat_code, cat_name, start_url):
    global total_downloaded
    print(f'\n=== [{cat_code}] {cat_name} ===')
    cat_dir = os.path.join(OUTPUT_BASE, cat_code)
    os.makedirs(cat_dir, exist_ok=True)
    resp = s.get(start_url, timeout=30)
    if resp.status_code != 200:
        print(f'  Error: {resp.status_code}')
        return
    soup = BeautifulSoup(resp.text, 'html.parser')
    subpages = extract_subpages(soup)
    print(f'  Found: {len(subpages)}')
    for i, (title, url) in enumerate(subpages):
        safe_title = re.sub(r'[^\w\u0400-\u04FF\s\-]', '', title).strip()[:60] or f'item_{i}'
        filename = f'{i+1:03d}_{safe_title.replace(" ", "_")}.html'
        filepath = os.path.join(cat_dir, filename)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 500:
            print(f'  {i+1:03d}. Skip: {title[:40]}')
            continue
        try:
            print(f'  {i+1:03d}. {title[:60]}...')
            download_page(url, filepath)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    page_html = f.read()
                page_soup = BeautifulSoup(page_html, 'html.parser')
                subs = extract_subpages(page_soup)
                if subs and len(subs) < 50:
                    for j, (sub_title, sub_url) in enumerate(subs):
                        sub_safe = re.sub(r'[^\w\u0400-\u04FF\s\-]', '', sub_title).strip()[:50] or f'sub_{j}'
                        sub_filename = f'{i+1:03d}_{sub_safe.replace(" ", "_")}.html'
                        sub_filepath = os.path.join(cat_dir, sub_filename)
                        if not os.path.exists(sub_filepath):
                            download_page(sub_url, sub_filepath)
        except Exception as e:
            print(f'  Error: {e}')
        time.sleep(0.5)
    downloaded = len(list(Path(cat_dir).glob('*.html')))
    print(f'  Downloaded: {downloaded}')

print('=' * 60)
all_cats = categories + extra_categories
for cat_code, cat_name, start_url in all_cats:
    try:
        download_category(cat_code, cat_name, start_url)
        time.sleep(1)
    except Exception as e:
        print(f'Error {cat_code}: {e}')
print(f'\nTotal: {total_downloaded}')
for cat_code, _, _ in all_cats:
    cat_dir = os.path.join(OUTPUT_BASE, cat_code)
    if os.path.exists(cat_dir):
        count = len(list(Path(cat_dir).glob('*.html')))
        print(f'  {cat_code}: {count}')
'''

with open(r'C:\1C_LLM\ckb\_download_its.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('File _download_its.py created successfully!')
