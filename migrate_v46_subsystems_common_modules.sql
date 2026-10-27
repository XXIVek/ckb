-- migrate_v46_subsystems_common_modules.sql
-- ============================================================================
-- Узел V46, шаг П1: признак коммита во всех версионных таблицах + таблицы
--       свойств подсистем и общих модулей конфигурации.
-- Норматив: docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md (раздел 2 — замеры,
--           раздел 3 — решение A1, раздел 4 — модель и решения D1…D11).
-- Дата: 2026-10-31.
--
-- Миграция аддитивна: ни одна колонка не снимается, ни одна строка не удаляется,
-- повторный прогон ничего не меняет. Итоговое состояние совпадает с чистой
-- установкой: шаги 1 и 1b — src/generate_ddl.py (порождает src/ddl_external_report.sql
-- и src/ddl_enrichment.sql), шаг 2 — create_1c_configurations_db.sql. Сверка —
-- tools/_cmp_ddl.py.
--
-- 1. Признак коммита (решение D11) добавляется во ВСЕ версионные таблицы — семь
--    существующих и четыре новых. Флаг NOT NULL DEFAULT FALSE: загрузчик заявляет
--    FALSE, TRUE ставит событие коммита. Таблицы `configurations` (заголовок) и
--    `configuration_objects` (индекс состава) флага не получают — они не являются
--    версионными цепочками: ложный флаг на строке индекса составил бы знание о
--    коммите там, где его никто не заявлял.
--
-- 2. Флаг НЕ участвует в отборе текущей ревизии (решение A1, раздел 3): текущей
--    остаётся максимальная revision_no по ключу цепочки. Поэтому определения витрин
--    меняются только в списке столбцов — предикат остаётся прежним.
--
-- 3. Колонка в определениях витрин ставится в КОНЕЦ списка столбцов: CREATE OR REPLACE
--    VIEW разрешает добавлять столбцы только в конец (прецедент migrate_v22_object_kind.sql,
--    строки 61–64). Иначе пришлось бы делать DROP VIEW, а над v_current_external_report
--    построен v_current_object_manifest — снятие базовой витрины потянуло бы за собой
--    манифест. Сам манифест флага не получает: он отвечает за состав детей, а не за
--    состояние строк (решение A1).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Признак коммита в существующих версионных таблицах
-- ---------------------------------------------------------------------------
ALTER TABLE external_report
    ADD COLUMN IF NOT EXISTS is_committed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE attributes
    ADD COLUMN IF NOT EXISTS is_committed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tabular_sections
    ADD COLUMN IF NOT EXISTS is_committed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS is_committed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE form_ext
    ADD COLUMN IF NOT EXISTS is_committed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE templates
    ADD COLUMN IF NOT EXISTS is_committed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE bsl_modules
    ADD COLUMN IF NOT EXISTS is_committed BOOLEAN NOT NULL DEFAULT FALSE;

-- ---------------------------------------------------------------------------
-- 2. Те же витрины текущего состояния — со столбцом флага в конце списка.
--    Предикат (максимальная revision_no по ключу цепочки) не меняется: он и после
--    узла V46 остаётся единственным правилом выбора текущей строки.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_external_report AS
SELECT er.id,
       er.uuid, er.containedobject_classid, er.containedobject_objectid, er.generatedtype_name,
       er.generatedtype_category, er.generatedtype_typeid, er.generatedtype_valueid, er.name,
       er.synonym, er.comment, er.default_form, er.auxiliary_form,
       er.main_data_composition_schema, er.default_settings_form, er.auxiliary_settings_form, er.default_variant_form,
       er.variants_storage, er.settings_storage, er.created_at, er.updated_at,
       er.configuration_id, er.object_kind, er.origin_kind, er.origin_path,
       er.origin_sha256, er.origin_manifest, er.origin_recorded_at, er.children_manifest,
       er.revision_no, er.changed_at, er.changed_by, er.is_committed
FROM external_report er
WHERE NOT EXISTS (SELECT 1
                  FROM external_report h
                  WHERE h.uuid = er.uuid
                    AND h.revision_no > er.revision_no);

CREATE OR REPLACE VIEW v_current_attributes AS
SELECT a.id,
       a.uuid, a.parent_uuid, a.name, a.synonym,
       a.comment, a.type, a.format, a.editformat,
       a.tooltip, a.password_mode, a.mark_negatives, a.mask,
       a.multiline, a.extended_edit, a.min_value, a.max_value,
       a.fill_checking, a.fill_from_filling_value, a.fill_value, a.choice_folders_and_items,
       a.choice_parameter_links, a.choice_parameters, a.quick_choice, a.create_on_input,
       a.choice_form, a.link_by_type, a.choice_history_on_input, a.created_at,
       a.revision_no, a.changed_at, a.changed_by, a.is_committed
FROM attributes a
WHERE NOT EXISTS (SELECT 1
                  FROM attributes h
                  WHERE h.uuid = a.uuid
                    AND h.revision_no > a.revision_no);

CREATE OR REPLACE VIEW v_current_tabular_sections AS
SELECT ts.id,
       ts.uuid, ts.parent_uuid, ts.internalinfo_generatedtype, ts.name,
       ts.synonym, ts.comment, ts.tooltip, ts.fill_checking,
       ts.standardattributes, ts.column_uuids, ts.created_at, ts.revision_no,
       ts.changed_at, ts.changed_by, ts.is_committed
FROM tabular_sections ts
WHERE NOT EXISTS (SELECT 1
                  FROM tabular_sections h
                  WHERE h.uuid = ts.uuid
                    AND h.revision_no > ts.revision_no);

CREATE OR REPLACE VIEW v_current_forms AS
SELECT f.id,
       f.uuid, f.parent_uuid, f.name, f.synonym,
       f.comment, f.form_type, f.include_help_in_contents, f.use_purposes,
       f.created_at, f.parent_type, f.revision_no, f.changed_at,
       f.changed_by, f.is_committed
FROM forms f
WHERE NOT EXISTS (SELECT 1
                  FROM forms h
                  WHERE h.uuid = f.uuid
                    AND h.revision_no > f.revision_no);

CREATE OR REPLACE VIEW v_current_form_ext AS
SELECT fe.id,
       fe.form_id, fe.form_uuid, fe.parent_uuid, fe.parent_type,
       fe.name, fe.command_bar_location, fe.report_result, fe.details_data,
       fe.report_form_type, fe.auto_show_state, fe.custom_settings_folder, fe.report_result_view_mode,
       fe.view_mode_application_on_set_report_result, fe.auto_command_bar, fe.events, fe.attributes,
       fe.commands, fe.items, fe.ext, fe.ext_size,
       fe.ext_truncated, fe.ext_bin, fe.ext_format, fe.ext_path,
       fe.created_at, fe.revision_no, fe.changed_at, fe.changed_by, fe.is_committed
FROM form_ext fe
JOIN forms f ON f.id = fe.form_id
             AND f.revision_no = fe.revision_no
WHERE NOT EXISTS (SELECT 1
                  FROM forms h
                  WHERE h.uuid = f.uuid
                    AND h.revision_no > f.revision_no);

CREATE OR REPLACE VIEW v_current_templates AS
SELECT t.id,
       t.uuid, t.parent_uuid, t.name, t.synonym,
       t.comment, t.template_type, t.created_at, t.parent_type,
       t.ext, t.ext_bin, t.ext_format, t.ext_size,
       t.ext_path, t.ext_root_tag, t.ext_truncated, t.revision_no,
       t.changed_at, t.changed_by, t.is_committed
FROM templates t
WHERE NOT EXISTS (SELECT 1
                  FROM templates h
                  WHERE h.uuid = t.uuid
                    AND h.revision_no > t.revision_no);

-- Модули: цепочка состояний идентифицируется путём внутри выгрузки (у модуля uuid нет), а
-- строки конфигурации (parent_uuid IS NULL) историей не живут — отдаются как есть. Предикат
-- не меняется; меняется только список столбцов.
CREATE OR REPLACE VIEW v_current_bsl_modules AS
SELECT m.id,
       m.configuration_id, m.module_name, m.file_path, m.code,
       m.object_type, m.object_name, m.report_id, m.created_at,
       m.parent_uuid, m.parent_type, m.module_type, m.code_size,
       m.truncated, m.revision_no, m.changed_at, m.changed_by, m.is_committed
FROM bsl_modules m
WHERE m.parent_uuid IS NULL
   OR NOT EXISTS (
        SELECT 1 FROM bsl_modules n
        WHERE n.parent_uuid = m.parent_uuid
          AND n.file_path = m.file_path
          AND n.revision_no > m.revision_no
   );

-- ---------------------------------------------------------------------------
-- 3. Новые таблицы (модель — раздел 4 плана, решения D1, D2, D3, D8, D9, D10, D11).
--    Внешних ключей нет осознанно (прецедент V20.1): FK на заголовок конфигурации
--    блокировал бы её пересоздание, а ссылка на объект метаданных читается индексом
--    состава, а не ключом.
--    Ключ цепочки состояния — (configuration_uuid, full_name, revision_no): full_name
--    является естественным ключом объекта (замер 2.3), object_name ключом быть не может
--    (D8: одноимённые объекты в разных группа). Глубина tree_depth считается от 1
--    (замер 2.2: 1…5), а не от 0, как depth индекса состава.
--    Состояние объявления (declaration_state) CHECK не получает: словарь задаёт разбор
--    (шаг П3, единый источник в коде разбора); повторять его в схеме — значит разъезжать
--    с кодом (прецедент 48 имён перечней до узла V43).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subsystems (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    parent_object_uuid UUID,
    full_name TEXT NOT NULL,
    parent_full_name TEXT,
    object_name TEXT NOT NULL,
    tree_depth SMALLINT NOT NULL,
    ordinal INTEGER NOT NULL DEFAULT 0,
    parent_source TEXT NOT NULL DEFAULT 'layout',
    declaration_state TEXT,
    comment TEXT,
    synonym JSONB,
    explanation TEXT,
    include_help_in_contents BOOLEAN,
    include_in_command_interface BOOLEAN,
    use_one_command BOOLEAN,
    content JSONB,
    content_unresolved JSONB,
    picture JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT subsystems_tree_depth_range CHECK (tree_depth BETWEEN 1 AND 5),
    CONSTRAINT subsystems_parent_source_known
        CHECK (parent_source IN ('layout', 'declared', 'index_name')),
    CONSTRAINT subsystems_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT subsystems_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT subsystems_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);

-- Ссылки включения Content (D3): исходный порядок держит jsonb-колонка родителя, здесь —
-- разрешённые ссылки. Ревизия строки относится к состоянию подсистемы, а не живёт своей
-- цепочкой — тот же порядок, что у form_ext (uq_form_ext_form_id_revision). Неразрешённая
-- ссылка остаётся строкой с resolved=FALSE и пустыми целевыми колонками: «ссылки нет» и
-- «ссылка есть, но цель не найдена» различимы.
CREATE TABLE IF NOT EXISTS subsystem_content (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    subsystem_object_uuid UUID NOT NULL,
    subsystem_full_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    ref_text TEXT NOT NULL,
    ref_form TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    target_object_type TEXT,
    target_object_uuid UUID,
    target_full_name TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT subsystem_content_ref_form_known
        CHECK (ref_form IN ('qualified_name', 'uuid')),
    CONSTRAINT subsystem_content_object_revision_ordinal_key
        UNIQUE (subsystem_object_uuid, revision_no, ordinal),
    CONSTRAINT subsystem_content_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT subsystem_content_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT subsystem_content_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);

-- Свойства общего модуля (D1, D6): набор свойств замкнут замером 2.5 — ровно 11 свойств
-- CommonModule, других ни в одной из трёх выгрузок нет. Словарь return_values_reuse снят
-- тем же замером (_v46e_cm_values_probe.py), а не взят из справочника по памяти. Текста
-- модуля здесь нет (D6, замер 2.6): 188 МБ на BGU2 и 294 МБ на BP3 — содержимое загружает
-- отдельная процедура, а не строка свойства.
CREATE TABLE IF NOT EXISTS common_modules (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    full_name TEXT NOT NULL,
    object_name TEXT NOT NULL,
    comment TEXT,
    synonym JSONB,
    global BOOLEAN,
    privileged BOOLEAN,
    server BOOLEAN,
    server_call BOOLEAN,
    external_connection BOOLEAN,
    client_managed_application BOOLEAN,
    client_ordinary_application BOOLEAN,
    return_values_reuse TEXT,
    declaration_state TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT common_modules_return_values_reuse_known
        CHECK (return_values_reuse IS NULL
               OR return_values_reuse IN ('DontUse', 'DuringSession', 'DuringRequest')),
    CONSTRAINT common_modules_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT common_modules_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT common_modules_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);

-- Дескриптор модуля общего модуля: путь относительно корня выгрузки вместо текста.
-- Состояние называет отсутствие содержательного состояния, а не молчит о нём (D9):
-- 'file' — текст есть и он будет загружен, 'bin_only' — есть только Module.bin,
-- 'indexed_no_file' — запись индекса состава без файла, 'file_not_in_index' — файл без
-- записи индекса. Слот вида один ('Module', словарь V40): слоты предопределённых программ
-- корня живут таблицами узла V44 и здесь не дублируются.
CREATE TABLE IF NOT EXISTS common_module_sources (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    module_name TEXT NOT NULL,
    module_type TEXT NOT NULL DEFAULT 'Module',
    file_path TEXT,
    file_size BIGINT,
    content_state TEXT NOT NULL,
    content_loaded BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT common_module_sources_module_type_check CHECK (module_type = 'Module'),
    CONSTRAINT common_module_sources_content_state_check
        CHECK (content_state IN ('file', 'bin_only', 'indexed_no_file', 'file_not_in_index')),
    CONSTRAINT common_module_sources_path_state_check
        CHECK (file_path IS NULL OR content_state = 'file'),
    CONSTRAINT common_module_sources_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT common_module_sources_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT common_module_sources_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT common_module_sources_configuration_object_module_revision_key
        UNIQUE (configuration_uuid, object_uuid, module_type, revision_no)
);

-- ---------------------------------------------------------------------------
-- 4. Индексы новых таблиц. Отдельного индекса по configuration_uuid у subsystems и
--    common_modules нет: его обслуживает уникальный индекс цепочки состояния с той же
--    ведущей колонкой (тот же порядок, что у bsl_modules_* узла V44). У subsystem_content
--    ведущая колонка уникального индекса — object подсистемы, поэтому индекс по
--    конфигурации нужен отдельно.
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_subsystems_configuration_full_name_revision
    ON subsystems(configuration_uuid, full_name, revision_no);
CREATE INDEX IF NOT EXISTS idx_subsystems_object_uuid_revision
    ON subsystems(object_uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_subsystems_full_name
    ON subsystems(full_name);
CREATE INDEX IF NOT EXISTS idx_subsystems_parent_object_uuid
    ON subsystems(parent_object_uuid) WHERE parent_object_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_subsystems_configuration_parent
    ON subsystems(configuration_uuid, parent_full_name);

CREATE INDEX IF NOT EXISTS idx_subsystem_content_configuration_uuid
    ON subsystem_content(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_subsystem_content_full_name
    ON subsystem_content(subsystem_full_name);
CREATE INDEX IF NOT EXISTS idx_subsystem_content_target_uuid
    ON subsystem_content(target_object_uuid) WHERE target_object_uuid IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_common_modules_configuration_full_name_revision
    ON common_modules(configuration_uuid, full_name, revision_no);
CREATE INDEX IF NOT EXISTS idx_common_modules_object_uuid_revision
    ON common_modules(object_uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_common_modules_full_name
    ON common_modules(full_name);

CREATE INDEX IF NOT EXISTS idx_common_module_sources_configuration_uuid
    ON common_module_sources(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_common_module_sources_object_uuid
    ON common_module_sources(object_uuid);

-- ---------------------------------------------------------------------------
-- 5. Витрины текущего состояния новых таблиц. Ключ цепочки — (configuration_uuid,
--    full_name): full_name является естественным ключом объекта (замер 2.3), цепочка
--    ведётся по имени, а не по object_uuid — пересоздание объекта с новым UUID продолжает
--    ту же цепочку, а не начинает новую (решение D8). Признак коммита в выдаче лежит, но
--    на круг строк не влияет: текущей остаётся максимальная ревизия независимо от флага
--    (решение A1).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_subsystems AS
SELECT s.id,
       s.configuration_uuid, s.object_uuid, s.parent_object_uuid,
       s.full_name, s.parent_full_name, s.object_name, s.tree_depth, s.ordinal,
       s.parent_source, s.declaration_state, s.comment, s.synonym, s.explanation,
       s.include_help_in_contents, s.include_in_command_interface, s.use_one_command,
       s.content, s.content_unresolved, s.picture, s.created_at,
       s.revision_no, s.changed_at, s.changed_by, s.is_committed
FROM subsystems s
WHERE NOT EXISTS (SELECT 1 FROM subsystems h
                  WHERE h.configuration_uuid = s.configuration_uuid
                    AND h.full_name = s.full_name
                    AND h.revision_no > s.revision_no);

-- Ссылки включения текущей ревизии подсистемы — по образцу v_current_form_ext: строки
-- относятся к той ревизии родителя, которая признана текущей.
CREATE OR REPLACE VIEW v_current_subsystem_content AS
SELECT sc.id,
       sc.configuration_uuid, sc.subsystem_object_uuid, sc.subsystem_full_name,
       sc.ordinal, sc.ref_text, sc.ref_form, sc.resolved,
       sc.target_object_type, sc.target_object_uuid, sc.target_full_name,
       sc.created_at,
       sc.revision_no, sc.changed_at, sc.changed_by, sc.is_committed
FROM subsystem_content sc
WHERE EXISTS (SELECT 1 FROM v_current_subsystems cs
              WHERE cs.configuration_uuid = sc.configuration_uuid
                AND cs.object_uuid = sc.subsystem_object_uuid
                AND cs.revision_no = sc.revision_no);

CREATE OR REPLACE VIEW v_current_common_modules AS
SELECT cm.id,
       cm.configuration_uuid, cm.object_uuid, cm.full_name, cm.object_name,
       cm.comment, cm.synonym, cm.global, cm.privileged, cm.server, cm.server_call,
       cm.external_connection, cm.client_managed_application,
       cm.client_ordinary_application, cm.return_values_reuse, cm.declaration_state,
       cm.created_at, cm.revision_no, cm.changed_at, cm.changed_by, cm.is_committed
FROM common_modules cm
WHERE NOT EXISTS (SELECT 1 FROM common_modules h
                  WHERE h.configuration_uuid = cm.configuration_uuid
                    AND h.full_name = cm.full_name
                    AND h.revision_no > cm.revision_no);

-- Дескрипторы модулей текущей ревизии общего модуля. Текста ни в одной строке нет (D6):
-- витрина перечисляет состояние и путь, содержимое читает отдельная процедура.
CREATE OR REPLACE VIEW v_current_common_module_sources AS
SELECT cs.id,
       cs.configuration_uuid, cs.object_uuid, cs.module_name, cs.module_type,
       cs.file_path, cs.file_size, cs.content_state, cs.content_loaded, cs.created_at,
       cs.revision_no, cs.changed_at, cs.changed_by, cs.is_committed
FROM common_module_sources cs
WHERE NOT EXISTS (SELECT 1 FROM common_module_sources h
                  WHERE h.configuration_uuid = cs.configuration_uuid
                    AND h.object_uuid = cs.object_uuid
                    AND h.module_type = cs.module_type
                    AND h.revision_no > cs.revision_no);

-- ---------------------------------------------------------------------------
-- 6. Проверка после применения.
-- ---------------------------------------------------------------------------
-- 6.1. Признак коммита есть во всех версионных таблицах — 11 таблиц (7 существующих и
--      4 новых); у заголовка конфигурации и индекса состава его нет (D11).
-- SELECT c.table_name
-- FROM information_schema.columns c
-- WHERE c.table_schema='public' AND c.column_name='is_committed'
-- ORDER BY c.table_name;                              -- ожидаем 11 строк
--
-- 6.2. Витрины отдают флаг и не меняют круг текущих строк: число строк витрины до и
--      после миграции одинаково (предикат не менялся).
-- SELECT count(*) FROM v_current_external_report;     -- совпадает с замером до миграции
--
-- 6.3. Новые таблицы пусты, но доступны для чтения витринами.
-- SELECT count(*) FROM v_current_subsystems;          -- 0
-- SELECT count(*) FROM v_current_common_modules;      -- 0
--
-- 6.4. Итоговая схема совпадает с чистой установкой: python tools/_cmp_ddl.py (rc=0).
--      Состав витрин и таблиц слоя проверяют python _layer_tree_check.py и
--      python tools/check_v19_revisions.py.
-- ============================================================================