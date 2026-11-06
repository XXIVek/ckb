#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, развилка разрешения ссылки: чем разрешается `MethodName` задания.

Мера та же, что у V53 (`_v53_q3_resolve_probe.py`, ответ Q2/Q3): ссылка обработчика
разрешается строкой общего модуля ТЕКУЩЕГО состояния СВОЕЙ конфигурации — витриной
`v_current_common_modules` слоя V46. Отвечает на вопросы, без которых модель разрешения
выдумывалась бы:

1. какова форма `MethodName` по корпусу (число сегментов, первый сегмент) и сколько
   различных модулей и методов даёт вид;
2. разрешается ли модуль витриной общего слоя (`exact`) или нет (`module_absent`) —
   разрешение идёт по своей конфигурации, а не по любой строке витрины;
3. доступен ли модуль серверному вызову (флаги `server`/`server_call` витрины): задание
   исполняется на сервере, поэтому ссылка на клиентский модуль — дефект данных, который
   обязан называться состоянием, а не молча проходить;
4. объявлен ли метод в тексте модуля — тексты общих модулей в живой БД не загружены
   (замер: `bsl_modules` с `parent_type='common_modules'` и непустым `code` — 0 строк,
   слой V46 пишет дескрипторы), поэтому метод ищется по ФАЙЛУ модуля выгрузки; отсутствие
   текста называется состоянием `text_unavailable`, а не «метода нет»;
5. что даёт индекс состава БД: строки `ScheduledJob.<Имя>` и `ScheduledJob.<Имя>.Schedule`
   (чем подтверждается нога содержимого на стороне писателя).

Зонд только читает. Запуск:  python _v54_q_resolve_probe.py [MinCfg ...]
"""
from __future__ import annotations
import os

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import psycopg2  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS: Tuple[str, ...] = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "ScheduledJobs"
MAX_EXAMPLES = 6
DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password=os.environ["PGPASSWORD"])
# Соответствие имени папки и строки заголовка БД установлено замером круга (П0/M1):
# число файлов совпало с числом строк индекса и с длиной перечня заголовка
# (2↔MinCfg, 1↔KomMag, 157↔BGU2, 186↔BP3), а не предполагалось по названию папки.
DUMP_TO_CONFIGURATION = {
    "MinCfg": "MinCfg",
    "KomMag": "XXI_Коммерческий_магазин_8_редакция_1_0_3",
    "BGU2": "БухгалтерияГосударственногоУчреждения",
    "BP3": "БухгалтерияПредприятия",
}
NS = "{http://v8.1c.ru/8.1/data/core}"
LOCAL = lambda tag: tag.split("}", 1)[-1]  # noqa: E731

# Кандидатные пути файла модуля общего модуля в XML-выгрузке. Проверяются оба, потому что
# layout зависит от версии выгрузки; какой из них сработал — называется ответом.
MODULE_CANDIDATES = (
    lambda dump, module: DUMP_ROOT / dump / "CommonModules" / module / "Ext" / "Module.bsl",
    lambda dump, module: DUMP_ROOT / dump / "CommonModules" / f"{module}.bsl",
)
DECL_RE_CACHE: Dict[str, re.Pattern] = {}


def view_files(dump: str) -> List[Path]:
    directory = DUMP_ROOT / dump / VIEW_DIR
    return sorted(directory.glob("*.xml")) if directory.is_dir() else []


def method_name_of(path: Path) -> str:
    """Значение `MethodName` файла регистрации (пустая строка = свойства нет)."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return ""
    for element in root.iter():
        if LOCAL(element.tag) == "MethodName" and element.text:
            return element.text.strip()
    return ""


def parse_method(value: str) -> Tuple[str, str, str, str]:
    """`CommonModule.<Модуль>.<Метод>` → (класс, модуль, метод, форма)."""
    if not value:
        return "", "", "", "absent"
    parts = value.split(".")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2], "three_segment"
    return (parts[0] if parts else ""), "", "", f"other_{len(parts)}_segments"


def module_file(dump: str, module: str) -> Tuple[Path, bool]:
    for builder in MODULE_CANDIDATES:
        candidate = builder(dump, module)
        if candidate.is_file():
            return candidate, True
    return MODULE_CANDIDATES[0](dump, module), False


def method_declared(path: Path, method: str) -> bool:
    """Объявлен ли метод (`Процедура|Функция <Имя>`) в тексте модуля выгрузки."""
    if method not in DECL_RE_CACHE:
        DECL_RE_CACHE[method] = re.compile(
            r"(?i)^\s*(процедура|функция)\s+" + re.escape(method) + r"\b", re.MULTILINE)
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False
    return bool(DECL_RE_CACHE[method].search(text))



def configuration_uuid(cur, dump_name: str):
    """uuid заголовка БД по имени выгрузки: соответствие проверено числом файлов круга."""
    wanted = DUMP_TO_CONFIGURATION.get(dump_name)
    if not wanted:
        return None
    cur.execute("SELECT uuid::text FROM configurations WHERE name = %s", (wanted,))
    row = cur.fetchone()
    return row[0] if row else None


def common_modules(cur, configuration_uuid: str) -> Dict[str, Dict[str, object]]:
    """Общие модули текущего состояния конфигурации — чем разрешается `MethodName`."""
    cur.execute(
        """SELECT object_name, object_uuid::text, server, server_call,
                  client_managed_application, client_ordinary_application,
                  external_connection, privileged, global
             FROM v_current_common_modules
            WHERE configuration_uuid = %s""",
        (configuration_uuid,),
    )
    out: Dict[str, Dict[str, object]] = {}
    for row in cur.fetchall():
        out[row[0]] = {
            "object_uuid": row[1], "server": row[2], "server_call": row[3],
            "client_managed": row[4], "client_ordinary": row[5],
            "external_connection": row[6], "privileged": row[7], "global": row[8],
        }
    return out


def index_counts(cur, configuration_uuid: str) -> Dict[str, object]:
    """Строки индекса состава БД по виду: верхние и дочерние `.Schedule`."""
    cur.execute(
        """SELECT co.name, co.object_type
             FROM configuration_objects co
             JOIN configurations c ON c.id = co.configuration_id
            WHERE c.uuid::text = %s AND co.name LIKE 'ScheduledJob%%'""",
        (configuration_uuid,),
    )
    rows = cur.fetchall()
    kinds = Counter(object_type for _name, object_type in rows)
    head = "ScheduledJob."
    return {
        "total": len(rows),
        "view": sum(1 for name, _k in rows if "." not in name[len(head):]),
        "schedule": sum(1 for name, _k in rows if name.endswith(".Schedule")),
        "kinds": dict(kinds),
    }


def module_texts(cur) -> int:
    """Число загруженных текстов общих модулей (слой V46 пишет дескрипторы, не тексты)."""
    cur.execute("""SELECT count(*) FROM bsl_modules
                    WHERE parent_type = 'common_modules' AND code IS NOT NULL""")
    return int(cur.fetchone()[0])


def probe_dump(cur, dump: str) -> None:
    print(f"\n=== {dump}: {VIEW_DIR} ===")
    files = view_files(dump)
    print(f"файлов регистрации: {len(files)}")
    if not files:
        return
    forms: Counter = Counter()
    values: List[Tuple[str, str]] = []
    for path in files:
        value = method_name_of(path)
        _cls, _module, _method, form = parse_method(value)
        forms[form] += 1
        if value:
            values.append((path.stem, value))
    print(f"формы MethodName: {dict(forms)}; непустых значений: {len(values)}")
    modules = {parse_method(v)[1] for _n, v in values}
    methods = {parse_method(v)[2] for _n, v in values}
    pairs = {(parse_method(v)[1], parse_method(v)[2]) for _n, v in values}
    print(f"различных модулей: {len(modules)}; различных методов: {len(methods)}; "
          f"пар модуль+метод: {len(pairs)}")

    cfg_uuid = configuration_uuid(cur, dump)
    if not cfg_uuid:
        print("  ⚠️ строки заголовка с таким именем в БД нет — разрешение не проверялось")
        return
    live = common_modules(cur, cfg_uuid)
    counts = index_counts(cur, cfg_uuid)
    same = "сходится" if counts["view"] == len(files) else "РАСХОЖДЕНИЕ"
    print(f"общих модулей текущего состояния: {len(live)}; строк индекса состава вида: "
          f"{counts['total']} (верхних {counts['view']}, .Schedule {counts['schedule']}), "
          f"виды: {counts['kinds']}; против файлов {len(files)} — {same}")
    print(f"текстов общих модулей в БД (bsl_modules.code): {module_texts(cur)} — поиск "
          "метода по тексту БД недоступен, метод ищется по файлу модуля выгрузки")

    states: Counter = Counter()
    flags: Counter = Counter()
    unresolved: List[str] = []
    not_declared: List[str] = []
    file_absent: List[str] = []
    for name, value in values:
        _cls, module, method, _form = parse_method(value)
        info = live.get(module)
        if info is None:
            states["module_absent"] += 1
            unresolved.append(f"{name} → {value}")
            continue
        states["module_exact"] += 1
        flags["server" if info["server"] else "server_false"] += 1
        if info["server_call"]:
            flags["server_call"] += 1
        if info["client_managed"] or info["client_ordinary"]:
            flags["client_module"] += 1
        path, found = module_file(dump, module)
        if not found:
            states["module_file_absent"] += 1
            file_absent.append(f"{name} → {module}")
            continue
        if method_declared(path, method):
            states["method_declared"] += 1
        else:
            states["method_not_declared"] += 1
            not_declared.append(f"{name} → {value}")
    print(f"состояния разрешения: {dict(states)}")
    print(f"флаги разрешённых модулей: {dict(flags)}")
    for label, items in (("модуль не разрешается", unresolved),
                         ("метод не объявлен в тексте модуля", not_declared),
                         ("файл модуля в выгрузке не найден", file_absent)):
        print(f"{label}: {len(items)} {items[:MAX_EXAMPLES]}")


def main(argv=None) -> int:
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== замеры разрешимости MethodName позиции 2.9 (только чтение) ===")
    conn = psycopg2.connect(**DB)
    try:
        with conn.cursor() as cur:
            for dump in wanted:
                if dump not in DUMPS:
                    print(f"выгрузка не из списка замеров: {dump}")
                    continue
                probe_dump(cur, dump)
    finally:
        conn.close()
    print("\nВывод: ссылка обработчика — `CommonModule.<Модуль>.<Метод>`; модуль "
          "разрешается строкой общего модуля текущего состояния своей конфигурации "
          "(витрина слоя V46), метод — текстом модуля выгрузки. Текстов модулей в БД на "
          "момент замера нет, поэтому состояние `text_unavailable` является границей базы, "
          "а не состоянием данных выгрузки.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
