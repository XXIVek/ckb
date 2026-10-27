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

-- ============================================
-- УЗЕЛ MEM-INDEX (27.10.2026) — ИНДЕКСЫ ПОД ТЕ ВЫРАЖЕНИЯ, КОТОРЫЕ ИСПОЛНЯЕТ ПОИСК
-- ============================================
-- Причина узла. search_docs (src/mcp_tools_api.py, шаги 3-4) ищет полнотекстово по СКЛЕЙКЕ
-- колонок, а индексы выше построены по одиночным колонкам. Выражение запроса и выражение
-- индекса — разные выражения, поэтому planner шёл Seq Scan: 1034 мс на 3 140 строках
-- сниппетов и 1335 мс на 25 495 строках групп на каждый промах поиска (замер 27.10.2026,
-- EXPLAIN ANALYZE). Одиночные FTS-индексы (idx_snippets_question_fts, idx_snippets_answer_fts,
-- idx_groups_name_fts, idx_groups_pagetitle_fts) при этом не читает ни один запрос
-- репозитория — поиск по исходникам находит их только в этом файле; они оставлены до
-- отдельного решения, потому что снятие — это ещё и ответ «кто будет искать по одной колонке».
CREATE INDEX IF NOT EXISTS idx_snippets_qa_fts
    ON knowledge_snippets USING GIN (to_tsvector('russian', question || ' ' || COALESCE(answer, '')));
CREATE INDEX IF NOT EXISTS idx_groups_title_fts
    ON groups USING GIN (to_tsvector('russian', name::text || ' ' || COALESCE(pagetitle, '')));

-- Шаг 1 поиска сравнивает LOWER(alias_name), а уникальные индексы построены по сырому
-- значению: предикат нижнего регистра индексом не обслуживался (Index Scan по
-- idx_alias_snippets + снято фильтром 23 603 строк). В базе 3 224 алиаса, отличающихся от
-- своей нижней формы, и 15 110 нижних форм, встречающихся несколько раз (одно имя законно
-- ведёт в несколько целей), поэтому индекс не уникальный.
CREATE INDEX IF NOT EXISTS idx_alias_name_lower ON alias_targets (LOWER(alias_name));

-- История сниппета — часть работы с долговременной памятью, а FK на snippet_id индекса не
-- имел: каждое изменение строки seq scan'ило таблицу аудита (245 строк на 27.10.2026 —
-- таблица растёт вместе с каждой правкой знания, поэтому цена растёт молча).
CREATE INDEX IF NOT EXISTS idx_audit_snippet ON snippet_audit_log (snippet_id, created_at DESC);

-- Нормализованная форма заголовка. Выражение повторено за normalize_title
-- (src/mcp_tools_api.py) и за предикатом шага 0 поиска: норма записи и норма поиска не
-- должны расходиться — расхождение дало бы «заголовок есть, а не находится». Колонка
-- generated именно поэтому: держать её актуальной кодом значит забыть один из путей.
-- Уникальный индекс закрепляет адрес карточки правил на уровне схемы; на момент добавления
-- дублей нормализованных адресов в базе 0 (замер 27.10.2026). varchar_pattern_ops — чтобы
-- тот же индекс обслуживал чтение поддеревьев адреса (`rules:core-rules:%`), которое иначе
-- стоит полным сканом.
ALTER TABLE knowledge_snippets ADD COLUMN IF NOT EXISTS question_norm text
    GENERATED ALWAYS AS (LOWER(BTRIM(REGEXP_REPLACE(question, '[[:space:]]+', ' ', 'g')))) STORED;
CREATE UNIQUE INDEX IF NOT EXISTS idx_snippets_question_norm
    ON knowledge_snippets (question_norm varchar_pattern_ops);

-- Карантин (узел Q1). Порождённый флаг is_marked здесь НЕ добавлен, хотя колонка была
-- написана и проверена: отрицание по тегам NOT (tags && ARRAY['mark-for-deletion']) ни один
-- запрос не фильтрует по всей таблице — оно применяется к множеству, уже отобранному GIN по
-- алиасам/полнотекстовому индексу или индексу parent_uuid (замер 27.10.2026: шаг 4 поиска
-- целиком 2.5 мс). Индекс по флагу остался бы мёртвым, а платил бы за каждую запись
-- сниппета; в контуре обогащения (config_snippets) та же колонка потребовала бы пару
-- «миграция + DDL-источник» ради того же неиспользуемого индекса. Узел вернётся вместе с
-- запросом, который фильтрует карантин по всей таблице.

