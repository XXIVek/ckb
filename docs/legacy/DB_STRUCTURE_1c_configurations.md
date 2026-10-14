# Структура базы данных 1c_configurations

ЦЕЛЬ: Хранение метаданных 1C конфигураций, расширений, внешних обработок и отчетов.

---

## ВАЖНО: XDTO-схемы

Для корректного парсинга XML конфигураций 1С необходимы XDTO-схемы. Без них мы не можем гарантировать корректную запись объектов.

Необходимые схемы:
- MetadataObjects.xdto - основные объекты метаданных
- Configuration.xdto - схема конфигурации
- DataCompositionSchema.xdto - схемы компоновки данных
- Form.xdto - схема форм
- ReportProcessing.xdto - обработка отчетов

Где взять:
1. В каталоге выгрузки: Configuration.xml содержит ссылки на типы
2. Документация 1C: https://dev.1c.ru/doc/xdto/
3. Справочник метаданных

Стратегия: работать через XPath/XQuery напрямую.

---

## ТАБЛИЦЫ БАЗЫ ДАННЫХ

### А. configurations - Конфигурации

Поля:
1. id (SERIAL PK) - Автоинкрементный идентификатор
2. name (VARCHAR(255) UNIQUE) - Имя конфигурации
3. synonym (TEXT) - Синоним/полное название
4. comment (TEXT) - Комментарий
5. version (VARCHAR(50)) - Версия
6. vendor_name (VARCHAR(255)) - Поставщик
7. main_mode (VARCHAR(50)) - Основной режим: Управляемое приложение / Стандартное приложение / Веб-клиент
8. usage_purpose (VARCHAR(100)) - Назначение использования: Приложение для платформы / Библиотека
9. embedded_language (VARCHAR(50)) - Вариант встроенного языка
10. main_roles (TEXT[]) - Основные роли (массив ссылок)
11. app_module (INT FK bsl_modules.id) - Модуль приложения (BSL)
12. session_module (INT FK bsl_modules.id) - Модуль сеанса (BSL)
13. data_proc_module (INT FK bsl_modules.id) - Модуль управления данными (BSL)
14. ext_conn_module (INT FK bsl_modules.id) - Модуль внешнего соединения (BSL)

Пример (БП 3.0): name=БухгалтерияПредприятия, synonym=Бухгалтерия предприятия ред. 3.0, version=3.0.206.19

---

### Б. config_extensions - Расширения конфигураций

Поля:
1. id (SERIAL PK)
2. configuration_id (INT FK configurations.id NOT NULL) - Ссылка на основную конфигурацию
3. name (VARCHAR(255) UNIQUE) - Имя расширения
4. synonym (TEXT) - Синоним
5. comment (TEXT) - Комментарий
6. version (VARCHAR(50)) - Версия
7. vendor_name (VARCHAR(255)) - Поставщик
8. uuid (UUID UNIQUE) - UUID расширения

Ограничение: configuration_id NOT NULL - расширение не может существовать без основной конфигурации.

---

### В. external_processing - Внешние обработки

Поля:
1. id (SERIAL PK)
2. configuration_id (INT FK configurations.id NULL) - Ссылка на конфигурацию (может быть NULL для универсальных)
3. name (VARCHAR(255) UNIQUE) - Имя обработки
4. synonym (TEXT) - Синоним
5. comment (TEXT) - Комментарий
6. processing_ref (INT FK metadata_processing.id) - Ссылка на объект метаданных Обработка
7. version (VARCHAR(50)) - Версия обработки
8. uuid (UUID UNIQUE) - UUID обработки

Пример: ТСД_1С_XXI_Век (configuration_id=NULL, универсальная обработка)

---

### Г. external_report - Внешние отчеты

Поля:
1. id (SERIAL PK)
2. configuration_id (INT FK configurations.id NULL) - Ссылка на конфигурацию (может быть NULL для универсальных)
3. name (VARCHAR(255) UNIQUE) - Имя отчета
4. synonym (TEXT) - Синоним
5. comment (TEXT) - Комментарий
6. report_ref (INT FK metadata_report.id) - Ссылка на объект метаданных Отчет
7. version (VARCHAR(50)) - Версия отчета
8. uuid (UUID UNIQUE) - UUID отчета

Пример: СравнениеУСНИ90_2 (configuration_id=NULL, универсальный отчет)

---

### Д. bsl_modules - Модули BSL

Поля:
1. id (SERIAL PK)
2. configuration_id (INT FK configurations.id) - Ссылка на конфигурацию/обработку/отчет
3. module_name (VARCHAR(255)) - Имя модуля
4. file_path (VARCHAR(500)) - Путь к файлу BSL
5. code (TEXT) - Полный код модуля
6. object_type (VARCHAR(50)) - Тип: AppModule, SessionModule, DataProcModule, ExtConnModule
7. object_name (VARCHAR(255)) - Имя родительского объекта

---

### Е. common_pictures - Общие картинки

Поля: id (SERIAL PK), configuration_id (INT FK), name (VARCHAR(255)), file_path (VARCHAR(500))

---

### Ж. common_designs - Общие макеты

Поля: id (SERIAL PK), configuration_id (INT FK), name (VARCHAR(255)), file_path (VARCHAR(500)), content (TEXT)

---

### З. common_forms - Общие формы

Поля: id (SERIAL PK), configuration_id (INT FK), name (VARCHAR(255)), file_path (VARCHAR(500)), module_code (TEXT)

---

## БУДУЩИЕ ТАБЛИЦЫ (объекты метаданных)

### И. metadata_report - Объекты метаданных Отчеты

Поля: id, configuration_id, name, synonym, comment, uuid, main_data_composition_schema, module_code, object_module_code, forms (JSONB), attributes (JSONB), tabular_sections (JSONB)

### К. metadata_processing - Объекты метаданных Обработки

Поля: id, configuration_id, name, synonym, comment, uuid, module_code, form_id

### Л. metadata_forms - Объекты метаданных Формы

Поля: id, configuration_id, name, type (Main/Settings/Variant), xml_content (TEXT), module_code (TEXT)

---

## ОТНОШЕНИЯ МЕЖДУ ТАБЛИЦАМИ

configurations (1) ──────── (N) bsl_modules
     │
     ├──── (1) ───── config_extensions
     │
     ├──── (1) ───── external_processing (configuration_id может быть NULL)
     │
     ├──── (1) ───── external_report (configuration_id может быть NULL)
     │
     ├──── (N) ───── common_pictures
     │
     ├──── (N) ───── common_designs
     │
     └──── (N) ───── common_forms

metadata_report (1) ── (N) metadata_forms
metadata_processing (1) ── (N) metadata_forms

---

## ПРИМЕРЫ ЗАПОЛНЕНИЯ

### Внешний отчет СравнениеУСНИ90_2

INSERT INTO external_report (configuration_id, name, synonym, comment, version, uuid)
VALUES (NULL, СравнениеУСНИ90_2, Сравнение УСН и 90, , 1.0.0.0, a6db7252-5cfd-4e33-8e28-66e8f1a74a46);

### Внешняя обработка ТСД_1С_XXI_Век

INSERT INTO external_processing (configuration_id, name, synonym, comment, version, uuid)
VALUES (NULL, ТСД_1С_XXI_Век, ТСД для 1С (XXI Век), Рабочее место для управления смартфонами, 1.0.0.0, uuid);

---

## СТРУКТУРА ФАЙЛОВ КОНФИГУРАЦИИ

### Внешний отчет:

Отчет/
├── Отчет.xml - Главный файл (Name, Synonym, Comment) + ChildObjects: Attributes, TabularSections, Forms, Templates
├── Ext/
│   ├── ObjectModule.bsl - Модуль объекта
│   └── ManagerModule.bsl - Модуль менеджера
└── Forms/
    ├── ФормаОтчета/
    │   ├── XMLForm.xml - Описание формы
    │   └── Ext/Form.xml - Расширенная форма
    │   └── Ext/Form/Module.bsl - Код модуля
    └── ...
└── Templates/
    ├── ОсновнаяСхемаКомпоновкиДанных/
    │   ├── XMLForm.xml - Описание макета
    │   └── Ext/Template.xml - DataCompositionSchema

---

Дата создания: 09.10.2026
Статус: Черновик - требуется доработка с учетом XDTO-схем

---

## ОБНОВЛЕНИЕ НА ОСНОВЕ СПЕЦИФИКАЦИЙ cc-1c-skills

### Версия формата метаданных: 2.17

#### Ключевые изменения для external_report:

Добавлены поля из Properties отчета (раздел 2.2 1c-erf-spec.md):
- main_data_composition_schema — основная СКД (ссылка на макет)
- default_form — основная форма
- auxiliary_form — вспомогательная форма
- default_settings_form — форма настроек по умолчанию
- auxiliary_settings_form — вспомогательная форма настроек
- default_variant_form — форма варианта по умолчанию
- variants_storage — хранилище вариантов
- settings_storage — хранилище настроек

#### Структура БД обновлена:
Теперь включает таблицы для:
1. report_attributes — реквизиты отчета [{uuid, name, type, synonym}]
2. report_tabular_sections — табличные части
3. tabular_section_attributes — реквизиты табличных частей
4. report_forms — формы с ссылками на XML-файлы
5. report_templates — макеты (включая СКД)

#### Классы объектов (ClassId):
- ExternalReport: e41aff26-25cf-4bb6-b6c1-3f478a75f374
- ExternalDataProcessor: e41aff26-25cf-4bb6-b6c1-3f478a75f374

#### Пространства имён XML:
- MDClasses: http://v8.1c.ru/8.3/MDClasses (корневой элемент)
- logform: http://v8.1c.ru/8.3/xcf/logform (Form.xml)
- core: http://v8.1c.ru/8.1/data/core (типы v8:)
- current-config: http://v8.1c.ru/8.1/data/enterprise/current-config (типы cfg:)
