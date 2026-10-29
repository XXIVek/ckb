-- _v48_p1_ddl_probe.sql
-- ============================================================================
-- Узел V48, шаг П1: проверка модели таблицы session_parameters ФАКТОМ вставки.
-- Каждый случай живёт в своей транзакции и откатывается: проверка ничего не
-- оставляет в базе. Запуск:
--   $env:PGPASSWORD='...'; C:\Postgres\bin\psql.exe -U postgres -h localhost \
--       -d ckb_1c_configurations -P pager=off -f _v48_p1_ddl_probe.sql
-- Отказ обязан быть назван именем ограничения, а не молчаливым пропуском
-- (молчание схемы — это отсутствие договорённости).
-- ============================================================================
\set ON_ERROR_STOP off

-- 1. позитив: составной тип (две записи <v8:Type>) принимается, кратность composite
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'СоставныйСеанс', 'СоставныйСеанс', 'composite', 'parsed',
        '[{"index":0,"value":"cfg:CatalogRef.Организации","class":"object_ref","state":"parsed","resolved":true,"target_object_type":"Catalog","target_object_uuid":"33333333-3333-3333-3333-333333333333","target_full_name":"Catalog.Организации"},
          {"index":1,"value":"cfg:CatalogRef.Товары","class":"object_ref","state":"parsed","resolved":true,"target_object_type":"Catalog","target_object_uuid":"44444444-4444-4444-4444-444444444444","target_full_name":"Catalog.Товары"}]'::jsonb,
        'SessionParameters/СоставныйСеанс.xml');
SELECT 'ОЖИДАЕМО 1: composite принят, строк = ' || count(*) FROM session_parameters;
-- содержательный запрос по цели ссылки идёт containment'ом по витрине (замер 2.5)
SELECT 'ОЖИДАЕМО 1b: containment по витрине = ' || count(*)
FROM v_current_session_parameters
WHERE types @> '[{"target_full_name":"Catalog.Организации"}]'::jsonb;
ROLLBACK;

-- 2. негатив: две записи, но заявлен одиночный тип (CHECK согласованности)
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'ДвеЗаписиSingle', 'ДвеЗаписиSingle', 'single', 'parsed',
        '[{"index":0,"value":"A"},{"index":1,"value":"B"}]'::jsonb,
        'SessionParameters/ДвеЗаписиSingle.xml');
SELECT 'ОЖИДАЕМО 2: ОТКАЗ, но строка принята — CHECK не сработал';
ROLLBACK;

-- 3. негатив: состояние absent при непустом массиве («не разобрали» ≠ «типа не было»)
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'AbsentНепустой', 'AbsentНепустой', 'absent', 'parsed',
        '[{"index":0,"value":"A"}]'::jsonb, 'SessionParameters/AbsentНепустой.xml');
SELECT 'ОЖИДАЕМО 3: ОТКАЗ, но строка принята';
ROLLBACK;

-- 3b. негатив: «типа не было» при состоянии разбора parsed — граница Q3.
--     Кратность здесь согласована (пустой массив ↔ absent), поэтому отказ обязан
--     назвать именно session_parameters_types_absent_matches_no_block: «не
--     разобрали» и «типа не было» различимы ограничением, а не договорённостью.
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'ПустоНоParsed', 'ПустоНоParsed', 'absent', 'parsed', '[]'::jsonb,
        'SessionParameters/ПустоНоParsed.xml');
SELECT 'ОЖИДАЕМО 3b: ОТКАЗ (types_absent_matches_no_block), но строка принята';
ROLLBACK;

-- 4. позитив: блока <Type> не было — absent + пустой массив
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'БезТипа', 'БезТипа', 'absent', 'absent', '[]'::jsonb,
        'SessionParameters/БезТипа.xml');
SELECT 'ОЖИДАЕМО 4: absent принят';
ROLLBACK;

-- 5. негатив: состояние разбора вне закрытого словаря
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'ЧужоеСостояние', 'ЧужоеСостояние', 'single', 'broken',
        '[{"index":0,"value":"A"}]'::jsonb, 'SessionParameters/ЧужоеСостояние.xml');
SELECT 'ОЖИДАЕМО 5: ОТКАЗ, но строка принята';
ROLLBACK;

-- 6. негатив: types — не массив. Отказ обязан назвать ограничение
--    session_parameters_types_is_array, а не внутреннюю ошибку
--    «cannot get array length of a non-array». Разница — в самой формуле CHECK:
--    в первой версии ограничения jsonb_array_length вызывался безусловно, и
--    та же вставка давала внутренний текст ошибки вместо отказа ограничения
--    (замер 29.10.2026 до правки CHECK). Поэтому согласованность кратности
--    выражена CASE с проверкой формы в первой ветке: порядок веток CASE
--    гарантирован, в отличие от плоского OR, где порядок вычисления
--    подвыражений не оговаривается.
--    Значение подается колонкой подзапроса VALUES — так проверка идёт по
--    значению строки в момент вставки, а не по свёрнутой константе: отдельный
--    замер показал, что голое константное выражение
--    (SELECT jsonb_array_length('5'::jsonb)) планировщик вычисляет ещё до
--    исполнения, и оно отвечает внутренним текстом ошибки.
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
SELECT '11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
       'НеМассив', 'НеМассив', 'single', 'parsed', v.types,
       'SessionParameters/НеМассив.xml'
FROM (VALUES ($json${"index":0}$json$::jsonb)) AS v(types);
SELECT 'ОЖИДАЕМО 6: ОТКАЗ (types_is_array), но строка принята';
ROLLBACK;

-- 6b. та же форма литералом — отказ обязан называть то же ограничение: граница
--     выражается CHECK при любой форме подачи значения, а не зависит от того,
--     откуда планировщик взял значение.
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'НеМассивЛитерал', 'НеМассивЛитерал', 'single', 'parsed',
        $json${"index":0}$json$::jsonb, 'SessionParameters/НеМассивЛитерал.xml');
SELECT 'ОЖИДАЕМО 6b: ОТКАЗ (types_is_array), но строка принята';
ROLLBACK;

-- 7. граница CHECK: лишние ключи записи и дубликат значения схема принимает —
--    поэтому словарь записи сторожит проверка узла, а не схема (замер 2.5)
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'ЛишниеКлючи', 'ЛишниеКлючи', 'composite', 'partial',
        '[{"index":0,"value":"A","class":"unknown","state":"unknown_form","мусор":1},
          {"index":1,"value":"A","class":"unknown","state":"unknown_form"}]'::jsonb,
        'SessionParameters/ЛишниеКлючи.xml');
SELECT 'ОЖИДАЕМО 7: принято СХЕМОЙ (словарь сторожит tools/check_v48_session_parameters.py)';
ROLLBACK;

-- 8. негатив: половина штампа изменения (пара changed_at <-> changed_by)
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path, changed_at)
VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
        'ПоловинаШтампа', 'ПоловинаШтампа', 'absent', 'absent', '[]'::jsonb,
        'SessionParameters/ПоловинаШтампа.xml', NOW());
SELECT 'ОЖИДАЕМО 8: ОТКАЗ, но строка принята';
ROLLBACK;

-- 9. ключ цепочки состояния: вторая ревизия по тому же object_name продолжает
--    цепочку и становится единственной текущей (правило A1)
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path, revision_no)
VALUES ('55555555-5555-5555-5555-555555555555', '66666666-6666-6666-6666-666666666666',
        'ПараметрСеанса', 'ПараметрСеанса', 'single', 'parsed',
        '[{"index":0,"value":"cfg:CatalogRef.Организации"}]'::jsonb,
        'SessionParameters/ПараметрСеанса.xml', 1);
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path, revision_no)
VALUES ('55555555-5555-5555-5555-555555555555', '66666666-6666-6666-6666-666666666666',
        'ПараметрСеанса', 'ПараметрСеанса', 'single', 'parsed',
        '[{"index":0,"value":"cfg:CatalogRef.Товары"}]'::jsonb,
        'SessionParameters/ПараметрСеанса.xml', 2);
SELECT 'ОЖИДАЕМО 9: строк витрины = ' || count(*)
       || ', текущая revision_no = ' || max(revision_no)
FROM v_current_session_parameters
WHERE configuration_uuid = '55555555-5555-5555-5555-555555555555';
-- тот же object_name в ДРУГОЙ конфигурации — не повтор: граница configuration_uuid
-- обязательна при любой форме ключа (замер _v48_q2_key_probe.py)
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path, revision_no)
VALUES ('77777777-7777-7777-7777-777777777777', '66666666-6666-6666-6666-666666666666',
        'ПараметрСеанса', 'ПараметрСеанса', 'absent', 'absent', '[]'::jsonb,
        'SessionParameters/ПараметрСеанса.xml', 1);
SELECT 'ОЖИДАЕМО 9b: та же строка в другой конфигурации принята, строк = ' || count(*)
FROM session_parameters;
ROLLBACK;

-- 10. негатив: revision_no = 0
BEGIN;
INSERT INTO session_parameters
    (configuration_uuid, object_uuid, object_name, full_name,
     type_multiplicity, type_parse_state, types, source_path, revision_no)
VALUES ('55555555-5555-5555-5555-555555555555', '66666666-6666-6666-6666-666666666666',
        'НулеваяРевизия', 'НулеваяРевизия', 'absent', 'absent', '[]'::jsonb,
        'SessionParameters/НулеваяРевизия.xml', 0);
SELECT 'ОЖИДАЕМО 10: ОТКАЗ, но строка принята';
ROLLBACK;

-- 11. после откатов база пустая: ни одна проверка не оставила строк
SELECT 'ОЖИДАЕМО 11: строк в таблице = ' || count(*) FROM session_parameters;
