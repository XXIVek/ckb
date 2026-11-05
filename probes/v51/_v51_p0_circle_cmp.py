#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V51, шаг П0: круг детей плана обмена — элементы XML против индекса состава.

Зачем отдельная проба. Индекс состава (`configuration_objects`) задуман как независимая нога
инварианта круга (приём V43/V48/V49/V50). По планам обмена он даёт расхождение с файлами:
по BGU2 строк `child_type='Attribute'` — 317, а непосредственных элементов `Attribute` в XML —
меньше. Пока расхождение не названо и не объяснено, индекс нельзя использовать как ногу
инварианта: проверка узла обязана сравнивать три множества, а не два из них.

Проба только читает: XML выгрузки и строки индекса. Ничего не пишет.

Запуск:  python _v51_p0_circle_cmp.py [BGU2|BP3|MinCfg]
"""

import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from external_db import transaction  # noqa: E402  (база ckb_1c_configurations)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
# имена выгрузок сопоставлены конфигурациям по кругу вида: у наибольшего круга — BGU2
DUMP_BY_NAME = {"BGU2": "ExchangePlans", "BP3": "ExchangePlans", "MinCfg": "ExchangePlans"}

# Типы детей, которые у вида встречаются (замер П0: Attribute, TabularSection, Form,
# Template, Command; слоты содержимого — Help/Content/AdditionalIndexes — лежат файлами).
KINDS = ("Attribute", "TabularSection", "Form", "Template", "Command", "Folder",
         "AdditionalAttribute", "Help", "Content", "AdditionalIndexes", "StandardAttribute")


def local(tag):
    return tag.split('}')[-1]


def xml_counts(path):
    """Все элементы детей внутри файла вида, считанные по типу тега."""
    counts = Counter()
    root = ET.parse(str(path)).getroot()
    for node in root.iter():
        name = local(node.tag)
        if name in KINDS:
            counts[name] += 1
    return counts


def dump_config_uuid(dump):
    """uuid заголовка выгрузки — атрибут `uuid` элемента `<Configuration>` (приём V32).

    Сопоставление выгрузки с конфигурацией идёт по нему, а не по имени: кириллица в консоли
    искажается, а порядок кругов (у BP3 планов обмена больше, чем у BGU2) перепутал бы ноги.
    """
    header = DUMP_ROOT / dump / "Configuration.xml"
    if not header.is_file():
        return ""
    root = ET.parse(str(header)).getroot()
    for node in root:
        if local(node.tag) == "Configuration":
            return node.attrib.get("uuid", "")
    return ""


def index_rows(cur, cfg_id):
    cur.execute("SELECT parent_name, child_type, count(*) FROM configuration_objects "
                "WHERE configuration_id = %s AND object_type = 'ExchangePlan' "
                "AND parent_name IS NOT NULL GROUP BY 1,2", (cfg_id,))
    idx = {}
    for parent_name, child_type, count in cur.fetchall():
        idx.setdefault(parent_name, Counter())[child_type or "<объект>"] = count
    return idx


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or sorted(DUMP_BY_NAME)
    print("=== П0: элементы XML вида против строк индекса состава ===")
    for dump in wanted:
        view = DUMP_ROOT / dump / "ExchangePlans"
        if not view.is_dir():
            print(f"\n{dump}: каталога ExchangePlans нет — состояние выгрузки, не отказ")
            continue
        # ключ сравнения — точечное имя объекта, как его даёт индекс состава
        # (`ExchangePlan.<Имя>`); имя файла вида само вид не называет.
        per_file = {f"ExchangePlan.{f.stem}": xml_counts(f) for f in sorted(view.glob("*.xml"))}
        with transaction() as cur:
            # сопоставление выгрузки с конфигурацией — по uuid заголовка из Configuration.xml
            # (приём V32): имя в консоли искажается, а порядок кругов (у BP3 планов обмена
            # больше, чем у BGU2) перепутал бы ноги инварианта.
            cfg_uuid = dump_config_uuid(dump)
            cur.execute("SELECT id FROM configurations WHERE uuid = %s", (cfg_uuid,))
            row = cur.fetchone()
            if not row:
                print(f"  конфигурации с uuid {cfg_uuid or '<не прочитан>'} в базе нет — "
                      f"сравнение не выполнено (это отсутствие сопоставления, а не расхождение)")
                continue
            cfg_id = row[0]
            idx = index_rows(cur, cfg_id)
            totals_xml, totals_idx = Counter(), Counter()
            names = sorted(set(per_file) | set(idx))
            print(f"  конфигурация {cfg_id} (uuid {cfg_uuid[:8]}, объектов в индексе "
                  f"{len(idx)}, файлов регистрации {len(per_file)}):")
            print(f"    {'объект':36} " + " ".join(f"{k[:12]:>14}" for k in KINDS))
            for name in names:
                xr = per_file.get(name, Counter())
                ir = idx.get(name, Counter())
                totals_xml.update(xr)
                totals_idx.update({k: v for k, v in ir.items() if k != "<объект>"})
                cells = " ".join(f"{xr.get(k, 0):>6}/{ir.get(k, 0):<7}" for k in KINDS)
                print(f"    {name[:36]:36} {cells}")
            print("    ИТОГО xml   :", {k: v for k, v in totals_xml.items() if v})
            print("    ИТОГО индекс:", {k: v for k, v in totals_idx.items() if v})
            print("    формат ячейки: элементов в XML / строк индекса")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
