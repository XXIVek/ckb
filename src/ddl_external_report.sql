-- ============================================================
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
