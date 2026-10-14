-- Аддитивная миграция V17 для УЖЕ СОЗДАННЫХ баз ckb_1c_configurations.
-- Тот же SQL, что и шаг 1b установки (src/ddl_enrichment.sql, источник истины - src/generate_ddl.py).
-- Всё через IF NOT EXISTS / CREATE OR REPLACE: применять можно повторно, данные не теряются.
-- ============================================================
-- Шаг 1b установки ckb_1c_configurations: обогащение (узел V17)
-- Дата: 13.10.2026
-- Источник истины: src/generate_ddl.py — файл перегенерируется.
-- Применяется ПОСЛЕ src/ddl_external_report.sql (шаг 1) и ДО
-- create_1c_configurations_db.sql (шаг 2); для уже созданных БД — аддитивная
-- миграция migrate_v17_enrichment.sql (тот же SQL).
--
-- Смысл: алиасы и сниппеты по уже сохранённому содержимому внешнего объекта
-- (решения E1..E6 в docs/CONFIGURATIONS_ENRICHMENT_PLAN.md).
-- Связь с объектом полиморфная: parent_uuid + parent_type, FK нет (E3),
-- очистка явная DELETE ... WHERE parent_uuid = ... (её делает delete_external_object).
-- target_uuid — text: целью может быть uuid строки другой таблицы, id элемента из
-- form_ext.items[].id или ссылка на строку config_snippets (target_snippet_id).
-- target_key — служебный ключ цели для уникальности алиаса; он вычисляемый,
-- в INSERT не участвует.
-- ============================================================

-- 1. config_aliases — алиасы поиска по объектам выгрузки
--    (аналог alias_targets в local_doc, но цель адресуется uuid, а не groups_id).
--    origin: 'generated' — снимается и пишется заново при перегенерации;
--            'manual'    — добавлен оператором через MCP, при перегенерации сохраняется.
CREATE TABLE IF NOT EXISTS config_aliases (
    id BIGSERIAL PRIMARY KEY,
    alias_name text NOT NULL,
    alias_norm text NOT NULL,
    target_type text NOT NULL,
    target_name text,
    target_uuid text,
    target_snippet_id bigint,
    target_key text GENERATED ALWAYS AS (
        COALESCE(target_uuid,
                 CASE WHEN target_snippet_id IS NULL THEN NULL
                      ELSE 'snippet:' || target_snippet_id END)
    ) STORED,
    parent_uuid uuid NOT NULL,
    parent_type text,
    weight real NOT NULL DEFAULT 1.0,
    description text,
    origin text NOT NULL DEFAULT 'generated',
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_aliases_alias_target
    ON config_aliases (alias_norm, target_key) WHERE active;
CREATE INDEX IF NOT EXISTS idx_config_aliases_norm ON config_aliases (alias_norm);
CREATE INDEX IF NOT EXISTS idx_config_aliases_parent ON config_aliases (parent_uuid);
CREATE INDEX IF NOT EXISTS idx_config_aliases_target ON config_aliases (target_key);

-- 2. config_snippets — автоматически извлечённые фрагменты кода объекта.
--    tsv вычисляется из question + answer (конфигурация simple: идентификаторы 1С
--    не склоняются), ручного заполнения нет. Порог отбора объявлений задаёт
--    src/enrichment_generator.py (MIN_BODY_LINES), а не схема.
CREATE TABLE IF NOT EXISTS config_snippets (
    id BIGSERIAL PRIMARY KEY,
    parent_uuid uuid NOT NULL,
    parent_type text,
    question text NOT NULL,
    answer text NOT NULL,
    source_kind text NOT NULL,
    source_uuid text,
    source_path text,
    target_type text,
    target_uuid text,
    tags text[] NOT NULL DEFAULT '{}',
    confidence real NOT NULL DEFAULT 0.85,
    is_verified boolean NOT NULL DEFAULT false,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', question || ' ' || answer)) STORED,
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_snippets_object_source
    ON config_snippets (parent_uuid, source_kind, COALESCE(source_uuid, ''), question);
CREATE INDEX IF NOT EXISTS idx_config_snippets_parent ON config_snippets (parent_uuid);
CREATE INDEX IF NOT EXISTS idx_config_snippets_tsv ON config_snippets USING GIN (tsv);

-- 3. config_snippet_dependencies — связи сниппета с объектами выгрузки.
--    Единственный FK в подсистеме: зависимость живёт вместе со сниппетом
--    (ON DELETE CASCADE), остальные связи полиморфные.
CREATE TABLE IF NOT EXISTS config_snippet_dependencies (
    id BIGSERIAL PRIMARY KEY,
    snippet_id bigint NOT NULL REFERENCES config_snippets(id) ON DELETE CASCADE,
    dependency_type text NOT NULL,
    target_type text NOT NULL,
    target_name text NOT NULL,
    target_uuid text,
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_snippet_deps
    ON config_snippet_dependencies (snippet_id, dependency_type, target_type, target_name);
-- Та же вторая граница, что и в src/ddl_enrichment.sql (шаг 1b): одна цель в двух
-- написаниях даёт разные target_name, но один target_uuid. Для уже созданных БД индекс
-- добавляется этой же миграцией (она идемпотентна), порядок — после создания таблицы.
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_snippet_deps_stable_target
    ON config_snippet_dependencies (snippet_id, target_type, target_uuid)
    WHERE target_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_config_snippet_deps_snippet
    ON config_snippet_dependencies (snippet_id);

-- 4. config_cross_references — указатели на documentation local_doc.
--    local_doc_id — bigint БЕЗ FK: это ссылка в другую базу (FDW/dblink нет).
--    Целостность проверяет генератор и отдельный psql-запрос к local_doc, не схема.
CREATE TABLE IF NOT EXISTS config_cross_references (
    id BIGSERIAL PRIMARY KEY,
    local_doc_kind text NOT NULL,
    local_doc_id bigint NOT NULL,
    target_type text NOT NULL,
    target_name text,
    target_uuid text,
    parent_uuid uuid NOT NULL,
    reference_type text NOT NULL DEFAULT 'linked_to',
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_cross_refs
    ON config_cross_references (local_doc_kind, local_doc_id, target_type, COALESCE(target_uuid, ''));
CREATE INDEX IF NOT EXISTS idx_config_cross_refs_parent ON config_cross_references (parent_uuid);

-- 5. Витрины анализа обогащения. v_config_enrichment — счётчики по объекту
--    (раздел 15 check_external_report_inventory.sql, validate_enrichment.py);
--    v_config_alias_targets — алиас вместе с его целью (varianty POISK
--    check_external_report_search.sql), неактивные алиасы скрыты.
CREATE OR REPLACE VIEW v_config_enrichment AS
SELECT e.id AS report_id,
       e.name AS report_name,
       e.uuid AS report_uuid,
       (SELECT count(*) FROM config_aliases a
         WHERE a.parent_uuid = e.uuid) AS aliases_total,
       (SELECT count(*) FROM config_aliases a
         WHERE a.parent_uuid = e.uuid AND a.origin = 'manual') AS aliases_manual,
       (SELECT count(*) FROM config_aliases a
         WHERE a.parent_uuid = e.uuid AND a.target_type = 'ConfigSnippet') AS aliases_snippet,
       (SELECT count(*) FROM config_snippets s
         WHERE s.parent_uuid = e.uuid) AS snippets,
       (SELECT count(*) FROM config_snippet_dependencies d
          JOIN config_snippets s ON s.id = d.snippet_id
         WHERE s.parent_uuid = e.uuid) AS snippet_dependencies,
       (SELECT count(*) FROM config_cross_references x
         WHERE x.parent_uuid = e.uuid) AS doc_links
FROM external_report e;

CREATE OR REPLACE VIEW v_config_alias_targets AS
SELECT a.id,
       a.alias_name,
       a.alias_norm,
       a.target_type,
       a.target_name,
       a.target_uuid,
       a.target_snippet_id,
       a.parent_uuid,
       a.parent_type,
       a.weight,
       a.origin,
       a.description,
       s.question AS snippet_question,
       s.source_kind AS snippet_source_kind
FROM config_aliases a
LEFT JOIN config_snippets s ON s.id = a.target_snippet_id
WHERE a.active;

SELECT 'Схема обогащения (шаг 1b) успешно создана!' AS status;

