#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Второй, независимый источник словаря слотов: ConfigDumpInfo.xml (замер 21.10.2026).

Зачем. Замер по файлам `.bsl` (`_v40_module_slots.py`) отвечает на вопрос «есть ли у вида
слот» только там, где текст модуля непустой: платформа пишет `Ext/*.bsl` при непустом
содержимом. Индекс состава перечисляет модуль как дочерний объект метаданных
(`Catalog.Товары.ObjectModule`, `Constant.Х.ValueManagerModule`). Если он перечисляет его
и у объекта с пустым модулем — словарь слотов снимается с индекса, а не с наличия файлов.
Это тот же источник, который будет читать замер группы B/C узла V38
(`configuration_objects.child_type`).

Границы:
  • имя объекта метаданных — идентификатор без точки, разбивка по точкам совпадает с
    разборщиком V33 (`src/config_dump_info_parser.py`): `Вид.Имя` — сам объект,
    `Вид.Имя.<дочерний…>` — его дочерний элемент;
  • имена в индексе — в ЕДИНСТВЕННОМ числе (`Catalog`, `Constant`), каталоги выгрузки —
    во множественном (`Catalogs`, `Constants`); сопоставление делает итоговая таблица,
    здесь вид называется так, как его даёт источник;
  • словарь дочерних путей ограничен ПРЯМЫМИ дочерними элементами вида: глубина
    (реквизиты, измерения, секции) даёт 100 609 разных путей и на вопрос о модулях не
    отвечает (замер первого варианта скрипта).
"""
import os
import re
from collections import defaultdict

ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DUMPS = ("BGU2", "BP3", "ZUP31", "UNF3", "UT11", "KomMag", "MinCfg")
META_RE = re.compile(r'<Metadata\s+name="([^"]*)"\s+id="([^"]*)"', re.S)

pairs = defaultdict(lambda: defaultdict(int))       # (вид, слот) -> {выгрузка: объектов}
objects = defaultdict(lambda: defaultdict(int))     # вид -> {выгрузка: объектов}
direct = defaultdict(lambda: defaultdict(int))      # (вид, прямой дочерний) -> {выгрузка: число}
odd = defaultdict(lambda: defaultdict(int))         # модули со слотом нестандартной глубины

for cfg in DUMPS:
    path = os.path.join(ROOT, cfg, "ConfigDumpInfo.xml")
    if not os.path.isfile(path):
        print(f"--- {cfg}: ConfigDumpInfo.xml нет")
        continue
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    names = [m.group(1) for m in META_RE.finditer(text)]
    for name in names:
        parts = name.split(".")
        if len(parts) < 2:
            continue
        kind = parts[0]
        if len(parts) == 2:
            objects[kind][cfg] += 1
            continue
        direct[(kind, parts[2])][cfg] += 1
        last = parts[-1]
        if not (last == "Module" or last.endswith("Module")):
            continue
        if len(parts) == 3:
            slot = last
        elif "Form" in parts[2:-1]:
            # В индексе сегмент формы — ЕДИНСТВЕННОЕ число (`Catalog.X.Form.Y`), а не
            # `Forms` (так во файловой раскладке). Ветка намеренно оставлена: по замеру
            # семи выгрузок она не срабатывает ни разу — индекс составом модуль формы
            # не моделирует. Авторитетный разбор с этим фактом и с файловой половиной —
            # `_v40_slots_table.py` (модули форм относятся к группе A: forms + form_ext.ext).
            slot = "Form/<имя>.Module"
        elif "Commands" in parts[2:-1]:
            slot = "Commands/<имя>." + last
        else:
            slot = ".".join(parts[3:-1]) + "." + last
            odd[(kind, slot)][cfg] += 1
        pairs[(kind, slot)][cfg] += 1
    print(f"--- {cfg}: записей <Metadata> {len(names)}")

print("\n=== 1. Модульные слоты по индексу состава: вид | слот | число объектов с этим слотом ===")
kinds_with = set()
for kind, slot in sorted(pairs):
    kinds_with.add(kind)
    print(f"  {kind:32} | {slot:30} | " +
          ", ".join(f"{c}:{n}" for c, n in sorted(pairs[(kind, slot)].items())))
print(f"\nвидов с модульными дочерними: {len(kinds_with)} | пар (вид, слот): {len(pairs)}")
if odd:
    print("нестандартная глубина пути модуля (названо явно):")
    for (kind, slot), per in sorted(odd.items()):
        print(f"  {kind:32} {slot:30} " + ", ".join(f"{c}:{n}" for c, n in sorted(per.items())))

print("\n=== 2. Виды с объектами в индексе, но БЕЗ модульных дочерних ===")
for kind in sorted(objects):
    if kind not in kinds_with:
        print(f"  {kind:32} объектов: " +
              ", ".join(f"{c}:{n}" for c, n in sorted(objects[kind].items())))

print("\n=== 3. Словарь ПРЯМЫХ дочерних элементов вида (полный) ===")
for kind, child in sorted(direct):
    print(f"  {kind:32} | {child:26} | " +
          ", ".join(f"{c}:{n}" for c, n in sorted(direct[(kind, child)].items())))

print("\n=== 4. Перечисляет ли индекс пустые модули (объектов со слотом / объектов вида) ===")
for kind, slot in sorted(pairs):
    n_slot = sum(pairs[(kind, slot)].values())
    n_obj = sum(objects[kind].values())
    ratio = (100.0 * n_slot / n_obj) if n_obj else 0.0
    verdict = "ДА: индекс шире непустых модулей" if ratio > 20.0 else "реже 20% объектов вида"
    print(f"  {kind:32} {slot:30} со слотом {n_slot:6} | видовых объектов {n_obj:6} | "
          f"{ratio:5.1f}% | {verdict}")
