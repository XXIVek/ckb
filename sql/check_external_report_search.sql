-- Ручная проверка содержательного наполнения и возможностей поиска по внешним отчётам.
-- Запуск (ON_ERROR_STOP обязателен: без него битая команда «съедает» остаток файла,
-- psql возвращает 0 и часть проверок молча не выполняется):
--   $env:PGCLIENTENCODING='UTF8'; psql -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f check_external_report_search.sql -o _v13_search_out.txt
-- Эталон: Test1_Otchet, uuid a6db7252-5cfd-4e33-8e28-66e8f1a74a46, имя СравнениеУСНИ90_2.

\pset footer off
\pset pager off

SELECT '=== 10. Реквизиты самого отчёта (не колонки ТЧ): имя, синоним, тип ===' AS section;
SELECT concat('ATTR name=', a.name, ' synonym_ru=', COALESCE(a.synonym ->> 'ru', '-'),
              ' types=', COALESCE(replace((a.type::jsonb -> 'types')::text, '"', ''), '-'))
FROM attributes a
WHERE a.parent_uuid = 'a6db7252-5cfd-4e33-8e28-66e8f1a74a46'::uuid
  AND NOT EXISTS (SELECT 1 FROM tabular_sections t, jsonb_array_elements_text(t.column_uuids) cu
                   WHERE t.parent_uuid = a.parent_uuid AND cu::uuid = a.uuid)
ORDER BY a.name;

SELECT '=== 11. Табличные части эталонного отчёта: имя, синоним, число колонок ===' AS section;
SELECT concat('TS name=', t.name, ' synonym_ru=', COALESCE(t.synonym ->> 'ru', '-'),
              ' cols=', jsonb_array_length(t.column_uuids))
FROM tabular_sections t WHERE t.parent_uuid = 'a6db7252-5cfd-4e33-8e28-66e8f1a74a46'::uuid ORDER BY t.name;

SELECT '=== 12. Колонки одной ТЧ в порядке выгрузки (связь column_uuids -> attributes) ===' AS section;
SELECT ord || '. ' || a.name || ' | ' || COALESCE(a.synonym ->> 'ru', '-') || ' | ' || COALESCE(replace((a.type::jsonb -> 'types')::text, '"', ''), '-')
FROM tabular_sections t
JOIN LATERAL jsonb_array_elements_text(t.column_uuids) WITH ORDINALITY AS cu(uuid, ord) ON true
JOIN attributes a ON a.uuid = cu.uuid::uuid
WHERE t.name = 'ТаблицаБУ'
ORDER BY cu.ord LIMIT 12;

SELECT '=== 13. Какие типы встречаются в реквизитах и колонках (топ) ===' AS section;
SELECT tt || '  x' || count(*) FROM attributes a, jsonb_array_elements_text(a.type::jsonb -> 'types') tt GROUP BY tt ORDER BY count(*) DESC, tt LIMIT 15;

SELECT '=== 14. Квалификаторы типов (число с точностью, ссылка на справочник) ===' AS section;
SELECT concat(a.name, ' -> ', (a.type::jsonb -> 'qualifiers')::text)
FROM attributes a WHERE a.type IS NOT NULL AND (a.type::jsonb) ? 'qualifiers' AND (a.type::jsonb -> 'qualifiers')::text <> '{}' ORDER BY a.name LIMIT 8;

SELECT '=== 15. BSL-модули эталонного отчёта: имена, размер кода, кириллица в коде ===' AS section;
SELECT concat('BSL id=', b.id, ' module=', b.module_name, ' object_type=', b.object_type,
              ' object_name=', b.object_name, ' code_len=', length(b.code),
              ' есть_кириллица=', (b.code ~ '[А-Яа-яЁё]')::text, ' file=', b.file_path)
FROM bsl_modules b WHERE b.report_id = (SELECT id FROM external_report WHERE uuid = 'a6db7252-5cfd-4e33-8e28-66e8f1a74a46')
ORDER BY b.id;

SELECT '=== 16. ПОИСК 1: отчёт по подстроке имени (ILIKE) ===' AS section;
SELECT id || ' | ' || name FROM external_report WHERE name ILIKE '%сравнен%' ORDER BY id;

SELECT '=== 17. ПОИСК 2: отчёт по русскому синониму (jsonb ->>) ===' AS section;
SELECT id || ' | ' || name || ' | synonym=' || (synonym ->> 'ru') FROM external_report WHERE synonym ->> 'ru' ILIKE '%сравнен%';

SELECT '=== 18. ПОИСК 3: любой реквизит/колонка по имени во всех загруженных объектах ===' AS section;
SELECT concat('name=', a.name, ' synonym_ru=', COALESCE(a.synonym ->> 'ru', '-'), ' родителя=', p.name)
FROM attributes a JOIN external_report p ON p.uuid = a.parent_uuid WHERE a.name ILIKE '%организаци%' ORDER BY a.name LIMIT 10;

SELECT '=== 19. ПОИСК 4: реквизиты по конкретному типу (ссылка на справочник) ===' AS section;
SELECT concat('name=', a.name, ' type=', tt, ' родителя=', p.name)
FROM attributes a JOIN external_report p ON p.uuid = a.parent_uuid, jsonb_array_elements_text(a.type::jsonb -> 'types') tt
WHERE tt LIKE '%CatalogRef.%' ORDER BY tt, a.name LIMIT 10;

SELECT '=== 20. ПОИСК 5: табличные части по имени их колонки ===' AS section;
SELECT DISTINCT concat('отчёт=', p.name, ' ТЧ=', t.name, ' найденная колонка=', a.name)
FROM tabular_sections t
JOIN external_report p ON p.uuid = t.parent_uuid
JOIN jsonb_array_elements_text(t.column_uuids) cu ON true
JOIN attributes a ON a.uuid = cu::uuid
WHERE a.name ILIKE '%номенклатур%' OR a.synonym ->> 'ru' ILIKE '%номенклатур%' ORDER BY 1 LIMIT 10;

SELECT '=== 21. ПОИСК 6: какой ТЧ принадлежит конкретная колонка (jsonb @>) ===' AS section;
SELECT concat('ТЧ=', t.name, ' отчёт=', p.name)
FROM tabular_sections t JOIN external_report p ON p.uuid = t.parent_uuid
WHERE t.column_uuids @> jsonb_build_array((SELECT uuid::text FROM attributes WHERE name = 'Номенклатура' LIMIT 1))
LIMIT 5;

SELECT '=== 22. ПОИСК 7: поиск по тексту всех модулей (BSL Ext/ + модули форм V14) ===';
-- Единый обзор «где что лежит»: модули Ext/ из bsl_modules и модули форм из form_ext.ext.
-- Именно этот набор текстов enrichment-MCP сможет разложить в сниппеты и алиасы.
-- Класс пробела — POSIX [[:space:]]: на сервере standard_conforming_strings = off,
-- backslash в строковом литерале съедается ('Процедура\s' -> 'Процедураs').
SELECT 'МОДУЛЬ=' || m.kind || ' объявлений_процедур=' || m.decls || ' | владелец=' || m.owner
FROM (
    SELECT 'bsl/' || COALESCE(b.module_type, '-') AS kind,
           regexp_count(b.code, 'Процедура[[:space:]]') + regexp_count(b.code, 'Функция[[:space:]]') AS decls,
           COALESCE(b.object_name, b.parent_uuid::text) || ' (' || b.file_path || ')' AS owner,
           b.parent_uuid
    FROM bsl_modules b
    UNION ALL
    SELECT 'form/' || COALESCE(f.form_type, '-') || '/' || COALESCE(fe.ext_format, '-'),
           regexp_count(fe.ext, 'Процедура[[:space:]]') + regexp_count(fe.ext, 'Функция[[:space:]]'),
           fe.name || ' (модуль формы)',
           fe.parent_uuid
    FROM form_ext fe JOIN forms f ON f.id = fe.form_id
) m
JOIN external_report p ON p.uuid = m.parent_uuid
WHERE m.decls > 0
ORDER BY m.kind, p.name;
-- Поиск по подстроке в модуле формы ordinary (V14): конкретное имя обработчика события.
SELECT 'ПОДСТРОКА В МОДУЛЕ ordinary: отчёт=' || e.name || ' форма=' || fe.name ||
       ' найдено=' || (position('ОтчетСформировать' IN fe.ext) > 0)::text
FROM form_ext fe
JOIN forms f ON f.id = fe.form_id
JOIN external_report e ON e.uuid = fe.parent_uuid
WHERE f.form_type = 'Ordinary'
ORDER BY e.name;

SELECT '=== 23. ПОИСК 8: полнотекстовый поиск по имени объекта и его синониму ===' AS section;
-- Важно: форма 'слово*' в этой среде теряет оператор (* отбрасывается), префикс задаётся явно: 'слово:*'
SELECT id || ' | ' || name FROM external_report
WHERE to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(synonym ->> 'ru', ''))
      @@ to_tsquery('simple', 'сравнение');
SELECT id || ' | ' || name FROM external_report
WHERE to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(synonym ->> 'ru', ''))
      @@ to_tsquery('simple', 'сравнен:*');

SELECT '=== 24. ПОИСК 9: реквизиты/колонки с числовыми квалификаторами (decimal с точностью) ===' AS section;
SELECT concat('name=', a.name, ' fraction_digits=', a.type::jsonb -> 'qualifiers' -> 'NumberQualifiers' ->> 'FractionDigits',
              ' родителя=', p.name)
FROM attributes a JOIN external_report p ON p.uuid = a.parent_uuid
WHERE a.type::jsonb -> 'qualifiers' ? 'NumberQualifiers' ORDER BY a.name LIMIT 6;

SELECT '=== 25. ПОИСК 10-11 (V13): содержимое макета и модуля формы ===' AS section;
-- ПОИСК 10: макет по фрагменту содержимого (макеты в bsl_modules не индексируются)
SELECT 'МАКЕТ=' || t.name || ' отчёт=' || e.name || ' root_tag=' || COALESCE(t.ext_root_tag, '-')
FROM templates t JOIN external_report e ON e.uuid = t.parent_uuid
WHERE t.ext LIKE '%DataCompositionSchema%' ORDER BY e.name;
-- ПОИСК 11: модуль формы по тексту процедуры — хранится в form_ext.ext (правило R9)
SELECT 'ФОРМА=' || fe.name || ' отчёт=' || e.name || ' формат=' || COALESCE(fe.ext_format, '-')
       || ' длина=' || COALESCE(length(fe.ext), 0)
FROM form_ext fe JOIN external_report e ON e.uuid = fe.parent_uuid
WHERE fe.ext LIKE '%ЗаполнитьДанныеНаСервере%' ORDER BY e.name;
-- контроль разделения модулей (R9): модуля формы в bsl_modules быть не должно
SELECT 'module_type=FormModule в bsl_modules = ' || count(*) FROM bsl_modules WHERE module_type = 'FormModule';
SELECT 'строк bsl_modules с текстом модуля формы = ' || count(*)
FROM bsl_modules WHERE code LIKE '%ЗаполнитьДанныеНаСервере%';
-- поиск объекта по элементу управления формы (datapath -> реквизит отчёта)
SELECT 'ОБЪЕКТ=' || e.name || ' элемент_формы=' || (el ->> 'name') || ' datapath=' || (el ->> 'datapath')
FROM form_ext fe
JOIN external_report e ON e.uuid = fe.parent_uuid
JOIN jsonb_array_elements(fe.items) el ON el ? 'datapath'
WHERE split_part(el ->> 'datapath', '.', 2) = 'Организация' ORDER BY e.name;

SELECT '=== 27. ПОИСК 12: элемент формы по имени и типу (V15 работает и для ordinary) ===' AS section;
-- Витрина v_form_elements единая: Managed из Form.xml (V13), Ordinary из 0/form контейнера
-- Form.bin (узел V15). Различия ключей jsonb (kind/type, datapath/data_source, title/captions)
-- закрыты в витрине через COALESCE, поэтому один и тот же запрос находит обе разновидности.
SELECT 'ЭЛЕМЕНТ=' || report_name || '/' || form_name || ' имя=' || element_name
       || ' kind=' || COALESCE(element_kind, '-') || ' type=' || COALESCE(element_type, '-')
       || ' form_type=' || form_type
FROM v_form_elements
WHERE element_name ILIKE '%Организация%' OR element_kind IN ('InputField', 'Field')
ORDER BY 1;
SELECT 'элементов ordinary-формы (Ожидание V15: 10 = страница + 9 элементов Test2_Otchet) = '
       || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary';
SELECT 'ordinary-элементов Field (Ожидание V15: 2 — Организация, ДатаОтчета) = ' || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary' AND element_kind = 'Field';

SELECT '=== 28. ПОИСК 13: элемент формы по подписи (caption) ===' AS section;
SELECT 'ЭЛЕМЕНТ=' || report_name || '/' || form_name || ' имя=' || element_name
       || ' подпись=' || caption_ru || ' kind=' || COALESCE(element_kind, '-')
FROM v_form_elements
WHERE caption_ru ILIKE '%период%' OR caption_ru ILIKE '%организация%'
      OR caption_ru ILIKE '%счета%' OR caption_ru ILIKE '%учреждение%'
ORDER BY 1;
-- Подписи ordinary-элементов (надписи Test2_Otchet): «Учреждение», «Дата отчета»,
-- «Поле списка1:», «Выберите счета:» — узел V15 извлекает их из 0/form.
SELECT 'ordinary-элементов с подписью (Ожидание V15: 4) = ' || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary' AND caption_ru IS NOT NULL;
SELECT 'ЭЛЕМЕНТ ПОДПИСЬ=' || report_name || '/' || element_path || ' -> ' || caption_ru
FROM v_form_elements
WHERE form_type = 'Ordinary' AND caption_ru IS NOT NULL ORDER BY 1;

SELECT '=== 29. ПОИСК 14: элемент по источнику данных + сверка с реквизитами отчёта ===' AS section;
-- Источник данных формы может быть реквизитом отчёта, колонкой ТЧ или атрибутом самой формы
-- (последнего в attributes нет) — витрина позволяет различить эти случаи в одном запросе.
SELECT 'ЭЛЕМЕНТ=' || ve.report_name || '/' || ve.form_name || ' имя=' || ve.element_name
       || ' источник=' || ve.data_source || ' | '
       || CASE WHEN a.uuid IS NULL THEN 'нет среди реквизитов отчёта (атрибут формы или внешний)'
               WHEN ts_column THEN 'колонка табличной части ' || ts_name
               ELSE 'реквизит отчёта' END
FROM (
    SELECT ve0.*,
           EXISTS (SELECT 1 FROM tabular_sections ts
                   JOIN jsonb_array_elements_text(ts.column_uuids) cu ON cu::uuid = a0.uuid
                   WHERE ts.parent_uuid = ve0.report_uuid) AS ts_column,
           (SELECT ts.name FROM tabular_sections ts
            JOIN jsonb_array_elements_text(ts.column_uuids) cu ON cu::uuid = a0.uuid
            WHERE ts.parent_uuid = ve0.report_uuid LIMIT 1) AS ts_name
    FROM v_form_elements ve0
    LEFT JOIN attributes a0 ON a0.parent_uuid = ve0.report_uuid
         AND a0.name = split_part(ve0.data_source, '.', 2)
    WHERE ve0.data_source IS NOT NULL
) ve
LEFT JOIN attributes a ON a.parent_uuid = ve.report_uuid
     AND a.name = split_part(ve.data_source, '.', 2)
ORDER BY 1;
-- V15: ordinary-форма даёт те же строки витрины. У Test2_Otchet источники элементов
-- (Организация, ДатаОтчета, ПолеСписка1) — атрибуты формы, а не реквизиты отчёта:
-- пометка «нет среди реквизитов отчёта» для них ожидаема и корректна.
SELECT 'ordinary-элементов с источником данных (Ожидание V15: 3) = ' || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary' AND data_source IS NOT NULL;
SELECT 'атрибутов ordinary-формы в form_ext.attributes (Ожидание V15: 4 — включая '
       || 'ВнешнийОтчетОбъект) = ' || count(*)
FROM form_ext fe JOIN forms f ON f.id = fe.form_id
CROSS JOIN LATERAL jsonb_array_elements(fe.attributes) AS attr
WHERE f.form_type = 'Ordinary' AND (attr ->> 'name') IS NOT NULL;

SELECT '=== 30. ПОИСК 15: обработчик события формы и его наличие в модуле ===' AS section;
-- Событие без обработчика в тексте модуля = признак неполного разбора (или обработчика из
-- другого модуля): для ordinary-формы модуль доступен с V14, поэтому проверка работает для обоих типов.
-- У ordinary-разметки имени обработчика нет (event -> 'handler' не заполняется), поэтому
-- дополнительно ищем по имени самого события: в ordinary-форме обработчик обычно и есть
-- процедура с именем события.
SELECT 'СОБЫТИЕ=' || ve.report_name || '/' || ve.form_name || ' ' || ve.event_name
       || ' -> ' || COALESCE(ve.handler_name, '(имя обработчика разметкой не задано)')
       || ' | имя события в модуле формы: ' || (position(ve.event_name IN fe.ext) > 0)::text
       || ' | обработчик в модуле формы: '
       || (position(COALESCE(ve.handler_name, ve.event_name) IN fe.ext) > 0)::text
       || ' | в модуле объекта: '
       || (position(COALESCE(ve.handler_name, ve.event_name) IN b.code) > 0)::text
FROM v_form_events ve
JOIN form_ext fe ON fe.form_uuid = ve.form_uuid
LEFT JOIN bsl_modules b ON b.parent_uuid = ve.report_uuid AND b.module_type = 'ObjectModule'
ORDER BY 1;
SELECT 'событий ordinary-формы через v_form_events (Ожидание V15: 1 — ПередОткрытием) = '
       || count(*)
FROM v_form_events WHERE form_type = 'Ordinary';
-- Обратный ход: процедура из модуля ordinary-формы (V14) как ключ поиска объекта.
-- Регулярки с кириллическими диапазонами на Windows-коллиляции ненадёжны — берём position().
SELECT 'МОДУЛЬ ФОРМЫ ordinary: отчёт=' || e.name || ' форма=' || fe.name
       || ' объявление обработчика найдено='
       || (position('Процедура ДействияФормыОтчетСформировать' IN fe.ext) > 0)::text
       || ' длина=' || length(fe.ext)
FROM form_ext fe
JOIN forms f ON f.id = fe.form_id
JOIN external_report e ON e.uuid = fe.parent_uuid
WHERE f.form_type = 'Ordinary' AND fe.ext LIKE '%ДействияФормыОтчетСформировать%'
ORDER BY e.name;

SELECT '=== 31. ПОИСК 16: полнотекстовый поиск по составу элементов (заготовка для алиасов) ===' AS section;
-- Лексический индекс по jsonb items/events/ext - то, что enrichment-MCP сможет разложить
-- в алиасы объектов (имена элементов, подписи, обработчики). Префикс задаём явно: to_tsquery
-- в форме 'слово*' оператор * теряет (проверено ранее).
SELECT 'FTS ЭЛЕМЕНТЫ: отчёт=' || e.name || ' контекст=' || ts_headline('simple', blob, q)
FROM (
    SELECT fe.parent_uuid,
           coalesce(fe.items::text, '') || ' ' || coalesce(fe.events::text, '') AS blob
    FROM form_ext fe
) src
JOIN external_report e ON e.uuid = src.parent_uuid
CROSS JOIN LATERAL to_tsquery('simple', 'Организация:*') q
WHERE to_tsvector('simple', src.blob) @@ q
ORDER BY e.name;
-- Ограничение FTS 'simple' (проверено 13.10.2026): идентификатор 1С без разделителей —
-- ОДИН лексем ('действияформыотчетсформировать'), поэтому префикс по хвосту слова не срабатывает.
-- Работает: префикс по началу идентификатора и подстрока через position(). Для поиска по
-- середине идентификатора нужен pg_trgm (в кластере доступен, не установлен) — см. план enrichment.
SELECT 'FTS МОДУЛЬ ordinary (V14): отчёт=' || e.name
FROM form_ext fe
JOIN forms f ON f.id = fe.form_id
JOIN external_report e ON e.uuid = fe.parent_uuid
CROSS JOIN LATERAL to_tsquery('simple', 'действияформыотчетсформировать:*') q
WHERE f.form_type = 'Ordinary' AND to_tsvector('simple', coalesce(fe.ext, '')) @@ q
ORDER BY e.name;
SELECT 'FTS МОДУЛЬ ordinary: префикс по ХВОСТУ идентификатора (ожидание false): найдено=' ||
       (to_tsvector('simple', coalesce(fe.ext, '')) @@ to_tsquery('simple', 'Сформировать:*'))::text
FROM form_ext fe
JOIN forms f ON f.id = fe.form_id
JOIN external_report e ON e.uuid = fe.parent_uuid
WHERE f.form_type = 'Ordinary'
ORDER BY e.name;
SELECT 'POSITION МОДУЛЬ ordinary (работает всегда): отчёт=' || e.name || ' найдено=' ||
       (position('ДействияФормыОтчетСформировать' IN fe.ext) > 0)::text
FROM form_ext fe
JOIN forms f ON f.id = fe.form_id
JOIN external_report e ON e.uuid = fe.parent_uuid
WHERE f.form_type = 'Ordinary'
ORDER BY e.name;

SELECT '=== 32. ПОИСК 17 (V17): объект по точному алиасу ===' AS section;
-- Точное совпадение alias_norm — то же, что делает search_config_aliases_tool (rank最高的 слой).
SELECT 'ТОЧНЫЙ АЛИАС «' || a.alias_name || '» → объект=' || e.name
       || ' цель=' || a.target_type || ':' || COALESCE(a.target_name, '-')
FROM v_config_alias_targets a
JOIN external_report e ON e.uuid = a.parent_uuid
WHERE a.alias_norm = lower('СреднийВозрастОС')
ORDER BY 1;

SELECT '=== 33. ПОИСК 18 (V17): цель по подстроке алиаса (FTS этого не умеет) ===' AS section;
-- Идентификатор 1С — одна лексема, поэтому середина и хвост ищутся position() по alias_norm.
SELECT 'ПОДСТРОКА «ДатаНачала» → объект=' || e.name || ' цель=' || a.target_type
       || ':' || COALESCE(a.target_name, '-') || ' ключ=' || COALESCE(a.target_uuid, '-')
FROM v_config_alias_targets a
JOIN external_report e ON e.uuid = a.parent_uuid
WHERE position('датаначала' IN a.alias_norm) > 0
ORDER BY a.target_type, a.alias_norm LIMIT 20;
SELECT 'ПОДСТРОКА «ийВозрастОС» (хвост идентификатора) → объектов=' ||
       count(DISTINCT a.parent_uuid) || ' алиасов=' || count(*)
FROM v_config_alias_targets a
WHERE position(lower('ийВозрастОС') IN a.alias_norm) > 0;

SELECT '=== 34. ПОИСК 19 (V17): код по имени процедуры через config_snippets.tsv ===' AS section;
-- Сниппеты строятся из объявлений модулей (form_ext.ext и bsl_modules.code), индекс tsv
-- вычислен в схеме (конфигурация 'simple'). Префикс задаём явно: to_tsquery('simple','имя:*').
SELECT 'СНИППЕТ по имени процедуры → объект=' || e.name || ' вопрос=' || s.question
       || ' verified=' || s.is_verified::text
FROM config_snippets s
JOIN external_report e ON e.uuid = s.parent_uuid
CROSS JOIN LATERAL to_tsquery('simple', 'ПередОткрытием:*') q
WHERE s.tsv @@ q
ORDER BY 1;
-- Фолбэк без FTS: подстрока по question (работает всегда, используется инструментом поиска).
SELECT 'ПОДСТРОКА по вопросу сниппета → объект=' || e.name || ' вопрос=' || s.question
FROM config_snippets s
JOIN external_report e ON e.uuid = s.parent_uuid
WHERE position('ПередОткрытием' IN s.question) > 0
ORDER BY 1;

SELECT '=== 35. ПОИСК 20 (V17): сниппеты по цели (get_config_snippets_for_object) ===' AS section;
-- Зависимость уже несёт стабильный target_uuid — тот же ключ, что у алиаса этой цели.
SELECT 'ЦЕЛЬ → сниппеты: объект=' || e.name || ' цель=' || d.target_type
       || ':' || d.target_name || ' сниппетов=' || count(*)
       || ' ключ=' || COALESCE(max(d.target_uuid), '-')
FROM config_snippet_dependencies d
JOIN config_snippets s ON s.id = d.snippet_id
JOIN external_report e ON e.uuid = s.parent_uuid
GROUP BY e.name, d.target_type, d.target_name
ORDER BY 1 LIMIT 40;


SELECT '=== 36. ПОИСК 21 (узел A): текст запроса набора данных макета в config_snippets ===' AS section;
-- В схеме компоновки данных запрос набора лежит в <query> внутри <dataSet> (без суффикса Text).
-- До узла A генератор вырезал только <*queryText*> - таких сниппетов не было вовсе.
-- FTS по 'simple' ищет полные лексемы: «ВЫБРАТЬ» находится как слово, префикс задаём явно.
SELECT 'ЗАПРОС МАКЕТА через FTS → объект=' || e.name || ' вопрос=' || s.question
       || ' verified=' || s.is_verified::text
FROM config_snippets s
JOIN external_report e ON e.uuid = s.parent_uuid
CROSS JOIN LATERAL to_tsquery('simple', 'ВЫБРАТЬ:*') q
WHERE s.tsv @@ q AND s.source_kind = 'template_query'
ORDER BY 1;
-- Имя набора данных входит в question авто-сниппета - поиск по нему работает и без FTS.
SELECT 'НАБОР ДАННЫХ по имени → объект=' || e.name || ' вопрос=' || s.question
       || ' цель=' || s.target_type || ':' || COALESCE(s.target_uuid, '-')
FROM config_snippets s
JOIN external_report e ON e.uuid = s.parent_uuid
WHERE s.source_kind = 'template_query'
  AND position(lower('НаборДанных1') IN lower(s.question)) > 0
ORDER BY 1;
-- Текст запроса ищется и по коду сниппета (подстрока - фолбэк для середины идентификатора).
SELECT 'ЗАПРОС по фрагменту кода → объект=' || e.name || ' вопрос=' || s.question
FROM config_snippets s
JOIN external_report e ON e.uuid = s.parent_uuid
WHERE position('РасходыПриУСН' IN s.answer) > 0 AND s.source_kind = 'template_query'
ORDER BY 1;
-- Покрытие: каждый разобранный <query> макета обязан дать сниппет с целью на этот макет.
SELECT 'ПОКРЫТИЕ: макетов с <query> = ' || count(*)
       || ', из них со сниппетом = ' || count(*) FILTER (WHERE has_snippet)
       || ', с целью Template = ' || count(*) FILTER (WHERE has_template_target)
FROM (
    SELECT t.uuid,
           EXISTS (SELECT 1 FROM config_snippets s
                    WHERE s.source_kind = 'template_query'
                      AND s.source_uuid = 'template:' || t.uuid::text) AS has_snippet,
           EXISTS (SELECT 1 FROM config_snippets s
                    WHERE s.source_kind = 'template_query'
                      AND s.target_type = 'Template'
                      AND s.target_uuid = t.uuid::text) AS has_template_target
    FROM templates t
    WHERE t.ext IS NOT NULL
      AND (position('<query>' IN t.ext) > 0 OR position(':query>' IN t.ext) > 0)
) x;

SELECT '=== 99. ИТОГОВЫЕ счётчики после всех тестов ===' AS section;
SELECT 'external_report = ' || count(*) FROM external_report;
SELECT 'attributes = ' || count(*) FROM attributes;
SELECT 'tabular_sections = ' || count(*) FROM tabular_sections;
SELECT 'forms = ' || count(*) FROM forms;
SELECT 'form_ext = ' || count(*) FROM form_ext;
SELECT 'templates = ' || count(*) FROM templates;
SELECT 'bsl_modules = ' || count(*) FROM bsl_modules;
SELECT 'config_aliases = ' || count(*) FROM config_aliases;
SELECT 'config_aliases активных = ' || count(*) FROM config_aliases WHERE active;
SELECT 'config_snippets = ' || count(*) FROM config_snippets;
SELECT 'config_snippet_dependencies = ' || count(*) FROM config_snippet_dependencies;
SELECT 'config_cross_references = ' || count(*) FROM config_cross_references;
