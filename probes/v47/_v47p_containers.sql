\encoding UTF8
\pset footer off
\pset tuples_only on

\echo '=== 5-segment module names: container segment (3rd) vocabulary ==='
WITH m AS (
  SELECT split_part(name, '.', 3) AS container, child_type
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND array_length(regexp_split_to_array(name, '[.]'), 1) = 5
    AND (child_type IN ('ObjectModule','ManagerModule','RecordSetModule',
                        'ValueManagerModule','Module','CommandModule')
         OR child_type LIKE 'Command%Module')
)
SELECT container, child_type, count(*) AS n
FROM m GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 25;

\echo '=== exact examples: one row per container segment ==='
WITH m AS (
  SELECT name, object_id, parent_name, object_name, child_type,
         row_number() OVER (PARTITION BY split_part(name, '.', 3) ORDER BY name) AS rn
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND array_length(regexp_split_to_array(name, '[.]'), 1) = 5
    AND (child_type IN ('ObjectModule','ManagerModule','RecordSetModule',
                        'ValueManagerModule','Module','CommandModule')
         OR child_type LIKE 'Command%Module')
)
SELECT name, object_id, object_name, child_type
FROM m WHERE rn = 1 ORDER BY name LIMIT 25;
