\set ON_ERROR_STOP on
SELECT 'TABLE ' || table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'bsl_modules!_%' ESCAPE '!' ORDER BY 1;
SELECT 'SELECT ''' || table_name || ''' AS t, COUNT(*) FROM ' || table_name || ';' FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'bsl_modules!_%' ESCAPE '!' ORDER BY 1 \gexec
SELECT table_name || '.' || column_name || ' ' || data_type || ' null=' || is_nullable FROM information_schema.columns WHERE table_name LIKE 'bsl_modules!_%' ESCAPE '!' ORDER BY table_name, ordinal_position;
SELECT conrelid::regclass::text || ' :: ' || conname || ' ' || contype FROM pg_constraint WHERE conrelid::regclass::text LIKE 'bsl_modules!_%' ESCAPE '!' ORDER BY 1;
SELECT tablename || ' :: ' || indexname FROM pg_indexes WHERE tablename LIKE 'bsl_modules!_%' ESCAPE '!' ORDER BY 1;

-- 6. заголовки конфигураций и их uuid (ключ связи узла V44)
SELECT 'CONFIG id=' || c.id || ' name=' || c.name || ' uuid=' || coalesce(c.uuid, '<NULL>')
FROM configurations c ORDER BY c.id;

-- 7. содержимое четырёх таблиц: вид модуля, состояние, размеры, ссылка на индекс
SELECT 'ROW mod_' || t.kind || ' uuid=' || m.configuration_uuid || ' state=' || m.code_state ||
       ' chars=' || coalesce(m.code_chars::text, 'NULL') ||
       ' bytes=' || coalesce(m.code_bytes::text, 'NULL') ||
       ' idx=' || coalesce(m.index_object_id, '<NULL>') ||
       ' src=' || coalesce(m.source_path, '<NULL>')
FROM (VALUES ('session'), ('managed_application'), ('ordinary_application'),
             ('external_connection')) AS t(kind)
JOIN LATERAL (
    SELECT configuration_uuid, code_state, code_chars, code_bytes, index_object_id, source_path
    FROM bsl_modules_session WHERE t.kind = 'session'
    UNION ALL
    SELECT configuration_uuid, code_state, code_chars, code_bytes, index_object_id, source_path
    FROM bsl_modules_managed_application WHERE t.kind = 'managed_application'
    UNION ALL
    SELECT configuration_uuid, code_state, code_chars, code_bytes, index_object_id, source_path
    FROM bsl_modules_ordinary_application WHERE t.kind = 'ordinary_application'
    UNION ALL
    SELECT configuration_uuid, code_state, code_chars, code_bytes, index_object_id, source_path
    FROM bsl_modules_external_connection WHERE t.kind = 'external_connection'
) m ON true
ORDER BY 1;

-- 8. записи индекса состава по слотам модулей корня (для сверки трёх контуров)
SELECT 'INDEX ' || coalesce(c.name, '<нет строки заголовка>') || ' id=' ||
       coalesce(o.configuration_id::text, 'NULL') ||
       ' slot=' || o.child_type || ' name=' || o.name ||
       ' object_id=' || coalesce(o.object_id, 'NULL')
FROM configuration_objects o
LEFT JOIN configurations c ON c.id = o.configuration_id
WHERE o.child_type = ANY (ARRAY['SessionModule','ManagedApplicationModule',
                                'OrdinaryApplicationModule','ExternalConnectionModule'])
ORDER BY o.configuration_id, o.child_type;

