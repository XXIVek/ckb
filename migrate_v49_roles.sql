-- migrate_v49_roles.sql
-- ============================================================================
-- Узел V49, шаг П1: таблицы содержимого ролей (позиция 2.4 нормативного списка
--       «Структура конфигурации.txt», группа F модели A–H) с витринами текущего
--       состояния.
-- Норматив: docs/CONFIGURATION_ROLES_PLAN.md
--           (раздел 2 — замеры П0, раздел 3 — решения Q0…Q10, раздел 4 — модель схемы).
-- Дата: 2026-10-29.
--
-- Миграция аддитивна: ни одна колонка не снимается, ни одна строка не удаляется,
-- повторный прогон ничего не меняет. Итоговое состояние совпадает с чистой
-- установкой: шаг 2 — create_1c_configurations_db.sql (зеркало этого файла).
-- Порождённые шагами 1 и 1b файлы (src/ddl_external_report.sql,
-- src/ddl_enrichment.sql) этим узлом не меняются: таблицы принадлежат слою
-- конфигурации (шаг 2), а не слою внешнего объекта, поэтому DDL-генератор
-- src/generate_ddl.py не правится — правка схемы идёт парой «миграция + зеркало
-- шага 2». Сверка пары — python _cmp_ddl.py.
--
-- 1. Четыре таблицы вида, общего контейнера нет (Q1, вариант A, решение оператора
--    от 29.10.2026): `roles` (роль и строка её содержимого), `role_rights` (строка
--    права), `role_restriction_templates` (текст ограничения шаблона с дедупликацией),
--    `role_sources` (дескриптор файла Ext/Rights.xml). Формулировка модели группы F
--    про configuration_object_content для ролей отпадает: правые строки — предмет
--    прямого запроса («какие роли дают Edit на Catalog.Товары»), в jsonb они остались
--    бы неиндексируемыми.
--
-- 2. Граница «таблица ≠ колонка заголовка»: таблица `roles` — это СОДЕРЖИМОЕ вида, а
--    колонка `configurations.roles` (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН ролей в строке
--    заголовка. Совпадение имён читается как риск, а не как связь: внешнего ключа нет
--    осознанно (прецедент V20.1), отношение читается именем, равенство множеств
--    сторожит постоянная проверка узла tools/check_v49_roles.py, а не схема. Тот же
--    прецедент, что `session_parameters` против одноимённой колонки (узел V48).
--
-- 3. Ключи цепочки состояния (Q2, вариант A — решение оператора от 29.10.2026):
--    у `roles`, `role_restriction_templates`, `role_sources` — цепочка по
--    (configuration_uuid, <ключ объекта>, revision_no); у `role_rights` своей цепи НЕТ:
--    ключ (role_id, target_full_name, right_name), а role_id указывает на конкретную
--    ревизию строки роли, поэтому текущность права следует из текущности роли.
--    Замер, который это разрешает: повторов цели внутри файла — 0, повторов имени
--    права у одной цели — 0, максимум прав на цель — 27.
--    Граница configuration_uuid обязательна при любой форме ключа (тот же порядок,
--    что у V47/V48), поэтому `role_rights.configuration_uuid` держится своей колонкой,
--    хотя выводима из роли: на ней работает чистка узла и вопрос по конфигурации.
--
-- 4. Разрешение цели права (Q3, вариант A). Цель разрешается индексом состава
--    `configuration_objects`: 47 650 из 52 722 целей разрешаются именем целиком,
--    5 072 — только префиксом (из них 5 052 — StandardAttribute), неразрешимых — 0
--    (замер 2.6 плана). Состояние `target_resolve_state` отличает «разрешили» от
--    «разрешили частично» — тот же приём, что `unknown_form` узла V48 и
--    `content_unresolved` узла V46; остаток пути называется колонкой
--    `target_unresolved_path`, а не теряется.
--
-- 5. Имя права — текст, а не справочник (Q4, вариант A). Словарь 69 имён закрыт по
--    корпусу, XSD вида `Role` в слое схемы отсутствует, поэтому внешний ключ означал бы
--    отказ записать право, которого мы не ждали (молчаливую потерю круга). Неизвестное
--    имя называется состоянием `right_name_state = 'unknown_name'` (прецедент
--    `unknown_form` V48); норматив словаря — карточка слоя, а не CHECK схемы.
--    Значение права выражается состоянием по значению ВЫГРУЗКИ (`granted` / `denied`),
--    а не смыслом «роль может»: в KomMag все 2 899 прав имеют значение false, в MinCfg
--    361 из 362 (позиция O1), и утверждать «роль ничего не даёт» без проверки по
--    документации платформы нельзя.
--
-- 6. Ограничения (RLS) — Q5, вариант A1 (решение оператора от 29.10.2026).
--    Замеры: шаблоны — 1 386 вхождений на 107 389 085 символов при 9 различных
--    текстах (776 550 символов, дедуп ×138); встроенных условий 8 915 на 4 010 051
--    символ при 3 686 различных (дедуп дал бы экономию 2,3 МБ — он неводится).
--    Поэтому текст шаблона хранится ОДИН раз на пару (имя, отпечаток) в границах
--    конфигурации, а встроенное условие права остаётся колонкой строки права.
--    ЯВНОЙ ссылки права на шаблон в выгрузке нет — словарь элементов замкнут и
--    называет состав `<right>`: `name`, `value`, `restrictionByCondition`
--    (_v49_p0_element_probe.py). Детей у самого `<restrictionByCondition>` прогон
--    `_v49_p2_restriction_probe.py` даёт два: `condition` (8 915) и `field` (3) — П0 их
--    не измерял, потому что останавливался на детях `<right>`; `<field>` хранится
--    колонкой `restriction_field_name`, а один `<condition/>` пустой — это наблюдение
--    разбора, а не строка с условием. Связь — вывод разбора: вызов пишется `#Имя(`,
--    платформенные функции пишутся без `#`, поэтому 8 887 из 8 914 условий с текстом
--    (99,7 %) вызывают шаблон своей роли, висячих вызовов — 0, условий без вызова — 27
--    (_v49_p0_rls_link_probe.py, пересчёт П2). Имена шаблонов несут сигнатуру параметров
--    (`ДляОбъекта(ПолеОбъекта)`), вызов пишется `#ДляОбъекта("")`: сопоставление
--    возможно только по сигнатуре до `(`, она и хранится колонкой `name_signature`.
--    Декларация «какие роли объявляют шаблон» — факт выгрузки и хранится перечнем
--    `holder_role_names` (прецедент перечней заголовка узла V43: скаляры текстом,
--    перечни массивом).
--
-- 7. Исходный XML `Rights.xml` не хранится (Q9, вариант A — решение оператора от
--    29.10.2026). Замер веса (_v49_p0_weight_probe.py): корпус 211 544 827 байт, после
--    сжатия 9 242 576 байт (коэффициент 22,89), нормализуемых данных 8 696 706
--    символов. Хранение `ext` стоило бы ~9 МБ в сжатом виде и стало бы ВТОРОЙ копией
--    содержимого, устаревающей при правке строк. Граница узла: побайтовое
--    воспроизведение `Rights.xml` не обещается (отступы и вид сущностей из строк не
--    восстанавливаются), смысловая сборка — из строк по `target_ordinal` и
--    `right_ordinal`. Словарь атрибутов корня измерен и является нормативом слоя, а не
--    колонкой: `xsi:type="Rights"` — константа, `version="2.20"` — одно значение на все
--    1 202 файла.
--
-- 8. Индекс по configuration_uuid отдельно не заводится там, где его обслуживает
--    уникальный индекс цепочки с той же ведущей колонкой (порядок V44/V46/V48). Для
--    `role_rights` ведущая колонка уникального индекса — `role_id`, поэтому индекс по
--    configuration_uuid заводится: на нём работает чистка узла и вопросы по конфигу.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Строка роли и её содержимого
-- ---------------------------------------------------------------------------
-- `object_uuid` — NOT NULL осознанно: uuid держится АТРИБУТОМ элемента `<Role>` в
-- файле метаданных (1 202 из 1 202 файлов, пустых — 0) и той же строкой индекса
-- состава `Role.<Имя>` (_v49_p0_rolefile_probe.py, 29.10.2026). `<Name>` совпадает с
-- именем файла во всех 1 202 случаях, `<ChildObjects>` — 0 файлов.
-- `synonym` — jsonb_nullable: «свойства в выгрузке нет» и «свойство есть, но пустое»
-- — разные состояния (замер: 1 201 файл с `<v8:item>`, 1 файл с `<Synonym/>`).
-- `comment` — текст или NULL (замер: 41 файл с текстом, 1 161 файл с `<Comment/>`).
-- Три флага — свойства СОДЕРЖИМОГО прав (по одному на файл, 1 202/1 202), а не
-- отдельного права: место им здесь, а не в строке права (замер 2.5 плана).
-- Счётчики — вывод разбора всего круга роли; они нужны потому, что пустое содержимое
-- (11 файлов без `<object>`: BGU2 2, BP3 9) обязано называться состоянием
-- `empty_content`, а не отсутствием строки (Q7).
CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    comment TEXT,
    synonym JSONB,
    set_for_new_objects BOOLEAN,
    set_for_attributes_by_default BOOLEAN,
    independent_rights_of_child_objects BOOLEAN,
    content_state TEXT NOT NULL,
    source_path TEXT NOT NULL,
    targets_count INTEGER NOT NULL DEFAULT 0,
    rights_count INTEGER NOT NULL DEFAULT 0,
    conditions_count INTEGER NOT NULL DEFAULT 0,
    templates_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT roles_content_state_known
        CHECK (content_state IN ('with_rights', 'empty_content',
                                 'indexed_no_file', 'file_not_in_index')),
    -- счётчики согласованы с состоянием содержимого: «прав нет» не соседствует с
    -- состоянием with_rights, «роль без прав» не даёт ненулевых счётчиков
    CONSTRAINT roles_counters_match_content_state
        CHECK (targets_count >= 0 AND rights_count >= 0 AND conditions_count >= 0
               AND templates_count >= 0
               AND (rights_count > 0 OR content_state <> 'with_rights')
               AND (rights_count = 0
                    OR content_state NOT IN ('empty_content', 'indexed_no_file',
                                             'file_not_in_index'))),
    CONSTRAINT roles_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT roles_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT roles_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT roles_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- 2. Строка права
-- ---------------------------------------------------------------------------
-- Одна строка = право `right_name` цели `target_full_name` в границах одной ревизии
-- одной роли. Цепочки ревизий у таблицы СВОЕЙ НЕТ (Q2, вариант A): ключ начинается с
-- `role_id`, а `role_id` указывает на конкретную строку `roles`, то есть на конкретную
-- ревизию; текущность права следует из текущности строки роли. Поэтому колонок
-- `revision_no`/`changed_*` здесь нет — и нет записи в
-- CONFIGURATION_VERSIONED_TABLES: запись в словаре означала бы цепь, которой у
-- таблицы нет. Витрина `v_current_role_rights` при этом есть (требование п.2
-- «у каждого блока своя витрина текущего состояния») — она читается связкой с
-- `v_current_roles`, а не поиском максимума по своей цепи.
-- `target_object_id`/`target_object_uuid` — ссылка на строку индекса состава
-- `configuration_objects` (не на таблицу содержимого: содержимое цели — другие узлы).
-- Внешнего ключа нет: цель может быть не разрешена (prefix_only/unresolved), а
-- разрешённая ссылка ведёт к строке, которую снимает перезагрузка индекса состава —
-- битая ссылка хуже состояния.
CREATE TABLE IF NOT EXISTS role_rights (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    target_kind TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    right_name TEXT NOT NULL,
    right_name_state TEXT NOT NULL,
    right_value_state TEXT NOT NULL,
    -- `<field>` внутри `<restrictionByCondition>` — имя поля объекта, к которому
    -- относится право (замер `_v49_p2_restriction_probe.py`: 3 вхождения корпуса,
    -- например `InformationRegister.ВерсииОбъектов` / `Read` / `ВерсияОбъекта`).
    -- Текст, а не ссылка: индекс состава поля не моделирует (замер 2.5).
    restriction_field_name TEXT,
    condition_text TEXT,
    condition_state TEXT NOT NULL,
    restriction_template_names TEXT[],
    target_ordinal INTEGER NOT NULL,
    right_ordinal INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT role_rights_names_not_blank
        CHECK (target_full_name <> '' AND right_name <> '' AND target_kind <> ''),
    -- имя поля из `<field>` пустым не бывает: пустой элемент — состояние разбора
    -- (наблюдение), а не строка с пустым именем
    CONSTRAINT role_rights_field_name_not_blank
        CHECK (restriction_field_name IS NULL OR restriction_field_name <> ''),
    CONSTRAINT role_rights_target_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    CONSTRAINT role_rights_right_name_state_known
        CHECK (right_name_state IN ('known', 'unknown_name')),
    CONSTRAINT role_rights_right_value_state_known
        CHECK (right_value_state IN ('granted', 'denied', 'unknown_form')),
    CONSTRAINT role_rights_condition_state_known
        CHECK (condition_state IN ('no_condition', 'with_call', 'no_call')),
    -- состояние условия и его содержимое не противоречат друг другу: «без условия» не
    -- держит текста, «с вызовом» держит хотя бы одно имя шаблона
    CONSTRAINT role_rights_condition_matches_state
        CHECK ((condition_state = 'no_condition' AND condition_text IS NULL
                AND restriction_template_names IS NULL)
               OR (condition_state = 'with_call' AND condition_text IS NOT NULL
                   AND COALESCE(array_length(restriction_template_names, 1), 0) > 0)
               OR (condition_state = 'no_call' AND condition_text IS NOT NULL
                   AND COALESCE(array_length(restriction_template_names, 1), 0) = 0)),
    -- состояние разрешения цели согласовано со ссылкой и с остатком пути: остаток
    -- называется, а не теряется (прецедент content_unresolved узла V46)
    CONSTRAINT role_rights_target_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only'
                   AND target_object_id IS NOT NULL
                   AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved'
                   AND target_object_id IS NULL
                   AND target_unresolved_path IS NOT NULL)),
    CONSTRAINT role_rights_ordinals_non_negative
        CHECK (target_ordinal >= 0 AND right_ordinal >= 0),
    -- Q2, вариант A: повтор цели или повтор имени права у цели — ошибка разбора, а не
    -- вторая строка (замеров таких повторов — 0)
    CONSTRAINT role_rights_role_target_right_key
        UNIQUE (role_id, target_full_name, right_name)
);

-- ---------------------------------------------------------------------------
-- 3. Текст ограничения шаблона (Q5, вариант A1: дедуп по (имя, отпечаток))
-- ---------------------------------------------------------------------------
-- Строка = ОДИН текст ограничения в границах конфигурации. Дедупликация выведена из
-- замера: 1 386 вхождений дают 107 389 085 символов, различных текстов — 9
-- (776 550 символов): повтор одного и того же текста в одной роли доходит до 33 раз,
-- а один и тот же текст объявляют до 664 ролей. Хранить его по числу вхождений —
-- значит раздуть слой в 138 раз без нового знания.
-- `name_signature` — часть имени до `(`: сопоставление вызова `#ДляОбъекта("")` с
-- объявлением `ДляОбъекта(ПолеОбъекта)` возможно только по сигнатуре (замер 2.9).
-- `holder_role_names` — перечень ролей, объявляющих этот текст: факт выгрузки, а не
-- вывод (прецедент перечней заголовка V43 — скаляры текстом, перечни массивом).
-- Явного ключа «право → шаблон» в схеме нет, потому его нет в выгрузке: связь выводится
-- из текста условия и хранится колонкой `role_rights.restriction_template_names`.
CREATE TABLE IF NOT EXISTS role_restriction_templates (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    name TEXT NOT NULL,
    name_signature TEXT NOT NULL,
    digest TEXT NOT NULL,
    condition_text TEXT NOT NULL,
    condition_length INTEGER NOT NULL,
    holder_role_names TEXT[],
    holders_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT role_restriction_templates_names_not_blank
        CHECK (name <> '' AND name_signature <> ''),
    -- сигнатура — начало полного имени: иначе строка описывала бы шаблон, которого
    -- в выгрузке нет
    CONSTRAINT role_restriction_templates_signature_is_name_prefix
        CHECK (left(name, char_length(name_signature)) = name_signature),
    -- отпечаток — sha1 в hex: он ключ дедупликации, пустой означал бы «текст неизвестен»
    CONSTRAINT role_restriction_templates_digest_shape
        CHECK (digest ~ '^[0-9a-f]{40}$'),
    CONSTRAINT role_restriction_templates_condition_not_blank
        CHECK (condition_text <> '' AND condition_length > 0),
    -- длина текста совпадает с его фактической длиной: счётчик не переписывается вручную
    CONSTRAINT role_restriction_templates_length_matches_text
        CHECK (condition_length = char_length(condition_text)),
    -- перечень носителей и его длина не расходятся; роль без носителя описывает шаблон,
    -- которого ни одна роль не объявляет, — этого в выгрузке не бывает
    CONSTRAINT role_restriction_templates_holders_match_count
        CHECK (holders_count >= 1
               AND COALESCE(array_length(holder_role_names, 1), 0) = holders_count),
    CONSTRAINT role_restriction_templates_revision_no_positive
        CHECK (revision_no >= 1),
    CONSTRAINT role_restriction_templates_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT role_restriction_templates_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- пара (имя, отпечаток) различает случаи «тот же текст под другим именем» и
    -- «то же имя с другим текстом» — оба наблюдаются (позиция O3), и ни один из них
    -- нельзя терять. Имя ограничения сокращено до `config`: полное
    -- `configuration_...` даёт 64 знака, а PostgreSQL обрезает идентификатор до 63
    -- молча — ссылка на обрезанное имя в проверке узла была бы хуже короткого имени
    CONSTRAINT role_restriction_templates_config_name_digest_revision_key
        UNIQUE (configuration_uuid, name, digest, revision_no)
);

-- ---------------------------------------------------------------------------
-- 4. Дескриптор файла содержимого прав (текста файла узел не читает — Q9)
-- ---------------------------------------------------------------------------
-- Каждая строка подтверждается записью индекса состава `Role.<Имя>.Rights`
-- (child_type='Rights', uuid у неё отсутствует, object_id = '<uuid роли>.0'), а не
-- повторным разбором `ConfigDumpInfo.xml` (тот же порядок, что `common_module_sources`
-- узла V46 и `session_parameters` узла V48). Состояния различают файл и запись
-- индекса; в четырёх замеренных выгрузках круг замкнут (1 202/1 202). Особого случая BP3
-- здесь нет — замер П2 (29.10.2026) даёт в BP3 каталог `Roles/` из 682 подкаталогов и 682
-- файла прав, то есть прежняя формулировка «каталога Roles/ нет» была неверной и снята.
-- Состояния `indexed_no_file` и `file_not_in_index` корпусом не даны, но заглушками не
-- являются: круг по каталогу и круг по индексу — разные круга (Q6), и достигаются они
-- синтетическими фикстурами шага П2 (`_v49_p2_offline_probe.py`), а не нулями корпуса.
CREATE TABLE IF NOT EXISTS role_sources (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    object_uuid UUID NOT NULL,
    source_path TEXT NOT NULL,
    file_size BIGINT,
    declaration_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT role_sources_names_not_blank
        CHECK (object_name <> '' AND source_path <> ''),
    CONSTRAINT role_sources_declaration_state_known
        CHECK (declaration_state IN ('file_and_index', 'indexed_no_file',
                                     'file_not_in_index')),
    -- размер и состояние согласованы: файла нет — размера нет; ожидаемого файла нет —
    -- это состояние, а не нулевой размер
    CONSTRAINT role_sources_size_matches_state
        CHECK ((declaration_state = 'file_and_index' AND file_size IS NOT NULL)
               OR (declaration_state <> 'file_and_index' AND file_size IS NULL)),
    CONSTRAINT role_sources_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT role_sources_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT role_sources_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT role_sources_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);


-- ---------------------------------------------------------------------------
-- 5. Индексы
-- ---------------------------------------------------------------------------
-- Отдельный индекс по configuration_uuid не заводится в `roles`,
-- `role_restriction_templates`, `role_sources`: его обслуживает уникальный индекс
-- цепочки с той же ведущей колонкой (порядок V44/V46/V48).
-- Индекс по configuration_uuid в `role_rights` заводится: ведущая колонка её
-- уникального индекса — `role_id`, а на configuration_uuid работает чистка узла.
-- Индексы по цели и имени права — ответ на карточку «какие роли дают Edit на
-- Catalog.Товары» и «какие права даёт роль» без сканирования 140 115 строк.
-- Частичный индекс по target_object_uuid — только разрешённые ссылки (5 072 из 52 722
-- их не имеют).
CREATE INDEX IF NOT EXISTS idx_roles_object_uuid_revision
    ON roles(object_uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_role_rights_configuration_uuid
    ON role_rights(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_role_rights_target_full_name
    ON role_rights(target_full_name);
CREATE INDEX IF NOT EXISTS idx_role_rights_right_name
    ON role_rights(right_name);
CREATE INDEX IF NOT EXISTS idx_role_rights_target_object_uuid
    ON role_rights(target_object_uuid) WHERE target_object_uuid IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 5.1 Дополнение, найденное разбором П2: поле права `<field>`
-- ---------------------------------------------------------------------------
-- П0 (`_v49_p0_element_probe.py`) перечислял детей `<right>` и на них останавливался;
-- детей `<restrictionByCondition>` он не измерял. Прогон `_v49_p2_restriction_probe.py`
-- даёт у этого элемента два имени: `condition` (8 915) и `field` (3). Текст `<field>` —
-- имя поля объекта, к которому относится право, то есть знание выгрузки: отбросить его как
-- «неизвестный элемент» означало бы его потерять. Колонка добавлена и в `CREATE TABLE`
-- выше (новая база), и этим идемпотентным ALTER — таблица уже создана прежним прогоном
-- файла (приём migrate_v42_configuration_header_fields.sql, migrate_v43).
DO $$
BEGIN
    IF to_regclass('public.role_rights') IS NULL THEN
        RETURN;                       -- пустой базы нет: CREATE держит колонку сам
    END IF;
    EXECUTE 'ALTER TABLE public.role_rights '
            || 'ADD COLUMN IF NOT EXISTS restriction_field_name TEXT';
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'role_rights_field_name_not_blank') THEN
        ALTER TABLE public.role_rights
            ADD CONSTRAINT role_rights_field_name_not_blank
            CHECK (restriction_field_name IS NULL OR restriction_field_name <> '');
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 6. Витрины текущего состояния
-- ---------------------------------------------------------------------------
-- Только строки максимальной ревизии; предикат совпадает с ключом цепи каждой таблицы.
-- `v_current_role_rights` — витрина через связку с `v_current_roles`: своей цепи у
-- прав нет (раздел 2), их текущность выводится из строки роли.
CREATE OR REPLACE VIEW v_current_roles AS
SELECT r.id,
       r.configuration_uuid, r.object_uuid, r.object_name, r.full_name,
       r.comment, r.synonym, r.set_for_new_objects,
       r.set_for_attributes_by_default, r.independent_rights_of_child_objects,
       r.content_state, r.source_path, r.targets_count, r.rights_count,
       r.conditions_count, r.templates_count, r.created_at,
       r.revision_no, r.changed_at, r.changed_by, r.is_committed
FROM roles r
WHERE NOT EXISTS (SELECT 1 FROM roles h
                  WHERE h.configuration_uuid = r.configuration_uuid
                    AND h.object_name = r.object_name
                    AND h.revision_no > r.revision_no);

-- Витрина прав строит текущность связкой с `v_current_roles`: своей цепи ревизий у
-- прав нет (раздел 3 шапки), `role_id` указывает на конкретную ревизию строки роли.
-- `DROP VIEW` перед пересозданием нужно для повторного прогона по уже созданной витрине:
-- `CREATE OR REPLACE VIEW` не меняет имён и порядка колонок, а колонка
-- `restriction_field_name` (дополнение П2, раздел 5.1) вставлена в середину списка —
-- на живой базе прогон падает с «cannot change name of view column». Приём
-- migrate_v46_bsl_modules_uuid.sql (та же правка витрины `v_current_bsl_modules`).
DROP VIEW IF EXISTS v_current_role_rights;
CREATE OR REPLACE VIEW v_current_role_rights AS
SELECT rr.id,
       rr.role_id, rr.configuration_uuid, rr.target_kind, rr.target_full_name,
       rr.target_object_id, rr.target_object_uuid, rr.target_resolve_state,
       rr.target_unresolved_path, rr.right_name, rr.right_name_state,
       rr.right_value_state, rr.restriction_field_name, rr.condition_text,
       rr.condition_state, rr.restriction_template_names, rr.target_ordinal,
       rr.right_ordinal, rr.created_at
FROM role_rights rr
JOIN v_current_roles rc ON rc.id = rr.role_id;

CREATE OR REPLACE VIEW v_current_role_restriction_templates AS
SELECT t.id,
       t.configuration_uuid, t.name, t.name_signature, t.digest,
       t.condition_text, t.condition_length, t.holder_role_names,
       t.holders_count, t.created_at, t.revision_no, t.changed_at,
       t.changed_by, t.is_committed
FROM role_restriction_templates t
WHERE NOT EXISTS (SELECT 1 FROM role_restriction_templates h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.name = t.name
                    AND h.digest = t.digest
                    AND h.revision_no > t.revision_no);

CREATE OR REPLACE VIEW v_current_role_sources AS
SELECT s.id,
       s.configuration_uuid, s.object_name, s.object_uuid, s.source_path,
       s.file_size, s.declaration_state, s.created_at, s.revision_no,
       s.changed_at, s.changed_by, s.is_committed
FROM role_sources s
WHERE NOT EXISTS (SELECT 1 FROM role_sources h
                  WHERE h.configuration_uuid = s.configuration_uuid
                    AND h.object_name = s.object_name
                    AND h.revision_no > s.revision_no);

-- ---------------------------------------------------------------------------
-- 7. Проверка применения
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    t_count INTEGER;
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO t_count FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN ('roles', 'role_rights', 'role_restriction_templates',
                         'role_sources');
    IF t_count <> 4 THEN
        RAISE EXCEPTION 'V49: создано таблиц: %, ожидалось 4', t_count;
    END IF;
    SELECT COUNT(*) INTO v_count FROM information_schema.views
    WHERE table_schema = 'public'
      AND table_name IN ('v_current_roles', 'v_current_role_rights',
                        'v_current_role_restriction_templates', 'v_current_role_sources');
    IF v_count <> 4 THEN
        RAISE EXCEPTION 'V49: создано витрин: %, ожидалось 4', v_count;
    END IF;
END $$;

SELECT 'roles' AS table_name, COUNT(*) AS row_count FROM roles
UNION ALL SELECT 'role_rights', COUNT(*) FROM role_rights
UNION ALL SELECT 'role_restriction_templates', COUNT(*) FROM role_restriction_templates
UNION ALL SELECT 'role_sources', COUNT(*) FROM role_sources
UNION ALL SELECT 'v_current_roles', COUNT(*) FROM v_current_roles
UNION ALL SELECT 'v_current_role_rights', COUNT(*) FROM v_current_role_rights
UNION ALL SELECT 'v_current_role_restriction_templates', COUNT(*) FROM v_current_role_restriction_templates
UNION ALL SELECT 'v_current_role_sources', COUNT(*) FROM v_current_role_sources
ORDER BY table_name;
