-- ============================================
-- migrate_v33_configuration_objects.sql — узел V33 (17.10.2026)
-- Аддитивная миграция для УЖЕ СОЗДАННЫХ баз: перечень объектов метаданных конфигурации.
--
-- Таблица `configuration_objects` создаётся шагом 2 установки
-- (create_1c_configurations_db.sql) — здесь тот же SQL, применённый к живой БД.
-- Порядок для живой базы: применить этот файл, затем проверить соответствие
-- `python _cmp_ddl.py` (он собирает временную БД шагами 1 → 1b → 2 и сверяет со живой).
--
-- Что появляется и почему именно так (замеры 17.10.2026 по C:\1C_LLM\LoadDoc\BGU2,
-- подробности — docs/config-scenarios/01_configuration.md):
--   * источник — индекс `ConfigDumpInfo.xml`: 122 164 записи `<Metadata>`
--     (86 379 с каноническим uuid v4, 35 713 составных `<uuid>.<N>`, 72 `<uuid>.1c`);
--     `configVersion` есть у 67 887 записей — у остальных его нет в самом индексе;
--   * `object_id` — TEXT: форма идентификатора разная, приводить всё к uuid нельзя;
--     `uuid` заполняется только когда идентификатор является каноническим uuid;
--   * `parent_name`/`depth` выводятся из имени (иерархия XML покрывает лишь часть
--     записей): чётное число сегментов — отсечь пару `вид.имя`, нечётное — последний
--     сегмент. На BGU3/BGU2 правило даёт существующего родителя для всех 110 461
--     не-верхних записей (0 пропусков).
-- ============================================

CREATE TABLE IF NOT EXISTS configuration_objects (
    id BIGSERIAL PRIMARY KEY,
    configuration_id INT NOT NULL REFERENCES configurations(id),
    name TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_name TEXT NOT NULL,
    child_type TEXT,
    parent_name TEXT,
    depth SMALLINT NOT NULL DEFAULT 0,
    object_id TEXT NOT NULL,
    uuid UUID,
    config_version TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT configuration_objects_name_unique UNIQUE (configuration_id, name),
    CONSTRAINT configuration_objects_object_id_unique UNIQUE (configuration_id, object_id),
    CONSTRAINT configuration_objects_depth_non_negative CHECK (depth >= 0)
);

CREATE INDEX IF NOT EXISTS idx_config_objects_config
    ON configuration_objects(configuration_id);
CREATE INDEX IF NOT EXISTS idx_config_objects_type
    ON configuration_objects(configuration_id, object_type);
CREATE INDEX IF NOT EXISTS idx_config_objects_object_name
    ON configuration_objects(configuration_id, object_name);
CREATE INDEX IF NOT EXISTS idx_config_objects_parent
    ON configuration_objects(configuration_id, parent_name);
CREATE INDEX IF NOT EXISTS idx_config_objects_object_id
    ON configuration_objects(configuration_id, object_id);
CREATE INDEX IF NOT EXISTS idx_config_objects_uuid
    ON configuration_objects(uuid) WHERE uuid IS NOT NULL;
