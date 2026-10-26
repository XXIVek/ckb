\encoding UTF8
\pset footer off
\pset tuples_only on

-- 1. Словарь сегментов в точечных именах модульных записей индекса.
--    Сегмент перед именем слота показывает, каким словом индекс описывает
--    владельца модуля; сравним его с именем каталога выгрузки.
\echo '=== 1. Сегмент перед слотом (index name vocabulary) ==='
WITH m AS (
  SELECT regexp_split_to_array(name, '[.]') AS p, child_type
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND (child_type IN ('ObjectModule','ManagerModule','RecordSetModule',
                        'ValueManagerModule','Module','CommandModule')
         OR child_type LIKE 'Command%Module')
)
SELECT p[array_length(p,1)-1] AS seg_before_slot,
       child_type             AS slot,
       count(*)
FROM m
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 20;

\echo '=== 2. Pervyj segment (vid) moduleznyh zapisej ==='
WITH m AS (
  SELECT split_part(name, '.', 1) AS kind
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND (child_type IN ('ObjectModule','ManagerModule','RecordSetModule',
                        'ValueManagerModule','Module','CommandModule')
         OR child_type LIKE 'Command%Module')
)
SELECT kind, count(*) AS n FROM m GROUP BY 1 ORDER BY n DESC LIMIT 14;

\echo '=== 3. Глубина записей модулей (число сегментов имени) ==='
WITH m AS (
  SELECT array_length(regexp_split_to_array(name, '[.]'), 1) AS segs, child_type
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND (child_type IN ('ObjectModule','ManagerModule','RecordSetModule',
                        'ValueManagerModule','Module','CommandModule')
         OR child_type LIKE 'Command%Module')
)
SELECT segs, count(*) FROM m GROUP BY 1 ORDER BY 1;
