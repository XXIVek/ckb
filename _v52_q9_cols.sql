SELECT table_name||' :: '||string_agg(column_name, ', ' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name IN ('subsystem_content','role_rights') GROUP BY table_name;
