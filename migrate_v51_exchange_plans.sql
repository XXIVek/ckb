-- migrate_v51_exchange_plans.sql
-- ============================================================================
-- Узел V51, шаг П1: план обмена (позиция 2.6 нормативного списка «Структура
--       конфигурации.txt») — таблицы вида, его перечня `<Content>` и команд, плюс
--       нога области видимости в общих таблицах детей.
-- Норматив: docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md
--           (раздел 2 и 5.5 — замеры П0/П2, раздел 5 — решения Q1…Q8, раздел 7 — план П1…П8).
-- Дата: 2026-10-31.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон ничего не
-- меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла).
-- Сверка пары — python _cmp_ddl.py.
--
-- Отличие от V48/V49/V50 названо прямо: те узлы правили только шаг 2, потому что их таблицы
-- принадлежали слою конфигурации. У V51 дети (реквизиты, табличные части, формы, макеты)
-- живут В ТЕХ ЖЕ таблицах, что построены шагом 1 под внешний объект (Q1, вариант A — принят
-- оператором 31.10.2026), поэтому правится и генератор src/generate_ddl.py, и шаг 2, и живая
-- база этой миграцией. Второй таблицы тех же сущностей не заводилось: два контракта ревизий,
-- две витрины и два ответа на один вопрос (замер 4 плана: 42 349 общих uuid детей).
--
-- 1. Нога области видимости детей (M1, M2, M3). `configuration_uuid` добавляется в
--    `attributes`, `tabular_sections`, `forms`, `templates`: uuid ребёнка повторяется между
--    конфигурациями, выросшими из общей базы (замер 3.2: 42 349 общих uuid, из них 14 у
--    детей планов обмена), поэтому прежнее `UNIQUE (uuid, revision_no)` различало бы строки
--    двух конфигураций только ревизией, а витрина выбирала бы одну «текущую» строку между
--    конфигурациями. `parent_type` добавляется только туда, где его нет (`attributes`,
--    `tabular_sections`); в `forms`/`templates` он есть с узла V13 и не переопределяется.
--    Правило (б) оператора: для строк внешнего объекта `configuration_uuid = parent_uuid`.
--    Сиротей нет (замер 5.1: 36 строк `attributes` из 36 и все строки
--    `forms`/`templates`/`tabular_sections` имеют `parent_uuid`, равный uuid существующего
--    внешнего объекта), поэтому UPDATE покрывает весь круг, а колонка объявляется NOT NULL без
--    периода «значение не заявлено». DO-блоки ниже называют исключение, если оно всё же есть:
--    `SET NOT NULL` падает текстом «null value in column», из которого не видно ни числа
--    строк, ни их родителя.
--    Ключи после переноса: `attributes`/`tabular_sections`/`commands` —
--    (configuration_uuid, parent_uuid, uuid, revision_no); `forms`/`templates` —
--    (configuration_uuid, parent_uuid, name, revision_no) (уточнение (а): имя
--    `Forms/<Имя>.xml` уникально внутри объекта, а uuid формы в индексе состава есть только
--    у строки-объекта формы).
--    `form_ext` колонки ноги НЕ получает: область видимости описания формы задаёт строка
--    самой формы, на которую ведёт FK, и своя колонка дала бы одну величину в двух таблицах.
--    Ногу несёт витрина `v_current_form_ext`, разрешая описание через форму. Витрины
--    перестроены без `COALESCE` и без ветвления на NULL: нога заполнена у всех строк именно
--    правилом (б) (M3).
--
-- 2. Новые колонки свойств детей — по замеру 5.5, а не «по вкусу»: `attributes` +3
--    (`data_history`, `full_text_search`, `indexing` — реквизит вида несёт 28 тегов против
--    25 покрытых), `tabular_sections` +1 (`line_number_length` — седьмой тег), `forms` и
--    `templates` без новых колонок (покрытие полное). Блок `<Type>` реквизита пишется в УЖЕ
--    существующую колонку `type` (text): разложенных колонок типа в схеме нет (замер 5.6).
--    CHECK по значениям свойств не кладётся (прецедент V50, Q7 вариант A): закрытость держат
--    измеренные словари src/configuration_exchange_plans.py, значение вне словаря остаётся
--    значением с состоянием `unknown_value` и названным виновником.
--
-- 3. Таблицы вида. `exchange_plans` — строка вида (40 свойств в порядке тегов файла, перечни
--    детей, слоты Help/AdditionalIndexes, состояния разбора), ключ по образцу
--    session_parameters V48. `exchange_plan_content` — строки перечня `<Content>` (замер
--    _v51_p1_content_probe.py: 46 файлов, корень `ExchangePlanContent`, 22 515 записей `Item`
--    ровно с двумя полями — `Metadata` и `AutoRecord`, домен `Deny` 22 174 / `Allow` 341),
--    модель — `subsystem_content` V46: цепь ревизий общая с родителем. `commands` — строки
--    команд вида (12 тегов, uuid даёт индекс состава), форма ключа как у `attributes`, но
--    DEFAULT вида родителя не получает: у внешнего объекта команд метаданных нет.
--
-- 4. Имена витрин обязаны совпасть с current_view() по реестру
--    CONFIGURATION_VERSIONED_TABLES (src/current_revision.py) — расхождение ловит
--    tools/check_v19_revisions.py. Круг стадии S4 от регистрации не расширяется: таблицы вида
--    вычтены константой EXCHANGE_PLAN_TABLES (src/configuration_load_contract.py), прецедент
--    V49/V50.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Таблицы детей: нога области видимости, вид родителя, измеренные свойства
-- ---------------------------------------------------------------------------

-- 1.1. attributes — реквизиты объектов и колонки табличных частей
ALTER TABLE attributes
    ADD COLUMN IF NOT EXISTS configuration_uuid UUID,
    ADD COLUMN IF NOT EXISTS parent_type TEXT NOT NULL DEFAULT 'external_report',
    ADD COLUMN IF NOT EXISTS data_history TEXT,
    ADD COLUMN IF NOT EXISTS full_text_search TEXT,
    ADD COLUMN IF NOT EXISTS indexing TEXT;

-- Предзаполнение ноги правилом (б): у строки внешнего объекта область видимости — сам
-- внешний объект. DO-блок обязан назвать исключение, если оно есть: SET NOT NULL падает
-- текстом «null value in column», из которого не видно ни числа строк, ни их родителя.
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    UPDATE attributes SET configuration_uuid = parent_uuid
     WHERE configuration_uuid IS NULL;
    SELECT count(*) INTO orphan_count FROM attributes WHERE configuration_uuid IS NULL;
    IF orphan_count > 0 THEN
        RAISE EXCEPTION
            'attributes: % строк без parent_uuid — ногу области видимости нечем заполнить',
            orphan_count;
    END IF;
END $$;

ALTER TABLE attributes ALTER COLUMN configuration_uuid SET NOT NULL;
-- прежний ключ различает строки двух конфигураций только ревизией (M2)
ALTER TABLE attributes DROP CONSTRAINT IF EXISTS attributes_uuid_revision_no_key;
ALTER TABLE attributes
    ADD CONSTRAINT attributes_configuration_parent_uuid_revision_key
        UNIQUE (configuration_uuid, parent_uuid, uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_attributes_configuration_uuid
    ON attributes(configuration_uuid);

-- 1.2. tabular_sections — табличные части (та же нога + седьмой тег вида)
ALTER TABLE tabular_sections
    ADD COLUMN IF NOT EXISTS configuration_uuid UUID,
    ADD COLUMN IF NOT EXISTS parent_type TEXT NOT NULL DEFAULT 'external_report',
    ADD COLUMN IF NOT EXISTS line_number_length INTEGER;

DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    UPDATE tabular_sections SET configuration_uuid = parent_uuid
     WHERE configuration_uuid IS NULL;
    SELECT count(*) INTO orphan_count FROM tabular_sections WHERE configuration_uuid IS NULL;
    IF orphan_count > 0 THEN
        RAISE EXCEPTION
            'tabular_sections: % строк без parent_uuid — ногу области видимости нечем заполнить',
            orphan_count;
    END IF;
END $$;

ALTER TABLE tabular_sections ALTER COLUMN configuration_uuid SET NOT NULL;
ALTER TABLE tabular_sections DROP CONSTRAINT IF EXISTS tabular_sections_uuid_revision_no_key;
ALTER TABLE tabular_sections
    ADD CONSTRAINT tabular_sections_configuration_parent_uuid_revision_key
        UNIQUE (configuration_uuid, parent_uuid, uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_tabular_sections_configuration_uuid
    ON tabular_sections(configuration_uuid);

-- 1.3. forms — описания форм: нога + ключ по ИМЕНИ формы (уточнение (а) оператора)
ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS configuration_uuid UUID;

DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    UPDATE forms SET configuration_uuid = parent_uuid
     WHERE configuration_uuid IS NULL;
    SELECT count(*) INTO orphan_count FROM forms WHERE configuration_uuid IS NULL;
    IF orphan_count > 0 THEN
        RAISE EXCEPTION
            'forms: % строк без parent_uuid — ногу области видимости нечем заполнить',
            orphan_count;
    END IF;
END $$;

ALTER TABLE forms ALTER COLUMN configuration_uuid SET NOT NULL;
ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_uuid_revision_no_key;
ALTER TABLE forms
    ADD CONSTRAINT forms_configuration_parent_name_revision_key
        UNIQUE (configuration_uuid, parent_uuid, name, revision_no);
CREATE INDEX IF NOT EXISTS idx_forms_configuration_uuid ON forms(configuration_uuid);

-- 1.4. templates — макеты: та же нога и тот же ключ по имени (`Templates/<Имя>.xml`)
ALTER TABLE templates
    ADD COLUMN IF NOT EXISTS configuration_uuid UUID;

DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    UPDATE templates SET configuration_uuid = parent_uuid
     WHERE configuration_uuid IS NULL;
    SELECT count(*) INTO orphan_count FROM templates WHERE configuration_uuid IS NULL;
    IF orphan_count > 0 THEN
        RAISE EXCEPTION
            'templates: % строк без parent_uuid — ногу области видимости нечем заполнить',
            orphan_count;
    END IF;
END $$;

ALTER TABLE templates ALTER COLUMN configuration_uuid SET NOT NULL;
ALTER TABLE templates DROP CONSTRAINT IF EXISTS templates_uuid_revision_no_key;
ALTER TABLE templates
    ADD CONSTRAINT templates_configuration_parent_name_revision_key
        UNIQUE (configuration_uuid, parent_uuid, name, revision_no);
CREATE INDEX IF NOT EXISTS idx_templates_configuration_uuid ON templates(configuration_uuid);

-- 1.5. form_ext — колонки ноги нет (см. пункт 1 шапки): нога держится у строки формы, на
--      которую ведёт FK; меняется только витрина (раздел 2).

-- ---------------------------------------------------------------------------
-- 2. Витрины текущего состояния детей: предикат по ключу области видимости (M3).
--    Тексты обязаны совпасть с шагом 1 (src/generate_ddl.py → ddl_external_report.sql):
--    расхождение определений ловит python _cmp_ddl.py.
--
--    Витрины СНИМАЮТСЯ, а не перезаписываются: `CREATE OR REPLACE VIEW` не разрешает менять
--    имена колонок по позиции («cannot change name of view column "uuid" to
--    "configuration_uuid"», замер прогона _v51_p1_migration_check.py), а нога области
--    видимости стоит в перечне колонок перед uuid — то есть порядок меняется намеренно.
--    Единственные зависимые объекты — `v_form_elements` и `v_form_events` (замер
--    pg_depend живой БД: других зависимых нет, функций и процедур в схеме нет); они
--    восстанавливаются своим текстом ниже, сразу после витрины форм.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS v_current_attributes, v_current_tabular_sections, v_current_forms,
    v_current_form_ext, v_current_templates CASCADE;

-- узел V51 (M3): предикат текущести строится по ключу области видимости
-- (configuration_uuid, parent_uuid, uuid), а не по одному uuid: 42 349 общих uuid детей
-- между конфигурациями, выросшими из общей базы (замер 3.2), дали бы одну «текущую» строку
-- сразу на несколько конфигураций. Витрина отдаёт и колонку ноги: запрос «строки этой
-- конфигурации» обязан идти через разрешение ревизий, а не через базовую таблицу.
-- Имя витрины прежнее — `current_view()` (src/current_revision.py) её не переименовывал.
CREATE OR REPLACE VIEW v_current_attributes AS
SELECT a.id,
       a.configuration_uuid, a.uuid, a.parent_uuid, a.parent_type, a.name, a.synonym,
       a.comment, a.type, a.format, a.editformat,
       a.tooltip, a.password_mode, a.mark_negatives, a.mask,
       a.multiline, a.extended_edit, a.min_value, a.max_value,
       a.fill_checking, a.fill_from_filling_value, a.fill_value, a.choice_folders_and_items,
       a.choice_parameter_links, a.choice_parameters, a.quick_choice, a.create_on_input,
       a.choice_form, a.link_by_type, a.choice_history_on_input,
       a.data_history, a.full_text_search, a.indexing, a.created_at,
       a.revision_no, a.changed_at, a.changed_by, a.is_committed
FROM attributes a
WHERE NOT EXISTS (SELECT 1
                  FROM attributes h
                  WHERE h.configuration_uuid = a.configuration_uuid
                    AND h.parent_uuid = a.parent_uuid
                    AND h.uuid = a.uuid
                    AND h.revision_no > a.revision_no);

-- узел V51 (M3): та же нога области видимости, что у v_current_attributes (см. комментарий
-- там же), плюс новые колонки ноги и вида родителя и измеренное свойство ТЧ
CREATE OR REPLACE VIEW v_current_tabular_sections AS
SELECT ts.id,
       ts.configuration_uuid, ts.uuid, ts.parent_uuid, ts.parent_type,
       ts.internalinfo_generatedtype, ts.name,
       ts.synonym, ts.comment, ts.tooltip, ts.fill_checking,
       ts.standardattributes, ts.column_uuids, ts.line_number_length, ts.created_at,
       ts.revision_no, ts.changed_at, ts.changed_by, ts.is_committed
FROM tabular_sections ts
WHERE NOT EXISTS (SELECT 1
                  FROM tabular_sections h
                  WHERE h.configuration_uuid = ts.configuration_uuid
                    AND h.parent_uuid = ts.parent_uuid
                    AND h.uuid = ts.uuid
                    AND h.revision_no > ts.revision_no);

-- узел V51 (M3 + уточнение (а)): нога области видимости и ключ по имени формы — витрина
-- разрешает текущую ревизию формы в границах (configuration_uuid, parent_uuid, name)
CREATE OR REPLACE VIEW v_current_forms AS
SELECT f.id,
       f.configuration_uuid, f.uuid, f.parent_uuid, f.name, f.synonym,
       f.comment, f.form_type, f.include_help_in_contents, f.use_purposes,
       f.created_at, f.parent_type, f.revision_no, f.changed_at,
       f.changed_by, f.is_committed
FROM forms f
WHERE NOT EXISTS (SELECT 1
                  FROM forms h
                  WHERE h.configuration_uuid = f.configuration_uuid
                    AND h.parent_uuid = f.parent_uuid
                    AND h.name = f.name
                    AND h.revision_no > f.revision_no);

-- узел V51: ногу области видимости описание формы получает от строки формы, а не из своей
-- колонки (см. комментарий к таблице form_ext): предикат сравнивает ключ формы
-- (configuration_uuid, parent_uuid, name), а не один uuid. В выдачу добавляется
-- `configuration_uuid` строки формы — иначе запрос «описания форм этой конфигурации» шёл бы
-- в обход витрины, то есть мимо разрешения ревизий.
CREATE OR REPLACE VIEW v_current_form_ext AS
SELECT fe.id,
       fe.form_id, f.configuration_uuid, fe.form_uuid, fe.parent_uuid, fe.parent_type,
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
                  WHERE h.configuration_uuid = f.configuration_uuid
                    AND h.parent_uuid = f.parent_uuid
                    AND h.name = f.name
                    AND h.revision_no > f.revision_no);

-- узел V51 (M3 + уточнение (а)): макет версионируется в границах
-- (configuration_uuid, parent_uuid, name) — той же формы ключа, что у формы
CREATE OR REPLACE VIEW v_current_templates AS
SELECT t.id,
       t.configuration_uuid, t.uuid, t.parent_uuid, t.name, t.synonym,
       t.comment, t.template_type, t.created_at, t.parent_type,
       t.ext, t.ext_bin, t.ext_format, t.ext_size,
       t.ext_path, t.ext_root_tag, t.ext_truncated, t.revision_no,
       t.changed_at, t.changed_by, t.is_committed
FROM templates t
WHERE NOT EXISTS (SELECT 1
                  FROM templates h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.parent_uuid = t.parent_uuid
                    AND h.name = t.name
                    AND h.revision_no > t.revision_no);

-- 2.6. Витрины анализа содержимого форм восстановлены после DROP ... CASCADE (см. шапку раздела 2).
--     Текст — тот же, что шаг 1 (src/ddl_external_report.sql, раздел 7.2): узел V51 их не меняет,
--     они сняты каскадом вместе с v_current_forms и обязаны вернуться в схему той же миграцией.
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

-- ---------------------------------------------------------------------------
-- 3. Таблицы вида: текст — тот же, что шаг 2 (create_1c_configurations_db.sql):
--    расхождение схемы ловит python _cmp_ddl.py (живая БД против собранной из скриптов),
--    а границы склеенных операторов ловит python _v51_paren_scan.py.
-- ---------------------------------------------------------------------------
-- Узел V51 (31.10.2026, позиция 2.6 нормативного списка «Структура конфигурации.txt»):
-- план обмена и полный цикл его детей (реквизиты, табличные части, формы с содержимым,
-- макеты с содержимым, команды, перечень реплицируемых объектов, слоты Help/AdditionalIndexes).
-- Норматив — docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md (раздел 2 и 5.5 — замеры П0/П2,
-- раздел 5 — решения Q1…Q8, раздел 7 — план П1…П8). Для живой БД, где таблицы уже созданы,
-- — migrate_v51_exchange_plans.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `exchange_plans` — СОДЕРЖИМОЕ вида, а
-- колонка configurations.exchange_plans (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида; внешнего
-- ключа нет осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v51_exchange_plans.py (П6), а не схема.
--
-- `object_uuid` NOT NULL: uuid плана обмена держит атрибут `<ExchangePlan uuid>` файла вида
-- (замер 5.5: uuid есть в файле вида у Attribute/TabularSection/Command, у Form/Template —
-- в файле описания), строка индекса состава `ExchangePlan.<Имя>` его подтверждает.
-- Расхождения круга (index_only / file_only / uuid_mismatch) называются ответом стадии, а не
-- разрешаются молча (приём V12/V48/V49/V50).
--
-- Свойств — ровно 40 тегов, порядок — порядок тегов файла. Словарь держит
-- `EXCHANGE_PLAN_PROPERTIES` (src/configuration_exchange_plans.py), порядок тегов и числа
-- словарей проверяет _v51_p2_dict_check.py. CHECK по ЗНАЧЕНИЯМ свойств не кладётся по
-- прецеденту V50 (Q7, вариант A): закрытость держит измеренный `PROPERTY_VALUE_DICTIONARY`,
-- значение вне него остаётся значением с состоянием `unknown_value` и названным виновником, а
-- не отказом записи. Состояния РАЗБОРА (properties_state, children_state, ...) замкнуты
-- CHECK'ом: это вывод слоя, а не значение выгрузки (тот же порядок, что V48/V49/V50).
--
-- Ссылки на формы (`DefaultObjectForm` и четыре `Auxiliary…`) хранятся текстом: цель такой
-- ссылки — собственный ребёнок вида, он же лежит в `form_names` этой же строки, поэтому
-- разрешение выводится связкой, а не дублируется колонками разрешения (в отличие от V50, где
-- ссылка вела на произвольный объект конфигурации и могла не разрешаться).
CREATE TABLE IF NOT EXISTS exchange_plans (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    -- 40 свойств вида в порядке тегов файла (словарь — EXCHANGE_PLAN_PROPERTIES).
    -- Два тега принадлежат только плану обмена (`DistributedInfoBase`,
    -- `IncludeConfigurationExtensions`), 16 тегов иерархии/папок/кодовых серий справочника
    -- у вида нет (замер сравнения раздела 2: совпадают 38 тегов из 40/54)
    synonym JSONB,
    comment TEXT,
    use_standard_commands BOOLEAN,
    code_length INTEGER,
    code_allowed_length TEXT,
    description_length INTEGER,
    default_presentation TEXT,
    edit_type TEXT,
    quick_choice BOOLEAN,
    choice_mode TEXT,
    input_by_string JSONB,
    search_string_mode_on_input_by_string TEXT,
    full_text_search_on_input_by_string TEXT,
    choice_data_get_mode_on_input_by_string TEXT,
    default_object_form TEXT,
    default_list_form TEXT,
    default_choice_form TEXT,
    auxiliary_object_form TEXT,
    auxiliary_list_form TEXT,
    auxiliary_choice_form TEXT,
    standard_attributes JSONB,
    characteristics JSONB,
    based_on JSONB,
    distributed_info_base BOOLEAN,
    include_configuration_extensions BOOLEAN,
    create_on_input TEXT,
    choice_history_on_input TEXT,
    include_help_in_contents BOOLEAN,
    data_lock_fields JSONB,
    data_lock_control_mode TEXT,
    full_text_search TEXT,
    object_presentation JSONB,
    extended_object_presentation JSONB,
    list_presentation JSONB,
    extended_list_presentation JSONB,
    explanation JSONB,
    data_history TEXT,
    update_data_history_immediately_after_write BOOLEAN,
    execute_after_write_data_history_version_processing BOOLEAN,
    -- перечни детей строки вида (Q2 закрыт постановкой оператора от 31.10.2026):
    -- реквизиты, табличные части и команды адресуются uuid (их даёт файл вида, индекс
    -- состава подтверждает), формы и макеты — ИМЕНЕМ: uuid формы повторяется между
    -- конфигурациями (замер 3.2: 42 349 общих uuid, из них 14 у детей планов обмена), а имя
    -- уникально в пределах вида (`Forms/<Имя>.xml`). Пустой перечень — NULL, а не '{}'
    -- (границы K1–K6 узла V43 и контракт ===EMPTY); порядок элементов побайтовый (COLLATE "C")
    attribute_uuids UUID[],
    tabular_section_uuids UUID[],
    command_uuids UUID[],
    form_names TEXT[],
    template_names TEXT[],
    -- слоты `Ext/Help.xml` и `Ext/AdditionalIndexes.xml` (Q4): исходный XML в jsonb по
    -- прецеденту `subsystems.Content` (V46). Замер П0: Help.xml — в 2/8/2 файлов выгрузок,
    -- AdditionalIndexes.xml — в 1/0/0; отсутствие файла — состояние выгрузки, а не ошибка
    help_state TEXT NOT NULL,
    help_content JSONB,
    additional_indexes_state TEXT NOT NULL,
    additional_indexes_content JSONB,
    -- состояния разбора строки (словари — константы src/configuration_exchange_plans.py:
    -- PROPERTIES_STATES, CHILD_STATES, STANDARD_ATTRIBUTE_STATES, SLOT_STATES). Разные
    -- виновники дают разные состояния, потому что устраняются разными правками: дополнить
    -- словарь замером, пересмотреть круг вида или признать состояние выгрузки
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    children_state TEXT NOT NULL,
    -- стандартные реквизиты (Q7): 371 вхождение на три выгрузки при 8 уникальных именах, в
    -- индекс состава они не входят — строк по ним не пишется, но наличие называется
    -- состоянием `present_not_indexed`, иначе их читали бы потерянными
    standard_attributes_state TEXT NOT NULL,
    -- `<Content>` разбирается таблицей exchange_plan_content; счётчик — вывод разбора круга
    content_state TEXT NOT NULL,
    content_count INTEGER NOT NULL,
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT exchange_plans_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT exchange_plans_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT exchange_plans_children_state_known
        CHECK (children_state IN ('with_children', 'empty_content',
                                  'indexed_no_file', 'file_not_in_index')),
    CONSTRAINT exchange_plans_standard_attributes_state_known
        CHECK (standard_attributes_state IN ('present_not_indexed', 'absent')),
    CONSTRAINT exchange_plans_content_state_known
        CHECK (content_state IN ('with_content', 'empty_content')),
    CONSTRAINT exchange_plans_slot_states_known
        CHECK (help_state IN ('with_content', 'absent', 'unknown_form')
               AND additional_indexes_state IN ('with_content', 'absent', 'unknown_form')),
    -- слот с содержимым держит тело, отсутствующий не держит; `unknown_form` — граница
    -- формы, которой корпус не давал (Help и AdditionalIndexes проверяются одинаково)
    CONSTRAINT exchange_plans_slot_content_matches_state
        CHECK ((help_state = 'with_content') = (help_content IS NOT NULL)
               AND (additional_indexes_state = 'with_content')
                   = (additional_indexes_content IS NOT NULL)),
    -- пустый перечень не даёт строк, непустой даёт (число строк сверяет проверка узла П6,
    -- здесь замкнута согласованность состояния и счётчика)
    CONSTRAINT exchange_plans_content_count_matches_state
        CHECK ((content_state = 'empty_content' AND content_count = 0)
               OR (content_state = 'with_content' AND content_count > 0)),
    -- «детей нет» и «круг снят» различаются состоянием children_state, а не нулями перечней:
    -- перечни при `indexed_no_file`/`file_not_in_index` обязаны быть названы стадией
    CONSTRAINT exchange_plans_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT exchange_plans_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT exchange_plans_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ по образцу session_parameters (V48): имя вида уникально в конфигурации, а uuid
    -- вида повторяется между конфигурациями, выросшими из общей базы (замер 3.2)
    CONSTRAINT exchange_plans_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- Строки перечня `<Content>` плана обмена (Q4) — вторая нога вопроса «что делает план
-- обмена»: без неё ответ «что реплицирует план» читался бы разбором xml каждый раз.
-- Замер _v51_p1_content_probe.py (31.10.2026): 46 файлов `Ext/Content.xml`, корень
-- `ExchangePlanContent`, 22 515 записей `Item`; каждая запись держит РОВНО два поля —
-- `Metadata` (точечное имя цели) и `AutoRecord` (`Deny` 22 174 / `Allow` 341, пустых и
-- отсутствующих полей — 0). В файле вида перечня нет (0 вхождений) — перечень живёт только
-- слотом, и это названо, потому что модель V50 (`common_attributes`) перечень держала в
-- файле регистрации.
-- Модель таблицы — `subsystem_content` (V46): цепь ревизий строки общая с родителем (строка
-- относится к `revision_no` строки вида), отдельной таблицы условий разрешения не заводим.
-- `auto_record_state` хранит значение выгрузки как есть (замером замкнут домен Allow/Deny)
-- плюс границу `unknown_form`: словарь замкнут четырьмя выгрузками, а не платформой.
CREATE TABLE IF NOT EXISTS exchange_plan_content (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    exchange_plan_object_uuid UUID NOT NULL,
    exchange_plan_full_name TEXT NOT NULL,
    -- позиция записи в файле; порядок писатель не меняет (прецедент target_ordinal V49)
    ordinal INTEGER NOT NULL,
    -- тег цели внутри записи (замер: во всех 22 515 записях — `Metadata`); колонка есть,
    -- потому что форма перечня — свойство выгрузки, а не обещание разбора
    target_tag TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    -- тип цели — часть точечного имени до первой точки (замер даёт InformationRegister,
    -- Document, Constant, Catalog, Sequence, ChartOfCalculationTypes и другие)
    target_object_type TEXT NOT NULL,
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    auto_record_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT exchange_plan_content_names_not_blank
        CHECK (exchange_plan_full_name <> '' AND target_full_name <> ''
               AND target_tag <> '' AND target_object_type <> ''),
    CONSTRAINT exchange_plan_content_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    -- состояние разрешения согласовано со ссылкой и остатком пути (тот же контракт, что
    -- role_rights V49 и common_attribute_targets V50): «цель найдена» и «цель не найдена»
    -- различимы структурой строки, а не молчанием колонок
    CONSTRAINT exchange_plan_content_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_object_uuid IS NOT NULL AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved' AND target_object_id IS NULL
                AND target_object_uuid IS NULL AND target_unresolved_path IS NOT NULL)),
    CONSTRAINT exchange_plan_content_auto_record_state_known
        CHECK (auto_record_state IN ('Allow', 'Deny', 'unknown_form')),
    CONSTRAINT exchange_plan_content_ordinal_non_negative CHECK (ordinal >= 0),
    CONSTRAINT exchange_plan_content_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT exchange_plan_content_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT exchange_plan_content_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- размерность родителя в ключе держится по той же причине, что у subsystem_content
    -- (узел V47): uuid плана обмена общий для конфигураций, выросших из общей базы, поэтому
    -- без configuration_uuid строка второй конфигурации падала бы на ключ первой
    CONSTRAINT exchange_plan_content_plan_revision_ordinal_key
        UNIQUE (configuration_uuid, exchange_plan_object_uuid, revision_no, ordinal)
);

-- Строки команд вида (замер 5.5: `ChildObjects/Command`, 12 тегов, атрибут `uuid` есть у
-- 1 из 1 записей корпуса). Таблица строится по образцу `attributes` — та же форма ключа
-- детей и та же цепь ревизий (Q6, вариант A: `revision_no` обязан значить одно и то же для
-- строк внешнего объекта и объекта конфигурации), но относится она к выгрузке конфигурации,
-- поэтому лежит здесь, а не в шаге 1 (src/generate_ddl.py): у внешнего объекта команд
-- метаданных нет, его команды интерфейса живут jsonb-колонкой `form_ext.commands`.
-- Колонка тега `Group` названа `command_group`: `group` — ключевое слово SQL, и колонка с
-- таким именем требовала бы кавычек в каждом запросе писателя и проверки. Несовпадение имени
-- XML и колонки хранится одним местом — словарём `COMMAND_PROPERTIES`.
-- `parent_type` NOT NULL БЕЗ значения по умолчанию осознанно: вид родителя обязана назвать
-- точка записи, а DEFAULT `'external_report'` означал бы здесь «дети внешнего объекта»,
-- которых у этой таблицы нет (в attributes DEFAULT унаследован от узла V13 намеренно).
CREATE TABLE IF NOT EXISTS commands (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    parent_type TEXT NOT NULL,
    uuid UUID NOT NULL,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    command_group TEXT,
    command_parameter_type TEXT,
    parameter_use_mode TEXT,
    modifies_data BOOLEAN,
    representation TEXT,
    tooltip JSONB,
    picture TEXT,
    shortcut TEXT,
    on_main_server_unavalable_behavior TEXT,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT commands_name_not_blank CHECK (name <> ''),
    CONSTRAINT commands_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- значения свойств (замер: `Group` = NavigationPanelImportant, `Representation` = Auto,
    -- `ParameterUseMode` = Single, `OnMainServerUnavalableBehavior` = Auto) CHECK'ом не
    -- замыкаются по той же причине, что свойства вида и общие реквизиты V50: закрытость
    -- держит словарь `COMMAND_VALUE_DICTIONARY`, значение вне него остаётся значением с
    -- состоянием `unknown_value` и названным виновником
    CONSTRAINT commands_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT commands_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT commands_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- форма ключа та же, что у attributes/tabular_sections: uuid ребёнка даёт индекс состава
    CONSTRAINT commands_configuration_parent_uuid_revision_key
        UNIQUE (configuration_uuid, parent_uuid, uuid, revision_no)
);

-- ---------------------------------------------------------------------------
-- 4. Витрины текущего состояния узла (текст — тот же, что шаг 2).
-- ---------------------------------------------------------------------------
-- Витрины текущего состояния узла V51. Предикат — тот же, что у витрин V46/V48/V50: строка
-- относится к максимальной ревизии в пределах ключа своей цепочки; признак коммита на круг
-- не влияет (решение A1). Имена витрин задаёт не этот файл: их отдаёт current_view() по
-- реестру CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py — по той же причине таблицы узла внесены и в этот реестр.
CREATE OR REPLACE VIEW v_current_exchange_plans AS
SELECT ep.id,
       ep.configuration_uuid, ep.object_uuid, ep.object_name, ep.full_name,
       ep.synonym, ep.comment, ep.use_standard_commands, ep.code_length,
       ep.code_allowed_length, ep.description_length, ep.default_presentation,
       ep.edit_type, ep.quick_choice, ep.choice_mode, ep.input_by_string,
       ep.search_string_mode_on_input_by_string, ep.full_text_search_on_input_by_string,
       ep.choice_data_get_mode_on_input_by_string, ep.default_object_form,
       ep.default_list_form, ep.default_choice_form, ep.auxiliary_object_form,
       ep.auxiliary_list_form, ep.auxiliary_choice_form, ep.standard_attributes,
       ep.characteristics, ep.based_on, ep.distributed_info_base,
       ep.include_configuration_extensions, ep.create_on_input, ep.choice_history_on_input,
       ep.include_help_in_contents, ep.data_lock_fields, ep.data_lock_control_mode,
       ep.full_text_search, ep.object_presentation, ep.extended_object_presentation,
       ep.list_presentation, ep.extended_list_presentation, ep.explanation,
       ep.data_history, ep.update_data_history_immediately_after_write,
       ep.execute_after_write_data_history_version_processing,
       ep.attribute_uuids, ep.tabular_section_uuids, ep.command_uuids,
       ep.form_names, ep.template_names,
       ep.help_state, ep.help_content, ep.additional_indexes_state,
       ep.additional_indexes_content,
       ep.properties_state, ep.unknown_property_names, ep.children_state,
       ep.standard_attributes_state, ep.content_state, ep.content_count, ep.source_path,
       ep.created_at, ep.revision_no, ep.changed_at, ep.changed_by, ep.is_committed
FROM exchange_plans ep
WHERE NOT EXISTS (SELECT 1 FROM exchange_plans h
                  WHERE h.configuration_uuid = ep.configuration_uuid
                    AND h.object_name = ep.object_name
                    AND h.revision_no > ep.revision_no);

-- Витрина перечня реплицируемых объектов — по образцу v_current_subsystem_content (V46):
-- строка относится к той ревизии родителя, которая признана текущей. Отдельного предиката
-- по «своей» максимальной ревизии не заводим: своей цепи у перечня нет, она общая с
-- родителем (Q6 узла V51), и два независимых максимума разошлись бы между строкой вида и
-- её перечнем.
CREATE OR REPLACE VIEW v_current_exchange_plan_content AS
SELECT ec.id,
       ec.configuration_uuid, ec.exchange_plan_object_uuid, ec.exchange_plan_full_name,
       ec.ordinal, ec.target_tag, ec.target_full_name, ec.target_object_type,
       ec.target_object_id, ec.target_object_uuid, ec.target_resolve_state,
       ec.target_unresolved_path, ec.auto_record_state, ec.created_at,
       ec.revision_no, ec.changed_at, ec.changed_by, ec.is_committed
FROM exchange_plan_content ec
WHERE EXISTS (SELECT 1 FROM v_current_exchange_plans ce
              WHERE ce.configuration_uuid = ec.configuration_uuid
                AND ce.object_uuid = ec.exchange_plan_object_uuid
                AND ce.revision_no = ec.revision_no);

-- Витрина команд текущего состояния. Предикат повторяет форму ключа детей —
-- (configuration_uuid, parent_uuid, uuid), как v_current_attributes узла V51: uuid ребёнка
-- повторяется между конфигурациями, поэтому нога области видимости обязательна и здесь.
CREATE OR REPLACE VIEW v_current_commands AS
SELECT c.id,
       c.configuration_uuid, c.parent_uuid, c.parent_type, c.uuid, c.name,
       c.synonym, c.comment, c.command_group, c.command_parameter_type,
       c.parameter_use_mode, c.modifies_data, c.representation, c.tooltip,
       c.picture, c.shortcut, c.on_main_server_unavalable_behavior,
       c.properties_state, c.unknown_property_names, c.created_at,
       c.revision_no, c.changed_at, c.changed_by, c.is_committed
FROM commands c
WHERE NOT EXISTS (SELECT 1 FROM commands h
                  WHERE h.configuration_uuid = c.configuration_uuid
                    AND h.parent_uuid = c.parent_uuid
                    AND h.uuid = c.uuid
                    AND h.revision_no > c.revision_no);

-- ---------------------------------------------------------------------------
-- 5. Индексы узла (текст — тот же, что шаг 2).
-- ---------------------------------------------------------------------------
-- Индексы узла V51. Отдельного индекса по configuration_uuid у exchange_plans,
-- exchange_plan_content и commands не заводим: его обслуживает уникальный индекс цепочки той
-- же таблицы с ведущей колонкой configuration_uuid — им же пользуются предикат витрины и
-- чистка стадии по конфигурации (тот же порядок, что V44/V46/V48/V49/V50). Индекс по
-- object_uuid заводится, потому что им связан перечень реплицируемых объектов со строкой
-- вида: предикат v_current_exchange_plan_content идёт по (object_uuid, revision_no), а в
-- уникальном индексе цепочки строки вида этой пары нет.
CREATE INDEX IF NOT EXISTS idx_exchange_plans_object_uuid_revision
    ON exchange_plans(object_uuid, revision_no);
-- Индексы перечня отвечают на карточку запроса «в каких планах обмена реплицируется этот
-- объект» (target_full_name — точечное имя из <Metadata>) и, для разрешённых ссылок, по
-- uuid цели. Отдельного индекса по ordinal нет: он ведомая колонка уникального индекса.
CREATE INDEX IF NOT EXISTS idx_exchange_plan_content_target_full_name
    ON exchange_plan_content(target_full_name);
CREATE INDEX IF NOT EXISTS idx_exchange_plan_content_target_object_uuid
    ON exchange_plan_content(target_object_uuid) WHERE target_object_uuid IS NOT NULL;
-- Команды: индекс по родителю заводится отдельно, потому что ведущая колонка уникального
-- индекса — configuration_uuid, а снятие круга стадии и карточка объекта идут по
-- (parent_uuid, revision_no); тот же порядок, что idx_attributes_parent_uuid узла V19.
CREATE INDEX IF NOT EXISTS idx_commands_parent_uuid ON commands(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_commands_name ON commands(name);
CREATE INDEX IF NOT EXISTS idx_commands_uuid_revision ON commands(uuid, revision_no);
