-- ============================================
-- БД 1c_configurations
-- Структура на основе спецификаций cc-1c-skills
-- Версия формата метаданных: 2.17
-- ============================================

-- Создание базы данных (выполнить вручную):
-- CREATE DATABASE ckb_1c_configurations;
-- \c ckb_1c_configurations

-- --------------------------------------------
-- ТАБЛИЦА А. configurations (конфигурации)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS configurations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    synonym TEXT,
    comment TEXT,
    version VARCHAR(50),
    vendor_name VARCHAR(255),
    uuid UUID,
    main_mode VARCHAR(50),
    usage_purpose VARCHAR(100),
    embedded_language VARCHAR(50),
    main_roles TEXT[],
    app_module_id INT,
    session_module_id INT,
    data_proc_module_id INT,
    ext_conn_module_id INT,
    mobile_functionality TEXT[],
    default_language VARCHAR(50),
    short_info TEXT,
    detailed_info TEXT,
    copyright VARCHAR(500),
    vendor_url VARCHAR(500),
    config_url VARCHAR(500),
    update_url VARCHAR(500),
    help_included BOOLEAN DEFAULT FALSE,
    lock_mode_default VARCHAR(50),
    modality_mode VARCHAR(100),
    ext_comp_sync_mode VARCHAR(100),
    interface_compat_mode VARCHAR(100),
    compatibility_mode VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА Б. config_extensions (расширения)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS config_extensions (
    id SERIAL PRIMARY KEY,
    configuration_id INT NOT NULL REFERENCES configurations(id),
    name VARCHAR(255) UNIQUE NOT NULL,
    synonym TEXT,
    comment TEXT,
    version VARCHAR(50),
    vendor_name VARCHAR(255),
    uuid UUID UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА В. external_processing (внешние обработки)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS external_processing (
    id SERIAL PRIMARY KEY,
    configuration_id INT REFERENCES configurations(id),
    name VARCHAR(255) UNIQUE NOT NULL,
    synonym TEXT,
    comment TEXT,
    version VARCHAR(50),
    uuid UUID UNIQUE,
    class_id VARCHAR(36) DEFAULT 'e41aff26-25cf-4bb6-b6c1-3f478a75f374',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА Г. external_report (внешние отчеты)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS external_report (
    id SERIAL PRIMARY KEY,
    configuration_id INT REFERENCES configurations(id),
    name VARCHAR(255) UNIQUE NOT NULL,
    synonym TEXT,
    comment TEXT,
    version VARCHAR(50),
    uuid UUID UNIQUE,
    class_id VARCHAR(36) DEFAULT 'e41aff26-25cf-4bb6-b6c1-3f478a75f374',
    main_data_composition_schema VARCHAR(255),
    default_form VARCHAR(255),
    auxiliary_form VARCHAR(255),
    default_settings_form VARCHAR(255),
    auxiliary_settings_form VARCHAR(255),
    default_variant_form VARCHAR(255),
    variants_storage VARCHAR(255),
    settings_storage VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА Д. bsl_modules (модули BSL)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS bsl_modules (
    id SERIAL PRIMARY KEY,
    configuration_id INT REFERENCES configurations(id),
    module_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    code TEXT,
    object_type VARCHAR(50),
    object_name VARCHAR(255),
    report_id INT REFERENCES external_report(id),
    processing_id INT REFERENCES external_processing(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА Е. report_attributes (реквизиты отчета)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS report_attributes (
    id SERIAL PRIMARY KEY,
    report_id INT NOT NULL REFERENCES external_report(id) ON DELETE CASCADE,
    uuid VARCHAR(36),
    name VARCHAR(255) NOT NULL,
    synonym TEXT,
    type VARCHAR(255),
    password_mode BOOLEAN DEFAULT FALSE,
    fill_checking VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА Ж. report_tabular_sections (табличные части)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS report_tabular_sections (
    id SERIAL PRIMARY KEY,
    report_id INT NOT NULL REFERENCES external_report(id) ON DELETE CASCADE,
    uuid VARCHAR(36),
    name VARCHAR(255) NOT NULL,
    synonym TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА З. tabular_section_attributes (реквизиты ТЧ)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS tabular_section_attributes (
    id SERIAL PRIMARY KEY,
    tsection_id INT NOT NULL REFERENCES report_tabular_sections(id) ON DELETE CASCADE,
    uuid VARCHAR(36),
    name VARCHAR(255) NOT NULL,
    synonym TEXT,
    type VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА И. report_forms (формы отчета)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS report_forms (
    id SERIAL PRIMARY KEY,
    report_id INT REFERENCES external_report(id),
    uuid VARCHAR(36),
    name VARCHAR(255) NOT NULL,
    synonym TEXT,
    form_type VARCHAR(50),
    xml_file_path VARCHAR(500),
    module_code TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА К. report_templates (макеты отчета)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS report_templates (
    id SERIAL PRIMARY KEY,
    report_id INT REFERENCES external_report(id),
    uuid VARCHAR(36),
    name VARCHAR(255) NOT NULL,
    synonym TEXT,
    template_type VARCHAR(100),
    xml_file_path VARCHAR(500),
    content_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ИНДЕКСЫ
-- --------------------------------------------
CREATE INDEX idx_configurations_name ON configurations(name);
CREATE INDEX idx_external_report_name ON external_report(name);
CREATE INDEX idx_external_processing_name ON external_processing(name);
CREATE INDEX idx_bsl_modules_config ON bsl_modules(configuration_id);
CREATE INDEX idx_report_attributes_report ON report_attributes(report_id);
CREATE INDEX idx_report_tsections_report ON report_tabular_sections(report_id);
CREATE INDEX idx_tsection_attrs_tsection ON tabular_section_attributes(tsection_id);
CREATE INDEX idx_report_forms_report ON report_forms(report_id);
CREATE INDEX idx_report_templates_report ON report_templates(report_id);
