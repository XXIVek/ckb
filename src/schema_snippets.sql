-- =====================================================
-- Таблица сниппетов конфигураций (analog knowledge_snippets)
-- =====================================================
CREATE TABLE IF NOT EXISTS config_snippets (
    id SERIAL PRIMARY KEY,
    config_id INTEGER REFERENCES configuration(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    tags JSONB DEFAULT '["bsl", "config"]'::jsonb,
    confidence DECIMAL(3,2) DEFAULT 0.90,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_config_snippets_config_id ON config_snippets(config_id);
CREATE INDEX IF NOT EXISTS idx_config_snippets_tags ON config_snippets USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_config_snippets_question_fts ON config_snippets USING GIN(to_tsvector('russian', question));

-- =====================================================
-- Таблица зависимостей сниппетов (analog cross_references)
-- =====================================================
CREATE TABLE IF NOT EXISTS config_snippet_dependencies (
    id SERIAL PRIMARY KEY,
    snippet_id INTEGER REFERENCES config_snippets(id) ON DELETE CASCADE,
    dependency_type TEXT NOT NULL DEFAULT 'depends_on',
    target_type TEXT NOT NULL,
    target_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_config_snippet_deps_snippet_id ON config_snippet_dependencies(snippet_id);
CREATE INDEX IF NOT EXISTS idx_config_snippet_deps_target ON config_snippet_dependencies(target_type, target_name);

-- =====================================================
-- Таблица логов экспорта (для обратной выгрузки)
-- =====================================================
CREATE TABLE IF NOT EXISTS config_export_log (
    id SERIAL PRIMARY KEY,
    config_id INTEGER REFERENCES configuration(id) ON DELETE CASCADE,
    target_path TEXT NOT NULL,
    objects_count INTEGER DEFAULT 0,
    changes_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    exported_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_config_export_log_config_id ON config_export_log(config_id);
CREATE INDEX IF NOT EXISTS idx_config_export_log_status ON config_export_log(status);
