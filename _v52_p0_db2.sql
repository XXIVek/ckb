-- Узел V52, шаг П0: второй офлайн-зонд — покрытость модулей вида узлом V47 и то, в каком
-- виде цели вида уже стоят в загруженных ногах (подсистемы, роли, нога заголовка).
-- Только чтение (BEGIN … ROLLBACK). Файл, а не `-c`, потому что кириллица в аргументе
-- PowerShell доходит до сервера в кодовой странице консоли (замер 01.11.2026: ошибка
-- `invalid byte sequence for encoding "UTF8"`).
BEGIN;

SELECT 'A. модули объектов вида в bsl_modules (узел V47): '||count(*)||' строк; parent_type: '
       ||coalesce(string_agg(DISTINCT m.parent_type, ', '), 'нет строк')
FROM bsl_modules m
         JOIN configuration_objects o ON o.uuid = m.parent_uuid
WHERE o.object_type = 'FilterCriterion';

SELECT 'B. примеры путей модулей вида: ' || m.file_path || ' | parent_type=' || m.parent_type
FROM bsl_modules m
         JOIN configuration_objects o ON o.uuid = m.parent_uuid
WHERE o.object_type = 'FilterCriterion'
LIMIT 5;

SELECT 'C. формат имён в ноге заголовка configurations.filter_criteria: '
       ||array_to_string(filter_criteria, ' ;; ')
FROM configurations
WHERE uuid IN (SELECT uuid FROM configurations ORDER BY created_at DESC LIMIT 4)
LIMIT 4;

SELECT 'D. ссылки подсистем на вид: ref_text=' || coalesce(ref_text, '(пусто)')
       || ' | full=' || coalesce(target_full_name, '(пусто)')
       || ' | resolved=' || coalesce(resolved::text, '(нет значения)')
FROM subsystem_content
WHERE target_object_type = 'FilterCriterion'
LIMIT 5;

SELECT 'E. ссылки прав ролей на вид: kind=' || coalesce(target_kind, '(пусто)')
       || ' | full=' || coalesce(target_full_name, '(пусто)')
       || ' | uuid=' || coalesce(target_object_uuid::text, '(нет)')
       || ' | state=' || coalesce(target_resolve_state, '(нет)')
FROM role_rights
WHERE target_kind = 'FilterCriterion'
LIMIT 5;

SELECT 'F. есть ли у вида строки детей в загруженных таблицах V51 (формы/команды): '
       ||(SELECT count(*) FROM forms WHERE parent_type = 'FilterCriterion')
       ||' / '||(SELECT count(*) FROM commands WHERE parent_type = 'FilterCriterion');

SELECT 'G. словари parent_type в таблицах детей (кого уже различает слой V51): '
       ||(SELECT coalesce(string_agg(DISTINCT parent_type, ', '), '(пусто)') FROM forms)
       ||' | commands: '
       ||(SELECT coalesce(string_agg(DISTINCT parent_type, ', '), '(пусто)') FROM commands);

SELECT 'H. колонки таблиц детей, которые узел V52 может переиспользовать: '
       ||table_name||': '||string_agg(column_name, ', ' ORDER BY ordinal_position)
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('attributes', 'tabular_sections', 'forms', 'form_ext', 'templates',
                     'commands', 'exchange_plans', 'exchange_plan_content')
GROUP BY table_name
ORDER BY table_name;

SELECT 'I. число строк в таблицах детей и витрины текущности (состояние на дату узла): '
       ||(SELECT count(*) FROM forms)||' forms / '
       ||(SELECT count(*) FROM form_ext)||' form_ext / '
       ||(SELECT count(*) FROM templates)||' templates / '
       ||(SELECT count(*) FROM commands)||' commands / '
       ||(SELECT count(*) FROM attributes)||' attributes / '
       ||(SELECT count(*) FROM exchange_plans)||' exchange_plans / '
       ||(SELECT count(*) FROM exchange_plan_content)||' exchange_plan_content';

SELECT 'J. витрины текущности детей (имена — чтобы называть их в модели): '
       ||string_agg(table_name, ', ')
FROM information_schema.views
WHERE table_schema = 'public' AND table_name LIKE 'v\_current%';

ROLLBACK;
