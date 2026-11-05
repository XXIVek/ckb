-- Зонд Q3 узла V52 (продолжение): чем держится разделение общих таблиц детей.
--   G. заполнена ли нога configuration_uuid у строк детей конфигурации;
--   H. то же по commands (единственная строка вида планов обмена);
--   I. какие индексы обслуживают предикат configuration_uuid + parent_uuid;
--   J. есть ли у form_ext собственная configuration_uuid (её нет — разделение держит цепочка
--      form_id → forms.configuration_uuid; расхождение с текстом задания называется прямо).
BEGIN;

SELECT 'G. forms parent_type=configuration_objects: строк ' || count(*)
       || ' | configuration_uuid заполнен ' || count(configuration_uuid)
       || ' | различных configuration_uuid ' || count(DISTINCT configuration_uuid)
FROM forms WHERE parent_type = 'configuration_objects';

SELECT 'H. commands: строк ' || count(*)
       || ' | configuration_uuid заполнен ' || count(configuration_uuid)
       || ' | parent_type = ' || coalesce(parent_type, '<null>')
FROM commands GROUP BY parent_type;

SELECT 'I. индекс: ' || tablename || ' :: ' || indexdef
FROM pg_indexes
WHERE tablename IN ('forms', 'form_ext', 'commands')
  AND (indexdef ILIKE '%configuration_uuid%' OR indexdef ILIKE '%parent_uuid%')
ORDER BY tablename, indexname;

SELECT 'J. form_ext: строк ' || count(*) || ' | колонки configuration_uuid в схеме '
       || (SELECT count(*) FROM information_schema.columns
           WHERE table_name = 'form_ext' AND column_name = 'configuration_uuid')
FROM form_ext;

SELECT 'K. form_ext через цепочку forms: configuration_uuid заполнен '
       || count(f.configuration_uuid) || ' из ' || count(*)
FROM form_ext fx JOIN forms f ON f.id = fx.form_id;

ROLLBACK;
