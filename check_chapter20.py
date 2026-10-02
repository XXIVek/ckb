import psycopg2
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
cur = conn.cursor()

# Проверка всех документов с "Механизм полнотекстового поиска"
print("=== Документы с 'Механизм полнотекстового поиска' ===")
cur.execute("""
    SELECT id, title, LENGTH(COALESCE(content, '')) 
    FROM docs 
    WHERE title LIKE '%Механизм полнотекстового поиска%'
    ORDER BY id
""")
for row in cur.fetchall():
    print(f"  ID={row[0]}, Title='{row[1]}', ContentLen={row[2]}")

# Проверка всех документов с "Глава 20"
print("\n=== Документы с 'Глава 20' ===")
cur.execute("""
    SELECT id, title, LENGTH(COALESCE(content, '')) 
    FROM docs 
    WHERE title LIKE '%Глава 20%'
    ORDER BY id
""")
for row in cur.fetchall():
    print(f"  ID={row[0]}, Title='{row[1]}', ContentLen={row[2]}")

# Проверка всех пустых документов о полнотекстовом поиске
print("\n=== Пустые документы о полнотекстовом поиске (для удаления) ===")
cur.execute("""
    SELECT id, LEFT(title, 70), LENGTH(content) 
    FROM docs 
    WHERE title LIKE '%полнотекстов%' AND LENGTH(COALESCE(content, '')) = 0
    ORDER BY id
""")
rows = cur.fetchall()
print(f"  Найдено: {len(rows)} документов")
for row in rows[:10]:
    print(f"    ID={row[0]}, Title='{row[1]}', ContentLen={row[2]}")

conn.close()




