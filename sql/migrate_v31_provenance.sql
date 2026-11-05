-- Аддитивная миграция V31 для УЖЕ СОЗДАННЫХ баз ckb_1c_configurations.
-- Узел V31 (вариант 2 плана правок, 16.10.2026): провенанс строки внешнего объекта —
-- из какого входа она загружена и чем подтверждён состав этого входа.
-- Дата: 16.10.2026.
-- Повторное применение безопасно: ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT IF EXISTS,
-- ADD CONSTRAINT после снятия, CREATE INDEX IF NOT EXISTS. Данные существующих строк
-- не меняются: провенанс у них остаётся незаписанным (NULL), и это честное состояние.
-- Источник истины — src/generate_ddl.py (шаг 1, генерирует src/ddl_external_report.sql):
-- тексты колонок, ограничений и индекса повторяются здесь ДОСЛОВНО, поэтому после этой
-- миграции живая БД и чистая установка совпадают (сверка python _cmp_ddl.py, ожидание:
-- расхождений нет, код возврата 0).
-- ============================================================
-- Что появляется и зачем (полная модель — docs/EXTERNAL_OBJECT_EDIT_PLAN.md, раздел 16):
--   * origin_kind        — вид источника: 'catalog' (каталог XML-выгрузки), 'binary_file'
--                          (файл .erf/.epf), 'authored_layout' (наш сгенерированный layout).
--   * origin_path        — путь этого входа (для .erf/.epf — сам файл, а не каталог разбора:
--                          последний удаляется после успеха и не является источником).
--   * origin_sha256      — digest несущего входа: файла или поимённого listing каталога.
--   * origin_manifest    — состав входа: для файла {kind, scope, size}, для каталога
--                          {kind, scope, file_count, files[] (путь, размер, sha256), truncated}.
--   * origin_recorded_at — когда провенанс записан.
--   Заполняет их ЗАГРУЗЧИК по факту своего входа (не оператор): в отличие от configuration_id
--   (узел V20), который force=True переносит, провенанс force=True ПЕРЕЗАПИСЫВАЕТ — это
--   слепок текущего источника, а не заявление оператора.
--   NULL в этих колонках означает «провенанс не записан»: строки, загруженные до узла V31,
--   и строки, источник которых не удалось прочитать (несущий файл не читается, listing
--   каталога обрезан по MAX_MANIFEST_FILES). Второй случай — предупреждение в карточке
--   загрузки, а не отказ загрузки (правило R15).
--   Digest каталога — поимённый listing, а не склейка содержимого: два разных каталога не
--   должны давать один отпечаток, и по listing видно, какой именно файл изменился между
--   двумя состояниями. Поэтому digest файла и digest каталога несравнимы — это держит
--   отдельное поле origin_manifest.scope, а не догадка читающего.
-- ============================================================

BEGIN;

ALTER TABLE external_report
    ADD COLUMN IF NOT EXISTS origin_kind TEXT,
    ADD COLUMN IF NOT EXISTS origin_path TEXT,
    ADD COLUMN IF NOT EXISTS origin_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS origin_manifest JSONB;

-- Время записи провенанса добавляется ОТДЕЛЬНО и сначала БЕЗ значения по умолчанию:
-- PostgreSQL заполняет существующие строки значением DEFAULT, а для строк, загруженных до
-- V31, время записи провенанса неизвестно — поставить сюда время миграции значило бы
-- соврать о факте. DEFAULT включается сразу после, как в src/generate_ddl.py: новая
-- загрузка обязана фиксировать момент записи провенанса.
ALTER TABLE external_report
    ADD COLUMN IF NOT EXISTS origin_recorded_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE external_report
    ALTER COLUMN origin_recorded_at SET DEFAULT CURRENT_TIMESTAMP;

-- Ограничения. Тексты обязаны совпадать с src/generate_ddl.py: _cmp_ddl.py сравнивает
-- pg_get_constraintdef, а не текст файла. Имена заданы явно — иначе автоимена от
-- чистой установки и от миграции разошлись бы.
ALTER TABLE external_report
    DROP CONSTRAINT IF EXISTS external_report_origin_kind_check;
ALTER TABLE external_report
    ADD CONSTRAINT external_report_origin_kind_check
    CHECK (origin_kind IS NULL
           OR origin_kind IN ('catalog', 'binary_file', 'authored_layout'));

-- Провенанс либо записан парой (вид + путь), либо отсутствует целиком: вид без пути —
-- строка, по которой нельзя ничего проверить, а путь без вида не говорит, что именно
-- сравнивать (digest файла и listing каталога несравнимы).
ALTER TABLE external_report
    DROP CONSTRAINT IF EXISTS external_report_origin_pair_check;
ALTER TABLE external_report
    ADD CONSTRAINT external_report_origin_pair_check
    CHECK ((origin_kind IS NULL) = (origin_path IS NULL));

-- Digest обязан быть SHA256: 64 hex-символа. Сравнение чисел из разных алгоритмов
-- означало бы «совпало» там, где сравнивать нечего.
ALTER TABLE external_report
    DROP CONSTRAINT IF EXISTS external_report_origin_sha256_check;
ALTER TABLE external_report
    ADD CONSTRAINT external_report_origin_sha256_check
    CHECK (origin_sha256 IS NULL OR origin_sha256 ~ '^[0-9a-f]{64}$');

-- Обратный запрос «не загружен ли уже этот файл/каталог» (сверка провенанса перед
-- force=True, поиск строки по digest'у источника) — тот же мотив, что у индекса
-- configuration_id.
CREATE INDEX IF NOT EXISTS idx_external_report_origin_sha256
    ON external_report(origin_sha256);

COMMIT;

-- Проверка результата:
--   python _cmp_ddl.py                     # расхождений нет, код возврата 0
--   SQL: SELECT origin_kind, count(*) FROM external_report GROUP BY 1;
--        -- до первой загрузки после V31: одна строка с NULL (= «не записан»)
--   SQL: SELECT conname FROM pg_constraint
--        WHERE conrelid = 'external_report'::regclass
--          AND conname LIKE 'external_report_origin%';   -- их обязано быть три
--   SQL: SELECT count(*) FROM pg_indexes WHERE tablename = 'external_report'
--          AND indexname = 'idx_external_report_origin_sha256';   -- должно быть 1
--   python tools/check_v31_provenance.py   # живой контракт: запись, карточка, сравнение
--   python validate_load_flow.py --with-load