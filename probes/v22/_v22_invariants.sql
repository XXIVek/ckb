-- _v22_invariants.sql — инварианты единой модели внешнего объекта (узел V22).
-- Запуск: psql -v ON_ERROR_STOP=1 -f _v22_invariants.sql
-- Ожидание: external_processing = NULL, processing_id = 0, сироты = 0,
--           kind_mismatch = 0, uuid_kind_conflict = 0.
\set ON_ERROR_STOP on

SELECT 'table_external_processing' AS check, COALESCE(to_regclass('public.external_processing')::text, 'ABSENT') AS result;

SELECT 'columns_processing_id' AS check, COUNT(*)::text AS result
FROM information_schema.columns WHERE column_name = 'processing_id';

SELECT 'columns_object_kind' AS check, COUNT(*)::text AS result
FROM information_schema.columns WHERE table_name = 'external_report' AND column_name = 'object_kind';

SELECT 'kind_counts' AS check,
       string_agg(object_kind || '=' || cnt, ' ') AS result
FROM (SELECT object_kind, COUNT(*) AS cnt FROM external_report GROUP BY object_kind) s;

SELECT 'header_children' AS check,
       e.id || '|' || e.object_kind || '|' || e.name || '|attrs=' ||
       (SELECT COUNT(*) FROM attributes a WHERE a.parent_uuid = e.uuid) ||
       '|ts=' || (SELECT COUNT(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid) ||
       '|forms=' || (SELECT COUNT(*) FROM forms f WHERE f.parent_uuid = e.uuid) ||
       '|form_ext=' || (SELECT COUNT(*) FROM form_ext fe WHERE fe.parent_uuid = e.uuid) ||
       '|templates=' || (SELECT COUNT(*) FROM templates tp WHERE tp.parent_uuid = e.uuid) ||
       '|bsl=' || (SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid = e.uuid) AS result
FROM external_report e ORDER BY e.id;

SELECT 'orphan_' || t.name AS check, t.cnt::text AS result FROM (
  SELECT 'attributes' AS name, COUNT(*) AS cnt FROM attributes a
    WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = a.parent_uuid)
  UNION ALL
  SELECT 'tabular_sections', COUNT(*) FROM tabular_sections a
    WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = a.parent_uuid)
  UNION ALL
  SELECT 'forms', COUNT(*) FROM forms f
    WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = f.parent_uuid)
  UNION ALL
  SELECT 'form_ext', COUNT(*) FROM form_ext f
    WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = f.parent_uuid)
  UNION ALL
  SELECT 'templates', COUNT(*) FROM templates t
    WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = t.parent_uuid)
  UNION ALL
  SELECT 'bsl_modules', COUNT(*) FROM bsl_modules b
    WHERE b.parent_uuid IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = b.parent_uuid)
  UNION ALL
  SELECT 'config_aliases', COUNT(*) FROM config_aliases c
    WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = c.parent_uuid)
  UNION ALL
  SELECT 'config_snippets', COUNT(*) FROM config_snippets c
    WHERE NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = c.parent_uuid)
  UNION ALL
  SELECT 'config_dependencies', COUNT(*) FROM config_snippet_dependencies d
    WHERE NOT EXISTS (SELECT 1 FROM config_snippets s WHERE s.id = d.snippet_id)
) t;

-- kinds mismatch: у attributes/tabular_sections колонки parent_type нет вовсе
-- (родитель фиксируется FK на external_report(uuid)), поэтому они в проверке не участвуют.
SELECT 'kind_mismatch_' || t.name AS check, t.cnt::text AS result FROM (
  SELECT 'forms' AS name, COUNT(*) AS cnt FROM forms c
    JOIN external_report e ON e.uuid = c.parent_uuid WHERE c.parent_type <> e.object_kind
  UNION ALL
  SELECT 'form_ext', COUNT(*) FROM form_ext c
    JOIN external_report e ON e.uuid = c.parent_uuid WHERE c.parent_type <> e.object_kind
  UNION ALL
  SELECT 'templates', COUNT(*) FROM templates c
    JOIN external_report e ON e.uuid = c.parent_uuid WHERE c.parent_type <> e.object_kind
  UNION ALL
  SELECT 'bsl_modules', COUNT(*) FROM bsl_modules c
    JOIN external_report e ON e.uuid = c.parent_uuid WHERE c.parent_type <> e.object_kind
  UNION ALL
  SELECT 'config_aliases', COUNT(*) FROM config_aliases c
    JOIN external_report e ON e.uuid = c.parent_uuid WHERE c.parent_type <> e.object_kind
  UNION ALL
  SELECT 'config_snippets', COUNT(*) FROM config_snippets c
    JOIN external_report e ON e.uuid = c.parent_uuid WHERE c.parent_type <> e.object_kind
) t;

SELECT 'uuid_kind_conflict' AS check, COUNT(*)::text AS result FROM (
  SELECT uuid FROM external_report GROUP BY uuid HAVING COUNT(DISTINCT object_kind) > 1) s;

-- enrichment self-цели: тип цели обязан совпадать с видом объекта
SELECT 'enrich_self_target_kind' AS check,
       COALESCE(string_agg(DISTINCT target_type, ','), 'none') AS result
FROM config_aliases WHERE target_type IN ('ExternalReport', 'ExternalProcessing');
