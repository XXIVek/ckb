#!/usr/bin/env python3
"""Добавление новых тегов для маркировки источников."""
import sys
sys.path.insert(0, 'src')
from database import get_connection

conn = get_connection()
cur = conn.cursor()

# Новые теги для маркировки источников
new_tags = [
    ('source:internet', 'Материалы из интернета', 'Пользовательский код или материалы, загруженные из внешних источников (HTML, markdown)', 0.7),
    ('source:official', 'Официальная документация', 'Проверенные материалы из официальной документации 1С', 1.0),
    ('source:its', 'Материалы с ИТС', 'Документация и материалы с портала ИТС', 0.9),
    ('source:user', 'Пользовательский код', 'Код, предоставленный пользователями или найденный в интернете', 0.6),
]

print("=== Добавление новых тегов ===")
for code, name, description, weight in new_tags:
    # Проверяем, существует ли тег
    cur.execute('SELECT id FROM doc_tags WHERE code = %s', (code,))
    exists = cur.fetchone()
    
    if exists:
        print(f"  [SKIP] Тег {code} уже существует")
    else:
        cur.execute(
            'INSERT INTO doc_tags (code, name, description, weight) VALUES (%s, %s, %s, %s)',
            (code, name, description, weight)
        )
        print(f"  [OK] Добавлен тег {code}: {name} (weight={weight})")

conn.commit()

# Обновляем существующие сниппеты с source_url
print("\n=== Обновление сниппетов с source_url ===")
cur.execute('SELECT id, question, tags FROM knowledge_snippets WHERE source_url IS NOT NULL')
snippets = cur.fetchall()

updated = 0
for s in snippets:
    current_tags = s[2] or []
    if 'source:internet' not in current_tags:
        new_tags_list = list(current_tags) + ['source:internet']
        cur.execute(
            'UPDATE knowledge_snippets SET tags = %s WHERE id = %s',
            (new_tags_list, s[0])
        )
        updated += 1
        print(f"  [OK] Обновлён сниппет [ID:{s[0]}]: {s[1][:60]}...")

conn.commit()
print(f"\nИтого обновлено: {updated} сниппетов")

# Получаем обновлённые теги
cur.execute('SELECT code, name, weight FROM doc_tags ORDER BY weight DESC')
rows = cur.fetchall()

print("\n=== Обновлённые теги ===")
for r in rows:
    print(f"  {r[0]}: {r[1]} (weight={r[2]})")

conn.close()
