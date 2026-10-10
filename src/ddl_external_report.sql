-- ============================================================
-- Скрипт перестройки схемы для внешних отчетов/обработок 1С
-- Дата: 10.10.2026
-- База: ckb_1c_configurations
-- ============================================================

-- 1. external_report — внешний отчет / внешняя обработка
CREATE TABLE external_report (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    containedobject_classid UUID DEFAULT 'e41aff26-25cf-4bb6-b6c1-3f478a75f374',
    containedobject_objectid UUID,
    generatedtype_name TEXT,
    generatedtype_category TEXT DEFAULT 'Object',
    generatedtype_typeid UUID,
    generatedtype_valueid UUID,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    default_form TEXT,
    auxiliary_form TEXT,
    main_data_composition_schema TEXT,
    default_settings_form TEXT,
    auxiliary_settings_form TEXT,
    default_variant_form TEXT,
    variants_storage TEXT,
    settings_storage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_external_report_uuid ON external_report(uuid);

-- 2. attributes — реквизиты объекта (универсальная)
CREATE TABLE attributes (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    type TEXT,
    format TEXT,
    editformat TEXT,
    tooltip TEXT,
    password_mode BOOLEAN DEFAULT FALSE,
    mark_negatives BOOLEAN DEFAULT FALSE,
    mask TEXT,
    multiline BOOLEAN DEFAULT FALSE,
    extended_edit BOOLEAN DEFAULT FALSE,
    min_value TEXT,
    max_value TEXT,
    fill_checking TEXT DEFAULT 'DontCheck',
    fill_from_filling_value BOOLEAN DEFAULT FALSE,
    fill_value TEXT,
    choice_folders_and_items TEXT,
    choice_parameter_links TEXT,
    choice_parameters TEXT,
    quick_choice TEXT DEFAULT 'Auto',
    create_on_input TEXT DEFAULT 'Auto',
    choice_form TEXT,
    link_by_type TEXT,
    choice_history_on_input TEXT DEFAULT 'Auto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_attributes_parent_uuid ON attributes(parent_uuid);
CREATE INDEX idx_attributes_name ON attributes(name);

-- 3. tabular_sections — табличные части
CREATE TABLE tabular_sections (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    internalinfo_generatedtype JSONB,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    tooltip TEXT,
    fill_checking TEXT DEFAULT 'DontCheck',
    standardattributes JSONB,
    column_uuids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tabular_sections_parent_uuid ON tabular_sections(parent_uuid);
CREATE INDEX idx_tabular_sections_name ON tabular_sections(name);

-- 4. forms — формы
CREATE TABLE forms (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    form_type TEXT DEFAULT 'Unmanaged',
    include_help_in_contents BOOLEAN DEFAULT FALSE,
    use_purposes JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_forms_parent_uuid ON forms(parent_uuid);
CREATE INDEX idx_forms_name ON forms(name);

-- 5. templates — макеты
CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    parent_uuid UUID NOT NULL REFERENCES external_report(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    template_type TEXT DEFAULT 'TabularDocument',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_templates_parent_uuid ON templates(parent_uuid);
CREATE INDEX idx_templates_name ON templates(name);

SELECT 'Схема успешно создана!' AS status;
