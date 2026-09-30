#!/usr/bin/env python3
"""Скачивание документации 1С с ИТС по категориям."""
import requests, os, re, time, sys
from pathlib import Path
from bs4 import BeautifulSoup

ITS_LOGIN = '08782-03'
ITS_PASSWORD = 'Sdt090985'
OUTPUT_BASE = r'C:\1C_LLM\ckb\docs\its'

# Категории: (код_папки, имя, URL browse категории)
categories = [
    ('language', 'Встроенный язык', 'https://its.1c.ru/db/v8327doc/browse/13/-1/3'),
    ('concept', 'Концепция системы', 'https://its.1c.ru/db/v8327doc/browse/13/-1/1'),
    ('config', 'Работа с конфигурацией', 'https://its.1c.ru/db/v8327doc/browse/13/-1/2'),
    ('cmdinterface', 'Командный интерфейс', 'https://its.1c.ru/db/v8327doc/browse/13/-1/4'),
    ('extension', 'Механизмы расширения', 'https://its.1c.ru/db/v8327doc/browse/13/-1/5'),
]
extra_categories = [
    ('queries', 'Работа с запросами', None),  # будет найдено автоматически
    ('reporting', 'Отчёты и обработки', None),
    ('platform', 'Платформа 1С:Предприятие', None),
]

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
})

print('Авторизация на ИТС...')
try:
    # Сначала получим куки
    resp = s.get('https://its.1c.ru/', timeout=15)
    resp = s.get('https://its.1c.ru/user/auth', timeout=15)
    token_match = re.search(r'name="_token".*?value="([^"]+)"', resp.text, re.DOTALL)
    if not token_match:
        token_match = re.search(r'value="([^"]+)".*?name="_token"', resp.text, re.DOTALL)
    csrf_token = token_match.group(1) if token_match else ''
    login_data = {'login': ITS_LOGIN, 'password': ITS_PASSWORD, '_token': csrf_token}
    resp = s.post('https://its.1c.ru/user/login', data=login_data, timeout=15, allow_redirects=True)
    print(f'Авторизация: {resp.url}')
except Exception as e:
    print(f'Ошибка авторизации: {e}')

total_downloaded = 0


def extract_content_links(soup):
    """Извлечь все ссылки на контент (hdoc) со страницы."""
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/db/v8327doc/content/' in href and href.endswith('/hdoc'):
            clean_href = href.split('#')[0].split('?')[0]
            url = f'https://its.1c.ru{clean_href}'
            title = a.get_text().strip()
            if title and len(title) > 2:
                links.append((title, url))
    return links


def download_page(url, filepath):
    """Скачать одну страницу."""
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


def download_category(cat_code, cat_name, browse_url):
    """Скачать все страницы категории."""
    global total_downloaded
    print(f'\n=== [{cat_code}] {cat_name} ===')
    cat_dir = os.path.join(OUTPUT_BASE, cat_code)
    os.makedirs(cat_dir, exist_ok=True)

    resp = s.get(browse_url, timeout=30)
    if resp.status_code != 200:
        print(f'  Ошибка загрузки browse: {resp.status_code}')
        return

    soup = BeautifulSoup(resp.text, 'html.parser')
    content_links = extract_content_links(soup)
    print(f'  Найдено подразделов: {len(content_links)}')

    for i, (title, url) in enumerate(content_links):
        safe_title = re.sub(r'[^\w\u0400-\u04FF\s\-]', '', title).strip()[:60] or f'item_{i}'
        filename = f'{i+1:03d}_{safe_title.replace(" ", "_")}.html'
        filepath = os.path.join(cat_dir, filename)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 500:
            print(f'  {i+1:03d}. SKIP: {title[:50]}')
            continue

        try:
            print(f'  {i+1:03d}. {title[:60]}...')
            download_page(url, filepath)
        except Exception as e:
            print(f'  Ошибка: {e}')

        time.sleep(0.3)

    downloaded = len(list(Path(cat_dir).glob('*.html')))
    print(f'  Скачано файлов: {downloaded}')


# === Основная логика ===
print('=' * 60)
all_cats = categories + extra_categories
for cat_code, cat_name, browse_url in all_cats:
    if browse_url is None:
        # Для дополнительных категорий попробуем найти browse URL
        print(f'\n=== [{cat_code}] {cat_name} (поиск browse URL) ===')
        try:
            resp = s.get('https://its.1c.ru/db/v8327doc/browse/13/-1', timeout=30)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                title = a.get_text().strip()
                if cat_code.lower() in title.lower() and '/browse/13/-1/' in href:
                    browse_url = f'https://its.1c.ru{href}'
                    print(f'  Найден URL: {browse_url}')
                    break
        except:
            pass

    if browse_url:
        try:
            download_category(cat_code, cat_name, browse_url)
            time.sleep(1)
        except Exception as e:
            print(f'Ошибка {cat_code}: {e}')
    else:
        print(f'  Пропуск: нет browse URL для [{cat_code}]')

print('=' * 60)
print(f'ИТОГО скачано: {total_downloaded} файлов')
for cat_code, cat_name, _ in all_cats:
    cat_dir = os.path.join(OUTPUT_BASE, cat_code)
    if os.path.exists(cat_dir):
        count = len(list(Path(cat_dir).glob('*.html')))
        print(f'  {cat_code}: {count} файлов')

