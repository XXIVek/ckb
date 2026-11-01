-- Зонд Q3 узла V52: готовы ли общие таблицы детей принимать строки вида FilterCriteria.
-- Отвечает на вопросы, без которых Q3 решался бы текстом плана:
--   A. есть ли у forms/form_ext/commands ноги области видимости (configuration_uuid, parent_uuid, parent_type);
--   B. замкнут ли словарь parent_type ограничением CHECK (тогда запись вида требует правки схемы);
--   C. сколько строк детей уже лежит по чужим видам конфигураций (замер V51);
--   D. что даёт индекс состава по детям вида (формы, команда, модули) — круг, который надо записать;
--   E. лежат ли модули вида в bsl_modules (узел V47), т.е. тексты читать не нужно.
BEGIN;

SELECT 'A. ноги области видимости: ' || table_name || ' -> '
       || string_agg(column_name, ', ' ORDER BY ordinal_position)
FROM information_schema.columns
WHERE table_name IN ('forms', 'form_ext', 'commands')
  AND column_name IN ('configuration_uuid', 'parent_uuid', 'parent_type',
                      'object_name', 'full_name', 'form_name', 'command_name')
GROUP BY table_name
ORDER BY table_name;

SELECT 'B. ограничение по parent_type: ' || conrelid::regclass::text || ' :: ' || conname
       || ' :: ' || pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid IN ('forms'::regclass, 'form_ext'::regclass, 'commands'::regclass)
  AND pg_get_constraintdef(oid) ILIKE '%parent_type%'
ORDER BY 1;

SELECT 'C. строк детей по parent_type: ' || table_name || ' :: '
       || coalesce(parent_type, '<null>') || ' = ' || cnt
FROM (
    SELECT 'forms' AS table_name, parent_type, count(*) AS cnt FROM forms GROUP BY parent_type
    UNION ALL
    SELECT 'form_ext', fx.parent_type, count(*)
      FROM form_ext fx JOIN forms f ON f.id = fx.form_id GROUP BY fx.parent_type
    UNION ALL
    SELECT 'commands', parent_type, count(*) FROM commands GROUP BY parent_type
) AS s
ORDER BY table_name, cnt DESC;

SELECT 'D. детей вида по индексу состава: ' || child_type || ' = ' || count(*)
       || ' | глубина ' || min(depth) || '-' || max(depth)
FROM configuration_objects
WHERE object_type = 'FilterCriterion' AND depth > 0
GROUP BY child_type
ORDER BY child_type;

SELECT 'E. модулей вида в bsl_modules: ' || coalesce(module_type, '<null>') || ' = ' || count(*)
FROM bsl_modules m
WHERE m.parent_type = 'configuration_objects'
  AND m.parent_uuid IN (SELECT uuid FROM configuration_objects
                        WHERE object_type = 'FilterCriterion')
GROUP BY module_type
ORDER BY module_type;

SELECT 'F. форм вида, уже лежащих в forms: ' || count(*)
FROM forms f
WHERE f.parent_type = 'FilterCriterion'
   OR f.parent_uuid IN (SELECT uuid FROM configuration_objects
                        WHERE object_type = 'FilterCriterion');

ROLLBACK;
