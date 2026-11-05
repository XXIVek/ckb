#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V57, шаг П0: замеры круга позиции 2.12 «Параметры функциональных опций».

Вид — `FunctionalOptionsParameter` (каталог `FunctionalOptionsParameters/`, перечень заголовка
`configurations.functional_options_parameters`). Зонд только читает: ни в БД, ни в файлы
выгрузок не пишет. Отвечает на вопросы, без которых модель записи вида выдумывалась бы:

1. круг вида по четырём выгрузкам — файлы регистрации, каталоги содержимого (форм, макетов,
   команд, модулей), записи индекса состава; сверка ног между собой и расхождения
   `file_only` / `index_only`; псевдозаписей и детей индекса — отдельным числом;
2. третья нога — перечень заголовка `configurations.functional_options_parameters` (живая БД,
   его заполняет стадия S2) и строки `configuration_objects` по ТОЧНОМУ `object_type`.
   Предикат обязано держать точное имя вида: `FunctionalOptionsParameter` начинается с того же
   слова, что соседний вид `FunctionalOption` (позиция 2.11, узел V56), — фильтр по началу
   имени слил бы два круга (замер `_v56_m1_probe.py`, раздел 1.2 плана V56);
3. словарь свойств узла вида (теги `Properties`) и ФОРМА каждого значения — пустое, скаляр,
   bool, многоязык, блок (форма задаёт вид разбора);
4. блок `Use` — чем он отличается от `Content` вида 2.11: элемент перечня здесь `<xr:Item>` с
   атрибутом `xsi:type`, а не `<xr:Object>`; форма элемента, кратность целей, дубли внутри
   файла, пустой блок, класс цели и ФОРМА адреса цели (объект / срез измерения / реквизит),
   разрешимость индексом состава (`exact` / `prefix_only` / `unresolved`);
5. связан ли круг 2.11 с кругом 2.12: ссылается ли хоть один `Location` функциональной опции
   на параметр, упоминает ли корневой `Configuration.xml` вид 2.12, есть ли у самого параметра
   цель вида `FunctionalOption`. Ответ решает, появится ли в схеме ссылка между кругами или её
   не будет (прецедент V56: внешнего ключа нет, потому что слои целей не загружены);
6. кросс-выгрузочные коллизии `uuid` и имён (M1) — ключ версионности выбирается по замеру, а
   не по схеме соседа (прецеденты V52/V53/V54/V55/V56);
7. цена круга (байты файлов регистрации) — порог, при котором круг резали бы на группы
   запроса (прецедент Q5 узла V48, замеры 1.4 узлов V50/V52/V53/V54/V56);
8. XSD вида: поиск по `xsd-schemas/` и `xsd-docs` — замкнут ли словарь свойств схемой, если
   корпуса для замыкания не хватает (файлов круга может быть меньше порога в 20 — тогда
   замыкает только XSD, а он отсутствует у всех узлов группы E).

Граница поиска связей (пункт 5): сканируются файлы круга 2.11 и корневой `Configuration.xml`
каждой выгрузки, а НЕ вся выгрузка целиком — полный обход BGU2/BP3 занял бы минуты и не
назвал бы ни одного нового состояния, а ссылки вида 2.12 в модели 1С существуют именно через
`Location` опции и через перечень заголовка.

Запуск:  python _v57_p0_probe.py            # все четыре выгрузки
         python _v57_p0_probe.py MinCfg     # одна
"""

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
VIEW_DIR = "FunctionalOptionsParameters"
VIEW_TAG = "FunctionalOptionsParameter"
SIBLING_TAG = "FunctionalOption"
VIEW_LIST_COLUMN = "configurations.functional_options_parameters"
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
          password="Sta090860")

XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
UUID_RE = re.compile(r'^\s*<' + VIEW_TAG + r'\s+uuid="([0-9a-fA-F-]{36})"', re.MULTILINE)
INDEX_VIEW_RE = re.compile(
    r'<Metadata name="' + VIEW_TAG + r'\.([^"]+)" id="([0-9a-fA-F-]{36})"'
)
SIBLING_INDEX_RE = re.compile(
    r'<Metadata name="' + SIBLING_TAG + r'\.([^"]+)" id="([0-9a-fA-F-]{36})"'
)
# срезы адреса цели: объект / разрез измерения / ресурс регистра / реквизит / ТЧ / прочее
TARGET_MARKERS = {
    "Dimension": "dimension", "Resource": "resource", "Attribute": "attribute",
    "TabularSection": "tabular_section", "Enum": "enum_value", "Command": "command",
    "Form": "form", "Template": "template",
}


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


def target_form(value):
    """Форма адреса цели: `object` (два сегмента) либо срез по известному маркеру."""
    parts = value.split(".")
    if len(parts) <= 2:
        return "object" if len(parts) == 2 else "bare"
    marker = TARGET_MARKERS.get(parts[2])
    return marker or "other:" + parts[2]


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
    """Все имена индекса состава выгрузки — чтобы разрешить цели блока `Use`."""
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


def resolve_target(value, index_names):
    """Состояние разрешения цели по индексу состава: exact / prefix_only / unresolved.

    Тот же словарь, что у узлов V50/V52/V56: цель существует ровно тогда, когда её полное
    имя есть в индексе; `prefix_only` — когда в индексе есть префикс цели, но нет самой цели.
    """
    if not value:
        return "empty_value", ""
    if value in index_names:
        return "exact", value
    parts = value.split(".")
    while parts:
        parts.pop()
        prefix = ".".join(parts)
        if prefix and prefix in index_names:
            return "prefix_only", prefix
    return "unresolved", ""



def note_target(info, value, index_names):
    """Класс цели, форма адреса и состояние разрешения цели по индексу состава."""
    info["use_classes"][value.split(".")[0]] += 1
    info["use_target_forms"][target_form(value)] += 1
    state, _ = resolve_target(value, index_names)
    info["use_states"][state] += 1
    if state != "exact":
        info["use_targets"][f"{state} {value}"] += 1


def probe_registration_file(path, index_names):
    """Словарь свойств узла вида + формы значений + блок `Use` (цели применения параметра)."""
    info = {"view_tag": "", "view_uuid": "", "props": Counter(), "shapes": Counter(),
            "top_tags": Counter(), "use_forms": Counter(), "use_item_tags": Counter(),
            "use_item_xsi": Counter(), "use_item_forms": Counter(), "use_states": Counter(),
            "use_classes": Counter(), "use_target_forms": Counter(), "use_targets": Counter(),
            "use_per_file": [], "use_dup": 0, "use_empty_files": 0,
            "children": Counter(), "child_uuid": Counter(),
            "empty_comment": 0, "no_synonym": 0, "error": ""}
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
        props = None
        children = None
        for block in meta:
            tag = local(block.tag)
            info["top_tags"][tag] += 1
            if tag == "Properties":
                props = block
            elif tag == "ChildObjects":
                children = block
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
                info["no_synonym"] += 1
            if tag != "Use":
                continue
            kids = list(prop)
            if not kids:
                if text:
                    info["use_forms"]["scalar"] += 1
                    note_target(info, text, index_names)
                else:
                    info["use_forms"]["empty_element"] += 1
                    info["use_empty_files"] += 1
                continue
            info["use_forms"]["block"] += 1
            seen = set()
            for item in kids:
                info["use_item_tags"][local(item.tag)] += 1
                info["use_item_xsi"][item.get(XSI_TYPE) or "<без xsi:type>"] += 1
                info["use_item_forms"]["text" if not list(item) else "nested"] += 1
                value = (item.text or "").strip()
                if not value:
                    info["use_states"]["empty_value"] += 1
                    continue
                note_target(info, value, index_names)
                if value in seen:
                    info["use_dup"] += 1
                seen.add(value)
            info["use_per_file"].append(len(kids))
        if children is not None:
            for child in children:
                info["children"][local(child.tag)] += 1
                if child.get("uuid"):
                    info["child_uuid"][local(child.tag)] += 1
    return info

def content_layout(view, dirs):
    """Раскладка каталогов содержимого вида: есть ли формы, макеты, команды, модули."""
    layouts, suffixes, sizes, empty_dirs = Counter(), Counter(), Counter(), []
    for name in dirs:
        directory = view / name
        files = [p for p in directory.rglob("*") if p.is_file()]
        if not files:
            empty_dirs.append(name)
            continue
        rel = tuple(sorted(
            (p.parent.relative_to(directory).parts or ("<корень>",)) for p in files))
        layouts[rel] += 1
        for p in files:
            suffixes[p.suffix.lower() or "<без расширения>"] += 1
            sizes[p.suffix.lower() or "<без расширения>"] += p.stat().st_size
    return layouts, suffixes, sizes, empty_dirs


def xsd_probe():
    """Есть ли XSD вида: по имени файла и по упоминанию тега в тексте схем."""
    found = []
    for root in XSD_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if VIEW_TAG in path.name or VIEW_DIR.lower() in path.name.lower():
                found.append(f"{path.relative_to(REPO_ROOT)} (имя файла)")
            if path.suffix.lower() == ".xsd":
                try:
                    if VIEW_TAG in path.read_text(encoding="utf-8", errors="ignore"):
                        found.append(f"{path.relative_to(REPO_ROOT)} (упоминание в тексте)")
                except Exception:  # noqa: BLE001
                    continue
    return found


def cross_kind_links(dump):
    """Связан ли круг 2.11 с кругом 2.12: `Location` опции и корень конфигурации.

    Граница: сканируются файлы круга 2.11 и `Configuration.xml` выгрузки, а не вся выгрузка.
    """
    out = {"location_to_parameter": 0, "location_total": 0, "location_classes": Counter(),
           "config_names": [], "config_error": ""}
    options = DUMP_ROOT / dump / "FunctionalOptions"
    if options.is_dir():
        for path in sorted(options.glob("*.xml")):
            try:
                root = ET.parse(str(path)).getroot()
            except Exception:  # noqa: BLE001
                continue
            for prop in root.iter():
                if local(prop.tag) != "Location":
                    continue
                out["location_total"] += 1
                value = (prop.text or "").strip()
                if value.startswith(VIEW_TAG + "."):
                    out["location_to_parameter"] += 1
                out["location_classes"][value.split(".")[0] if value else "<пусто>"] += 1
    config = DUMP_ROOT / dump / "Configuration.xml"
    if config.is_file():
        try:
            text = config.read_text(encoding="utf-8-sig", errors="replace")
            out["config_names"] = sorted(set(
                re.findall(r"<" + VIEW_TAG + r">([^<]+)</" + VIEW_TAG + r">", text)))
        except Exception as exc:  # noqa: BLE001
            out["config_error"] = f"{type(exc).__name__}: {exc}"
    else:
        out["config_error"] = "Configuration.xml нет"
    return out


def header_list(dump):
    """Перечень заголовка `configurations.functional_options_parameters` (третья нога)."""
    import psycopg2

    wanted = DUMP_TO_CONFIGURATION.get(dump)
    if not wanted:
        return None, f"имя выгрузки не из словаря соответствия: {dump}"
    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return None, f"БД недоступна: {type(exc).__name__}: {exc}"
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT functional_options_parameters FROM configurations WHERE name = %s",
                (wanted,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None, f"строки заголовка с именем {wanted!r} в БД нет"
    if row[0] is None:
        return [], "перечень заголовка NULL (стадия S2 его не заполнила)"
    return list(row[0]), ""


def db_index_counts():
    """Строки `configuration_objects` по обоим видам — точным предикатом, не по префиксу."""
    import psycopg2

    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return [(f"БД недоступна: {type(exc).__name__}", "", 0)]
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.name, o.object_type, count(*) FROM configuration_objects o "
                "JOIN configurations c ON c.id = o.configuration_id "
                "WHERE o.object_type IN (%s, %s) GROUP BY 1, 2 ORDER BY 1, 2",
                (VIEW_TAG, SIBLING_TAG),
            )
            return list(cur.fetchall())
    finally:
        conn.close()



def probe_dump(dump, corpus):
    print("=" * 78)
    print(f"ВЫГРУЗКА {dump}")
    links = cross_kind_links(dump)
    print(f"связь круга 2.11 → 2.12: `Location` опций {links['location_total']}, из них на "
          f"параметр {links['location_to_parameter']}; классы Location "
          f"{dict(links['location_classes'])}")
    print(f"перечень корня `Configuration.xml` (<{VIEW_TAG}>): имён "
          f"{len(links['config_names'])} {links['config_names'][:3]} {links['config_error']}")
    corpus["links"].update(links["location_classes"])
    corpus["location_total"] += links["location_total"]
    corpus["location_to_parameter"] += links["location_to_parameter"]
    corpus["config_names_by_dump"][dump] = set(links["config_names"])

    view = DUMP_ROOT / dump / VIEW_DIR
    index_views, index_children, index_pseudo, index_error = index_entries(dump)
    index_names = index_all_names(dump)
    if index_error:
        print(f"⚠️ {index_error}")
    if not view.is_dir():
        print(f"каталога {VIEW_DIR}/ нет; записей индекса состава вида: {len(index_views)}; "
              f"псевдозаписей индекса: {sum(index_pseudo.values())}")
        corpus["no_dir_dumps"] += 1
        corpus["index_views_no_dir"] += len(index_views)
        corpus["index_pseudo_no_dir"] += sum(index_pseudo.values())
        return
    files = sorted(p for p in view.iterdir() if p.suffix.lower() == ".xml" and p.is_file())
    dirs = sorted(p.name for p in view.iterdir() if p.is_dir())
    print(f"файлов регистрации: {len(files)}, каталогов содержимого: {len(dirs)}, "
          f"записей индекса вида: {len(index_views)}, "
          f"псевдозаписей индекса: {sum(index_pseudo.values())}")

    file_names = {p.stem for p in files}
    index_name_set = set(index_views)
    print(f"нога файлов: {len(file_names)}; нога индекса: {len(index_name_set)}; "
          f"file_only={sorted(file_names - index_name_set)[:5]} "
          f"index_only={sorted(index_name_set - file_names)[:5]}")
    empty_index_uuid = sum(1 for v in index_views.values() if not v[0])
    print(f"пустых uuid в индексе: {empty_index_uuid}")
    print(f"псевдозаписи индекса по форме: {dict(index_pseudo)}")
    orphan_children = sorted(set(index_children) - index_name_set)
    print(f"детских записей вида в индексе: {len(index_children)}; без строки вида: "
          f"{len(orphan_children)} {orphan_children[:5]}")
    layouts, suffixes, sizes, empty_dirs = content_layout(view, dirs)
    print(f"раскладка каталогов содержимого — {len(layouts)} вариантов:")
    for key, count in layouts.most_common(12):
        print(f"    {str(key):48} {count}")
    print(f"расширений файлов содержимого: {dict(suffixes)}; байты: {dict(sizes)}; "
          f"каталогов без единого файла: {len(empty_dirs)} {empty_dirs[:5]}")
    reg_bytes = sum(p.stat().st_size for p in files)
    other_bytes = sum(p.stat().st_size for p in view.rglob("*") if p.is_file()) - reg_bytes
    print(f"цена круга: файлов регистрации {reg_bytes} байт, прочего содержимого {other_bytes} байт")

    agg_props, shapes, view_tags, uuids = Counter(), Counter(), Counter(), Counter()
    top_tags = Counter()
    use_forms, use_item_tags, use_item_xsi, use_item_forms = (Counter(), Counter(), Counter(),
                                                              Counter())
    use_states, use_classes, use_target_forms, use_targets = (Counter(), Counter(), Counter(),
                                                             Counter())
    per_file_counts = []
    errors = Counter()
    use_files = empty_use_files = dup_total = 0
    empty_comment = no_synonym = 0
    children, child_uuid = Counter(), Counter()
    uuid_by_name = {}
    for path in files:
        info = probe_registration_file(path, index_names)
        if info["error"]:
            errors[info["error"]] += 1
            continue
        view_tags[info["view_tag"]] += 1
        uuids["nonempty" if info["view_uuid"] else "empty"] += 1
        uuid_by_name[path.stem] = (info["view_uuid"] or "").lower()
        index_uuid = (index_views.get(path.stem, ("", ""))[0] or "").lower()
        if index_uuid and index_uuid == (info["view_uuid"] or "").lower():
            uuids["совпадает с индексом"] += 1
        elif index_uuid:
            uuids["РАСХОДИТСЯ с индексом"] += 1
        top_tags.update(info["top_tags"])
        agg_props.update(info["props"])
        for key, count in info["shapes"].items():
            shapes[key] += count
        use_forms.update(info["use_forms"])
        use_item_tags.update(info["use_item_tags"])
        use_item_xsi.update(info["use_item_xsi"])
        use_item_forms.update(info["use_item_forms"])
        use_states.update(info["use_states"])
        use_classes.update(info["use_classes"])
        use_target_forms.update(info["use_target_forms"])
        use_targets.update(info["use_targets"])
        if info["use_per_file"]:
            use_files += 1
            per_file_counts.extend(info["use_per_file"])
        empty_use_files += info["use_empty_files"]
        dup_total += info["use_dup"]
        empty_comment += info["empty_comment"]
        no_synonym += info["no_synonym"]
        children.update(info["children"])
        child_uuid.update(info["child_uuid"])

    print(f"узел вида: {dict(view_tags)}; uuid: {dict(uuids)}; файлов с ошибкой: {dict(errors)}")
    print(f"верхний уровень узла вида: {dict(top_tags)}")
    print(f"словарь свойств узла вида — {len(agg_props)} имён тегов (файлов круга: {len(files)})")
    for tag, count in sorted(agg_props.items(), key=lambda kv: -kv[1]):
        forms = ", ".join(f"{s}×{c}" for s, c in sorted(shapes.items()) if s.startswith(tag + "="))
        print(f"    {tag:22} в {count:4} файлах ({forms})")
    print(f"форма Use: {dict(use_forms)}; пустых элементов: {empty_use_files}; "
          f"файлов с непустым: {use_files}; дублей целей внутри файла: {dup_total}")
    print(f"элементы перечня Use: теги {dict(use_item_tags)}; xsi:type {dict(use_item_xsi)}; "
          f"форма содержимого {dict(use_item_forms)}")
    print(f"состояния целей Use: {dict(use_states)}; классы: {dict(use_classes)}")
    print(f"формы адреса целей Use: {dict(use_target_forms)}")
    if per_file_counts:
        print(f"целей на файл: мин {min(per_file_counts)}, макс {max(per_file_counts)}, "
              f"всего {sum(per_file_counts)} на {len(per_file_counts)} файлов")
    print(f"целей Use кроме разрешённых (top): {use_targets.most_common(6)}")
    print(f"пустых Comment: {empty_comment}; пустых Synonym: {no_synonym}")
    print(f"дети в блоке ChildObjects: {dict(children)}; с uuid: {dict(child_uuid)}")

    corpus["files"] += len(files)
    corpus["dirs"] += len(dirs)
    corpus["index_views"] += len(index_views)
    corpus["index_pseudo"] += sum(index_pseudo.values())
    corpus["reg_bytes"] += reg_bytes
    corpus["other_bytes"] += other_bytes
    corpus["props"].update(agg_props)
    corpus["use_states"].update(use_states)
    corpus["use_classes"].update(use_classes)
    corpus["use_target_forms"].update(use_target_forms)
    corpus["use_item_tags"].update(use_item_tags)
    corpus["use_item_xsi"].update(use_item_xsi)
    corpus["per_file"].extend(per_file_counts)
    corpus["use_files"] += use_files
    corpus["empty_use"] += empty_use_files
    corpus["dups"] += dup_total
    corpus["names"].update(file_names)
    corpus["names_by_dump"][dump] = file_names
    corpus["uuid_by_dump"][dump] = {k: v for k, v in uuid_by_name.items() if v}





def main():
    dumps = tuple(sys.argv[1:]) or DUMPS
    unknown = [d for d in dumps if not (DUMP_ROOT / d).is_dir()]
    if unknown:
        print(f"выгрузок нет: {unknown}; доступны: {list(DUMPS)}")
        return 2
    print(f"круг позиции 2.12: каталог {VIEW_DIR}/, тег вида {VIEW_TAG}, перечень заголовка "
          f"{VIEW_LIST_COLUMN} (третья нога — живая БД ниже); соседний вид для сверки предиката "
          f"— {SIBLING_TAG} (позиция 2.11, узел V56 закрыт)")
    corpus = {"files": 0, "dirs": 0, "index_views": 0, "index_pseudo": 0, "no_dir_dumps": 0,
              "index_views_no_dir": 0, "index_pseudo_no_dir": 0, "reg_bytes": 0,
              "other_bytes": 0, "props": Counter(), "use_states": Counter(),
              "use_classes": Counter(), "use_target_forms": Counter(),
              "use_item_tags": Counter(), "use_item_xsi": Counter(), "per_file": [],
              "use_files": 0, "empty_use": 0, "dups": 0, "names": set(),
              "names_by_dump": {}, "uuid_by_dump": {}, "links": Counter(),
              "location_total": 0, "location_to_parameter": 0, "config_names_by_dump": {}}
    for dump in dumps:
        probe_dump(dump, corpus)

    print("=" * 78)
    print("ИТОГ ПО КОРПУСУ")
    print(f"выгрузок просмотрено: {len(dumps)}; без каталога вида: {corpus['no_dir_dumps']}; "
          f"файлов регистрации: {corpus['files']}; каталогов содержимого: {corpus['dirs']}")
    print(f"записей индекса вида: {corpus['index_views']}; псевдозаписей индекса: "
          f"{corpus['index_pseudo']}; записей индекса при отсутствии каталога: "
          f"{corpus['index_views_no_dir']} (псевдых: {corpus['index_pseudo_no_dir']})")
    print(f"байтов файлов регистрации: {corpus['reg_bytes']}; байтов прочего содержимого: "
          f"{corpus['other_bytes']}")
    print(f"словарь свойств по корпусу — {len(corpus['props'])} имён тегов: "
          f"{dict(sorted(corpus['props'].items(), key=lambda kv: -kv[1]))}")
    print(f"Use по корпусу: состояний целей {dict(corpus['use_states'])}; классов "
          f"{dict(corpus['use_classes'])}; форм адреса {dict(corpus['use_target_forms'])}")
    print(f"Use: элементов перечня {dict(corpus['use_item_tags'])}; xsi:type "
          f"{dict(corpus['use_item_xsi'])}; файлов с непустым перечнем: {corpus['use_files']}; "
          f"пустых перечней: {corpus['empty_use']}; дублей внутри файла: {corpus['dups']}")
    if corpus["per_file"]:
        print(f"целей применения на файл: мин {min(corpus['per_file'])}, "
              f"макс {max(corpus['per_file'])}, всего {sum(corpus['per_file'])}")
    print(f"связь кругов: `Location` опций {corpus['location_total']}, из них на параметр "
          f"{corpus['location_to_parameter']}; классы Location {dict(corpus['links'])}; "
          f"имён вида в перечне корня Configuration.xml: "
          f"{sum(len(v) for v in corpus['config_names_by_dump'].values())}")

    print("=" * 78)
    print("ТРЕТЬЯ НОГА: ПЕРЕЧЕНЬ ЗАГОЛОВКА (живая БД) И СТРОКИ configuration_objects")
    for dump in dumps:
        names, err = header_list(dump)
        if err:
            print(f"⚠️ {dump}: {err}")
            continue
        header = set(names)
        files = corpus["names_by_dump"].get(dump, set())
        root = corpus["config_names_by_dump"].get(dump, set())
        print(f"{dump}: перечня {len(header)}; файлов {len(files)}; "
              f"file_only={sorted(files - header)[:5]} header_only={sorted(header - files)[:5]}")
        print(f"    корень `Configuration.xml` перечней: {len(root)}; "
              f"root_only={sorted(root - header)[:5]} root_missing={sorted(header - root)[:5]}")
    for row in db_index_counts():
        print(f"    {row}")

    print("=" * 78)
    print("КРОСС-ВЫГРУЗОЧНЫЕ КОЛЛИЗИИ (M1)")
    uuid_map = defaultdict(set)
    name_map = defaultdict(set)
    for dump in dumps:
        for name, uuid in corpus["uuid_by_dump"].get(dump, {}).items():
            name_map[name].add(dump)
            uuid_map[uuid].add(dump)
    shared_uuid = {u: sorted(d) for u, d in uuid_map.items() if len(d) > 1}
    shared_name = {n: sorted(d) for n, d in name_map.items() if len(d) > 1}
    pairs = defaultdict(int)
    for src in list(shared_uuid.values()) + list(shared_name.values()):
        pairs[tuple(src)] += 1
    print(f"различных uuid по корпусу: {len(uuid_map)}; различных имён: {len(name_map)}")
    print(f"uuid в двух и более выгрузках: {len(shared_uuid)}; имён в двух и более: "
          f"{len(shared_name)}; пар выгрузок: {dict(pairs)}")
    print(f"примеров общих имён: {list(shared_name.items())[:3]}")

    print("=" * 78)
    verdict = "НЕТ" if corpus["files"] < 20 else "да"
    print(f"ЗАМЫКАЕТСЯ ЛИ СЛОВАРЬ СВОЙСТВ КОРПУСОМ: {verdict} — файлов круга {corpus['files']}; "
          "порог прогона 20 файлов; если корпус меньше порога, словарь держится только этим "
          "корпусом, и незнакомый тег обязан оставаться значением с состоянием "
          "(unknown_tag / unknown_value), а не отказом записи")
    found = xsd_probe()
    print(f"XSD вида по маске имени и по упоминанию в тексте XSD: "
          f"{found if found else 'не найдено ни одного файла'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
