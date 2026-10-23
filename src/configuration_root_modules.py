#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Модули предопределённых программ корня конфигурации (узел V44, 22.10.2026).

Слой загрузки конфигурации (первый): свойства заголовка (V42) + перечни имён состава (V43) +
ЭТИ ЧЕТЫРЕ МОДУЛЯ. Модули объектов (общие модули, `ObjectModule`, `ManagerModule`,
`CommandModule`, модули форм) в этот узел НЕ входят — это второй и третий слой загрузки
конфигурации; там и вырабатывается стратегия загрузки модулей по видам объектов.

Основание — файл оператора `C:\\1C_LLM\\Анализ модулей конфигурации.txt` (22.10.2026), п. 1:
«Конфигурация — максимум 4 модуля: модуль приложения (он же модуль управляемого приложения
в режиме простых форм), модуль сеанса, модуль внешнего соединения, модуль простого приложения»,
и требование «связь по UUID конфигурации». Отдельная таблица на каждый вид модуля — решение
оператора 21.10.2026 (норматив `docs/config-scenarios/01_configuration.md`, группа C): такие
модули существуют в единственном экземпляре на конфигурацию и не вызываются по имени объекта,
поэтому их нельзя класть ни в `bsl_modules` (зона модулей внешнего объекта), ни в одну таблицу
с модулями объектов.

Ключ связи — `configuration_uuid`, а НЕ `configuration_id` (решение оператора 22.10.2026):
`force=True` и будущая версионность заголовка меняют `id`, а `uuid` из `Configuration.xml`
остаётся тем же. Ссылка на `id` теряла бы модули при каждой перезагрузке заголовка. Внешнего
ключа в схеме нет осознанно — по той же причине, что у `external_report.configuration_id`
(узел V20.1): ключ блокировал бы пересоздание и версионирование строки заголовка, а
целостность ведёт приложение.

Один словарь на четыре места (модуль, писатели, загрузчик, SQL) — по той же причине, по
которой фильтр карантина живёт в `src/quarantine.py`, а имена 48 перечней —
в `src/configuration_child_properties.py`: четыре имени, переписанных порознь, разъезжаются.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── константы узла V44: один источник для модуля, писателей, загрузчика и SQL ──────
EXT_DIR = "Ext"
# Сколько примеров называть текстом предупреждения (дальше — «ещё N»).
MAX_EXAMPLES = 10

# Состояния строки модуля (CHECK `<table>_code_state_check`). Пустой код допустим только
# там, где текста нет по факту выгрузки (граница N2); состояние `file` обязывает непустой код.
STATE_FILE = "file"
STATE_EMPTY_FILE = "empty_file"
STATE_INDEXED_NO_FILE = "indexed_no_file"
STATE_UNDECODED = "undecoded"
CODE_STATES: Tuple[str, ...] = (
    STATE_FILE, STATE_EMPTY_FILE, STATE_INDEXED_NO_FILE, STATE_UNDECODED,
)
# Состояния, в которых колонка `code` остаётся NULL (CHECK пары «код ↔ состояние»).
CODE_ABSENT_STATES: Tuple[str, ...] = (STATE_EMPTY_FILE, STATE_INDEXED_NO_FILE,
                                       STATE_UNDECODED)
# Состояние «модуля нет вовсе»: ни файла в `Ext/`, ни записи индекса состава. Строки в
# таблице при этом нет (N2), поэтому состояния в CHECK и быть не может — колонка принимает
# только CODE_STATES. `read_root_module_file` назвать его не в праве: он не знает про индекс
# состава, а «файла нет» становится состоянием строки `indexed_no_file` (пустой модуль
# платформы) только когда индекс его подтверждает. Без отдельного состояния отсутствующий
# модуль попадал бы в счётчик `indexed_no_file` — и «платформа ждёт пустой модуль»
# отличалось бы от «такого модуля в конфигурации нет» только догадкой читающего.
STATE_ABSENT = "absent"
# Словарь состояний отчёта: четыре состояния строки плюс «модуля нет». Один перечень на
# загрузчик, карточку инструмента и проверку — по той же причине, по которой имена четырёх
# таблиц знает только этот модуль: перечень, переписанный в вызывающем коде, разъезжается.
REPORT_STATES: Tuple[str, ...] = CODE_STATES + (STATE_ABSENT,)

# Границы узла (замер 22.10.2026: семь XML-выгрузок + живой индекс состава четырёх
# загруженных конфигураций). Они же — основания для CHECK и для проверки
# `tools/check_v44_configuration_root_modules.py`.
#   N1. Файл лежит ТОЛЬКО в `<каталог выгрузки>/Ext/<Имя>.bsl` (словарь V40, группа C:
#       предопределённые модули корня моделируются индексом записями
#       `Configuration.<Имя>.<Слот>` 1:1 с файлами). Другого расположения у них нет.
#   N2. Состояния строки различимы: файл с текстом, пустой файл, «индекс перечисляет, файла
#       нет», «файл не раскодирован». Модуля нет вовсе — строки в таблице нет: «нет модуля» и
#       «модуль пустой» — разные факты, одна строка с пустым кодом их бы слила (тот же
#       контракт, что «манифеста нет» / «манифест пуст» у V19 и `===EMPTY` у V39/V42).
#       Состояние «модуля нет» (`absent`) — состояние ОТЧЁТА, а не строки: колонка принимает
#       только CODE_STATES, CHECK его не принимает, поэтому он и не входит в них (см.
#       STATE_ABSENT). Различает его не читатель файла, а сопоставление с индексом состава.
#   N3. Текст нормализуется как модули форм (`src/external_subdir_parser.py`): BOM снимается
#       (`utf-8-sig`), обрамляющая пустота снимается. Счётчики считаются по нормализованному
#       тексту, поэтому сходятся с `length(code)`/`octet_length(code)` в проверке.
#   N4. Порога усечения нет (решение оператора 22.10.2026): код сохраняется целиком, объём
#       называется колонками размеров, а не обрезается молча.
#   N5. Одна строка на конфигурацию и вид модуля — уникальность по `configuration_uuid`.
#       Это и есть «по одной строке на конфигурацию, ключ — конфигурация» из норматива.
#   N6. Ссылка на индекс состава сохраняется (`index_object_id` — запись
#       `Configuration.<Имя>.<Слот>`), поэтому проверка сверяет три контура: индекс ↔ файл ↔
#       строку БД. Индекс читается из таблицы `configuration_objects`, а не парсится
#       `ConfigDumpInfo.xml` повторно: второй источник того же факта разошёлся бы с первым
#       (правило V43).

# (вид, имя модуля, имя файла в Ext/, слот индекса состава, таблица, русское название).
# Имена модулей и слотов — словарь V40 (`_v40_slots_table.py`, вид `Configuration`); имена
# файлов — замер семи выгрузок 22.10.2026. Порядок — по пунктам 1.1–1.4 файла оператора.
ROOT_MODULE_KINDS: Tuple[Tuple[str, str, str, str, str, str], ...] = (
    ("session", "SessionModule", "SessionModule.bsl", "SessionModule",
     "bsl_modules_session", "Модуль сеанса"),
    ("managed_application", "ManagedApplicationModule", "ManagedApplicationModule.bsl",
     "ManagedApplicationModule", "bsl_modules_managed_application",
     "Модуль приложения (управляемого; он же модуль приложения в режиме простых форм)"),
    ("ordinary_application", "OrdinaryApplicationModule", "OrdinaryApplicationModule.bsl",
     "OrdinaryApplicationModule", "bsl_modules_ordinary_application",
     "Модуль простого приложения (конфигурации на обычных формах)"),
    ("external_connection", "ExternalConnectionModule", "ExternalConnectionModule.bsl",
     "ExternalConnectionModule", "bsl_modules_external_connection",
     "Модуль внешнего соединения"),
)
ROOT_MODULE_COUNT = len(ROOT_MODULE_KINDS)

KINDS: Tuple[str, ...] = tuple(item[0] for item in ROOT_MODULE_KINDS)
MODULE_NAMES: Tuple[str, ...] = tuple(item[1] for item in ROOT_MODULE_KINDS)
INDEX_SLOTS: Tuple[str, ...] = tuple(item[3] for item in ROOT_MODULE_KINDS)
TABLES: Tuple[str, ...] = tuple(item[4] for item in ROOT_MODULE_KINDS)

KIND_BY_SLOT: Dict[str, str] = {item[3]: item[0] for item in ROOT_MODULE_KINDS}
KIND_BY_MODULE: Dict[str, str] = {item[1]: item[0] for item in ROOT_MODULE_KINDS}
TABLE_BY_KIND: Dict[str, str] = {item[0]: item[4] for item in ROOT_MODULE_KINDS}
FILE_BY_KIND: Dict[str, str] = {item[0]: item[2] for item in ROOT_MODULE_KINDS}
MODULE_BY_KIND: Dict[str, str] = {item[0]: item[1] for item in ROOT_MODULE_KINDS}
TITLE_BY_KIND: Dict[str, str] = {item[0]: item[5] for item in ROOT_MODULE_KINDS}
# Файлы `Ext/*.bsl`, которых нет среди четырёх предопределённых модулей: словарь неполон
# либо в каталоге лежит модуль чужого вида. Называется поимённо, а не сворачивается в ноль
# (тот же механизм, что `UNKNOWN_PROPERTY` у разбора заголовка V42).
KNOWN_EXT_BSL = {item[2].lower(): item[0] for item in ROOT_MODULE_KINDS}


def root_module_tables() -> Tuple[str, ...]:
    """Четыре таблицы узла (для явной очистки и для проверки схемы)."""
    return TABLES


def table_for_kind(kind: str) -> str:
    """Таблица вида модуля; неизвестный вид — ошибка программы, а не молчаливый None."""
    try:
        return TABLE_BY_KIND[kind]
    except KeyError:
        raise ValueError(
            f"неизвестный вид предопределённого модуля корня: {kind!r}; словарь знает "
            f"только {', '.join(KINDS)}"
        ) from None



def read_root_module_file(source_dir, kind: str) -> Dict:
    """Прочитать файл модуля из `Ext/` и назвать его состояние (N1, N2, N3).

    Возвращает dict с ключами `state`, `text`, `code_chars`, `code_bytes`, `source_path`,
    `reason`. Исключений не бросает: отсутствующий файл — штатное состояние выгрузки, а не
    сбой программы (тот же контракт, что у декодера обычных форм V15).
    """
    file_name = FILE_BY_KIND[kind]
    path = Path(source_dir) / EXT_DIR / file_name
    relative = f"{EXT_DIR}/{file_name}"
    if not path.is_file():
        return {"state": STATE_INDEXED_NO_FILE, "text": None, "code_chars": None,
                "code_bytes": None, "source_path": None, "reason": None}
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        # Расшифровать «как получилось» — значит выдать мусор за код модуля.
        return {"state": STATE_UNDECODED, "text": None, "code_chars": None,
                "code_bytes": None, "source_path": relative,
                "reason": f"{path.name}: {exc}"}
    # N3: та же нормализация, что у модулей форм. Счётники считаются по нормализованному
    # значению, иначе `code_chars` не сойдётся с `length(code)` в проверке.
    text = text.strip()
    if not text:
        return {"state": STATE_EMPTY_FILE, "text": None, "code_chars": 0, "code_bytes": 0,
                "source_path": relative, "reason": None}
    encoded = text.encode("utf-8")
    return {"state": STATE_FILE, "text": text, "code_chars": len(text),
            "code_bytes": len(encoded), "source_path": relative, "reason": None}


def _stray_ext_files(root: Path) -> List[str]:
    """Файлы `Ext/*.bsl` вне четырёх предопределённых модулей (замер полноты словаря)."""
    ext_dir = root / EXT_DIR
    if not ext_dir.is_dir():
        return []
    return [candidate.name for candidate in sorted(ext_dir.glob("*.bsl"))
            if candidate.name.lower() not in KNOWN_EXT_BSL]


def collect_root_modules(source_dir, index_rows: Optional[Dict[str, Dict]] = None) -> Dict:
    """Собрать строки четырёх модулей корня: файл (`Ext/`) + запись индекса состава.

    `index_rows` — словарь `{слот: {"name", "object_id"}}`, выбранный загрузчиком из
    `configuration_objects` (N6). `None`/пустой означает «индекс недоступен»: ссылки на индекс
    остаются NULL, и это состояние загрузки, а не ответ о конфигурации — предупреждение
    называет это прямо.

    Ответ: `rows` — строки по колонкам писателя (без `configuration_uuid`: его знает
    загрузчик, а не разбор), `counts` по состояниям отчёта (`REPORT_STATES` — четыре
    состояния строки плюс `absent`: модуля нет вовсе), `by_kind` по видам в порядке
    `ROOT_MODULE_KINDS`, `warnings`,
    `stray_ext_bsl` (файлы `Ext/*.bsl` вне четырёх), `index_matched`/`index_unmatched`.
    """
    root = Path(source_dir)
    index_rows = index_rows or {}
    rows: List[Dict] = []
    counts: Dict[str, int] = {state: 0 for state in REPORT_STATES}
    by_kind: Dict[str, str] = {}
    warnings: List[str] = []

    for kind, module_name, _file_name, slot, _table, title in ROOT_MODULE_KINDS:
        read = read_root_module_file(root, kind)
        index_row = index_rows.get(slot)
        # Состояние строки определяет сопоставление файла с индексом состава, а не только
        # факт чтения файла: «файла нет» без записи индекса — это модуля нет (N2), а не
        # пустой модуль платформы. Счётчики и `by_kind` обязаны называть именно это, иначе
        # сумма состояний перестала бы равняться числу записанных строк.
        state = read["state"]
        if state == STATE_INDEXED_NO_FILE and index_row is None:
            state = STATE_ABSENT
        counts[state] += 1
        by_kind[kind] = state
        if read["reason"]:
            warnings.append(
                f"{title}: файл {read['source_path']} не раскодирован — {read['reason']}; "
                f"код не записан (состояние `{STATE_UNDECODED}`)"
            )
        if state == STATE_ABSENT:
            # Строки нет вовсе (N2) — пустая строка читалась бы как «модуль есть, но пустой».
            continue
        rows.append({
            # `kind` — не колонка: он нужен загрузчику, чтобы выбрать писателя (и, значит,
            # таблицу) по виду, а не по имени таблицы из строки. Писатель INSERT строит по
            # своей спецификации COLUMNS, поэтому лишний ключ в контракт не попадает.
            "kind": kind,
            "module_name": module_name,
            "source_path": read["source_path"],
            "code": read["text"],
            "code_chars": read["code_chars"],
            "code_bytes": read["code_bytes"],
            "code_state": read["state"],
            "index_object_id": (index_row or {}).get("object_id"),
        })

    # Записи индекса, которые словарь не разрешает: это неполнота нашего словаря, а не пустой
    # модуль конкретной выгрузки (аналог `unknown_types` у V43).
    index_unmatched = sorted(slot for slot in index_rows if slot not in KIND_BY_SLOT)
    if index_unmatched:
        warnings.append(
            f"индекс состава перечисляет модули корня вне словаря V44: "
            f"{', '.join(index_unmatched[:MAX_EXAMPLES])} — они не записаны; "
            "`ROOT_MODULE_KINDS` их не покрывает"
        )
    if not index_rows:
        warnings.append(
            f"индекс состава (`configuration_objects`) недоступен — ссылки `index_object_id` "
            f"остаются NULL, а отсутствующий файл записан состоянием `{STATE_ABSENT}`, а не "
            f"`{STATE_INDEXED_NO_FILE}`: без записи индекса нельзя утверждать, что платформа "
            "этот модуль ожидает. Загрузка файлов при этом корректна: файл — источник кода, "
            "индекс — только подтверждение"
        )

    stray = _stray_ext_files(root)
    if stray:
        shown = ", ".join(stray[:MAX_EXAMPLES])
        hidden = len(stray) - MAX_EXAMPLES
        if hidden > 0:
            shown += f", … (ещё {hidden})"
        warnings.append(
            f"в каталоге {EXT_DIR}/ есть файлы модулей вне четырёх предопределённых модулей "
            f"корня: {shown}. Этим слоем они не записаны: общие модули и модули объектов "
            "относятся ко второму слою загрузки конфигурации"
        )

    return {
        "rows": rows,
        "counts": counts,
        "by_kind": by_kind,
        "written": len(rows),
        "kinds_total": ROOT_MODULE_COUNT,
        "index_available": bool(index_rows),
        "index_rows": len(index_rows),
        "index_matched": len(index_rows) - len(index_unmatched),
        "index_unmatched": index_unmatched,
        "stray_ext_bsl": stray,
        "warnings": warnings,
    }


