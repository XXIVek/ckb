# Сценарий 4: Загрузка внешнего отчета (external_report)

## 🎯 Когда использовать
- В корневом XML выгрузки есть элемент `<ExternalReport>` — признак варианта по правилу R1
  (файл в корне каталога, без рекурсии в подкаталоги)
- Один отчет без привязки к конфигурации
- Пример: СравнениеУСН, Тестовые отчеты (`Test1_Otchet` … `Test4_Otchet_Regress`)

## 📂 Структура каталога внешнего отчета (фактический эталон `Test1_Otchet`)

```
Test1_Otchet/
├── СравнениеУСНИ90_2.xml                                    ← Метаданные (ExternalReport)
├── СравнениеУСНИ90_2/
│   ├── Ext/ObjectModule.bsl                                 ← Модуль объекта → bsl_modules
│   ├── Forms/ФормаОтчета.xml                                ← Регистрация формы (uuid) → forms
│   ├── Forms/ФормаОтчета/Ext/Form.xml                       ← Описание формы → form_ext
│   ├── Forms/ФормаОтчета/Ext/Form/Module.bsl                ← Модуль формы → form_ext.ext
│   ├── Templates/ОсновнаяСхемаКомпоновкиДанных.xml          ← Регистрация макета (uuid) → templates
│   └── Templates/ОсновнаяСхемаКомпоновкиДанных/Ext/Template.xml ← Содержимое макета → templates.ext
```

`Forms/<Имя>.xml` и `Templates/<Имя>.xml` (рядом с каталогом содержимого) — единственный источник
`uuid` формы/макета; каталоги `Forms/`, `Templates/` без этих файлов не порождают строк.

## 🔄 Алгоритм загрузки

Отдельного «анализа источника» нет: тип каталога определяет сама единая точка входа
(правило R1 норматива `FLOWCHART_1c-configurations-core.md`).

```python
load_1c_catalog_tool(source_path=r"C:\1C_LLM\LoadDoc\Отчет", force=False)
# Внешний отчёт → запись в external_report с object_kind='external_report' (узел V22: тот же
# заголовок, что у внешней обработки; вид различает колонка, отдельной таблицы нет),
# дети из корневого XML (V12) и из подкаталогов Forms/, Templates/, Ext/ (V13).
# Дубликат по UUID → ⚠️ карточка; подтверждение перезагрузки — force=True.

delete_external_report_tool(source_path=... | uuid=... | report_id=...)
# Удаляет объект, его BSL-модули; формы/описания форм/макеты/реквизиты/ТЧ — каскадом.
```

### Шаг 3: Проверка результата (счётчики в карточке)

| Метрика | Описание |
|---------|----------|
| Тип / ID / UUID / Название | узел внешнего объекта |
| `attributes` | реквизиты объекта + колонки табличных частей из `ChildObjects` |
| `tabular_sections` | табличные части (колонки — в `column_uuids`) |
| `forms` | строки форм по файлам `Forms/<Имя>.xml` |
| `form_ext` | описания форм (`Form.xml`) и их модули (`Form/Module.bsl`) |
| `templates` | макеты, содержимое — в `ext` / `ext_bin` |
| `bsl_modules` | модули `Ext/objectmodule.bsl`, `Ext/managermodule.bsl` (модули форм — в `form_ext.ext`) |

## ⚠️ Edge-cases

### Пустой ChildObjects (0 реквизитов, 0 ТЧ, 0 форм, 0 макетов)
- `<ChildObjects/>` пуст — загрузка **не падает** (эталон `Test3_Otchet_Null`, `Test4_Otchet_Regress`)
- В `external_report` вставляется только корневая запись из `Properties`
- Дочерние таблицы (`attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`) пустые — это **нормально**
- UUID из корневого тега `<ExternalReport uuid="...">` обязателен

### Пустой UUID
- Пустой `uuid` у корневого объекта ИЛИ у любого дочернего элемента (`Attribute`,
  `TabularSection`, `Form`, `Template`) — `❌` по правилу R3, загрузка не начинается, БД чиста

### Отсутствие папок Forms/Templates/Ext
- Загрузка продолжается без ошибок, счётчики `forms`/`form_ext`/`templates`/`bsl_modules` = 0,
  в карточке — предупреждение
- Бинарная форма (`Forms/<Имя>/Ext/Form.bin`) — не ошибка: содержимое в `form_ext.ext_bin`,
  свойства формы не разбираются

### Форма/макет есть в XML, но нет каталога содержимого (или наоборот)
- Имена из корневого XML — только сверка; расхождение даёт предупреждение, а не отказ
- `uuid` формы и макета берётся исключительно из `Forms/<Имя>.xml` / `Templates/<Имя>.xml`

## 📊 Схема БД для внешних отчетов (6 таблиц)

| Таблица | Строк | Назначение | Связь |
|---------|-------|-----------|---------------------|
| `external_report` | Главный | Внешние объекты 1С: отчёты и обработки; вид — `object_kind` (`external_report` / `external_processing`, CHECK, узел V22) | `uuid UNIQUE` |
| `attributes` | Реквизиты | Универсальная таблица реквизитов и колонок ТЧ | `parent_uuid` → uuid ON DELETE CASCADE |
| `tabular_sections` | ТЧ | Табличные части (колонки — jsonb `column_uuids`) | `parent_uuid` → uuid ON DELETE CASCADE |
| `forms` | Формы | Регистрация форм (V13), `UNIQUE (parent_uuid, uuid)` | `parent_uuid` → uuid ON DELETE CASCADE |
| `form_ext` | Описания форм | Свойства `Form.xml`, модуль формы в `ext`, бинарь в `ext_bin` (V13) | `form_id` → `forms(id)` ON DELETE CASCADE |
| `templates` | Макеты | Регистрация макетов + содержимое `ext` / `ext_bin` / `ext_root_tag` (V13) | `parent_uuid` → uuid ON DELETE CASCADE |
| `bsl_modules` | Модули | Модули объекта/менеджера, `parent_uuid` + `module_type` (V13) | FK на объект отсутствует — очистка явная |

### Поле `external_report.name` может быть из:
- `<Properties><Name>` — приоритет 1
- Имя файла XML (без .xml) — fallback

### Опциональные поля в `external_report` (все NULL по умолчанию):
| Поле | Источник из XML |
|------|----------------|
| `default_form` | `<DefaultForm>` |
| `auxiliary_form` | `<AuxiliaryForm>` |
| `main_data_composition_schema` | `<MainDataCompositionSchema>` |
| `default_settings_form` | `<DefaultSettingsForm>` |
| `auxiliary_settings_form` | `<AuxiliarySettingsForm>` |
| `default_variant_form` | `<DefaultVariantForm>` |
| `variants_storage` | `<VariantsStorage>` |
| `settings_storage` | `<SettingsStorage>` |

## 📖 Ссылки на детальную документацию
- `external_report_strategy.md` — полная схема БД, обновление 10.10.2026
- `external_report_xml_guide.md` — разбор XML, допустимые значения, примеры SQL
