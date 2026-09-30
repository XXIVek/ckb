import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
cur = conn.cursor()

# Таблицы
cur.execute("CREATE TABLE IF NOT EXISTS doc_categories (id SERIAL PRIMARY KEY, code VARCHAR(50) UNIQUE NOT NULL, name VARCHAR(200) NOT NULL, description TEXT, created_at TIMESTAMP DEFAULT NOW())")
print('Table doc_categories: OK')

cur.execute("CREATE TABLE IF NOT EXISTS docs (id SERIAL PRIMARY KEY, category_id INTEGER REFERENCES doc_categories(id), title VARCHAR(1000) NOT NULL, content TEXT, source_url VARCHAR(2000), local_path VARCHAR(2000), tags TEXT[], created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW())")
print('Table docs: OK')

cur.execute("CREATE TABLE IF NOT EXISTS doc_fragments (id SERIAL PRIMARY KEY, category_id INTEGER REFERENCES doc_categories(id), fragment_type VARCHAR(50) NOT NULL, name VARCHAR(1000) NOT NULL, signature TEXT, content TEXT, parent_fragment_id INTEGER REFERENCES doc_fragments(id), related_doc_id INTEGER REFERENCES docs(id), full_text_search TSVECTOR, created_at TIMESTAMP DEFAULT NOW())")
print('Table doc_fragments: OK')

cur.execute("CREATE TABLE IF NOT EXISTS import_log (id SERIAL PRIMARY KEY, source_type VARCHAR(50), source_path VARCHAR(2000), docs_imported INTEGER DEFAULT 0, fragments_imported INTEGER DEFAULT 0, status VARCHAR(20), error_message TEXT, created_at TIMESTAMP DEFAULT NOW())")
print('Table import_log: OK')

cur.execute("CREATE TABLE IF NOT EXISTS search_cache (id SERIAL PRIMARY KEY, query_hash CHAR(64) UNIQUE NOT NULL, result_ids INTEGER[], category_filter VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP)")
print('Table search_cache: OK')

conn.commit()

# Индексы
cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_content_fts ON docs USING GIN(to_tsvector('russian', content))")
cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_tags ON docs USING GIN(tags)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_title_fts ON docs USING GIN(to_tsvector('russian', title))")
cur.execute("CREATE INDEX IF NOT EXISTS idx_fragments_fts ON doc_fragments USING GIN(full_text_search)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_fragments_name ON doc_fragments USING gist (name gist_trgm_ops)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_fragments_type ON doc_fragments(fragment_type)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_hash ON search_cache(query_hash)")
conn.commit()
print('Indexes: OK')

# Категории
cur.execute("SELECT COUNT(*) FROM doc_categories")
count = cur.fetchone()[0]
if count == 0:
    cur.execute("INSERT INTO doc_categories (code, name, description) VALUES ('language', 'Язык БСЛ', 'Синтаксис языка, типы данных, встроенные объекты'), ('platform', 'Платформа 1С', 'COM-интерфейсы, HTTP-сервисы, файловые операции'), ('its', 'ИТС', 'Материалы с портала Интеграция и Технологии'), ('methodology', 'Методология', 'Бухгалтерский учёт, НД/НР, методические рекомендации')")
    conn.commit()
    print('Categories: inserted')

# Функции и триггеры
cur.execute("CREATE OR REPLACE FUNCTION update_fragment_fts() RETURNS TRIGGER AS $$ BEGIN NEW.full_text_search := to_tsvector('russian', COALESCE(NEW.name, '') || ' ' || COALESCE(NEW.signature, '') || ' ' || COALESCE(NEW.content, '')); RETURN NEW; END; $$ LANGUAGE plpgsql")
print('Function update_fragment_fts: OK')

cur.execute("CREATE TRIGGER trg_update_fragment_fts BEFORE INSERT OR UPDATE ON doc_fragments FOR EACH ROW EXECUTE FUNCTION update_fragment_fts()")
print('Trigger trg_update_fragment_fts: OK')

cur.execute("CREATE OR REPLACE FUNCTION update_updated_at() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql")
print('Function update_updated_at: OK')

cur.execute("CREATE TRIGGER trg_update_docs_updated_at BEFORE UPDATE ON docs FOR EACH ROW EXECUTE FUNCTION update_updated_at()")
print('Trigger trg_update_docs_updated_at: OK')

conn.commit()

# Проверка
cur.execute("SELECT code, name FROM doc_categories ORDER BY code")
rows = cur.fetchall()
print('\nCategories:')
for r in rows:
    print(f'  [{r[0]}] {r[1]}')

cur.close()
conn.close()
print('\n=== Schema initialized successfully! ===')
