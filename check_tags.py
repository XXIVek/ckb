#!/usr/bin/env python3
"""Проверка текущих тегов в базе данных."""
import sys
sys.path.insert(0, 'src')
from database import get_connection

conn = get_connection()
cur = conn.cursor()

# Получаем все теги
cur.execute('SELECT code, name, weight FROM doc_tags ORDER BY weight DESC')
rows = cur.fetchall()

print("=== Текущие теги ===")
for r in rows:
    print(f"  {r[0]}: {r[1]} (weight={r[2]})")

# Получаем все сниппеты с source_url
cur.execute('SELECT id, question, source_url, confidence FROM knowledge_snippets WHERE source_url IS NOT NULL')
snippets = cur.fetchall()

print(f"\n=== Сниппеты с source_url ({len(snippets)} шт.) ===")
for s in snippets:
    print(f"  [ID:{s[0]}] {s[1][:60]}... | URL: {s[2]} | confidence={s[3]}")

conn.close()
