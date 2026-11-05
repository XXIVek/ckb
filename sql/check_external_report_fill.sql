-- Ручная проверка заполнения и целостности данных внешних отчётов (база ckb_1c_configurations).
-- Запуск (ON_ERROR_STOP обязателен: без него битая команда «съедает» остаток файла,
-- psql продолжает с кодом возврата 0 и часть проверок молча не выполняется):
--   $env:PGCLIENTENCODING='UTF8'; psql -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f check_external_report_fill.sql -o _v13_fill_out.txt
-- Вывод в файл (-o) обязателен: конвейер PowerShell перекодирует кириллицу.
-- Ожидаемые значения соответствуют эталонной паре выгрузок:
--   Test1_Otchet (uuid a6db7252-5cfd-4e33-8e28-66e8f1a74a46, управляемая форма) —
--     реквизитов объекта 3 + колонок табличных частей 33 = 36 строк в attributes,
--     3 строки в tabular_sections, форма из Form.xml (V13/V14.1);
--   Test2_Otchet (uuid d364e104-e1ef-49e7-8163-d2ab726aaa96, ОБЫЧНАЯ форма «Отчет») —
--     модуль из 0/module (V14) и состав из 0/form (V15): items 10, attributes 4, events 1,
--     commands 1, auto_command_bar «ДействияФормы».

\pset footer off
\pset pager off

SELECT '=== 1. Загруженные объекты и счётчики дочерних данных ===' AS section;
SELECT concat('id=', e.id, ' name=', e.name, ' attrs=',
              (SELECT count(*) FROM attributes a WHERE a.parent_uuid = e.uuid),
              ' ts=', (SELECT count(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid),
              ' bsl=', (SELECT count(*) FROM bsl_modules b WHERE b.report_id = e.id))
FROM external_report e ORDER BY e.id;

SELECT '=== 2. Разделение: реквизиты объекта vs колонки табличных частей (одна таблица attributes) ===' AS section;
SELECT concat('name=', e.name, ' всего_attrs=',
              (SELECT count(*) FROM attributes a WHERE a.parent_uuid = e.uuid),
              ' колонок_ТЧ=',
              (SELECT count(DISTINCT cu::uuid) FROM tabular_sections t, jsonb_array_elements_text(t.column_uuids) cu
                WHERE t.parent_uuid = e.uuid AND cu::uuid IN (SELECT a.uuid FROM attributes a WHERE a.parent_uuid = e.uuid)),
              ' реквизитов_объекта=',
              (SELECT count(*) FROM attributes a WHERE a.parent_uuid = e.uuid
                 AND NOT EXISTS (SELECT 1 FROM tabular_sections t, jsonb_array_elements_text(t.column_uuids) cu
                                  WHERE t.parent_uuid = e.uuid AND cu::uuid = a.uuid)))
FROM external_report e ORDER BY e.id;

SELECT '=== 3. Каждой ТЧ соответствует строка attributes с parent_uuid = uuid объекта (не ТЧ) ===' AS section;
SELECT concat('ts=', t.name, ' parent_uuid_совпадает_с_объектом=',
              (t.parent_uuid = e.uuid)::text, ' колонок_в_списке=', jsonb_array_length(t.column_uuids),
              ' найдено_в_attributes=',
              (SELECT count(*) FROM jsonb_array_elements_text(t.column_uuids) cu
                WHERE EXISTS (SELECT 1 FROM attributes a WHERE a.uuid = cu::uuid)))
FROM tabular_sections t JOIN external_report e ON e.uuid = t.parent_uuid ORDER BY t.id;

SELECT '=== 4. Битые ссылки column_uuids (должно быть 0) ===' AS section;
SELECT concat('ts=', t.name, ' несуществующих_ колонок=',
              (SELECT count(*) FROM jsonb_array_elements_text(t.column_uuids) cu
                WHERE NOT EXISTS (SELECT 1 FROM attributes a WHERE a.uuid = cu::uuid)))
FROM tabular_sections t ORDER BY t.id;

SELECT '=== 5. Дубликаты uuid (должно быть 0 во всех таблицах) ===' AS section;
SELECT 'dup external_report = ' || count(*) FROM (SELECT uuid FROM external_report GROUP BY uuid HAVING count(*) > 1) d;
SELECT 'dup attributes = ' || count(*) FROM (SELECT uuid FROM attributes GROUP BY uuid HAVING count(*) > 1) d;
SELECT 'dup tabular_sections = ' || count(*) FROM (SELECT uuid FROM tabular_sections GROUP BY uuid HAVING count(*) > 1) d;

SELECT '=== 6. Сироты (дочерние данные без родителя / bsl без отчёта) - должно быть 0 ===' AS section;
SELECT 'attrs-сироты = ' || count(*) FROM attributes a WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = a.parent_uuid);
SELECT 'ts-сироты = ' || count(*) FROM tabular_sections t WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = t.parent_uuid);
SELECT 'bsl-сироты = ' || count(*) FROM bsl_modules b WHERE b.report_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM external_report e WHERE e.id = b.report_id);
SELECT 'attrs с пустым uuid = ' || count(*) FROM attributes a WHERE a.uuid IS NULL;

SELECT '=== 7. Заполненность ключевых полей attributes (jsonb/text/boolean) ===' AS section;
SELECT concat('всего=', count(*),
              ' synonym=', count(*) FILTER (WHERE synonym IS NOT NULL),
              ' type=', count(*) FILTER (WHERE type IS NOT NULL),
              ' comment=', count(*) FILTER (WHERE comment IS NOT NULL),
              ' mask=', count(*) FILTER (WHERE mask IS NOT NULL),
              ' password_mode_true=', count(*) FILTER (WHERE password_mode),
              ' multiline_true=', count(*) FILTER (WHERE multiline),
              ' fill_value=', count(*) FILTER (WHERE fill_value IS NOT NULL))
FROM attributes;
SELECT 'synonym jsonb типы: ' || string_agg(DISTINCT jsonb_typeof(synonym), ',') FROM attributes WHERE synonym IS NOT NULL;
SELECT 'type парсится как json: ' || count(*) FILTER (WHERE type::jsonb ? 'types') || ' из ' || count(*) FROM attributes WHERE type IS NOT NULL;

SELECT '=== 8. Заполненность tabular_sections ===' AS section;
SELECT concat('всего=', count(*),
              ' generatedtype=', count(*) FILTER (WHERE internalinfo_generatedtype IS NOT NULL),
              ' standardattributes=', count(*) FILTER (WHERE standardattributes IS NOT NULL),
              ' column_uuids=', count(*) FILTER (WHERE column_uuids IS NOT NULL),
              ' synonym=', count(*) FILTER (WHERE synonym IS NOT NULL))
FROM tabular_sections;
SELECT concat('generatedtype[0] category=', internalinfo_generatedtype -> 0 ->> 'category',
              ' name=', internalinfo_generatedtype -> 0 ->> 'name',
              ' | [1] category=', internalinfo_generatedtype -> 1 ->> 'category',
              ' элементов=', jsonb_array_length(internalinfo_generatedtype))
FROM tabular_sections ORDER BY id LIMIT 5;

SELECT '=== 9. Заполненность external_report (синоним, GeneratedType, DataCompositionSchema) ===' AS section;
SELECT concat('name=', name, ' synonym_ru=', COALESCE(synonym ->> 'ru', '-'),
              ' langs=', COALESCE((SELECT count(*) FROM jsonb_object_keys(synonym))::text, '-'),
              ' gt_category=', COALESCE(generatedtype_category, '-'),
              ' gt_name=', COALESCE(generatedtype_name, '-'),
              ' schema=', COALESCE(left(main_data_composition_schema, 40), '-'),
              ' classid_eq_default=', (containedobject_classid = 'e41aff26-25cf-4bb6-b6c1-3f478a75f374')::text)
FROM external_report ORDER BY id;

-- ==========================================================================
-- Разделы 10-14: содержимое подкаталогов Forms/, Templates/, Ext/ (узел V13).
-- ==========================================================================

SELECT '=== 10. Полные счётчики V13 по каждому объекту ===' AS section;
SELECT concat('id=', e.id, ' name=', e.name,
              ' attrs=', (SELECT count(*) FROM attributes a WHERE a.parent_uuid = e.uuid),
              ' ts=', (SELECT count(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid),
              ' forms=', (SELECT count(*) FROM forms f WHERE f.parent_uuid = e.uuid),
              ' form_ext=', (SELECT count(*) FROM form_ext fe WHERE fe.parent_uuid = e.uuid),
              ' templates=', (SELECT count(*) FROM templates tp WHERE tp.parent_uuid = e.uuid),
              ' bsl_by_parent_uuid=', (SELECT count(*) FROM bsl_modules b WHERE b.parent_uuid = e.uuid),
              ' bsl_by_report_id=', (SELECT count(*) FROM bsl_modules b WHERE b.report_id = e.id))
FROM external_report e ORDER BY e.id;

SELECT '=== 11. Модули Ext/ в bsl_modules (R9): module_type, размеры, parent_uuid ===' AS section;
SELECT concat('module_type=', COALESCE(b.module_type, '-'),
              ' file=', b.file_path,
              ' code_size=', COALESCE(b.code_size::text, '-'),
              ' len(code)=', COALESCE(length(b.code)::text, '-'),
              ' truncated=', COALESCE(b.truncated::text, '-'),
              ' parent_type=', COALESCE(b.parent_type, '-'),
              ' report_id=', COALESCE(b.report_id::text, '-'))
FROM bsl_modules b WHERE b.parent_uuid IS NOT NULL ORDER BY b.id;
SELECT 'модулей формы в bsl_modules (должно быть 0) = ' || count(*)
FROM bsl_modules
WHERE module_type = 'FormModule'
   OR lower(replace(file_path, chr(92), '/')) LIKE '%/form/module.bsl%';

SELECT '=== 12. Формы: forms + form_ext (свойства, jsonb, модуль формы в ext) ===' AS section;
-- Внимание: у формы, выгруженной в бинарном виде (Form.bin вместо Form.xml), свойства не
-- разбираются, но jsonb-колонки заполняются ПУСТЫМИ контейнерами ([] / {}), а не NULL.
-- Признак разобранной формы — items/events с содержимым: jsonb_array_length(items) > 0,
-- а не items IS NOT NULL. Достоверный признак содержимого модуля — length(ext) > 0.
SELECT concat('form=', f.name, ' uuid=', f.uuid, ' form_type=', COALESCE(f.form_type, '-'),
              ' synonym=', (f.synonym IS NOT NULL)::text,
              ' | ext_len=', COALESCE(length(fe.ext)::text, '0'),
              ' ext_size=', COALESCE(fe.ext_size::text, '-'),
              ' ext_format=', COALESCE(fe.ext_format, '-'),
              ' has_bin=', (fe.ext_bin IS NOT NULL)::text,
              ' items=', (fe.items IS NOT NULL)::text,
              ' events=', (fe.events IS NOT NULL)::text,
              ' auto_command_bar=', (fe.auto_command_bar IS NOT NULL)::text,
              ' commands=', (fe.commands IS NOT NULL)::text,
              ' attributes=', (fe.attributes IS NOT NULL)::text)
FROM forms f LEFT JOIN form_ext fe ON fe.form_id = f.id ORDER BY f.id;
SELECT concat('items[0].tag=', jsonb_typeof(fe.items),
              ' элементов_верхнего_уровня=', COALESCE(jsonb_array_length(fe.items)::text, '-'),
              ' form=', fe.name)
FROM form_ext fe WHERE fe.items IS NOT NULL ORDER BY fe.id;

SELECT '=== 13. Макеты: содержимое Templates/Ext в templates.ext / ext_bin ===' AS section;
SELECT concat('template=', t.name, ' ext_format=', COALESCE(t.ext_format, '-'),
              ' ext_size=', COALESCE(t.ext_size::text, '-'),
              ' has_ext=', (t.ext IS NOT NULL)::text, ' has_bin=', (t.ext_bin IS NOT NULL)::text,
              ' root_tag=', COALESCE(t.ext_root_tag, '-'),
              ' truncated=', COALESCE(t.ext_truncated::text, '-'),
              ' начало=', COALESCE(replace(left(t.ext, 60), chr(10), ' '), '-'))
FROM templates t ORDER BY t.id;

SELECT '=== 14. Целостность V13: сироты, дубли в пределах родителя (R10), пропуски ===' AS section;
SELECT 'forms-сироты = ' || count(*) FROM forms f WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = f.parent_uuid);
SELECT 'templates-сироты = ' || count(*) FROM templates tp WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = tp.parent_uuid);
SELECT 'form_ext без строки forms = ' || count(*) FROM form_ext fe LEFT JOIN forms f ON f.id = fe.form_id WHERE f.id IS NULL;
SELECT 'form_ext.form_uuid <> forms.uuid = ' || count(*) FROM form_ext fe JOIN forms f ON f.id = fe.form_id WHERE fe.form_uuid IS DISTINCT FROM f.uuid;
SELECT 'form_ext.parent_uuid <> forms.parent_uuid = ' || count(*) FROM form_ext fe JOIN forms f ON f.id = fe.form_id WHERE fe.parent_uuid IS DISTINCT FROM f.parent_uuid;
SELECT 'bsl-сироты по parent_uuid = ' || count(*) FROM bsl_modules b WHERE b.parent_uuid IS NOT NULL AND NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = b.parent_uuid);
SELECT 'dup forms в пределах родителя = ' || count(*) FROM (SELECT parent_uuid, uuid FROM forms GROUP BY 1, 2 HAVING count(*) > 1) d;
SELECT 'dup templates в пределах родителя = ' || count(*) FROM (SELECT parent_uuid, uuid FROM templates GROUP BY 1, 2 HAVING count(*) > 1) d;
SELECT 'dup form_ext на форму = ' || count(*) FROM (SELECT form_id FROM form_ext GROUP BY 1 HAVING count(*) > 1) d;
SELECT 'dup bsl_modules по (parent_uuid, file_path) = ' || count(*) FROM (SELECT parent_uuid, file_path FROM bsl_modules WHERE parent_uuid IS NOT NULL GROUP BY 1, 2 HAVING count(*) > 1) d;
SELECT 'forms без form_ext = ' || count(*) FROM forms f WHERE NOT EXISTS (SELECT 1 FROM form_ext fe WHERE fe.form_id = f.id);
SELECT 'form_ext без ext и без ext_bin = ' || count(*) FROM form_ext WHERE ext IS NULL AND ext_bin IS NULL;
SELECT 'templates без ext и без ext_bin = ' || count(*) FROM templates WHERE ext IS NULL AND ext_bin IS NULL;

SELECT '=== 15. Поиск по содержимому модуля формы и макета (R9, R10) ===' AS section;
-- Поиск по тексту модуля работает для обоих источников: Managed (Form.xml + Module.bsl)
-- и Ordinary (V14: модуль извлечён из Form.bin). Считаем объявления процедур/функций.
-- ВАЖНО: на этом сервере standard_conforming_strings = off, backslash в литерале съедается
-- ('Процедура\s' становится 'Процедураs'), поэтому класс пробела — POSIX [[:space:]].
SELECT concat('obj=', e.name, ' модуль_формы=', fe.name, ' формат=', COALESCE(fe.ext_format, '-'),
              ' объявлений_процедур=', regexp_count(fe.ext, 'Процедура[[:space:]]') + regexp_count(fe.ext, 'Функция[[:space:]]'),
              ' есть_экспорт=', (regexp_count(fe.ext, 'Экспорт') > 0)::text)
FROM form_ext fe JOIN external_report e ON e.uuid = fe.parent_uuid
WHERE COALESCE(fe.ext, '') <> ''
ORDER BY e.id;
SELECT concat('obj=', e.name, ' макет=', t.name, ' root_tag=', COALESCE(t.ext_root_tag, '-'))
FROM templates t JOIN external_report e ON e.uuid = t.parent_uuid
WHERE t.ext LIKE '%DataCompositionSchema%'
ORDER BY e.id;

SELECT '=== 16. Типы форм и заполненность содержимого (V14: у ordinary-формы ext заполнен) ===' AS section;
SELECT concat('obj=', e.name, ' form=', f.name, ' form_type=', COALESCE(f.form_type, '-'),
              ' ext_format=', COALESCE(fe.ext_format, '-'),
              ' ext_chars=', length(COALESCE(fe.ext, ''))::text,
              ' ext_bin_bytes=', COALESCE(length(fe.ext_bin)::text, '-'),
              ' items_len=', CASE WHEN jsonb_typeof(fe.items) = 'array'
                                 THEN jsonb_array_length(fe.items)::text ELSE '-' END,
              ' events_len=', CASE WHEN jsonb_typeof(fe.events) = 'array'
                                  THEN jsonb_array_length(fe.events)::text ELSE '-' END,
              ' ext_path=', COALESCE(fe.ext_path, '-'))
FROM forms f
JOIN external_report e ON e.uuid = f.parent_uuid
LEFT JOIN form_ext fe ON fe.form_id = f.id
ORDER BY e.id, f.name;
-- После V14 заполненный ext обязателен для ОБЕИХ разновидностей форм:
-- Managed — из Forms/<Имя>/Ext/Form/Module.bsl (V13), Ordinary — из 0/module контейнера
-- Form.bin (V14). Пустой ext = дефект, а не «норма до V14».
SELECT 'форм Managed с заполненным ext = ' || count(*)
FROM forms f JOIN form_ext fe ON fe.form_id = f.id
WHERE f.form_type = 'Managed' AND length(fe.ext) > 0;
SELECT 'форм Ordinary с заполненным ext (Ожидание V14: 1) = ' || count(*)
FROM forms f JOIN form_ext fe ON fe.form_id = f.id
WHERE f.form_type = 'Ordinary' AND length(fe.ext) > 0;
SELECT 'форм Ordinary с пустым ext (ДЕФЕКТ V14: модуль не извлечён) = ' || count(*)
FROM forms f JOIN form_ext fe ON fe.form_id = f.id
WHERE f.form_type = 'Ordinary' AND (fe.ext IS NULL OR length(fe.ext) = 0);
SELECT 'форм Ordinary без ext_bin (дефект: содержимое потеряно) = ' || count(*)
FROM forms f JOIN form_ext fe ON fe.form_id = f.id
WHERE f.form_type = 'Ordinary' AND fe.ext_bin IS NULL;

SELECT '=== 17. Инварианты V14: ext_size = octet_length(ext_bin), путь на Form.bin ===' AS section;
-- ext_size описывает ДВОИЧНОЕ содержимое (Form.bin целиком), а не текст модуля: менять
-- формат ext (NULL -> bin) загрузчик не вправе, иначе инвариант V13 нарушается.
SELECT 'нарушений инварианта ext_size/формата/пути = ' || count(*) || ' (Ожидание: 0)'
FROM form_ext fe JOIN forms f ON f.id = fe.form_id
WHERE f.form_type = 'Ordinary'
  AND (fe.ext_bin IS NULL
       OR fe.ext_format <> 'bin'
       OR fe.ext_truncated
       OR fe.ext_size IS DISTINCT FROM octet_length(fe.ext_bin)
       OR fe.ext_path NOT LIKE '%Form.bin');
SELECT 'дублей модуля ordinary-формы в bsl_modules (правило R9) = ' || count(*)
       || ' (Ожидание: 0)'
FROM bsl_modules b
WHERE b.parent_uuid IN (SELECT parent_uuid FROM form_ext WHERE ext_format = 'bin')
  AND (b.module_type = 'FormModule'
       OR lower(replace(b.file_path, chr(92), '/')) LIKE '%/form/module.bsl%'
       OR b.code LIKE '%ДействияФормыОтчетСформировать%');
-- V15: состав ordinary-формы разложен загрузчиком из 0/form контейнера Form.bin в те же
-- колонки, что и разбор Form.xml. Пустые items/attributes/events/commands — ДЕФЕКТ разбора
-- (при отсутствии v8unpack загрузка даёт предупреждение, и тогда такие нули объяснимы:
-- см. карточку загрузки).
-- jsonb_array_length падает на не-массиве, поэтому тип проверяется через CASE, а не OR.
SELECT 'ordinary-форм с пустыми items (ДЕФЕКТ V15: состав не разложен) = ' || count(*)
FROM form_ext fe JOIN forms f ON f.id = fe.form_id
WHERE f.form_type = 'Ordinary'
  AND CASE WHEN jsonb_typeof(fe.items) = 'array'
           THEN jsonb_array_length(fe.items) = 0 ELSE true END;
SELECT 'ordinary-форм с заполненными attributes/events/commands и auto_command_bar '
       || '(Ожидание V15: 1) = ' || count(*)
FROM form_ext fe JOIN forms f ON f.id = fe.form_id
WHERE f.form_type = 'Ordinary'
  AND jsonb_typeof(fe.attributes) = 'array' AND jsonb_array_length(fe.attributes) > 0
  AND jsonb_typeof(fe.events) = 'array' AND jsonb_array_length(fe.events) > 0
  AND jsonb_typeof(fe.commands) = 'array' AND jsonb_array_length(fe.commands) > 0
  AND jsonb_typeof(fe.auto_command_bar) = 'object'
  AND (fe.auto_command_bar ->> 'name') IS NOT NULL;

SELECT '=== 18. Состав форм через витрины анализа (migrate_v14_form_analysis_views.sql) ===' AS section;
SELECT report_name, form_name, COALESCE(form_type, '-') AS form_type,
       count(*) AS elements, count(data_source) AS with_data_source,
       count(caption_ru) AS with_caption
FROM v_form_elements GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
SELECT 'элементов ordinary-формы через v_form_elements (Ожидание V15: 10) = ' || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary';
-- Эталон V15 для Test2_Otchet (обычная форма «Отчет», версия разметки 0/form = 27):
-- 10 элементов (страница + 9 элементов), из них 3 привязаны к источникам данных формы,
-- у 4 есть подпись (надписи), типы разложены у всех; событие формы — 1 (ПередОткрытием).
SELECT 'ordinary-элементов с типом (Ожидание V15: 10) = ' || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary' AND element_kind IS NOT NULL;
SELECT 'ordinary-элементов с источником данных (Ожидание V15: 3) = ' || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary' AND data_source IS NOT NULL;
SELECT 'ordinary-элементов с подписью (Ожидание V15: 4) = ' || count(*)
FROM v_form_elements WHERE form_type = 'Ordinary' AND caption_ru IS NOT NULL;
SELECT 'событий ordinary-формы через v_form_events (Ожидание V15: 1) = ' || count(*)
FROM v_form_events WHERE form_type = 'Ordinary';
-- Имена и подписи элементов ordinary-формы — те же колонки витрины, что и у Managed:
-- расхождения ключей (kind/type, datapath/data_source, title/captions) закрыты COALESCE.
SELECT concat('form=', form_name, ' path=', COALESCE(element_path, '-'),
              ' kind=', COALESCE(element_kind, '-'),
              ' data_source=', COALESCE(data_source, '-'),
              ' caption=', COALESCE(caption_ru, '-'))
FROM v_form_elements WHERE form_type = 'Ordinary' ORDER BY ordinal;
SELECT concat('obj=', ve.report_name, ' form=', ve.form_name, ' event=', ve.event_name,
              ' handler=', COALESCE(ve.handler_name, '-'),
              ' обработчик в тексте модуля=',
              (position(ve.handler_name IN fe.ext) > 0)::text)
FROM v_form_events ve
JOIN form_ext fe ON fe.form_uuid = ve.form_uuid
ORDER BY 1;


SELECT '=== 19. Скалярные свойства содержимого формы (V14.1) ===' AS section;
-- Свойства берутся из КОРНЯ Form.xml (в XML содержимого формы нет обёртки <Properties>, в
-- отличие от XML метаданных). У управляемой формы отчёта они заданы в выгрузке, поэтому
-- пустые колонки — дефект разбора. У ordinary-формы (Form.bin) скалярные свойства не
-- разбираются — это ожидаемые NULL: узел V15 разложил состав элементов
-- (items/attributes/events/commands/auto_command_bar), скаляры из Form.bin в него не входили.
-- У формы внешней обработки ReportFormType и свойства
-- результата отчёта могут отсутствовать законно (проверка считаем только для Managed+xml).
SELECT concat('obj=', e.name, ' form=', fe.name, ' формат=', COALESCE(fe.ext_format, '-'),
              ' command_bar_location=', COALESCE(fe.command_bar_location, '<NULL>'),
              ' report_result=', COALESCE(fe.report_result, '<NULL>'),
              ' details_data=', COALESCE(fe.details_data, '<NULL>'),
              ' report_form_type=', COALESCE(fe.report_form_type, '<NULL>'),
              ' auto_show_state=', COALESCE(fe.auto_show_state, '<NULL>'),
              ' view_mode=', COALESCE(fe.report_result_view_mode, '<NULL>'),
              ' app_view_mode=', COALESCE(fe.view_mode_application_on_set_report_result, '<NULL>'),
              ' settings_folder=', COALESCE(fe.custom_settings_folder, '<NULL>'))
FROM external_report e
JOIN forms f ON f.parent_uuid = e.uuid
JOIN form_ext fe ON fe.form_id = f.id
ORDER BY 1;
SELECT 'управляемых форм с Form.xml и пустым report_form_type (ДЕФЕКТ V14.1: не разобрано) = ' || count(*)
FROM form_ext fe JOIN forms f ON f.id = fe.form_id
WHERE f.form_type = 'Managed' AND fe.ext_format = 'xml' AND fe.report_form_type IS NULL;
SELECT 'управляемых форм с заполненными report_result и report_form_type (Ожидание V14.1: 1) = ' || count(*)
FROM form_ext fe JOIN forms f ON f.id = fe.form_id
WHERE f.form_type = 'Managed' AND fe.report_result IS NOT NULL AND fe.report_form_type IS NOT NULL;


SELECT '=== 20. Обогащение V17: счётчики по объекту (витрина против прямого подсчёта) ===' AS section;
-- Витрина v_config_enrichment обязана сходиться с прямым подсчётом по тем же таблицам:
-- расхождение значит, что в витрине потеряно условие (origin, active, JOIN к сниппету).
SELECT concat('obj=', v.report_name, ' aliases=', v.aliases_total, ' manual=', v.aliases_manual,
              ' на_цели_сниппеты=', v.aliases_snippet, ' snippets=', v.snippets,
              ' deps=', v.snippet_dependencies, ' doc_links=', v.doc_links)
FROM v_config_enrichment v ORDER BY 1;
SELECT 'расхождений витрины с прямым подсчётом (должно быть 0) = ' || count(*)
FROM v_config_enrichment v
CROSS JOIN LATERAL (
    SELECT (SELECT count(*) FROM config_aliases a
             WHERE a.parent_uuid = v.report_uuid) AS aliases,
           (SELECT count(*) FROM config_snippets s
             WHERE s.parent_uuid = v.report_uuid) AS snippets,
           (SELECT count(*) FROM config_snippet_dependencies d
              JOIN config_snippets s ON s.id = d.snippet_id
             WHERE s.parent_uuid = v.report_uuid) AS deps,
           (SELECT count(*) FROM config_cross_references x
             WHERE x.parent_uuid = v.report_uuid) AS links
) c
WHERE v.aliases_total <> c.aliases OR v.snippets <> c.snippets
   OR v.snippet_dependencies <> c.deps OR v.doc_links <> c.links;

SELECT '=== 21. Обогащение V17: сироты (должно быть 0) ===' AS section;
-- FK в подсистеме один: зависимость -> сниппет (ON DELETE CASCADE). Остальные связи
-- полиморфные по parent_uuid, поэтому сироты ловятся только запросом (правило E3 плана).
SELECT 'алиасов без родителя в external_report = ' || count(*) FROM config_aliases a
WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = a.parent_uuid);
SELECT 'сниппетов без родителя в external_report = ' || count(*) FROM config_snippets s
WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = s.parent_uuid);
SELECT 'связей documentation без родителя в external_report = ' || count(*)
FROM config_cross_references x
WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = x.parent_uuid);
SELECT 'зависимостей без сниппета (FK это исключает, проверяем на всякий случай) = ' || count(*)
FROM config_snippet_dependencies d
WHERE NOT EXISTS (SELECT 1 FROM config_snippets s WHERE s.id = d.snippet_id);
SELECT 'алиасов на несуществующий сниппет (target_snippet_id) = ' || count(*) FROM config_aliases a
WHERE a.target_snippet_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM config_snippets s WHERE s.id = a.target_snippet_id);


SELECT '=== 22. Обогащение V17: цели разрешимы в сохранённом содержимом (битых = 0) ===' AS section;
-- Словарь целей = ТО ЖЕ, что строит генератор (docs/CONFIGURATIONS_ENRICHMENT_PLAN.md, раздел 3):
-- uuid строк выгрузки, module:<id bsl_modules>, module:form:<uuid формы>,
-- form_item:<uuid формы>:<имя элемента>, snippet:<id сниппета>.
WITH content_targets(target_uuid) AS (
    SELECT uuid::text FROM external_report
    UNION ALL SELECT uuid::text FROM attributes
    UNION ALL SELECT uuid::text FROM tabular_sections
    UNION ALL SELECT uuid::text FROM forms
    UNION ALL SELECT uuid::text FROM templates
    UNION ALL SELECT 'module:' || id::text FROM bsl_modules
    UNION ALL SELECT 'module:form:' || form_uuid::text FROM form_ext WHERE ext IS NOT NULL
    UNION ALL SELECT 'snippet:' || id::text FROM config_snippets
    UNION ALL SELECT 'form_item:' || fe.form_uuid::text || ':' || (item ->> 'name')
        FROM form_ext fe
        CROSS JOIN LATERAL jsonb_array_elements(
            CASE WHEN jsonb_typeof(fe.items) = 'array' THEN fe.items ELSE '[]'::jsonb END
        ) AS item
        WHERE item ->> 'name' IS NOT NULL
)
SELECT 'неразрешимых целей: алиасов=' ||
       (SELECT count(*) FROM config_aliases a
         WHERE a.active AND a.target_key IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM content_targets c WHERE c.target_uuid = a.target_key)) ||
       ', зависимостей=' ||
       (SELECT count(*) FROM config_snippet_dependencies d
         WHERE NOT EXISTS (SELECT 1 FROM content_targets c WHERE c.target_uuid = d.target_uuid)) ||
       ' (должно быть 0 и 0)';
SELECT 'зависимостей с пустым target_uuid (резолв обязателен, должно быть 0) = ' || count(*)
FROM config_snippet_dependencies d WHERE d.target_uuid IS NULL;


SELECT '=== 23. Обогащение V17: происхождение и дубли (manual и generated не смешиваются) ===' AS section;
-- Перегенерация снимает ТОЛЬКО origin='generated' и is_verified=false; ручные данные обязаны
-- выживать (сама проверка выживания — validate_enrichment_flow.py, здесь — инварианты схемы).
SELECT 'алиасов с неизвестным origin (должно быть 0) = ' || count(*) FROM config_aliases
WHERE origin NOT IN ('generated', 'manual');
SELECT 'ручных сниппетов, помеченных generated (должно быть 0) = ' || count(*)
FROM config_snippets WHERE is_verified AND source_kind = 'generated';
SELECT 'дублей активного алиаса (alias_norm, target_key) = ' || count(*) FROM (
    SELECT alias_norm, target_key FROM config_aliases WHERE active
    GROUP BY 1, 2 HAVING count(*) > 1) d;
SELECT 'дублей сниппета (parent_uuid, source_kind, question) = ' || count(*) FROM (
    SELECT parent_uuid, source_kind, question FROM config_snippets
    GROUP BY 1, 2, 3 HAVING count(*) > 1) d;
SELECT 'дублей зависимости (snippet_id, dependency_type, target_type, target_name) = ' || count(*)
FROM (
    SELECT snippet_id, dependency_type, target_type, target_name FROM config_snippet_dependencies
    GROUP BY 1, 2, 3, 4 HAVING count(*) > 1) d;
SELECT 'связей documentation с недопустимым local_doc_kind (должно быть 0) = ' || count(*)
FROM config_cross_references WHERE local_doc_kind NOT IN ('group', 'snippet');

