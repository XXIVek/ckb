#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_v59_p0_frame_probe.py — форма регистрационных файлов позиций пакета 1 (каркас).

Зачем. Пакетная загрузка позиций строится спецификацией позиции (контейнер выгрузки,
тег вида, таблица, ключ, колонки, ожидаемые счётчики). Спецификация не пишется по
памяти: она выводится из фактической формы файлов. Этот зонд снимает по четырём
выгрузкам для каждой позиции пакета 1 (кластер 1 по замеру формы
`probes/misc/_position_shapes_probe.py`, 05.11.2026):

  1. есть ли контейнер и сколько в нём файлов, чем именно (по расширениям);
  2. каким тегом вида оканчивается цепочка `MetaDataObject/...` — факт, а не догадка;
  3. какие свойства встречаются в файле вида и в какой доле файлов: это будущие
     колонки, и «свойство есть не во всех файлах» обязано быть названо числом;
  4. какие вложенные блоки (`Attributes`, `Forms`, `Templates`, …) встречаются — это
     круг пакета 2, он называется сейчас, чтобы каркас под пакет 1 не переделывать;
  5. содержимое вида (`Ext/`, `.bin`, `.png`, `.xsd`) — позиции с содержимым требуют
     отдельного круга, и это граница, а не деталь.

Вывод — таблица на позицию и JSON для повторного чтения. Вывод пишется в `_scratch/`
(узел ROOT-FILES), сам зонд живёт в `probes/v59/` (правило `probes/README.md`).

Запуск из корня репозитория:
    python probes/v59/_v59_p0_frame_probe.py
    python probes/v59/_v59_p0_frame_probe.py --positions 2.26,2.27 --exports BP3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "_scratch"

EXPORTS_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_EXPORTS = ["BP3", "ZUP31", "UT11", "MinCfg"]

# Позиции пакета 1. Контейнер назван нормативным списком
# (`C:\1C_LLM\Структура конфигурации.txt`), тег вида НЕ задаётся — его называет замер.
POSITIONS = {
    "2.18": ("CommonTemplates", "Общие макеты"),
    "2.19": ("CommonPictures", "Общие картинки"),
    "2.20": ("XDTOPackages", "XDTO-пакеты"),
    "2.23": ("WSReferences", "WS-ссылки"),
    "2.25": ("IntegrationServices", "Сервисы интеграции"),
    "2.26": ("StyleItems", "Элементы стиля"),
    "2.27": ("Styles", "Стили"),
    "2.28": ("Languages", "Языки"),
    "5.2": ("Sequences", "Последовательности"),
    "19": ("ExternalDataSources", "Внешние источники данных"),
}

MAX_FILE = 2_000_000      # файл больше не разбирается, но называется числом байт
MAX_SAMPLES = 4           # файлов вида на позицию в одной выгрузке

MAX_FILE = 2_000_000      # файл больше не разбирается, но называется числом байт
MAX_SAMPLES = 4           # файлов вида на позицию в одной выгрузке

# Файл регистрации вида. Узел V59 (замер `_v59_p0_frame_probe.py`): позиции пакета 1
# пишутся файлом `<Имя>.xml`, а не `<Имя>.mdo`, как виды узлов V48–V58 — поэтому круг
# файлов регистрации называется расширением, а не одним расширением прежних узлов.
REGISTRATION_EXTENSIONS = {".mdo", ".xml"}



def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def walk_files(folder: Path):
    for dirpath, _dirs, files in os.walk(folder):
        for name in files:
            yield Path(dirpath) / name


def shape_of(path: Path) -> dict:
    """Цепочка до тега вида, свойства и вложенные блоки одного файла регистрации."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001 — отказ чтения называется, а не пропускается
        return {"error": f"{type(exc).__name__}: {exc}"}

    chain = [strip_ns(root.tag)]
    node = root
    while len(node) == 1 and strip_ns(node[0].tag) not in ("Properties", "ChildObjects"):
        node = node[0]
        chain.append(strip_ns(node.tag))

    props: Counter = Counter()
    blocks: Counter = Counter()
    for child in node:
        tag = strip_ns(child.tag)
        props[tag] += 1
        for sub in child:
            blocks[f"{tag}/{strip_ns(sub.tag)}"] += 1
    return {"chain": chain, "props": props, "blocks": blocks}


def new_entry() -> dict:
    return {"found": False, "by_ext": Counter(), "bytes": 0, "registration": 0,
            "content": 0, "kinds": Counter(), "props": Counter(), "props_in": Counter(),
            "blocks": Counter(), "files": 0, "sampled": 0, "too_big": 0,
            "max_bytes": 0, "errors": []}


def measure(position: str, container: str, exports) -> dict:
    per_export = {}
    agg_props_in: Counter = Counter()
    agg_blocks: Counter = Counter()
    agg_kinds: Counter = Counter()
    sampled_total = 0
    for export in exports:
        folder = Path(EXPORTS_ROOT) / export / container
        entry = new_entry()
        entry["found"] = folder.is_dir()
        per_export[export] = entry
        if not entry["found"]:
            continue
        samples = []
        for path in walk_files(folder):
            ext = path.suffix.lower() or "<без расширения>"
            entry["by_ext"][ext] += 1
            size = path.stat().st_size if path.exists() else 0
            entry["bytes"] += size
            entry["max_bytes"] = max(entry["max_bytes"], size)
            entry["files"] += 1
            # Узел V59: регистрацией является файл ВЕРХНЕГО уровня `<Имя>.xml`; XML внутри
            # `Ext/` (`Picture.xml`, `Template.xml`, `WSDefinition.xml`) — содержимое вида,
            # и относился к регистрации, пока круг считался по расширению рекурсивно
            # (замер `--mode layout`: CommonPictures BP3 — 2029 объектов против 4058 файлов).
            if ext in REGISTRATION_EXTENSIONS and path.parent == folder:
                entry["registration"] += 1
                if len(samples) < MAX_SAMPLES:
                    samples.append(path)
            else:
                entry["content"] += 1
        for path in samples:
            if path.stat().st_size > MAX_FILE:
                entry["too_big"] += 1
                continue
            shape = shape_of(path)
            if "error" in shape:
                entry["errors"].append(f"{path.name}: {shape['error']}")
                continue
            entry["sampled"] += 1
            entry["kinds"][" → ".join(shape["chain"][1:])] += 1
            for tag, count in shape["props"].items():
                entry["props"][tag] += count
                entry["props_in"][tag] += 1
            for tag, count in shape["blocks"].items():
                entry["blocks"][tag] += count
        agg_props_in.update(entry["props_in"])
        agg_blocks.update(entry["blocks"])
        agg_kinds.update(entry["kinds"])
        sampled_total += entry["sampled"]
    return {
        "position": position, "container": container, "title": POSITIONS[position][1],
        "totals": {
            "exports_found": sum(1 for e in per_export.values() if e["found"]),
            "files": sum(e["files"] for e in per_export.values()),
            "registration": sum(e["registration"] for e in per_export.values()),
            "content": sum(e["content"] for e in per_export.values()),
            "bytes": sum(e["bytes"] for e in per_export.values()),
        },
        "per_export": {exp: {
            "found": e["found"], "files": e["files"], "registration": e["registration"],
            "content": e["content"], "by_ext": dict(e["by_ext"]), "kinds": dict(e["kinds"]),
            "max_bytes": e["max_bytes"], "too_big": e["too_big"], "errors": e["errors"],
        } for exp, e in per_export.items()},
        "kinds": dict(agg_kinds),
        "sampled_total": sampled_total,
        "properties": {tag: {"files": n, "of_sampled": f"{n}/{sampled_total}"}
                       for tag, n in agg_props_in.items()},
        "blocks": dict(agg_blocks),
    }


def registration_counts(container: str, exports) -> dict:
    """Число объектов позиции по выгрузке: файлы регистрации верхнего уровня.

    Одна функция на зонд и на проверку `tools/check_position_frame.py`: счётчики
    спецификации и их сверка считаются одним и тем же способом, иначе проверка
    подтверждала бы круг другим определением, чем тот, которым круг измерялся.
    """
    out = {}
    for export in exports:
        folder = Path(EXPORTS_ROOT) / export / container
        if not folder.is_dir():
            out[export] = None
            continue
        out[export] = sum(1 for entry in folder.iterdir()
                          if entry.is_file()
                          and entry.suffix.lower() in REGISTRATION_EXTENSIONS)
    return out


def layout(position: str, container: str, exports) -> None:
    """Где у позиции файл регистрации, а где содержимое (режим `--mode layout`).

    Узел V59. Прежний замер формы (`probes/misc/_position_shapes_probe.py`) считал
    файл регистрации по глубине дерева и попадал на содержимое `Ext/` — для позиций
    с содержимым это давало ложную «плоскую форму». Здесь разделяется прямо: запись
    верхнего уровня каталога (каталог объекта или файл `<Имя>.xml`) против содержимого
    внутри неё, и называется корневой тег файла верхнего уровня, если он XML.
    """
    print("\nРазложение каталога позиции (регистрация против содержимого)")
    print("-" * 78)
    for export in exports:
        folder = Path(EXPORTS_ROOT) / export / container
        if not folder.is_dir():
            print(f"  {export}: контейнера нет")
            continue
        entries = sorted(folder.iterdir(), key=lambda p: p.name)
        dirs = [e for e in entries if e.is_dir()]
        files = [e for e in entries if e.is_file()]
        print(f"  {export}: верхних записей {len(entries)} "
              f"(каталогов объектов {len(dirs)}, файлов {len(files)})")
        for entry in files[:2]:
            root_tag = "<не XML>"
            if entry.suffix.lower() in REGISTRATION_EXTENSIONS:
                shape = shape_of(entry)
                root_tag = (" → ".join(shape.get("chain", []))
                            if "error" not in shape else shape["error"])
            print(f"    файл верхнего уровня: {entry.name} — {root_tag}")
        for entry in dirs[:2]:
            inside = sorted(p for p in entry.rglob("*") if p.is_file())
            rel = [str(p.relative_to(folder)) for p in inside[:6]]
            print(f"    каталог объекта: {entry.name} — файлов {len(inside)}, "
                  f"первые: {rel}")
            for candidate in inside[:1]:
                if candidate.suffix.lower() in REGISTRATION_EXTENSIONS:
                    shape = shape_of(candidate)
                    chain = (" → ".join(shape.get("chain", []))
                             if "error" not in shape else shape["error"])
                    print(f"      XML внутри каталога: {candidate.name} — {chain}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", default=",".join(POSITIONS))
    ap.add_argument("--exports", default=",".join(DEFAULT_EXPORTS))
    ap.add_argument("--json", default=str(OUT_DIR / "v59_frame_shape.json"))
    ap.add_argument("--mode", choices=("shape", "layout"), default="shape",
                    help="shape — свойства файлов; layout — где регистрация, где содержимое")
    args = ap.parse_args()

    wanted = [p.strip() for p in args.positions.split(",") if p.strip()]
    exports = [e.strip() for e in args.exports.split(",") if e.strip()]

    print("Форма позиций пакета 1 по выгрузкам (каркас пакетной загрузки)")
    print("=" * 78)
    results = {}
    for position in wanted:
        if position not in POSITIONS:
            print(f"\n⚠️ позиция {position} вне круга зонда — она не из пакета 1")
            continue
        container, title = POSITIONS[position]
        if args.mode == "layout":
            print(f"\n{position} {title} — контейнер `{container}`")
            layout(position, container, exports)
            continue
        data = measure(position, container, exports)
        results[position] = data
        totals = data["totals"]
        print(f"\n{position} {title} — контейнер `{container}`")
        print(f"  выгрузок с контейнером: {totals['exports_found']}/{len(exports)}; "
              f"файлов {totals['files']} (регистрации {totals['registration']}, "
              f"содержимое {totals['content']}), {totals['bytes'] / 1024:.0f} КБ; "
              f"теги вида: {data['kinds'] or 'не разобрано'}")
        for export in exports:
            entry = data["per_export"][export]
            if not entry["found"]:
                print(f"  {export}: контейнера нет")
                continue
            print(f"  {export}: файлов {entry['files']} (рег. {entry['registration']}, "
                  f"содерж. {entry['content']}), расширения {entry['by_ext']}, "
                  f"макс. файл {entry['max_bytes']} Б")
            for err in entry["errors"]:
                print(f"    ⚠️ {err}")
        props = ", ".join(f"{tag} {info['of_sampled']}" for tag, info in
                          sorted(data["properties"].items(),
                                 key=lambda kv: -kv[1]["files"]))
        print(f"  свойства (файлов из {data['sampled_total']} разобранных): {props or 'нет'}")
        blocks = ", ".join(f"{tag} ×{n}" for tag, n in
                           sorted(data["blocks"].items(), key=lambda kv: -kv[1])[:25])
        print(f"  вложенные блоки: {blocks or 'нет'}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    print("\n" + "-" * 78)
    print(f"JSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

