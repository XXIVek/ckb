#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\1C_LLM\ckb')
from src.database import get_connection

conn = get_connection()
cur = conn.cursor()

# Проверим документ ID=184 (Глава 7. Формы) на наличие ключевых слов
keywords = ['ГенераторСлучайныхЧисел', 'Диаграмма', 'диаграмм', '7.3.4.3.2']
cur.execute("SELECT content::text FROM docs WHERE id=184;")
row = cur.fetchone()
content = row[0] if row and row[0] else ''

print(f"Документ ID=184, длина контента: {len(content)}")
print("\nПоиск ключевых слов:")
for kw in keywords:
    pos = content.find(kw)
    if pos >= 0:
        context = content[max(0,pos-50):pos+len(kw)+50]
        print(f"  НАЙДЕНО '{kw}' на позиции {pos}")
        print(f"    Контекст: ...{context}...")
    else:
        print(f"  НЕ НАЙДЕНО '{kw}'")

cur.close()
conn.close()
