#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V43: SQL-блоки 48 колонок-массивов генерируются из модуля, а не переписываются.

Причина та же, по которой 48 имён лежат в одном словаре `src/configuration_child_properties.py`:
имена колонок живут в трёх местах (бутстрап шага 2, аддитивная миграция, писатель), и
переписанные порознь они обязательно разъедутся. Скрипт печатает готовые блоки из словаря,
остальное — вставка этого текста в файлы; повторный запуск даёт тот же текст (идемпотентно).

Заодно скрипт сверяет словарь с замером живого индекса (`_v43_types.txt`, 22.10.2026):
проверка видит и лишнее имя, и отсутствующее, а не только «сколько-то колонок добавлено».

Вывод — `_v43_sql_blocks.txt` (артефакт, не трекается): BLOCK A — объявления колонок в
`create_1c_configurations_db.sql`, BLOCK B — пары «колонка, object_type» для
`migrate_v43_configuration_child_arrays.sql`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import configuration_child_properties as cp  # noqa: E402

TYPE_SQL = "TEXT[]"
PROBE_FILE = ROOT / "_scratch" / "_v43_types.txt"
OUT_FILE = ROOT / "_scratch" / "_v43_sql_blocks.txt"


def probe_types():
    """Виды, реально отданные индексом состава на depth=0 (замер живой БД)."""
    if not PROBE_FILE.exists():
        return []
    kinds = []
    for line in PROBE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and "|" in line:
            kinds.append(line.split("|")[0].strip())
    return kinds


def check_against_probe():
    kinds = probe_types()
    module = list(cp.CHILD_OBJECT_TYPES)
    problems = []
    if not kinds:
        print("замер индекса (_v43_types.txt) не найден — сверка с живой БД пропущена")
        return problems
    extra = sorted(set(kinds) - set(module))
    missing = sorted(set(module) - set(kinds))
    allowed_extra = {cp.ROOT_OBJECT_TYPE}
    unexpected_extra = sorted(set(extra) - allowed_extra)
    problems += [f"в индексе есть, в словаре нет: {name}" for name in unexpected_extra]
    problems += [f"в словаре есть, в индексе нет: {name}" for name in missing]
    print(f"замер: видов {len(kinds)}, словарь: {len(module)}; "
          f"вне словаря только {sorted(set(extra) - allowed_extra) or 'ничего'} "
          f"(корень {cp.ROOT_OBJECT_TYPE} — граница K1)")
    if not sorted(set(extra)) == sorted(allowed_extra):
        problems.append(f"лишние виды за пределами границ: {sorted(set(extra))}")
    if len(set(module)) != len(module) or len(set(cp.CHILD_ARRAY_COLUMNS)) != len(module):
        problems.append("в словаре повторяющиеся object_type или имена колонок")
    numbers = sorted(number for (_t, _c, number) in cp.CHILD_PROPERTIES)
    if numbers != list(range(1, cp.CHILD_COUNT + 1)):
        problems.append(f"нумерация пунктов файла оператора не 1..{cp.CHILD_COUNT}")
    return problems


def block_bootstrap():
    lines = [
        "    -- Узел V43 (22.10.2026): 48 дочерних свойств конфигурации — массивы имён",
        "    -- объектов метаданных каждого вида. Источник — индекс состава",
        "    "
        "``ConfigDumpInfo.xml`` (``configuration_objects``, узел V33), а НЕ свойства",
        "    -- ``<Properties>`` корня: дочернее свойство конфигурации — это перечень её",
        "    -- объектов, а не значение XML. Имена колонок задаёт единственный словарь",
        "    -- ``src/configuration_child_properties.py`` (CHILD_PROPERTIES), здесь тот же",
        "    -- порядок (пункты файла оператора 1..48).",
        "    -- Тип TEXT[] по контракту файла оператора («поле — всегда список значений,",
        "    -- тип строка макс. 80»): замер 274 141 строки индекса подтверждает границу 80",
        "    -- (K3) и отсутствие дублей имён внутри вида (K4).",
        "    -- Пустое состояние — NULL, а не '{}': «вида в конфигурации нет» и «вид есть,",
        "    -- но объектов ноль» индекс различить не может, поэтому выбран тот же контракт,",
        "    -- что у V39/V42 (пустая колонка читается как «в выгрузке этого нет»).",
    ]
    for object_type, column, number in cp.CHILD_PROPERTIES:
        lines.append(f"    {column} {TYPE_SQL},")
    return "\n".join(lines)


def block_migration_pairs():
    lines = [
        "    -- {имя колонки, object_type индекса состава}; порядок совпадает с порядком",
        "    -- объявления в шаге 2 и со словарём CHILD_PROPERTIES (один источник имён).",
        "    child_arrays TEXT[][] := ARRAY[",
    ]
    pairs = []
    for object_type, column, _number in cp.CHILD_PROPERTIES:
        pairs.append(f"        ['{column}', '{object_type}']")
    lines.append(",\n".join(pairs))
    lines.append("    ];")
    return "\n".join(lines)


def main():
    problems = check_against_probe()
    text = "\n\n".join([
        "# узел V43 — сгенерировано _v43_gen_sql.py из src/configuration_child_properties.py",
        f"# колонок: {cp.CHILD_COUNT}, тип: {TYPE_SQL}",
        "# BLOCK A — create_1c_configurations_db.sql (вставить после `content JSONB,`)",
        block_bootstrap(),
        "",
        "# BLOCK B — migrate_v43_configuration_child_arrays.sql (массив пар DO-блока)",
        block_migration_pairs(),
        "",
    ])
    OUT_FILE.write_text(text, encoding="utf-8")
    print(f"колонок: {cp.CHILD_COUNT}, файл: {OUT_FILE.name}")
    if problems:
        print("РАСХОЖДЕНИЯ:")
        for problem in problems:
            print(" -", problem)
        return 1
    print("расхождений словаря с замером индекса нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
