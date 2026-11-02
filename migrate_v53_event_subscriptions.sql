-- migrate_v53_event_subscriptions.sql
-- ============================================================================
-- Узел V53, шаг П1: подписка на событие (позиция 2.8 нормативного списка «Структура
--       конфигурации.txt») — таблица вида и таблица записей её блока `<Source>`,
--       витрины текущего состояния и индексы.
-- Норматив: docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md (раздел 1 — круг и коллизии,
--           раздел 2 — словарь свойств и формы целей, раздел 5 — M1…M7,
--           раздел 6 — решения Q1…Q8, раздел 7 — план П1…П8).
-- Дата: 2026-11-02.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон ничего не
-- меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла).
-- Сверка пары — python _cmp_ddl.py.
--
-- Отличие от V51 и V52 названо прямо. У плана обмена (V51) и критериев отбора (V52) есть
-- дети вида — реквизиты, табличные части, формы, макеты, команды; они пишутся ОБЩИМИ
-- таблицами детей, и миграции приходилось заводить для них ноги области видимости. У
-- подписки на события детей НЕТ (замер раздела 1.2: в `ConfigDumpInfo.xml` запись вида —
-- самозакрывающийся элемент, каталогов содержимого во всех четырёх выгрузках ноль), поэтому
-- миграция создаёт ровно две таблицы — строку вида и строки блока `<Source>` — и ни одной
-- существующей таблицы не меняет. Колонок `children_state`, `form_names`, `command_uuids`
-- здесь нет осознанно (M2): состояние «детей нет» описывало бы то, чего вид не имеет, а
-- ровность круга сторожит проверка П6 обходом подкаталогов (она обязана дать ноль).
--
-- Что создаётся и почему ровно так (каждая граница — замер, ссылка в комментариях блоков):
--   1. `event_subscriptions` — свойства вида по 6 тегам `Properties` (порядок тегов файла;
--      набор замкнут: один и тот же во всех 772 файлах четырёх выгрузок, XSD метаданных в
--      выгрузках нет — раздел 1.5), состояние имени события (словарь 18 имён держит разбор,
--      а не схема — Q6, вариант A по прецеденту Q7 узла V50), обработчик текстом и
--      разложенным (Q2, решение оператора), состояние блока `<Source>` с его счётчиком,
--      цепь ревизий и ключ `UNIQUE (configuration_uuid, object_name, revision_no)`: граница
--      конфигурации обязательна, потому что 162 uuid и 192 имён подписок стоят одновременно
--      в BGU2 и BP3, а 772 строки круга дают 610 различных uuid и 580 различных имён
--      (замер `_v53_m1_probe.py`, M1);
--   2. `event_subscription_sources` — строки блока `<Source>` файла регистрации (25 100
--      записей: Type 24 729 + TypeSet 371; BGU2 11 706, BP3 13 379, KomMag 10, MinCfg 5;
--      пустых блоков корпуса ноль — состояние `empty_sources` строки вида остаётся
--      границей, а не ожидаемым значением, M4). Без своей цепи ревизий (Q4, вариант A):
--      ключ начинается с `event_subscription_id`, `ON DELETE CASCADE` снимает строки вместе
--      с ревизией вида, текущность читается витриной связкой (прецедент
--      `filter_criterion_content` V52, `common_attribute_targets` V50, `role_rights` V49);
--   3. витрины `v_current_event_subscriptions` (предикат по ключу цепи) и
--      `v_current_event_subscription_sources` (связка по `event_subscription_id`); имена
--      витрин задаёт реестр `CONFIGURATION_VERSIONED_TABLES` (src/current_revision.py),
--      безцепочечная таблица — `CONFIGURATION_UNVERSIONED_TABLES`
--      (src/external_table_writer.py);
--   4. индексы: (object_uuid, revision_no), частичный по `handler_module`, по
--      `target_full_name`, частичные по `target_object_uuid` и `target_meta_type`.
--      Отдельного индекса по `configuration_uuid` нет: его обслуживает уникальный индекс
--      цепочки той же таблицы (тот же порядок, что V46/V48/V49/V50/V51/V52).
--
-- Чего миграция НЕ делает (границы узла названы в плане, раздел 8): внешнего ключа на
-- `common_modules` у `handler_module` нет по решению оператора Q2 (вариант A) и по
-- прецеденту V20.1: обработчик не уникален на подписку (248 уникальных значений при 311
-- подписках в BGU2), а связь читается витриной `v_current_common_modules` по имени —
-- колонка uuid дублировала бы состояние, которое витрина даёт. Колонки `defined_types` для
-- целей `cfg:DefinedType.<Имя>` (139 записей) не заводится: узла определяемых типов нет.
-- Колонок слотов `Help`/`Interface` у вида нет: соответствующих тегов `Properties` в 772
-- файлах круга нет ни одного (замер раздела 2 — словарь ровно из шести тегов).
-- ============================================================================

-- Узел V53 (02.11.2026, позиция 2.8 нормативного списка «Структура конфигурации.txt»):
-- подписка на событие и записи её блока `<Source>` (круг целей срабатывания).
-- Норматив — docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md (раздел 1 — круг и коллизия
-- uuid/имён, раздел 2 — словарь свойств, формы целей и словарь событий, раздел 5 — M1…M7,
-- раздел 6 — решения Q1…Q8, раздел 7 — план П1…П8). Для живой БД, где таблицы уже созданы,
-- — migrate_v53_event_subscriptions.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `event_subscriptions` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.event_subscriptions (TEXT[], узел V43, пункт 8 файла оператора
-- «Дочерние свойства для конфигурации.txt») — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет
-- осознанно (прецедент V20.1), равенство множеств сторожит tools/check_v53_event_subscriptions.py.

-- ---------------------------------------------------------------------------
-- Строка подписки на событие. Свойства — по тегам файла регистрации в их порядке
-- (словарь EVENT_SUBSCRIPTION_PROPERTIES разбора, раздел 2 плана: ровно 6 тегов
-- `Properties` во всех 772 файлах четырёх выгрузок). Тег `Name` ключуется колонкой
-- object_name, тег `Source` — вторая таблица пары (event_subscription_sources).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    synonym JSONB,
    -- пустой `Comment` — NULL, отдельного состояния не заводим (Q7, вариант A; замер:
    -- пустых комментариев 297 в BGU2 и 1 в KomMag — это отсутствие текста, а не свойство)
    comment TEXT,
    -- тег `Event` — имя события. Значение хранится как в выгрузке; состояние говорит,
    -- известно ли имя (словарь 18 имён замкнут замером корпуса и держит константа слоя
    -- EVENT_NAME_DICTIONARY, а не CHECK — Q6, вариант A по прецеденту Q7 узла V50):
    -- незнакомое имя остаётся значением с состоянием `unknown_name` и виновником, а не
    -- отказом записи. `empty_value` и `absent` — границы, которых корпус не давал (во всех
    -- 772 файлах тег есть и непустой), но «тега нет» и «значение пустое» различимы
    -- состоянием, а не нулем и не молчанием (прецедент default_form_state V52)
    event TEXT,
    event_state TEXT NOT NULL,
    -- тег `Handler` — обработчик. Текст как в выгрузке плюс разложение на модуль и метод
    -- (Q2, решение оператора): вопрос «какие подписки вызывает этот общий модуль» читается
    -- индексом по handler_module без разбора текста. Внешнего ключа на common_modules нет:
    -- связь не один-к-одному (248 уникальных обработчиков при 311 подписках в BGU2, замер
    -- 2.3), а колонка uuid дублировала бы то, что даёт витрина v_current_common_modules.
    -- `unknown_form` — значение не вида `CommonModule.<Модуль>.<Метод>` (корпус таких не
    -- давал ни одного: 772 из 772 проходят обе проверки формы), `unresolved` — форма
    -- корректна, модуля в текущем состоянии конфигурации нет (замер: таких ноль)
    handler TEXT,
    handler_module TEXT,
    handler_method TEXT,
    handler_state TEXT NOT NULL,
    -- блок `<Source>` — круг целей срабатывания (вторая таблица пары). Пустой блок
    -- называется состоянием, а не отсутствием строк и не нулём без состояния (M4,
    -- прецедент content_state V52/V50); счётчик — вывод разбора круга, вручную не
    -- переписывается. Пустых блоков корпус не давал ни разу (замер 1.4)
    source_state TEXT NOT NULL,
    source_count INTEGER NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT event_subscriptions_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT event_subscriptions_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50, V52)
    CONSTRAINT event_subscriptions_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    -- имя события: состояние согласно значению. `known` — имя из замеренного словаря,
    -- `unknown_name` — значение вне словаря (оно остаётся записанным), `empty_value` —
    -- тег есть и значение пустое, `absent` — тега нет в файле
    CONSTRAINT event_subscriptions_event_state_known
        CHECK (event_state IN ('known', 'unknown_name', 'empty_value', 'absent')),
    CONSTRAINT event_subscriptions_event_state_matches_value
        CHECK ((event_state IN ('known', 'unknown_name') AND event IS NOT NULL
                AND event <> '')
               OR (event_state = 'empty_value' AND event = '')
               OR (event_state = 'absent' AND event IS NULL)),
    -- обработчик: словарь состояний и согласование состояния с текстом и разложением —
    -- «разрешилось» и «не разрешилось» различимы структурой строки, а не молчанием
    CONSTRAINT event_subscriptions_handler_state_known
        CHECK (handler_state IN ('exact', 'unresolved', 'unknown_form', 'empty_value',
                                 'absent')),
    CONSTRAINT event_subscriptions_handler_state_matches_value
        CHECK ((handler_state IN ('exact', 'unresolved')
                AND handler IS NOT NULL AND handler <> ''
                AND handler_module IS NOT NULL AND handler_module <> ''
                AND handler_method IS NOT NULL AND handler_method <> '')
               OR (handler_state = 'unknown_form'
                   AND handler IS NOT NULL AND handler <> ''
                   AND handler_module IS NULL AND handler_method IS NULL)
               OR (handler_state = 'empty_value' AND handler = ''
                   AND handler_module IS NULL AND handler_method IS NULL)
               OR (handler_state = 'absent' AND handler IS NULL
                   AND handler_module IS NULL AND handler_method IS NULL)),
    -- пустой блок называется состоянием, а не отсутствием строк; согласование состояния и
    -- счётчика замкнуто здесь, а число строк круга сверяет проверка узла П6
    CONSTRAINT event_subscriptions_source_state_known
        CHECK (source_state IN ('with_sources', 'empty_sources')),
    CONSTRAINT event_subscriptions_source_count_matches_state
        CHECK ((source_state = 'empty_sources' AND source_count = 0)
               OR (source_state = 'with_sources' AND source_count > 0)),
    CONSTRAINT event_subscriptions_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT event_subscriptions_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT event_subscriptions_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна, потому что 162
    -- uuid и 192 имён подписок стоят одновременно в BGU2 и BP3 (замер _v53_m1_probe.py)
    CONSTRAINT event_subscriptions_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- Строки блока `<Source>` файла регистрации — круг целей срабатывания подписки, то
-- есть ответ на вопрос «на какие объекты метаданных она действует» (замеры раздела 2.2
-- плана: 25 100 записей — BGU2 11 706, BP3 13 379, KomMag 10, MinCfg 5; пустых блоков
-- корпуса ноль, максимум в одном файле 789 — BP3). Элемент блока — тег `v8:Type` или
-- `v8:TypeSet` со значением-ссылкой; ни uuid, ни имени у элемента нет, идентичность
-- даёт только порядок в файле (`ordinal`) — тот же приём, что `filter_criterion_content`
-- (V52), `exchange_plan_content` (V51), `common_attribute_targets` (V50).
--
-- Таблица НЕ версионируется своей цепочкой (Q4, вариант A): ключ начинается с
-- `event_subscription_id`, а он указывает на конкретную строку `event_subscriptions`, то
-- есть на конкретную ревизию; ON DELETE CASCADE снимает строки вместе с ревизией вида.
-- Текущность выводится из витрины `v_current_event_subscriptions` связкой, а не поиском
-- максимума по своей цепи, поэтому колонок `revision_no`/`changed_*` здесь нет — и записи
-- в `CONFIGURATION_VERSIONED_TABLES` нет; таблица названа исключением
-- `CONFIGURATION_UNVERSIONED_TABLES` (src/external_table_writer.py).
-- `configuration_uuid` повторяет значение строки вида осознанно (тот же порядок, что
-- role_rights V49, common_attribute_targets V50, filter_criterion_content V52): запрос
-- «какие подписки настроены на этот вид метаданных» идёт по строкам источника, и без
-- колонки он требовал бы связки с таблицей вида и с её витриной на каждом шаге.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_subscription_sources (
    id BIGSERIAL PRIMARY KEY,
    event_subscription_id BIGINT NOT NULL
        REFERENCES event_subscriptions(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    subscription_object_uuid UUID NOT NULL,
    subscription_full_name TEXT NOT NULL,
    -- позиция записи в файле; порядок писатель не меняет (прецедент ordinal V50/V51/V52)
    ordinal INTEGER NOT NULL,
    -- измеренный тег элемента (`Type` 24 729, `TypeSet` 371): форма перечня является
    -- свойством выгрузки, а не обещанием разбора. Отличие от V52 названо: у элемента нет
    -- атрибута `xsi:type`, вместо него формой элемента является сам тег (замер 2.2)
    source_tag TEXT NOT NULL,
    -- значение элемента как в выгрузке (`cfg:CatalogObject.Организации` либо
    -- `cfg:CatalogObject`) — обещание сохранения текста, по нему сверяет меру проверка П6
    target_raw TEXT NOT NULL,
    -- класс цели — часть значения после `cfg:` до первой точки; измеренный словарь
    -- классов (30 записей) держит константа слоя SOURCE_CLASS_META_TYPES, а не CHECK
    -- (Q6, вариант A): незнакомый класс остаётся значением с состоянием `unknown_class`
    target_class TEXT NOT NULL,
    -- вид метаданных, к которому сводит класс разбора (`CatalogObject` → `Catalog`,
    -- `ConstantValueManager` → `Constant`); NULL — класс вне измеренного словаря
    target_meta_type TEXT,
    -- имя объекта цели (часть после первой точки) либо NULL для голой ссылки; голые
    -- ссылки — 265 записей корпуса, и это форма цели, а не потерянное имя (M5)
    target_object_name TEXT,
    -- имя цели в форме индекса состава (`Catalog.Организации`, для голой ссылки — `Catalog`,
    -- для неизвестного класса — измеренный класс целиком); колонка NOT NULL осознанно:
    -- пустой строкой состояние не читается
    target_full_name TEXT NOT NULL,
    -- форма значения: `named` (есть часть после точки), `bare` (только класс),
    -- `empty` (тег есть, значение пустое), `unknown_form` (значение не разбирается как
    -- `cfg:<Класс>[.<Имя>]`). Последних двух корпус не давал — это границы состояний
    target_form TEXT NOT NULL,
    -- ссылка на СТРОКУ индекса состава: внешнего ключа нет осознанно (прецедент V20.1 и
    -- записей V49/V50/V51/V52), потому что цель бывает неразрешённой, а разрешённая
    -- ссылка ведёт к строке, которую снимает перезагрузка индекса
    target_object_id TEXT,
    target_object_uuid UUID,
    -- состояние разрешения (Q3, вариант A): именованная цель — точным совпадением имени с
    -- записью индекса состава данной конфигурации (`exact` 24 835, `unresolved` — граница),
    -- голая — присутствием хоть одной записи этого вида метаданных в индексе
    -- (`type_present` 242 / `type_absent` 23 — называется прямо, M5); `unknown_class` —
    -- класс вне измеренного словаря (корпус таких не давал)
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    -- пустыми строками состояние не читается: обязательные части строки ненулевые,
    -- известная часть вида метаданных либо отсутствует (NULL), либо непустая. Отдельного
    -- требования к `target_full_name` здесь нет — для форм `empty` и `unknown_form`
    -- точечного имени цели не существует, его пустоту сторожит
    -- `event_subscription_sources_resolve_matches_reference`
    CONSTRAINT event_subscription_sources_names_not_blank
        CHECK (subscription_full_name <> '' AND source_tag <> ''
               AND (target_meta_type IS NULL OR target_meta_type <> '')),
    CONSTRAINT event_subscription_sources_ordinal_non_negative CHECK (ordinal >= 0),
    CONSTRAINT event_subscription_sources_source_tag_known
        CHECK (source_tag IN ('Type', 'TypeSet')),
    CONSTRAINT event_subscription_sources_target_form_known
        CHECK (target_form IN ('named', 'bare', 'empty', 'unknown_form')),
    CONSTRAINT event_subscription_sources_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'unresolved', 'type_present',
                                        'type_absent', 'unknown_class', 'empty_value',
                                        'unknown_form')),
    -- состояние разрешения согласно форме значения, ссылке и остатку пути (тот же контракт,
    -- что role_rights V49, common_attribute_targets V50, exchange_plan_content V51,
    -- filter_criterion_content V52): «цель найдена» и «цель не найдена» различимы
    -- структурой строки, а не молчанием. Точечное имя цели выводимо из её частей, и
    -- инвариант записан прямо: именно по этому имени идёт вопрос «какие подписки
    -- настроены на этот объект метаданных»
    CONSTRAINT event_subscription_sources_resolve_matches_reference
        CHECK (
              (target_resolve_state = 'exact' AND target_form = 'named'
               AND target_meta_type IS NOT NULL AND target_object_name IS NOT NULL
               AND target_full_name = target_meta_type || '.' || target_object_name
               AND target_object_id IS NOT NULL AND target_object_uuid IS NOT NULL
               AND target_unresolved_path IS NULL)
           OR (target_resolve_state = 'unresolved' AND target_form = 'named'
               AND target_meta_type IS NOT NULL AND target_object_name IS NOT NULL
               AND target_full_name = target_meta_type || '.' || target_object_name
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NOT NULL)
           OR (target_resolve_state IN ('type_present', 'type_absent')
               AND target_form = 'bare' AND target_meta_type IS NOT NULL
               AND target_object_name IS NULL
               AND target_full_name = target_meta_type
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NULL)
           OR (target_resolve_state = 'unknown_class' AND target_form IN ('named', 'bare')
               AND target_class <> '' AND target_meta_type IS NULL
               AND target_full_name = target_class
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NOT NULL)
           OR (target_resolve_state = 'empty_value' AND target_form = 'empty'
               AND target_raw = '' AND target_class = '' AND target_full_name = ''
               AND target_meta_type IS NULL AND target_object_name IS NULL
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NULL)
           OR (target_resolve_state = 'unknown_form' AND target_form = 'unknown_form'
               AND target_raw <> '' AND target_class = '' AND target_full_name = ''
               AND target_meta_type IS NULL AND target_object_name IS NULL
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path = target_raw)
        ),
    -- форма цели согласована с её разбором: именованная держит имя объекта, голая — не
    -- держит (замер 2.2: 24 835 именованных и 265 голых записей; пустых и неразбираемых
    -- значений корпус не давал — это границы состояний)
    CONSTRAINT event_subscription_sources_form_matches_target
        CHECK ((target_form = 'named' AND target_object_name IS NOT NULL
                AND target_object_name <> '')
               OR (target_form = 'bare' AND target_object_name IS NULL)
               OR (target_form IN ('empty', 'unknown_form')
                   AND target_object_name IS NULL)),
    -- ключ строки источника (Q4, вариант A): своей цепи ревизий нет, позиция в файле
    -- различает записи одной подписки — ни uuid, ни имени у элемента блока нет (замер 2.2)
    CONSTRAINT event_subscription_sources_subscription_ordinal_key
        UNIQUE (event_subscription_id, ordinal)
);

-- ---------------------------------------------------------------------------
-- Витрины текущего состояния узла V53. Предикат — тот же, что у витрин
-- V46/V48/V49/V50/V51/V52: строка относится к максимальной ревизии в пределах ключа своей
-- цепочки; признак коммита на круг не влияет (решение A1). Имена витрин задаёт не этот
-- файл: их отдаёт current_view() по реестру CONFIGURATION_VERSIONED_TABLES
-- (src/current_revision.py), а расхождение имени ловит tools/check_v19_revisions.py —
-- кроме `v_current_event_subscription_sources`: своей цепи ревизий у строк источника нет
-- (Q4 узла V53, вариант A), поэтому она строится связкой по event_subscription_id с
-- витриной строки вида (прецедент v_current_filter_criterion_content V52,
-- v_current_common_attribute_targets V50).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_event_subscriptions AS
SELECT es.id,
       es.configuration_uuid, es.object_uuid, es.object_name, es.full_name,
       es.synonym, es.comment, es.event, es.event_state,
       es.handler, es.handler_module, es.handler_method, es.handler_state,
       es.source_state, es.source_count,
       es.properties_state, es.unknown_property_names,
       es.source_path, es.created_at, es.revision_no, es.changed_at, es.changed_by,
       es.is_committed
FROM event_subscriptions es
WHERE NOT EXISTS (SELECT 1 FROM event_subscriptions h
                  WHERE h.configuration_uuid = es.configuration_uuid
                    AND h.object_name = es.object_name
                    AND h.revision_no > es.revision_no);

-- Витрина строк источника строит текущность связкой с v_current_event_subscriptions: своей
-- цепи ревизий у них нет, event_subscription_id указывает на конкретную ревизию строки вида.
CREATE OR REPLACE VIEW v_current_event_subscription_sources AS
SELECT ss.id,
       ss.event_subscription_id, ss.configuration_uuid, ss.subscription_object_uuid,
       ss.subscription_full_name, ss.ordinal, ss.source_tag, ss.target_raw,
       ss.target_class, ss.target_meta_type, ss.target_object_name, ss.target_full_name,
       ss.target_form, ss.target_object_id, ss.target_object_uuid,
       ss.target_resolve_state, ss.target_unresolved_path, ss.created_at
FROM event_subscription_sources ss
JOIN v_current_event_subscriptions es ON es.id = ss.event_subscription_id;

-- ---------------------------------------------------------------------------
-- Индексы узла V53 (подписка на событие, позиция 2.8). Отдельного индекса по
-- configuration_uuid у event_subscriptions и event_subscription_sources не заводим: у
-- строки вида его обслуживает уникальный индекс цепочки с ведущей колонкой
-- configuration_uuid — им же пользуются предикат витрины и чистка стадии по конфигурации
-- (тот же порядок, что V46/V48/V49/V50/V51/V52); у строк источника ведущая колонка
-- уникального индекса — event_subscription_id, то есть снятие круга и связка с витриной
-- идут по нему.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_object_uuid_revision
    ON event_subscriptions(object_uuid, revision_no);
-- Карточка «какие подписки вызывает этот общий модуль» идёт по имени модуля (Q2, вариант A
-- оператора): разложение даёт точное значение, а не разбор текста; частичный — потому что
-- при состояниях `empty_value` и `absent` колонки нет, а индекс по NULL-значениям смысла
-- не имеет (тот же приём, что idx_config_objects_uuid узла V33).
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_handler_module
    ON event_subscriptions(handler_module) WHERE handler_module IS NOT NULL;
-- Строки источника: запрос карточки «на какие объекты метаданных действует эта подписка»
-- и обратный «какие подписки настроены на этот объект» идут по точечному имени цели; для
-- разрешённых ссылок — по uuid цели (те же два индекса, что idx_filter_criterion_content_*
-- узла V52). Третий индекс — по виду метаданных: голые ссылки (265 записей корпуса) цели
-- не называют, и вопрос «какие подписки настроены на вид целиком» без него не читается.
-- Отдельного индекса по ordinal нет: он ведомая колонка уникального индекса.
CREATE INDEX IF NOT EXISTS idx_event_subscription_sources_target_full_name
    ON event_subscription_sources(target_full_name);
CREATE INDEX IF NOT EXISTS idx_event_subscription_sources_target_object_uuid
    ON event_subscription_sources(target_object_uuid) WHERE target_object_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_subscription_sources_target_meta_type
    ON event_subscription_sources(target_meta_type) WHERE target_meta_type IS NOT NULL;

SELECT 'Подписки на события (узел V53) добавлены в схему!' AS status;
