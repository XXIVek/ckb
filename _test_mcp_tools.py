#!/usr/bin/env python3
"""Проверка работы всех MCP-инструментов."""
import sys
sys.path.insert(0, 'src')
from search import list_categories, search_docs, search_fragments, get_doc, get_fragment_by_name
from importers import import_html_files

print("=" * 60)
print("ПРОВЕРКА MCP-ИНСТРУМЕНТОВ")
print("=" * 60)

# 1. list_categories
print("\n[1] list_categories()")
cats = list_categories()
for c in cats:
    print(f"   [{c['code']}] {c['name']} — {c['doc_count']} docs, {c['fragment_count']} frags")

# 2. search_docs - общий поиск
print("\n[2] search_docs('запрос', limit=5)")
results = search_docs('запрос', limit=5)
print(f"   Найдено: {len(results)} результатов")
for r in results[:3]:
    title = r['title'][:60] if r['title'] else '(no title)'
    cat = r.get('category_code', '?')
    print(f"   [{cat}] {title}")

# 3. search_docs - поиск по категории language
print("\n[3] search_docs('администрирование', category='language', limit=5)")
results_lang = search_docs('администрирование', category='language', limit=5)
print(f"   Найдено: {len(results_lang)} результатов")
for r in results_lang:
    title = r['title'][:60] if r['title'] else '(no title)'
    print(f"   - {title}")

# 4. search_docs - поиск по категории platform
print("\n[4] search_docs('конфигурация', category='platform', limit=5)")
results_plat = search_docs('конфигурация', category='platform', limit=5)
print(f"   Найдено: {len(results_plat)} результатов")
for r in results_plat[:3]:
    title = r['title'][:60] if r['title'] else '(no title)'
    print(f"   - {title}")

# 5. search_docs - поиск по категории its
print("\n[5] search_docs('объект', category='its', limit=5)")
results_its = search_docs('объект', category='its', limit=5)
print(f"   Найдено: {len(results_its)} результатов")
for r in results_its[:3]:
    title = r['title'][:60] if r['title'] else '(no title)'
    print(f"   - {title}")

# 6. get_doc - получение документа по ID
if results:
    doc_id = results[0]['id']
    print(f"\n[6] get_doc(doc_id={doc_id})")
    doc = get_doc(doc_id)
    if doc:
        title = doc['title'][:60] if doc['title'] else '(no title)'
        content_len = len(doc.get('content', ''))
        print(f"   Заголовок: {title}")
        print(f"   Содержимое: {content_len} символов")

# 7. search_fragments - поиск фрагментов
print("\n[7] search_fragments('метод', fragment_type='method', limit=5)")
frags = search_fragments('метод', fragment_type='method', limit=5)
print(f"   Найдено: {len(frags)} фрагментов")

# 8. get_fragment_by_name
print("\n[8] get_fragment_by_name('type', 'Integer')")
frag = get_fragment_by_name('type', 'Integer')
if frag:
    print(f"   Найдено: {frag['name']} ({frag['fragment_type']})")
else:
    print("   Не найден (это нормально — в БД пока только документы)")

print("\n" + "=" * 60)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 60)
