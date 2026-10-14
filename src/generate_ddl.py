#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация SQL DDL скрипта для внешних отчетов/обработок.

Источник истины по схеме внешнего отчёта: этот файл -> src/ddl_external_report.sql.
Порядок чистой установки ckb_1c_configurations (нормативный, зафиксирован 13.10.2026):
    1. CREATE DATABASE ckb_1c_configurations;
    2. psql -f src/ddl_external_report.sql      -- external_report, attributes,
                                                -- tabular_sections, forms, form_ext,
                                                -- templates + витрины анализа
    2b. psql -f src/ddl_enrichment.sql         -- config_* (шаг 1b, FK на шаг 1)
    3. psql -f create_1c_configurations_db.sql  -- configurations, config_extensions,
                                                -- external_processing, bsl_modules
Внешний отчёт создаётся раньше configurations, поэтому FK
external_report.configuration_id -> configurations(id) (узел V20) объявлен защищённым
блоком (DO + to_regclass) и в этом файле, и в create_1c_configurations_db.sql:constraint
создаёт тот шаг, который выполняется вторым. Оба блока идемпотентны.
Шаг 2 применим и после шага 3: external_report создаётся через IF NOT EXISTS.
Витрины v_form_elements / v_form_events входят в DDL намеренно: на них опираются
check_external_report_fill.sql / check_external_report_search.sql /
check_external_report_inventory.sql, без них проверка на чистой БД падает. Для уже
созданных БД есть аддитивная миграция migrate_v14_form_analysis_views.sql (тот же SQL,
CREATE OR REPLACE). Сверку обеспечивает _cmp_ddl.py — он сравнивает и колонки, и
определения витрин.
"""

sql_content = r"""-- ============================================================
-- Скрипт перестройки схемы для внешних отчетов/обработок 1С
-- Дата: 10.10.2026, обновлено 13.10.2026 (узел V14/V15: IF NOT EXISTS + витрины раздела 7),
-- 14.10.2026 (узел V20: configuration_id — заявленная оператором привязка к конфигурации;
-- узел V20.1 того же дня: FK снят, целостность проверяет инструмент, устаревание — при чтении)
-- База: ckb_1c_configurations
-- Источник истины: src/generate_ddl.py — правки вносить в него, этот файл перегенерируется.
-- external_report и его индекс создаются через IF NOT EXISTS, чтобы скрипт применялся
-- после create_1c_configurations_db.sql (тот создаёт external_report с теми же колонками).
-- ============================================================

-- 1. external_report — внешний отчет / внешняя обработка
CREATE TABLE IF NOT EXISTS external_report (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    containedobject_classid UUID DEFAULT 'e41aff26-25cf-4bb6-b6c1-3f478a75f374',
    containedobject_objectid UUID,
    generatedtype_name TEXT,
    generatedtype_category TEXT DEFAULT 'Object',
    generatedtype_typeid UUID,
    generatedtype_valueid UUID,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    default_form TEXT,
    auxiliary_form TEXT,
    main_data_composition_schema TEXT,
    default_settings_form TEXT,
    auxiliary_settings_form TEXT,
    default_variant_form TEXT,
    variants_storage TEXT,
    settings_storage TEXT,
    -- узел V20: строка заголовка конфигурации (configurations.id), к которой внешний объект
    -- ПРИВЯЗАН ОПЕРАТОРОМ. NULL = привязка НЕ заявлена: это не «подтверждено, что отчёт
    -- универсальный», а «мы об этом ничего не заявляли». Из выгрузки 1С значение не выводится
    -- (в XML нет ссылки на конфигурацию), при force=True загрузчик переносит прежнее значение.
    -- узел V20.1 (решение оператора 14.10.2026): FK ЗДЕСЬ НЕТ. Конфигурация — справочная
    -- система, которую ни загрузка, ни обогащение, ни карточка не читают для своей работы;
    -- блокировать удаление заголовка значит запретить вести справочник, а ошибка приходила бы
    -- сырым сообщением psycopg2, а не строкой с действием. Целостность обеспечивает инструмент
    -- set_object_configuration_tool (битый id отклоняется на записи), а устаревание ссылки
    -- обнаруживается при чтении: карточка объекта и сводка различают not_declared / bound /
    -- dangling и прямо требуют перепривязки. Тот же контракт, что у config_cross_references.
    -- local_doc_id (ссылка без FK, проверку делает инструмент). Индекс оставлен намеренно:
    -- перепривязка ищется обратным запросом «кто привязан к конфигурации N».
    configuration_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_external_report_uuid ON external_report(uuid);
CREATE INDEX IF NOT EXISTS idx_external_report_configuration_id ON external_report(configuration_id);

-- Узел V20.1: внешнего ключа external_report.configuration_id -> configurations(id) здесь НЕТ
-- (он добавлялся узлом V20 защищённым DO-блоком в двух местах и был снят по решению оператора).
-- Причина: конфигурация — справочная система, нужная только при проверке данных отчёта; FK
-- блокировал бы удаление заголовка, а ошибка приходила бы в момент записи через psql. Теперь
-- битый id отклоняет set_object_configuration_tool (enrichment-MCP), а ссылка, потерявшая
-- заголовок, обнаруживается при чтении — карточка объекта и сводка печатают «требуется
-- перепривязка». Индекс оставляем: по нему ищутся все объекты, привязанные к конфигурации.
-- Для уже созданных баз с FK — migrate_v21_drop_configuration_fk.sql.

-- 2. attributes — реквизиты объекта (универсальная)
CREATE TABLE attributes (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    type TEXT,
    format TEXT,
    editformat TEXT,
    tooltip TEXT,
    password_mode BOOLEAN DEFAULT FALSE,
    mark_negatives BOOLEAN DEFAULT FALSE,
    mask TEXT,
    multiline BOOLEAN DEFAULT FALSE,
    extended_edit BOOLEAN DEFAULT FALSE,
    min_value TEXT,
    max_value TEXT,
    fill_checking TEXT DEFAULT 'DontCheck',
    fill_from_filling_value BOOLEAN DEFAULT FALSE,
    fill_value TEXT,
    choice_folders_and_items TEXT,
    choice_parameter_links TEXT,
    choice_parameters TEXT,
    quick_choice TEXT DEFAULT 'Auto',
    create_on_input TEXT DEFAULT 'Auto',
    choice_form TEXT,
    link_by_type TEXT,
    choice_history_on_input TEXT DEFAULT 'Auto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_attributes_parent_uuid ON attributes(parent_uuid);
CREATE INDEX idx_attributes_name ON attributes(name);

-- 3. tabular_sections — табличные части
CREATE TABLE tabular_sections (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    internalinfo_generatedtype JSONB,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    tooltip TEXT,
    fill_checking TEXT DEFAULT 'DontCheck',
    standardattributes JSONB,
    column_uuids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tabular_sections_parent_uuid ON tabular_sections(parent_uuid);
CREATE INDEX idx_tabular_sections_name ON tabular_sections(name);

-- 4. forms — формы (V13: метка типа родителя, uuid уникален в пределах родителя)
CREATE TABLE forms (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    form_type TEXT DEFAULT 'Unmanaged',
    include_help_in_contents BOOLEAN DEFAULT FALSE,
    use_purposes JSONB,
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT forms_parent_uuid_uuid_key UNIQUE (parent_uuid, uuid)
);
CREATE INDEX idx_forms_parent_uuid ON forms(parent_uuid);
CREATE INDEX idx_forms_name ON forms(name);
CREATE INDEX idx_forms_uuid ON forms(uuid);
CREATE INDEX idx_forms_parent_type ON forms(parent_type);

-- 5. templates — макеты (V13: содержимое Templates/<Имя>/Ext/Template.xml|.bin)
CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    template_type TEXT DEFAULT 'TabularDocument',
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    ext TEXT,
    ext_bin BYTEA,
    ext_format TEXT,
    ext_size INTEGER,
    ext_path TEXT,
    ext_root_tag TEXT,
    ext_truncated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT templates_parent_uuid_uuid_key UNIQUE (parent_uuid, uuid)
);
CREATE INDEX idx_templates_parent_uuid ON templates(parent_uuid);
CREATE INDEX idx_templates_name ON templates(name);
CREATE INDEX idx_templates_uuid ON templates(uuid);
CREATE INDEX idx_templates_parent_type ON templates(parent_type);

-- 6. form_ext — содержимое формы (V13): одна строка на форму.
--    ext - текст модуля формы (Forms/<Имя>/Ext/Form/Module.bsl),
--    ext_bin - содержимое бинарной формы (Forms/<Имя>/Ext/Form.bin),
--    скалярные свойства Form.xml и его вложенные перечни (events/attributes/
--    commands/items/auto_command_bar) - jsonb.
CREATE TABLE form_ext (
    id SERIAL PRIMARY KEY,
    form_id INTEGER NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    form_uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    name TEXT,
    command_bar_location TEXT,
    report_result TEXT,
    details_data TEXT,
    report_form_type TEXT,
    auto_show_state TEXT,
    custom_settings_folder TEXT,
    report_result_view_mode TEXT,
    view_mode_application_on_set_report_result TEXT,
    auto_command_bar JSONB,
    events JSONB,
    attributes JSONB,
    commands JSONB,
    items JSONB,
    ext TEXT,
    ext_size INTEGER,
    ext_truncated BOOLEAN NOT NULL DEFAULT FALSE,
    ext_bin BYTEA,
    ext_format TEXT,
    ext_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX uq_form_ext_form_id ON form_ext(form_id);
CREATE INDEX idx_form_ext_form_uuid ON form_ext(form_uuid);
CREATE INDEX idx_form_ext_parent_uuid ON form_ext(parent_uuid);
CREATE INDEX idx_form_ext_name ON form_ext(name);

-- 7. Витрины анализа содержимого форм: v_form_elements, v_form_events (узел V14/V15).
--    Таблицы не меняются — используются уже существующие jsonb-колонки
--    form_ext.items / form_ext.events. Единая точка SQL-анализа и для Managed
--    (items разобраны из Form.xml, узел V13), и для Ordinary (items/events будут
--    разложены из Form.bin узлом V15). Ключи-синонимы различаются, поэтому витрина
--    нормализует их COALESCE-ом:
--      kind        <- Managed: item.kind;        Ordinary(V15): item.type
--      data_source <- Managed: item.datapath;    Ordinary(V15): item.data_source
--      caption_ru  <- Managed: item.title.ru;    Ordinary(V15): item.captions.ru
--      path/page   <- есть только у Ordinary(V15); у Managed иерархия в items не
--                     сохраняется (парсер раскрывает ChildItems в плоский список).
--    Тот же SQL повторяет аддитивная миграция migrate_v14_form_analysis_views.sql —
--    она нужна для уже созданных БД; источником истины остаётся этот файл.
CREATE OR REPLACE VIEW v_form_elements AS
SELECT e.id                                   AS report_id,
       e.name                                 AS report_name,
       e.uuid                                 AS report_uuid,
       f.name                                 AS form_name,
       f.uuid                                 AS form_uuid,
       f.form_type                            AS form_type,
       fe.ext_format                          AS ext_format,
       ord                                    AS ordinal,
       el ->> 'id'                            AS element_id,
       el ->> 'name'                          AS element_name,
       COALESCE(el ->> 'kind', el ->> 'type') AS element_kind,
       el ->> 'type'                          AS element_type,
       el ->> 'path'                          AS element_path,
       el ->> 'page'                          AS page_name,
       COALESCE(el ->> 'datapath', el ->> 'data_source') AS data_source,
       COALESCE(el -> 'title' ->> 'ru', el -> 'captions' ->> 'ru')  AS caption_ru,
       COALESCE(el -> 'tooltip' ->> 'ru')     AS tooltip_ru,
       el ->> 'command_name'                  AS command_name,
       el                                     AS raw
FROM form_ext fe
JOIN forms f            ON f.id = fe.form_id
JOIN external_report e  ON e.uuid = fe.parent_uuid
CROSS JOIN LATERAL jsonb_array_elements(fe.items) WITH ORDINALITY AS item(el, ord)
WHERE jsonb_typeof(fe.items) = 'array';

CREATE OR REPLACE VIEW v_form_events AS
SELECT e.id                        AS report_id,
       e.name                      AS report_name,
       e.uuid                      AS report_uuid,
       f.name                      AS form_name,
       f.uuid                      AS form_uuid,
       f.form_type                 AS form_type,
       fe.ext_format               AS ext_format,
       ord                         AS ordinal,
       ev ->> 'event'              AS event_name,
       ev ->> 'handler'            AS handler_name,
       COALESCE(ev -> 'representation' ->> 'ru') AS event_caption_ru,
       ev                          AS raw
FROM form_ext fe
JOIN forms f            ON f.id = fe.form_id
JOIN external_report e  ON e.uuid = fe.parent_uuid
CROSS JOIN LATERAL jsonb_array_elements(fe.events) WITH ORDINALITY AS ev_row(ev, ord)
WHERE jsonb_typeof(fe.events) = 'array';

SELECT 'Схема успешно создана!' AS status;
"""

with open(r"C:\1C_LLM\ckb\src\ddl_external_report.sql", "w", encoding="utf-8") as f:
    f.write(sql_content)

print("SQL файл создан: C:\\1C_LLM\\ckb\\src\\ddl_external_report.sql")

# ---------------------------------------------------------------------------
# Шаг 1b установки: обогащение (алиасы и сниппеты), узел V17.
# Источник истины остаётся этот файл; выход - src/ddl_enrichment.sql.
# Порядок установки: шаг 1 (ddl_external_report.sql) -> шаг 1b (ddl_enrichment.sql)
# -> шаг 2 (create_1c_configurations_db.sql). Для уже созданных БД есть аддитивная
# миграция migrate_v17_enrichment.sql (тот же SQL). Сверка - _cmp_ddl.py, он обязан
# применять все три шага.
# ---------------------------------------------------------------------------
ENRICHMENT_PARTS = []

ENRICHMENT_PARTS.append(r"""-- ============================================================
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
""")

ENRICHMENT_PARTS.append(r"""
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
-- Вторая граница — по стабильному ключу цели. uq_config_snippet_deps различает написания
-- ('Форма.Элемент' и 'Элемент' — разные target_name), а это одна и та же цель: у неё один
-- target_uuid. Код сворачивает такие дубли до вставки (src/enrichment_snippets.py,
-- ключ target_type + target_uuid или нормализованный target_name), индекс не даёт
-- пропущенному дублю лечь в БД. Частичный — потому что target_uuid может быть NULL
-- (цель не найдена в сохранённом содержимом), а NULL в уникальном индексе не считается.
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
""")


with open(r"C:\1C_LLM\ckb\src\ddl_enrichment.sql", "w", encoding="utf-8") as f:
    f.write("".join(ENRICHMENT_PARTS))

print("SQL файл создан: C:\\1C_LLM\\ckb\\src\\ddl_enrichment.sql")
