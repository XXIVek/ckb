#!/usr/bin/env python3
"""Очистка БД и повторный импорт с правильной категоризацией."""
import sys, psycopg2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from importers import import_html_files

# Сначала очистим базу
conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
cur = conn.cursor()
cur.execute('DELETE FROM docs')
cur.execute('DELETE FROM import_log')
conn.commit()
print('База очищена.')
cur.close()
conn.close()

BASE = r'C:\1C_LLM\ckb\docs\its'

# folder_name -> db_category_code
import_mapping = [
    ('language', 'language'),
    ('concept', 'its'),
    ('config', 'platform'),
    ('cmdinterface', 'its'),
    ('extension', 'its'),
]

for folder_name, db_category in import_mapping:
    folder = Path(BASE) / folder_name
    if not folder.exists():
        print(f'Папка не найдена: {folder}')
        continue
    
    html_files = list(folder.rglob('*.html'))
    print(f'\n=== [{folder_name}] -> category={db_category} ({len(html_files)} файлов) ===')
    
    result = import_html_files(str(folder), category_code=db_category)
    print(f'  Импортировано: {result["docs_imported"]}')
    print(f'  Ошибок: {result["errors"]}')

print('\n=== ИТОГО в БД ===')
conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
cur = conn.cursor()
cur.execute('SELECT dc.code, COUNT(*) FROM docs d JOIN doc_categories dc ON d.category_id = dc.id GROUP BY dc.code ORDER BY dc.code')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} документов')
cur.close()
conn.close()
