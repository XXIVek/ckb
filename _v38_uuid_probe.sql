-- Замер узла V38 (шаг 1): коллизии uuid метаданных внутри индекса состава.
-- Вопрос: годится ли глобальная граница UNIQUE (uuid, revision_no) для дочерних
-- объектов конфигурации (реквизитов, ТЧ, форм, макетов), или нужна граница
-- в пределах родителя (parent_uuid, uuid, revision_no).
-- Запуск: psql -v ON_ERROR_STOP=1 -d ckb_1c_configurations -f _v38_uuid_probe.sql

\set ON_ERROR_STOP on

SELECT 'S0 состояние индекса по конфигурациям' AS section;
SELECT c.id, c.name, count(*) AS idx_rows,
       count(o.uuid) AS uuid_filled,
       count(DISTINCT o.uuid) AS uuid_distinct
FROM configurations c
JOIN configuration_objects o ON o.configuration_id = c.id
GROUP BY c.id, c.name
ORDER BY c.id;

SELECT 'S1 дубли uuid внутри одной конфигурации' AS section;
SELECT configuration_id, uuid, count(*) AS n,
       count(DISTINCT COALESCE(parent_name, name)) AS distinct_parents,
       min(COALESCE(parent_name, name)) AS parent_a,
       max(COALESCE(parent_name, name)) AS parent_b
FROM configuration_objects
WHERE uuid IS NOT NULL
GROUP BY configuration_id, uuid
HAVING count(*) > 1
ORDER BY n DESC, configuration_id
LIMIT 25;

SELECT 'S2 итог по дублям (одна строка на конфигурацию)' AS section;
SELECT configuration_id,
       count(*) FILTER (WHERE dup_n > 1) AS dup_uuid_values,
       count(*) FILTER (WHERE dup_parents > 1) AS dup_across_parents
FROM (
    SELECT configuration_id, uuid,
           count(*) AS dup_n,
           count(DISTINCT COALESCE(parent_name, name)) AS dup_parents
    FROM configuration_objects
    WHERE uuid IS NOT NULL
    GROUP BY configuration_id, uuid
) s
GROUP BY configuration_id
ORDER BY configuration_id;

SELECT 'S3 дубли uuid МЕЖДУ конфигурациями (важно: attributes.uuid уникален глобально)' AS section;
SELECT count(*) AS uuid_shared_between_configs
FROM (
    SELECT uuid
    FROM configuration_objects
    WHERE uuid IS NOT NULL
    GROUP BY uuid
    HAVING count(DISTINCT configuration_id) > 1
) s;

SELECT 'S4 примеры общих uuid между конфигурациями' AS section;
SELECT uuid,
       count(DISTINCT configuration_id) AS configs,
       array_agg(DISTINCT configuration_id) AS config_ids,
       min(COALESCE(parent_name, name)) AS sample_name_a,
       max(COALESCE(parent_name, name)) AS sample_name_b
FROM configuration_objects
WHERE uuid IS NOT NULL
GROUP BY uuid
HAVING count(DISTINCT configuration_id) > 1
LIMIT 15;

SELECT 'S5 формы object_id по конфигурациям (канонические / составные / суффиксные)' AS section;
SELECT configuration_id,
       count(*) AS rows_all,
       count(*) FILTER (WHERE object_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') AS canonical,
       count(*) FILTER (WHERE object_id ~ '^[0-9a-f-]{36}\.[0-9]+$') AS composite_num,
       count(*) FILTER (WHERE object_id ~ '^[0-9a-f-]{36}\.[0-9a-f]+$'
                          AND object_id !~ '^[0-9a-f-]{36}\.[0-9]+$') AS suffix_hex,
       count(*) FILTER (WHERE uuid IS NULL) AS uuid_null
FROM configuration_objects
GROUP BY configuration_id
ORDER BY configuration_id;
