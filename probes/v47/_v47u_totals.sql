\encoding UTF8
\pset footer off
\pset tuples_only on

\echo '=== totals per configuration ==='
SELECT c.id, c.name, count(o.id) AS idx_rows
FROM configurations c LEFT JOIN configuration_objects o ON o.configuration_id = c.id
GROUP BY c.id, c.name ORDER BY c.id;

\echo '=== depth histogram (current) ==='
SELECT depth, count(*) FROM configuration_objects GROUP BY depth ORDER BY depth;

\echo '=== composite-id rows: total and child_type fill ==='
SELECT count(*) AS composite,
       count(*) FILTER (WHERE child_type IS NOT NULL AND child_type <> '') AS child_type_filled
FROM configuration_objects WHERE object_id LIKE '%.%';

\echo '=== own name available as last segment of parent_name? ==='
WITH m AS (
  SELECT (split_part(parent_name, '.', array_length(regexp_split_to_array(parent_name,'[.]'),1))
          = (regexp_split_to_array(name,'[.]'))[array_length(regexp_split_to_array(name,'[.]'),1)-1]) AS own_from_parent
  FROM configuration_objects
  WHERE object_id LIKE '%.%'
    AND array_length(regexp_split_to_array(name,'[.]'),1) >= 5
)
SELECT own_from_parent, count(*) FROM m GROUP BY 1 ORDER BY 2 DESC;
