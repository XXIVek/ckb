# -*- coding: utf-8 -*-
"""_v53_p6_db_class_probe.py — три измерения одного числа: файл, разбор, строки БД.

Зачем. Независимый зонд `_v53_p6_counts_probe.py` по файлам даёт по трём классам целей числа
на 15 больше, чем таблица 2.2 плана (`DocumentObject` 11 919 против 11 907, `CatalogObject`
6 002 против 6 000, `InformationRegisterRecordSet` 3 249 против 3 248). Прежде чем переносить
числа в эталон постоянной проверки, надо знать, какое из измерений расходится: текст файла
(зонд), разбор (модуль загрузки) или строки таблицы (БД). Сравнение идёт по ключу
(файл | ordinal | класс), чтобы расхождение называлось строками, а не только числами.

Запуск: python _v53_p6_db_class_probe.py
"""
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from configuration_event_subscriptions import (  # noqa: E402
    CFG_PREFIX, DIR_NAME, collect_event_subscriptions,
)
from configuration_event_subscriptions_loader import read_index_records  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
SOURCE_BLOCK_RE = re.compile(r"<Source>(.*?)</Source>", re.S)
RE_SOURCE_VALUE = {tag: re.compile(r"<v8:%s>\s*(.*?)\s*</v8:%s>" % (tag, tag), re.S)
                   for tag in ("Type", "TypeSet")}


def raw_values(text):
    """Записи блока `Source` регуляркой по тексту — та же мера, что у зонда П6."""
    source = SOURCE_BLOCK_RE.search(text)
    if not source:
        return []
    return [(tag, value) for tag, pattern in RE_SOURCE_VALUE.items()
            for value in pattern.findall(source.group(1))]


def class_of(value):
    body = value[len(CFG_PREFIX) + 1:] if value.startswith(CFG_PREFIX + ":") else ""
    return body.split(".")[0] if body else ""


def main():
    for tag in DUMPS:
        dump = DUMP_ROOT / tag
        directory = dump / DIR_NAME
        if not directory.is_dir():
            print(f"{tag}: каталога вида нет")
            continue
        cfg_uuid = str(configuration_uuid_from_layout(str(dump)).get("uuid") or "")

        raw = Counter()
        raw_keys = set()
        files = sorted(p for p in directory.rglob("*.xml") if p.is_file())
        for path in files:
            text = path.read_text(encoding="utf-8")
            name = path.stem
            for ordinal, (_tag, value) in enumerate(raw_values(text)):
                cls = class_of(value)
                raw[cls] += 1
                raw_keys.add(f"{name}|{ordinal}|{cls}")

        with transaction() as cur:
            cur.execute("SELECT id FROM configurations WHERE uuid = %s::uuid", (cfg_uuid,))
            row = cur.fetchone()
            configuration_id = int(row[0]) if row else 0
            index_info = read_index_records(cur, configuration_id)
            cur.execute("SELECT target_class, count(*) FROM event_subscription_sources "
                        "WHERE configuration_uuid = %s::uuid GROUP BY target_class", (cfg_uuid,))
            db_class = {str(r[0]): int(r[1]) for r in cur.fetchall()}
            cur.execute("SELECT subscription_full_name || '|' || ordinal::text || '|' || "
                        "target_class FROM event_subscription_sources "
                        "WHERE configuration_uuid = %s::uuid", (cfg_uuid,))
            db_keys = {str(r[0]) for r in cur.fetchall()}

        parsed = collect_event_subscriptions(dump, index_info["rows"])
        parsed_class = Counter(str(row["target_class"]) for row in parsed["source_rows"])
        parsed_keys = {f"{row['subscription_full_name']}|{row['ordinal']}|{row['target_class']}"
                       for row in parsed["source_rows"]}

        print(f"\n=== {tag} (uuid {cfg_uuid}) ===")
        print(f"файлов: {len(files)}; записей Source: зонд {sum(raw.values())}, "
              f"разбор {sum(parsed_class.values())}, БД {sum(db_class.values())}")
        diffs = []
        for cls in sorted(set(raw) | set(parsed_class) | set(db_class)):
            a, b, c = raw.get(cls, 0), parsed_class.get(cls, 0), db_class.get(cls, 0)
            if not (a == b == c):
                diffs.append(f"  РАСХОЖДЕНИЕ {cls}: зонд {a}, разбор {b}, БД {c}")
        print("\n".join(diffs) if diffs else "  классы совпали по всем значениям")
        print(f"  ключей (файл|ordinal|класс): зонд {len(raw_keys)}, "
              f"разбор {len(parsed_keys)}, БД {len(db_keys)}")
        only_raw = sorted(raw_keys - parsed_keys)
        only_parsed = sorted(parsed_keys - raw_keys)
        only_db = sorted(db_keys - parsed_keys)
        if only_raw:
            print(f"  только у зонда ({len(only_raw)}): {only_raw[:6]}")
        if only_parsed:
            print(f"  только у разбора ({len(only_parsed)}): {only_parsed[:6]}")
        if only_db:
            print(f"  только в БД ({len(only_db)}): {only_db[:6]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
