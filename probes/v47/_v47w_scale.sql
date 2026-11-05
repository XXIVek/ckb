\encoding UTF8
\pset footer off
\pset tuples_only on

\echo '=== 1. composite rows by child_type (scale of object content) ==='
SELECT coalesce(nullif(child_type,''),'<NULL>') AS child_type, count(*)
FROM configuration_objects WHERE object_id LIKE '%.%'
GROUP BY 1 ORDER BY 2 DESC LIMIT 30;

\echo '=== 2. module slots: full kind -> slot map from the live index ==='
SELECT split_part(name,'.',1) AS kind, child_type AS slot, count(*)
FROM configuration_objects
WHERE child_type IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule',
                     'Module','CommandModule')
GROUP BY 1,2 ORDER BY 1,3 DESC;

\echo '=== 3. module slots: kinds count and totals ==='
SELECT count(DISTINCT split_part(name,'.',1)) AS kinds, count(*) AS rows_total
FROM configuration_objects
WHERE child_type IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule',
                     'Module','CommandModule');

\echo '=== 4. container segment vocabulary of 5-segment rows (all child_type) ==='
SELECT split_part(name,'.',3) AS container, count(*)
FROM configuration_objects
WHERE object_id LIKE '%.%' AND array_length(regexp_split_to_array(name,'[.]'),1) = 5
GROUP BY 1 ORDER BY 2 DESC LIMIT 20;
