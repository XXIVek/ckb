-- _v51_p1_dict_probe.sql — офлайн-зонд состояния шага П1 (узел V51) по живой БД.
-- Каждая негативная проверка обособлена SAVEPOINT'ом: без них первая же ожидаемая ошибка
-- перевела бы транзакцию в состояние «aborted», и все последующие проверки были бы пропущены.
-- В конце ROLLBACK: живая база от прогона не меняется.
-- Запуск: psql -d ckb_1c_configurations -tA -P footer=off -P pager=off -f _v51_p1_dict_probe.sql
\pset pager off
\set ON_ERROR_STOP off
BEGIN;

-- 1. Данные через перестроенные витрины детей: attrs 36, ts 3, forms 2, ext 2, tpl 2.
--    Элементы и события формы витрины считают по jsonb, поэтому их число сверяется с прямым
--    подсчётом по тем же строкам form_ext: совпадение и есть проверка faithful-перестройки.
SELECT '1 витрины детей: attrs 36, ts 3, forms 2, ext 2, tpl 2; elements/events = прямой подсчёт';
SELECT 'v_current_attributes', count(*) FROM v_current_attributes;
SELECT 'v_current_tabular_sections', count(*) FROM v_current_tabular_sections;
SELECT 'v_current_forms', count(*) FROM v_current_forms;
SELECT 'v_current_form_ext', count(*) FROM v_current_form_ext;
SELECT 'v_current_templates', count(*) FROM v_current_templates;
SELECT 'v_form_elements', count(*) FROM v_form_elements;
SELECT 'v_form_events', count(*) FROM v_form_events;
SELECT 'elements прямым jsonb-подсчётом', count(*)
FROM form_ext fe
JOIN v_current_forms f ON f.id = fe.form_id
CROSS JOIN LATERAL jsonb_array_elements(fe.items) e
WHERE jsonb_typeof(fe.items) = 'array';
SELECT 'events прямым jsonb-подсчётом', count(*)
FROM form_ext fe
JOIN v_current_forms f ON f.id = fe.form_id
CROSS JOIN LATERAL jsonb_array_elements(fe.events) e
WHERE jsonb_typeof(fe.events) = 'array';

-- 2. Витрины узла V51 читаются и пусты: круг вида ещё не писался (шаг П4).
SELECT '2 витрины узла V51 обязаны читаться и быть пустыми';
SELECT 'v_current_exchange_plans', count(*) FROM v_current_exchange_plans;
SELECT 'v_current_exchange_plan_content', count(*) FROM v_current_exchange_plan_content;

-- 3. Правило (б) Q1: у строк внешнего объекта нога равна родителю.
SELECT '3 нога области видимости = parent_uuid (нулей нет: колонка NOT NULL)';
SELECT 'attrs_noga_ne_rodnitelya', count(*) FROM attributes WHERE configuration_uuid <> parent_uuid;
SELECT 'tabular_sections_noga_ne_rodnitelya', count(*) FROM tabular_sections WHERE configuration_uuid <> parent_uuid;
SELECT 'forms_noga_ne_rodnitelya', count(*) FROM forms WHERE configuration_uuid <> parent_uuid;
SELECT 'templates_noga_ne_rodnitelya', count(*) FROM templates WHERE configuration_uuid <> parent_uuid;

-- 4. Витрина отдаёт колонку ноги: иначе запрос «строки этой конфигурации» шёл бы в базовую
--    таблицу и обходил разрешение ревизий.
SELECT '4 витрина v_current_attributes содержит колонку ноги (1 = есть)';
SELECT 'v_current_attributes_has_noga', count(*)
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'v_current_attributes' AND column_name = 'configuration_uuid';

-- 5. Ключ детей держит ногу: одна пара (uuid, revision_no) в двух конфигурациях — две строки
--    (замер 3.2: 42 349 общих uuid), а повтор внутри конфигурации — отказ.
--    Список колонок берётся из information_schema: позиционный `INSERT ... SELECT *` попал бы
--    в колонку id (сдвиг на одну), поэтому он назван явно. Фильтр по схеме обязателен:
--    в information_schema есть собственный view `attributes` (атрибуты составных типов), и без
--    table_schema его колонки перемешиваются с колонками таблицы (замер прогона: udt_catalog…).
SELECT '5 ключ детей: копия строки с другой ногой проходит, повтор — отказ';
SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) AS attr_cols
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'attributes' AND column_name <> 'id' \gset
CREATE TEMP TABLE _probe_attr AS
SELECT * FROM attributes WHERE configuration_uuid = parent_uuid LIMIT 1;
ALTER TABLE _probe_attr DROP COLUMN id;
UPDATE _probe_attr SET configuration_uuid = '33333333-3333-3333-3333-333333333333';
INSERT INTO attributes (:attr_cols) SELECT * FROM _probe_attr;
SELECT '5a копия с другой ногой вставлена (ожидаем 1)', count(*) FROM attributes
WHERE configuration_uuid = '33333333-3333-3333-3333-333333333333';
SAVEPOINT sp_dup;
INSERT INTO attributes (:attr_cols) SELECT * FROM _probe_attr;
ROLLBACK TO sp_dup;
SELECT '5b повтор той же ноги отклонён (ожидаем 1 — строка не удвоилась)', count(*) FROM attributes
WHERE configuration_uuid = '33333333-3333-3333-3333-333333333333';

-- 6. Словари состояний вида замкнуты: неизвестное значение отклоняется, известное проходит.
SELECT '6 словарь properties_state: неизвестное значение отклоняется, известное проходит';
SAVEPOINT sp_bad_state;
INSERT INTO exchange_plans
    (configuration_uuid, object_uuid, object_name, full_name, source_path,
     properties_state, children_state, standard_attributes_state,
     content_state, content_count, help_state, additional_indexes_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222', 'ЗондПлана', 'ПланОбмена.ЗондПлана',
        'C:/probe/ExchangePlans/ЗондПлана.xml',
        'нет_такого_состояния', 'empty_content', 'absent',
        'empty_content', 0, 'absent', 'absent', 1, now(), 'load', true);
ROLLBACK TO sp_bad_state;
-- пара changed_at/changed_by без DEFAULT: писатель обязан называть её целиком (замер прогона —
-- первая версия зонда без changed_at падала именно на exchange_plans_changed_pair_check)
INSERT INTO exchange_plans
    (configuration_uuid, object_uuid, object_name, full_name, source_path,
     properties_state, children_state, standard_attributes_state,
     content_state, content_count, help_state, additional_indexes_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222', 'ЗондПлана', 'ПланОбмена.ЗондПлана',
        'C:/probe/ExchangePlans/ЗондПлана.xml',
        'all_known', 'empty_content', 'absent',
        'empty_content', 0, 'absent', 'absent', 1, now(), 'load', true);
SELECT '6a строка с известным словарём вставлена (ожидаем 1)', count(*) FROM exchange_plans
WHERE object_name = 'ЗондПлана';

-- 7. Пара «состояние перечня ↔ число строк» и домен AutoRecord: обе границы обязаны работать.
SELECT '7 пара content_state/content_count и домен auto_record_state';
SAVEPOINT sp_bad_pair;
INSERT INTO exchange_plans
    (configuration_uuid, object_uuid, object_name, full_name, source_path,
     properties_state, children_state, standard_attributes_state,
     content_state, content_count, help_state, additional_indexes_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '44444444-4444-4444-4444-444444444444', 'ЗондПлана2', 'ПланОбмена.ЗондПлана2',
        'C:/probe/ExchangePlans/ЗондПлана2.xml',
        'all_known', 'empty_content', 'absent',
        'empty_content', 3, 'absent', 'absent', 1, now(), 'load', true);
ROLLBACK TO sp_bad_pair;
SAVEPOINT sp_bad_auto;
INSERT INTO exchange_plan_content
    (configuration_uuid, exchange_plan_object_uuid, exchange_plan_full_name, ordinal,
     target_tag, target_full_name, target_object_type, target_resolve_state, auto_record_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222', 'ПланОбмена.ЗондПлана', 0,
        'Catalog', 'Справочник.Товары', 'Catalog', 'exact', 'Можно', 1, now(), 'load', true);
ROLLBACK TO sp_bad_auto;
-- разрешение цели обязано совпадать со ссылкой: `exact` без target_object_id/target_object_uuid
-- — это строка, которая утверждает разрешение, не ссылаясь ни на что (замер прогона)
SAVEPOINT sp_bad_resolve;
INSERT INTO exchange_plan_content
    (configuration_uuid, exchange_plan_object_uuid, exchange_plan_full_name, ordinal,
     target_tag, target_full_name, target_object_type, target_resolve_state, auto_record_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222', 'ПланОбмена.ЗондПлана', 0,
        'Catalog', 'Справочник.Товары', 'Catalog', 'exact', 'Deny', 1, now(), 'load', true);
ROLLBACK TO sp_bad_resolve;
INSERT INTO exchange_plan_content
    (configuration_uuid, exchange_plan_object_uuid, exchange_plan_full_name, ordinal,
     target_tag, target_full_name, target_object_type, target_object_id, target_object_uuid,
     target_resolve_state, auto_record_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222', 'ПланОбмена.ЗондПлана', 0,
        'Catalog', 'Справочник.Товары', 'Catalog', '7',
        '66666666-6666-6666-6666-666666666666', 'exact', 'Deny', 1, now(), 'load', true);
SELECT '7a строка перечня с известным доменом вставлена (ожидаем 1)', count(*)
FROM exchange_plan_content WHERE exchange_plan_full_name = 'ПланОбмена.ЗондПлана';

-- 8. Команда вида: вид родителя обязан быть назван писателем (DEFAULT нет намеренно),
--    словарь свойств закрыт.
SELECT '8 commands: parent_type без значения по умолчанию, словарь properties_state закрыт';
SAVEPOINT sp_no_parent_type;
INSERT INTO commands
    (configuration_uuid, parent_uuid, uuid, name, properties_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222',
        '55555555-5555-5555-5555-555555555555', 'ЗондКоманда', 'all_known', 1, now(), 'load', true);
ROLLBACK TO sp_no_parent_type;
SAVEPOINT sp_bad_cmd_state;
INSERT INTO commands
    (configuration_uuid, parent_uuid, parent_type, uuid, name, properties_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222', 'configuration_objects',
        '55555555-5555-5555-5555-555555555555', 'ЗондКоманда', 'нет_такого', 1, now(), 'load', true);
ROLLBACK TO sp_bad_cmd_state;
INSERT INTO commands
    (configuration_uuid, parent_uuid, parent_type, uuid, name, properties_state,
     revision_no, changed_at, changed_by, is_committed)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222', 'configuration_objects',
        '55555555-5555-5555-5555-555555555555', 'ЗондКоманда', 'all_known', 1, now(), 'load', true);
SELECT '8a строка команды с названным видом родителя вставлена (ожидаем 1)', count(*)
FROM commands WHERE name = 'ЗондКоманда';

ROLLBACK;
SELECT '9 после отката живой базы';
SELECT 'exchange_plans', count(*) FROM exchange_plans;
SELECT 'exchange_plan_content', count(*) FROM exchange_plan_content;
SELECT 'commands', count(*) FROM commands;
SELECT 'attrs (ожидаем прежнее 36)', count(*) FROM attributes;
