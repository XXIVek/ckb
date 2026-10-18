-- =====================================================================
-- migrate_v19_revisions.sql — узел V19, этап 1 (схема): версионность состояний
-- =====================================================================
-- Аддитивная миграция для УЖЕ созданных баз ckb_1c_configurations. Источник истины —
-- src/generate_ddl.py (шаг 1) и create_1c_configurations_db.sql (шаг 2); этот файл приводит
-- живую базу к той же схеме, что даёт чистая установка. Сверка — python _cmp_ddl.py.
--
-- Модель (M1–M8, docs/CONFIGURATIONS_ENRICHMENT_PLAN.md, раздел 11):
--   M1  одна строка = одно состояние объекта; цепочка строк на один uuid даёт историю;
--   M2  первая загрузка = ревизия 1 (revision_no NOT NULL DEFAULT 1);
--   M3  снятие ребёнка выражается новой ревизией родителя БЕЗ этого uuid в манифесте,
--       колонки состояния у детей при этом нет (A1);
--   M4  манифест состава детей — jsonb на строке родителя (только external_report: он и есть
--       владелец детей; у tabular_sections состав колонок уже лежит в column_uuids, у form_ext
--       состав элементов — в items);
--   M5  «текущее» состояние — максимальный revision_no в цепочке; разрешается через витрины
--       v_current_* (единственная точка доступа для кода и витрин анализа);
--   M6  внешние ключи parent_uuid -> external_report(uuid) сняты: при двух ревизиях uuid
--       родителя не уникален, каскад делают явными DELETE (src/external_report_loader.py:
--       pre_v19_table_names / cascade_delete_pre_v19_children);
--   M7  явная загрузка каталога (force=True) историю сбрасывает: цепочки снимаются,
--       загруженный каталог становится ревизией 1;
--   M8  событие изменения — changed_at (момент) + changed_by ('load' | 'edit' | 'restore');
--       оба NULL означают «событие не записано» (снимок до V19).
--
-- Порядок шагов:
--   0. снять витрины анализа: они будут читать v_current_*, а v_current_* появятся ниже;
--   1. колонки состояния (revision_no / changed_at / changed_by) и манифест состава детей;
--   2. снятие ограничений, которые при двух ревизиях становятся ложными (UNIQUE по uuid,
--      UNIQUE (parent_uuid, uuid), внешние ключи parent_uuid -> external_report(uuid),
--      уникальные индексы детей без revision_no);
--   3. граница состояния (uuid, revision_no) + инварианты revision_no / changed_*;
--   4. индексы разрешения текущей ревизии;
--   5. витрины текущего состояния (v_current_*), манифест (v_current_object_manifest) и
--      перевод витрин анализа (v_form_elements / v_form_events / v_config_enrichment)
--      на текущее состояние.
--
-- Миграция идемпотентна: повторный прогон схему не меняет. Существующие строки получают
-- revision_no = 1 (значение по умолчанию, таблица не переписывается) и
-- changed_at = changed_by = NULL — «снимок до V19». Ошибка любого шага — ROLLBACK.
-- Запускать с -v ON_ERROR_STOP=1.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 0. Витрины анализа читают только текущую ревизию, поэтому пересоздаются
--    после v_current_*. Снимаются заранее: CREATE OR REPLACE VIEW не меняет
--    состав колонок, а ссылка источника меняется с таблиц на витрины.
-- ---------------------------------------------------------------------
DROP VIEW IF EXISTS v_form_elements;
DROP VIEW IF EXISTS v_form_events;
DROP VIEW IF EXISTS v_config_enrichment;

-- ---------------------------------------------------------------------
-- 1. Колонки состояния и манифест состава детей. DEFAULT 1 кладёт
--    revision_no существующим строкам: загруженное до V19 становится
--    ревизией 1; changed_at / changed_by остаются NULL — событие для них
--    не записывали (отличить снимок до V19 от записи V19 можно только этим).
-- ---------------------------------------------------------------------
ALTER TABLE external_report
    ADD COLUMN IF NOT EXISTS children_manifest JSONB,
    ADD COLUMN IF NOT EXISTS revision_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS changed_by TEXT;

ALTER TABLE attributes
    ADD COLUMN IF NOT EXISTS revision_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS changed_by TEXT;

ALTER TABLE tabular_sections
    ADD COLUMN IF NOT EXISTS revision_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS changed_by TEXT;

ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS revision_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS changed_by TEXT;

ALTER TABLE templates
    ADD COLUMN IF NOT EXISTS revision_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS changed_by TEXT;

ALTER TABLE form_ext
    ADD COLUMN IF NOT EXISTS revision_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS changed_by TEXT;

ALTER TABLE bsl_modules
    ADD COLUMN IF NOT EXISTS revision_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS changed_by TEXT;

-- ---------------------------------------------------------------------
-- 2. Снятие прежних границ.
--    2a. внешние ключи parent_uuid -> external_report(uuid): при двух ревизиях
--        родителя uuid больше не уникален, поэтому такой ключ существовать не
--        может (M6). Каскад удаления детей делает загрузчик явными DELETE.
--        form_ext.form_id -> forms(id) остаётся: описание формы адресуется id
--        строки-ревизии своей формы, а не uuid.
--    2b. уникальность по uuid (и по parent_uuid, uuid) означала «одна строка на
--        объект»: вторую ревизию того же uuid таблица не помещала бы.
--    2c. уникальные индексы детей без revision_no — то же для form_ext и для
--        модулей Ext/ (у модулей uuid нет, цепочка идёт по (parent_uuid, file_path)).
--    Ограничения удаляются вместе с индексами, которые их обслуживали.
-- ---------------------------------------------------------------------
ALTER TABLE attributes DROP CONSTRAINT IF EXISTS attributes_parent_uuid_fkey;
ALTER TABLE tabular_sections DROP CONSTRAINT IF EXISTS tabular_sections_parent_uuid_fkey;
ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_parent_uuid_fkey;
ALTER TABLE templates DROP CONSTRAINT IF EXISTS templates_parent_uuid_fkey;

ALTER TABLE external_report DROP CONSTRAINT IF EXISTS external_report_uuid_key;
ALTER TABLE attributes DROP CONSTRAINT IF EXISTS attributes_uuid_key;
ALTER TABLE tabular_sections DROP CONSTRAINT IF EXISTS tabular_sections_uuid_key;
ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_parent_uuid_uuid_key;
ALTER TABLE templates DROP CONSTRAINT IF EXISTS templates_parent_uuid_uuid_key;

DROP INDEX IF EXISTS uq_form_ext_form_id;
DROP INDEX IF EXISTS uq_bsl_modules_parent_file;

-- ---------------------------------------------------------------------
-- 3. Граница состояния и инварианты.
--    3a. UNIQUE (uuid, revision_no) — одна строка на состояние: повторная
--        ревизия того же uuid в ту же цепочку не ляжет, разные цепочки при
--        этом не мешают друг другу. У form_ext границы нет: описание формы
--        адресуется UNIQUE (form_id, revision_no) (3b).
--    3b. bsl_modules: цепочка модуля — (parent_uuid, file_path, revision_no);
--        частичный индекс потому, что у модулей конфигурации parent_uuid NULL,
--        они не версионируются (M1 относится к внешним объектам).
--    3c. инварианты: revision_no положительный; changed_at и changed_by либо
--        оба NULL («событие не записано»), либо оба заполнены; changed_by —
--        только словарь src/current_revision.py::CHANGED_LOAD/EDIT/RESTORE.
-- ---------------------------------------------------------------------
DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'external_report_uuid_revision_no_key') THEN
        ALTER TABLE external_report
            ADD CONSTRAINT external_report_uuid_revision_no_key UNIQUE (uuid, revision_no);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'attributes_uuid_revision_no_key') THEN
        ALTER TABLE attributes
            ADD CONSTRAINT attributes_uuid_revision_no_key UNIQUE (uuid, revision_no);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tabular_sections_uuid_revision_no_key') THEN
        ALTER TABLE tabular_sections
            ADD CONSTRAINT tabular_sections_uuid_revision_no_key UNIQUE (uuid, revision_no);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'forms_uuid_revision_no_key') THEN
        ALTER TABLE forms
            ADD CONSTRAINT forms_uuid_revision_no_key UNIQUE (uuid, revision_no);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'templates_uuid_revision_no_key') THEN
        ALTER TABLE templates
            ADD CONSTRAINT templates_uuid_revision_no_key UNIQUE (uuid, revision_no);
    END IF;
END $do$;

DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'external_report_revision_no_positive') THEN
        ALTER TABLE external_report
            ADD CONSTRAINT external_report_revision_no_positive CHECK (revision_no >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'external_report_changed_by_known') THEN
        ALTER TABLE external_report
            ADD CONSTRAINT external_report_changed_by_known
            CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'external_report_changed_pair_check') THEN
        ALTER TABLE external_report
            ADD CONSTRAINT external_report_changed_pair_check
            CHECK ((changed_at IS NULL) = (changed_by IS NULL));
    END IF;
END $do$;

DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'attributes_revision_no_positive') THEN
        ALTER TABLE attributes
            ADD CONSTRAINT attributes_revision_no_positive CHECK (revision_no >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'attributes_changed_by_known') THEN
        ALTER TABLE attributes
            ADD CONSTRAINT attributes_changed_by_known
            CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'attributes_changed_pair_check') THEN
        ALTER TABLE attributes
            ADD CONSTRAINT attributes_changed_pair_check
            CHECK ((changed_at IS NULL) = (changed_by IS NULL));
    END IF;
END $do$;

DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tabular_sections_revision_no_positive') THEN
        ALTER TABLE tabular_sections
            ADD CONSTRAINT tabular_sections_revision_no_positive CHECK (revision_no >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tabular_sections_changed_by_known') THEN
        ALTER TABLE tabular_sections
            ADD CONSTRAINT tabular_sections_changed_by_known
            CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tabular_sections_changed_pair_check') THEN
        ALTER TABLE tabular_sections
            ADD CONSTRAINT tabular_sections_changed_pair_check
            CHECK ((changed_at IS NULL) = (changed_by IS NULL));
    END IF;
END $do$;

DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'forms_revision_no_positive') THEN
        ALTER TABLE forms
            ADD CONSTRAINT forms_revision_no_positive CHECK (revision_no >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'forms_changed_by_known') THEN
        ALTER TABLE forms
            ADD CONSTRAINT forms_changed_by_known
            CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'forms_changed_pair_check') THEN
        ALTER TABLE forms
            ADD CONSTRAINT forms_changed_pair_check
            CHECK ((changed_at IS NULL) = (changed_by IS NULL));
    END IF;
END $do$;

DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'templates_revision_no_positive') THEN
        ALTER TABLE templates
            ADD CONSTRAINT templates_revision_no_positive CHECK (revision_no >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'templates_changed_by_known') THEN
        ALTER TABLE templates
            ADD CONSTRAINT templates_changed_by_known
            CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'templates_changed_pair_check') THEN
        ALTER TABLE templates
            ADD CONSTRAINT templates_changed_pair_check
            CHECK ((changed_at IS NULL) = (changed_by IS NULL));
    END IF;
END $do$;

DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'form_ext_revision_no_positive') THEN
        ALTER TABLE form_ext
            ADD CONSTRAINT form_ext_revision_no_positive CHECK (revision_no >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'form_ext_changed_by_known') THEN
        ALTER TABLE form_ext
            ADD CONSTRAINT form_ext_changed_by_known
            CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'form_ext_changed_pair_check') THEN
        ALTER TABLE form_ext
            ADD CONSTRAINT form_ext_changed_pair_check
            CHECK ((changed_at IS NULL) = (changed_by IS NULL));
    END IF;
END $do$;

DO $do$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bsl_modules_revision_no_positive') THEN
        ALTER TABLE bsl_modules
            ADD CONSTRAINT bsl_modules_revision_no_positive CHECK (revision_no >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bsl_modules_changed_by_known') THEN
        ALTER TABLE bsl_modules
            ADD CONSTRAINT bsl_modules_changed_by_known
            CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bsl_modules_changed_pair_check') THEN
        ALTER TABLE bsl_modules
            ADD CONSTRAINT bsl_modules_changed_pair_check
            CHECK ((changed_at IS NULL) = (changed_by IS NULL));
    END IF;
END $do$;

-- ---------------------------------------------------------------------
-- 4. Индексы разрешения текущей ревизии. Витрины v_current_* работают на
--    NOT EXISTS по той же цепочке, поэтому индекс по (uuid, revision_no) —
--    не ускорение, а опора контракта M5; без него поиск максимальной
--    ревизии читал бы таблицу целиком.
-- ---------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_form_ext_form_id_revision ON form_ext(form_id, revision_no);
CREATE INDEX IF NOT EXISTS idx_external_report_uuid_revision ON external_report(uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_attributes_uuid_revision ON attributes(uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_tabular_sections_uuid_revision ON tabular_sections(uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_forms_uuid_revision ON forms(uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_templates_uuid_revision ON templates(uuid, revision_no);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_parent_file_revision
    ON bsl_modules(parent_uuid, file_path, revision_no) WHERE parent_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bsl_modules_parent_uuid_revision
    ON bsl_modules(parent_uuid, revision_no) WHERE parent_uuid IS NOT NULL;

-- ---------------------------------------------------------------------
-- 5. Единая точка доступа к текущему состоянию (M5, S1–S5).
--    Текущая ревизия — максимальная по ключу цепочки; отдельный признак
--    «текущая» не заводится: его пришлось бы поддерживать при каждой вставке,
--    а пропущенная поддержка осталась бы незаметной.
--    Граница form_ext иная: описание формы относится к ревизии формы, поэтому
--    текущим считается описание с тем же revision_no, что у строки формы
--    (uq_form_ext_form_id_revision), а не максимум по form_uuid — два максимума
--    по разным ключам могли бы разойтись.
--    Модули конфигурации (parent_uuid IS NULL) историей не живут: M1 относится
--    к внешним объектам, поэтому они отдаются как есть.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_external_report AS
SELECT er.id,
       er.uuid, er.containedobject_classid, er.containedobject_objectid, er.generatedtype_name,
       er.generatedtype_category, er.generatedtype_typeid, er.generatedtype_valueid, er.name,
       er.synonym, er.comment, er.default_form, er.auxiliary_form,
       er.main_data_composition_schema, er.default_settings_form, er.auxiliary_settings_form, er.default_variant_form,
       er.variants_storage, er.settings_storage, er.created_at, er.updated_at,
       er.configuration_id, er.object_kind, er.origin_kind, er.origin_path,
       er.origin_sha256, er.origin_manifest, er.origin_recorded_at, er.children_manifest,
       er.revision_no, er.changed_at, er.changed_by
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
       a.revision_no, a.changed_at, a.changed_by
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
       ts.changed_at, ts.changed_by
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
       f.changed_by
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
       fe.created_at, fe.revision_no, fe.changed_at, fe.changed_by
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
       t.changed_at, t.changed_by
FROM templates t
WHERE NOT EXISTS (SELECT 1
                  FROM templates h
                  WHERE h.uuid = t.uuid
                    AND h.revision_no > t.revision_no);

CREATE OR REPLACE VIEW v_current_bsl_modules AS
SELECT m.id,
       m.configuration_id, m.module_name, m.file_path, m.code,
       m.object_type, m.object_name, m.report_id, m.created_at,
       m.parent_uuid, m.parent_type, m.module_type, m.code_size,
       m.truncated, m.revision_no, m.changed_at, m.changed_by
FROM bsl_modules m
WHERE m.parent_uuid IS NULL
   OR NOT EXISTS (
        SELECT 1 FROM bsl_modules n
        WHERE n.parent_uuid = m.parent_uuid
          AND n.file_path = m.file_path
          AND n.revision_no > m.revision_no
   );

-- 5.1. Манифест состава детей текущего состояния (M3, M4). Единственный способ
--      ответить, какие дети относятся к текущему состоянию: uuid в манифесте есть —
--      член текущий, uuid убран — член снят (решение A1: признака состояния на
--      строке ребёнка нет). manifest_missing различает «манифеста нет» (строки,
--      загруженные до V19) и «манифест пуст» (состав снят целиком) — читать их
--      одинаково значит соврать. Ключи манифеста задаёт src/current_revision.py::
--      build_children_manifest.
CREATE OR REPLACE VIEW v_current_object_manifest AS
SELECT er.uuid        AS object_uuid,
       er.revision_no AS object_revision_no,
       er.object_kind,
       er.name        AS object_name,
       er.children_manifest IS NULL AS manifest_missing,
       er.children_manifest         AS manifest,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'attribute_uuids') = 'array'
                    THEN er.children_manifest -> 'attribute_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS attribute_uuids,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'tabular_section_uuids') = 'array'
                    THEN er.children_manifest -> 'tabular_section_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS tabular_section_uuids,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'form_uuids') = 'array'
                    THEN er.children_manifest -> 'form_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS form_uuids,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'template_uuids') = 'array'
                    THEN er.children_manifest -> 'template_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS template_uuids,
       ARRAY(
           SELECT (e)::text
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'module_paths') = 'array'
                    THEN er.children_manifest -> 'module_paths' ELSE '[]'::jsonb END
           ) AS e
       ) AS module_paths
FROM v_current_external_report er;

-- 5.2. Витрины анализа содержимого форм (узел V14/V15) переводятся на текущее
--      состояние: историческое описание формы в состав элементов не входит, иначе
--      один и тот же элемент считался бы дважды. Таблицы не меняются —
--      используются уже существующие jsonb-колонки form_ext.items / form_ext.events.
--      Ключи-синонимы Managed и Ordinary нормализуются COALESCE-ом (см. шаг 1).
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
FROM v_current_forms f
JOIN form_ext fe        ON fe.form_id = f.id
JOIN v_current_external_report e ON e.uuid = fe.parent_uuid
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
FROM v_current_forms f
JOIN form_ext fe        ON fe.form_id = f.id
JOIN v_current_external_report e ON e.uuid = fe.parent_uuid
CROSS JOIN LATERAL jsonb_array_elements(fe.events) WITH ORDINALITY AS ev_row(ev, ord)
WHERE jsonb_typeof(fe.events) = 'array';

-- 5.3. Счётчики обогащения (шаг 1b) считаются по текущему состоянию объекта:
--      исторические ревизии одного uuid не должны множиться в строках витрины.
--      Колонка object_kind остаётся последней — порядок столбцов не меняется,
--      поэтому определение заменяется без DROP VIEW.
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
         WHERE x.parent_uuid = e.uuid) AS doc_links,
       COALESCE(e.object_kind, 'external_report') AS object_kind
FROM v_current_external_report e;

COMMIT;

-- ---------------------------------------------------------------------
-- Проверка после применения (то же, что в разделе «Проверки» правил):
--   python _cmp_ddl.py                    # живая схема == шаги 1 + 1b + 2 установки
--   python validate_external_children.py  # содержимое детей, витрины, сироты
-- Ожидаемые инварианты живой БД после миграции:
--   * у всех существовавших строк revision_no = 1, changed_at = changed_by = NULL;
--   * витрины v_current_* отдают ровно по одной строке на uuid (или на
--     (parent_uuid, file_path) для модулей) — число строк витрины равно числу
--     строк таблицы, пока история не началась;
--   * v_current_object_manifest: manifest_missing = true у строк, загруженных до V19
--     (манифест появится при следующей загрузке или правке), массивы пусты.
-- ---------------------------------------------------------------------