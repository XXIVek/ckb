-- ==========================================================================
-- Витрины анализа содержимого форм: v_form_elements, v_form_events.
-- Additive-миграция (узел V14/V15): таблицы не меняются, используются уже
-- существующие jsonb-колонки form_ext.items / form_ext.events.
--
-- Назначение: единая точка SQL-анализа и для Managed (items разобраны из Form.xml,
-- узел V13), и для Ordinary (items/events будут разложены из Form.bin узлом V15).
-- Ключи-синонимы различаются, поэтому витрина нормализует их COALESCE-ом:
--   kind        <- Managed: item.kind;        Ordinary(V15): item.type
--   data_source <- Managed: item.datapath;    Ordinary(V15): item.data_source
--   caption_ru  <- Managed: item.title.ru;    Ordinary(V15): item.captions.ru
--   path/page   <- есть только у Ordinary(V15); у Managed иерархия в items не сохраняется
--                  (парсер раскрывает ChildItems в плоский список) - см. «слепые зоны».
--
-- Запуск: $env:PGCLIENTENCODING='UTF8'; psql -v ON_ERROR_STOP=1 -U postgres -h localhost
--         -d ckb_1c_configurations -P pager=off -f migrate_v14_form_analysis_views.sql
-- Для уже созданных БД это единственный способ создать витрины; на чистой БД их создаёт
-- шаг 3 установки — src/ddl_external_report.sql (раздел 7, генерируется из
-- src/generate_ddl.py). Текст витрин в этом файле обязан совпадать с DDL-источником:
-- расхождение ловит _cmp_ddl.py, он сравнивает колонки и нормализованные определения
-- витрин (VIEWS в перечне сверки). Поэтому правки определений вносим в generate_ddl.py,
-- а сюда копируем готовый текст.
-- ==========================================================================

\pset footer off
\pset pager off

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

-- Самопроверка: витрины читаются, видны обе формы и их наполнение.
SELECT 'v_form_elements: ' || count(*) || ' строк, форм с элементами: '
       || count(DISTINCT (report_name, form_name)) FROM v_form_elements;
SELECT 'v_form_events: '   || count(*) || ' строк' FROM v_form_events;
SELECT report_name, form_name, COALESCE(form_type, '-') AS form_type,
       COALESCE(ext_format, '-') AS ext_format, count(*) AS elements
FROM v_form_elements GROUP BY 1, 2, 3, 4 ORDER BY 1, 2;
SELECT COALESCE(form_name, '-') || ' | ' || COALESCE(event_name, '-') || ' | '
       || COALESCE(handler_name, '-') AS event_row FROM v_form_events ORDER BY 1;
