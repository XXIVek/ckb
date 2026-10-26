-- Замер узла V38 (шаг 1), продолжение: природа общих uuid между конфигурациями.
-- S3 (_v38_uuid_probe.sql) дал 42 349 значений uuid, встречающихся в двух конфигурациях.
-- Вопросы этого замера:
--   S6  это один и тот же объект метаданных в двух поставках (имя совпадает) или настоящая
--       коллизия идентичности (имена разные)? Какой уровень иерархии затронут?
--   S7  какая доля uuid каждой конфигурации оказывается общим с другой;
--   S8  какие виды метаданных дают общие uuid.
-- Запуск: psql -U postgres -d ckb_1c_configurations -v ON_ERROR_STOP=1 -f _v38_uuid_shared.sql

\set ON_ERROR_STOP on

CREATE TEMP TABLE shared_uuid AS
SELECT uuid,
       count(DISTINCT configuration_id) AS cfgs,
       count(DISTINCT name) AS distinct_names,
       count(DISTINCT COALESCE(parent_name, name)) AS distinct_parents,
       min(depth) AS min_depth,
       max(depth) AS max_depth,
       min(name) AS name_a
FROM configuration_objects
WHERE uuid IS NOT NULL
GROUP BY uuid
HAVING count(DISTINCT configuration_id) > 1;

SELECT 'S6 природа общих uuid' AS section;
SELECT count(*) AS shared_uuid_values,
       count(*) FILTER (WHERE distinct_names = 1) AS same_name_in_all_configs,
       count(*) FILTER (WHERE distinct_names > 1) AS different_name,
       count(*) FILTER (WHERE distinct_parents > 1) AS different_parent,
       count(*) FILTER (WHERE min_depth = 0) AS shared_at_top_level,
       count(*) FILTER (WHERE min_depth > 0) AS shared_only_nested
FROM shared_uuid;

SELECT 'S7 доля общих uuid по конфигурациям' AS section;
SELECT c.id, c.name,
       count(o.uuid) AS uuid_filled,
       count(*) FILTER (WHERE o.uuid IN (SELECT uuid FROM shared_uuid)) AS uuid_shared,
       count(*) FILTER (WHERE o.uuid NOT IN (SELECT uuid FROM shared_uuid)) AS uuid_own
FROM configurations c
JOIN configuration_objects o ON o.configuration_id = c.id
GROUP BY c.id, c.name
ORDER BY c.id;

SELECT 'S8 виды метаданных, дающие общие uuid (top 30)' AS section;
SELECT split_part(name_a, '.', 1) AS kind, count(*) AS shared_uuids
FROM shared_uuid
GROUP BY 1
ORDER BY shared_uuids DESC
LIMIT 30;

SELECT 'S9 глубина записей с общими uuid' AS section;
SELECT min_depth, count(*) FROM shared_uuid GROUP BY 1 ORDER BY 1;
