#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\1C_LLM\ckb')
from src.database import get_connection

conn = get_connection()
cur = conn.cursor()

keywords = ['ГенераторСлучайныхЧисел', 'СлучайноеЧисло', '7.3.4.3.2']
cur.execute("SELECT content::text FROM docs WHERE id=280;")
row = cur.fetchone()
content = row[0] if row and row[0] else ''

print(f"Документ ID=280, длина контента: {len(content)}")
print("\nПоиск ключевых слов:")
for kw in keywords:
    pos = content.find(kw)
    if pos >= 0:
        context = content[max(0,pos-80):pos+len(kw)+80]
        print(f"\n  НАЙДЕНО '{kw}' на позиции {pos}")
        print(f"  Контекст:\n    ...{context}...")
    else:
        print(f"\n  НЕ НАЙДЕНО '{kw}'")

cur.close()
conn.close()
