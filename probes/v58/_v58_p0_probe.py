#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V58, шаг П0: замеры круга позиции 2.13 «Определяемые типы».

Вид — `DefinedType` (каталог `DefinedTypes/`, перечень заголовка
`configurations.defined_types`). Зонд только читает: ни в БД, ни в файлы выгрузок не пишет.

Отвечает на вопросы, без которых модель записи вида выдумывалась бы:

1. круг вида по четырём выгрузкам — файлы регистрации, каталоги содержимого, записи индекса
   состава; сверка ног и расхождения `file_only` / `index_only` / `uuid_mismatch`; детей и
   псевдозаписей индекса — отдельным числом;
2. третья нога — перечень заголовка `configurations.defined_types` (живая БД, заполняет стадия
   S2) и строки `configuration_objects` по ТОЧНОМУ `object_type`: имя вида `DefinedType` входит
   в адрес цели `cfg:DefinedType.<Имя>`, по которому слои V48/V50/V52 уже пишут записи класса
   `defined_type_ref`;
3. четвёртая нога — перечень имён вида в `<ChildObjects>` корневого `Configuration.xml`;
4. словарь свойств узла вида (теги `Properties`) и ФОРМА каждого значения;
5. блок `<Type>` — главное содержимое вида: формы блока, КРАТНОСТЬ значений (сколько `<v8:Type>`
   на файл), ФОРМА значения (`Ref` / `Object` / `RecordSet` / `RecordManager` / `ValueManager` /
   `DefinedType` / примитив / прочее), квалификаторы, разрешение индексом состава
   (`exact` / `prefix_only` / `unresolved`), самоссылки и ссылки на другой определяемый тип;
6. покрывает ли существующий словарь классов типа (узел V48, `classify_type_value`) ФОРМЫ,
   которые даёт корпус этого вида — нужен ли собственный словарь форм разбора;
7. зачем узел нужен: сколько ссылок `cfg:DefinedType.<Имя>` уже лежит в живой БД слоями
   V48/V50/V52 без разрешения — то, что снимает следующий шаг;
8. кросс-выгрузочные коллизии `uuid` и имён (M1) — ключ версионности выбирается по замеру, а не
   по схеме соседа (прецеденты V50…V57);
9. цена круга (байты файлов регистрации) — порог, при котором круг резали бы на группы запроса
   (прецедент Q5 узла V48, замеры 1.4 узлов V50…V57);
10. XSD вида — замкнут ли словарь свойств схемой;
11. состояние живой схемы и реестра инструментов на начало узла: таблиц вида нет, число
    инструментов ядра называется прогоном реестра, а не памятью.

Граница: полный обход всех выгрузок на предмет ссылок на вид НЕ делается — он занял бы минуты;
число ссылок берётся из уже загруженных слоёв (живая БД), а число ссылок видов, чьи слои не
загружены, названо прежним замером V48 (2.4.4: BGU2 2942, BP3 4721) ссылкой, а не новым прогоном.

Запуск:  python _v58_p0_probe.py            # все четыре выгрузки
         python _v58_p0_probe.py MinCfg     # одна
"""

import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "DefinedTypes"
VIEW_TAG = "DefinedType"
DUMP_INFO = "ConfigDumpInfo.xml"
XSD_ROOTS = (Path(r"C:\1C_LLM\ckb\xsd-schemas"), Path(r"C:\1C_LLM\ckb\xsd-docs"))
REPO_ROOT = Path(r"C:\1C_LLM\ckb")
DUMP_TO_CONFIGURATION = {
    "MinCfg": "MinCfg",
    "KomMag": "XXI_Коммерческий_магазин_8_редакция_1_0_3",
    "BGU2": "БухгалтерияГосударственногоУчреждения",
    "BP3": "БухгалтерияПредприятия",
}
DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password=os.environ["PGPASSWORD"])

XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
UUID_RE = re.compile(r'^\s*<' + VIEW_TAG + r'\s+uuid="([0-9a-fA-F-]{36})"', re.MULTILINE)

# ФОРМЫ значения типа по корпусу. Словарь строится ЗАМЕРОМ, а не догадкой: непознанная форма
# называется `other:<суффикс>` — это основание для состояния `unknown_form`, а не для молчания.
VALUE_SUFFIX_FORMS = {
    "Ref": "object_ref",
    "Object": "object_manager",
    "RecordSet": "record_set",
    "RecordManager": "record_manager",
    "ValueManager": "value_manager",
    "Manager": "manager",
    "EnumKey": "enum_key",
}
QUALIFIER_TAGS = ("StringQualifiers", "NumberQualifiers", "DateQualifiers")
TYPE_VALUE_TAGS = ("Type", "TypeSet")


def local(tag):
    return tag.split('}')[-1]


def shape_of(node):
    """Форма значения свойства: пустое / xsi:nil / скаляр / bool / число / многоязык / блок."""
    if node.get(XSI_NIL):
        return "xsi_nil"
    kids = [local(k.tag) for k in node]
    if not kids:
        text = (node.text or "").strip()
        if not text:
            return "empty"
        if text in ("true", "false", "1", "0"):
            return "bool"
        if text.lstrip("-").isdigit():
            return "integer"
        return "scalar"
    if set(kids) <= {"item"}:
        return "multilang"
    return "block"


def value_form(value):
    """ФОРМА значения типа: примитив / определяемый тип / <Вид><суффикс>.<Имя> / прочее.

    Возвращает пару (форма, адрес цели вида `<Вид>.<Имя>`, если он выводится). Префикс
    пространства имён отбрасывается по разделителю, а не по имени: один и тот же URI в корпусе
    пишут разные префиксы (`cfg`, `d4p1`, …), и признак класса — URI, а не имя (2.4.4 V48).
    """
    if not value:
        return "empty_value", ""
    prefix, sep, body = value.rpartition(":")
    if not sep:
        return "no_namespace", ""
    if prefix == "xs":
        return "primitive", ""
    parts = body.split(".")
    if len(parts) < 2:
        # одиночный сегмент под своим префиксом: встроенные типы платформы (`v8:UUID` и т. п.)
        # и всё, что корпус под этим префиксом ещё даёт; префикс называется отдельно
        return "single_segment", ""
    head, name = parts[0], ".".join(parts[1:])
    if not name:
        return "empty_value", ""
    if head == VIEW_TAG:
        return "defined_type_ref", VIEW_TAG + "." + name
    if head.endswith("KeyManager"):
        return "key_manager", head[: -len("KeyManager")] + "." + name
    for suffix, form in VALUE_SUFFIX_FORMS.items():
        if head.endswith(suffix):
            return form, head[: -len(suffix)] + "." + name
    return "other:" + head, ""


def resolve_target(value, index_names):
    """Состояние разрешения цели индексом состава: exact / prefix_only / unresolved."""
    if not value:
        return "empty_value", ""
    body = value.split(":")[-1]
    if body in index_names:
        return "exact", body
    parts = body.split(".")
    while parts:
        parts.pop()
        prefix = ".".join(parts)
        if prefix and prefix in index_names:
            return "prefix_only", prefix
    return "unresolved", ""


def index_entries(dump):
    """Записи индекса состава вида: нога вида, ноги детей и псевдозаписи верхнего уровня."""
    path = DUMP_ROOT / dump / DUMP_INFO
    if not path.is_file():
        return {}, {}, {}, f"индекса состава нет: {path}"
    prefix = f"{VIEW_TAG}."
    views, children, pseudo = {}, {}, Counter()
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001
        return {}, {}, {}, f"{type(exc).__name__}: {exc}"
    for node in root.iter():
        if local(node.tag) != "Metadata":
            continue
        name = node.get("name") or ""
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        parts = rest.split(".")
        if len(parts) == 1 and parts[0]:
            views[parts[0]] = (node.get("id") or "", name)
        elif len(parts) == 2:
            children.setdefault(parts[0], Counter())[parts[1]] += 1
        else:
            pseudo[".".join(parts[1:-1]) or "<пусто>"] += 1
    return views, children, pseudo, ""


def index_all_names(dump):
    """Все имена индекса состава выгрузки — чтобы разрешать значения блока `<Type>`."""
    path = DUMP_ROOT / dump / DUMP_INFO
    if not path.is_file():
        return set()
    names = set()
    try:
        root = ET.parse(str(path)).getroot()
    except Exception:  # noqa: BLE001
        return names
    for node in root.iter():
        if local(node.tag) == "Metadata":
            name = node.get("name") or ""
            if name:
                names.add(name)
    return names



def note_value(info, value, index_names):
    """Класс, форма, префикс и состояние разрешения одного значения блока `<Type>`."""
    info["values_total"] += 1
    form, kind = value_form(value)
    info["value_forms"][form] += 1
    if kind:
        info["value_kinds"][kind.split(".")[0]] += 1
        info["target_names"][kind] += 1
    info["value_namespaces"][value.split(":")[0] if ":" in value else "<без префикса>"] += 1
    if form == "primitive":
        # цели у значения нет: это тип, а не адрес объекта метаданных
        info["value_states"]["no_target"] += 1
    elif kind:
        # разрешается адресом индекса состава (`<Вид>.<Имя>`), а не текстом значения:
        # `cfg:DocumentRef.Х` — это форма записи, а индексом существует `Document.Х` (прецедент V48)
        state, _ = resolve_target(kind, index_names)
        info["value_states"][state] += 1
        if state != "exact":
            info["unresolved_targets"][f"{state} {kind}"] += 1
    else:
        state, _ = resolve_target(value, index_names)
        info["value_states"][state] += 1
    if form == "defined_type_ref":
        info["defined_type_refs"] += 1
        info["defined_type_resolved"][state] += 1
        if kind == info["self_name"]:
            info["self_refs"] += 1
        elif state != "exact" and kind in info["own_type_names"]:
            info["defined_type_resolved"]["цель_есть_файлом_этой_же_выгрузки"] += 1


def probe_registration_file(path, index_names, own_type_names):
    """Словарь свойств узла вида + блок `<Type>` (главное содержимое вида)."""
    info = {"view_tag": "", "view_uuid": "", "self_name": f"{VIEW_TAG}.{path.stem}",
            "own_type_names": own_type_names, "props": Counter(), "shapes": Counter(),
            "top_tags": Counter(), "internal_tags": Counter(), "generated_attrs": Counter(),
            "type_block_shapes": Counter(), "type_multiplicity": Counter(),
            "type_item_tags": Counter(), "value_forms": Counter(), "value_kinds": Counter(),
            "value_states": Counter(), "value_namespaces": Counter(), "qualifiers": Counter(),
            "qualifier_values": Counter(), "defined_type_resolved": Counter(),
            "target_names": Counter(), "unresolved_targets": Counter(),
            "values_total": 0, "self_refs": 0, "defined_type_refs": 0, "dup_values": 0,
            "no_type_block": 0, "empty_comment": 0, "empty_synonym": 0, "error": ""}
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001  битый XML называется, а не пропускается
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info
    if local(root.tag) != "MetaDataObject":
        info["error"] = f"корень не MetaDataObject: {local(root.tag)}"
        return info
    for meta in root:
        info["view_tag"] = local(meta.tag)
        info["view_uuid"] = meta.get("uuid") or ""
        props = internal = None
        for block in meta:
            tag = local(block.tag)
            info["top_tags"][tag] += 1
            if tag == "Properties":
                props = block
            elif tag == "InternalInfo":
                internal = block
        if internal is not None:
            for node in internal.iter():
                tag = local(node.tag)
                info["internal_tags"][tag] += 1
                if tag == "GeneratedType":
                    for attr, want in (("name", "name"), ("category", "category")):
                        if node.get(attr):
                            info["generated_attrs"][want] += 1
        if props is None:
            info["error"] = "блок Properties не найден"
            return info
        for prop in props:
            tag = local(prop.tag)
            info["props"][tag] += 1
            info["shapes"][f"{tag}={shape_of(prop)}"] += 1
            text = (prop.text or "").strip()
            if tag == "Comment" and not text:
                info["empty_comment"] += 1
            if tag == "Synonym" and not list(prop):
                info["empty_synonym"] += 1
            if tag != "Type":
                continue
            kids = list(prop)
            if not kids and not text:
                info["type_block_shapes"]["<пустой блок>"] += 1
                info["no_type_block"] += 1
                continue
            if not kids and text:
                info["type_block_shapes"]["scalar"] += 1
                info["type_multiplicity"][1] += 1
                note_value(info, text, index_names)
                continue
            info["type_block_shapes"][tuple(sorted(local(k.tag) for k in kids))] += 1
            n_values, seen = 0, set()
            for kid in kids:
                tag2 = local(kid.tag)
                info["type_item_tags"][tag2] += 1
                if tag2 in TYPE_VALUE_TAGS:
                    n_values += 1
                    value = (kid.text or "").strip()
                    note_value(info, value, index_names)
                    if value in seen:
                        info["dup_values"] += 1
                    seen.add(value)
                elif tag2 in QUALIFIER_TAGS:
                    for q in kid:
                        info["qualifiers"][f"{tag2}.{local(q.tag)}"] += 1
                        info["qualifier_values"][
                            f"{tag2}.{local(q.tag)}={q.text}"] += 1
                else:
                    info["type_item_tags"]["unknown:" + tag2] += 1
            info["type_multiplicity"][n_values] += 1
            if n_values == 0:
                info["no_type_block"] += 1
    return info


def content_layout(view, dirs):
    """Раскладка каталогов содержимого вида: есть ли формы, макеты, команды, модули."""
    layouts, sizes, empty_dirs = Counter(), Counter(), []
    for name in dirs:
        directory = view / name
        files = [p for p in directory.rglob("*") if p.is_file()]
        if not files:
            empty_dirs.append(name)
            continue
        layouts[name] += len(files)
        sizes[name] += sum(p.stat().st_size for p in files)
    return layouts, sizes, empty_dirs


def config_names(dump):
    """Четвёртая нога — перечень имён вида в `<ChildObjects>` корня выгрузки."""
    config = DUMP_ROOT / dump / "Configuration.xml"
    if not config.is_file():
        return [], "Configuration.xml нет"
    try:
        text = config.read_text(encoding="utf-8-sig", errors="replace")
        return sorted(set(re.findall(r"<" + VIEW_TAG + r">([^<]+)</" + VIEW_TAG + r">",
                                     text))), ""
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"


def ns_map_of(path):
    """Объявления xmlns этого файла: префикс → URI (класс типа вычисляют по URI, а не по префиксу)."""
    head = path.read_text(encoding="utf-8-sig", errors="replace")[:4000]
    return dict(re.findall(r'xmlns:?([\w.-]*)="([^"]+)"', head))


def v48_classifier_check(values):
    """Сколько значений вида понимает существующий словарь классов типа (узел V48).

    Функция `classify_type_value` слоя V48 импортируется как есть — проверка идёт по её
    настоящему коду, а не по пересказу. Ответ нужен до кода: если словарь V48 формы этого вида
    не покрывает, узлу нужен собственный словарь форм, а не прежний. Прогон — по всем значениям
    блока `<Type>` круга, а не по выборке.
    """
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "src"))
    try:
        from src.configuration_session_parameters import classify_type_value
    except Exception as exc:  # noqa: BLE001
        return Counter({f"импорт не удался: {type(exc).__name__}": len(values)}), Counter()
    classes = Counter()
    reasons = Counter()
    for ns_map, value in values:
        entry = classify_type_value(value, ns_map)
        classes[entry.get("class")] += 1
        if entry.get("reason"):
            reasons[entry["reason"][:70]] += 1
    return classes, reasons


def header_list(dump):
    """Перечень заголовка `configurations.defined_types` (третья нога)."""
    import psycopg2

    wanted = DUMP_TO_CONFIGURATION.get(dump)
    if not wanted:
        return None, "имя выгрузки не из словаря соответствия"
    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return None, f"БД недоступна: {type(exc).__name__}: {exc}"
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT defined_types FROM configurations WHERE name = %s", (wanted,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None, f"строки заголовка с именем {wanted!r} в БД нет"
    if row[0] is None:
        return [], "перечень заголовка NULL (стадия S2 его не заполнила)"
    return list(row[0]), ""


def db_index_counts():
    """Строки `configuration_objects` точным предиктом по виду (не по началу имени)."""
    import psycopg2

    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return [("БД недоступна: %s" % type(exc).__name__, "", 0)]
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.name, o.object_type, count(*) FROM configuration_objects o "
                "JOIN configurations c ON c.id = o.configuration_id "
                "WHERE o.object_type = %s GROUP BY 1, 2 ORDER BY 1", (VIEW_TAG,))
            return list(cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        return [("ошибка запроса: %s" % type(exc).__name__, "", 0)]
    finally:
        conn.close()


def db_unresolved_defined_type_refs():
    """Сколько ссылок `cfg:DefinedType.*` уже записано слоями V48/V50/V52 без разрешения."""
    import psycopg2

    out = []
    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return [("БД недоступна: %s" % type(exc).__name__, "", 0)]
    try:
        with conn.cursor() as cur:
            for table in ("session_parameters", "common_attributes", "filter_criteria"):
                try:
                    cur.execute(
                        "SELECT count(*) FROM %s s, jsonb_array_elements(s.types) t "
                        "WHERE t->>'class' = 'defined_type_ref'" % table)
                    entries = cur.fetchone()[0]
                    cur.execute(
                        "SELECT count(*) FROM %s s WHERE EXISTS (SELECT 1 FROM "
                        "jsonb_array_elements(s.types) t "
                        "WHERE t->>'class' = 'defined_type_ref')" % table)
                    rows = cur.fetchone()[0]
                    out.append((table, rows, entries))
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    out.append((f"{table}: {type(exc).__name__}", "", 0))
    finally:
        conn.close()
    return out


def db_schema_state():
    """Состояние живой схемы на начало узла: таблицы и витрины вида, колонка заголовка."""
    import psycopg2

    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return [("БД недоступна: %s" % type(exc).__name__, "")]
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, 'TABLE' FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name LIKE '%%defined%%' "
                "UNION ALL SELECT table_name, 'COLUMN' FROM information_schema.columns "
                "WHERE table_schema='public' AND column_name LIKE '%%defined%%' "
                "UNION ALL SELECT table_name, 'VIEW' FROM information_schema.views "
                "WHERE table_schema='public' AND table_name LIKE '%%defined%%' ORDER BY 2, 1")
            rows = list(cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        return [("ошибка запроса: %s" % type(exc).__name__, "")]
    finally:
        conn.close()
    return rows or [("таблиц, витрин и колонок с именем defined, кроме "
                     "configurations.defined_types, нет", "")]


def registry_tool_count():
    """Число инструментов ядра — по регистру `@mcp.tool()`, а не по памяти."""
    text = (REPO_ROOT / "server_configurations_core.py").read_text(encoding="utf-8")
    return len(re.findall(r"^@mcp\.tool\(\)", text, re.MULTILINE))


def xsd_probe():
    """Есть ли XSD вида — им замыкается словарь свойств при малом корпусе."""
    hits = []
    for root in XSD_ROOTS:
        if not root.is_dir():
            hits.append(f"каталога нет: {root}")
            continue
        for path in root.rglob("*.xsd"):
            if VIEW_DIR.lower() in path.name.lower() or VIEW_TAG.lower() in path.name.lower():
                hits.append(str(path))
    return hits


# Каталоги видов, у которых бывает блок `<Type>` (перечислены по замеру 2.4.4 узла V48).
# Полный обход выгрузки не делается: в BGU2 158 925 XML, а названий видов, где значения типа
# бывают, корпус уже перечисляет.
REF_DIRS = ("Catalogs", "Documents", "InformationRegisters", "AccumulationRegisters",
            "ChartsOfCharacteristicTypes", "Constants", "SessionParameters",
            "CommonAttributes", "FilterCriteria", "ExchangePlans", "AccountingRegisters",
            "CumulationRegisters", "BusinessProcesses", "Tasks", "ChartsOfAccounts",
            "ChartsOfCalculationTypes")
REF_NEEDLE = ":DefinedType."


def corpus_refs_to_view():
    """Сколько мест ЧУЖИХ видов ссылаются на вид: подстрока `:DefinedType.` в значениях типа.

    Это подтверждение прежнего замера V48 (2.4.4: BGU2 2942, BP3 4721 значения внутри
    `<v8:TypeSet>`), а не новый источник знания: ответ нужен, чтобы сказать, ради чего узел
    существует, если слои целей (реквизиты видов) ещё не загружены.
    """
    out = []
    for dump in DUMPS:
        files_total, hits_total, per_dir = 0, 0, []
        for name in REF_DIRS:
            directory = DUMP_ROOT / dump / name
            if not directory.is_dir():
                continue
            files = hits = 0
            for path in directory.glob("*.xml"):
                try:
                    text = path.read_text(encoding="utf-8-sig", errors="replace")
                except Exception:  # noqa: BLE001
                    continue
                n = text.count(REF_NEEDLE)
                if n:
                    files += 1
                    hits += n
            if files:
                per_dir.append((name, files, hits))
            files_total += files
            hits_total += hits
        out.append((dump, files_total, hits_total, per_dir))
    return out


def probe_dump(dump, corpus):
    print("=" * 78)
    print(f"ВЫГРУЗКА {dump}")
    view = DUMP_ROOT / dump / VIEW_DIR
    if not view.is_dir():
        print("каталога вида НЕТ — files_found = 0, наблюдение directory_missing")
        corpus["directory_missing"].append(dump)
        for key in ("per_dump_files", "per_dump_bytes", "per_dump_index", "per_dump_values"):
            corpus[key][dump] = 0
        return
    files = sorted(p for p in view.iterdir() if p.is_file() and p.suffix.lower() == ".xml")
    other = sorted(p for p in view.rglob("*") if p.is_file() and p.suffix.lower() != ".xml")
    dirs = sorted(p.name for p in view.iterdir() if p.is_dir())
    total_bytes = sum(p.stat().st_size for p in files)
    layouts, sizes, empty_dirs = content_layout(view, dirs)
    print(f"файлов регистрации: {len(files)}, байт {total_bytes}; не-XML {len(other)}; "
          f"каталогов содержимого {len(dirs)} {dirs}; прочего содержимого "
          f"{sum(sizes.values())} байт; пустых каталогов {len(empty_dirs)}")
    if layouts:
        print(f"раскладка содержимого: {layouts.most_common()}")

    index_views, index_children, index_pseudo, index_error = index_entries(dump)
    index_names = index_all_names(dump)
    print(f"записей индекса состава вида: {len(index_views)}; строк детей {len(index_children)}; "
          f"псевдозаписей {sum(index_pseudo.values())}; ошибка: {index_error or 'нет'}")
    for name, kids in list(index_children.items())[:5]:
        print(f"  дети {name}: {dict(kids)}")

    names_file = {}
    for path in files:
        m = UUID_RE.search(path.read_text(encoding="utf-8-sig", errors="replace"))
        names_file[path.stem] = m.group(1) if m else ""
    only_files = sorted(set(names_file) - set(index_views))
    only_index = sorted(set(index_views) - set(names_file))
    mismatch = sorted(n for n in set(names_file) & set(index_views)
                      if (names_file[n] or "").lower() != (index_views[n][0] or "").lower())
    empty_uuid = sorted(n for n, u in names_file.items() if not u)
    print(f"файл_без_индекса {len(only_files)} {only_files[:3]}; индекс_без_файла "
          f"{len(only_index)} {only_index[:3]}; uuid_mismatch {len(mismatch)} "
          f"{mismatch[:3]}; пустых uuid {len(empty_uuid)}")

    cfg_names, cfg_error = config_names(dump)
    print(f"перечень корня `<{VIEW_TAG}>`: имён {len(cfg_names)}; ошибка: {cfg_error or 'нет'}; "
          f"совпадает с файлами: {sorted(names_file) == cfg_names}")
    hdr, hdr_error = header_list(dump)
    if hdr is None:
        print(f"перечень заголовка: {hdr_error}")
    else:
        print(f"перечень заголовка: имён {len(hdr)}; совпадает с файлами: "
              f"{sorted(names_file) == sorted(hdr)}; {hdr_error or ''}")

    own_type_names = {f"{VIEW_TAG}.{n}" for n in index_views}
    all_values = []
    for path in files:
        info = probe_registration_file(path, index_names, own_type_names)
        for key in ("props", "shapes", "top_tags", "internal_tags", "generated_attrs",
                    "type_block_shapes", "type_item_tags", "value_forms", "value_kinds",
                    "value_states", "value_namespaces", "qualifiers", "qualifier_values",
                    "type_multiplicity", "defined_type_resolved", "target_names",
                    "unresolved_targets"):
            corpus[key].update(info[key])
        corpus["values_total"] += info["values_total"]
        corpus["self_refs"] += info["self_refs"]
        corpus["defined_type_refs"] += info["defined_type_refs"]
        corpus["dup_values"] += info["dup_values"]
        corpus["no_type_block"] += info["no_type_block"]
        corpus["empty_comment"] += info["empty_comment"]
        corpus["empty_synonym"] += info["empty_synonym"]
        corpus["max_values_per_file"] = max(corpus["max_values_per_file"],
                                           max(info["type_multiplicity"] or [0]))
        if info["error"]:
            corpus["errors"].append(f"{dump}\\{path.name}: {info['error']}")
        for form, count in info["value_forms"].items():
            if form.startswith("other:"):
                corpus["other_forms"][f"{dump} {form}"] += count
        corpus["files"] += 1
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        ns_map = ns_map_of(path)
        all_values += [(ns_map, v) for v in
                       re.findall(r"<v8:Type>([^<]+)</v8:Type>", text)]
    for stem, uid in names_file.items():
        corpus["names"][stem] += 1
        if uid:
            corpus["uuids"][uid] += 1
            corpus["uuid_dumps"][uid].add(dump)
        corpus["name_dumps"][stem].add(dump)
    corpus["per_dump_files"][dump] = len(files)
    corpus["per_dump_bytes"][dump] = total_bytes
    corpus["per_dump_index"][dump] = len(index_views)
    corpus["per_dump_values"][dump] = len(all_values)
    # повторных имён внутри одной выгрузки быть не может: имена файлов каталога уникальны
    # по конструкции каталога. Число называется нулём потому, что его проверяют, а не потому,
    # что его предполагают: оно считается как файлы минус различные имена круга выгрузки.
    corpus["per_dump_names"][dump] = len(names_file)
    classes, reasons = v48_classifier_check(all_values)
    corpus["v48_classes"].update(classes)
    for reason, count in reasons.most_common():
        corpus["v48_reasons"][reason] += count


def report(corpus, only):
    print("=" * 78)
    print("ОБЩИЙ КОРПУС")
    print(f"файлов разобрано: {corpus['files']}; ошибок разбора: {len(corpus['errors'])}")
    for e in corpus["errors"][:5]:
        print(f"  {e}")
    if corpus["directory_missing"]:
        print(f"каталога вида нет: {corpus['directory_missing']}")
    print("\nТЕГИ Properties (словарь свойств узла):")
    for k, v in corpus["props"].most_common():
        print(f"   {k}: {v}")
    print("\nФОРМЫ значений свойств:")
    for k, v in corpus["shapes"].most_common():
        print(f"   {k}: {v}")
    print(f"\nБлоки верхнего уровня: {dict(corpus['top_tags'])}")
    print(f"InternalInfo: {dict(corpus['internal_tags'])} атрибутов GeneratedType: "
          f"{dict(corpus['generated_attrs'])}")
    print("\nФОРМЫ блока <Type> (топ 12):")
    for k, v in corpus["type_block_shapes"].most_common(12):
        print(f"   {k}: {v}")
    print("\nКРАТНОСТЬ значений типа (число <v8:Type> на файл):")
    for k in sorted(corpus["type_multiplicity"]):
        print(f"   {k}: {corpus['type_multiplicity'][k]}")
    print(f"   максимум {corpus['max_values_per_file']}; файлов без значений типа: "
          f"{corpus['no_type_block']}; повторов значений внутри файла: {corpus['dup_values']}")
    print("\nФОРМЫ значений типа:")
    for k, v in corpus["value_forms"].most_common():
        print(f"   {k}: {v}")
    print("Виды метаданных целей (первый сегмент адреса):")
    for k, v in corpus["value_kinds"].most_common(25):
        print(f"   {k}: {v}")
    print("Состояние разрешения цели индексом состава:")
    for k, v in corpus["value_states"].most_common():
        print(f"   {k}: {v}")
    print(f"различных адресов целей значений: {len(corpus['target_names'])}; "
          f"топ-8: {corpus['target_names'].most_common(8)}")
    print("целей, которых нет в индексе состава (топ 10):")
    for k, v in corpus["unresolved_targets"].most_common(10):
        print(f"   {v} {k}")
    print(f"Ссылок на определяемый тип: {corpus['defined_type_refs']}; самоссылок: "
          f"{corpus['self_refs']}; раскладка {dict(corpus['defined_type_resolved'])}")
    print(f"Непознанные ФОРМЫ по выгрузкам: {dict(corpus['other_forms'])}")
    print(f"Квалификаторы: {dict(corpus['qualifiers'])}")
    print("Значения квалификаторов (топ 12):")
    for k, v in corpus["qualifier_values"].most_common(12):
        print(f"   {k}: {v}")
    print(f"Префиксы значений: {dict(corpus['value_namespaces'])}")
    print(f"пустых Comment: {corpus['empty_comment']}; пустых Synonym: "
          f"{corpus['empty_synonym']}; значений типа всего: {corpus['values_total']}")
    print("\nЧЕМ КОРПУС ВИДА НЕ ПОКРЫТ СЛОВАРЁМ ТИПА УЗЛА V48 (прогон по настоящему коду):")
    print(f"   классы: {dict(corpus['v48_classes'])}")
    for reason, count in corpus["v48_reasons"].most_common(6):
        print(f"   причина ({count}): {reason}")
    print("\nЦЕНЫ КРУГА:")
    for d in only:
        print(f"   {d}: файлов {corpus['per_dump_files'].get(d, 0)}, байт "
              f"{corpus['per_dump_bytes'].get(d, 0)}, значений типа "
              f"{corpus['per_dump_values'].get(d, 0)}, записей индекса "
              f"{corpus['per_dump_index'].get(d, 0)}")
    print(f"ИТОГО байт: {sum(corpus['per_dump_bytes'].values())}")
    shared_uuid = sum(1 for ds in corpus["uuid_dumps"].values() if len(ds) > 1)
    shared_name = sum(1 for ds in corpus["name_dumps"].values() if len(ds) > 1)
    dup_inside = sum(corpus["per_dump_files"].get(d, 0) - corpus["per_dump_names"].get(d, 0)
                     for d in only)
    print(f"\nM1: различных uuid {len(corpus['uuids'])} при файлах {corpus['files']}; различных "
          f"имён {len(corpus['name_dumps'])}; uuid в 2+ выгрузках {shared_uuid}; имён в 2+ "
          f"выгрузках {shared_name}; повторов имён внутри выгрузки {dup_inside}")
    pairs = Counter(tuple(sorted(ds)) for ds in corpus["name_dumps"].values() if len(ds) > 1)
    print(f"пары коллизий имён: {dict(pairs)}")
    print("\nССЫЛКИ НА ВИД, УЖЕ ЗАПИСАННЫЕ СЛОЯМИ (живая БД):")
    for table, rows, entries in db_unresolved_defined_type_refs():
        print(f"   {table}: строк вида {rows}, записей класса defined_type_ref {entries}")
    print("ССЫЛКИ НА ВИД ИЗ ЧУЖИХ ВИДОВ КОРПУСА (подстрока `:DefinedType.`):")
    for dump, files_total, hits_total, per_dir in corpus_refs_to_view():
        print(f"   {dump}: файлов {files_total}, вхождений {hits_total}")
        for name, files, hits in per_dir:
            print(f"      {name}: файлов {files}, вхождений {hits}")
    print("СТРОКИ configuration_objects (точная нога):")
    for name, otype, count in db_index_counts():
        print(f"   {name} {otype}: {count}")
    print("\nСОСТОЯНИЕ ЖИВОЙ СХЕМЫ (объекты с именем defined):")
    for name, kind in db_schema_state():
        print(f"   {kind} {name}")
    print("\nXSD вида:")
    for h in xsd_probe() or ["   не найден ни в xsd-schemas, ни в xsd-docs"]:
        print(f"   {h}")
    print(f"\nРЕЕСТР ИНСТРУМЕНТОВ ЯДРА: {registry_tool_count()}")


def main():
    only = sys.argv[1:] or list(DUMPS)
    corpus = {"files": 0, "props": Counter(), "shapes": Counter(), "top_tags": Counter(),
              "internal_tags": Counter(), "generated_attrs": Counter(),
              "type_block_shapes": Counter(), "type_item_tags": Counter(),
              "type_multiplicity": Counter(), "value_forms": Counter(), "value_kinds": Counter(),
              "value_states": Counter(), "value_namespaces": Counter(), "qualifiers": Counter(),
              "qualifier_values": Counter(), "defined_type_resolved": Counter(),
              "target_names": Counter(), "unresolved_targets": Counter(),
              "other_forms": Counter(), "per_dump_values": {}, "per_dump_files": {},
              "per_dump_names": {},
              "per_dump_bytes": {}, "per_dump_index": {}, "names": Counter(),
              "uuids": Counter(), "uuid_dumps": defaultdict(set),
              "name_dumps": defaultdict(set), "directory_missing": [],
              "values_total": 0, "self_refs": 0, "defined_type_refs": 0, "dup_values": 0,
              "no_type_block": 0, "empty_comment": 0, "empty_synonym": 0,
              "max_values_per_file": 0, "errors": [], "sample_values": [],
              "v48_classes": Counter(), "v48_reasons": Counter()}
    for dump in only:
        probe_dump(dump, corpus)
    report(corpus, only)


if __name__ == "__main__":
    main()

