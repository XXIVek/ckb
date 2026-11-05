-- ==========================================================================
-- check_external_report_inventory.sql — инвентарь «что видно из БД без
-- распаковки Form.bin». Сессия 13.10.2026, задача 1.
--
-- Назначение: показать, какие сведения о внешнем отчёте доступны напрямую из
-- ckb_1c_configurations (карточка объекта, реквизиты и колонки ТЧ, свойства и
-- содержимое форм, модули, макеты, витрины), а какие остаются «слепой зоной».
-- Вывод этого файла — источник для отчёта
--   docs/config-scenarios/ANALYSIS_2026-10-13_content_inventory.md
--
-- Запуск (метки разделов печатает SQL, \echo в -o файл не пишется):
--   $env:PGCLIENTENCODING='UTF8'; $env:PGPASSWORD='Sta090860'
--   C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost `
--     -d ckb_1c_configurations -P pager=off -f check_external_report_inventory.sql `
--     -o _v15_inventory_out.txt
--
-- Отличия от check_external_report_fill.sql: тот проверяет инварианты (числа
-- должны совпасть с ожиданием), этот — описывает состав (что вообще видно).
-- Пустой jsonb-массив не считается заполненным: используется jsonb_typeof и
-- jsonb_array_length, а не IS NOT NULL.
--
-- Ожидания эталонной пары после V14/V15:
--   Test1_Otchet — управляемая форма: содержимое (items/attributes/events/commands/
--     auto_command_bar и скаляры) берётся из Form.xml (V13/V14.1), модуль — из Form/Module.bsl;
--   Test2_Otchet — обычная форма «Отчет»: модуль из 0/module (V14), состав из 0/form (V15):
--     items 10, attributes 4, events 1, commands 1, auto_command_bar «ДействияФормы».
-- Слепые зоны, оставшиеся после V15: скалярные свойства ordinary-формы (Form.xml для неё
-- не выгружается) и заголовок ordinary-формы — декодер его читает, но колонки под него в
-- form_ext нет (DDL узла V15 не менялся), поэтому в БД он не сохраняется.
-- ==========================================================================

SELECT '### 0. колонки целевых таблиц' AS section;
SELECT table_name || ': ' || string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position)
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('external_report','forms','form_ext','templates','attributes','tabular_sections','bsl_modules')
GROUP BY table_name ORDER BY table_name;

SELECT '### 1. сводка по внешним объектам и их детям' AS section;
SELECT e.id, e.name, e.uuid,
       (SELECT count(*) FROM attributes a       WHERE a.parent_uuid  = e.uuid) AS attrs,
       (SELECT count(*) FROM tabular_sections t WHERE t.parent_uuid  = e.uuid) AS ts,
       (SELECT count(*) FROM forms f            WHERE f.parent_uuid  = e.uuid) AS forms,
       (SELECT count(*) FROM templates tp       WHERE tp.parent_uuid  = e.uuid) AS templates,
       (SELECT count(*) FROM bsl_modules b      WHERE b.parent_uuid  = e.uuid) AS bsl
FROM external_report e ORDER BY e.id;

SELECT '### 2. инвентаризация форм: тип и чем реально наполнено' AS section;
SELECT f.id, f.name, f.form_type, fe.ext_format,
       (fe.ext      IS NOT NULL) AS has_ext,   (fe.ext_bin    IS NOT NULL) AS has_bin,
       (fe.items    IS NOT NULL) AS has_items, (fe.events     IS NOT NULL) AS has_events,
       (fe.commands IS NOT NULL) AS has_cmd,   (fe.attributes IS NOT NULL) AS has_attrs,
       (fe.auto_command_bar IS NOT NULL) AS has_acb,
       length(fe.ext) AS ext_len, octet_length(fe.ext_bin) AS bin_len
FROM forms f LEFT JOIN form_ext fe ON fe.form_id = f.id
ORDER BY f.name;

SELECT '### 2b. скалярные свойства form_ext по обеим формам' AS section;
SELECT fe.name, fe.command_bar_location, fe.report_result, fe.details_data, fe.report_form_type,
       fe.auto_show_state, fe.custom_settings_folder, fe.report_result_view_mode,
       fe.view_mode_application_on_set_report_result, fe.ext_size, fe.ext_truncated, fe.ext_path
FROM form_ext fe ORDER BY fe.name;

SELECT '### 3. структура jsonb управляемой формы (ключи верхнего уровня items)' AS section;
SELECT fe.name,
       jsonb_typeof(fe.items)     AS items_type,
       CASE WHEN jsonb_typeof(fe.items) = 'array' THEN jsonb_array_length(fe.items) END AS n_items,
       jsonb_typeof(fe.events)    AS events_type,
       jsonb_typeof(fe.attributes) AS attrs_type,
       jsonb_typeof(fe.commands)  AS cmd_type,
       jsonb_typeof(fe.auto_command_bar) AS acb_type
FROM form_ext fe ORDER BY fe.name;

SELECT '### 3b. ключи первого элемента items управляемой формы' AS section;
SELECT fe.name AS form, k AS item_key, t AS item_type
FROM form_ext fe
CROSS JOIN LATERAL jsonb_object_keys(fe.items -> 0) AS k
CROSS JOIN LATERAL jsonb_typeof(fe.items -> 0 -> k) AS t
WHERE jsonb_typeof(fe.items) = 'array' AND jsonb_array_length(fe.items) > 0
ORDER BY fe.name, item_key;

SELECT '### 3c. элементы управляемой формы (name/type) — как устроена витрина для Managed' AS section;
SELECT fe.name AS form,
       e -> 'name' AS name_raw,
       e -> 'type' AS type_raw,
       left(e::text, 300) AS item_head
FROM form_ext fe
CROSS JOIN LATERAL jsonb_array_elements(fe.items) AS e
WHERE jsonb_typeof(fe.items) = 'array'
ORDER BY fe.name;

SELECT '### 4. модули BSL: кто есть кто' AS section;
SELECT b.id, b.parent_type, b.module_type, b.file_path, b.code_size, b.truncated,
       (b.code IS NOT NULL) AS has_code
FROM bsl_modules b ORDER BY b.parent_type, b.module_type;

SELECT '### 5. макеты: тип содержимого и размер' AS section;
SELECT tp.id, tp.name, tp.ext_root_tag, length(tp.ext) AS ext_len, octet_length(tp.ext_bin) AS bin_len,
       (tp.ext IS NOT NULL) AS has_ext, (tp.ext_bin IS NOT NULL) AS has_bin
FROM templates tp ORDER BY tp.name;

SELECT '### 6. целостность: сироты и дубли' AS section;
SELECT count(*) AS orphan_form_ext FROM form_ext fe LEFT JOIN forms f ON f.id = fe.form_id WHERE f.id IS NULL;
SELECT count(*) AS orphan_bsl FROM bsl_modules b LEFT JOIN external_report e ON e.uuid = b.parent_uuid
WHERE b.parent_uuid IS NOT NULL AND e.id IS NULL;
SELECT count(*) AS dup_forms FROM (SELECT parent_uuid, uuid FROM forms GROUP BY 1,2 HAVING count(*) > 1) d;
SELECT count(*) AS orphan_attributes FROM attributes a LEFT JOIN external_report e ON e.uuid = a.parent_uuid WHERE e.id IS NULL;

SELECT '### 7. классификация состояния обычных форм (после V14/V15 ожидаем OK)' AS section;
-- V15: состав elements layout (0/form) разкладывается загрузчиком в items/attributes/events/
-- commands/auto_command_bar, поэтому «ожидания» больше нет — пустые колонки ordinary-формы
-- это ДЕФЕКТ (или следствие отсутствующего v8unpack: тогда в карточке загрузки предупреждение).
SELECT f.name,
       CASE WHEN fe.ext_bin IS NULL THEN 'ДЕФЕКТ: Ordinary без ext_bin'
            WHEN fe.ext IS NULL     THEN 'ДЕФЕКТ V14: модуль формы не извлечён из ext_bin'
            WHEN CASE WHEN jsonb_typeof(fe.items) = 'array'
                      THEN jsonb_array_length(fe.items) = 0 ELSE true END
                 THEN 'ДЕФЕКТ V15: состав 0/form не разложен'
            ELSE 'OK' END AS state,
       length(fe.ext) AS ext_len,
       CASE WHEN jsonb_typeof(fe.items) = 'array' THEN jsonb_array_length(fe.items) END AS n_items,
       CASE WHEN jsonb_typeof(fe.attributes) = 'array'
            THEN jsonb_array_length(fe.attributes) END AS n_attributes,
       CASE WHEN jsonb_typeof(fe.events) = 'array' THEN jsonb_array_length(fe.events) END AS n_events,
       CASE WHEN jsonb_typeof(fe.commands) = 'array'
            THEN jsonb_array_length(fe.commands) END AS n_commands
FROM forms f JOIN form_ext fe ON fe.form_id = f.id WHERE f.form_type = 'Ordinary';
-- Эталон Test2_Otchet: n_items = 10, n_attributes = 4, n_events = 1, n_commands = 1.

SELECT '### 8. реквизиты/ТЧ/синонимы эталона — что видно без распаковки' AS section;
SELECT e.name AS report, e.synonym IS NOT NULL AS has_synonym, e.comment IS NOT NULL AS has_comment,
       e.default_form, e.main_data_composition_schema, e.variants_storage, e.settings_storage,
       e.generatedtype_name, e.generatedtype_category
FROM external_report e ORDER BY e.name;
SELECT '--- 8b. attributes: наполненность по колонкам ---' AS section;
SELECT count(*) AS n,
       count(synonym) AS synonym, count(comment) AS comment, count(type) AS type,
       count(format) AS format, count(editformat) AS editformat, count(mask) AS mask,
       count(choice_parameter_links) AS choice_links, count(choice_parameters) AS choice_params,
       count(fill_value) AS fill_value, count(link_by_type) AS link_by_type
FROM attributes;
SELECT '--- 8c. реквизиты объекта (не колонки ТЧ) ---' AS section;
SELECT a.parent_uuid, a.name, a.synonym -> 'ru' AS synonym_ru, left(a.type, 120) AS type_head
FROM attributes a
WHERE NOT EXISTS (SELECT 1 FROM tabular_sections ts WHERE ts.column_uuids @> jsonb_build_array(a.uuid))
ORDER BY a.parent_uuid, a.name;
SELECT '--- 8d. табличные части и число колонок ---' AS section;
SELECT ts.name, ts.synonym -> 'ru' AS synonym_ru,
       ts.internalinfo_generatedtype IS NOT NULL AS has_gen_type,
       jsonb_array_length(ts.column_uuids) AS n_cols
FROM tabular_sections ts ORDER BY ts.name;

SELECT '### 9. модули: два источника (bsl_modules для Ext/, form_ext.ext для формы)' AS section;
SELECT 'bsl_modules' AS source, b.parent_type AS obj, b.module_type AS kind, b.file_path AS source_ref,
       b.code_size AS size, length(b.code) - length(replace(b.code, chr(10), '')) + 1 AS lines
FROM bsl_modules b
UNION ALL
SELECT 'form_ext.ext', fe.parent_type, fe.name || ' (FormModule)', fe.ext_path,
       length(fe.ext), length(fe.ext) - length(replace(fe.ext, chr(10), '')) + 1
FROM form_ext fe WHERE fe.ext IS NOT NULL
ORDER BY 1, 2, 3;

SELECT '### 9b. объявлений процедур/функций по каждому модулю' AS section;
SELECT 'bsl_modules' AS source, b.module_type AS kind,
       (length(b.code) - length(replace(lower(b.code), 'процедура ', ''))) / 10
     + (length(b.code) - length(replace(lower(b.code), 'функция ', ''))) / 9 AS decls
FROM bsl_modules b
UNION ALL
SELECT 'form_ext.ext', fe.name,
       (length(fe.ext) - length(replace(lower(fe.ext), 'процедура ', ''))) / 10
     + (length(fe.ext) - length(replace(lower(fe.ext), 'функция ', ''))) / 9
FROM form_ext fe WHERE fe.ext IS NOT NULL
ORDER BY 1, 2;
-- 9c. Структура attributes.type: типы и квалификаторы. Колонка текстовая (JSON-строка),
--     поэтому для анализа нужен каст: (type::jsonb -> 'types' ->> 0).
SELECT '### 9c. содержимое attributes.type (каст JSON-строки)' AS section;
SELECT e.name AS report, a.name, a.type::jsonb -> 'types' ->> 0 AS type_first,
       (a.type::jsonb -> 'qualifiers' -> 'StringQualifiers' ->> 'AllowedLength') AS allowed_length,
       (a.type::jsonb -> 'qualifiers' -> 'NumberQualifiers' ->> 'Precision') AS number_precision,
       (a.type::jsonb -> 'qualifiers' -> 'DateQualifiers' -> 'DateQualifiers' ->> 0) AS date_qualifiers,
       (a.type::jsonb -> 'qualifiers' -> 'EnumQualifiers' -> 'EnumTypes' ->> 0) AS enum_ref,
       (a.type::jsonb -> 'qualifiers' -> 'GuidQualifiers' IS NOT NULL) AS is_guid
FROM attributes a JOIN external_report e ON e.uuid = a.parent_uuid
WHERE a.type IS NOT NULL
ORDER BY e.name, type_first, a.name;
SELECT '### 9d. типы данных реквизитов: сводка' AS section;
SELECT e.name AS report, a.type::jsonb -> 'types' ->> 0 AS type_first, count(*) AS n
FROM attributes a JOIN external_report e ON e.uuid = a.parent_uuid
GROUP BY 1, 2 ORDER BY 1, n DESC, type_first;
SELECT '### 9e. стандартные реквизиты табличных частей' AS section;
SELECT e.name AS report, ts.name AS tabular_section, jsonb_array_length(ts.standardattributes) AS n_std_attrs,
       (SELECT string_agg(s ->> 'name', ', ' ORDER BY s ->> 'name')
          FROM jsonb_array_elements(ts.standardattributes) s) AS std_attr_names
FROM tabular_sections ts JOIN external_report e ON e.uuid = ts.parent_uuid
ORDER BY e.name, ts.name;


SELECT '### 10. витрины v_form_elements / v_form_events (один источник для Managed и Ordinary)' AS section;
-- источник различается колонкой ext_format: 'xml' = Form.xml (V13), 'bin' = Form.bin (V15)
SELECT 'v_form_elements' AS view, count(*) AS rows_total,
       count(*) FILTER (WHERE ext_format = 'xml') AS from_managed_xml,
       count(*) FILTER (WHERE ext_format = 'bin') AS from_ordinary_bin,
       count(data_source) AS with_data_source, count(caption_ru) AS with_caption
FROM v_form_elements;
SELECT '--- 10b. v_form_events ---' AS section;
SELECT 'v_form_events' AS view, count(*) AS rows_total,
       count(*) FILTER (WHERE ext_format = 'xml') AS from_managed_xml,
       count(*) FILTER (WHERE ext_format = 'bin') AS from_ordinary_bin,
       count(handler_name) AS with_handler
FROM v_form_events;
SELECT '--- 10c. состав витрин по объектам ---' AS section;
SELECT report_name, form_name, form_type, ext_format, count(*) AS elements
FROM v_form_elements GROUP BY 1,2,3,4 ORDER BY 1,2,3,4;
SELECT '--- 10d. события по объектам ---' AS section;
SELECT report_name, form_name, form_type, ext_format, event_name, COALESCE(handler_name, '-') AS handler_name
FROM v_form_events ORDER BY 1,2,3,4,5;
SELECT '--- 10e. типы элементов в витрине (после V15 ожидаем TableField/ListField/Label/Field) ---' AS section;
SELECT COALESCE(element_kind, '-') AS element_kind, COALESCE(element_type, '-') AS element_type,
       ext_format, count(*) AS n
FROM v_form_elements GROUP BY 1,2,3 ORDER BY 3, 1, 2;

SELECT '### 11. слепые зоны: что НЕ видно без распаковки Form.bin' AS section;
-- После V15 все четыре флага для ordinary-формы обязаны быть false: состав разкладывается
-- при загрузке из 0/form. Настоящие слепые зоны после V15 — скалярные свойства ordinary-формы
-- (для неё Form.xml не выгружается) и её заголовок (колонки под него в form_ext нет).
SELECT f.name AS form, f.form_type,
       (fe.items IS NULL OR jsonb_array_length(fe.items) = 0) AS items_empty,
       (fe.attributes IS NULL OR jsonb_array_length(fe.attributes) = 0) AS attributes_empty,
       (fe.events IS NULL OR jsonb_array_length(fe.events) = 0) AS events_empty,
       (fe.commands IS NULL OR jsonb_array_length(fe.commands) = 0) AS commands_empty
FROM forms f JOIN form_ext fe ON fe.form_id = f.id
ORDER BY f.form_type, f.name;
SELECT 'форм с незаполненным составом (Ожидание V15: 0) = ' || count(*)
FROM forms f JOIN form_ext fe ON fe.form_id = f.id
WHERE (fe.items IS NULL OR jsonb_array_length(fe.items) = 0)
   OR (fe.attributes IS NULL OR jsonb_array_length(fe.attributes) = 0)
   OR (fe.events IS NULL OR jsonb_array_length(fe.events) = 0)
   OR (fe.commands IS NULL OR jsonb_array_length(fe.commands) = 0);

-- 12. Заполненность второстепенных колонок: пусто по источнику или не разобрано.
-- Смысл колонки note: отличить «свойства нет в выгрузке» (норма) от
-- «свойство в выгрузке есть, но мы его не сохраняем» (слепая зона / дефект).
SELECT '### 12. заполненность второстепенных колонок' AS section;
SELECT col, filled, total, note FROM (
    SELECT 'external_report.configuration_id (привязка к конфигурации)' AS col,
           count(*) FILTER (WHERE configuration_id IS NOT NULL) AS filled,
           count(*) AS total,
           'узел V20/V20.1: заявляется только оператором (id строки configurations.id); внешнего '
             || 'ключа в схеме нет осознанно — битой ссылки не создаёт инструмент, а потерянная '
             || 'ссылка видна состоянием «битая» (раздел 15f); пусто = «привязка не заявлена», '
             || 'а НЕ «отчёт универсальный»; из выгрузки 1С не берётся' AS note
    FROM external_report
    UNION ALL
    SELECT 'forms.synonym' AS col,
           count(*) FILTER (WHERE synonym IS NOT NULL AND synonym <> '{}'::jsonb) AS filled,
           count(*) AS total,
           'подпись формы из Forms/<Имя>.xml; у ordinary {} — заголовок ordinary-формы декодер V15 читает из 0/form, но колонки под него в form_ext нет' AS note
    FROM forms
    UNION ALL
    SELECT 'forms.use_purposes', count(*) FILTER (WHERE jsonb_array_length(use_purposes) > 0),
           count(*), 'назначения формы (usePurposes) в выгрузке не заданы — []' FROM forms
    UNION ALL
    SELECT 'forms.include_help_in_contents', count(*) FILTER (WHERE include_help_in_contents),
           count(*), 'булево false — значение по умолчанию, это не дефект' FROM forms
    UNION ALL
    SELECT 'form_ext.auto_command_bar (не пустой)',
           count(*) FILTER (WHERE jsonb_typeof(auto_command_bar) = 'object'
                              AND auto_command_bar <> '{}'::jsonb),
           count(*), 'у managed — id/name/autofill панели; у ordinary — name/presentation/items панели действий из 0/form, узел V15'
             FROM form_ext
    UNION ALL
    SELECT 'form_ext скаляр report_form_type', count(*) FILTER (WHERE report_form_type IS NOT NULL),
           count(*), 'V14.1: читается из корня Form.xml; у ordinary пусто (Form.xml отсутствует)'
             FROM form_ext
    UNION ALL
    SELECT 'form_ext.ext (текст модуля формы)', count(*) FILTER (WHERE ext IS NOT NULL), count(*),
           'V14: у ordinary берётся из 0/module внутри ext_bin' FROM form_ext
    UNION ALL
    SELECT 'form_ext.ext_truncated', count(*) FILTER (WHERE ext_truncated), count(*),
           'порог MAX_TEXT_CHARS = 1 000 000 символов' FROM form_ext
    UNION ALL
    SELECT 'tabular_sections.standardattributes (не пустой)',
           count(*) FILTER (WHERE jsonb_typeof(standardattributes) = 'array'
                              AND standardattributes <> '[]'::jsonb),
           count(*), 'стандартные реквизиты ТЧ (LineNumber и т.п.) сохраняются' FROM tabular_sections
    UNION ALL
    SELECT 'tabular_sections.fill_checking', count(*) FILTER (WHERE fill_checking IS NOT NULL),
           count(*), 'условие отбора при заполнении' FROM tabular_sections
    UNION ALL
    SELECT 'tabular_sections.comment', count(*) FILTER (WHERE comment IS NOT NULL), count(*),
           'в выгрузке комментариев нет' FROM tabular_sections
    UNION ALL
    SELECT 'templates.template_type', count(*) FILTER (WHERE template_type IS NOT NULL), count(*),
           'тип макета из Templates/<Имя>.xml (DataCompositionSchema / SpreadsheetDocument)'
             FROM templates
    UNION ALL
    SELECT 'templates.ext (текст макета)', count(*) FILTER (WHERE ext IS NOT NULL), count(*),
           'структура макета (датасеты, поля, настройки) НЕ разбирается — только текст' FROM templates
    UNION ALL
    SELECT 'external_report.main_data_composition_schema',
           count(*) FILTER (WHERE main_data_composition_schema IS NOT NULL), count(*),
           'ссылка на макет СКД; у ordinary-отчёта её нет по источнику' FROM external_report
    UNION ALL
    SELECT 'external_report.default_form', count(*) FILTER (WHERE default_form IS NOT NULL), count(*),
           'имя основной формы' FROM external_report
    UNION ALL
    SELECT 'external_report.variants_storage / settings_storage',
           count(*) FILTER (WHERE variants_storage IS NOT NULL OR settings_storage IS NOT NULL),
           count(*), 'в выгрузке не заданы — норма' FROM external_report
    UNION ALL
    SELECT 'attributes.type', count(*) FILTER (WHERE type IS NOT NULL), count(*),
           'JSON-строка {"types":[...],"qualifiers":{...}} в текстовой колонке — требует каста'
             FROM attributes
    UNION ALL
    SELECT 'attributes.choice_folders_and_items',
           count(*) FILTER (WHERE choice_folders_and_items IS NOT NULL), count(*),
           'значение по умолчанию 1С «Items» проставлено всем реквизитам — не признак настройки'
             FROM attributes
    UNION ALL
    SELECT 'attributes.format / mask / fill_value / choice_links',
           count(*) FILTER (WHERE format IS NOT NULL OR mask IS NOT NULL OR fill_value IS NOT NULL
                              OR choice_parameter_links IS NOT NULL),
           count(*), 'в этой выгрузке свойства не заданы — пусто по источнику, не дефект' FROM attributes
) s ORDER BY col;

-- 13. Атрибуты самой формы (её источники данных) и команды формы.
--     V15: у ordinary те же колонки заполняются из 0/form (источники данных формы, команда
--     панели «ДействияФормы»), поэтому раздел показывает обе разновидности формы.
SELECT '### 13. атрибуты формы (источники данных) и команды формы' AS section;
SELECT form, count(*) AS n_attributes_distinct,
       jsonb_agg((name, typ) ORDER BY name) AS attrs
FROM (
    SELECT DISTINCT fe.name AS form, a ->> 'name' AS name,
                    COALESCE(a ->> 'type', '-') AS typ
    FROM form_ext fe CROSS JOIN LATERAL jsonb_array_elements(fe.attributes) a
    WHERE jsonb_typeof(fe.attributes) = 'array' AND jsonb_array_length(fe.attributes) > 0
) d GROUP BY form ORDER BY form;
SELECT form, count(*) AS n_commands_distinct,
       jsonb_agg((name, act) ORDER BY name) AS cmds
FROM (
    SELECT DISTINCT fe.name AS form, c ->> 'name' AS name,
                    COALESCE(c ->> 'action', '-') AS act
    FROM form_ext fe CROSS JOIN LATERAL jsonb_array_elements(fe.commands) c
    WHERE jsonb_typeof(fe.commands) = 'array' AND jsonb_array_length(fe.commands) > 0
) d GROUP BY form ORDER BY form;
SELECT fe.name AS form, jsonb_typeof(fe.auto_command_bar) AS acb_type,
       (SELECT string_agg(k, ', ' ORDER BY k) FROM jsonb_object_keys(fe.auto_command_bar) k) AS acb_keys
FROM form_ext fe ORDER BY fe.name;

-- 14. Макеты: чем различимы из БД и что остаётся только текстом (слепая зона).
SELECT '### 14. макеты: тип, корневой тег, различимость содержимого' AS section;
SELECT name, COALESCE(template_type, '-') AS template_type, COALESCE(ext_root_tag, '-') AS ext_root_tag,
       length(ext) AS ext_chars, octet_length(ext_bin) AS ext_bin_bytes,
       (length(ext) - length(replace(ext, '<dcsset:', ''))) / 8 AS dcsset_tags,
       (length(ext) - length(replace(ext, '<dcssch:', ''))) / 8 AS dcssch_tags,
       position('SELECT' IN upper(ext)) > 0 AS has_sql_text,
       'структура макета (датасеты/поля/настройки) не разобрана — только текстовый поиск по ext' AS note
FROM templates ORDER BY name;

-- 15. Обогащение V17: что появляется ПОВЕРХ сохранённого содержимого и чего не хватает.
SELECT '### 15. обогащение: счётчики по объекту (витрина v_config_enrichment)' AS section;
SELECT report_name AS obj, aliases_total, aliases_manual, aliases_snippet, snippets,
       snippet_dependencies, doc_links
FROM v_config_enrichment ORDER BY 1;

SELECT '### 15b. цели: строк-алиасов и РАЗЛИЧНЫХ целей по типам (это два разных счёта)' AS section;
SELECT target_type, count(*) AS alias_rows, count(DISTINCT target_uuid) AS distinct_targets
FROM v_config_alias_targets WHERE target_uuid IS NOT NULL
GROUP BY target_type ORDER BY target_type;

SELECT '### 15c. происхождение: что перегенерация снимает, а что нет' AS section;
SELECT CASE WHEN origin = 'manual' THEN 'manual (перегенерация не трогает)'
            ELSE 'generated (снимается и пишется заново)' END AS origin_kind, count(*)
FROM config_aliases GROUP BY 1 ORDER BY 1;
SELECT CASE WHEN is_verified THEN 'manual (перегенерация не трогает)'
            ELSE 'generated (снимается и пишется заново)' END AS snippet_kind, count(*)
FROM config_snippets GROUP BY 1 ORDER BY 1;

SELECT '### 15d. сниппеты: откуда извлечены и на что ссылаются зависимости' AS section;
SELECT s.source_kind, count(*) AS snippets, sum(count(*)) OVER () AS total
FROM config_snippets s GROUP BY s.source_kind ORDER BY 2 DESC, 1;
SELECT d.dependency_type, d.target_type, count(*) AS deps
FROM config_snippet_dependencies d GROUP BY 1, 2 ORDER BY 3 DESC, 1, 2;

SELECT '### 15e. узел A: запросы наборов данных макета разобраны в сниппеты' AS section;
SELECT 'макетов, в ext которых есть <query> = ' || count(*)
FROM templates
WHERE ext IS NOT NULL
  AND (position('<query>' IN ext) > 0 OR position(':query>' IN ext) > 0);
SELECT 'сниппетов template_query = ' || count(*)
       || ' (авто ' || count(*) FILTER (WHERE NOT is_verified)
       || ', ручных ' || count(*) FILTER (WHERE is_verified)
       || '; с целью Template ' || count(*) FILTER (WHERE target_type = 'Template') || ')'
FROM config_snippets WHERE source_kind = 'template_query';
-- СЛЕПАЯ ЗОНА была бы здесь: макет с <query>, по которого нет ни одного сниппета.
SELECT 'СЛЕПАЯ ЗОНА: макетов с <query> без сниппета = ' || count(*)
FROM templates t
WHERE t.ext IS NOT NULL
  AND (position('<query>' IN t.ext) > 0 OR position(':query>' IN t.ext) > 0)
  AND NOT EXISTS (SELECT 1 FROM config_snippets s
                   WHERE s.source_kind = 'template_query'
                     AND s.source_uuid = 'template:' || t.uuid::text);

SELECT '### 15f. привязки к конфигурации: состояния (узел V20.1 — FK снят, состояний три)' AS section;
-- Внешнего ключа external_report.configuration_id -> configurations(id) в схеме нет осознанно:
-- конфигурация — справочная система, которая нужна только при проверке данных отчёта, а FK
-- блокировал бы ведение самого справочника. Поэтому состояние «битая ссылка» возможно по
-- построению и обязано измеряться: это тот же признак, который инструменты требуют исправить
-- (перепривязка). Снимок имени/версии не хранится — состояния считаются живым JOIN.
SELECT 'объектов ' || count(*)
       || ', привязка не заявлена ' || count(*) FILTER (WHERE state = 'not_declared')
       || ', привязано ' || count(*) FILTER (WHERE state = 'bound')
       || ', битая ссылка ' || count(*) FILTER (WHERE state = 'dangling')
FROM (SELECT CASE WHEN er.configuration_id IS NULL THEN 'not_declared'
                  WHEN c.id IS NULL THEN 'dangling' ELSE 'bound' END AS state
      FROM external_report er
      LEFT JOIN configurations c ON c.id = er.configuration_id) s;
SELECT 'БИТЫХ привязок (должно быть 0 — иначе объекту нужна перепривязка) = ' || count(*)
FROM external_report er
WHERE er.configuration_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM configurations c WHERE c.id = er.configuration_id);
-- обратный перечень (его же отдаёт config_enrichment_stats_tool без uuid): без него
-- перепривязку было бы нечем искать
SELECT 'cfg id=' || c.id || ' | ' || c.name
       || ' | объектов привязано: '
       || (SELECT count(*) FROM external_report er WHERE er.configuration_id = c.id)
FROM configurations c ORDER BY c.name;
SELECT 'заголовков конфигураций в справочнике = ' || count(*) FROM configurations;
-- инфраструктура: индекс нужен обратному поиску, внешнего ключа быть не должно
SELECT 'индекс idx_external_report_configuration_id (должен быть 1) = ' || count(*)
FROM pg_indexes WHERE tablename = 'external_report'
  AND indexname = 'idx_external_report_configuration_id';
SELECT 'внешних ключей external_report_configuration_fkey (должно быть 0) = ' || count(*)
FROM pg_constraint WHERE conrelid = 'external_report'::regclass
  AND conname = 'external_report_configuration_fkey';

SELECT '### 15g. виды внешних объектов: отчёт и обработка в одной таблице (узел V22)' AS section;
-- Узел V22: заголовок внешнего объекта ОДИН (external_report), вид строки различает колонка
-- object_kind. Поэтому «сколько объектов в базе» без вида — вопрос, на который нельзя
-- ответить честно: число объектов не говорит, чего именно. Раздел измеряет и состав по видам,
-- и инварианты вида; он осмыслен и тогда, когда обработки в базе нет (тогда по виду нули, а
-- инварианты обязаны сойтись такими же нулями). Тот же набор инвариантов проверяет
-- validate_load_flow.py::check_kind_invariant, но только во время своего прогона и на своих
-- каталогах; этот раздел работает на любом состоянии базы.
SELECT 'объектов по видам: '
       || COALESCE(string_agg(object_kind || ' = ' || cnt, ', ' ORDER BY object_kind),
                   '(объектов в базе нет)') AS section_counts
FROM (SELECT COALESCE(object_kind, '(пусто)') AS object_kind, count(*) AS cnt
      FROM external_report GROUP BY COALESCE(object_kind, '(пусто)')) k;
-- словарь видов замкнут CHECK'ом: нового вида без писателя заголовка и без словаря
-- parent_type в обогащении появиться не может
SELECT 'CHECK external_report_object_kind_check (должен быть 1) = ' || count(*)
FROM pg_constraint WHERE conname = 'external_report_object_kind_check';
SELECT 'строк вне словаря видов, NULL или неизвестный (должно быть 0) = ' || count(*)
FROM external_report
WHERE object_kind IS NULL
   OR object_kind NOT IN ('external_report', 'external_processing');
-- вид строки не может противоречить ClassId из той же выгрузки. Пустой ClassId в проверку не
-- попадает: у внешнего объекта из выгрузки он бывает пуст, ожидаемое значение берётся из
-- корневого тега ExternalReport / ExternalDataProcessor, а загрузчик обязан предупредить
SELECT 'object_kind противоречит containedobject_classid (должно быть 0) = ' || count(*)
FROM external_report
WHERE COALESCE(lower(btrim(containedobject_classid::text)), '') <> ''
  AND lower(btrim(containedobject_classid::text)) <>
      CASE COALESCE(object_kind, '')
          WHEN 'external_report'     THEN 'e41aff26-25cf-4bb6-b6c1-3f478a75f374'
          WHEN 'external_processing' THEN 'c3831ec8-d8d5-4f93-8a22-f9bfae07327f'
          ELSE lower(btrim(containedobject_classid::text))
      END;
-- дети обязаны наследовать вид родителя: колонка parent_type есть у forms, form_ext,
-- templates, bsl_modules и у строк обогащения (у attributes/tabular_sections её нет, их вид
-- определяется родителем через FK на external_report(uuid))
SELECT 'дочерних строк с parent_type не вида родителя (должно быть 0) = '
       || ((SELECT count(*) FROM forms c JOIN external_report e ON e.uuid = c.parent_uuid
             WHERE c.parent_type IS DISTINCT FROM e.object_kind)
         + (SELECT count(*) FROM form_ext c JOIN external_report e ON e.uuid = c.parent_uuid
             WHERE c.parent_type IS DISTINCT FROM e.object_kind)
         + (SELECT count(*) FROM templates c JOIN external_report e ON e.uuid = c.parent_uuid
             WHERE c.parent_type IS DISTINCT FROM e.object_kind)
         + (SELECT count(*) FROM bsl_modules c JOIN external_report e ON e.uuid = c.parent_uuid
             WHERE c.parent_type IS DISTINCT FROM e.object_kind)
         + (SELECT count(*) FROM config_aliases c JOIN external_report e ON e.uuid = c.parent_uuid
             WHERE c.parent_type IS DISTINCT FROM e.object_kind)
         + (SELECT count(*) FROM config_snippets c
              JOIN external_report e ON e.uuid = c.parent_uuid
             WHERE c.parent_type IS DISTINCT FROM e.object_kind)) AS bad_parent_type;

-- цель «сам объект» обязана быть типа вида: ExternalProcessing у обработки и ExternalReport у
-- отчёта, иначе алиас или указатель documentation указывает вникуда
SELECT 'ссылок на сам объект с целевым типом не вида объекта (должно быть 0) = '
       || ((SELECT count(*) FROM config_aliases c JOIN external_report e ON e.uuid = c.parent_uuid
             WHERE c.active
               AND ((e.object_kind = 'external_processing' AND c.target_type = 'ExternalReport')
                 OR (e.object_kind = 'external_report' AND c.target_type = 'ExternalProcessing')))
         + (SELECT count(*) FROM config_cross_references x
              JOIN external_report e ON e.uuid = x.parent_uuid
             WHERE (e.object_kind = 'external_processing' AND x.target_type = 'ExternalReport')
                OR (e.object_kind = 'external_report' AND x.target_type = 'ExternalProcessing'))) AS bad_self_target;
-- один uuid под двумя видами — отдельный исход загрузки (kind_conflict), второй строки
-- возникать не должно
SELECT 'uuid, занятых строками двух видов одновременно (должно быть 0) = ' || count(*)
FROM (SELECT uuid FROM external_report GROUP BY uuid HAVING COUNT(DISTINCT object_kind) > 1) s;
-- мёртвых объектов схемы быть не должно: вторую таблицу заголовка и колонку связи модулей
-- узел V22 снял осознанно
SELECT 'таблицы external_processing в схеме быть не должно = ' || count(*)
FROM pg_class WHERE relname = 'external_processing';
SELECT 'колонки bsl_modules.processing_id быть не должно = ' || count(*)
FROM information_schema.columns
WHERE table_name = 'bsl_modules' AND column_name = 'processing_id';
-- витрина обязана отдавать вид: без неё вопрос «чего именно в базе N объектов» не задать
SELECT 'витрина v_config_enrichment отдаёт object_kind (должно быть 1) = ' || count(*)
FROM information_schema.columns
WHERE table_name = 'v_config_enrichment' AND column_name = 'object_kind';
-- обогащение по видам (его же печатает config_enrichment_stats_tool без uuid)
SELECT 'обогащение по видам: '
       || COALESCE(string_agg(object_kind || ': объектов ' || objects
                              || ', алиасов ' || aliases || ', сниппетов ' || snippets,
                              ' | ' ORDER BY object_kind), '(обогащения нет ни у одного объекта)')
FROM (SELECT object_kind, count(*) AS objects,
             COALESCE(sum(aliases_total), 0) AS aliases, COALESCE(sum(snippets), 0) AS snippets
      FROM v_config_enrichment GROUP BY object_kind) k;
-- у обработки self-цель обязана быть ExternalProcessing: без неё карточка и алиасы описывали
-- бы обработку как отчёт
SELECT 'объектов обработки с self-целью ExternalProcessing (должно быть равно числу объектов вида) = '
       || count(*)
FROM external_report e
WHERE e.object_kind = 'external_processing'
  AND EXISTS (SELECT 1 FROM config_aliases a
               WHERE a.parent_uuid = e.uuid AND a.active
                 AND a.target_type = 'ExternalProcessing');

SELECT '### 16. обогащение: слепые зоны (что пока не заполнено)' AS section;
SELECT 'объектов без обогащения (не сгенерировано) = ' || count(*)
FROM external_report e
WHERE NOT EXISTS (SELECT 1 FROM config_aliases a WHERE a.parent_uuid = e.uuid);
SELECT 'связей documentation = ' || count(*)
       || ' (таблица заполняется отдельным сценарием: в пилоте связи не создавались)'
FROM config_cross_references;
SELECT 'алиасов с пустым target_key (цель не опознана) = ' || count(*)
FROM config_aliases WHERE active AND target_key IS NULL;
SELECT 'целей TabularSectionColumn: это колонки ТЧ (33 в эталоне) — в алиасах они общие '
       || 'с реквизитами по таблице attributes, различие видно только по target_type' AS note,
       count(*) AS alias_rows FROM v_config_alias_targets
WHERE target_type = 'TabularSectionColumn';
