# 1C Form Tools

Инструменты для редактирования модулей **обычных форм** внешних обработок 1С через Git и внешние редакторы (Claude Code, VS Code и др.)

## Проблема

При сохранении обработки из конфигуратора в XML:

| Тип формы | Модуль | Можно редактировать извне? |
|-----------|--------|---------------------------|
| Управляемая | `Module.bsl` (отдельный файл) | Да |
| Обычная | Внутри `Form.bin` (бинарник) | Нет |

## Решение

```
  Конфигуратор                    Git-репозиторий                  Редактор
 ┌───────────┐                   ┌─────────────────┐            ┌───────────┐
 │ Сохранить │  ──── XML ────►  │ Form.bin        │            │           │
 │ как XML   │                   │                 │            │ Claude    │
 └───────────┘                   │  extract ▼      │            │ Code      │
                                 │                 │            │           │
                                 │ Form.bin        │   edit     │ VS Code   │
                                 │ Module.bsl ◄────┼────────────┤           │
                                 │                 │            │ ...       │
                                 │  git commit     │            └───────────┘
                                 │  (auto-pack ▲)  │
 ┌───────────┐                   │                 │
 │ Открыть   │  ◄─── XML ─────  │ Form.bin ✓      │
 │ из XML    │                   └─────────────────┘
 └───────────┘
```

Три Python-скрипта + Git pre-commit hook:

- **extract_form_modules.py** — распаковывает `Form.bin` через v8unpack, извлекает модуль в `Module.bsl`
- **pack_form_modules.py** — упаковывает `Module.bsl` обратно в `Form.bin` через v8unpack
- **epf_module_tools.py** — извлекает модуль объекта и модули всех обычных форм напрямую из `.epf`, когда XML-выгрузки нет (см. [ниже](#работа-напрямую-с-epf-без-xml-выгрузки))
- **pre-commit hook** — автоматически вызывает pack при коммите

## Лицензия

[MIT](LICENSE)

## Требования

- Python 3.10+
- Git

### Зависимости

| Пакет | Назначение | Лицензия |
|-------|-----------|----------|
| [v8unpack](https://github.com/saby-integration/v8unpack) | Распаковка/сборка контейнеров 1С (Form.bin) | MIT |
| [tqdm](https://github.com/tqdm/tqdm) | Прогресс-бары (транзитивная зависимость v8unpack) | MIT/MPL |

Установка:

```
pip install v8unpack
```

## Установка в свой проект

Скопировать скрипты и hook в целевой репозиторий:

```cmd
mkdir <ваш-проект>\.1c-tools
copy extract_form_modules.py <ваш-проект>\.1c-tools\
copy pack_form_modules.py    <ваш-проект>\.1c-tools\
copy pre-commit              <ваш-проект>\.git\hooks\pre-commit
```

Для корректной работы хука с кириллическими путями:

```cmd
cd <ваш-проект>
git config core.quotePath false
```

## Рабочий процесс

### 1. Сохранение из конфигуратора

В конфигураторе: **Файл -> Сохранить как...** -> выбрать формат **Файлы XML** -> сохранить в каталог репозитория (например `src/`)

### 2. Извлечение модулей обычных форм

```cmd
python .1c-tools\extract_form_modules.py src --force
```

Результат — рядом с каждым `Form.bin` появится `Module.bsl`:

```
src/
├── Ext/
│   └── ObjectModule.bsl            <- модуль объекта (уже .bsl)
└── Forms/
    ├── УправляемаяФорма/
    │   └── Ext/Form/Module.bsl     <- уже есть от платформы
    └── ОбычнаяФорма/
        └── Ext/
            ├── Form.bin            <- бинарные данные формы
            └── Module.bsl          <- ИЗВЛЕЧЁННЫЙ модуль
```

### 3. Редактирование

Любым текстовым редактором — VS Code, Claude Code и т.д.

### 4. Коммит

```bash
git add -A
git commit -m "Рефакторинг основной формы"
```

Pre-commit hook автоматически:
1. Обнаружит изменённые `Module.bsl` рядом с `Form.bin`
2. Упакует модуль обратно в `Form.bin`
3. Добавит обновлённый `Form.bin` в коммит

### 5. Загрузка в конфигуратор

В конфигураторе: **Файл -> Открыть...** -> выбрать XML файл из каталога `src/`

## Работа напрямую с .epf (без XML-выгрузки)

Основной рабочий процесс выше требует XML-выгрузку из конфигуратора. Если её нет —
есть только сам файл внешней обработки — модули можно править прямо в `.epf`
скриптом **epf_module_tools.py**. Извлекаются **модуль объекта** и модули **всех
обычных форм**; бинарник и тексты хранятся раздельно — путь к каталогу исходников
передаётся параметром:

```cmd
:: 1. Извлечь модули в каталог исходников
python epf_module_tools.py extract bin\Обработка.epf src\Обработка
```

Результат — каталог исходников рядом НЕ с бинарником:

```
bin/
└── Обработка.epf               <- собранный бинарник (после pack готов к открытию в 1С)
src/
└── Обработка/
    ├── ObjectModule.bsl        <- модуль объекта (если он не пуст)
    ├── Форма.Module.bsl        <- модуль обычной формы «Форма»
    └── ДругаяФорма.Module.bsl  <- ...по файлу на каждую форму
```

```cmd
:: 2. Отредактировать .bsl любым редактором

:: 3. Упаковать обратно (рядом с .epf останется бэкап .epf.bak)
python epf_module_tools.py pack bin\Обработка.epf src\Обработка
```

При упаковке соответствие определяется по именам файлов: `ObjectModule.bsl` и
`<ИмяФормы>.Module.bsl` (имена форм скрипт берёт из метаданных внутри `.epf`).
Файлы, которым не нашлось модуля в контейнере, пропускаются с предупреждением.

Ограничения:

- правятся только тексты модулей — разметку форм, реквизиты и т.п. по-прежнему
  редактируют в конфигураторе;
- если модуль объекта в `.epf` пуст, 1С не хранит его в контейнере — упаковать
  `ObjectModule.bsl` в такую обработку нельзя (сначала создайте пустой модуль
  объекта в конфигураторе и пересохраните `.epf`);
- pre-commit hook на `.epf` не распространяется (он ищет пары `Form.bin` + `Module.bsl`) —
  после правки `.bsl` упаковку запускать вручную.

## Параметры скриптов

### extract_form_modules.py

```
python extract_form_modules.py <каталог> [--force] [--verbose]

  каталог   Каталог с XML-выгрузкой обработки
  --force   Перезаписать существующие Module.bsl
  --verbose Подробный вывод
```

### pack_form_modules.py

```
python pack_form_modules.py <каталог> [--no-backup] [--verbose]

  каталог     Каталог с XML-выгрузкой обработки
  --no-backup Не создавать Form.bin.bak
  --verbose   Подробный вывод
```

### epf_module_tools.py

```
python epf_module_tools.py <команда> <файл.epf> <каталог> [--force] [--no-backup]

  команда     extract — извлечь модули из .epf в каталог исходников
              pack    — упаковать .bsl из каталога исходников обратно в .epf
  каталог     Каталог исходников: ObjectModule.bsl, <ИмяФормы>.Module.bsl
  --force     extract: перезаписать существующие .bsl
  --no-backup pack: не создавать .epf.bak
```

## Интеграция с Claude Code

В каталоге `.claude/skills/` находятся скиллы для Claude Code:

- `/1c-form-extract` — извлечение модулей
- `/1c-form-pack` — упаковка модулей

Для подключения скопируйте каталог `.claude/skills/` в свой проект.

## Технические детали

### Формат Form.bin

`Form.bin` — контейнер 1С, содержащий два файла:
- **form** — бинарные данные разметки формы (элементы, свойства, привязки)
- **module** — текст модуля формы в UTF-8 с BOM

### Как работают скрипты

Все скрипты используют `v8unpack` (`container_reader` / `container_writer`):

1. **Extract**: `container_reader.extract(Form.bin, temp_dir)` -> находит файл `module` -> сохраняет как `Module.bsl`
2. **Pack**: `container_reader.extract(Form.bin, temp_dir)` -> заменяет `module` содержимым `Module.bsl` -> `container_writer.build(temp_dir, Form.bin)`

Данные внутри `Form.bin` хранятся без сжатия (`deflate=False`, `nested=True`).

### Формат .epf (epf_module_tools.py)

`.epf` — тоже контейнер 1С, но данные в нём **сжаты deflate**. Внутри (соответствие
имён — из `v8unpack/MetaDataObject/DataProcessor.py`):

- `root` — указатель на корневой GUID обработки;
- `<корневой-guid>` — метаданные обработки, `<корневой-guid>.0` — **текст модуля
  объекта** (если модуль пуст — файла нет);
- `<guid-формы>` — метаданные формы (в т.ч. её имя), `<guid-формы>.0` — вложенный
  контейнер обычной формы (внутри — те же `form` и `module`, что и в `Form.bin`).

Поэтому вместо прямого `build` используется полный конвейер v8unpack, как при сборке
`.epf` самой библиотекой:

1. **Extract**: `container_reader.extract(.epf, temp_dir, deflate=True, recursive=True)`
2. **Pack**: замена `module`/`<guid>.0` -> `container_writer.compress_and_build(src, packed)` (дожатие
   deflate, вложенные каталоги собираются в контейнеры) -> `container_writer.build(packed, .epf, nested=True)`

## Структура проекта

```
1c-form-tools/
├── extract_form_modules.py       <- извлечение Module.bsl из Form.bin
├── pack_form_modules.py          <- упаковка Module.bsl обратно в Form.bin
├── epf_module_tools.py           <- extract/pack модулей (объекта и форм) напрямую из .epf
├── pre-commit                    <- Git hook (авто-pack при коммите)
├── .claude/skills/               <- скиллы для Claude Code
│   ├── 1c-form-extract/SKILL.md
│   └── 1c-form-pack/SKILL.md
└── README.md
```
