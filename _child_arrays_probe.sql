-- Замер узла «массивы имён дочерних свойств конфигурации» (по файлу
-- C:\1C_LLM\Дочерние свойства для конфигурации.txt, 48 видов).
-- Цель замера: назвать ТОЧНЫЕ источники для 48 колонок-массивов в `configurations`
-- по живой таблице `configuration_objects` (индекс состава, узел V33), а не по именам
-- из файла — в файле есть опечатки (`ChartOfAccountss`, `BusinessProcesss`,
-- `FilterCriterions`, `CalculationRegister` без -s).
-- Вопросы:
--   K1  какие виды метаданных реально отдаёт индекс на уровне верхних объектов (depth=0)
--       и сколько их в каждой из загруженных конфигураций;
--   K2  какие значения `child_type` встречаются глубже (нумераторы, последовательности,
--       формы, реквизиты) — из них заполняются только те два вида, что указаны как
--       «используется только для документов»;
--   K3  предельная длина имени (файл задаёт 80 символов — это граница платформы или
--       наблюдение? замер по 171k имён даёт ровно 80);
--   K4  уникальны ли имена внутри вида в пределах одной конфигурации (массив имён обязан
--       быть однозначным);
--   K5  как индекс моделирует нумераторы и последовательности (имя короткое неоднозначно).
-- Запуск: $env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -h localhost -U postgres -d ckb_1c_configurations -v ON_ERROR_STOP=1 -tA -P footer=off -f _child_arrays_probe.sql

\set ON_ERROR_STOP on

SELECT 'K1 верхние виды (depth=0) по конфигурациям' AS section;
SELECT o.object_type,
       count(*) AS rows_all,
       count(*) FILTER (WHERE o.configuration_id = (SELECT id FROM configurations WHERE name = 'MinCfg')) AS mincfg,
       count(*) FILTER (WHERE o.configuration_id = (SELECT id FROM configurations WHERE name = 'KomMag')) AS kommag,
       count(*) FILTER (WHERE o.configuration_id = (SELECT id FROM configurations WHERE name = 'BGU2')) AS bgu2,
       count(*) FILTER (WHERE o.configuration_id = (SELECT id FROM configurations WHERE name = 'BP3')) AS bp3
FROM configuration_objects o
WHERE o.depth = 0
GROUP BY 1
ORDER BY 1;

SELECT 'K2 child_type глубже уровня (depth>0)' AS section;
SELECT COALESCE(child_type, '<null>') AS child_type, count(*) AS rows_all
FROM configuration_objects
WHERE depth > 0
GROUP BY 1
ORDER BY 2 DESC
LIMIT 40;

SELECT 'K3 длина имени: максимум по всем и по видам' AS section;
SELECT max(length(object_name)) AS max_name_len,
       max(length(name)) AS max_full_len,
       count(*) FILTER (WHERE length(object_name) > 80) AS over_80
FROM configuration_objects;

SELECT 'K3b виды с максимальной длиной имени (top 10)' AS section;
SELECT object_type, max(length(object_name)) AS max_len
FROM configuration_objects
GROUP BY 1
ORDER BY max_len DESC NULLS LAST
LIMIT 10;

SELECT 'K4 уникальность имени внутри вида в одной конфигурации' AS section;
SELECT count(*) AS dup_name_kind_cfg
FROM (
    SELECT configuration_id, object_type, object_name
    FROM configuration_objects
    WHERE depth = 0
    GROUP BY 1, 2, 3
    HAVING count(*) > 1
) d;

SELECT 'K5 нумераторы и последовательности в индексе (примеры)' AS section;
SELECT object_type, child_type, depth, name, parent_name, object_id
FROM configuration_objects
WHERE name ~ '(Нумератор|Последовательность|Sequence|Numerator)'
ORDER BY name
LIMIT 12;

SELECT 'K5b счётчики по этим видам' AS section;
SELECT object_type, COALESCE(child_type,'<null>') AS child_type, depth, count(*)
FROM configuration_objects
WHERE name ~ '(Нумератор|Последовательность|Sequence|Numerator)'
GROUP BY 1, 2, 3
ORDER BY 1, 4 DESC;
