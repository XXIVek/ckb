-- 1C Knowledge Base Schema (local_doc) v2
-- Основная структура: группы -> элементы, сниппеты, алиасы

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================
-- ТЕГИ — основной механизм классификации
-- ============================================
CREATE TABLE IF NOT EXISTS doc_tags (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    weight DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- КАТЕГОРИИ — для обратной совместимости
-- ============================================
CREATE TABLE IF NOT EXISTS doc_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- ГРУППЫ — иерархическая структура справки
-- ============================================
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    name VARCHAR(1000) NOT NULL,
    description TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_groups_name_fts ON groups USING GIN(to_tsvector('russian', name));
CREATE INDEX IF NOT EXISTS idx_groups_tags ON groups USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_groups_parent ON groups(parent_id);

-- ============================================
-- ЭЛЕМЕНТЫ — элементы справки, подчинённые группам
-- ============================================
CREATE TABLE IF NOT EXISTS elements (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    name VARCHAR(1000) NOT NULL,
    content TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_elements_name_fts ON elements USING GIN(to_tsvector('russian', name));
CREATE INDEX IF NOT EXISTS idx_elements_content_fts ON elements USING GIN(to_tsvector('russian', content));
CREATE INDEX IF NOT EXISTS idx_elements_tags ON elements USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_elements_group ON elements(group_id);
CREATE INDEX IF NOT EXISTS idx_elements_name_trgm ON elements USING gist (name gist_trgm_ops);

-- ============================================
-- СНИППЕТЫ — примеры кода, привязанные к элементам
-- ============================================
CREATE TABLE IF NOT EXISTS knowledge_snippets (
    id SERIAL PRIMARY KEY,
    element_id INTEGER REFERENCES elements(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source_url VARCHAR(2000),
    tags TEXT[],
    confidence FLOAT DEFAULT 0.5,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snippets_question_fts ON knowledge_snippets USING GIN(to_tsvector('russian', question));
CREATE INDEX IF NOT EXISTS idx_snippets_answer_fts ON knowledge_snippets USING GIN(to_tsvector('russian', answer));
CREATE INDEX IF NOT EXISTS idx_snippets_tags ON knowledge_snippets USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_snippets_element ON knowledge_snippets(element_id);

-- ============================================
-- АУДИТ СНИППЕТОВ — история изменений
-- ============================================
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

-- ============================================
-- АЛИАСЫ — поиск по синонимам для групп, элементов и сниппетов
-- ============================================
CREATE TABLE IF NOT EXISTS search_aliases (
    id SERIAL PRIMARY KEY,
    alias_name VARCHAR(500) NOT NULL,
    target_type VARCHAR(50) NOT NULL CHECK (target_type IN ('group', 'element', 'snippet')),
    target_id INTEGER NOT NULL,
    weight DOUBLE PRECISION DEFAULT 1.0,
    active BOOLEAN DEFAULT true,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aliases_name_fts ON search_aliases USING GIN (to_tsvector('russian', alias_name));
CREATE INDEX IF NOT EXISTS idx_aliases_active ON search_aliases (active);
CREATE UNIQUE INDEX IF NOT EXISTS uq_alias_target ON search_aliases (alias_name, target_type);
