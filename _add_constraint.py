#!/usr/bin/env python3
"""Добавление UNIQUE constraint на local_path."""
import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='local_doc',
    user='postgres', password='Sta090860'
)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE docs ADD CONSTRAINT uq_docs_local_path UNIQUE (local_path)")
    conn.commit()
    print('Constraint uq_docs_local_path добавлен!')
except Exception as e:
    conn.rollback()
    if 'already exists' in str(e).lower():
        print('Constraint уже существует.')
    else:
        print(f'Ошибка: {e}')
finally:
    cur.close()
    conn.close()
