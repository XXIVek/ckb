"""Рекурсивная загрузка всех подразделов ITS."""
import requests
from bs4 import BeautifulSoup
import time
from pathlib import Path

OUTPUT_DIR = Path('_its_download')
OUTPUT_DIR.mkdir(exist_ok=True)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# Начальные URL для обхода
START_URLS = [
    'https://its.1c.ru/db/metod8dev/browse/13/-1',
    'https://its.1c.ru/db/metod8dev/browse/13/-1/3199',
    'https://its.1c.ru/db/metod8dev/browse/13/-1/3190',
    'https://its.1c.ru/db/metod8dev/browse/13/-1/3272',
]

# Собираем все URL через BFS
visited_urls = set()
queue = list(START_URLS)
all_urls = []

while queue:
    url = queue.pop(0)
    
    if url in visited_urls:
        continue
    visited_urls.add(url)
    
    print(f"[+] Обход: {url}")
    
    try:
        resp = session.get(url, timeout=30)
        
        if resp.status_code != 200:
            print(f"    [!] Статус {resp.status_code}, пропускаем")
            continue
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Сохраняем HTML
        filename = url.rstrip('/').split('/')[-1] or 'index'
        safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in filename)
        filepath = OUTPUT_DIR / f"{safe_name}.html"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        
        print(f"    [OK] {filepath.name} ({len(resp.text)} bytes)")
        all_urls.append(url)
        
        # Ищем новые подразделы
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            if '/browse/' in href or '/content/' in href:
                full_url = href if href.startswith('http') else f"https://its.1c.ru{href}"
                if full_url not in visited_urls:
                    queue.append(full_url)
        
        time.sleep(0.5)
        
    except Exception as e:
        print(f"    [!] Ошибка: {e}")

print(f"\n=== ИТОГО ===")
print(f"  Всего загружено страниц: {len(all_urls)}")
print(f"  Всего HTML файлов в папке: {len(list(OUTPUT_DIR.glob('*.html')))}")

# Показываем все файлы
for f in sorted(OUTPUT_DIR.glob('*.html'), key=lambda x: x.stat().st_size, reverse=True):
    print(f"  [{f.stat().st_size:>8} bytes] {f.name}")



