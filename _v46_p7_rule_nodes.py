#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П7 узла V46: карточка нового инструмента, перечень слоя, узел журнала, правка матрицы.

Зачем: П5 добавил в регистр `server_configurations_core.py` инструмент
`load_configuration_object_properties_tool` (4 → 5) и сделал стадию S4 конвейера работающей.
После этого три живые карточки слоя стали неправдой: карточка слоя перечисляет четыре
инструмента, `checks:index` говорит «четыре инструмента», `functional:goal-and-stages` называет
S4 заглушкой. Проверка `_layer_tree_check.py` требует карточку на каждый инструмент регистра и
полноту `===INDEX` — скрыть это нельзя, поэтому карточка заводится здесь же, где меняется
регистр (правило узла EDIT-CALL: состав инструментов меняется вместе с узлом журнала о составе).

Что делает:
  1. пишет карточку `rules:core-rules:load-configuration-object-properties-tool` (теги берутся
     у прежней карточки инструмента того же ряда, алиасы — адресные + русские);
  2. дописывает строку в перечень `===LINKS` и адрес в `===INDEX` карточки слоя (число состава в
     заголовке таблицы правится, потому что оно названо);
  3. правит три карточки по факту: `checks:index` (число инструментов, новая проверяющая
     команда), `functional:goal-and-stages` (слои, стадии, матрица, FORBID, TOOLS, CHECK, SOURCE),
     `functional:load-catalog` и `load-1c-catalog-tool` (что входит в первый слой);
  4. пишет узел журнала `rules:core-rules:journal:node:v46` и строку перечня журнала.

Правки текста — точечные: каждое совпадение обязано быть единственным, иначе шаг называется
отказом, а не молча пропущенной заменой (два текста одного правила расходятся молча).

Запуск:
    python _v46_p7_rule_nodes.py            # что будет сделано
    python _v46_p7_rule_nodes.py --write    # записать
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

MARKER = "core-rules"
LAYER_ADDRESS = f"{RL.ROOT_MARKER}:{MARKER}:"
TOOL = "load_configuration_object_properties_tool"
TOOL_LEAF = TOOL.replace("_", "-")
TOOL_ADDRESS = f"{LAYER_ADDRESS}{TOOL_LEAF}"
JOURNAL_ADDRESS = f"{LAYER_ADDRESS}{RL.STATE_JOURNAL}:node:v46"
JOURNAL_INDEX = f"{LAYER_ADDRESS}{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}"
LAYER_CARD = LAYER_ADDRESS
GOAL_ADDRESS = f"{RL.functional_prefix(MARKER)}goal-and-stages"
LOAD_CATALOG_ADDRESS = f"{RL.functional_prefix(MARKER)}load-catalog"
CHECKS_INDEX = f"{LAYER_ADDRESS}{RL.STATE_CHECKS}:{RL.INDEX_LEAF}"
CATALOG_TOOL_ADDRESS = f"{LAYER_ADDRESS}load-1c-catalog-tool"

from _v46_p7_texts import (  # noqa: E402
    JOURNAL_NODE,
    JOURNAL_SECTION,
    TOOL_ALIASES_RU,
    TOOL_CARD,
)


def level_aliases(address):
    """Алиасы каждого уровня адреса — их требует дампер (`by_alias`)."""
    parts = (address or "").split(":")
    return [
        ":".join(parts[:i]) + ":"
        for i in range(1, len(parts))
        if any(parts[:i])
    ]


def tool_aliases():
    short = f"{MARKER}:{TOOL_LEAF}"
    return list(dict.fromkeys(
        [TOOL_ADDRESS, short] + level_aliases(TOOL_ADDRESS) + level_aliases(short) + [MARKER]
        + TOOL_ALIASES_RU))


def existing_tags(cur):
    """Теги прежней карточки инструмента того же ряда — новая строка не должна отличаться."""
    cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s",
                (f"{LAYER_ADDRESS}load-configuration-root-modules-tool",))
    row = cur.fetchone()
    if not row:
        raise SystemExit("нет карточки-образца для тегов: ряд инструментов слоя не найден")
    return list(row["tags"] or [])


def write_card(cur, address, answer, tags, aliases, dry):
    """Строка правила по адресу: `question` — адрес, `answer` — содержимое (контракт узла V44)."""
    key = RL.source_url(address)
    cur.execute("SELECT id FROM knowledge_snippets WHERE source_url=%s", (key,))
    known = cur.fetchone()
    print(f"{'обновлено ' if known else 'создано   '}  {address}  {len(answer)} симв.")
    if dry:
        return None
    if known:
        cur.execute("UPDATE knowledge_snippets SET answer=%s, tags=%s WHERE id=%s",
                    (answer, tags, known["id"]))
        snippet_id = known["id"]
    else:
        cur.execute(
            "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags,"
            " confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, 1.0, TRUE) RETURNING id",
            (address, answer, key, tags))
        snippet_id = cur.fetchone()["id"]
    for alias in aliases:
        cur.execute(
            "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags,"
            " weight) VALUES (%s,'snippet',NULL,%s,%s,1.0) "
            "ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
            (alias, snippet_id, tags))
    return snippet_id


def patch(cur, address, old, new, dry, label="", optional=False):
    """Точечная правка карточки: одно совпадение — иначе шаг называется отказом.

    `optional=True` — правка-исправление, которая нужна только строке с прежним текстом: если
    прежнего текста в карточке нет (строка ещё не пислась или уже исправлена), шаг называется
    пропуском, а не отказом. Иначе повторный прогон того же прогона врал бы о своём результате.
    """
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    if new in text:
        # Повторный прогон не должен называть отказом уже внесённую правку (идемпотентность).
        print(f"без изменений  {address}  правка уже внесена — {label or old[:40]!r}")
        return True
    hits = text.count(old)
    if hits == 0 and optional:
        print(f"пропуск       {address}  прежнего текста нет — {label or old[:40]!r}")
        return True
    if hits != 1:
        print(f"⚠️ ОТКАЗ {address}: совпадений {hits} (нужно одно) — {label or old[:40]!r}")
        return False
    print(f"{'правка     ' if not dry else 'сухо-правка'}  {address}  ← {label or old[:60]!r}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text.replace(old, new), row["id"]))
    return True


def append_after(cur, address, anchor, line, dry, label="", exact=False, before=False):
    """Дописать строку рядом со строкой-образцом (перечни `===LINKS`/`===INDEX` идут блоками).

    `exact` — образец сравнивается со строкой целиком (перечень `===INDEX` содержит адреса без
    обрамления, подстрока одного адреса встречается и в таблице `===LINKS`); `before` — вставлять
    перед образцом, когда перечень упорядочен (оба перечня слоя идут по алфавиту адресов).
    """
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    lines = text.splitlines()
    want = anchor.strip()
    if exact:
        # Строка перечня (`===INDEX`) опознаётся только целиком: адрес входит и в таблицу
        # `===LINKS` той же карточки, поэтому подстрока не является признаком внесённой строки.
        if any(item.strip() == line.strip() for item in lines):
            print(f"без изменений  {address}  строка перечня уже есть — {label}")
            return True
    elif line in text:
        print(f"без изменений  {address}  строка уже есть — {label}")
        return True
    if exact:
        at = [i for i, item in enumerate(lines) if item.strip() == want]
    else:
        at = [i for i, item in enumerate(lines) if anchor in item]
    if len(at) != 1:
        print(f"⚠️ ОТКАЗ {address}: строк-образцов {len(at)} — {anchor[:60]!r}")
        return False
    lines.insert(at[0] if before else at[0] + 1, line)
    print(f"{'строка     ' if not dry else 'сухо-строка'}  {address}  + {label}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    ("\n".join(lines) + "\n", row["id"]))
    return True



def main(argv=None):
    dry = "--write" not in (argv or sys.argv[1:])
    with get_cursor() as cur:
        tags = existing_tags(cur)
        new_id = write_card(cur, TOOL_ADDRESS, TOOL_CARD, tags, tool_aliases(), dry)

        # ── карточка слоя: перечень детей (`===LINKS`) и индекс (`===INDEX`)
        # Оба перечня упорядочены по адресу, поэтому строка ставится перед соседом
        # `load-configuration-root-modules-tool`; в таблице id называется строкой карточки,
        # а не числом состава в тексте (правило карточки слоя: числа состава словами не хранят).
        row_id = new_id if new_id else "(после записи)"
        append_after(cur, LAYER_CARD,
                     f"| 6157 | `rules:core-rules:load-configuration-root-modules-tool`",
                     f"| {row_id} | `{TOOL_ADDRESS}` | Нужны свойства подсистем и общих модулей "
                     "уже загруженной конфигурации и дескрипторы файлов их модулей. |",
                     dry, "строка LINKS", before=True)
        append_after(cur, LAYER_CARD, TOOL_ADDRESS.replace("object-properties", "root-modules"),
                     TOOL_ADDRESS, dry, "строка INDEX", exact=True, before=True)
        ok = patch(cur, LAYER_CARD, "слой `1c-configurations-core` (11):",
                   "слой `1c-configurations-core` (12):", dry, "число состава LINKS")
        ok &= patch(cur, LAYER_CARD,
                    "снятие объекта, модули предопределённых программ корня\nконфигурации.",
                    "снятие объекта, модули предопределённых программ корня\nконфигурации, "
                    "свойства подсистем и общих модулей (стадия S4, узел V46).",
                    dry, "что загружает сервер")

        # ── проверки слоя: число инструментов и новая проверяющая команда
        ok &= patch(cur, CHECKS_INDEX, "равен контракту (четыре инструмента)",
                    "равен контракту (пять инструментов)", dry, "число регистра")
        # Формулировка родителя строки текста модуля: родителем является uuid самого общего
        # модуля (`parent_type = 'common_modules'`), а не «секция CommonModule». Правка идёт до
        # добавления строки перечня, иначе прогон дал бы две одинаковые строки таблицы.
        ok &= patch(cur, CHECKS_INDEX, "тексты модулей по `parent_uuid` секции `CommonModule`",
                    "тексты модулей по `parent_uuid` = uuid общего модуля",
                    dry, "проверка: родитель модуля")
        append_after(cur, CHECKS_INDEX, "| `python _layer_ls.py rules:core-rules:` |",
                     "| `python _v46_p5_loader_probe.py MinCfg` | свойства подсистем и общих "
                     "модулей: отчёт слоя против строк таблиц, идемпотентность снятием, круг "
                     "снятия по видам, тексты модулей по `parent_uuid` = uuid общего модуля, "
                     "возврат базового состояния, стадия S4 внутри `load_catalog` (узел V46) |",
                     dry, "строка проверок")

        # ── исправление формулировки групп (узел V46, тот же прогон; идёт ДО правок состояния)
        # План узла назвал загружаемый слой «группа C модели A–H», а модель A–H (узел V38,
        # `docs/config-scenarios/01_configuration.md`) группой C называет модули предопределённых
        # программ корня: свойства подсистем там относятся к группе E, общие модули — к группе B.
        # Расхождение двух текстов одного правила молча оставлять нельзя, поэтому исправление
        # идёт этим же прогоном; правки помечены `optional` — на строке, где прежнего текста нет
        # (база ещё не исправлялась), это пропуск, а не отказ.
        ok &= patch(cur, GOAL_ADDRESS,
                    "свойства подсистем и общих модулей группы C\n"
                    "   (`subsystems`, `subsystem_content`, `common_modules`, `common_module_sources`) — реализованы с\n"
                    "   узла V46, тексты модулей общих модулей остаются отдельной просьбой",
                    "свойства подсистем и общих модулей реализованы\n"
                    "   с узла V46 (`subsystems`, `subsystem_content`, `common_modules`, `common_module_sources`; по\n"
                    "   модели A–H узла V38 это часть групп B и E, а не группа C — формулировка плана называла их\n"
                    "   группой C, расхождение исправлено этим же узлом), тексты модулей общих модулей остаются\n"
                    "   отдельной просьбой",
                    dry, "слои: имена групп", optional=True)
        # Тот же текст — перенос строки оставил висячую строку «отдельной просьбой»; правка
        # переноса идёт отдельным шагом, потому что содержимое она не меняет.
        ok &= patch(cur, GOAL_ADDRESS,
                    "отдельной просьбой\n   (`with_module_content`, решение D-S4)",
                    "отдельной просьбой (`with_module_content`, решение D-S4)",
                    dry, "слои: перенос строки", optional=True)
        ok &= patch(cur, GOAL_ADDRESS, "(группа C частично, узел V46); S5",
                    "(часть групп B/E, узел V46); S5", dry, "стадии: имена групп", optional=True)
        ok &= patch(cur, GOAL_ADDRESS,
                    "S4 — свойства подсистем и общих модулей (группа C частично, узел V46); слои 2 и 3 не реализованы",
                    "S4 — свойства подсистем и общих модулей (часть групп B/E, узел V46); слои 2 и 3 не реализованы",
                    dry, "матрица: имена групп", optional=True)
        ok &= patch(cur, GOAL_ADDRESS,
                    "выдавать S4 за закрытую всю группу C (реквизиты,\nформы, макеты, модули объектов — группы A–H остаются);",
                    "выдавать S4 за закрытые остальные группы A–H модели V38\n(реквизиты, формы, макеты, модули объектов, значения перечислений);",
                    dry, "FORBID: имена групп", optional=True)
        ok &= patch(cur, GOAL_ADDRESS,
                    "`python _v46_p5_loader_probe.py MinCfg` — содержимое группы C (узел V46).",
                    "`python _v46_p5_loader_probe.py MinCfg` — свойства подсистем и общих модулей (узел V46).",
                    dry, "CHECK: имена групп", optional=True)

        # ── матрица состояния: S4 больше не заглушка (узел V46)
        ok &= patch(cur, GOAL_ADDRESS,
                    "(`configurations`), индекс состава и перечни имён (`configuration_objects`), четыре модуля\n"
                    "   предопределённых программ корня — реализован; слой 2 — модули объектов и общие модули\n"
                    "   (`ObjectModule`, `ManagerModule`, `RecordSetModule`, `ValueManagerModule`, `CommandModule`) — не\n"
                    "   реализован, по нему только зонды `_v46*`, `_v47*`; слой 3 — содержимое дочерних узлов объектов\n"
                    "   (реквизиты, табличные части, формы, макеты, права, расписания) — не реализован.",
                    "(`configurations`), индекс состава и перечни имён (`configuration_objects`), четыре модуля\n"
                    "   предопределённых программ корня — реализован; свойства подсистем и общих модулей реализованы\n"
                    "   с узла V46 (`subsystems`, `subsystem_content`, `common_modules`, `common_module_sources`; по\n"
                    "   модели A–H узла V38 это часть групп B и E, а не группа C — формулировка плана называла их\n"
                    "   группой C, расхождение исправлено этим же узлом), тексты модулей общих модулей остаются\n"
                    "   отдельной просьбой (`with_module_content`, решение D-S4); слой 2 — модули объектов\n"
                    "   (`ObjectModule`, `ManagerModule`, `RecordSetModule`, `ValueManagerModule`, `CommandModule`) — не\n"
                    "   реализован; слой 3 — содержимое дочерних узлов объектов (реквизиты, табличные части, формы,\n"
                    "   макеты, права, расписания) — не реализован.",
                    dry, "слои загрузки")
        ok &= patch(cur, GOAL_ADDRESS, "S4 содержимое дочерних объектов —\n   заглушка;",
                    "S4 свойства подсистем и общих модулей\n   (часть групп B/E, узел V46);",
                    dry, "стадия S4")
        ok &= patch(cur, GOAL_ADDRESS,
                    "| конфигурация | слой 1 реализован (S1–S3); слои 2 и 3 не реализованы; S4 — заглушка |",
                    "| конфигурация | слой 1 реализован (S1–S3); S4 — свойства подсистем и общих модулей "
                    "(часть групп B/E, узел V46); слои 2 и 3 не реализованы |",
                    dry, "строка матрицы")
        ok &= patch(cur, GOAL_ADDRESS, "выдавать заглушку\nS4 за выполненную стадию;",
                    "выдавать S4 за закрытые остальные группы A–H модели V38\n"
                    "(реквизиты, формы, макеты, модули объектов, значения перечислений);",
                    dry, "FORBID")
        ok &= patch(cur, GOAL_ADDRESS,
                    "load_1c_catalog_tool, load_external_object_file_tool, load_configuration_root_modules_tool,\n"
                    "delete_external_report_tool",
                    "load_1c_catalog_tool, load_external_object_file_tool, load_configuration_root_modules_tool,\n"
                    "load_configuration_object_properties_tool, delete_external_report_tool",
                    dry, "TOOLS")
        ok &= patch(cur, GOAL_ADDRESS,
                    "границы заголовка конфигурации; `python _journal_code_history.py` — покрыта ли история изменений\n"
                    "регистра записями слоя.",
                    "границы заголовка конфигурации; `python _journal_code_history.py` — покрыта ли история изменений\n"
                    "регистра записями слоя; `python _v46_p5_loader_probe.py MinCfg` — свойства подсистем и общих "
                    "модулей (узел V46).",
                    dry, "CHECK")
        ok &= patch(cur, GOAL_ADDRESS,
                    "`rules:core-rules:journal:node:v45` (конвейер S1–S4 и закрытый контракт результата),",
                    "`rules:core-rules:journal:node:v45` (конвейер S1–S4 и закрытый контракт результата),\n"
                    "`rules:core-rules:journal:node:v46` (свойства подсистем и общих модулей, контракт 4→5),",
                    dry, "SOURCE")

        # ── функция слоя и карточка точки входа: что входит в первый слой
        ok &= patch(cur, LOAD_CATALOG_ADDRESS,
                    "конвейером первого слоя (узел V45), состояние стадий —\n"
                    "   `rules:core-rules:functional:goal-and-stages`.",
                    "конвейером первого слоя (узел V45), состояние стадий —\n"
                    "   `rules:core-rules:functional:goal-and-stages`. Стадия S4 конвейера пишет\n"
                    "   свойства подсистем и общих модулей (узел V46); для случая «изменились только файлы\n"
                    "   регистрации» служит `load_configuration_object_properties_tool` — заголовок при этом\n"
                    "   не пересоздаётся.",
                    dry, "MUST 3")
        ok &= patch(cur, LOAD_CATALOG_ADDRESS,
                    "load_1c_catalog_tool, load_external_object_file_tool, delete_external_report_tool",
                    "load_1c_catalog_tool, load_external_object_file_tool,\n"
                    "load_configuration_object_properties_tool, delete_external_report_tool",
                    dry, "TOOLS")
        ok &= patch(cur, CATALOG_TOOL_ADDRESS,
                    "конфигурация (первый слой —\n"
                    "заголовок, индекс состава, модули предопределённых программ корня).",
                    "конфигурация (первый слой —\n"
                    "заголовок, индекс состава, модули предопределённых программ корня, свойства подсистем и общих\n"
                    "модулей — стадия S4, узел V46).",
                    dry, "WHEN")

        # ── узел журнала о составе регистра (обязателен при изменении регистра)
        write_card(cur, JOURNAL_ADDRESS, JOURNAL_NODE, tags,
                   [JOURNAL_ADDRESS, f"{MARKER}:{RL.STATE_JOURNAL}:node:v46"]
                   + level_aliases(JOURNAL_ADDRESS), dry)
        append_after(cur, JOURNAL_INDEX, "`rules:core-rules:journal:node:v45`",
                     f"| `{JOURNAL_ADDRESS}` | план `docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md`"
                     f" (28.10.2026) | {JOURNAL_SECTION} |", dry, "строка индекса журнала")

        print("\n" + ("⚠️ ничего не записано (нет --write)" if dry else "✅ записи выполнены"))
        if not ok:
            print("⚠️ часть правок названа отказами — их нельзя пропускать молча.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


