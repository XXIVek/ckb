-- Узел V52, шаг П0: офлайн-зонд по живой БД `ckb_1c_configurations` о позиции 2.7
-- «Критерии отбора» (FilterCriteria / object_type индекса `FilterCriterion`).
--
-- Зонд только читает: `BEGIN … ROLLBACK`, чтобы негативные наблюдения не меняли живую базу
-- (приём `_v51_p1_dict_probe.sql`). Отвечает на вопросы, без которых модель записи вида
-- выдумывалась бы:
--   1. заполнена ли независимая нога круга в заголовке (`configurations.filter_criteria`);
--   2. что даёт индекс состава по виду: верхние записи, дети, глубина, расхождение с заголовком;
--   3. есть ли в схеме таблицы вида (ответ — «нет», и это называется, а не подразумевается);
--   4. кто уже ссылается на критерии: подсистемы (нога `subsystem_content`), роли
--      (`role_rights`), строки индекса состава с `child_type='FilterCriterion'`.
--
-- Запуск:
--   $env:PGPASSWORD=(Get-Content .env | ConvertFrom-StringData).PGPASSWORD; C:\Postgres\bin\psql.exe -tA -P footer=off -U postgres \
--       -d ckb_1c_configurations -f _v52_p0_db_probe.sql

\pset footer off

BEGIN;

SELECT '=== 1. независимая нога круга: configurations.filter_criteria (последние загрузки)';
SELECT name,
       uuid::text,
       to_char(created_at, 'YYYY-MM-DD HH24:MI') AS loaded_at,
       coalesce(array_length(filter_criteria, 1), 0) AS names_in_header,
       coalesce(array_length(subsystems, 1), 0)      AS names_subsystems
FROM configurations
ORDER BY created_at DESC
LIMIT 12;

SELECT '=== 2. индекс состава: строки вида FilterCriterion по конфигурациям (depth = 0)';
SELECT c.name,
       count(*) FILTER (WHERE o.depth = 0)                    AS top_rows,
       count(*) FILTER (WHERE o.depth > 0)                    AS deeper_rows,
       count(DISTINCT o.uuid) FILTER (WHERE o.depth = 0)      AS distinct_uuid
FROM configuration_objects o
         JOIN configurations c ON c.id = o.configuration_id
WHERE o.object_type = 'FilterCriterion'
GROUP BY c.name
ORDER BY top_rows DESC;

SELECT '=== 2а. child_type у строк вида (есть ли у вида дети в индексе)';
SELECT coalesce(nullif(o.child_type, ''), '(пусто)') AS child_type,
       o.depth,
       count(*)
FROM configuration_objects o
WHERE o.object_type = 'FilterCriterion'
GROUP BY 1, 2
ORDER BY 3 DESC;

SELECT '=== 2б. примеры точечных имён строк вида (первые 8 по одной конфигурации)';
SELECT c.name, o.name, o.child_type, o.depth, left(o.uuid::text, 8) AS uuid_head
FROM configuration_objects o
         JOIN configurations c ON c.id = o.configuration_id
WHERE o.object_type = 'FilterCriterion'
ORDER BY c.name, o.name
LIMIT 8;

SELECT '=== 3. таблицы вида в живой схеме (ожидаем: нет ни одной)';
SELECT coalesce(string_agg(table_name, ', '),
                'таблиц по словам criter/filter/condition нет') AS tables_found
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (table_name ILIKE '%criter%' OR table_name ILIKE '%filter%'
       OR table_name ILIKE '%condition%');

SELECT '=== 3а. колонки с корнем criter/filter в любой таблице схемы (кого уже трогать нельзя)';
SELECT coalesce(string_agg(table_name || '.' || column_name, ', '), 'таких колонок нет') AS cols
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (column_name ILIKE '%criter%' OR column_name ILIKE '%filter%');

SELECT '=== 4. ссылки на критерии в ноге перечня подсистем (subsystem_content)';
SELECT coalesce(target_object_type, '(не разрешилось)') AS target_object_type,
       count(*)                                          AS rows_count,
       count(DISTINCT configuration_uuid)                AS configs
FROM subsystem_content
WHERE ref_text LIKE 'FilterCriteria%'
   OR target_object_type = 'FilterCriterion'
GROUP BY 1
ORDER BY rows_count DESC;

SELECT '=== 4а. то же по конфигурациям (кто именно ссылается)';
SELECT c.name,
       count(*)                    AS refs_total,
       count(*) FILTER (WHERE sc.resolved IS FALSE) AS unresolved
FROM subsystem_content sc
         JOIN configurations c ON c.uuid = sc.configuration_uuid
WHERE sc.ref_text LIKE 'FilterCriteria%'
GROUP BY c.name
ORDER BY refs_total DESC;

SELECT '=== 5. ссылки на критерии в правах ролей (role_rights)';
SELECT coalesce(nullif(target_kind, ''), '(пусто)') AS target_kind,
       target_resolve_state,
       count(*)                                     AS rows_count,
       count(DISTINCT configuration_uuid)           AS configs
FROM role_rights
WHERE target_full_name LIKE 'FilterCriteria%'
   OR target_kind = 'FilterCriterion'
GROUP BY 1, 2
ORDER BY rows_count DESC;

SELECT '=== 6. строки индекса с child_type = FilterCriterion (дети подсистем в индексе состава)';
SELECT c.name,
       count(*)                            AS rows_count,
       count(DISTINCT o.parent_name)       AS distinct_parents
FROM configuration_objects o
         JOIN configurations c ON c.id = o.configuration_id
WHERE o.child_type = 'FilterCriterion'
GROUP BY c.name
ORDER BY rows_count DESC;

SELECT '=== 7. весь словарь child_type индекса состава (контекст: что уже моделировано)',
       '(для сравнения: узел V51 опирался на тот же индекс)';
SELECT coalesce(nullif(child_type, ''), '(пусто)') AS child_type, count(*)
FROM configuration_objects
GROUP BY 1
ORDER BY 2 DESC
LIMIT 40;

ROLLBACK;
