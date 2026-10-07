-- 1C Knowledge Base Schema (local_doc) v3 — объединённая схема алиасов
-- Основная структура: группы -> сниппеты, алиасы в alias_targets

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
    pagetitle VARCHAR(1000),
    title VARCHAR(1000),
    versionInfo VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_groups_name_fts ON groups USING GIN(to_tsvector('russian', name));
CREATE INDEX IF NOT EXISTS idx_groups_pagetitle_fts ON groups USING GIN(to_tsvector('russian', pagetitle));
CREATE INDEX IF NOT EXISTS idx_groups_tags ON groups USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_groups_parent ON groups(parent_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_groups_name_parent ON groups (name, parent_id) WHERE parent_id IS NULL;

-- ============================================
-- СНИППЕТЫ — примеры кода, привязанные к группам
-- ============================================
CREATE TABLE IF NOT EXISTS knowledge_snippets (
    id SERIAL PRIMARY KEY,
    groups_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_snippets_groups ON knowledge_snippets(groups_id);

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
-- АЛИАСЫ — объединённая таблица поиска по синонимам
-- target_type: 'group' или 'snippet'
-- groups_id / snippets_id: заполняется только один в зависимости от target_type
-- Partial unique индексы решают проблему NULL
-- ============================================
CREATE TABLE IF NOT EXISTS alias_targets (
    id SERIAL PRIMARY KEY,
    alias_name VARCHAR(500) NOT NULL,
    target_type VARCHAR(20) NOT NULL CHECK (target_type IN ('group', 'snippet')),
    groups_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    snippets_id INTEGER REFERENCES knowledge_snippets(id) ON DELETE CASCADE,
    tags TEXT[],
    weight DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Partial unique индексы (NULL не участвует в уникальности)
CREATE UNIQUE INDEX IF NOT EXISTS uq_alias_group ON alias_targets (alias_name, groups_id) WHERE groups_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_alias_snippet ON alias_targets (alias_name, snippets_id) WHERE snippets_id IS NOT NULL;

-- Индексы для быстрого поиска по ID
CREATE INDEX IF NOT EXISTS idx_alias_groups ON alias_targets(groups_id);
CREATE INDEX IF NOT EXISTS idx_alias_snippets ON alias_targets(snippets_id);

-- Полнотекстовый индекс для быстрого поиска по алиасам
CREATE INDEX IF NOT EXISTS idx_alias_fts ON alias_targets USING GIN(to_tsvector('russian', alias_name));

