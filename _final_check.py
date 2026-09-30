#!/usr/bin/env python3
"""Финальная проверка работы БД и поиска."""
import sys
sys.path.insert(0, 'src')
from search import list_categories, search_docs

# Категории
cats = list_categories()
print('=== Категории ===')
for c in cats:
    print(f'  {c["code"]}: {c["doc_count"]} docs')

# Поиск
results = search_docs('документация', limit=3)
print(f'\nПоиск "документация": {len(results)} результатов')
for r in results:
    title = r['title'][:50] if r['title'] else '(no title)'
    print(f'  - {title}')

# Поиск по language
results_lang = search_docs('система', category='language', limit=3)
print(f'\nПоиск "система" в language: {len(results_lang)} результатов')
for r in results_lang:
    title = r['title'][:50] if r['title'] else '(no title)'
    print(f'  - {title}')
