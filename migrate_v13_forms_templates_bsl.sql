-- ============================================================
-- V13: формы, макеты и модули из подкаталогов выгрузки внешнего отчёта.
-- Миграция ТОЛЬКО additive: новые колонки, новая таблица form_ext, новые индексы,
-- замена глобальной уникальности uuid на уникальность в пределах родителя.
-- Существующие FK (parent_uuid -> external_report(uuid) ON DELETE CASCADE) сохраняются:
-- снятие FK под полиморфизм (parent_type) - отдельная миграция при реализации
-- вариантов configuration / extension / external_processing.
--
-- Запуск (кириллица в консоли Windows ломается, поэтому только -f и только с UTF8):
--   $env:PGCLIENTENCODING='UTF8'
--   C:\Postgres\bin\psql.exe -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f migrate_v13_forms_templates_bsl.sql
-- ============================================================
BEGIN;

-- ------------------------------------------------------------
-- 1. forms: метка типа родителя (полиморфная привязка)
-- ------------------------------------------------------------
ALTER TABLE forms ADD COLUMN IF NOT EXISTS parent_type text NOT NULL DEFAULT 'external_report';

-- ------------------------------------------------------------
-- 2. templates: содержимое макета из Templates\<Имя>\Ext\
--    ext          - текст содержимого (XML: схема компоновки данных и т.п.);
--    ext_bin      - двоичное содержимое (Ext\Template.bin), если XML-описания нет;
--    ext_format   - 'xml' | 'bin' | 'none'; ext_size - размер исходного файла;
--    ext_path     - путь файла относительно каталога выгрузки;
--    ext_root_tag - корневой тег XML содержимого (DataCompositionSchema и т.п.);
--    ext_truncated - содержимое сохранено не целиком (превышен порог).
-- ------------------------------------------------------------
ALTER TABLE templates ADD COLUMN IF NOT EXISTS parent_type text NOT NULL DEFAULT 'external_report';
ALTER TABLE templates ADD COLUMN IF NOT EXISTS ext text;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS ext_bin bytea;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS ext_format text;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS ext_size integer;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS ext_path text;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS ext_root_tag text;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS ext_truncated boolean NOT NULL DEFAULT false;

-- ------------------------------------------------------------
-- 3. Уникальность: uuid уникален в пределах родителя, а не глобально.
--    Расширение переиспользует uuid формы/макета базовой конфигурации, поэтому
--    глобальный UNIQUE(uuid) блокирует варианты configuration/extension.
--    Индекс по одному uuid сохраняется - поиск по uuid остаётся быстрым.
-- ------------------------------------------------------------
ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_uuid_key;
ALTER TABLE forms ADD CONSTRAINT forms_parent_uuid_uuid_key UNIQUE (parent_uuid, uuid);
CREATE INDEX IF NOT EXISTS idx_forms_uuid ON forms(uuid);
CREATE INDEX IF NOT EXISTS idx_forms_parent_type ON forms(parent_type);

ALTER TABLE templates DROP CONSTRAINT IF EXISTS templates_uuid_key;
ALTER TABLE templates ADD CONSTRAINT templates_parent_uuid_uuid_key UNIQUE (parent_uuid, uuid);
CREATE INDEX IF NOT EXISTS idx_templates_uuid ON templates(uuid);
CREATE INDEX IF NOT EXISTS idx_templates_parent_type ON templates(parent_type);

-- ------------------------------------------------------------
-- 4. form_ext: содержимое формы (поля из Forms\<Имя>\Ext\Form.xml) и её модуля.
--    Одна строка на форму. Цепочка каскада: external_report -> forms -> form_ext.
--    ext      - текст модуля формы (Forms\<Имя>\Ext\Form\Module.bsl);
--    ext_bin  - содержимое бинарной формы (Forms\<Имя>\Ext\Form.bin);
--    прочие поля - скалярные свойства Form.xml, вложенные перечни - jsonb.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS form_ext (
    id SERIAL PRIMARY KEY,
    form_id integer NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    form_uuid uuid NOT NULL,
    parent_uuid uuid NOT NULL,
    parent_type text NOT NULL DEFAULT 'external_report',
    name text,
    command_bar_location text,
    report_result text,
    details_data text,
    report_form_type text,
    auto_show_state text,
    custom_settings_folder text,
    report_result_view_mode text,
    view_mode_application_on_set_report_result text,
    auto_command_bar jsonb,
    events jsonb,
    attributes jsonb,
    commands jsonb,
    items jsonb,
    ext text,
    ext_size integer,
    ext_truncated boolean NOT NULL DEFAULT false,
    ext_bin bytea,
    ext_format text,
    ext_path text,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_form_ext_form_id ON form_ext(form_id);
CREATE INDEX IF NOT EXISTS idx_form_ext_form_uuid ON form_ext(form_uuid);
CREATE INDEX IF NOT EXISTS idx_form_ext_parent_uuid ON form_ext(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_form_ext_name ON form_ext(name);

-- ------------------------------------------------------------
-- 5. bsl_modules: та же логика разделения по родителю и конфигурации,
--    что у attributes / tabular_sections. Модули ФОРМ здесь не пишутся -
--    их содержимое хранится в form_ext.ext (решение оператора по узлу V13).
--    FK на report_id в живой схеме отсутствует, поэтому очистка явная.
-- ------------------------------------------------------------
ALTER TABLE bsl_modules ADD COLUMN IF NOT EXISTS parent_uuid uuid;
ALTER TABLE bsl_modules ADD COLUMN IF NOT EXISTS parent_type text NOT NULL DEFAULT 'external_report';
ALTER TABLE bsl_modules ADD COLUMN IF NOT EXISTS module_type varchar(50);
ALTER TABLE bsl_modules ADD COLUMN IF NOT EXISTS code_size integer;
ALTER TABLE bsl_modules ADD COLUMN IF NOT EXISTS truncated boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS idx_bsl_modules_parent_uuid ON bsl_modules(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_module_type ON bsl_modules(module_type);
-- одна строка на файл модуля в пределах родителя; частичный индекс не задевает
-- существующие строки конфигураций (parent_uuid IS NULL)
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_parent_file
    ON bsl_modules(parent_uuid, file_path) WHERE parent_uuid IS NOT NULL;

COMMIT;

SELECT 'Миграция V13 применена' AS status;
SELECT 'form_ext строк: ' || count(*) FROM form_ext;
SELECT 'templates с ext: ' || count(*) FROM templates WHERE ext IS NOT NULL;
SELECT 'bsl_modules с parent_uuid: ' || count(*) FROM bsl_modules WHERE parent_uuid IS NOT NULL;

