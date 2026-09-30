-- 1C Knowledge Base Schema (local_doc)
-- NOTE: Run pg_trgm extension first: CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS doc_categories (id SERIAL PRIMARY KEY, code VARCHAR(50) UNIQUE NOT NULL, name VARCHAR(200) NOT NULL, description TEXT, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS docs (id SERIAL PRIMARY KEY, category_id INTEGER REFERENCES doc_categories(id), title VARCHAR(1000) NOT NULL, content TEXT, source_url VARCHAR(2000), local_path VARCHAR(2000) UNIQUE, tags TEXT[], created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());

CREATE INDEX IF NOT EXISTS idx_docs_content_fts ON docs USING GIN(to_tsvector('russian', content));
CREATE INDEX IF NOT EXISTS idx_docs_tags ON docs USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_docs_title_fts ON docs USING GIN(to_tsvector('russian', title));

CREATE TABLE IF NOT EXISTS doc_fragments (id SERIAL PRIMARY KEY, category_id INTEGER REFERENCES doc_categories(id), fragment_type VARCHAR(50) NOT NULL, name VARCHAR(1000) NOT NULL, signature TEXT, content TEXT, parent_fragment_id INTEGER REFERENCES doc_fragments(id), related_doc_id INTEGER REFERENCES docs(id), full_text_search TSVECTOR, created_at TIMESTAMP DEFAULT NOW());

CREATE INDEX IF NOT EXISTS idx_fragments_fts ON doc_fragments USING GIN(full_text_search);
CREATE INDEX IF NOT EXISTS idx_fragments_name ON doc_fragments USING gist (name gist_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_fragments_type ON doc_fragments(fragment_type);

CREATE TABLE IF NOT EXISTS import_log (id SERIAL PRIMARY KEY, source_type VARCHAR(50), source_path VARCHAR(2000), docs_imported INTEGER DEFAULT 0, fragments_imported INTEGER DEFAULT 0, status VARCHAR(20), error_message TEXT, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS search_cache (id SERIAL PRIMARY KEY, query_hash CHAR(64) UNIQUE NOT NULL, result_ids INTEGER[], category_filter VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_search_cache_hash ON search_cache(query_hash);
-- Таблица для сохранённых полезных пар вопрос-ответ (обратная связь)
CREATE TABLE IF NOT EXISTS knowledge_snippets (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source_url VARCHAR(2000),
    local_path VARCHAR(2000),
    tags TEXT[],
    category VARCHAR(50) REFERENCES doc_categories(code),
    confidence FLOAT DEFAULT 0.0,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snippets_question_fts ON knowledge_snippets USING GIN(to_tsvector('russian', question));
CREATE INDEX IF NOT EXISTS idx_snippets_answer_fts ON knowledge_snippets USING GIN(to_tsvector('russian', answer));
CREATE INDEX IF NOT EXISTS idx_snippets_tags ON knowledge_snippets USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_snippets_category ON knowledge_snippets(category);

-- Таблица для отслеживания добавленных/исправленных записей (audit log)
CREATE TABLE IF NOT EXISTS snippet_audit_log (
    id SERIAL PRIMARY KEY,
    snippet_id INTEGER REFERENCES knowledge_snippets(id),
    action VARCHAR(20) NOT NULL,
    old_question TEXT,
    new_question TEXT,
    old_answer TEXT,
    new_answer TEXT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
