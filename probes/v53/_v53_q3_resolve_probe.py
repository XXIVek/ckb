#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V53, развилка Q3: разрешает ли индекс состава цели блока `Source` и ссылки `Handler`.

Зонд только читает. Отвечает на вопросы, без которых модель разрешения целей выдумывалась бы:

1. сколько записей `Source` (квалификатор `Type` — конкретный объект, `TypeSet` — все объекты
   типа) даёт вид по четырём выгрузкам;
2. разрешается ли цель записью индекса состава целиком (`exact`), только префиксом вида
   метаданных (`prefix_only`) или ничем (`unresolved`) — тем же приёмом, что узлы V49–V52
   (ключ `configuration_objects.name` = полное точечное имя, затем срез префикса);
3. чем разрешается `Handler` (`CommonModule.<Имя>.<Метод>`) — строкой общего модуля узла V46
   или ничем;
4. каков объединённый словарь значений `Event` по корпусу (закрыт ли он и чем подтверждён:
   XSD вида в `xsd-schemas/2.20` отсутствует — это названо, а не промолчано).

Цель берётся из файла выгрузки, индекс — из таблицы `configuration_objects` (повторный разбор
`ConfigDumpInfo.xml` вторым источником быть не может, правило V43).

Запуск:  python _v53_q3_resolve_probe.py            # все четыре выгрузки
         python _v53_q3_resolve_probe.py MinCfg     # одна
"""

import os
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import psycopg2  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
# Имя папки выгрузки ≠ name строки заголовка БД (прецедент V52): соответствие установлено
# замером П0 — число верхних строк индекса состава вида совпало с числом файлов регистрации
# (2↔MinCfg, 1↔KomMag, 311↔BGU2, 458↔BP3), а не предполагаемо по названию папки.
DUMP_TO_CONFIGURATION = {
    "MinCfg": "MinCfg",
    "KomMag": "XXI_Коммерческий_магазин_8_редакция_1_0_3",
    "BGU2": "БухгалтерияГосударственногоУчреждения",
    "BP3": "БухгалтерияПредприятия",
}
VIEW_DIR = "EventSubscriptions"
MAX_EXAMPLES = 8
DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password=os.environ["PGPASSWORD"])

# Квалификатор `cfg:<Класс>` → вид метаданных индекса состава. Замер П0 назвал 30 классов по
# корпусу; словарь закрыт именно ими, а не списком платформы: неизвестный класс называется
# состоянием `unknown_class`, а не тихо отсекается (приём V50 Q7 — незнакомое значение остаётся
# значением с состоянием).
CLASS_TO_META = {
    "CatalogObject": "Catalog",
    "CatalogManager": "Catalog",
    "DocumentObject": "Document",
    "DocumentManager": "Document",
    "DocumentJournalManager": "DocumentJournal",
    "InformationRegisterRecordSet": "InformationRegister",
    "InformationRegisterManager": "InformationRegister",
    "AccumulationRegisterRecordSet": "AccumulationRegister",
    "AccumulationRegisterManager": "AccumulationRegister",
    "AccountingRegisterRecordSet": "AccountingRegister",
    "AccountingRegisterManager": "AccountingRegister",
    "CalculationRegisterRecordSet": "CalculationRegister",
    "CalculationRegisterManager": "CalculationRegister",
    "ChartOfAccountsObject": "ChartOfAccounts",
    "ChartOfAccountsManager": "ChartOfAccounts",
    "ChartOfCharacteristicTypesObject": "ChartOfCharacteristicTypes",
    "ChartOfCharacteristicTypesManager": "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypesObject": "ChartOfCalculationTypes",
    "ChartOfCalculationTypesManager": "ChartOfCalculationTypes",
    "BusinessProcessObject": "BusinessProcess",
    "BusinessProcessManager": "BusinessProcess",
    "TaskObject": "Task",
    "TaskManager": "Task",
    "ExchangePlanObject": "ExchangePlan",
    "ConstantValueManager": "Constant",
    "ReportManager": "Report",
    "DataProcessorManager": "DataProcessor",
    "SequenceRecordSet": "Sequence",
    "RecalculationRecordSet": "Recalculation",
    "DefinedType": "DefinedType",
}


def local(tag):
    return tag.split("}")[-1]


def view_files(dump_dir):
    kind_dir = Path(dump_dir) / VIEW_DIR
    if not kind_dir.is_dir():
        return []
    return sorted(p for p in kind_dir.glob("*.xml") if p.is_file())


def read_file(path):
    """Записи `Source` (квалификатор, значение), `Event`, `Handler`, `Name` одного файла."""
    root = ET.parse(str(path)).getroot()
    view = None
    for node in root:
        if local(node.tag) != "MetaDataObject":
            view = node
            break
    out = {"name": "", "sources": [], "event": "", "handler": ""}
    if view is None:
        return out
    for props in view:
        if local(props.tag) != "Properties":
            continue
        for prop in props:
            tag = local(prop.tag)
            if tag == "Name":
                out["name"] = (prop.text or "").strip()
            elif tag == "Event":
                out["event"] = (prop.text or "").strip()
            elif tag == "Handler":
                out["handler"] = (prop.text or "").strip()
            elif tag == "Source":
                for item in prop:
                    out["sources"].append((local(item.tag), (item.text or "").strip()))
    return out


def meta_name_for(value):
    """Имя объекта индексного ключа для цели `Source` — или None, если класс неизвестен.

    Замер назвал две ФОРМЫ цели, и обе встречаются при обоих квалификаторах:
    `cfg:<Класс>.<ИмяОбъекта>` — конкретный объект (`named`), и `cfg:<Класс>` без имени —
    весь тип целиком (`bare`). Состояние разрешения у них разное, поэтому форма возвращается
    третьим элементом, а не теряется в имени.
    """
    body = value.split(":", 1)[1] if value.startswith("cfg:") else value
    meta_type, _, rest = body.partition(".")
    kind = CLASS_TO_META.get(meta_type)
    if kind is None:
        return None, meta_type, rest, "unknown_class"
    if not rest:
        return kind, kind, "", "bare"
    if meta_type == "DefinedType":
        return f"DefinedType.{rest}", kind, rest, "named"
    head = rest.split(".")[0]
    return f"{kind}.{head}", kind, rest, "named"


def index_keys(cur, configuration_uuid):
    """Полные точечные имена индекса состава конфигурации + множество видов объектов."""
    cur.execute(
        """SELECT co.name, co.object_type
             FROM configuration_objects co
             JOIN configurations c ON c.id = co.configuration_id
            WHERE c.uuid::text = %s""",
        (configuration_uuid,),
    )
    names = set()
    kinds = set()
    for name, object_type in cur.fetchall():
        names.add(name)
        kinds.add(object_type)
    return names, kinds


def common_module_names(cur, configuration_uuid):
    """Имена общих модулей текущего состояния (слой V46) — чем разрешается `Handler`."""
    cur.execute(
        """SELECT object_name FROM v_current_common_modules
            WHERE configuration_uuid = %s""",
        (configuration_uuid,),
    )
    return {row[0] for row in cur.fetchall()}


def configuration_uuid(cur, dump_name):
    """uuid заголовка БД по имени выгрузки: соответствие проверено числом файлов круга (П0)."""
    wanted = DUMP_TO_CONFIGURATION.get(dump_name)
    if not wanted:
        return None
    cur.execute("SELECT uuid::text FROM configurations WHERE name = %s", (wanted,))
    row = cur.fetchone()
    return row[0] if row else None


def probe_dump(cur, dump_name):
    print(f"\n=== {dump_name}: {VIEW_DIR} ===")
    files = view_files(DUMP_ROOT / dump_name)
    print(f"файлов регистрации: {len(files)}")
    if not files:
        return
    uuid_value = configuration_uuid(cur, dump_name)
    if not uuid_value:
        print("  ⚠️ строки заголовка с таким именем в БД нет — разрешение целей не проверялось")
        return
    names, kinds = index_keys(cur, uuid_value)
    kind_prefixes = {n.split(".")[0] for n in names}
    cur.execute(
        """SELECT count(*) FROM configuration_objects co
             JOIN configurations c ON c.id = co.configuration_id
            WHERE c.uuid::text = %s AND co.object_type = 'EventSubscription'""",
        (uuid_value,),
    )
    index_rows = cur.fetchone()[0]
    same = "сходится" if index_rows == len(files) else "РАСХОЖДЕНИЕ"
    print(f"строк индекса состава вида: {index_rows} против файлов {len(files)} — {same}")
    modules = common_module_names(cur, uuid_value)
    print(f"строк индекса состава: {len(names)}; видов объектов: {len(kinds)}; "
          f"общих модулей текущего состояния: {len(modules)}")

    states = Counter()
    qual_states = {}
    forms = Counter()
    unknown_classes = Counter()
    handler_states = Counter()
    handler_missing = Counter()
    events = Counter()
    examples = []
    prefix_examples = []
    for path in files:
        data = read_file(path)
        events[data["event"]] += 1
        for qual, value in data["sources"]:
            if not value:
                states["empty_value"] += 1
                continue
            meta_name, kind, _rest, form = meta_name_for(value)
            forms[f"{qual}/{form}"] += 1
            if meta_name is None:
                states["unknown_class"] += 1
                unknown_classes[kind] += 1
                continue
            if form == "bare":
                # цель без имени объекта — «все объекты типа»: разрешается множеством строк
                # этого вида индекса состава, а не строкой объекта
                state = "type_present" if kind in kinds else "type_absent"
            elif meta_name in names:
                state = "exact"
            elif kind in kind_prefixes:
                state = "prefix_only"
            else:
                state = "unresolved"
            states[state] += 1
            qual_states.setdefault(f"{qual}/{form}", Counter())[state] += 1
            if state == "prefix_only" and len(prefix_examples) < MAX_EXAMPLES:
                prefix_examples.append(f"{data['name']} [{qual}/{form}] {value} → {meta_name}")
            elif state not in ("exact", "type_present", "prefix_only") \
                    and len(examples) < MAX_EXAMPLES:
                examples.append(f"{data['name']} [{qual}/{form}] {value} → {meta_name}")
        handler = data["handler"]
        if not handler:
            handler_states["empty"] += 1
            continue
        parts = handler.split(".")
        if len(parts) >= 2 and parts[0] == "CommonModule":
            handler_states["exact" if parts[1] in modules else "unresolved"] += 1
            if parts[1] not in modules:
                handler_missing[parts[1]] += 1
        else:
            handler_states["unknown_form"] += 1

    print(f"состояния разрешения целей Source: {dict(states)}")
    print(f"формы целей (квалификатор/форма): {dict(sorted(forms.items()))}")
    for qual, counter in sorted(qual_states.items()):
        print(f"    {qual:22} — {dict(sorted(counter.items()))}")
    if unknown_classes:
        print(f"    неизвестных классов: {dict(unknown_classes)}")
    print(f"состояния разрешения Handler: {dict(handler_states)}")
    if handler_missing:
        print(f"    модулей-виновников: {len(handler_missing)}; примеры: "
              f"{dict(list(handler_missing.most_common(MAX_EXAMPLES)))}")
    print(f"значения Event по файлам ({len(events)}): {dict(sorted(events.items()))}")
    print("примеры неразрешённых целей:")
    for e in examples:
        print("    ", e)
    print("примеры целей с префиксом вида (имени объекта в индексе нет):")
    for e in prefix_examples:
        print("    ", e)


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== Q3 разрешимость целей Source и Handler (только чтение) ===")
    conn = psycopg2.connect(**DB)
    try:
        with conn.cursor() as cur:
            for name in wanted:
                if name not in DUMPS:
                    print(f"выгрузка не из списка замеров: {name}")
                    continue
                probe_dump(cur, name)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
