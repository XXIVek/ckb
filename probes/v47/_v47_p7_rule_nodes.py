#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П7 узла V47: нормативы слоя, карта стадий, две узловые записи журнала слоя `core-rules`.

Зачем. Узел V47 сделал стадию S4b работающей (модули объектов конфигурации в `bsl_modules`) и
ничего не добавил в регистр `server_configurations_core.py` (решение Q4.1). После этого три живые
карточки слоя стали неправдой, а четвёртая оказалась неправдой раньше:

  1. `rules:core-rules:functional:goal-and-stages` — пункт 2 `===MUST===` называет слой 2
     (модули объектов) нереализованным, стадия S4b в перечне стадий отсутствует, строка матрицы
     «конфигурация» говорит «слои 2 и 3 не реализованы», `===FORBID===` запрещает называть слой 2
     реализованным, `===CHECK===` не знает проверяющей команды узла;
  2. `rules:core-rules:` (карточка слоя) — описание сервера заканчивается стадией S4 узла V46;
  3. `rules:core-rules:load-1c-catalog-tool` — карточка инструмента до сих пор перечисляет первый
     слой без стадии S4: правка узла V46 в неё не вошла (расхождение нашёл этот прогон);
  4. `rules:core-rules:checks:index` — строка проверки регистра утверждает «четыре инструмента»,
     тогда как `tools/check_mcp_tool_wiring.py` даёт 5/5 (замер 28.10.2026). Число в правиле
     устарело молча — его правят строкой, а не памятью.

Плюс две узловые записи журнала слоя:

  * `rules:core-rules:journal:node:rule-file-removal` — файл правил слоя снят коммитом `d957ee2e`,
    норматив несут карточки слоя; запись отвечает на вопрос, где норматив «Слои загрузки
    конфигурации», на который ссылался docstring `src/configuration_root_module_loader.py`
    (вопрос оператора 28.10.2026: записи журнала по этому поводу в слое не было);
  * `rules:core-rules:journal:node:v47` — снимок узла V47 с числами своего прогона (критерий 7
    плана `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md`).

Запуск:
    python _v47_p7_rule_nodes.py                     # что будет сделано (сухо)
    python _v47_p7_rule_nodes.py --write             # записать
    python _v47_p7_rule_nodes.py --close <hash>      # строки перечня журнала становятся закрытыми
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

from _v47_p7_texts import (  # noqa: E402
    JOURNAL_RULEFILE,
    JOURNAL_RULEFILE_SECTION,
    JOURNAL_V47,
    JOURNAL_V47_SECTION,
)

MARKER = "core-rules"
LAYER_ADDRESS = f"{RL.ROOT_MARKER}:{MARKER}:"
GOAL_ADDRESS = f"{RL.functional_prefix(MARKER)}goal-and-stages"
LOAD_CATALOG_ADDRESS = f"{RL.functional_prefix(MARKER)}load-catalog"
CATALOG_TOOL_ADDRESS = f"{LAYER_ADDRESS}load-1c-catalog-tool"
CHECKS_INDEX = f"{LAYER_ADDRESS}{RL.STATE_CHECKS}:{RL.INDEX_LEAF}"
JOURNAL_INDEX = f"{LAYER_ADDRESS}{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}"
JOURNAL_V47_ADDRESS = f"{LAYER_ADDRESS}{RL.STATE_JOURNAL}:node:v47"
JOURNAL_RULEFILE_ADDRESS = f"{LAYER_ADDRESS}{RL.STATE_JOURNAL}:node:rule-file-removal"
PLAN_DOC = "docs/CONFIGURATION_OBJECT_MODULES_PLAN.md"
TAGS_SOURCE = f"{LAYER_ADDRESS}{RL.STATE_JOURNAL}:node:v46"

RULEFILE_ALIASES_RU = [
    "файл правил слоя снят",
    "норматив слоя — карточки правил",
    "где норматив слои загрузки конфигурации",
    "arhiv_rules копия правил core",
]
V47_ALIASES_RU = [
    "модули объектов конфигурации",
    "стадия S4b",
    "словарь вид метаданных → слот модуля",
    "bsl_modules модули объектов конфигурации",
]


def level_aliases(address):
    """Алиасы каждого уровня адреса — их требует дампер (`by_alias`)."""
    parts = (address or "").split(":")
    return [
        ":".join(parts[:i]) + ":"
        for i in range(1, len(parts))
        if any(parts[:i])
    ]


def journal_aliases(address, leaf_alias, ru):
    short = f"{MARKER}:{RL.STATE_JOURNAL}:{leaf_alias}"
    return list(dict.fromkeys(
        [address, short] + level_aliases(address) + level_aliases(short) + [MARKER] + ru))


def existing_tags(cur):
    """Теги прежней узловой записи журнала того же слоя — новая строка не должна отличаться."""
    cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s", (TAGS_SOURCE,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("нет карточки-образца для тегов: узловая запись журнала слоя не найдена")
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
    """Точечная правка карточки: одно совпадение — иначе шаг называется отказом."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    if new in text:
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
    """Дописать строку рядом со строкой-образцом (перечни `===LINKS`/`===INDEX` идут блоками)."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    lines = text.splitlines()
    want = anchor.strip()
    if exact:
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


def journal_section(leaf):
    """Описание раздела для строки перечня журнала — по листовому имени адреса."""
    return JOURNAL_V47_SECTION if leaf == "node:v47" else JOURNAL_RULEFILE_SECTION


def has_row(cur, card_address, address):
    """Строка перечня по адресу есть в ЛЮБОЙ форме: плановой или закрытой (`git:<hash>`)."""
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (card_address,))
    row = cur.fetchone()
    return bool(row and f"`{address}`" in (row["answer"] or ""))


def close_index_rows(cur, sha, dry):
    """Строки перечня журнала меняют носителя: закрытый узел называется коммитом (формат V44/V45)."""
    ok = True
    for address, section in ((JOURNAL_V47_ADDRESS, JOURNAL_V47_SECTION),
                             (JOURNAL_RULEFILE_ADDRESS, JOURNAL_RULEFILE_SECTION)):
        ok &= patch(cur, JOURNAL_INDEX,
                    f"| `{address}` | план `{PLAN_DOC}` (28.10.2026) | {section} |",
                    f"| `{address}` | git:{sha} (28.10.2026) | {section} |",
                    dry, "строка индекса журнала: закрытие узла", optional=True)
    return ok


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    dry = "--write" not in args
    if "--close" in args:
        sha = args[args.index("--close") + 1] if "--close" in args[:-1] else ""
        if not sha:
            print("ОТКАЗ: после --close нужен хеш коммита закрытия узла")
            return 1
        with get_cursor() as cur:
            ok = close_index_rows(cur, sha, dry)
        print("\n" + ("⚠️ ничего не записано (нет --write)" if dry else "✅ записи выполнены"))
        return 0 if ok else 1

    with get_cursor() as cur:
        tags = existing_tags(cur)

        # ── карта стадий: слой 2 перестаёт быть нереализованным, появляется S4b
        ok = patch(cur, GOAL_ADDRESS,
                   "отдельной просьбой (`with_module_content`, решение D-S4); слой 2 — модули объектов\n"
                   "   (`ObjectModule`, `ManagerModule`, `RecordSetModule`, `ValueManagerModule`, "
                   "`CommandModule`) — не\n"
                   "   реализован; слой 3 — содержимое дочерних узлов объектов (реквизиты, табличные "
                   "части, формы,\n"
                   "   макеты, права, расписания) — не реализован.",
                   "отдельной просьбой (`with_module_content`, решение D-S4); слой 2 — модули объектов\n"
                   "   конфигурации (`ObjectModule`, `ManagerModule`, `RecordSetModule`,\n"
                   "   `ValueManagerModule`, `CommandModule`, плюс слот `Module` у `WebService`, "
                   "`HTTPService`,\n"
                   "   `IntegrationService`, `Bot`, `WebSocketClient`) — реализован с узла V47: стадия\n"
                   "   S4b, таблица одна — `bsl_modules` с `parent_type = 'configuration_objects'`, "
                   "ключ\n"
                   "   `(parent_uuid, file_path, revision_no)`; файла нет — строки нет (решение Q2),\n"
                   "   пустой модуль и отсутствующий для объектов не различаются — это тоже Q2; "
                   "слой 3 —\n"
                   "   содержимое дочерних узлов объектов (реквизиты, табличные части, формы, макеты,\n"
                   "   права, расписания) — не реализован.",
                   dry, "слои загрузки")

        ok &= patch(cur, GOAL_ADDRESS,
                    "S4 свойства подсистем и общих модулей\n"
                    "   (часть групп B/E, узел V46); S5 (анализ и снижение сниппетов) в `STAGES` нет.",
                    "S4 свойства подсистем и общих модулей\n"
                    "   (часть групп B/E, узел V46) → S4b модули объектов конфигурации (узел V47); "
                    "S5 (анализ и\n"
                    "   снижение сниппетов) в `STAGES` нет, и загрузчик обогащения не вызывает — S5 "
                    "остаётся\n"
                    "   отдельным вызовом (решение оператора 28.10.2026).",
                    dry, "стадии конвейера")

        ok &= patch(cur, GOAL_ADDRESS,
                    "стадии — `STAGES`;",
                    "стадии — `STAGES`. Узел V47 шестого инструмента не добавлял: дозагрузки модулей\n"
                    "   отдельным входом нет (решение Q4.1), ошибка загрузки означает перезагрузку "
                    "всей конфигурации;",
                    dry, "источник состояния — регистр")

        ok &= patch(cur, GOAL_ADDRESS,
                    "| конфигурация | слой 1 реализован (S1–S3); S4 — свойства подсистем и общих "
                    "модулей (часть групп B/E, узел V46); слои 2 и 3 не реализованы |",
                    "| конфигурация | слой 1 реализован (S1–S3); S4 — свойства подсистем и общих "
                    "модулей (часть групп B/E, узел V46); S4b — модули объектов конфигурации, слой 2 "
                    "(узел V47); слой 3 не реализован |",
                    dry, "строка матрицы «конфигурация»")

        ok &= patch(cur, GOAL_ADDRESS,
                    "называть слой 2 или слой 3 реализованным; выдавать S4 за закрытые остальные "
                    "группы A–H модели V38\n"
                    "(реквизиты, формы, макеты, модули объектов, значения перечислений);",
                    "называть слой 3 реализованным (слой 2 — модули объектов — закрыт узлом V47);\n"
                    "выдавать S4/S4b за закрытые остальные группы A–H модели V38 (реквизиты, формы,\n"
                    "макеты, значения перечислений: S4b закрывает только модули);",
                    dry, "FORBID")

        ok &= patch(cur, GOAL_ADDRESS,
                    "`python _v46_p5_loader_probe.py MinCfg` — свойства подсистем и общих модулей "
                    "(узел V46).",
                    "`python _v46_p5_loader_probe.py MinCfg` — свойства подсистем и общих модулей "
                    "(узел V46);\n"
                    "`python tools/check_v47_configuration_object_modules.py` — модули объектов "
                    "конфигурации:\n"
                    "контуры индекс ↔ файл ↔ строка БД, полнота по группам объектов, эталоны по "
                    "четырём выгрузкам,\n"
                    "граница ключа по живым определениям `pg_get_indexdef` (узел V47).",
                    dry, "CHECK")

        ok &= patch(cur, GOAL_ADDRESS,
                    "`rules:core-rules:journal:node:v46` (свойства подсистем и общих модулей, "
                    "контракт 4→5),",
                    "`rules:core-rules:journal:node:v46` (свойства подсистем и общих модулей, "
                    "контракт 4→5),\n"
                    "`rules:core-rules:journal:node:v47` (модули объектов конфигурации, стадия S4b, "
                    "реестр остаётся пятёркой),\n"
                    "`rules:core-rules:journal:node:rule-file-removal` (файл правил слоя снят; "
                    "норматив — карточки слоя),",
                    dry, "SOURCE: история стадий")

        # ── карточка слоя: что загружает сервер (описание заканчивалось стадией S4)
        ok &= patch(cur, LAYER_ADDRESS,
                    "конфигурации, свойства подсистем и общих модулей (стадия S4, узел V46). "
                    "Точка входа одна",
                    "конфигурации, свойства подсистем и общих модулей (стадия S4, узел V46), модули\n"
                    "объектов конфигурации (стадия S4b, узел V47 — тем же вызовом, отдельного входа "
                    "нет). Точка входа одна",
                    dry, "SUMMARY: что загружает сервер")

        # ── проверки слоя: новая проверяющая команда узла (число регистра в карточке уже
        # называет пять — расхождение приписал этому узлу устаревший дамп, см. снимок v47)
        append_after(cur, CHECKS_INDEX, "| `python _layer_ls.py rules:core-rules:` |",
                     "| `python tools/check_v47_configuration_object_modules.py` | модули объектов "
                     "конфигурации: контуры индекс ↔ файл ↔ строка БД, полнота по группам объектов, "
                     "эталоны по четырём выгрузкам, граница ключа `(parent_uuid, file_path, "
                     "revision_no)` по живым определениям `pg_get_indexdef` (узел V47) |",
                     dry, "строка проверок узла V47")

        # ── функция загрузки и карточка инструмента: что входит в выгрузку конфигурации
        ok &= patch(cur, LOAD_CATALOG_ADDRESS,
                    "незагружаемым заголовок конфигурации — он загружается с узла V32, состояние "
                    "стадий читается\nкарточкой `rules:core-rules:functional:goal-and-stages`.",
                    "незагружаемым заголовок конфигурации — он загружается с узла V32, состояние "
                    "стадий читается\nкарточкой `rules:core-rules:functional:goal-and-stages`. "
                    "Называть незагружаемыми модули\nобъектов конфигурации — их пишет стадия S4b того "
                    "же конвейера (узел V47); обещать\nотдельный инструмент дозагрузки модулей — его "
                    "нет (решение Q4.1).",
                    dry, "FORBID")
        ok &= patch(cur, LOAD_CATALOG_ADDRESS,
                    "`rules:core-rules:journal:node:v45` (конвейер S1–S4 и закрытый контракт "
                    "результата).",
                    "`rules:core-rules:journal:node:v45` (конвейер S1–S4 и закрытый контракт "
                    "результата),\n"
                    "`rules:core-rules:journal:node:v46` (свойства подсистем и общих модулей),\n"
                    "`rules:core-rules:journal:node:v47` (модули объектов конфигурации, стадия S4b).",
                    dry, "SOURCE")
        ok &= patch(cur, CATALOG_TOOL_ADDRESS,
                    "модулей — стадия S4, узел V46). Расширение возвращает",
                    "модулей — стадия S4, узел V46; модули объектов конфигурации — слой 2, стадия\n"
                    "S4b, узел V47). Расширение возвращает",
                    dry, "WHEN: состав загрузки конфигурации")

        # ── две узловые записи журнала слоя + строки его перечня
        write_card(cur, JOURNAL_RULEFILE_ADDRESS, JOURNAL_RULEFILE, tags,
                   journal_aliases(JOURNAL_RULEFILE_ADDRESS, "node:rule-file-removal",
                                   RULEFILE_ALIASES_RU), dry)
        write_card(cur, JOURNAL_V47_ADDRESS, JOURNAL_V47, tags,
                   journal_aliases(JOURNAL_V47_ADDRESS, "node:v47", V47_ALIASES_RU), dry)
        # Порядок строк: v46 → v47 → rule-file-removal. Обе строки вставляют после строки v46,
        # поэтому вторая вставляется первой (в dry-записи строки v47 ещё нет, и вторым образцом
        # она быть не может). Признак внесения — адрес в перечне ЛЮБОЙ формы: после `--close`
        # строка выглядит как `git:<hash>`, и повторный прогон не должен добавлять вторую строку
        # того же узла (два перечня одного правила расходятся молча).
        for address, leaf, label in (
                (JOURNAL_RULEFILE_ADDRESS, "node:rule-file-removal", "снят файл правил"),
                (JOURNAL_V47_ADDRESS, "node:v47", "узел V47")):
            if has_row(cur, JOURNAL_INDEX, address):
                print(f"без изменений  {JOURNAL_INDEX}  строка перечня уже есть — {label}")
                continue
            append_after(cur, JOURNAL_INDEX, "`rules:core-rules:journal:node:v46` | git:a7386264",
                         f"| `{address}` | план `{PLAN_DOC}` (28.10.2026) | "
                         f"{journal_section(leaf)} |",
                         dry, f"строка индекса журнала: {label}")

        print("\n" + ("⚠️ ничего не записано (нет --write)" if dry else "✅ записи выполнены"))
        if not ok:
            print("⚠️ часть правок названа отказами — их нельзя пропускать молча.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

