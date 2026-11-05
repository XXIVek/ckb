\encoding UTF8
\pset footer off
\pset tuples_only on

\echo '=== A. module rows by child_type (filter by NAME tail) — full list ==='
WITH m AS (
  SELECT coalesce(nullif(child_type,''),'<NULL>') AS child_type
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))
        IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule','Module','CommandModule')
)
SELECT child_type, count(*) FROM m GROUP BY 1 ORDER BY 2 DESC;

\echo '=== A2. total module rows (name tail) ==='
SELECT count(*) FROM configuration_objects
WHERE object_id LIKE '%.%'
  AND split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))
      IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule','Module','CommandModule');

\echo '=== B. last name segment vocabulary of composite rows (top 20) ==='
SELECT split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1)) AS tail, count(*)
FROM configuration_objects WHERE object_id LIKE '%.%'
GROUP BY 1 ORDER BY 2 DESC LIMIT 20;

\echo '=== C. composite rows by segment count ==='
SELECT array_length(regexp_split_to_array(name,'[.]'),1) AS segs, count(*)
FROM configuration_objects WHERE object_id LIKE '%.%'
GROUP BY 1 ORDER BY 1;

\echo '=== D. owner uuid resolvable for module rows (name tail) ==='
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

\echo '=== E. CommandModule composite rows per configuration ==='
SELECT configuration_id, count(*) FROM configuration_objects
WHERE object_id LIKE '%.%' AND child_type = 'CommandModule'
GROUP BY 1 ORDER BY 1;

\echo '=== F. is name == parent_name || '.' || last segment? (composite rows) ==='
SELECT (name = parent_name || '.' || split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))) AS name_from_parent,
       count(*)
FROM configuration_objects WHERE object_id LIKE '%.%' GROUP BY 1 ORDER BY 2 DESC;

\echo '=== G. object_name equals which segment of name (composite, segs>=5) ==='
SELECT (object_name = (regexp_split_to_array(name,'[.]'))[2]) AS obj_is_seg2,
       (object_name = (regexp_split_to_array(name,'[.]'))[array_length(regexp_split_to_array(name,'[.]'),1)-1]) AS obj_is_own,
       count(*)
FROM configuration_objects
WHERE object_id LIKE '%.%' AND array_length(regexp_split_to_array(name,'[.]'),1) >= 5
GROUP BY 1,2 ORDER BY 3 DESC;

\echo '=== H. kinds of composite module rows (first segment) with child_type tail ==='
SELECT split_part(name,'.',1) AS kind, count(*)
FROM configuration_objects
WHERE object_id LIKE '%.%'
  AND split_part(name,'.',array_length(regexp_split_to_array(name,'[.]'),1))
      IN ('ObjectModule','ManagerModule','RecordSetModule','ValueManagerModule','Module','CommandModule')
GROUP BY 1 ORDER BY 2 DESC;
