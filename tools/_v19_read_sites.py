r"""Сторож и замер мест чтения версионируемых таблиц (узел V19, инвариант S2).

Что проверяет. С узла V19 строки семи таблиц версионированы: чтение `WHERE uuid = ...`
без разрешения текущего состояния отдало бы все ревизии сразу (M5). Поэтому читать
базовые таблицы наружу нельзя — обращение ведёт к витрине `v_current_*` либо к
формулировке `src/current_revision.py` (S1–S5).

Режимы:
  python tools/_v19_read_sites.py            # замер и разбор по модулям (код возврата 0)
  python tools/_v19_read_sites.py --guard    # то же + код возврата 1, если осталось
                                             # прямое чтение вне единой точки доступа
  python tools/_v19_read_sites.py --details  # печать каждого посчитанного места
  from _v19_read_sites import scan, guard    # то же решение без stdio: guard(scan()) даёт
                                             # список нарушений (validate_project.py, шаг 8)

Как считается. Одно совпадение = одно SQL-обращение к таблице (`FROM` / `JOIN` /
`INSERT INTO` / `UPDATE` / `DELETE FROM`). Считаются только строковые константы Python
(`ast.Constant`) — то, что реально уходит в SQL: docstring'ы модулей, классов и функций
из счёта сняты (в прежнем замере по сырому тексту предложение «место читает
`FROM external_report`» в docstring попадало в итог). Комментарий внутри SQL-строки
остаётся частью строки и учитывается — для SQL он часть текста, а не отдельная сущность.

Разбивка по виду обращения: чтение (`FROM` / `JOIN`) — наружу запрещено; письмо
(`INSERT INTO` / `UPDATE` / `DELETE FROM`) — норма узла V19, витрины не обновляются.
Чтения через `v_current_*` считаются отдельно и нарушением не считаются.

Число прямых чтений измерялось как цена узла до реализации (замер 18.10.2026 — 51); после
перевода S2 оно обязано быть нулём. Сам перевод измеряется другим числом — вызовами единой
точки доступа (`current_view(...)`, `current_child_count_sql(...)`, `table_name(...)`,
`chain_*_sql(...)`, `row_by_id_sql(...)`, см. `CHANNEL_FUNCS`): после перевода SQL собирается
подстановкой (`f"SELECT ... FROM {cr.current_view(TABLE)}"`), имени таблицы в литерале нет,
поэтому счёт по литералам у переведённых модулей даёт ноль. Ноль в столбцах «чтения» и
«через витрины» при ненулевых вызовах канала — это и есть закрытый S2; нули и там, и там —
пустое измерение, и в режиме стража оно считается провалом, а не успехом.

Граница замера — f-строки с подстановкой имени таблицы: `f"FROM {table}"` не содержит
имени в литерале, поэтому в основной счёт не входит. Такие места разбираются по
категориям (см. `interpolated_sites`): имя из единого модуля, имя через переменную той
же функции, таблица вне семи версионируемых, письмо — и `review`, где имя вывести нечем:
эти места перечисляются для проверки человеком.

Счёт вызовов канала строится по именам из `CHANNEL_FUNCS` этого инструмента, поэтому он сам
подлежит проверке: `channel_names_check` сверяет словарь с экспортом модуля. Имя, которого в
модуле нет, даёт пустой счёт — тот же молчаливый пропуск, что и пустой `WHERE`; новая
функция модуля, не внесённая в словарь, остаётся несчитанной. Любой из двух случаев —
провал и замера, и стража (S1).

`src/current_revision.py` — единая точка доступа: именно он определяет чтения цепочки
состояний, поэтому считается отдельно и в нарушение не входит.

Тот же ответ, что даёт `--guard`, без stdio-транспорта даёт `guard(scan())` — список строк, у
которых нет префикса `GUARD_OK`: это нарушения. `validate_project.py` (шаг 8) импортирует
`scan()` и `guard()` напрямую, чтобы решение и текст не разъезжались между CLI и валидатором:
решение и объяснение печатает этот инструмент, валидатор сообщает только «ok / fails».

Запуск только читает файлы; БД не трогает.
"""

import argparse
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# S1: список версионируемых таблиц задаёт единая точка доступа, а не этот скрипт —
# иначе сторож проверяет по своему перечню и разошёлся бы с модулем незаметно.
from current_revision import VERSIONED_TABLES as TABLE_MAP  # noqa: E402
import current_revision as CHANNEL_MODULE  # noqa: E402  # сверка имён помощников канала

TABLE_SET = set(TABLE_MAP)
TABLES = sorted(TABLE_MAP)
_NAMES = "|".join(TABLES)
# Одно обращение = глагол + имя базовой таблицы. Витрины `v_current_*`/`v_form_*` этот
# образец не матчует: \b требует границы перед именем, а у витрин к имени приписан префикс.
PAT = re.compile(r"(FROM|JOIN|INSERT INTO|UPDATE|DELETE FROM)\s+(" + _NAMES + r")\b", re.I)
READ_VERBS = {"FROM", "JOIN"}
VIEW_NAMES = "|".join("v_current_" + t for t in TABLES)
VIEW_PAT = re.compile(r"(FROM|JOIN)\s+(" + VIEW_NAMES + r")\b", re.I)
# Прежний счёт — по сырому тексту (включает docstring'ы и комментарии). Число историческое.
RAW_PAT = re.compile(r"\b(" + _NAMES + r")\b", re.I)

# DDL-источники: это описание схемы, а не места чтений — их правит миграция,
# их сверяет _cmp_ddl.py.
EXCLUDE = {"generate_ddl.py", "ddl_external_report.sql", "ddl_enrichment.sql"}
# Единая точка доступа (S1): модуль, который и определяет чтения цепочки. Считать его
# обращения нарушением — значит требовать, чтобы точку доступа реализовали в другом месте.
CHANNEL = {"current_revision.py"}

SERVERS = (
    "server_configurations_core.py",
    "server_configurations_enrichment.py",
    "server_configurations_export.py",
)
# Витрины анализа содержимого — их определения узел V19 перевёл на `v_current_*`.
ANALYSIS_VIEWS = ("v_form_elements", "v_form_events", "v_config_enrichment",
                  "v_config_alias_targets")

SUB_TOKEN = "\x00"
SUB_PAT = re.compile(r"(FROM|JOIN|INSERT INTO|UPDATE|DELETE FROM)\s+" + SUB_TOKEN, re.I)
PLACEHOLDER = "{...}"
# Глаголы письма: к S2 не относятся (витрины не обновляются), но и они обязаны
# формироваться единой точкой доступа (S5).
WRITE_SUB_VERBS = {"INSERT INTO", "UPDATE", "DELETE FROM"}
# Признак идентификатора в тексте: им разрешаются имена из констант (`OBJECTS_TABLE`).
NAME_PAT = re.compile(r"[a-z_][a-z0-9_]*")
# Маркеры единой точки доступа. Если любой из них есть в тексте места (или в окружающем
# его определении), формулировку задаёт current_revision.py, а не модуль-вызыватель.
# Имена берутся из CHANNEL_FUNCS (объявлен ниже) — двух списков, которые могут разойтись,
# быть не должно: расхождение и есть тот дефект, из-за которого вызывающий начинает писать своё.
CHANNEL_CONSTANTS = (
    "current_revision", "TABLES[", "TABLES.get", "CURRENT_VIEWS", "REVISION_COLUMNS",
    "MODULE_KEY_EXPR", "VIEW_MEMBER_COLUMNS", "MANIFEST_MEMBERS", "changed_by",
    "revision_no",
)

# Вызовы единой точки доступа. Считать их обязан и замер, и сторож: после перевода S2
# SQL в модулях-вызывателях собирается подстановкой (`f"SELECT ... FROM {cr.current_view(TABLE)}"`),
# имени таблицы в литерале там нет, поэтому счёт по литералам даёт ноль и в модуле, и
# в строке «через витрины». Нули при полностью переведённом коде и есть та ложь, которую
# этот раздел снимает: мерить надо и формулировки (их создаёт канал), и места их вызова.
#   current — текущее состояние (M5); chain — вся цепочка состояний или строка по
#   первичному ключу (S4); key — формат ключа (модуля, элемента формы); write — письмо
#   состояния; sql — иное SQL-выражение единой точки доступа (литерал uuid, член манифеста).
# Словарь обязан совпадать с публичными помощниками `src/current_revision.py`: неполный
# список занижает число переведённых мест, а имена, которых в модуле нет, вымирают молча.
# Список проверяет `tools/check_v19_revisions.py` (группа PHRASES): каждое имя из
# CHANNEL_FUNCS обязано существовать в `src/current_revision.py`.
CHANNEL_FUNCS = {
    "current_view": "current",
    "current_child_count_sql": "current",
    "current_child_rows_sql": "current",
    "current_children_condition": "current",
    "current_children_counts_sql": "current",
    "manifest_member_set_sql": "current",
    "manifest_missing_sql": "current",
    "manifest_member_count_sql": "current",
    "manifest_array_sql": "current",
    "table_name": "chain",
    "revision_chain_count_sql": "chain",
    "chain_count_sql": "chain",
    "chain_exists_sql": "chain",
    "row_by_id_sql": "chain",
    "module_key_sql": "key",
    "form_item_key_sql": "key",
    "uuid_literal": "sql",
    "revision_defaults": "write",
    "build_children_manifest": "write",
    "stamp_revision_rows": "write",
}
CHANNEL_KINDS = ("current", "chain", "key", "write", "sql")
CHANNEL_LABELS = {
    "current": "текущее состояние (M5)",
    "chain": "вся цепочка состояний / строка по первичному ключу (S4)",
    "key": "формат ключа (модуля, элемента формы)",
    "write": "письмо состояния",
    "sql": "иное SQL-выражение единой точки доступа",
}
# Как модули называют сам модуль канала: `from current_revision import current_view`
# (вызов без владельца) или `import current_revision as cr` (владелец `cr`). Вызов
# `self.table_name()` у писателя к каналу не относится — у него свой владелец.
CHANNEL_OWNERS = {"current_revision", "cr"}
# Текст места (f-строка или определение функции) считается сформированным каналом, если в
# нём есть имя любого помощника канала или его константа.
CHANNEL_MARKERS = tuple(CHANNEL_FUNCS) + CHANNEL_CONSTANTS


def targets():
    files = sorted(p for p in (ROOT / "src").glob("*.py") if p.name not in EXCLUDE)
    files += [ROOT / n for n in SERVERS if (ROOT / n).exists()]
    return files


def doc_ids_of(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    ids.add(id(body[0].value))
    return ids


def sql_strings(tree):
    """Строковые константы дерева, кроме docstring'ов (module/class/function).
    В Python 3.12+ литеральные части f-строк — тоже Constant'ы, поэтому `f"... FROM
    external_report ..."` в счёт попадает; не попадает только подстановка `{...}`."""
    skip = doc_ids_of(tree)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            out.append((getattr(node, "lineno", 0), node.value))
    return out


def call_owner(node):
    """Владелец вызова: `cr.chain_count_sql(...)` → `cr`, `self.table_name()` → `self`."""
    value = node.func.value
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return ""


def channel_call_sites(tree):
    """Вызовы единой точки доступа в файле — то, чем переведённый код читает состояние.

    После перевода S2 имя таблицы в литерале не встречается: SQL собирается подстановкой
    (`f"FROM {cr.current_view(TABLE)}"`), а чтение всей цепочки — вызовом
    `cr.chain_count_sql(...)`. Поэтому счёт по литералам (PAT, VIEW_PAT) такие места не
    видит и без этого раздела отчёт показал бы нули там, где работа сделана.

    Разрешаются обе формы импорта: вызов без владельца (`from current_revision import
    current_view`) и вызов с владельцем `current_revision`/`cr`. Чужие владельцы
    (`self.table_name()` у писателя) в счёт не берутся.

    Возвращает список кортежей `(строка, имя функции, вид обращения)`."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name, owner = node.func.id, ""
        elif isinstance(node.func, ast.Attribute):
            name, owner = node.func.attr, call_owner(node)
        else:
            continue
        if name not in CHANNEL_FUNCS:
            continue
        if owner and owner not in CHANNEL_OWNERS:
            continue
        out.append((getattr(node, "lineno", 0), name, CHANNEL_FUNCS[name]))
    return out


def interpolated_sites(tree, text):
    """Места `глагол + подстановка` внутри f-строк: `f"FROM {table}"` не содержит имени
    таблицы в литерале, поэтому в основной счёт такие обращения не входят. Каждое такое
    место получает категорию — от неё зависит, является ли оно нарушением:

      write    — глагол письма (`INSERT INTO` / `UPDATE` / `DELETE FROM`): к S2 не относится,
                 но по S5 должен идти через `current_revision` (письма витрин не касаются);
      channel  — имя версионируемой таблицы названо в самой f-строке через единый модуль;
      indirect — имя приходит из переменной, а вызов единого модуля есть в этой же функции;
      other    — в подстановке названа таблица, которой нет среди семи версионируемых
                 (индекс состава, таблицы обогащения, `local_doc`) — к V19 не относится;
      review   — чем является имя, вывести нечем: место смотрит человек.

    Возвращает список кортежей `(строка, категория, глагол, читаемый фрагмент)`."""
    functions = function_segments(tree, text)
    constants = constant_names(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        joined = join_parts(node)
        match = SUB_PAT.search(joined)
        if not match:
            continue
        verb = match.group(1).upper()
        segment = segment_of(text, node)
        kind = classify_sub(verb, segment, enclosing_segment(functions, getattr(node, "lineno", 0)),
                           substituted_names(node, constants))
        out.append((getattr(node, "lineno", 0), kind, verb, readable(joined[match.start():])))
    return out


SUB_KINDS = (
    ("channel", "имя названо в самой f-строке через единый модуль"),
    ("indirect", "имя через переменную, вызов единого модуля в этой же функции"),
    ("other", "названа таблица вне семи версионируемых — к V19 не относится"),
    ("write", "письмо (INSERT/UPDATE/DELETE) — вне S2, по S5 ведётся через current_revision"),
    ("review", "требует проверки человеком: имя из литерала не выводится"),
)


def join_parts(node):
    """Текст f-строки со служебным признаком подстановки вместо выражений."""
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append(SUB_TOKEN)
    return "".join(parts)


def segment_of(text, node):
    """Исходный текст узла (вместе с выражениями подстановки) — маркеры единого модуля
    в собранном тексте f-строки не видны, их ищут в исходнике."""
    try:
        return ast.get_source_segment(text, node) or ""
    except (AttributeError, ValueError):
        return ""


def function_segments(tree, text):
    """Диапазоны строк определений функций и их исходный текст — чтобы отличать
    `имя через переменную` от собственного WHERE."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((getattr(node, "lineno", 0), getattr(node, "end_lineno", 0),
                        segment_of(text, node)))
    return out


def enclosing_segment(functions, lineno):
    """Текст ближайшей функции, содержащей строку (пустая строка — код верхнего уровня)."""
    inner = None
    for start, end, segment in functions:
        if start <= lineno <= end and (inner is None or start > inner[0]):
            inner = (start, end, segment)
    return inner[2] if inner else ""


def constant_names(tree):
    """Модульные и классовые константы `ИМЯ = "строка"` — ими часто называют таблицу
    (`OBJECTS_TABLE`, `TABLE` у писателя), и это имя разрешается без догадок."""
    out = {}
    for node in ast.walk(tree):
        for target in getattr(node, "targets", []):
            if isinstance(target, (ast.Name, ast.Attribute)) and isinstance(
                    getattr(node, "value", None), ast.Constant) and isinstance(
                    node.value.value, str):
                name = target.id if isinstance(target, ast.Name) else target.attr
                out[name] = node.value.value
    return out


def substituted_names(node, constants):
    """Имена, названные внутри подстановок: строковые литералы аргументов
    (`table_name('bsl_modules')`), значения модульных и классовых констант
    (`OBJECTS_TABLE`, `cls.TABLE`)."""
    out = set()
    for value in node.values:
        if not isinstance(value, ast.FormattedValue):
            continue
        for inner in ast.walk(value):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                out.update(NAME_PAT.findall(inner.value))
            elif isinstance(inner, (ast.Name, ast.Attribute)):
                key = inner.id if isinstance(inner, ast.Name) else inner.attr
                if key in constants:
                    out.update(NAME_PAT.findall(constants[key]))
    return {name for name in out if name}


def classify_sub(verb, segment, enclosing, names):
    """Категория места с подстановкой (см. docstring `interpolated_sites`)."""
    if verb in WRITE_SUB_VERBS:
        return "write"
    for marker in CHANNEL_MARKERS:
        if marker in segment:
            return "channel"
    if names & TABLE_SET:
        return "channel"
    for marker in CHANNEL_MARKERS:
        if marker in enclosing:
            return "indirect"
    if names:
        return "other"
    return "review"


def readable(fragment):
    """Фрагмент f-строки с подстановкой в читаемом виде: `{...}` вместо служебного
    признака подстановки — иначе список мест выводится непечатными символами."""
    return " ".join((fragment or "").replace(SUB_TOKEN, PLACEHOLDER).split())[:70]


def channel_names_check():
    """Самопроверка: словарь каналов этого инструмента против экспорта модуля.

    `CHANNEL_FUNCS` — то, чем меряется переведённая часть S2. Если имя в нём опечаталось
    или помощник переименован, счёт молча расходится с кодом: часть мест перестаёт попадать
    в замер, а «ноль нарушений» читается там, где измерение пустое. Обратная сторона та же:
    новую функцию модуля этот инструмент не заметит и её вызовы не посчитает. Поэтому
    расхождение словаря с модулем — провал и замера, и стража (S1).

    Возвращает dict: `missing` — имена из словаря, которых нет в модуле; `uncovered` —
    публичные функции модуля, которых нет в словаре; `confirmed` — подтверждённые имена;
    `ok` — истинно, когда расхождений нет.
    """
    missing = sorted(name for name in CHANNEL_FUNCS if not hasattr(CHANNEL_MODULE, name))
    defined = sorted(name for name in dir(CHANNEL_MODULE)
                     if not name.startswith("_")
                     and getattr(getattr(CHANNEL_MODULE, name, None), "__module__", None)
                     == CHANNEL_MODULE.__name__)
    uncovered = sorted(set(defined) - set(CHANNEL_FUNCS))
    confirmed = sorted(set(CHANNEL_FUNCS) - set(missing))
    return {"missing": missing, "uncovered": uncovered, "confirmed": confirmed,
            "ok": not missing and not uncovered}


def scan():
    """Структурированный замер: отчёт и режим стража читают эти данные, а не текст.

    Ключи результата:
      modules    — разбор по модулям (имя, чтения, письма, чтения через витрины, вызовы
                   канала по видам, сырой счёт);
      sites      — посчитанные обращения к базовым таблицам (module, lineno, verb, table);
      view_sites — обращения к `v_current_*` (не нарушение, а доказательство перевода);
      channel_sites — вызовы единой точки доступа (module, lineno, функция, вид);
      subs       — f-подстановки после глагола (module, lineno, категория, глагол, фрагмент);
      violations — чтения базовых таблиц вне CHANNEL: то, что сторожит `--guard`;
      channel_names — самопроверка словаря каналов: missing / uncovered / confirmed / ok;
      totals     — итоги.
    """
    modules, sites, view_sites, subs, violations = [], [], [], [], []
    channel_sites = []
    totals = {"reads": 0, "writes": 0, "view_reads": 0, "channel_reads": 0,
              "channel_writes": 0, "channel_calls": 0, "channel_internal": 0, "subs": 0,
              "raw": 0, "violations": 0}
    totals.update({f"channel_{kind}": 0 for kind in CHANNEL_KINDS})
    for path in targets():
        text = path.read_text(encoding="utf-8", errors="ignore")
        raw = len(RAW_PAT.findall(text))
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            print(f"!! {path.name}: файл не разобран ({exc}) — в счёт не вошёл")
            continue
        reads = writes = view_reads = 0
        module_sites = []
        for lineno, sql in sql_strings(tree):
            for verb, table in PAT.findall(sql):
                verb = verb.upper()
                if verb in READ_VERBS:
                    reads += 1
                else:
                    writes += 1
                module_sites.append((path.name, lineno, verb, table))
            for verb, view in VIEW_PAT.findall(sql):
                view_reads += 1
                view_sites.append((path.name, lineno, verb.upper(), view))
        module_subs = interpolated_sites(tree, text)
        channel = channel_call_sites(tree)
        chan_counts = {kind: 0 for kind in CHANNEL_KINDS}
        for _, _, kind in channel:
            chan_counts[kind] += 1
        sites += module_sites
        channel_sites += [(path.name, lineno, name, kind) for lineno, name, kind in channel]
        subs += [(path.name, lineno, kind, verb, snippet)
                 for lineno, kind, verb, snippet in module_subs]
        if path.name in CHANNEL:
            totals["channel_reads"] += reads
            totals["channel_writes"] += writes
            # вызовы внутри самой точки доступа — композиция формулировок
            # (`current_child_count_sql` строит SQL поверх `current_view`), а не перевод
            # чужого места: их печатают отдельным числом, чтобы итог «через канал»
            # не читался как число переведённых модулей.
            totals["channel_internal"] += len(channel)
        else:
            totals["reads"] += reads
            totals["writes"] += writes
            violations += [site for site in module_sites if site[2] in READ_VERBS]
        totals["view_reads"] += view_reads
        totals["channel_calls"] += len(channel)
        for kind in CHANNEL_KINDS:
            totals[f"channel_{kind}"] += chan_counts[kind]
        totals["subs"] += len(module_subs)
        totals["raw"] += raw
        modules.append({"name": path.name, "reads": reads, "writes": writes,
                        "view_reads": view_reads, "subs": len(module_subs),
                        "chan": chan_counts, "chan_total": len(channel),
                        "raw": raw, "channel": path.name in CHANNEL})
    totals["violations"] = len(violations)
    return {"modules": modules, "sites": sites, "view_sites": view_sites,
            "channel_sites": channel_sites, "subs": subs,
            "violations": violations, "channel_names": channel_names_check(),
            "totals": totals}


def format_row(name, reads, writes, chan, view_reads, raw):
    """Строка таблицы замеров. Первые два числа — чтения и письма базовых таблиц,
    дальше — вызовы единой точки доступа по видам, чтения витрин и прежний «сырой» счёт."""
    return (f"{name:34} {reads:>7} {writes:>7} "
            f"{chan['current']:>11} {chan['chain']:>11} {chan['key']:>11} {chan['write']:>13} "
            f"{chan['sql']:>9} {view_reads:>14} {raw:>11}")


GUARD_OK = "OK:"
GUARD_HEADER = ("DIRECT READS", "EMPTY MEASUREMENT", "CHANNEL NAMES OUT OF SYNC")


def external_channel(totals: dict) -> int:
    """Обращения канала вне самой точки доступа — чем измеряется переведённая часть S2.

    Число переводится из «всего обращений минус композиция формулировок внутри
    current_revision.py» в одну функцию: отчёт и решение стража обязаны называть одно и то
    же число (S3)."""
    return totals["channel_calls"] - totals["channel_internal"]


def guard(res: dict) -> list[str]:
    """Решение стража списком строк: строка начинается с `OK:` — правило проверено,
    иначе это нарушение с объяснением. Вынесено из печати, потому что решение нужен
    и `validate_project.py` (шаг 8), и `--guard`: одно и то же решение в двух местах
    разошлось бы. Нулевых прямых чтений мало — измерение не должно быть пустым (S2),
    а словарь каналов обязан совпадать с экспортом current_revision.py (S1), иначе
    счёт вызовов молча отстаёт при переименовании helpers."""
    totals = res["totals"]
    # «вне точки доступа» = все обращения минус композиция самой точки доступа — той же
    # формулировкой пользуется и отчёт (правило S3: один ответ на два вывода).
    external = external_channel(totals)
    out: list[str] = []
    if totals["violations"]:
        # Места нарушения перечисляет само решение, а не только отчёт: validate_project.py
        # печатает строки guard() и без них сказал бы «есть N чтений», не отвечая где.
        shown = "; ".join(f"{name}:{lineno} {verb} {table}"
                          for name, lineno, verb, table in res["violations"][:10])
        hidden = totals["violations"] - min(totals["violations"], 10)
        out.append(
            f"DIRECT READS: {totals['violations']} — прямые чтения базовых таблиц вне единой"
            " точки доступа.\n"
            "Перевести на current_view(...), а чтение всей цепочки состояний — на\n"
            "current_revision.chain_exists_sql / chain_count_sql / row_by_id_sql (правило S4)."
            f"\nМеста: {shown}" + (f" … и ещё {hidden}" if hidden > 0 else ""))
    else:
        out.append(
            f"{GUARD_OK}DIRECT READS: 0 — все обращения к версионируемым таблицам идут через\n"
            f"current_revision.py: канал {totals['channel_calls']} ({external} из модулей + "
            f"{totals['channel_internal']} внутри точки доступа), витрин литералом — "
            f"{totals['view_reads']}, записей: {totals['writes']}")
    if totals["channel_calls"]:
        out.append(f"{GUARD_OK}EMPTY MEASUREMENT: False — посчитано обращений через канал: "
                   f"{totals['channel_calls']} (из них {external} в модулях)")
    else:
        out.append(
            "EMPTY MEASUREMENT: True — посчитано 0 обращений: при нулевом измерении пройденная\n"
            "проверка ничего не подтверждает. Так ведёт себя и опечатка в словаре каналов, и\n"
            "вернувшийся к своему SQL код. Смотри колонку канала в таблице и --details.")
    names = res["channel_names"]
    if names["ok"]:
        out.append(f"{GUARD_OK}CHANNEL NAMES OUT OF SYNC: missing=[] uncovered=[] — словарь"
                   f" каналов ({len(CHANNEL_FUNCS)} имён) совпадает с экспортом current_revision.py")
    else:
        out.append(
            f"CHANNEL NAMES OUT OF SYNC: в словаре нет {names['uncovered']},"
            f" в current_revision.py нет {names['missing']}.\n"
            "Счёт вызовов строится по CHANNEL_FUNCS: при переименовании или новой функции\n"
            "словарь отстаёт молча, а нулевые счётчики неотличимы от пройденной проверки (S1).\n"
            "Правь словарь инструмента, а не имена в модуле.")
    return out


def report(res, guard_mode=False):
    """Печатает замер; в режиме стража — только итог и нарушения. Возвращает код возврата."""
    totals = res["totals"]
    modules = sorted(res["modules"],
                     key=lambda m: (-(m["reads"] + m["writes"] + m["view_reads"] + m["chan_total"]),
                                    m["name"]))
    total_chan = {kind: totals[f"channel_{kind}"] for kind in CHANNEL_KINDS}
    print("ЗАМЕР: обращения к таблицам состояния внешнего объекта (семь базовых таблиц),")
    print("       к витринам текущего состояния v_current_* и к единой точке доступа")
    print("       (AST: строковые литералы, docstring и SQL-сверки из счёта исключены)\n")
    print(f"{'модуль':34} {'чтения':>7} {'письма':>7} "
          f"{'канал·сост':>11} {'канал·цепь':>11} {'канал·ключ':>11} {'канал·письма':>13} "
          f"{'канал·sql':>10} {'через витрины':>14} {'сырой счёт':>11}")
    for module in modules:
        if guard_mode and not (module["reads"] or module["writes"] or module["view_reads"]
                              or module["chan_total"]):
            continue
        print(format_row(module["name"], module["reads"], module["writes"], module["chan"],
                         module["view_reads"], module["raw"]))
    print(format_row("ИТОГО", totals["reads"], totals["writes"], total_chan,
                     totals["view_reads"], totals["raw"]))
    print(f"{'  в единой точке доступа ' + ', '.join(sorted(CHANNEL)):34} "
          f"{totals['channel_reads']:>7} {totals['channel_writes']:>7}")
    print("       канал·сост / цепь / ключ / письма — вызовы current_revision (S3, S4, S5):")
    for kind in CHANNEL_KINDS:
        print(f"         {'канал·' + kind:14} {CHANNEL_LABELS[kind]}")
    print("       Числом в этих колонках измеряется переведённая часть S2: после перевода")
    print("       SQL строится подстановкой, имени таблицы в литерале нет, и столбцы")
    print("       «чтения»/«через витрины» у модулей-вызывателей правомерно нулевые.\n")
    print(f"обращений через единый канал: {totals['channel_calls']}")
    for kind in CHANNEL_KINDS:
        print(f"  {CHANNEL_LABELS[kind]:52} {totals[f'channel_{kind}']:>4}")
    print(f"  из них вне точки доступа (переведённые места модулей): "
          f"{external_channel(totals):>4}")
    print(f"  из них внутри точки доступа (композиция её собственных формулировок): "
          f"{totals['channel_internal']:>4}")
    print()
    print(f"прямых чтений базовых таблиц вне единой точки доступа: {totals['violations']}"
          " — это и есть нарушения S2")
    print(f"чтений витрин литералом в SQL (имя `v_current_*` в самом тексте запроса): "
          f"{totals['view_reads']}")
    print(f"писем (INSERT/UPDATE/DELETE) — вне S2, но обязаны идти через current_revision: "
          f"{totals['writes']}")
    print(f"базовых таблиц литералом внутри самой точки доступа "
          f"({', '.join(sorted(CHANNEL))}): чтений {totals['channel_reads']},"
          f" писем {totals['channel_writes']} — её SQL строится подстановкой,"
          " ноль здесь ожидаем")
    names = res["channel_names"]
    print(f"словарь каналов этого инструмента против экспорта current_revision.py: "
          f"описано {len(CHANNEL_FUNCS)}, подтверждено {len(names['confirmed'])},"
          f" отсутствующих имён {len(names['missing'])}, неучтённых публичных "
          f"{len(names['uncovered'])}")
    for name in names["missing"]:
        print(f"  ❌ {name}: имени в current_revision.py нет — счёт по нему молча обнуляется")
    for name in names["uncovered"]:
        print(f"  ⚠️  {name}: функция есть, в CHANNEL_FUNCS её нет — её вызовы не считаются")
    if res["subs"]:
        print(f"\nf-подстановки после глагола ({totals['subs']}) — имя таблицы в литерале не видно;")
        print("категории (нарушением S2 не являются ни одна, кроме review — их проверяет человек):")
        counts = {}
        for entry in res["subs"]:
            counts[entry[2]] = counts.get(entry[2], 0) + 1
        for kind, label in SUB_KINDS:
            if counts.get(kind):
                print(f"  {counts[kind]:>3}  {kind:8} — {label}")
        for name, lineno, kind, verb, snippet in res["subs"]:
            if kind == "review":
                print(f"    {name}:{lineno}  {snippet}")
    if res["violations"]:
        print("\nНАРУШЕНИЯ — прямые чтения базовых таблиц вне единой точки доступа:")
        # нарушение — четыре значения (модуль, строка, глагол, таблица): ровно те же
        # кортежи, что и в res["sites"]; лишние поля здесь неоткуда взяться.
        for name, lineno, verb, table in res["violations"]:
            print(f"  {name}:{lineno}  {verb} {table}")
    if not guard_mode:
        print(
            "\nЧтения базовых таблиц вне единой точки доступа — это S2: WHERE uuid = ? без"
            "\nrevision_no вернул бы все ревизии сразу. Формулировку даёт current_revision.py:"
            "\nтекущее состояние — current_view(...); вся цепочка состояний или строка по"
            "\nпервичному ключу — chain_exists_sql / chain_count_sql / row_by_id_sql (правило S4)."
            "\nСвой WHERE по базовой таблице вне этих формулировок — регрессия (M5)."
            "\nСтолбец «сырой счёт» — прежнее измерение без AST, по нему видно, сколько"
            "\nсовпадений давали docstring и SQL-файлы."
        )
        return 0
    # Решение вынесено в guard(): и CLI, и validate_project.py читают один и тот же список.
    lines = guard(res)
    problems = [line for line in lines if not line.startswith(GUARD_OK)]
    print()
    if problems:
        print("СТРАЖ: провал — нарушения S1/S2:")
        for line in problems:
            print(line)
    else:
        print("СТРАЖ: пройдено — прямых чтений базовых таблиц вне единой точки доступа нет,")
        print("       S2 закрыт: формулировку чтения даёт current_revision.py, модули её вызывают.")
    for line in lines:
        if line.startswith(GUARD_OK):
            print(line[len(GUARD_OK):])
    return 1 if problems else 0


def main(argv=None):
    """CLI. Без флагов — замер (таблица по модулям + подстановки + правила).
    `--guard` — только итог и нарушения, rc=1 при наличии нарушения.
    `--details` — дополнительно печатает каждое посчитанное место."""
    parser = argparse.ArgumentParser(
        description="Сторож и замер мест чтения версионируемых таблиц (узел V19, S2).",
        epilog="Запуск только читает файлы; БД не трогает.",
    )
    parser.add_argument("--guard", action="store_true",
                       help="режим стража: печатать только итог и нарушения, rc=1 при нарушениях")
    parser.add_argument("--details", action="store_true",
                       help="печатать каждое посчитанное место (модуль:строка, глагол, таблица)")
    args = parser.parse_args(argv)
    res = scan()
    if args.details:
        print("ПОСЧИТАННЫЕ МЕСТА (модуль:строка  ГЛАГОЛ таблица):")
        for name, lineno, verb, table in sorted(res["sites"]):
            print(f"  {name}:{lineno}  {verb} {table}")
        print("\nОБРАЩЕНИЯ ЧЕРЕЗ ЕДИНУЮ ТОЧКУ ДОСТУПА (модуль:строка  вид  функция):")
        for name, lineno, func, kind in sorted(res["channel_sites"]):
            print(f"  {name}:{lineno}  {kind:8} {func}")
        print("\nЧТЕНИЯ ВИТРИН ЛИТЕРАЛОМ (модуль:строка  ГЛАГОЛ витрина):")
        for name, lineno, verb, view in sorted(res["view_sites"]):
            print(f"  {name}:{lineno}  {verb} {view}")
        print()
    return report(res, guard_mode=args.guard)


if __name__ == "__main__":
    raise SystemExit(main())
