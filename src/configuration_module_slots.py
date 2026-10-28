#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Словарь слотов модулей объектов конфигурации (узел V47, 28.10.2026).

Один источник для четырёх мест — загрузчика (П4), писателя (П3), проверки (П5) и
проб: перечень слотов, граница круга, вывод пути файла модуля из записи индекса
состава и разрешение каталога вида. Переписанные порознь, эти четыре знания
разъезжаются первым же новым видом метаданных — тот же приём, что `CHILD_PROPERTIES`
узла V43, `ROOT_MODULE_KINDS` узла V44, `src/quarantine.py`.

Норматив: `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md` (шаг П2, разделы 2–3),
модель сценария — `docs/config-scenarios/01_configuration.md`.

Чем задаётся круг (раздел 2 плана): колонкой `child_type` таблицы
`configuration_objects`, а НЕ хвостом точечного имени — хвост путает слот с именем
объекта (`Catalog.Товары.TabularSection.Состав` даёт хвост `Состав`). Граница круга
(раздел 3 плана):

* предмет V47 — пять слотов объектов (`ObjectModule`, `ManagerModule`, `RecordSetModule`,
  `ValueManagerModule`, `CommandModule`) плюс слот `Module` видов, не являющихся общими
  модулями (`WebService`, `HTTPService`, `IntegrationService`, `Bot`, `WebSocketClient`)
  = 13 389 записей по четырём загруженным строкам заголовков;
* вне предмета — 6 039 записей `CommonModule.*.Module`: их адресует контракт V46
  (`common_module_sources` держит путь и размер, текста в базе нет — решение D6).
  Записать их вторым местом значило бы завести два места для одного факта и потерять
  границу снятия строк. Граница названа словарём (`scope_of`), а не молчанием: «вне
  предмета узла» и «не нашли» — разные ответы проверки П5.

Путь выводится из имени записи индекса ДО обращения к диску — поэтому он может быть
у каждой строки таблицы (решение Q2: `file_path` обязателен). Каталог вида разрешается
фактом его существования в выгрузке (решение C6): словарь `CATALOG_TO_KIND` узла V33
перевёрнут и даёт основные формы, три пары исключений записаны явно (их закрыл шаг П0:
`_v47x_kinds.py`, разделы A–C — других неразрешённых видов нет), эвристика
множественного числа — последний вариант, а не первый.

Отсутствующий файл — НЕ отказ и НЕ строка в базе (решение Q2: «нет строки» означает
«модуль пуст»). Поэтому `iter_module_rows` называет состояние записи
(`file` / `empty_file` / `indexed_no_file`) и выдаёт спецификацию строки только там,
где файл есть и непустой. Состояния `undecoded` здесь нет: раскодирование — дело П3,
и политика чтения там новая (без усечения, нечитаемый файл = отказ по C5); её не задаёт
`_read_bsl_modules` внешних объектов.

Дешёвые проверки раньше дорогих (следствие правила «ошибка загрузки = полная
перезагрузка», Q4.1): здесь разрешаются путь и существование файла, но содержимое
файла не читается ни при каком состоянии.
"""
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from config_dump_info_parser import CATALOG_TO_KIND
from configuration_root_module_loader import configuration_uuid_from_layout

# ── константы узла V47: один источник для загрузчика, писателя, проверки и проб ────
HEADER_TABLE = "configurations"
INDEX_TABLE = "configuration_objects"
TARGET_TABLE = "bsl_modules"
# Значение `bsl_modules.parent_type` для строк этого узла. Отличие от внешнего контура
# (`external_report`) принципиально: снятие прежних строк идёт парой
# `configuration_uuid` + `parent_type` (приём V46 `remove_common_module_texts`), а общая
# граница с внешним контуром снесла бы чужие строки — этот дефект уже случался и пойман
# проверкой (раздел 10 плана: `_remove_rows` без границы по `parent_type`).
PARENT_TYPE = "configuration_objects"

EXT_DIR = "Ext"
MODULE_FILE_SUFFIX = ".bsl"
MODULE_BIN_SUFFIX = ".bin"
CONFIGURATION_XML = "Configuration.xml"
# Сколько примеров называть текстом (дальше — «ещё N»), как в V43/V44/V46.
MAX_EXAMPLES = 10

# Пять слотов модулей объектов (замер 28.10.2026 по `child_type`, раздел 2 плана).
OBJECT_SLOTS: Tuple[str, ...] = (
    "ObjectModule",
    "ManagerModule",
    "RecordSetModule",
    "ValueManagerModule",
    "CommandModule",
)
# Шестой слот — `Module`. Он НЕ принадлежит одному кругу: замер раздела 3 показывает,
# что 6 039 из 6 096 его записей — общие модули (предмет V46).
MODULE_SLOT = "Module"
# Виды, чей слот `Module` принадлежит V47 (замер 28.10.2026: 57 записей, пять видов).
# Перечень закрытый: слот `Module` по умолчанию вне предмета, а не внутри него.
MODULE_SLOT_KINDS: Tuple[str, ...] = (
    "WebService",
    "HTTPService",
    "IntegrationService",
    "Bot",
    "WebSocketClient",
)
# Виды, чьи модули адресованы другим узлом. Названы явно, потому что «вне предмета» и
# «не нашли» — разные ответы проверки (П5), и молчание о первом читалось бы как ноль.
V46_SLOT_KINDS: Tuple[str, ...] = ("CommonModule",)
# Полный измеряемый перечень шести слотов — для проб и проверки полноты словаря.
SLOTS: Tuple[str, ...] = OBJECT_SLOTS + (MODULE_SLOT,)

# Каталог контейнера владельца: запись `…Command.<Имя>.CommandModule` лежит в
# `<КаталогВида>/<Объект>/Commands/<Команда>/Ext/CommandModule.bsl`. Вложенные владельцы
# среди шести слотов — только команды (замер: 1 110 записей из 19 428, все
# `CommandModule`); у `ManagerModule` вложенных владельцев нет (6 247 записей, все из
# двух сегментов имени). Иные контейнеры (Form, Attribute, TabularSection…) в круг не
# входят: модули форм индексом не моделируются вовсе (узел V40), а слоты вторичных
# объектов вне предмета V47 (решение Q5).
CONTAINER_DIR: Dict[str, str] = {"Command": "Commands"}

# Три пары «вид → каталог выгрузки», подтверждённые фактом существования каталога
# (полный охват `_v47x_kinds.py`, прогон 28.10.2026: без них неразрешаются ровно эти
# три вида, 71 запись). Обратная эвристика V40 даёт плюрал внутри составного слова
# (`Chart` → `Charts`), а не плюрал всего имени, поэтому исключения — часть словаря,
# а не правка эвристики.
KIND_DIR_EXCEPTIONS: Dict[str, str] = {
    "ChartOfAccounts": "ChartsOfAccounts",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "ChartOfCalculationTypes": "ChartsOfCalculationTypes",
}

# Причины отказа вывести путь (шаг П2 плана). Отсутствующего файла среди них нет:
# файла нет — строки нет (Q2), и это состояние записи, а не отказ.
REFUSAL_KIND_UNRESOLVED = "kind_unresolved"
REFUSAL_CONTAINER_UNMAPPED = "container_unmapped"
REFUSAL_NO_DUMP_FOR_CONFIG = "no_dump_for_config"
REFUSALS: Tuple[str, ...] = (
    REFUSAL_KIND_UNRESOLVED,
    REFUSAL_CONTAINER_UNMAPPED,
    REFUSAL_NO_DUMP_FOR_CONFIG,
)
# Дефекты нашего словаря или данных индекса, а не состояние выгрузки. В перечне плана их
# нет именно потому, что это не отказы: свернуть их в `kind_unresolved` значило бы
# спрятать неполноту словаря за отсутствием каталога. Ожидание прогона — нули.
DEFECT_NAME_SHAPE = "name_shape_unexpected"
DEFECT_OWNER_UUID = "owner_uuid_missing"
DEFECTS: Tuple[str, ...] = (DEFECT_NAME_SHAPE, DEFECT_OWNER_UUID)

# Состояния записи индекса по факту выгрузки. Строка в `bsl_modules` появляется только
# при `STATE_FILE` с непустым кодом (решение Q2).
STATE_FILE = "file"
STATE_EMPTY_FILE = "empty_file"
STATE_INDEXED_NO_FILE = "indexed_no_file"
STATES: Tuple[str, ...] = (STATE_FILE, STATE_EMPTY_FILE, STATE_INDEXED_NO_FILE)

# Границы круга, которые возвращает `scope_of`.
SCOPE_V47 = "v47_object_module"
SCOPE_V46 = "v46_common_module"
SCOPE_OUT = "out_of_scope"


def _build_catalog_by_kind() -> Dict[str, Tuple[str, ...]]:
    """Инверсия словаря V33 «каталог выгрузки ↔ вид метаданных»: вид → каталоги.

    Инверсия односторонняя осознанно: словарь не биективен (`AccountRoles` и
    `AccountSettings` дают один вид; `ChartOfCharacteristicTypes` встречается и как
    каталог с тем же именем), поэтому у вида их несколько, а выбирает их существование
    каталога на диске (решение C6).
    """
    out: Dict[str, List[str]] = {}
    for catalog, kind in CATALOG_TO_KIND.items():
        out.setdefault(kind, []).append(catalog)
    return {kind: tuple(sorted(names)) for kind, names in out.items()}


CATALOG_BY_KIND: Dict[str, Tuple[str, ...]] = _build_catalog_by_kind()


# ── граница круга ──────────────────────────────────────────────────────────────────
def scope_of(object_type: str, slot: str) -> str:
    """Кому принадлежит запись индекса с таким видом и слотом.

    `slot` — значение `child_type`, а не хвост имени. Ответов три, и все названы:
    предмет V47, предмет V46 (общие модули — у них свои таблицы и своё снятие строк),
    вне предмета (вторичные объекты, модули форм, неизвестные слоты).
    """
    kind = str(object_type or "")
    slot = str(slot or "")
    if slot in OBJECT_SLOTS:
        return SCOPE_V47
    if slot == MODULE_SLOT:
        if kind in MODULE_SLOT_KINDS:
            return SCOPE_V47
        if kind in V46_SLOT_KINDS:
            return SCOPE_V46
        return SCOPE_OUT
    return SCOPE_OUT


def in_scope(object_type: str, slot: str) -> bool:
    """Принадлежит ли запись кругу узла V47."""
    return scope_of(object_type, slot) == SCOPE_V47


def scope_condition_sql() -> str:
    """Условие WHERE круга узла для таблицы индекса (алиас `o`).

    Один текст на загрузчик, проверку и пробы: граница, записанная в трёх местах,
    разъезжается при первом же новом виде. Параметры — `slots`, `module_slot`,
    `module_kinds` (см. `scope_params`). Вид берётся из колонки `object_type`, а не из
    `split_part(name, '.', 1)`: колонку пишет тот же разбор индекса, и два способа
    разложить одно имя разошлись бы на имени с точкой внутри сегмента.

    Первая ветвь перечисляет ПЯТЬ слотов объектов, а не шесть: слот `Module` входит в
    круг только со второй ветвью, по видам. Иначе в круг попадают 6 039 записей общих
    модулей (предмет V46) — этот дефект поймала проба П2, посчитав 19 428 вместо 13 389.
    """
    return ("(o.child_type = ANY(%(slots)s)\n"
            "         OR (o.child_type = %(module_slot)s\n"
            "             AND o.object_type = ANY(%(module_kinds)s)))")


def scope_params() -> Dict[str, object]:
    """Параметры `scope_condition_sql` (массивы psycopg2 из списков имён)."""
    return {"slots": list(OBJECT_SLOTS), "module_slot": MODULE_SLOT,
            "module_kinds": list(MODULE_SLOT_KINDS)}


def object_group(name: str) -> str:
    """Группа объектов — верхний объект; атом полноты (решение Q4).

    `Catalog.Товары.Command.Провести.CommandModule` и `Catalog.Товары.ObjectModule`
    принадлежат одной группе `Catalog.Товары`: группа загружена — загружена целиком,
    отказ группы останавливает загрузку и называется ею же. Полноту нельзя сворачивать
    к одному числу, поэтому группа выводится словарём, а не догадкой читающего.
    """
    parts = str(name or "").split(".")
    if len(parts) < 2:
        return str(name or "")
    return ".".join(parts[:2])


# ── разрешение каталога вида ───────────────────────────────────────────────────────
def kind_dir_candidates(kind: str) -> List[str]:
    """Варианты каталога вида: подтверждения раньше эвристики.

    Порядок: явное подтверждённое исключение → каталоги из перевёрнутого словаря V33 →
    обратная эвристика множественного числа. Принимающий шаг — существование каталога
    (решение C6), поэтому список не обязан быть однозначным; он обязан быть полным
    настолько, чтобы ни одна запись не осталась `kind_unresolved` без причины.
    """
    kind = str(kind or "")
    if not kind:
        return []
    out: List[str] = []

    def add(value: str) -> None:
        if value and value not in out:
            out.append(value)

    add(KIND_DIR_EXCEPTIONS.get(kind, ""))
    for catalog in CATALOG_BY_KIND.get(kind, ()):
        add(catalog)
    # Эвристика V40 — последний вариант: она рождает формы, которых в выгрузке нет
    # (`Charts` вместо `ChartsOfAccounts`), и ошиблась бы молча, стой она первой.
    forms = {kind, kind + "s", kind + "es"}
    for i in range(len(kind)):
        if kind[i] == "s":
            forms.add(kind[:i] + kind[i + 1:] + "s")
    if kind.endswith("y"):
        forms.add(kind[:-1] + "ies")
    for suffix in ("on", "um", "us"):
        if kind.endswith(suffix):
            forms.add(kind[:-len(suffix)] + "a")
    for form in sorted(forms, key=len, reverse=True):
        add(form)
    return out


def resolve_kind_dir(dump_dir, kind: str, cache: Optional[Dict] = None) -> str:
    """Каталог вида, который существует в этой выгрузке ('' — если такого нет).

    `cache` — словарь {(каталог выгрузки, вид): каталог вида}. Обход идёт по десяткам
    тысяч записей при ограниченном числе видов, и каждый вызов не должен перечитывать
    каталог выгрузки.
    """
    key = (str(dump_dir), str(kind or ""))
    if cache is not None and key in cache:
        return cache[key]
    result = ""
    for candidate in kind_dir_candidates(kind):
        if (Path(dump_dir) / candidate).is_dir():
            result = candidate
            break
    if cache is not None:
        cache[key] = result
    return result


# ── вывод пути файла модуля ────────────────────────────────────────────────────────
def derive_module_path(record: Dict, dump_dir, cache: Optional[Dict] = None) -> Dict:
    """Вывести путь файла модуля из записи индекса состава.

    `record` — строка `configuration_objects`: нужны `name` и колонки, которые пишет
    загрузчик индекса (`object_type`, `object_name`, `child_type`, `parent_name`).
    `name` остаётся источником цепочки и группы: колонки — производные от него, и
    расхождение колонки с именем называется дефектом, а не разрешается молча.

    Возвращает словарь с ключами:
      `ok` — выведен ли путь;
      `rel_path` — путь относительно корня выгрузки, разделители '/' (тот же формат,
        что `bsl_modules.file_path` внешнего контура и `common_module_sources.file_path`
        узла V46: два места с одним смыслом разошлись бы в проверке П5);
      `abs_path` — абсолютный путь (проверка существования, чтение в П3);
      `bin_path` — путь машинного кода рядом (открытая позиция O1: проверка обязана
        назвать такие записи отдельной строкой, а не молчать о них);
      `reason` — причина отказа (одна из `REFUSALS`) или дефекта (одна из `DEFECTS`);
      `slot`, `kind`, `object_name`, `owner_name`, `owner_type`, `container_type`,
      `container_name`, `group` — состав, из которого путь собран (он же нужен писателю
      для `object_type`/`object_name` и проверке для полноты по группам).
    """
    name = str(record.get("name") or "")
    kind = str(record.get("object_type") or "")
    slot = str(record.get("child_type") or "")
    out = {
        "ok": False, "reason": None, "name": name,
        "slot": slot, "kind": kind,
        "object_name": str(record.get("object_name") or ""),
        "owner_name": str(record.get("parent_name") or ""),
        "owner_type": "", "container_type": "", "container_name": "",
        "rel_path": "", "abs_path": "", "bin_path": "",
        "group": object_group(name),
    }
    if not name or not kind or not slot:
        out["reason"] = DEFECT_NAME_SHAPE
        return out
    if slot not in SLOTS:
        # Слот вне словаря — неполнота словаря, а не чужой модуль конкретной выгрузки.
        out["reason"] = DEFECT_NAME_SHAPE
        return out

    # Цепочка владельца — из `parent_name`, который даёт правило D3 индекса (родитель
    # существует в том же индексе для всех некорневых записей). Длина цепочки 2 —
    # модуль объекта верхнего уровня; 4 — модуль вложенного владельца (команды).
    chain = [part for part in out["owner_name"].split(".") if part]
    if len(chain) == 2:
        if chain[0] != kind or chain[1] != out["object_name"]:
            # Колонки не сошлись с именем: строку записал не этот разбор либо имя
            # содержит точку внутри сегмента. Догадываться нельзя — это дефект данных.
            out["reason"] = DEFECT_NAME_SHAPE
            return out
        out["owner_type"] = chain[0]
        parts = [chain[1]]
    elif len(chain) == 4:
        if chain[0] != kind or chain[1] != out["object_name"]:
            out["reason"] = DEFECT_NAME_SHAPE
            return out
        container_type = chain[2]
        container_dir = CONTAINER_DIR.get(container_type, "")
        out["container_type"] = container_type
        out["container_name"] = chain[3]
        out["owner_name"] = ".".join(chain)
        if not container_dir:
            out["owner_type"] = container_type
            out["reason"] = REFUSAL_CONTAINER_UNMAPPED
            return out
        out["owner_type"] = container_type
        parts = [chain[1], container_dir, chain[3]]
    else:
        out["reason"] = DEFECT_NAME_SHAPE
        return out

    kind_dir = resolve_kind_dir(dump_dir, kind, cache)
    if not kind_dir:
        out["reason"] = REFUSAL_KIND_UNRESOLVED
        return out
    segments = [kind_dir] + parts + [EXT_DIR, slot + MODULE_FILE_SUFFIX]
    out["rel_path"] = "/".join(segments)
    absolute = Path(dump_dir).joinpath(*segments)
    out["abs_path"] = str(absolute)
    out["bin_path"] = str(absolute.with_name(slot + MODULE_BIN_SUFFIX))
    out["ok"] = True
    out["reason"] = None
    return out


# ── разрешение каталога выгрузки по строке заголовка ──────────────────────────────
def configuration_root_uuid(dump_dir) -> str:
    """uuid корня из `Configuration.xml` каталога выгрузки ('' — если не прочитан).

    Читается тот же разбор, что у загрузчика (`configuration_uuid_from_layout`, V44), а
    не своё регулярное выражение: два чтения одного файла разошлись бы при первом же
    отличии кодировки или формы файла.
    """
    info = configuration_uuid_from_layout(str(dump_dir))
    return str(info.get("uuid") or "").strip().lower()


def resolve_dump_dir(configuration_uuid: str, dump_root) -> Dict:
    """Каталог выгрузки по uuid строки заголовка (решение C5 плана).

    Имя каталога выбирает экспортирующий (`BP3`), а `configurations.name` — имя из
    выгрузки («БухгалтерияПредприятия»): совпадения имени нет ни у одной из четырёх
    загруженных строк, поэтому сопоставление идёт только по uuid корня
    `Configuration.xml`. Провенанса строк конфигурации в схеме нет (решение D-C), так
    что другого источника нет вовсе — отсюда и причина отказа `no_dump_for_config`.

    Возвращает `{"path": …, "matches": […]}` либо `{"reason": no_dump_for_config,
    "scanned": N, "known_uuids": […]}`. Несколько каталогов с тем же uuid — не ошибка и
    не тай-брейк: `matches` называет их все, `path` — первый по имени каталога.
    """
    wanted = str(configuration_uuid or "").strip().lower()
    root = Path(str(dump_root))
    if not wanted or not root.is_dir():
        return {"reason": REFUSAL_NO_DUMP_FOR_CONFIG, "scanned": 0, "known_uuids": []}
    matches: List[str] = []
    seen: List[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        found = configuration_root_uuid(entry)
        if not found:
            continue
        seen.append(found)
        if found == wanted:
            matches.append(str(entry))
    if matches:
        return {"path": matches[0], "matches": matches}
    return {"reason": REFUSAL_NO_DUMP_FOR_CONFIG, "scanned": len(seen),
            "known_uuids": sorted(set(seen))[:MAX_EXAMPLES]}


# ── чтение записей индекса и обход модулей ────────────────────────────────────────
INDEX_RECORD_SQL = """
    SELECT o.id, o.name, o.object_type, o.object_name, o.child_type, o.parent_name,
           o.depth, o.object_id, o.uuid::text AS record_uuid,
           p.uuid::text AS owner_uuid, c.uuid::text AS configuration_uuid,
           c.name AS configuration_name
      FROM {index} o
      JOIN {header} c ON c.id = o.configuration_id
      LEFT JOIN {index} p
             ON p.configuration_id = o.configuration_id AND p.name = o.parent_name
     WHERE c.uuid = %(configuration_uuid)s::uuid
       AND {scope}
     ORDER BY o.name
""".format(index=INDEX_TABLE, header=HEADER_TABLE, scope=scope_condition_sql())


def configuration_header(cur, configuration_uuid: str) -> Optional[Dict]:
    """Строка заголовка конфигурации по uuid (None — если её нет).

    Отдельная функция нужна затем, что отсутствующая строка заголовка — не пустой
    результат обхода: загрузчик модулей требует уже загруженную конфигурацию
    (прецедент V44/V46: внешнего ключа в схеме нет осознанно), и «нет такой
    конфигурации» обязано называться причиной, а не нулём строк.
    """
    cur.execute(
        "SELECT id, uuid::text AS uuid, name FROM %s WHERE uuid = %%s::uuid"
        % HEADER_TABLE, (str(configuration_uuid or ""),))
    row = cur.fetchone()
    if not row:
        return None
    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))


def iter_index_records(cur, configuration_uuid: str) -> Iterable[Dict]:
    """Записи индекса круга узла для одной строки заголовка (словари).

    Источник — таблица `configuration_objects`, а не повторный разбор
    `ConfigDumpInfo.xml` (правило V43/V44: двух независимых чтений одного файла быть не
    может). uuid владельца берётся LEFT JOIN по имени родителя в той же конфигурации:
    записи модулей uuid не имеют (правило D2 индекса — колонка заполняется только у
    канонических идентификаторов), владелец — имеет.
    """
    params = scope_params()
    params["configuration_uuid"] = str(configuration_uuid or "")
    cur.execute(INDEX_RECORD_SQL, params)
    columns = [desc[0] for desc in cur.description]
    for values in cur.fetchall():
        yield dict(zip(columns, values))


def module_row_spec(record: Dict, derived: Dict, configuration_uuid: str) -> Dict:
    """Спецификация строки `bsl_modules` без кода (код добавляет П3).

    Форма — та же, что у `_read_bsl_modules` внешнего контура (указание оператора:
    адаптировать существующую запись, а не писать заново), с двумя изменениями из шага
    П3 плана: `parent_type` = `configuration_objects` и добавлена `configuration_uuid`.

    `object_type`/`object_name` берутся у самой записи индекса — это вид и имя ВЕРХНЕГО
    объекта конфигурации, которые пишет разбор индекса (у записи модуля команды они те
    же, что у каталога: `Catalog.Товары.Command.Провести.CommandModule` даёт
    `Catalog`/`Товары`). Отдельной колонкой прямой владелец не выводится: он уже указан
    `parent_uuid` (для модуля команды — запись команды), а имя команды видно из
    `file_path`. Выведенный вид владельца колонками не становится по трём причинам:
    он расходится с колонками той же записи индекса (проверка П5 сверял бы строку с
    выводом, а не с источником); он расходится с узлом V46, который пишет в эти колонки
    вид метаданных и имя владельца (`COMMON_MODULE_OBJECT_TYPE`); и он создал бы третье
    значение одного понятия в одной таблице (внешний контур пишет туда слот модуля).
    Верхний объект остаётся в `derived["group"]` — атоме полноты (Q4).

    `code_size` здесь не вычисляется: он равен числу символов раскодированного текста и
    относится к чтению (П3), а не к выводу пути. `report_id` остаётся None: колонка
    существует для совместимости с запросами внешнего контура (узел V22), строки
    конфигурации к ней не обращаются.
    """
    return {
        "configuration_uuid": str(configuration_uuid or ""),
        "parent_uuid": str(record.get("owner_uuid") or ""),
        "parent_type": PARENT_TYPE,
        "module_name": derived["slot"],
        "module_type": derived["slot"],
        "file_path": derived["rel_path"],
        "object_type": str(record.get("object_type") or ""),
        "object_name": str(record.get("object_name") or ""),
        "report_id": None,
        "truncated": False,
    }


def iter_module_rows(cur, configuration_uuid: str, dump_root,
                     cache: Optional[Dict] = None,
                     dump_dir: Optional[str] = None) -> Iterable[Dict]:
    """Обход модулей круга узла: записи индекса → состояние и спецификация строки.

    Каталог выгрузки берётся одним из двух способов: `dump_dir` назван вызывающему
    известен (загрузчик П4 открыл `source_path` сам — сканировать каталог выгрузок и
    читать `Configuration.xml` каждого незачем), иначе его ищет `resolve_dump_dir` по
    uuid корня. Совпадение uuid с заголовком проверяет вызывающий (писатель называет
    для этого причину `dump_dir_mismatch`), а не обход: каталог здесь назван тем, кто
    его открыл, и второй проверки от этого меньше не становится.

    Каждый словарь результата содержит:
      `state` — `file` / `empty_file` / `indexed_no_file` либо None (был отказ);
      `refusal` — причину отказа (одну из `REFUSALS`) или дефекта (одну из `DEFECTS`);
      `row` — спецификацию строки писателя (П3) только при `state == file`;
      `derived` — вывод пути и состав владельца (нет только при дефекте разбора имени);
      `group` — группа объектов (атом полноты, Q4);
      `size_bytes`, `bin_side` — факты диска: размер файла и наличие машинного кода
      рядом (открытая позиция O1: проверка обязана назвать такие записи отдельной
      строкой, а не молчать о них).

    Файл не читается ни при каком состоянии: сначала дешёвые проверки (путь,
    существование), дорогое чтение — в П3, где нечитаемый файл является отказом стадии
    по правилу C5, а не потерянной строкой.
    """
    cache = {} if cache is None else cache
    if dump_dir:
        resolved = {"path": str(dump_dir)}
    else:
        resolved = resolve_dump_dir(configuration_uuid, dump_root)
    resolved_dir = resolved.get("path", "")
    for record in iter_index_records(cur, configuration_uuid):
        name = str(record.get("name") or "")
        base = {
            "name": name, "group": object_group(name),
            "slot": record.get("child_type"), "kind": record.get("object_type"),
            "object_name": record.get("object_name"),
            "index_id": record.get("id"), "object_id": record.get("object_id"),
            "configuration_name": record.get("configuration_name"),
            "state": None, "refusal": None, "row": None, "derived": None,
            "size_bytes": None, "bin_side": False,
        }
        if not resolved_dir:
            base["refusal"] = REFUSAL_NO_DUMP_FOR_CONFIG
            yield base
            continue
        derived = derive_module_path(record, resolved_dir, cache)
        base["derived"] = derived
        if not derived["ok"]:
            base["refusal"] = derived["reason"]
            yield base
            continue
        absolute = Path(derived["abs_path"])
        exists = absolute.is_file()
        base["bin_side"] = (not exists) and Path(derived["bin_path"]).is_file()
        if not exists:
            base["state"] = STATE_INDEXED_NO_FILE
            yield base
            continue
        try:
            base["size_bytes"] = absolute.stat().st_size
        except OSError:
            base["size_bytes"] = None
        if not base["size_bytes"]:
            # Файл есть и он пуст: строки нет (Q2), но состояние названо — иначе
            # «пустой модуль» и «модуля нет» стали бы одним ответом.
            base["state"] = STATE_EMPTY_FILE
            yield base
            continue
        if not record.get("owner_uuid"):
            # Родителю не на что указать: `parent_uuid` обязателен (миграция V47). Это
            # дефект данных индекса, а не состояние выгрузки, и он не превращается в
            # «модуль пуст»: пустой была бы строка, а строки здесь нет по чужой причине.
            base["refusal"] = DEFECT_OWNER_UUID
            yield base
            continue
        base["state"] = STATE_FILE
        base["row"] = module_row_spec(record, derived, configuration_uuid)
        yield base






