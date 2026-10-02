# Очистка базы данных
import sys
sys.path.insert(0, 'src')
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
cur = conn.cursor()

cur.execute("DELETE FROM snippet_audit_log")
print('Очищен snippet_audit_log: OK')

tables_to_clear = ['docs', 'doc_fragments', 'search_aliases', 'knowledge_snippets', 'import_log']

for table in tables_to_clear:
    cur.execute('DELETE FROM ' + table)
    print('Удалено из ' + table + ': OK')

conn.commit()
cur.close()
conn.close()

print('\nБаза данных очищена!')
