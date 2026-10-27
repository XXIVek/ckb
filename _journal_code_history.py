#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Покрытие истории изменений кода MCP записями слоя (узел JOURNAL-COVERAGE, план П1).

Зачем: карточки `rules:<слой>:functional:edit-mcp-code` велят писать узел журнала об изменении
состава инструментов, но ни одна проверка не сверяла, что об изменениях регистра вообще что-то
записано. Инструмент отвечает по каждому слою кода MCP на два вопроса:

1. сколько в слое карточек журнала, какие из них об изменении кода или состава и какая дата в
   самом свежем таком узле (это справочные строки, не мера);
2. покрыто ли каждое имя инструмента, упомянутое в коммите, менявшем регистр (`@mcp.tool()`,
   `EXPECTED_TOOLS`, `DELETED_TOOLS`), записью слоя — живой карточкой или узлом журнала.

Мерой является имя, а не дата. Замер 28.10.2026: сравнение дат дало два ложных провала в
`kb-rules` и `core-rules` — коммит `d957ee2e` (26.10.2026) удалял из кода `get_load_rules_tool`,
`get_search_rules_tool`, `get_load_config_rules_tool`, исполняя решение, узел о котором записан
24.10.2026. Дата записи предшествует исполнению почти всегда, поэтому по датам покрытой выглядит
только та история, где код отстал, а не та, где её не записали.

Порог (решение D3 плана `docs/RULES_CONTEXT_PLAN.md`): провалом считается только случай, когда имя
не читается в слое НИ живой карточкой, НИ узлом журнала. Живая карточка — действующее правило
(форма «удалено, потому что…»); узел журнала — снимок, и слой вправе его не вести (у export-слоя
перечень журнала снят узлом RESTRUCTURE-LAYERS 27.10.2026 как дубль).

Числа регистра берутся из `EXPECTED_TOOLS` того же файла, что и проверка проводки
(`tools/check_mcp_tool_wiring.py`), а не из текста узла: снимок журнала описывает прошлое
состояние, и расхождение с текущим числом — не ошибка снимка, а признак того, что узла о
текущем состоянии нет.

Запуск:
    python _journal_code_history.py                # четыре слоя кода MCP
    python _journal_code_history.py kb-rules       # один слой
    python _journal_code_history.py --nodes        # показывать узлы журнала с датами

Код возврата: 0 — имена изменений читаются в слоях; 1 — есть имя, не читаемое нигде в слое.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
import quarantine as Q  # noqa: E402
from check_mcp_tool_wiring import DELETED_TOOLS, EXPECTED_TOOLS  # noqa: E402
from database import get_cursor  # noqa: E402

# Слой правил -> файл регистра его инструментов. Имена файлов, а не метки: EXPECTED_TOOLS
# индексируется файлами, и вторая копия отображения разошлась бы с проверкой проводки.
LAYER_SERVER = {
    "kb-rules": "server.py",
    "core-rules": "server_configurations_core.py",
    "enrich-rules": "server_configurations_enrichment.py",
    "export-rules": "server_configurations_export.py",
}

# Узел журнала считается рассказывающим об изменении кода или состава, если в нём есть имя
# регистра или слова о составе. Разбор широкий намеренно: снимок может описывать узел кода без
# чисел — такие записи тоже относятся к истории правок.
CODE_MARKS = re.compile(
    r"@mcp\.tool|EXPECTED_TOOLS|DELETED_TOOLS|состав инструментов|изменил[аи]? состав|"
    r"сня[тщ]ы?е? инструмент|инструмент(?:ов|а|ы)? (?:слоя|регистра|контракта|сервера)|"
    r"\d+\s*(?:→|->)\s*\d+",
    re.IGNORECASE,
)
GIT_MARKS = r"@mcp\.tool|EXPECTED_TOOLS|DELETED_TOOLS"
# Имя инструмента регистра из изменённой строки (`def load_doc_tool(`, имя в списке
# `EXPECTED_TOOLS`, декоратор над ним). Мера — имя, а не дата: коммит исполняет решение, узел о
# котором записан раньше, и по датам такая история выглядит непокрытой (замер 28.10.2026).
TOOL_NAME = re.compile(r"\b([a-z][a-z0-9_]*_tool)\b")
DATE_ISO = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
DATE_DOTS = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(20\d{2})(?!\d)")


def dates_of(text):
    """Даты снимка в обоих форматах, которыми они пишутся в текстах узлов."""
    found = []
    for m in DATE_ISO.finditer(text):
        found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in DATE_DOTS.finditer(text):
        found.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
    return sorted(found)


def journal_nodes(marker):
    """Карточки журнала слоя: (адрес, текст, даты, об_коде_ли). Снятые строки не считаются."""
    where, params = RL.layer_sql(marker)
    sql = (f"SELECT question, answer, tags FROM knowledge_snippets WHERE {where}"
           f"{Q.sql_not_marked('tags')}")
    with get_cursor() as cur:
        cur.execute(sql, tuple(params) + (list(Q.MARK_ARRAY),))
        rows = cur.fetchall()
    out = []
    for row in rows:
        rel = RL.layer_relative(row["question"], marker)
        if RL.state_of(rel) != RL.STATE_JOURNAL:
            continue
        text = row["answer"] or ""
        out.append((rel, text, dates_of(text), bool(CODE_MARKS.search(text))))
    return sorted(out, key=lambda item: (item[2][-1] if item[2] else date.min, item[0]))


def composition_commits(path, limit=40):
    """Коммиты, менявшие строки регистра инструментов, и имена затронутых инструментов.

    `-G` фильтрует по диффу одним вызовом; имена берутся из изменённых строк (`def *_tool`,
    `@mcp.tool`, списки `EXPECTED_TOOLS`/`DELETED_TOOLS`) — по ним покрытие и проверяется.
    """
    res = subprocess.run(
        ["git", "--no-pager", "log", "--format=%H%x09%ad", "--date=short", "-G", GIT_MARKS,
         "--", path],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if res.returncode != 0:
        return None
    commits = []
    for line in res.stdout.splitlines()[:limit]:
        sha, _, day = line.partition("\t")
        try:
            year, month, day_no = (int(x) for x in day.split("-"))
        except ValueError:
            continue
        show = subprocess.run(
            ["git", "--no-pager", "show", "--format=", "--unified=0", sha, "--", path],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        names = set()
        for diff_line in show.stdout.splitlines():
            if diff_line.startswith(("+", "-")) and not diff_line.startswith(("+++", "---")):
                names.update(TOOL_NAME.findall(diff_line))
        commits.append((date(year, month, day_no), sha[:8], names))
    return sorted(commits)


def layer_texts(marker):
    """Тексты слоя двумя частями: живые карточки и узлы журнала (снятые строки не считаются)."""
    where, params = RL.layer_sql(marker)
    sql = (f"SELECT question, answer FROM knowledge_snippets WHERE {where}"
           f"{Q.sql_not_marked('tags')}")
    with get_cursor() as cur:
        cur.execute(sql, tuple(params) + (list(Q.MARK_ARRAY),))
        rows = cur.fetchall()
    live, journal = [], []
    for row in rows:
        rel = RL.layer_relative(row["question"], marker)
        (journal if RL.state_of(rel) == RL.STATE_JOURNAL else live).append(row["answer"] or "")
    return "\n".join(live), "\n".join(journal)


def compact(text):
    """Текст без пробелов и переводов строк — по нему ищется имя инструмента.

    Тексты карточек переносятся на 90–95 символов, и длинное имя (`get_config_snippet_tool`)
    оказывается разорванным между строками. Обычный поиск подстроки дал бы ложный провал ровно на
    тех именах, которые в слое названы (замер 28.10.2026: 11 «непокрытых» имён enrich-слоя и 19
    в kb-слое, часть из которых в карточках есть). Имя инструмента пробелов не содержит, поэтому
    снятие всей пустоты ничего не склеивает кроме переноса.
    """
    return re.sub(r"\s+", "", text or "")


def foreign_names(server):
    """Имена инструментов других серверов регистра.

    Дифф файла сервера упоминает чужое имя в docstring или комментарии («аналог add_snippet_tool»,
    «снимок — как в add_aliases_tool»): это ссылка на чужой контракт, а не изменение состава этого
    слоя. Требовать от слоя называть чужой инструмент значило бы требовать того, что прямо запрещено
    `tools/check_search_rules_sync.py` — живые имена чужих инструментов в правилах слоя.
    Замер 28.10.2026: без этого исключения enrich-слой проваливался на `add_snippet_tool`,
    `add_aliases_tool`, а kb-слой — на `get_config_snippet_tool`, которые относятся к другим
    серверам.
    """
    return {name for other, names in EXPECTED_TOOLS.items() if other != server for name in names}


def report_layer(marker, show_nodes=False):
    server = LAYER_SERVER[marker]
    registry = len(EXPECTED_TOOLS.get(server, []))
    nodes = journal_nodes(marker)
    code_nodes = [n for n in nodes if n[3]]
    last_node = code_nodes[-1] if code_nodes else None
    commits = composition_commits(server) or []
    live_text, journal_text = layer_texts(marker)

    print(f"\n[{marker}] регистр {server}: {registry} инструментов")
    print(f"  карточек журнала: {len(nodes)}, из них об изменении кода/состава: {len(code_nodes)}")
    if last_node:
        day = last_node[2][-1].isoformat() if last_node[2] else "дата в тексте не названа"
        print(f"  (справочно) самый свежий узел о составе: {day}  {last_node[0]}")
    else:
        print("  (справочно) узлов об изменении кода/состава в журнале нет")
    if not commits:
        print("  коммитов, менявших регистр, git не показывает — измерять нечего")
        return True
    names = set()
    for _, _, changed in commits:
        names |= changed
    print(f"  коммитов, менявших регистр: {len(commits)} (последний "
          f"{commits[-1][0].isoformat()} {commits[-1][1]}), имён в их диффах: {len(names)}")
    if show_nodes:
        for rel, text, days, is_code in nodes:
            mark = "код" if is_code else "   "
            day = days[-1].isoformat() if days else "----------"
            print(f"    [{mark}] {day}  {rel}  {len(text)} симв.")

    if not names:
        print("  → имён инструментов в диффах нет: состав регистра эти коммиты не меняли, "
              "покрытие не измеряется — это не провал")
        return True
    foreign = names & foreign_names(server)
    demanded = names - foreign
    live_flat, journal_flat = compact(live_text), compact(journal_text)
    in_live = {name for name in demanded if name in live_flat}
    in_journal = {name for name in demanded - in_live if name in journal_flat}
    uncovered = sorted(demanded - in_live - in_journal)
    print(f"  чужих имён в диффах (регистр другого сервера, покрытием не считаются): {len(foreign)}")
    print(f"  покрыто живой карточкой: {len(in_live)}, узлом журнала: {len(in_journal)}, "
          f"не покрыто нигде: {len(uncovered)}")
    if uncovered:
        print("  → НЕ ПОКРЫТО: имя изменения регистра не читается в слое ни живой карточкой, "
              "ни узлом журнала: " + ", ".join(uncovered[:8]))
        untracked = [name for name in uncovered if name not in DELETED_TOOLS]
        print(f"    из них {len(uncovered) - len(untracked)} названо снятым в `DELETED_TOOLS` "
              f"(механизм регистра есть, текста правила нет); {len(untracked)} вне `DELETED_TOOLS` "
              "— снятие или переименование не записаны даже механизмом регистра")
        return False
    print("  → история покрыта: каждое имя изменения регистра читается записью слоя")
    return True


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    show_nodes = "--nodes" in args
    markers = [a for a in args if not a.startswith("--")] or list(LAYER_SERVER)
    unknown = [m for m in markers if m not in LAYER_SERVER]
    if unknown:
        print(f"слоёв кода MCP нет среди известных: {', '.join(unknown)}; "
              f"мои слои: {', '.join(LAYER_SERVER)}")
        return 2
    ok = all([report_layer(m, show_nodes) for m in markers])
    print("\n=== ИТОГ ===")
    print("✅ имена изменений регистра читаются записями слоёв" if ok
          else "❌ есть имя изменения регистра, не читаемое в слое ни живой карточкой, "
               "ни узлом журнала")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

