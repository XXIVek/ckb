import psycopg2
import sys

conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
cur = conn.cursor()

# Проверка документов о полнотекстовом поиске
print("=== Документы по полнотекстовому поиску (новые) ===")
cur.execute("""
    SELECT id, LEFT(title, 80), LENGTH(COALESCE(content, '')) 
    FROM docs 
    WHERE title LIKE '%полнотекстов%' OR title LIKE '%Глава 20%'
    ORDER BY id DESC LIMIT 10
""")
for row in cur.fetchall():
    print(f"  ID={row[0]}, Title='{row[1]}', ContentLen={row[2]}")

# Проверка всех заполненных документов
print("\n=== Итоговая статистика ===")
cur.execute("SELECT COUNT(*) FROM docs")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM docs WHERE LENGTH(COALESCE(content, '')) > 0")
filled = cur.fetchone()[0]
print(f"  Всего документов: {total}")
print(f"  С контентом: {filled} ({filled*100//total}%)")

# Проверка контента в новом документе (самый высокий ID)
cur.execute("""
    SELECT id, LEFT(title, 80), SUBSTRING(content FROM 1 FOR 200) 
    FROM docs 
    WHERE LENGTH(COALESCE(content, '')) > 0
    ORDER BY id DESC LIMIT 3
""")
print("\n=== Последние документы с контентом (первые 200 символов) ===")
for row in cur.fetchall():
    content_preview = row[2].replace('\n', ' ')[:200]
    print(f"  ID={row[0]}, Title='{row[1]}', ContentPreview='{content_preview}...'")

conn.close()
