"""Замер формы контейнеров нормативного списка по реальным выгрузкам 1С (узел GROUP-SPEED).

Вопрос замера: являются ли 34 открытые позиции нормативного списка
«Структура конфигурации.txt» 34 разными задачами или немногими формами,
повторёнными много раз. Ответ нужен для оценки темпа: при одной группе в день
34 позиции дают ~34 дня, при одной форме на несколько групп — кратно меньше.

Метод (без 1С, только файлы выгрузки): для каждой позиции берётся каталог
контейнера выгрузки (`<выгрузка>/<Контейнер>/*.xml`), из файлов берётся проба,
разбирается корневой элемент и множество его прямых детей — это и есть форма
позиции; позиции группируются union-find по близости множеств
(Jaccard >= THRESHOLD).

Проба по умолчанию — 4 выгрузки (тот же круг, что у офлайн-проб узлов V5x),
перебирается аргументом --exports. Файлы больше MAX_FILE не разбираются, но
учитываются в числе и размере: форма берётся из разбираемых.

Запуск:
    python probes/misc/_position_shapes_probe.py
    python probes/misc/_position_shapes_probe.py --exports BP3
    python probes/misc/_position_shapes_probe.py --sample 20 --threshold 0.4
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET

EXPORTS_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_EXPORTS = ["BP3", "ZUP31", "UT11", "MinCfg"]
SAMPLE = 8
MAX_FILE = 4 * 1024 * 1024
THRESHOLD = 0.5
NS_RE = re.compile(r"^\{[^}]*\}")

# Позиция -> имя каталога контейнера выгрузки. Номера и порядок повторяют
# нормативный список «Структура конфигурации.txt» (47 позиций второго и третьего
# слоя); CLOSED — позиции, закрытые стадиями контракта (2.1–2.13).
POSITIONS: list[tuple[str, str, bool]] = [
    ("2.1", "Subsystems", True),
    ("2.2", "CommonModules", True),
    ("2.3", "SessionParameters", True),
    ("2.4", "Roles", True),
    ("2.5", "CommonAttributes", True),
    ("2.6", "ExchangePlans", True),
    ("2.7", "FilterCriteria", True),
    ("2.8", "EventSubscriptions", True),
    ("2.9", "ScheduledJobs", True),
    ("2.10", "Bots", True),
    ("2.11", "FunctionalOptions", True),
    ("2.12", "FunctionalOptionsParameters", True),
    ("2.13", "DefinedTypes", True),
    ("2.14", "SettingsStorages", False),
    ("2.15", "CommonCommands", False),
    ("2.16", "CommandGroups", False),
    ("2.17", "CommonForms", False),
    ("2.18", "CommonTemplates", False),
    ("2.19", "CommonPictures", False),
    ("2.20", "XDTOPackages", False),
    ("2.21", "WebServices", False),
    ("2.22", "HTTPServices", False),
    ("2.23", "WSReferences", False),
    ("2.24", "WebSocketClients", False),
    ("2.25", "IntegrationServices", False),
    ("2.26", "StyleItems", False),
    ("2.27", "Styles", False),
    ("2.28", "Languages", False),
    ("3", "Constants", False),
    ("4", "Catalogs", False),
    ("5", "Documents", False),
    ("5.1", "DocumentNumerators", False),
    ("5.2", "Sequences", False),
    ("6", "DocumentJournals", False),
    ("7", "Enums", False),
    ("8", "Reports", False),
    ("9", "DataProcessors", False),
    ("10", "ChartsOfCharacteristicTypes", False),
    ("11", "ChartsOfAccounts", False),
    ("12", "ChartsOfCalculationTypes", False),
    ("13", "InformationRegisters", False),
    ("14", "AccumulationRegisters", False),
    ("15", "AccountingRegisters", False),
    ("16", "CalculationRegisters", False),
    ("17", "BusinessProcesses", False),
    ("18", "Tasks", False),
    ("19", "ExternalDataSources", False),
]

# Структурные маркеры, которыми форма позиции различается содержательно.
MARKERS = [
    "Attributes", "TabularSections", "Forms", "Templates", "Commands",
    "ObjectModule", "ManagerModule", "FormCommandModule", "CommandModules",
    "Recalculations", "CalculationOrders", "BalancesAndTurnovers", "RecordSet",
    "Dimensions", "Resources", "InformationRegisters", "AccountingRegisters",
    "AccumulationRegisters", "CalculationRegisters", "ChartsOfCharacteristicTypes",
    "ChartsOfAccounts", "ChartsOfCalculationTypes", "BusinessProcesses", "Tasks",
    "Addresses", "AdditionalAttributes", "AdditionalProperties", "FolderForms",
    "NonStandardOutput", "Portals", "WebServices", "HTTPServices",
    "IntegrationServices", "Queues", "Routes", "Methods", "PacketInfo",
    "Versions", "Storages", "Settings", "Options", "Parameters", "Values",
    "Sections", "Groups", "Items", "Contents", "Properties", "ScriptText",
    "Description", "Synonym", "ToolTip", "Presentation", "Server", "CallOptions",
    "AutoUse", "DataSeparation",
]

POSITION_ORDER = {pos: i for i, (pos, _, _) in enumerate(POSITIONS)}

def strip_ns(tag: str) -> str:
    return NS_RE.sub("", tag)


def container_files(folder: str) -> list[str]:
    return sorted(
        os.path.join(folder, n)
        for n in os.listdir(folder)
        if n.lower().endswith(".xml") and n != "ConfigDumpInfo.xml"
    )


def sample_files(names: list[str], sample: int) -> list[str]:
    """Файлы пробы: все, если их не больше sample, иначе равномерная выборка + самый большой."""
    if len(names) <= sample:
        return list(names)
    step = len(names) / sample
    picked = [names[int(i * step)] for i in range(sample)]
    biggest = max(names, key=lambda p: os.path.getsize(p))
    if biggest not in picked:
        picked[-1] = biggest
    return picked


def read_child_tags(path: str, max_file: int, depth: int = 3) -> set[str] | None:
    """Множество тегов дерева на глубинах 2..depth.

    Файл объекта выгрузки 1С имеет корень-обёртку с единственным ребёнком, поэтому
    форма позиции — не прямые дети корня, а теги на два-три уровня глубже: один
    уровень даёт у всех контейнеров одно и то же значение (замер 05.11.2026).
    """
    try:
        if os.path.getsize(path) > max_file:
            return None
        root = ET.parse(path).getroot()
    except Exception:
        return None
    tags: set[str] = set()

    def walk(elem, level: int) -> None:
        for child in elem:
            tags.add(strip_ns(child.tag))
            if level < depth:
                walk(child, level + 1)

    walk(root, 1)
    tags.discard(strip_ns(root.tag))
    return tags


def collect(positions, exports, sample, max_file, depth=3) -> dict[str, dict]:
    """Сбор формы каждой позиции по выгрузкам: множества тегов, файлы, размеры."""
    out: dict[str, dict] = {}
    for pos, container, closed in positions:
        tags: set[str] = set()
        sigs: set[frozenset] = set()
        found_exports = 0
        files_total = 0
        sizes: list[int] = []
        unparsed = 0
        for export in exports:
            folder = os.path.join(EXPORTS_ROOT, export, container)
            if not os.path.isdir(folder):
                continue
            found_exports += 1
            names = container_files(folder)
            files_total += len(names)
            sizes.extend(os.path.getsize(p) for p in names)
            for path in sample_files(names, sample):
                child_tags = read_child_tags(path, max_file, depth)
                if child_tags is None:
                    unparsed += 1
                    continue
                tags |= child_tags
                sigs.add(frozenset(child_tags))
        out[pos] = {
            "pos": pos,
            "container": container,
            "closed": closed,
            "exports": found_exports,
            "files": files_total,
            "median_kb": round(statistics.median(sizes) / 1024, 1) if sizes else 0.0,
            "max_kb": round(max(sizes) / 1024, 1) if sizes else 0.0,
            "tags": tags,
            "sig_count": len(sigs),
            "unparsed": unparsed,
        }
    return out


def cluster(rows: dict[str, dict], threshold: float) -> list[list[str]]:
    """Union-find по близости множеств тегов: Jaccard >= threshold."""
    keys = list(rows)
    parent = {k: k for k in keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(keys):
        ta = rows[a]["tags"]
        if not ta:
            continue
        for b in keys[i + 1:]:
            tb = rows[b]["tags"]
            if not tb:
                continue
            union = len(ta | tb)
            if union and len(ta & tb) / union >= threshold:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb
    groups: dict[str, list[str]] = {}
    for k in keys:
        groups.setdefault(find(k), []).append(k)
    return [sorted(v, key=lambda p: POSITION_ORDER[p]) for v in groups.values()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Замер формы контейнеров нормативного списка")
    ap.add_argument("--exports", default=",".join(DEFAULT_EXPORTS))
    ap.add_argument("--sample", type=int, default=SAMPLE)
    ap.add_argument("--max-file", type=int, default=MAX_FILE)
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--depth", type=int, default=3)
    args = ap.parse_args()

    exports = [e.strip() for e in args.exports.split(",") if e.strip()]
    missing = [e for e in exports if not os.path.isdir(os.path.join(EXPORTS_ROOT, e))]
    if missing:
        print(f"выгрузок нет: {', '.join(missing)}")
        return 2
    print(f"выгрузки: {', '.join(exports)} | проба на контейнер: {args.sample} файла"
          f" | более {args.max_file // (1024 * 1024)} МБ не разбирается"
          f" | порог близости: {args.threshold}")

    rows = collect(POSITIONS, exports, args.sample, args.max_file, args.depth)
    print(f"глубина разбора формы: {args.depth} уровня")

    print("\n=== ПОЗИЦИЯ -> ФОРМА КОНТЕЙНЕРА ===")
    print("поз   контейнер                       выгр  файлов  медиан   макс  сигн детей маркеры")
    for pos, container, _ in POSITIONS:
        r = rows[pos]
        marks = [m for m in MARKERS if m in r["tags"]]
        print(f"{pos:<5} {container:<31} {r['exports']}/{len(exports)}  {r['files']:>6} "
              f"{r['median_kb']:>7} {r['max_kb']:>6} {r['sig_count']:>4}{len(r['tags']):>5} "
              f" {','.join(marks[:7])}{'...' if len(marks) > 7 else ''}")

    present = [pos for pos, _, _ in POSITIONS if rows[pos]["exports"] > 0]
    absent = [pos for pos, _, _ in POSITIONS if rows[pos]["exports"] == 0]
    groups = cluster({pos: rows[pos] for pos in present}, args.threshold)
    groups.sort(key=lambda g: -len(g))

    print(f"\n=== КЛАСТЕРЫ ФОРМЫ (Jaccard >= {args.threshold}) ===")
    for n, g in enumerate(groups, 1):
        open_pos = [pos for pos in g if not rows[pos]["closed"]]
        closed_pos = [pos for pos in g if rows[pos]["closed"]]
        common = set.intersection(*(rows[pos]["tags"] for pos in g)) if len(g) > 1 else set()
        print(f"\nкластер {n}: позиций {len(g)} — открыто {len(open_pos)}, закрыто {len(closed_pos)}")
        print(f"  открытые : {', '.join(open_pos) if open_pos else '—'}")
        if closed_pos:
            print(f"  закрытые : {', '.join(closed_pos)} — реализация уже есть")
        print(f"  файлов во всех выгрузках: {sum(rows[pos]['files'] for pos in g)}")
        if common:
            shown = sorted(common)[:12]
            print(f"  общее: {', '.join(shown)}{' ...' if len(common) > 12 else ''}")

    print("\n=== БЛИЖАЙШАЯ ЗАКРЫТАЯ ПОЗИЦИЯ (по общности формы) ===")
    print("открытая позиция          близкая закрытая        общих  Jaccard  своих тегов")
    closed_positions = [pos for pos, _, closed in POSITIONS if closed]
    reuse_map: dict[str, tuple[str, float]] = {}
    for pos, container, closed in POSITIONS:
        if closed or not rows[pos]["tags"]:
            continue
        best_pos, best_score, best_shared = "", 0.0, 0
        for cpos in closed_positions:
            tc = rows[cpos]["tags"]
            if not tc:
                continue
            shared = len(rows[pos]["tags"] & tc)
            union = len(rows[pos]["tags"] | tc)
            score = shared / union if union else 0.0
            if score > best_score:
                best_pos, best_score, best_shared = cpos, score, shared
        reuse_map[pos] = (best_pos, best_score)
        print(f"{pos:<5} {container:<21} {best_pos:<5} {rows[best_pos]['container'] if best_pos else '—':<19}"
              f" {best_shared:>6} {best_score:>8.2f} {len(rows[pos]['tags']):>10}")

    covered_by_reuse = sum(1 for pos, (_, score) in reuse_map.items() if score >= 0.5)
    print(f"\nоткрытых позиций с близкой закрытой (Jaccard >= 0.5): {covered_by_reuse}"
          f" из {len(reuse_map)}")

    open_present = [pos for pos in present if not rows[pos]["closed"]]
    open_groups = [g for g in groups if any(not rows[pos]["closed"] for pos in g)]
    print("\n=== ИТОГ ===")
    print(f"позиций норматива: {len(POSITIONS)} | контейнер есть хотя бы в одной выгрузке:"
          f" {len(present)} | нет ни в одной: {len(absent)}"
          f"{' (' + ', '.join(absent) + ')' if absent else ''}")
    print(f"закрыто стадиями: {sum(1 for _, _, c in POSITIONS if c)} | открыто и с формой"
          f" в выгрузке: {len(open_present)}")
    print(f"кластеров формы среди открытых: {len(open_groups)}"
          f" | наибольший: {len(open_groups[0]) if open_groups else 0} позиций")
    sizes = sorted((len(g) for g in open_groups), reverse=True)
    print(f"размеры кластеров открытых: {sizes}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())


