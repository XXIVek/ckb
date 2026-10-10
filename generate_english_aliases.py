#!/usr/bin/env python3
"""Генерация и добавление англоязычных алиасов для ВСЕХ групп документации."""
import sys
sys.path.insert(0, 'src')

from database import get_connection
import re

def extract_english_names(pagetitle):
    """Извлечь английские названия из pagetitle."""
    english_names = []
    
    match = re.search(r'\(([^(]+)\)$', pagetitle)
    if match:
        content = match.group(1).strip()
        parts = re.split(r'\.', content)
        for part in parts:
            part = part.strip()
            if re.match(r'^[A-Z][a-zA-Z0-9]+$', part):
                english_names.append(part)
    
    return list(set(english_names))

def generate_aliases_for_group(pagetitle, group_id):
    """Сгенерировать список алиасов для группы."""
    aliases = set()
    english_names = extract_english_names(pagetitle)
    
    for name in english_names:
        if len(name) >= 3:
            aliases.add(name)
    
    if len(english_names) >= 2:
        for i in range(len(english_names)):
            for j in range(i+1, len(english_names)):
                alias = f"{english_names[i]}.{english_names[j]}"
                if all(len(part) >= 3 for part in alias.split('.')):
                    aliases.add(alias)
    
    translit_map = {
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D',
        'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I',
        'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
        'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T',
        'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch',
        'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '',
        'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    
    translit = ''
    for char in pagetitle:
        translit += translit_map.get(char, char)
    
    translit = re.sub(r'[^a-zA-Z0-9.]', '', translit)
    if translit and len(translit) >= 5 and translit[0] != '.' and translit[-1] != '.':
        letter_count = sum(1 for c in translit if c.isalpha())
        if letter_count >= 2:
            aliases.add(translit)
    
    return list(aliases)

def main():
    conn = get_connection()
    cur = conn.cursor()
    
    # Получаем количество групп без алиасов
    cur.execute("""
        SELECT COUNT(*) FROM groups 
        WHERE id NOT IN (SELECT groups_id FROM alias_targets WHERE groups_id IS NOT NULL)
    """)
    total_remaining = cur.fetchone()[0]
    print(f"=== Групп без алиасов: {total_remaining} ===")
    
    if total_remaining == 0:
        print("Все группы уже имеют алиасы!")
        cur.close()
        conn.close()
        return
    
    # Пакетная обработка по 500 групп
    batch_size = 500
    processed = 0
    total_aliases_added = 0
    errors = 0
    
    while processed < total_remaining:
        # Получаем следующую пачку групп
        cur.execute("""
            SELECT id, pagetitle FROM groups 
            WHERE id NOT IN (SELECT groups_id FROM alias_targets WHERE groups_id IS NOT NULL)
            ORDER BY id
            LIMIT %s
        """, (batch_size,))
        rows = cur.fetchall()
        
        if not rows:
            break
        
        batch_processed = 0
        for group_id, pagetitle in rows:
            try:
                aliases = generate_aliases_for_group(pagetitle, group_id)
                
                if not aliases:
                    continue
                
                for alias_name in aliases:
                    cur.execute("""
                        INSERT INTO alias_targets (alias_name, target_type, groups_id, tags, weight, created_at, updated_at)
                        VALUES (%s, 'group', %s, '{language,bsl}', 0.8, NOW(), NOW())
                        ON CONFLICT DO NOTHING
                    """, (alias_name, group_id))
                
                batch_processed += 1
                total_aliases_added += len(aliases)
                
            except Exception as e:
                errors += 1
        
        processed += len(rows)
        
        if batch_processed > 0:
            print(f"Обработано: {processed}/{total_remaining} | Добавлено алиасов: {total_aliases_added} | Ошибок: {errors}")
    
    conn.commit()
    
    print(f"\n=== ИТОГИ ===")
    print(f"Обработано групп: {processed}")
    print(f"Добавлено алиасов: {total_aliases_added}")
    print(f"Ошибок: {errors}")
    
    # Проверка результата
    cur.execute("SELECT COUNT(*) FROM alias_targets WHERE target_type = 'group'")
    group_aliases = cur.fetchone()[0]
    print(f"Всего алиасов для групп: {group_aliases}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()


