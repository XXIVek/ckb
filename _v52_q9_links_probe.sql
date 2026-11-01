-- Зонд Q9 узла V52: сколько ссылок на вид FilterCriteria уже лежит в базе и разрешимы ли они.
--   A. ссылки подсистем (`subsystem_content`) на вид: число и состояние разрешения;
--   B. ссылки прав ролей (`role_rights`) на вид: число, состояние, kinds целей;
--   C. есть ли среди них ссылки, которые указывали бы на строку вида (строк вида в схеме нет —
--      колонок и таблиц по виду не существует, ответ называется фактом схемы, а не нулём).
BEGIN;

SELECT 'A. subsystem_content: ссылок на вид ' || count(*)
       || ' | resolved: ' || coalesce(string_agg(resolved::text, '/'), '<нет строк>')
       || ' | различных конфигураций ' || count(DISTINCT configuration_uuid)
FROM subsystem_content
WHERE target_object_type = 'FilterCriterion';

SELECT 'B. role_rights: ссылок на вид ' || count(*)
       || ' | состояний: ' || coalesce(string_agg(target_resolve_state, '/' ORDER BY target_resolve_state), '<нет строк>')
       || ' | различных конфигураций ' || count(DISTINCT configuration_uuid)
FROM role_rights
WHERE target_kind = 'FilterCriterion';

SELECT 'C. таблиц/витрин вида в схеме: ' || count(*)
FROM pg_class
WHERE relkind IN ('r', 'v')
  AND (relname LIKE 'filter_criter%' OR relname LIKE 'v_current_filter_criter%');

SELECT 'D. пример цели подсистемы: ' || configuration_uuid::text || ' | ' || target_full_name
       || ' | resolved=' || resolved::text
FROM subsystem_content
WHERE target_object_type = 'FilterCriterion'
LIMIT 3;

SELECT 'E. пример цели права: ' || configuration_uuid::text || ' | ' || target_full_name
       || ' | ' || target_resolve_state
FROM role_rights
WHERE target_kind = 'FilterCriterion'
LIMIT 3;

ROLLBACK;
