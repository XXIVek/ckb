# Инструкция по использованию XSD-схем и Markdown-спецификаций для XML выгрузки 1С

## Обзор

Создана система XSD-схем и Markdown-документации для формата XML выгрузки метаданных 1С:Предприятие 8.3.
Включает схемы валидации и документацию, загруженные в БД `local_doc`.

## Структура каталогов

```
C:\1C_LLM\ckb\
├── xsd-schemas/                    # XSD-схемы для валидации XML
│   ├── 2.20/                       # Схемы версии формата 2.20
│   │   ├── root-metaobject.xsd     # Корневой MetaDataObject
│   │   ├── objects/                # По типу объекта (31 файл)
│   │   ├── child-objects/          # Дочерние объекты (5 файлов)
│   │   ├── forms/                  # Формы (2 файла)
│   │   ├── templates/              # Макеты (1 файл)
│   │   ├── shared/                 # Общие элементы
│   │   └── extensions/             # Расширения
│   └── examples/                   # Примеры XML
│
├── xsd-docs/                       # Markdown-спецификации
│   ├── overview/                   # Обзорная документация (6 файлов)
│   ├── objects/                    # По типу объекта
│   ├── child-objects/              # Дочерние объекты
│   ├── forms/                      # Формы
│   ├── templates/                  # Макеты
│   └── dsl/                        # DSL форматы
```

## Загрузка в БД документации

| Тип | Файлов создано | Сниппетов загружено |
|-----|---------------|-------------------|
| XSD-схемы (.xsd) | 35 | 11 (ключевые) |
| Markdown-спецификации (.md) | 12 | 12 |
| **Итого** | **47** | **23** |

Категории: `xml-spec` (Markdown), `xsd-schema` (XSD сниппеты).

## Поиск по БД документации

```python
search_docs_tool("ExternalReport", limit=10)       # XSD + Markdown
search_docs_tool("Attribute реквизит", limit=5)     # XSD + Markdown
search_docs_tool("TabularSection табличная часть", limit=5)  # XSD + Markdown
search_docs_tool("xmlns v8 Type", limit=5)          # Пространства имён
search_docs_tool("MetaDataObject корневой элемент", limit=5)  # Обзор
```

## Расширение схемы

1. Создать XSD в `xsd-schemas/2.20/objects/<имя>.xsd`
2. Создать MD в `xsd-docs/objects/<номер>-<имя>.md`
3. Загрузить через add_snippet_tool (groups_id=None)

## Версия формата

Все схемы ориентированы на формат **2.20** (платформа 8.3.24+).