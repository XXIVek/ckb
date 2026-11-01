-- migrate_v52_filter_criteria.sql
-- ============================================================================
-- Узел V52, шаг П1: критерий отбора (позиция 2.7 нормативного списка «Структура
--       конфигурации.txt») — таблица вида и таблица строк его условия `<Content>`,
--       витрины текущего состояния и индексы.
-- Норматив: docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md (раздел 1.3 — коллизия uuid,
--           раздел 2 — словарь свойств и формы значений, раздел 5 — M1…M5,
--           раздел 6 — решения Q1…Q10, раздел 7 — план П1…П8).
-- Дата: 2026-11-01.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон ничего не
-- меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла).
-- Сверка пары — python _cmp_ddl.py.
--
-- Отличие от V51 названо прямо. V51 правил и шаг 1 (src/generate_ddl.py), потому что дети
-- вида живут в тех же таблицах, что построены под внешний объект, и им требовались ноги
-- области видимости. У V52 те же ноги (configuration_uuid, parent_uuid) в
-- forms/form_ext/commands добавил V51, поэтому миграция создаёт только таблицы вида и
-- ничего в существующих таблицах не меняет — замер _v52_q3_children_probe.py и
-- _v52_q3_legs_probe.sql (68/66/1 строк детей с parent_type='configuration_objects';
-- у form_ext ноги configuration_uuid нет — фильтр идёт связкой по form_id, CHECK на
-- parent_type в схеме нет ни у одной из трёх таблиц). Схему детей Q3 (вариант A) узел не
-- трогает.
--
-- Что создаётся и почему ровно так (каждая граница — замер, ссылка в комментариях блоков):
--   1. `filter_criteria` — свойства вида по 11 тегам `Properties` (порядок тегов файла;
--      набор замкнут: один и тот же во всех 15 файлах четырёх выгрузок), блок `<Type>`
--      закрытыми словарями V48/V50 с собственной веткой `TypeSet` (Q6 узла V52 — решение
--      оператора), состояния ссылок на форму (M5: BGU2/BP3 дают пустые теги), перечни
--      детей (`form_names`, `command_uuids` — других видов детей у вида нет, замер 1.2),
--      цепь ревизий и ключ `UNIQUE (configuration_uuid, object_name, revision_no)`:
--      граница конфигурации обязательна, потому что 15 верхних строк вида дают 14 uuid
--      (`FilterCriterion.СвязанныеДокументы` 18bf6916… стоит в BGU2 и BP3), а имя —
--      общее для четырёх конфигураций (замер 1.3, M1);
--   2. `filter_criterion_content` — строки блока `<Content>` файла регистрации
--      (1 219 целей: 727 BGU2 + 492 BP3; MinCfg и KomMag дают пустой блок — состояние
--      `empty_content` строки вида). Без своей цепи ревизий (Q2, вариант A): ключ
--      начинается с `filter_criterion_id`, `ON DELETE CASCADE` снимает строки вместе с
--      ревизией вида, текущность читается витриной связкой (прецедент
--      `common_attribute_targets` V50);
--   3. витрины `v_current_filter_criteria` (предикат по ключу цепи) и
--      `v_current_filter_criterion_content` (связка по `filter_criterion_id`); имена
--      витрин задаёт реестр `CONFIGURATION_VERSIONED_TABLES` (src/current_revision.py),
--      безцепочечная таблица — `CONFIGURATION_UNVERSIONED_TABLES`
--      (src/external_table_writer.py);
--   4. индексы: (object_uuid, revision_no), GIN по `types`, `target_full_name`,
--      частичный по `target_object_uuid`. Отдельного индекса по `configuration_uuid` нет:
--      его обслуживает уникальный индекс цепочки той же таблицы (тот же порядок, что
--      V46/V48/V49/V50/V51).
--
-- Чего миграция НЕ делает (границы узла названы в плане, раздел 8): колонок состояний
-- слотов `Help`/`AdditionalIndexes` не заводит — тега `Help` в `Properties` нет ни в одном
-- из 15 файлов круга (Q8, вариант A; негативный факт держит tools/check_v52_filter_criteria.py);
-- ресурсы справки формы (`Ext/Help.xml`, `Ext/Help/`) не хранит (Q7, вариант A —
-- наблюдение называется ответом стадии); тексты модулей вида не читает — их пишет узел V47
-- в `bsl_modules` (замер П0: 11 строк по объектам вида уже лежат в базе).
-- ============================================================================

-- Узел V52 (01.11.2026, позиция 2.7 нормативного списка «Структура конфигурации.txt»):
-- критерий отбора и строки его условия (блок `<Content>` файла регистрации вида).
-- Норматив — docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md (раздел 1.3 — коллизия uuid,
-- раздел 2 — словарь свойств и формы значений, раздел 5 — M1…M5, раздел 6 — решения
-- Q1…Q10, раздел 7 — план П1…П8). Для живой БД, где таблицы уже созданы, —
-- migrate_v52_filter_criteria.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `filter_criteria` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.filter_criteria (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида;
-- внешнего ключа нет осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v52_filter_criteria.py (П6), а не схема.
--
-- Ключ обязан включать конфигурацию (M1, Q2 вариант A; замеры _v52_p0_db_probe.sql и
-- _v52_q2_key_probe.sql): 15 верхних строк вида дают 14 различных uuid —
-- `FilterCriterion.СвязанныеДокументы` (18bf6916-83cc-41e5-a35b-1489450ae632) стоит и в
-- BGU2, и в BP3; имя `СвязанныеДокументы` встречается в четырёх конфигурациях с тремя
-- различными uuid, всего совпадающих имён вида — 7. Ни uuid, ни имя по отдельности строки
-- двух конфигураций не различают, поэтому граница configuration_uuid обязательна при любой
-- форме ключа (тот же приём, что `exchange_plans` V51, `common_attributes` V50,
-- `session_parameters` V48). `object_uuid` заводится отдельной колонкой и поисковым
-- индексом, но ключом не становится.
-- Свойств — ровно 11 тегов `Properties`: один и тот же набор во всех 15 файлах четырёх
-- выгрузок, порядок тегов одинаков везде (различных наборов по файлам — 1 на выгрузку).
-- Словарь `FILTER_CRITERION_PROPERTIES` (src/configuration_filter_criteria.py) задаётся
-- порядком тегов файла: пропуск позиции означал бы молчаливую потерю свойства
-- (прецеденты `COMMON_ATTRIBUTE_PROPERTIES` V50, `EXCHANGE_PLAN_PROPERTIES` V51).
-- CHECK по ЗНАЧЕНИЯМ свойств не кладётся по прецеденту V50/V51 (Q7 узла V50, вариант A):
-- закрытость держит измеренный `PROPERTY_VALUE_DICTIONARY`, значение вне него остаётся
-- значением с состоянием `unknown_value` и названным виновником, а не отказом записи.
-- Состояния РАЗБОРА (`properties_state`, `children_state`, `content_state`, состояния
-- ссылок на форму) замкнуты CHECK'ом: это вывод слоя, а не значение выгрузки.
--
-- `Comment` в MinCfg — скаляр («какой то комментарий»), в остальных выгрузках — пустой тег
-- (замер 2.1). Колонка TEXT принимает обе формы: вид разбора задаёт форма значения, а не
-- имя тега (приём V50/V51). Это названо здесь, потому что словарь плана обмена (40 тегов)
-- переиспользовать нельзя: по именам совпадают 7 тегов, только у критерия — 4
-- (`Type`, `Content`, `DefaultForm`, `AuxiliaryForm`), только у плана обмена — 33.
--
-- Слотов `Help`/`AdditionalIndexes` у вида нет: тега `Help` в `Properties` нет ни в одном
-- из 15 файлов круга (замер П0). Колонок состояний слотов не заводится (Q8 узла V52,
-- вариант A): константная колонка с единственным возможным значением описывала бы то, чего
-- в выгрузке нет, и отличала бы узел от замера. Негативный факт держит проверка П6
-- эталоном «0 тегов `Help`/`AdditionalIndexes` на 15 файлов круга».
--
-- Перечни детей — только формы и команды (замер 1.2: строк `Attribute`, `TabularSection`
-- и `Template` этого вида в индексе состава нет ни в одной выгрузке). Формы адресуются
-- ИМЕНЕМ: uuid формы повторяется между конфигурациями (замер V51 3.2 — 42 349 общих uuid),
-- а имя уникально в пределах вида (`Forms/<Имя>.xml`); команда — uuid, он держится
-- элементом `<Command uuid>` файла вида. Пустой перечень — NULL, а не '{}' (границы K1–K6
-- узла V43 и контракт ===EMPTY); порядок элементов побайтовый (COLLATE "C").
CREATE TABLE IF NOT EXISTS filter_criteria (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    -- свойства вида в порядке тегов файла (словарь FILTER_CRITERION_PROPERTIES); тег `Name`
    -- ключуется колонкой object_name, тег `Type` разобран блоком ниже, тег `Content` —
    -- второй таблицей пары (filter_criterion_content)
    synonym JSONB,
    comment TEXT,
    -- блок <Type> (Q6 узла V52, вариант A): те же закрытые словари, что легли в
    -- `session_parameters` (V48) и `common_attributes` (V50). Отличие названо прямо:
    -- KomMag даёт `<v8:TypeSet>cfg:DocumentRef</v8:TypeSet>`, а существующий разбор
    -- V48/V50 такой формы содержимого не имеет и дал бы запись `unknown_form` с
    -- потерянным значением (замер П2) — поэтому узел V52 разбирает `TypeSet` собственной
    -- веткой парсера (решение оператора при закрытии Q6). Форма контейнера называется
    -- записью `types[].container` ('Type' | 'TypeSet'), отдельной колонки не заводим:
    -- словарь записи jsonb задаёт разбор одной константой (прецедент `TYPE_ENTRY_KEYS`
    -- узла V48), а не схема — CHECK по отдельной записи массива PostgreSQL отклоняет
    -- текстом «cannot use subquery in check constraint» (замер V48 2.5).
    type_raw TEXT,
    type_multiplicity TEXT NOT NULL,
    type_parse_state TEXT NOT NULL,
    types JSONB NOT NULL DEFAULT '[]',
    type_qualifiers JSONB,
    use_standard_commands BOOLEAN,
    default_form TEXT,
    auxiliary_form TEXT,
    list_presentation JSONB,
    extended_list_presentation JSONB,
    explanation JSONB,
    -- состояния ссылок на форму (M5): пустой тег — состояние выгрузки, а не потеря и не
    -- «формы нет». BGU2 и BP3 дают пустые `DefaultForm`/`AuxiliaryForm` (7 и 6 файлов),
    -- MinCfg и KomMag — скаляр-ссылку. `unknown_form` — граница структуры, которой корпус
    -- не давал; `absent` — тега нет в файле (замер: во всех 15 файлах круга тег есть).
    -- Разрешение ссылки отдельными колонками не дублируется: цель — собственный ребёнок
    -- вида, он же лежит в `form_names` этой же строки (тот же приём, что V51).
    default_form_state TEXT NOT NULL,
    auxiliary_form_state TEXT NOT NULL,
    -- перечни детей строки вида (другого вида детей у вида нет — замер 1.2)
    form_names TEXT[],
    command_uuids UUID[],
    -- содержимое вида — строки блока `<Content>` файла регистрации (M4: файла
    -- `FilterCriteria/<Имя>/Ext/Content.xml` в выгрузке нет, в отличие от плана обмена).
    -- Пустой блок называется состоянием, а не нулём и не отсутствием строк (M5: MinCfg и
    -- KomMag дают `<Content/>`); счётчик — вывод разбора круга, вручную не переписывается
    content_state TEXT NOT NULL,
    content_count INTEGER NOT NULL,
    -- «детей нет» и «круг снят» различаются состоянием children_state, а не нулями
    -- перечней (словарь V51 переиспользуется: тот же вывод об одних и тех же виновниках)
    children_state TEXT NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT filter_criteria_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT filter_criteria_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50)
    CONSTRAINT filter_criteria_unknown_names_match_state
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state <> 'all_known'
                AND COALESCE(array_length(unknown_property_names, 1), 0) > 0)),
    CONSTRAINT filter_criteria_children_state_known
        CHECK (children_state IN ('with_children', 'empty_content',
                                  'indexed_no_file', 'file_not_in_index')),
    CONSTRAINT filter_criteria_form_ref_states_known
        CHECK (default_form_state IN ('with_reference', 'empty_value', 'absent',
                                      'unknown_form')
               AND auxiliary_form_state IN ('with_reference', 'empty_value', 'absent',
                                           'unknown_form')),
    -- пустое значение и отсутствие тега не держат текста, скаляр-ссылка и структура —
    -- держат (структура сохраняется текстом, вложенность называется состоянием)
    CONSTRAINT filter_criteria_form_ref_value_matches_state
        CHECK ((default_form IS NULL) = (default_form_state IN ('empty_value', 'absent'))
               AND (auxiliary_form IS NULL) = (auxiliary_form_state IN ('empty_value',
                                                                       'absent'))),
    -- <Type>: «не разобрали» не равно «типа не было» — те же три ограничения, что у
    -- session_parameters (V48) и common_attributes (V50), потому что код и схема обязаны
    -- отвечать одинаково; форму CASE, а не плоский OR, задал замер V48 2.5 (иначе для
    -- не-массива вызывается jsonb_array_length и строка отклоняется внутренней ошибкой
    -- «cannot get array length of a non-array», а не именем ограничения)
    CONSTRAINT filter_criteria_type_multiplicity_known
        CHECK (type_multiplicity IN ('absent', 'single', 'composite')),
    CONSTRAINT filter_criteria_type_parse_state_known
        CHECK (type_parse_state IN ('parsed', 'partial', 'unknown_form', 'absent')),
    CONSTRAINT filter_criteria_types_is_array
        CHECK (jsonb_typeof(types) = 'array'),
    CONSTRAINT filter_criteria_types_absent_matches_no_block
        CHECK ((types = '[]'::jsonb) = (type_multiplicity = 'absent')
               AND (type_parse_state = 'absent') = (type_multiplicity = 'absent')),
    CONSTRAINT filter_criteria_type_multiplicity_matches_types
        CHECK (CASE WHEN jsonb_typeof(types) <> 'array' THEN TRUE
                    ELSE type_multiplicity = CASE
                             WHEN jsonb_array_length(types) = 1 THEN 'single'
                             WHEN jsonb_array_length(types) > 1 THEN 'composite'
                             ELSE 'absent'
                         END
                END),
    -- пустой перечень называется состоянием, а не отсутствием строк (прецедент
    -- common_attributes.content_state V50); согласование состояния и счётчика замкнуто
    -- здесь, а число строк круга сверяет проверка узла П6
    CONSTRAINT filter_criteria_content_state_known
        CHECK (content_state IN ('with_content', 'empty_content')),
    CONSTRAINT filter_criteria_content_count_matches_state
        CHECK ((content_state = 'empty_content' AND content_count = 0)
               OR (content_state = 'with_content' AND content_count > 0)),
    CONSTRAINT filter_criteria_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT filter_criteria_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT filter_criteria_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна, потому что один
    -- uuid вида встречается в двух конфигурациях, а имя — в четырёх (замер 1.3)
    CONSTRAINT filter_criteria_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- Строки блока `<Content>` файла регистрации — состав вида, то есть ответ на вопрос
-- «по каким полям метаданных можно отбирать» (замеры _v52_p0_content_probe.py и
-- _v52_q4_resolve_probe.py: BGU2 727 целей, BP3 492, всего 1 219; MinCfg и KomMag дают
-- пустой блок — состояние `empty_content` строки вида, а не пустая таблица и не ноль).
-- Элемент перечня — ОДИН тег `Item` с текстом-ссылкой, без атрибутов и без вложенных
-- тегов (замер 2.2): ни uuid, ни имени у элемента нет, идентичность даёт только порядок
-- в файле (`ordinal`) — тот же приём, что `exchange_plan_content` (V51) и
-- `common_attribute_targets` (V50).
--
-- Таблица НЕ версионируется своей цепочкой (Q2 узла V52, вариант A по прецеденту V50):
-- ключ начинается с `filter_criterion_id`, а он указывает на конкретную строку
-- `filter_criteria`, то есть на конкретную ревизию; ON DELETE CASCADE снимает строки
-- условия вместе с ревизией вида. Текущность строки условия выводится из витрины
-- `v_current_filter_criteria` связкой, а не поиском максимума по своей цепи, поэтому
-- колонок `revision_no`/`changed_*` здесь нет — и записи в
-- `CONFIGURATION_VERSIONED_TABLES` нет (запись означала бы цепь, которой у таблицы нет);
-- таблица названа исключением `CONFIGURATION_UNVERSIONED_TABLES`
-- (src/external_table_writer.py) по прецеденту `role_rights` V49.
-- `configuration_uuid` повторяет значение строки вида осознанно (тот же порядок, что
-- role_rights V49 и common_attribute_targets V50): запрос «в каких критериях отбора
-- участвует это поле» идёт по строкам условия, и без колонки он требовал бы связки с
-- таблицей вида и с её витриной на каждом шаге.
--
-- Цели разрешаются индексом состава (Q4, вариант A): строк `attributes` чужих видов в базе
-- нет (группа A модели для документов, справочников и прочих видов не загружена), но
-- индекс состава их содержит (`child_type = Attribute` — 79 502 строки по всей базе).
-- Замер _v52_q4_resolve_probe.py: все 1 219 целей данного круга разрешаются состоянием
-- `exact`; `prefix_only` и `unresolved` — граница, запрещающая молчать о неразрешённой
-- цели, а не ожидаемое значение.
--
-- Имена колонок отличаются от текста П1 плана (`target_ref_text`) и это названо: текстом
-- ссылки является `target_full_name` (точечное имя цели целиком), второй колонки с тем же
-- содержимым не заводим — две колонки одного смысла дали бы два ответа на один вопрос.
-- Форма пары «тег + имя» берётся у `exchange_plan_content` (V51), где `target_tag` держит
-- измеренный тег элемента (`Item` во всех 1 219 записях), а не выдуманное состояние.
CREATE TABLE IF NOT EXISTS filter_criterion_content (
    id BIGSERIAL PRIMARY KEY,
    filter_criterion_id BIGINT NOT NULL
        REFERENCES filter_criteria(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    criterion_object_uuid UUID NOT NULL,
    criterion_full_name TEXT NOT NULL,
    -- позиция записи в файле; порядок писатель не меняет (прецедент target_ordinal V49,
    -- ordinal V50/V51) — он и есть обещание сборки перечня `<Content>` из строк
    ordinal INTEGER NOT NULL,
    target_tag TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    -- тип цели — часть точечного имени до первой точки (замер 2.2: Document, Catalog,
    -- InformationRegister и другие); остальной путь участвует в разрешении индексом
    target_object_type TEXT NOT NULL,
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT filter_criterion_content_names_not_blank
        CHECK (criterion_full_name <> '' AND target_full_name <> ''
               AND target_tag <> '' AND target_object_type <> ''),
    CONSTRAINT filter_criterion_content_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    -- состояние разрешения согласно ссылке и остатку пути (тот же контракт, что
    -- role_rights V49, common_attribute_targets V50, exchange_plan_content V51):
    -- «цель найдена» и «цель не найдена» различимы структурой строки, а не молчанием
    CONSTRAINT filter_criterion_content_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_object_uuid IS NOT NULL AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved' AND target_object_id IS NULL
                AND target_object_uuid IS NULL AND target_unresolved_path IS NOT NULL)),
    CONSTRAINT filter_criterion_content_ordinal_non_negative CHECK (ordinal >= 0),
    -- Q2, вариант A: повтор цели внутри одной ревизии вида — ошибка разбора, а не вторая
    -- строка (замеров повторов на круге — 0); ordinal различает записи и сохраняет
    -- порядок перечня. Границы configuration_uuid в этом ключе нет осознанно: её держит
    -- FK на строку вида, в ключах которой configuration_uuid уже есть (отличие от
    -- exchange_plan_content, где своей цепи у перечня нет и он версионируется родителем)
    CONSTRAINT filter_criterion_content_criterion_ordinal_key
        UNIQUE (filter_criterion_id, ordinal)
);

-- Витрины текущего состояния узла V52. Предикат — тот же, что у витрин
-- V46/V48/V49/V50/V51: строка относится к максимальной ревизии в пределах ключа своей
-- цепочки; признак коммита на круг не влияет (решение A1). Имена витрин задаёт не этот
-- файл: их отдаёт current_view() по реестру CONFIGURATION_VERSIONED_TABLES
-- (src/current_revision.py), а расхождение имени ловит tools/check_v19_revisions.py —
-- кроме `v_current_filter_criterion_content`: своей цепи ревизий у строк условия нет
-- (Q2 узла V52, вариант A), поэтому она строится связкой по filter_criterion_id с
-- витриной строки вида (прецедент v_current_common_attribute_targets V50).
CREATE OR REPLACE VIEW v_current_filter_criteria AS
SELECT fc.id,
       fc.configuration_uuid, fc.object_uuid, fc.object_name, fc.full_name,
       fc.synonym, fc.comment, fc.type_raw, fc.type_multiplicity, fc.type_parse_state,
       fc.types, fc.type_qualifiers, fc.use_standard_commands, fc.default_form,
       fc.auxiliary_form, fc.list_presentation, fc.extended_list_presentation,
       fc.explanation, fc.default_form_state, fc.auxiliary_form_state,
       fc.form_names, fc.command_uuids, fc.content_state, fc.content_count,
       fc.children_state, fc.properties_state, fc.unknown_property_names,
       fc.source_path, fc.created_at, fc.revision_no, fc.changed_at, fc.changed_by,
       fc.is_committed
FROM filter_criteria fc
WHERE NOT EXISTS (SELECT 1 FROM filter_criteria h
                  WHERE h.configuration_uuid = fc.configuration_uuid
                    AND h.object_name = fc.object_name
                    AND h.revision_no > fc.revision_no);

-- Витрина строк условия строит текущность связкой с v_current_filter_criteria: своей цепи
-- ревизий у них нет, filter_criterion_id указывает на конкретную ревизию строки вида.
CREATE OR REPLACE VIEW v_current_filter_criterion_content AS
SELECT cc.id,
       cc.filter_criterion_id, cc.configuration_uuid, cc.criterion_object_uuid,
       cc.criterion_full_name, cc.ordinal, cc.target_tag, cc.target_full_name,
       cc.target_object_type, cc.target_object_id, cc.target_object_uuid,
       cc.target_resolve_state, cc.target_unresolved_path, cc.created_at
FROM filter_criterion_content cc
JOIN v_current_filter_criteria cf ON cf.id = cc.filter_criterion_id;

-- Индексы узла V52 (критерий отбора, позиция 2.7). Отдельного индекса по
-- configuration_uuid у filter_criteria и filter_criterion_content не заводим: у строки вида
-- его обслуживает уникальный индекс цепочки с ведущей колонкой configuration_uuid — им же
-- пользуются предикат витрины и чистка стадии по конфигурации (тот же порядок, что
-- V46/V48/V49/V50/V51); у строк условия ведущая колонка уникального индекса —
-- filter_criterion_id, то есть снятие круга и связка с витриной идут по нему.
CREATE INDEX IF NOT EXISTS idx_filter_criteria_object_uuid_revision
    ON filter_criteria(object_uuid, revision_no);
-- GIN по types — тот же индекс, что idx_session_parameters_types_gin (V48) и
-- idx_common_attributes_types_gin (V50): карточка «какие критерии отбора имеют тип по
-- ссылке на этот вид/определяемый тип» идёт по содержимому массива (containment @>),
-- а не по отдельной колонке значения — запись types закрыта словарём разбора, а не
-- колонками (замер V48 2.5: CHECK подзапросом в CHECK не выражается).
CREATE INDEX IF NOT EXISTS idx_filter_criteria_types_gin
    ON filter_criteria USING GIN (types);
-- Строки условия: запрос карточки «в каких критериях отбора участвует это поле метаданных»
-- идёт по точечному имени цели, для разрешённых ссылок — по uuid цели (те же два индекса,
-- что idx_exchange_plan_content_* узла V51). Отдельного индекса по ordinal нет: он ведомая
-- колонка уникального индекса.
CREATE INDEX IF NOT EXISTS idx_filter_criterion_content_target_full_name
    ON filter_criterion_content(target_full_name);
CREATE INDEX IF NOT EXISTS idx_filter_criterion_content_target_object_uuid
    ON filter_criterion_content(target_object_uuid) WHERE target_object_uuid IS NOT NULL;
