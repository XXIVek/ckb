\encoding UTF8
\pset footer off
\pset tuples_only on

\echo '=== A. composite-id module rows by child_type (CURRENT) ==='
SELECT coalesce(nullif(child_type,''),'<NULL>') AS child_type, count(*) AS n
FROM configuration_objects
WHERE object_id LIKE '%.%'
  AND split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))
      IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule','Module','CommandModule')
GROUP BY 1 ORDER BY 2 DESC;

\echo '=== B. name shape (segments) of those rows ==='
WITH m AS (
  SELECT array_length(regexp_split_to_array(name,'[.]'),1) AS segs
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))
        IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule','Module','CommandModule')
)
SELECT segs, count(*) FROM m GROUP BY 1 ORDER BY 1;

\echo '=== C. is object_name equal to the top-level object name? ==='
WITH m AS (
  SELECT (object_name = (regexp_split_to_array(name,'[.]'))[2]) AS obj_is_top,
         (parent_name = array_to_string((regexp_split_to_array(name,'[.]'))[1:2],'.')) AS parent_is_top
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND array_length(regexp_split_to_array(name,'[.]'),1) >= 5
    AND split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))
        IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule','Module','CommandModule')
)
SELECT obj_is_top, parent_is_top, count(*) FROM m GROUP BY 1,2 ORDER BY 3 DESC;

\echo '=== D. owner uuid resolution by object_id prefix (module rows) ==='
WITH m AS (
  SELECT split_part(object_id,'.',1) AS owner_uuid
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))
        IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule','Module','CommandModule')
)
SELECT (o.uuid IS NOT NULL) AS owner_found, count(*)
FROM m LEFT JOIN configuration_objects o ON o.uuid::text = m.owner_uuid
GROUP BY 1 ORDER BY 2 DESC;

\echo '=== E. child_type fill state of ALL composite rows (current) ==='
SELECT (child_type IS NOT NULL AND child_type <> '') AS filled, count(*)
FROM configuration_objects WHERE object_id LIKE '%.%' GROUP BY 1;
