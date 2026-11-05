-- migrate_v55_bots.sql
-- ============================================================================
-- Узел V55, шаг П1: бот (позиция 2.10 нормативного списка «Структура
--       конфигурации.txt») — ОДНА таблица вида: свойства файла регистрации,
--       ссылка `Picture` и дескрипторы модуля вида.
-- Норматив: docs/CONFIGURATION_BOTS_PLAN.md (раздел 1 — круг тремя ногами и его
--           разрежённость по четырём выгрузкам, раздел 2 — словарь пяти тегов и
--           форма ссылки `Picture`, раздел 5 — M1…M7, раздел 6 — решение Q1
--           (вариант A оператора) и предложения Q2…Q7, раздел 7 — план П1…П9).
-- Дата: 2026-11-04.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон
-- ничего не меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла, перенос
--             делает _v55_p1_mirror.py, а не переписывание от руки).
-- Сверка пары — python _cmp_ddl.py.
--
-- Отличие от V48…V54 названо прямо, и оно определяет весь узел: **вид существует
-- ровно в одной выгрузке эталонного набора**. `Bots/` есть только у `MinCfg`
-- (2 файла регистрации и 2 модуля `Ext/Module.bsl`); у `KomMag`, `BGU2`, `BP3`
-- каталога вида нет ни файлом, ни строкой индекса состава, а перечень заголовка
-- `configurations.bots` у этих трёх строк — NULL (замер `_v55_p0_probe.py`,
-- `_v55_m1_probe.py`, раздел 1.1 плана). Из этого следуют две границы, которые
-- нельзя сгладить:
--   1. словарь свойств корпуса **не замыкает** (5 тегов по 2 файлам; XSD вида в
--      `xsd-schemas/` — 35 файлов — и `xsd-docs` нет, поиск по маске `bot` не дал
--      ни одного файла). Поэтому незнакомый тег остаётся значением с состоянием
--      `unknown_tag` и именем виновника в `unknown_property_names`, а не отказом
--      записи (Q1, решение оператора — вариант A; механизм тот же, что у
--      `event_subscriptions` V53 и `scheduled_jobs` V54);
--   2. замер коллизий uuid и имён между выгрузками даёт ноль **потому, что
--      сравнивать нечего** (2 строки в одной выгрузке), а не потому, что коллизий
--      нет. Границу ключа это не меняет: перечень заголовка хранит детей массивом
--      имён, и ключ держит `configuration_uuid` по прецедентам V48…V54 (M1).
-- ============================================================================

-- Узел V55 (04.11.2026, позиция 2.10 нормативного списка «Структура конфигурации.txt»):
-- бот — свойства файла регистрации `Bots/<Имя>.xml`, ссылка `Picture` и дескрипторы
-- модуля вида. Перечень заголовка — пункт 10 файла оператора «Дочерние свойства для
-- конфигурации.txt» (`10.Bot /Bots - Боты`, орфография источника сохранена).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `bots` — СОДЕРЖИМОЕ вида, а колонка
-- configurations.bots (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет
-- осознанно (прецедент V20.1), равенство множеств сторожит tools/check_v55_bots.py.
--
-- Что создаётся и почему ровно так (каждая граница — замер, ссылка в комментариях
-- блоков):
--   1. `bots` — свойства вида по 5 тегам `Properties` (в обоих файлах круга есть все
--      пять: Name 2/2, Synonym 2/2, Comment 2/2, Predefined 2/2, Picture 2/2; пустых
--      `Comment` и отсутствующих `Synonym` корпус не давал ни разу), состояние разбора
--      свойств, ссылка `Picture` с различением класса цели (Q3), дескрипторы модуля
--      вида без текстов (Q4: тексты пишет узел V47, мера M5), цепь ревизий и ключ
--      `UNIQUE (configuration_uuid, object_name, revision_no)`;
--   2. второй таблицы нет (M3): детей общей раскладки у вида, кроме модуля, ноль —
--      блок `ChildObjects` пуст в обоих файлах, каталогов `Forms/`, `Templates/`,
--      `Commands/` нет ни в одной выгрузке (замер 1.1); содержимого со своей схемой
--      тоже нет: файл `Ext/Module.bsl` — модуль группы B, а не содержимое вида.
--      Колонок `children_state`, `form_names`, `command_uuids`, `template_names` здесь
--      нет осознанно: состояние «детей нет» описывало бы то, чего вид не имеет, а
--      ровность круга сторожит проверка П6 обходом подкаталогов (она обязана дать
--      ноль) — тот же порядок, что V53;
--   3. витрина `v_current_bots` — предикат по ключу цепи; её имя задаёт реестр
--      `CONFIGURATION_VERSIONED_TABLES` (src/current_revision.py), а расхождение имени
--      ловит `tools/check_v19_revisions.py`;
--   4. индексы: `(object_uuid, revision_no)` — карточка объекта по uuid; частичные по
--      `picture_full_name` и `picture_object_uuid` — обратный вопрос «какие боты
--      ссылаются на эту общую картинку». Отдельного индекса по `configuration_uuid`
--      нет: его обслуживает уникальный индекс цепочки с ведущей колонкой
--      `configuration_uuid` (тот же порядок, что V46, V48…V54).
--
-- Чего узел НЕ делает (границы раздела 8 плана): не трогает тексты модулей вида —
-- `bsl_modules` пишет узел V47 (2 строки MinCfg уже лежат, замер `_v55_m1_probe.py`);
-- не утверждает существование цели `Picture` в базе (слой `CommonPictures`, позиция
-- 2.19, не загружен; `StdPicture.*` индексом не разрешается осознанно); не заполняет
-- перечень `configurations.bots` (его пишет стадия S2 узла V43); не загружает
-- определённые типы (`DefinedTypes` в выгрузке вида нет).

-- ---------------------------------------------------------------------------
-- Строка бота. Свойства — по тегам файла регистрации в их порядке (словарь
-- BOT_PROPERTIES слоя разбора; замер `_v55_p0_probe.py`, раздел 2 плана: ровно 5
-- тегов `Properties` — Name, Synonym, Comment, Predefined, Picture — в обоих файлах
-- круга; верхний уровень файла кроме `Properties` ничего не несёт, блок
-- `ChildObjects` пуст). Тег `Name` ключуется колонкой object_name; тег `Picture`
-- разложен ниже; тег `Module` — дескрипторы ниже, тексты пишет V47. Словарь тегов
-- корпусом НЕ замкнут (2 файла, XSD нет), поэтому Q1 (решение оператора — вариант A)
-- держит незнакомый тег состоянием и именем виновника, а не отказом записи.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bots (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    synonym JSONB,
    -- тег `Comment` — комментарий. Пустых комментариев корпус не давал (замер 1.1: 0 из
    -- 2 файлов), отдельного состояния не заводим — тот же порядок, что `comment` V53/V54:
    -- отсутствие текста отличается от отсутствующего тега состоянием properties_state
    comment TEXT,
    -- тег `Predefined` — предопределённость (наблюдённые значения: true 1, false 1; тег
    -- есть в обоих файлах). Колонка nullable по образцу флагов `use_flag`/`predefined`
    -- узла V54 и `common_modules` V46: «тега нет» называется состоянием properties_state,
    -- а не подстановкой ложного значения. Значение флага не утверждает правомочие бота
    -- (прецедент O1 узла V49)
    predefined BOOLEAN,
    -- тег `Picture` — ссылка на картинку. Блок несёт `xr:Ref` (адрес цели) и
    -- `xr:LoadTransparent` (признак загрузки прозрачности); кратность — ровно один блок и
    -- ровно один `Ref` на файл (замер 2.1: блоков 2, `Ref` 2, `LoadTransparent` 2),
    -- поэтому ссылка хранится колонками строки вида, а не отдельной таблицей (Q1,
    -- решение оператора — вариант A: таблица `bot_pictures` при кратности 1 избыточна).
    -- `picture_ref` — адрес КАК В ВЫГРУЗКЕ; `picture_full_name` — нормализованный адрес
    -- цели; `picture_object_id`/`picture_object_uuid` — только то, что дала строка индекса
    -- состава ЭТОЙ конфигурации (uuid у составных идентификаторов индекса NULL — граница
    -- колонки `uuid` таблицы configuration_objects, узел V33), поэтому `object_id`
    -- хранится текстом и при пустом uuid
    picture_ref TEXT,
    picture_target_class TEXT NOT NULL,
    picture_full_name TEXT,
    picture_object_id TEXT,
    picture_object_uuid UUID,
    picture_load_transparent BOOLEAN,
    picture_load_transparent_state TEXT NOT NULL,
    -- состояние разбора ссылки `Picture` (Q3, вариант A): `exact` — адрес вида
    -- `CommonPicture.<Имя>`, и строка индекса состава этой выгрузки есть (замер 2.1:
    -- `CommonPicture.ОбщаяКартинка1` — 1 из 2); `std_picture` — префикс `StdPicture.`:
    -- стандартное средство платформы, индексом состава не разрешается НИКОГДА
    -- (`StdPicture.GroupConversation` — 1 из 2), и это не «не разрешилось», а другой класс
    -- цели; `unresolved` — прочий адрес или адрес вида `CommonPicture.`, строки которого в
    -- индексе нет (корпус таких не давал — это граница разбора, а не ожидаемое значение);
    -- `empty_value` — блок есть, значение `Ref` пустое (корпус не давал); `absent` — блока
    -- `Picture` в файле нет (корпус не давал: тег есть в 2/2 файлов). Внешнего ключа нет
    -- осознанно: слой `CommonPictures` (позиция 2.19) не загружен, а `StdPicture.*`
    -- существует только в платформе (прецедент Q3 узлов V50/V52/V53)
    picture_state TEXT NOT NULL,
    -- модуль вида `Bots/<Имя>/Ext/Module.bsl` — ТОЛЬКО дескрипторы (Q4, вариант A):
    -- тексты пишет узел V47 в `bsl_modules` (2 строки MinCfg уже лежат, 662 байта —
    -- замер `_v55_m1_probe.py`), стадия V55 их не читает и не снимает (мера M5).
    -- `module_state` — состояние двух ног модуля: `file_and_index` (файл есть и запись
    -- индекса состава `Bot.<Имя>.Module` есть — 2 из 2, замер 1.1), `index_only` и
    -- `file_only` (корпус не давал ни разу — ровность ног сторожит проверка П6), `absent`
    -- (ни файла, ни записи индекса — корпус не давал)
    module_state TEXT NOT NULL,
    module_source_path TEXT,
    module_source_size BIGINT,
    -- признак того, что строку `bsl_modules` уже написал узел V47: проверяется по живой
    -- БД, а не повторным разбором `ConfigDumpInfo.xml` (правило V43). `FALSE` при
    -- имеющемся файле означает «V47 для этой выгрузки ещё не запускалась», а не «модуля
    -- нет»
    module_loaded BOOLEAN NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT bots_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT bots_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50, V52,
    -- V53, V54). Именно этот механизм и есть ответ Q1 (решение оператора — вариант A):
    -- корпус словарь не замыкает, поэтому незнакомый тег не является отказом записи
    CONSTRAINT bots_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    -- «всё известно» обязано покрывать обязательную часть строки: тег `Predefined` есть во
    -- всех файлах круга (2/2, замер 2), поэтому при состоянии `all_known` флаг непустой —
    -- иначе состояние врало бы о полноте разбора (прецедент
    -- scheduled_jobs_all_known_covers_required_parts V54). Наличия блока `Picture` здесь
    -- не требуется осознанно: «тега нет» — состояние picture_state, а не результат
    -- разбора словаря свойств, и будущая выгрузка без картинки обязана читаться, а не
    -- падать
    CONSTRAINT bots_all_known_covers_required_parts
        CHECK (properties_state <> 'all_known' OR predefined IS NOT NULL),
    -- класс цели ссылки различается структурой строки, а не молчанием: `CommonPicture.`
    -- — объект конфигурации, `StdPicture.` — стандартное средство платформы, `other` —
    -- прочий адрес, `''` — адреса нет (замер 2.1: 1 + 1 на двух файлах круга)
    CONSTRAINT bots_picture_target_class_known
        CHECK (picture_target_class IN ('common_picture', 'std_picture', 'other', '')),
    CONSTRAINT bots_picture_state_known
        CHECK (picture_state IN ('exact', 'std_picture', 'unresolved', 'empty_value',
                                 'absent')),
    -- состояние ссылки согласно её значению и результату разрешения индексом состава:
    -- разрешённая держит адрес, класс `common_picture` и `object_id` строки индекса;
    -- стандартное средство держит адрес и класс `std_picture`, но не держит ничего из
    -- индекса (его там нет по определению); неразрешённая держит адрес, но не держит
    -- строк индекса; пустое значение и отсутствующий блок различимы состоянием, а не
    -- нулём (прецеденты handler_state V53, method_state V54, target_resolve_state V53)
    CONSTRAINT bots_picture_state_matches_value
        CHECK ((picture_state = 'exact'
                AND picture_ref IS NOT NULL AND picture_ref <> ''
                AND picture_full_name IS NOT NULL AND picture_full_name <> ''
                AND picture_target_class = 'common_picture'
                AND picture_object_id IS NOT NULL AND picture_object_id <> '')
               OR (picture_state = 'std_picture'
                   AND picture_ref IS NOT NULL AND picture_ref <> ''
                   AND picture_full_name LIKE 'StdPicture.%'
                   AND picture_target_class = 'std_picture'
                   AND picture_object_id IS NULL AND picture_object_uuid IS NULL)
               OR (picture_state = 'unresolved'
                   AND picture_ref IS NOT NULL AND picture_ref <> ''
                   AND picture_full_name IS NOT NULL AND picture_full_name <> ''
                   AND picture_target_class IN ('common_picture', 'other')
                   AND picture_object_id IS NULL AND picture_object_uuid IS NULL)
               OR (picture_state = 'empty_value'
                   AND picture_ref = '' AND picture_target_class = ''
                   AND picture_full_name IS NULL AND picture_object_id IS NULL
                   AND picture_object_uuid IS NULL)
               OR (picture_state = 'absent'
                   AND picture_ref IS NULL AND picture_target_class = ''
                   AND picture_full_name IS NULL AND picture_object_id IS NULL
                   AND picture_object_uuid IS NULL
                   AND picture_load_transparent IS NULL
                   AND picture_load_transparent_state = 'absent')),
    -- uuid цели возможен только у разрешённой ссылки: при `std_picture` и `unresolved`
    -- строки индекса нет, и подставленный uuid врал бы о существовании цели
    CONSTRAINT bots_picture_uuid_only_when_resolved
        CHECK (picture_object_uuid IS NULL OR picture_state = 'exact'),
    -- признак загрузки прозрачности: значение и его отсутствие различимы состоянием
    -- (прецедент словаря состояний атрибутов V54); при отсутствующем блоке значения быть
    -- не может (замер 2.1: `LoadTransparent=true` в 2/2 файлов круга)
    CONSTRAINT bots_picture_load_transparent_state_known
        CHECK (picture_load_transparent_state IN ('set', 'absent')),
    CONSTRAINT bots_picture_load_transparent_matches_picture
        CHECK ((picture_load_transparent_state = 'set'
                AND picture_load_transparent IS NOT NULL
                AND picture_state <> 'absent')
               OR (picture_load_transparent_state = 'absent'
                   AND picture_load_transparent IS NULL)),
    -- модуль вида: состояние двух ног и дескриптор согласованы — путь и размер
    -- называются только при файле; «записи индекса нет» и «файла нет» различимы
    -- состоянием, а не нулём (прецеденты schedule_file_state V54, code_state V44)
    CONSTRAINT bots_module_state_known
        CHECK (module_state IN ('file_and_index', 'index_only', 'file_only', 'absent')),
    CONSTRAINT bots_module_state_matches_descriptor
        CHECK ((module_state IN ('file_and_index', 'file_only')
                AND module_source_path IS NOT NULL AND module_source_path <> ''
                AND module_source_size IS NOT NULL AND module_source_size >= 0)
               OR (module_state IN ('index_only', 'absent')
                   AND module_source_path IS NULL AND module_source_size IS NULL)),
    -- строка `bsl_modules` возможна только там, где модуль подтверждён индексом состава
    -- (её пишет узел V47); при `file_only` строки модуля нет осознанно, а `FALSE` при
    -- `file_and_index` — это «V47 для этой выгрузки ещё не запускалась», а не «модуля
    -- нет» (Q4, вариант A, мера M5)
    CONSTRAINT bots_module_loaded_matches_state
        CHECK ((module_loaded AND module_state = 'file_and_index') OR NOT module_loaded),
    CONSTRAINT bots_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT bots_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT bots_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна. Замер коллизий
    -- между выгрузками даёт ноль потому, что сравнивать нечего (2 строки в одной
    -- выгрузке), а не потому, что коллизий нет; перечень заголовка хранит детей массивом
    -- имён, и тот же ключ читают витрины видов V48…V54 (замер `_v55_m1_probe.py`,
    -- раздел 1.3 плана)
    CONSTRAINT bots_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- Витрины узла V55. Текущее состояние строки бота выводится тем же порядком, что
-- витрины V46/V48/V49/V50/V51/V52/V53/V54: строка относится к максимальной ревизии в
-- пределах ключа своей цепочки; признак коммита на круг не влияет (решение A1). Имя
-- витрины задаёт не этот файл: его отдаёт current_view() по реестру
-- CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py. Второй витрины у узла нет (M3): второй таблицы у вида
-- нет — детей и содержимого со своей схемой у него ноль (замер 1.1), а модуль вида
-- читается витриной узла V47 (`v_current_bsl_modules`), а не своей.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_bots AS
SELECT b.id,
       b.configuration_uuid, b.object_uuid, b.object_name, b.full_name,
       b.synonym, b.comment, b.predefined,
       b.picture_ref, b.picture_target_class, b.picture_full_name,
       b.picture_object_id, b.picture_object_uuid,
       b.picture_load_transparent, b.picture_load_transparent_state, b.picture_state,
       b.module_state, b.module_source_path, b.module_source_size, b.module_loaded,
       b.properties_state, b.unknown_property_names,
       b.source_path, b.created_at, b.revision_no, b.changed_at, b.changed_by,
       b.is_committed
FROM bots b
WHERE NOT EXISTS (SELECT 1 FROM bots h
                  WHERE h.configuration_uuid = b.configuration_uuid
                    AND h.object_name = b.object_name
                    AND h.revision_no > b.revision_no);

-- ---------------------------------------------------------------------------
-- Индексы узла V55 (боты, позиция 2.10). Отдельного индекса по configuration_uuid у
-- таблицы bots не заводим: у строки вида его обслуживает уникальный индекс цепочки с
-- ведущей колонкой configuration_uuid — им же пользуются предикат витрины и чистка
-- стадии по конфигурации (тот же порядок, что V46, V48…V54).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_bots_object_uuid_revision
    ON bots(object_uuid, revision_no);
-- Обратный вопрос карточки «какие боты ссылаются на эту картинку» идёт по нормализованному
-- адресу цели (он есть и у `StdPicture.` — стандартное средство тоже спрашивается), а для
-- разрешённых ссылок — по uuid цели из индекса состава (те же два индекса, что
-- idx_event_subscription_sources_target_* узла V53). Частичные — потому что при состояниях
-- `empty_value` и `absent` колонок нет, а индекс по NULL-значениям смысла не имеет.
-- Отдельного индекса по module_source_path нет: модуль вида читается строкой `bsl_modules`
-- и её витриной (узел V47), а не поиском по пути в таблице вида (Q4, вариант A).
CREATE INDEX IF NOT EXISTS idx_bots_picture_full_name
    ON bots(picture_full_name) WHERE picture_full_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bots_picture_object_uuid
    ON bots(picture_object_uuid) WHERE picture_object_uuid IS NOT NULL;

SELECT 'Боты (узел V55) добавлены в схему!' AS status;