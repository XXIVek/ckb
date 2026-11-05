-- migrate_v58_defined_types.sql
-- ============================================================================
-- Узел V58, шаг П1: определяемый тип (позиция 2.13 нормативного списка «Структура
--       конфигурации.txt») — ОДНА таблица вида: свойства файла регистрации,
--       `InternalInfo` и блок `<Type>` колонками строки вида.
-- Норматив: docs/CONFIGURATION_DEFINED_TYPES_PLAN.md (раздел 1 — круг четырьмя ногами и
--           его совпадение 820/820, раздел 2 — словарь свойств, блок `<Type>`, закрытый
--           словарь 25 ФОРМ значения и пяти классов, разрешение целей, востребованность
--           вида чужими видами, раздел 5 — M1…M8, раздел 6 — решение Q1 (вариант A
--           оператора, 05.11.2026) и Q2…Q7, раздел 7 — план П1…П9).
-- Дата: 2026-11-05.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон ничего не
-- меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла, перенос делает
--             _v58_p1_mirror.py, а не переписывание от руки).
-- Сверка пары — python _cmp_ddl.py.
--
-- То, что `src/generate_ddl.py` конфигурационных таблиц вида не описывает (он держит схему
-- внешнего объекта в `src/ddl_external_report.sql`), называется отдельной строкой отчёта
-- шага П1, а не пропускается — тот же порядок, что у V53…V57 (прецедент раздела 3 плана
-- V57, строки 265–271).
--
-- Отличие от V48…V57 названо прямо, и оно определяет форму хранения: **вид существует во
-- всех четырёх выгрузках эталонного набора, и детей у него нет ни одной строкой**
-- (`DefinedTypes/` — 2 / 1 / 304 / 513 файла; записей индекса состава вида ровно столько
-- же; каталогов содержимого, `Ext/`, `Forms/`, `Templates/`, `Commands/`, модуля — ноль;
-- псевдозаписей индекса — ноль; перечень `ChildObjects` пуст). Круг совпадает четырьмя
-- ногами: файлы ↔ индекс состава ↔ перечень заголовка `configurations.defined_types` ↔
-- перечень корня `Configuration.xml` (820/820; расхождения `file_only`/`index_only`/
-- `header_only`/`root_only`/`uuid_mismatch` пусты, и пустота называется числом 0). Из
-- этого следуют две границы:
--   1. единственное содержательное свойство вида — блок `<Type>` (17 544 значения на круг),
--      и он хранится колонками строки вида, а НЕ второй таблицей (Q1, решение оператора —
--      вариант A: «одна таблица, как в V48/V50/V52»). Значение типа не имеет собственной
--      идентифицируемой цели — в отличие от перечней применения `<Content>`/`<Source>`/
--      `<Use>`, которые V50/V52/V53/V56/V57 клали второй таблицей именно потому, что
--      каждая их строка несёт адрес цели и порядок в файле;
--   2. словарь свойств вида корпусом **не замыкает** (XSD вида в `xsd-schemas/` и
--      `xsd-docs` не найден ни одним поиском — раздел 1.5), поэтому незнакомый тег остаётся
--      значением с состоянием `unknown_tag` и именем виновника в `unknown_property_names`, а
--      не отказом записи (Q7, вариант A; механизм `event_subscriptions` V53,
--      `scheduled_jobs` V54, `bots` V55, `functional_options*` V56/V57).
-- ============================================================================

-- Узел V58 (05.11.2026, позиция 2.13 нормативного списка «Структура конфигурации.txt»):
-- определяемый тип — свойства файла регистрации `DefinedTypes/<Имя>.xml`, его `InternalInfo`
-- и блок `<Type>`. Колонку `configurations.defined_types` (TEXT[]) пишет стадия S2 узла V43.
--
-- Граница «таблица ≠ колонка заголовка»: таблица `defined_types` — СОДЕРЖИМОЕ вида, а
-- колонка configurations.defined_types (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида; внешнего
-- ключа нет осознанно (прецедент V20.1), равенство множеств сторожит

-- Что создаётся и почему ровно так (каждая граница — замер, ссылка в комментариях блоков):
--   1. `defined_types` — свойства вида по четырём тегам `Properties` (все четыре есть во
--      всех 820 файлах: Name 820/820, Synonym 820/820, Comment 820/820, блок `Type`
--      820/820 — раздел 2.1 плана), `InternalInfo` (четыре значения — 820/820, формат
--      UUID 1640/1640 — Q4 и раздел 2.1), блок `<Type>` теми же колонками, что уже живут
--      в `session_parameters` (V48), `common_attributes` (V50) и `filter_criteria` (V52),
--      состояние разбора свойств, цепь ревизий и ключ `UNIQUE (configuration_uuid,
--      object_name, revision_no)` (M1: 247 имён и 243 `uuid` вида встречаются в двух
--      выгрузках сразу — пара BGU2/BP3);
--   2. второй таблицы нет (Q1, вариант A оператора): детей, содержимого и перечней целей у
--      вида ноль (замер 1.2), а значения блока не имеют своей цели; витрина одна;
--   3. классы значений и разрешение целей живут ВНУТРИ записей `types` (ключи `class`,
--      `state`, `resolved`, `target_*`), а не отдельными колонками-счётчиками: распределение
--      11 385 / 4 906 / 950 / 106 / 197 и 17 341 / 197 / 6 — вывод из записей, и колонка с
--      ним стала бы вторым источником знания (правило V43). Закрытый словарь записей
--      (`TYPE_ENTRY_KEYS` слоя разбора П3) задаёт РАЗБОР, а не схема: CHECK по отдельной
--      записи массива PostgreSQL отклоняет текстом «cannot use subquery in check constraint»
--      (замер V48 2.5), поэтому схема держит форму верхнего уровня и согласованность
--      `type_multiplicity` с числом записей, а полноту и словарь записей сверяет шаг П6;
--   4. индексы: `(object_uuid, revision_no)` — карточка объекта по uuid; GIN по `types` —
--      обратный вопрос «в каких определяемых типах встречается цель `X`» оператором
--      containment `types @> '[{"target_full_name":"Catalog.X"}]'` (тот же индекс, что
--      `idx_session_parameters_types_gin` V48, `idx_common_attributes_types_gin` V50 и
--      `idx_filter_criteria_types_gin` V52 — практика блока `<Type>`, а не новое решение);
--      частичный по `type_id` — связка идентификатора типа с его именем для узла V25
--      (разбор `.erf`/`.epf` через `ibcmd` без `.cf` называет типы идентификаторами
--      `<v8:TypeId>`). Отдельного индекса по `configuration_uuid` нет: его обслуживает
--      уникальный индекс цепочки с ведущей колонкой `configuration_uuid` (тот же порядок,
--      что V46, V48…V57).
--
-- Чего узел НЕ делает (границы раздела 8 плана): не трогает `bsl_modules` (модуля у вида нет
-- ни файлом, ни индексом — замер 1.2); не трогает таблицы детей группы A (детей нет); не
-- заполняет перечень `configurations.defined_types` (его пишет стадия S2 узла V43); не
-- утверждает существование цели значения в базе (`exact` — факт наличия строки индекса
-- состава данной выгрузки); не переразрешает класс `defined_type_ref` в слоях V48/V50/V52
-- (замер раздела 3: таких записей в БД 0, их появление зависит от незагруженных слоёв
-- группы A); не утверждает востребованность вида (217 неиспользуемых типов — наблюдение
-- замера, а не колонка — M6).

-- ---------------------------------------------------------------------------
-- Строка определяемого типа. Свойства — по тегам файла регистрации в их порядке
-- (словарь DEFINED_TYPE_PROPERTIES слоя разбора; замер `_v58_p0_probe.py`, раздел 2.1 плана:
-- четыре тега `Properties` — Name, Synonym, Comment, Type — есть во всех 820 файлах круга;
-- верхний уровень файла кроме `Properties` и пустого `ChildObjects` ничего не несёт). Тег
-- `Name` ключуется колонкой object_name; тег `Type` разложен ниже; `InternalInfo` — ниже.
-- Словарь тегов корпусом НЕ замкнут (XSD вида нет, раздел 1.5), поэтому Q7 (вариант A)
-- держит незнакомый тег состоянием и именем виновника, а не отказом записи.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS defined_types (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    -- тег `Synonym` — многоязычный синоним (jsonb по образцу `synonym` V46/V48/V50/V52);
    -- тег есть в 820/820 файлов, пустых синонимов корпус не даёт ни одного (замер 2.1:
    -- multilang 820/820), поэтому отсутствие тега отличается от пустого блока состоянием
    -- properties_state (тот же порядок, что `comment` V53/V54/V55)
    synonym JSONB,
    -- тег `Comment` — комментарий (пустой блок в 803 файлах из 820, непустых 17, наибольшая
    -- длина 167 символов — замер 2.1 и `_v58_p3_offline_probe.py`).
    -- Пустая строка и отсутствующий тег различимы состоянием properties_state, а не
    -- подстановкой значения
    comment TEXT,

    -- `InternalInfo` — идентификаторы вида (Q4, решение — хранить). Несёт четыре значения:
    -- атрибут `name` элемента `xr:GeneratedType`, его атрибут `category`, содержимое блоков
    -- `xr:TypeId` и `xr:ValueId`. По корпусу: все четыре значения есть в 820/820 файлов,
    -- `category` = `DefinedType` 820/820, `name` = `DefinedType.<имя файла>` 820/820, формат
    -- UUID у `TypeId`/`ValueId` 1640/1640 (`_v58_p1_name_check.py`, `_v58_p0_gen_check.py`).
    -- Аргумент не в дешёвости колонок: узел V25 прямо назван в контракте слоем, где без
    -- `.cf` имена типов остаются идентификаторами `<v8:TypeId>`; строка вида отвечает на
    -- вопрос, каким идентификатором описан тип значения, и связывает имя вида с этим
    -- идентификатором. Ключом ни одно из четырёх значений не становится: 1154 различных
    -- идентификатора на 1640 слотов (486 совпадений — общие объекты пары BGU2/BP3,
    -- раздел 1.3), поэтому они читаются поисковым индексом, а не ключом. Формат значения
    -- CHECK'ом не закрепляется (regex отклонял бы будущую выгрузку с другим написанием, а
    -- корпус такого не давал) — формат называется постоянной проверкой шага П6
    -- `tools/check_v58_defined_types.py`.
    generated_name TEXT,
    type_category TEXT,
    type_id TEXT,
    value_id TEXT,
    -- состояние `InternalInfo`: `full` — названы все четыре значения (820/820 по корпусу);
    -- `partial` — названа часть (корпус не давал — это граница разбора, а не ожидаемое
    -- значение); `absent` — блока в файле нет (корпус не давал: блок есть в 820/820).
    -- «Блока нет» и «блок есть, но значений нет» различимы состоянием, а не нулём
    -- (прецеденты picture_state V55, handler_state V53, method_state V54)
    internal_info_state TEXT NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    -- блок `<Type>` — единственное содержательное свойство вида: 820/820 файлов несут ровно
    -- один контейнер `<v8:Type>` (контейнер `TypeSet` — 0 файлов, M4), внутри — от 1 до 657
    -- значений, всего 17 544. Колонки и их состояния — те же, что у V48, V50 и V52:
    -- `type_raw` — исходный XML блока «как в выгрузке»; `type_multiplicity` — кратность по
    -- числу записей (определение оператора от 29.10.2026: одна запись — одиночный тип,
    -- несколько — составной; по кругу `single` 433 / `composite` 387 / `absent` 0, максимум
    -- 657 значений в одном файле (замер 2.2));
    -- `type_parse_state` — что понял разбор; `types` — записи значений в закрытом словаре
    -- разбора; `type_qualifiers` — квалификаторы составного типа «как есть» (размещение по
    -- значениям не замерялось; по корпусу — 191 блок квалификаторов в 182 файлах, девять
    -- файлов несут по два блока: составной тип строка+число — раздел 2.2).
    -- Отличие от V48/V50/V52 ровно одно: словарь ФОРМ значения шире (пять классов вместо
    -- двух) — комментарий `types` ниже и Q3 плана
    type_raw TEXT,
    type_multiplicity TEXT NOT NULL,
    type_parse_state TEXT NOT NULL,
    -- записи значений блока. Ключи записи замкнуты константой слоя разбора `TYPE_ENTRY_KEYS`
    -- (`index`, `value`, `ns_uri`, `class`, `state`, `container`) — форму контейнера называет
    -- запись, отдельной колонки не заводим (образец V52); ключи цели (`resolved`,
    -- `target_full_name`, `target_object_type`, `target_object_uuid`) добавляются ТОЛЬКО у
    -- разрешённого адресом индекса состава значения (прецедент D3 V39/V46: отсутствие ключа
    -- читается как «цели нет»). Классы по замеру круга: `ref_value` 11 385
    -- (`cfg:<Вид>Ref.<Имя>`), `object_value` 4 906 (`cfg:<Вид>Object.<Имя>`), `record_set` 950
    -- (`cfg:<Вид>RecordSet.<Имя>`), `value_manager` 106 (`cfg:<Вид>ValueManager.<Имя>`),
    -- `primitive` 197 (`xs:string` 160, `xs:decimal` 27, `xs:boolean` 6, `xs:dateTime` 4) —
    -- 25 наблюдаемых ФОРМ (раздел 2.3). Словарь V58 СВОЙ, общий
    -- словарь V48/V50/V52 не правится (Q3): в живых слоях новых классов не было ни разу
    -- (`primitive` 209 и `object_ref` 452 на 661 запись — замер раздела 3), а расширение
    -- затронуло бы CHECK'и и постоянные проверки трёх узлов. Разрешение цели значения —
    -- адресом индекса состава `<Вид>.<Имя>` (суффикс формы `Ref`/`Object`/`RecordSet`/
    -- `ValueManager` отбрасывается, текст значения индексом не ищется — прецедент V48):
    -- `exact` 17 341 (2 413 различных разрешённых адресов целей; выведенных из формы значения
    -- адресов 2 419 — шесть `BusinessProcessRoutePoint.*` строк индекса не имеют), `no_target`
    -- 197 (примитивы `xs:*` — цели нет по определению), `unresolved` 6 (все шесть —
    -- `cfg:BusinessProcessRoutePointRef.*`: строк вида `BusinessProcessRoutePoint` в индексе
    -- состава 0 — замер 2.5, состояние индекса, а не дефект разбора; развилка Q6)
    types JSONB NOT NULL DEFAULT '[]',
    type_qualifiers JSONB,
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT defined_types_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT defined_types_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецеденты V50, V52,
    -- V53, V54, V55). Это и есть механизм Q7 (вариант A): корпус словарь не замыкает,
    -- поэтому незнакомый тег не является отказом записи
    CONSTRAINT defined_types_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    -- «всё известно» обязано покрывать обязательную часть строки: блок `<Type>` есть во
    -- всех 820 файлах круга (замер 2.1), поэтому при состоянии `all_known` он назван —
    -- иначе состояние врало бы о полноте разбора (прецеденты
    -- scheduled_jobs_all_known_covers_required_parts V54, bots_all_known_covers_required_parts V55).
    -- Наличия синонима и комментария здесь не требуется осознанно: пустой комментарий —
    -- 78 файлов круга (замер 2.1), и «текста нет» не является незнакомым значением.
    -- `InternalInfo` в эту границу НЕ входит осознанно (замер пробы П1 05.11.2026): блок
    -- лежит вне `<Properties>` и его полнота выражается СОСТОЯНИЕМ `internal_info_state`,
    -- согласованным с его значениями ограничением `defined_types_internal_info_matches_values`;
    -- смешение двух независимых блоков одной границей читалось бы как «свойства не
    -- разобраны» там, где не разобран идентификатор (прецедент V52, где `default_form_state`
    -- и `properties_state` держатся раздельно)
    CONSTRAINT defined_types_all_known_covers_required_parts
        CHECK (properties_state <> 'all_known' OR type_parse_state <> 'absent'),
    CONSTRAINT defined_types_internal_info_state_known
        CHECK (internal_info_state IN ('full', 'partial', 'absent')),
    -- состояние `InternalInfo` выводимо из его значений в обе стороны: `full` держит все
    -- четыре значения, причём имя генерируемого типа равно `DefinedType.` || имя объекта, а
    -- категория равна имени вида (замер 820/820 — `_v58_p1_name_check.py`: тег `Name`
    -- совпадает с именем файла регистрации, атрибут `name` — с `DefinedType.<имя>`,
    -- `category` = `DefinedType`); `partial` держит часть значений и не держит все четыре;
    -- `absent` не держит ничего (прецедент bots_picture_state_matches_value V55)
    CONSTRAINT defined_types_internal_info_matches_values
        CHECK ((internal_info_state = 'full'
                AND generated_name IS NOT NULL AND generated_name <> ''
                AND generated_name = 'DefinedType.' || object_name
                AND type_category = 'DefinedType'
                AND type_id IS NOT NULL AND type_id <> ''
                AND value_id IS NOT NULL AND value_id <> '')
               OR (internal_info_state = 'partial'
                   AND (generated_name IS NOT NULL OR type_category IS NOT NULL
                        OR type_id IS NOT NULL OR value_id IS NOT NULL)
                   AND NOT (generated_name IS NOT NULL AND type_category IS NOT NULL
                            AND type_id IS NOT NULL AND value_id IS NOT NULL))
               OR (internal_info_state = 'absent'
                   AND generated_name IS NULL AND type_category IS NULL
                   AND type_id IS NULL AND value_id IS NULL)),
    -- ---------- блок `<Type>`: те же пять ограничений, что у V48/V50/V52 ----------
    CONSTRAINT defined_types_type_multiplicity_known
        CHECK (type_multiplicity IN ('absent', 'single', 'composite')),
    CONSTRAINT defined_types_type_parse_state_known
        CHECK (type_parse_state IN ('parsed', 'partial', 'unknown_form', 'absent')),
    CONSTRAINT defined_types_types_is_array
        CHECK (jsonb_typeof(types) = 'array'),
    -- «не разбирали» не равно «типа не было»: пустой массив и состояние `absent` связаны с
    -- отсутствием блока `<Type>` в обе стороны (Q3 узла V48, вариант A). По корпусу блока без
    -- значения нет (820/820 несут хотя бы одно), состояние держится границей разбора
    CONSTRAINT defined_types_types_absent_matches_no_block
        CHECK ((types = '[]'::jsonb) = (type_multiplicity = 'absent')
               AND (type_parse_state = 'absent') = (type_multiplicity = 'absent')),
    -- CASE, а не плоский OR: порядок веток CASE гарантирован, поэтому jsonb_array_length не
    -- вызывается для не-массива, и такая строка отклоняется ограничением
    -- defined_types_types_is_array с именем, а не внутренней ошибкой «cannot get array length
    -- of a non-array» (замер V48 2.5, _v48_p1_ddl_probe.sql, случай 6)
    CONSTRAINT defined_types_type_multiplicity_matches_types
        CHECK (CASE WHEN jsonb_typeof(types) <> 'array' THEN TRUE
                    ELSE type_multiplicity = CASE
                             WHEN jsonb_array_length(types) = 1 THEN 'single'
                             WHEN jsonb_array_length(types) > 1 THEN 'composite'
                             ELSE 'absent'
                         END
                   END),
    CONSTRAINT defined_types_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT defined_types_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT defined_types_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна. Замер круга даёт
    -- 247 имён и 243 `uuid` вида, встречающихся в двух выгрузках сразу (пара BGU2/BP3,
    -- `_v58_m1_check.py`); без границы конфигурации две выгрузки слились бы в одну строку.
    -- Перечень заголовка хранит детей массивом имён, и тот же ключ читают витрины видов
    -- V46/V48/V49/V50/V51/V52/V53/V54/V55/V56/V57
    CONSTRAINT defined_types_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);


COMMENT ON TABLE defined_types IS
    'Свойства определяемых типов выгрузки (узел V58, позиция 2.13 списка групп). '
    'НЕ то же, что configurations.defined_types — перечень имён вида в строке заголовка '
    '(узел V43). Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); '
    'uuid метаданных — отдельная колонка, ключом не является (Q2, M1). Закрытый словарь '
    'записей types задаёт РАЗБОР (TYPE_ENTRY_KEYS слоя П3), CHECK выражает только форму '
    'верхнего уровня и согласованность type_multiplicity (замер V48 2.5). Блок <Type> '
    'хранится колонками строки вида, второй таблицы нет (Q1, решение оператора от '
    '05.11.2026 — вариант A по прецеденту V48/V50/V52).';

COMMENT ON COLUMN defined_types.type_multiplicity IS
    'absent | single | composite. Определение оператора от 29.10.2026: одна запись types — '
    'одиночный тип, несколько записей — составной. Выводится из числа записей и закрепляется '
    'CHECK defined_types_type_multiplicity_matches_types. По кругу: single 433, composite 387, '
    'absent 0, максимум 657 значений в одном файле (замер 2.2 плана).';

COMMENT ON COLUMN defined_types.type_parse_state IS
    'parsed | partial | unknown_form | absent — что понял разбор. absent — блока <Type> в '
    'файле не было; partial — разобрана часть значений; unknown_form — форма блока вне '
    'словаря. Словарь тот же, что у session_parameters (V48), common_attributes (V50), '
    'filter_criteria (V52).';

COMMENT ON COLUMN defined_types.types IS
    'Записи значений блока <Type>: обязательные ключи index, container, value, ns_uri, class, '
    'state, resolve_state (словарь разбора TYPE_ENTRY_KEYS; форму контейнера называет запись, '
    'отдельной колонки нет — образец V52; состояние разрешения выражает именно этот ключ, '
    'ключа resolved слоя V48 здесь нет); ключи target_full_name, target_object_type, '
    'target_object_uuid — только у разрешённого индексом состава значения (состояние exact), '
    'ключ reason — только у записи с состоянием unknown_form. Классы замкнуты словарём слоя '
    'V58: ref_value 11385, object_value 4906, record_set 950, value_manager 106, primitive 197 '
    'на 17544 записи (замер 2.3). Из 17341 записей exact разрешено 2413 различных адресов '
    'целей; выведенных из формы значения адресов 2419 — шесть BusinessProcessRoutePoint.* '
    'строк индекса состава не имеют (замер 2.5, пересчёт _v58_p3_offline_probe.py). Классы '
    'object_ref/defined_type_ref слоёв V48/V50/V52 этим узлом не переопределяются (Q3).';

COMMENT ON COLUMN defined_types.internal_info_state IS
    'full | partial | absent — что файл дал из блока InternalInfo. full держит все четыре '
    'значения, имя генерируемого типа равно DefinedType. || object_name, категория равна '
    'DefinedType (замер 820/820, _v58_p1_name_check.py); ключом ни один из четырёх '
    'идентификаторов не становится (1154 различных значения на 1640 слота — раздел 1.3).';

COMMENT ON COLUMN defined_types.generated_name IS
    'Атрибут name элемента xr:GeneratedType — имя генерируемого платформой типа значения '
    '(DefinedType.<ИмяОбъекта>). Связывает имя вида с идентификатором, которым тот описан в '
    'разборе бинарных внешних объектов (узел V25: без .cf имена типов остаются <v8:TypeId>).';


-- ---------------------------------------------------------------------------
-- Витрины узла V58. Текущее состояние строки определяемого типа выводится тем же
-- порядком, что витрины V46/V48/V49/V50/V51/V52/V53/V54/V55/V56/V57: строка относится к
-- максимальной ревизии в пределах ключа своей цепочки; признак коммита на круг не влияет
-- (решение A1). Имя витрины задаёт не этот файл: его отдаёт current_view() по реестру
-- CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py. Второй витрины у узла нет (Q1, M7): второй таблицы у вида
-- нет — детей, содержимого и перечней целей со своей схемой у него ноль (замер 1.2).
-- `types` и `type_multiplicity` перечислены своими колонками: содержательный запрос по цели
-- значения идёт по витрине, containment @> на витрине работает так же, как на таблице
-- (прецедент V48 2.5).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_defined_types AS
SELECT dt.id,
       dt.configuration_uuid, dt.object_uuid, dt.object_name, dt.full_name,
       dt.synonym, dt.comment,
       dt.generated_name, dt.type_category, dt.type_id, dt.value_id,
       dt.internal_info_state,
       dt.properties_state, dt.unknown_property_names,
       dt.type_raw, dt.type_multiplicity, dt.type_parse_state,
       dt.types, dt.type_qualifiers, dt.source_path,
       dt.created_at, dt.revision_no, dt.changed_at, dt.changed_by, dt.is_committed
FROM defined_types dt
WHERE NOT EXISTS (SELECT 1 FROM defined_types h
                  WHERE h.configuration_uuid = dt.configuration_uuid
                    AND h.object_name = dt.object_name
                    AND h.revision_no > dt.revision_no);

-- ---------------------------------------------------------------------------
-- Индексы узла V58 (определяемые типы, позиция 2.13). Отдельного индекса по
-- configuration_uuid у таблицы нет: у строки вида его обслуживает уникальный индекс
-- цепочки с ведущей колонкой configuration_uuid — им же пользуются предикат витрины и
-- чистка стадии по конфигурации (тот же порядок, что V46, V48…V57).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_defined_types_object_uuid_revision
    ON defined_types(object_uuid, revision_no);
-- GIN по содержимому types отвечает на обратный вопрос «в каких определяемых типах
-- встречается цель Catalog.X» оператором containment:
--   types @> '[{"target_full_name":"Catalog.Организации"}]'
-- Тот же индекс, что idx_session_parameters_types_gin (V48),
-- idx_common_attributes_types_gin (V50) и idx_filter_criteria_types_gin (V52): блок <Type>
-- во всех узлах, которые его хранят, читается containment-запросом (замеры 2.5 V48,
-- 2.4 V50, 2.6 V52). Для V58 вопрос стоит так же остро: 3 659 ссылок `cfg:DefinedType.*`
-- из файлов чужих видов и 17 544 значения круга (раздел 2.6).
CREATE INDEX IF NOT EXISTS idx_defined_types_types_gin
    ON defined_types USING gin (types jsonb_path_ops);
-- Частичный индекс по идентификатору генерируемого типа: связывает идентификатор, которым
-- тип назван в разборе бинарных внешних объектов (узел V25: без `.cf` имена типов остаются
-- `<v8:TypeId>`), с его именем в конфигурации. Частичный — потому что при состояниях
-- `partial` и `absent` значений нет, а индекс по NULL смысла не имеет (прецедент
-- idx_bots_picture_object_uuid V55). По `value_id` индекса нет осознанно: он является
-- идентификатором значения, а не типа, и адресного вопроса по нему слой не ставит.
CREATE INDEX IF NOT EXISTS idx_defined_types_type_id
    ON defined_types(type_id) WHERE type_id IS NOT NULL;

SELECT 'Определяемые типы (узел V58) добавлены в схему!' AS status;

