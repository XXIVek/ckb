#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка текста правил поиска с кодом MCP-сервера `server.py` (только статика, БД не трогается).

Зачем. 20.10.2026 `get_search_rules_tool()` отдал `SEARCH_RULES.md` с шапкой «актуально на
07.10.2026»: счётчики ниже живых (snippets ~1 498 против 2 887, aliases 198 643 против 208 529),
категорий 4 против пяти, в таблице инструментов нет карантина (узел Q1) и нет самих инструментов
правил, а шаг интерпретации обещает «Извлекаем answer — пример кода», которого поиск не отдаёт
(выдача урезана до 200 символов, `src/mcp_tools_api.py::search_docs`). Вызов Шага 0 поэтому не
спасает: он даёт устаревший текст, который сам вводит в заблуждение. Причина не в тексте, а в
отсутствии сверки: `tools/check_mcp_tool_wiring.py` накрывал только три сервера конфигураций,
`server.py` не сверялся с документами ничем.

Что проверяется:
  1. `server.py` входит в DEFAULT_TARGETS и в EXPECTED_TOOLS `check_mcp_tool_wiring.py`
     (иначе проверка контракта молча перестала бы считать инструменты knowledge-base);
  2. каждое имя `*_tool`, упомянутое в правилах поиска, реально зарегистрировано в одном из
     четырёх MCP-серверов (класс дефекта «правило обещает инструмент, которого нет»);
  3. обязательные маркеры механики поиска присутствуют в обоих текстах: алиасный шаг — точное
     совпадение; выдача — ID + превью; содержимое группы читается `get_doc_tool`, содержимого
     сниппета — `get_snippet_tool`, правка — `update_snippet_tool` (узел P6, 20.10.2026: дефект
     «содержимое сниппета не читается ничем» закрыт, поэтому маркер теперь требует читателя, а не
     констатирует пробел); порог усечения назван константой; счётчики берутся из замера, а не из
     текста;
  4. запрещённые устаревшие утверждения не вернулись в текст (замерные числа 07.10.2026,
     обещание «Извлекаем answer», «категорий 4», формулировка открытого дефекта чтения сниппета).

Код возврата 0 — расхождений нет; 1 — есть (печатаются конкретные строки).

Запуск:
    python tools/check_search_rules_sync.py        # PYTHONIOENCODING задавать не нужно
Включён в validate_project.py шагом 9.

Кодировка вывода. Строка итога содержит «✅», а консоль Windows по умолчанию cp1251: без
перекодирования stdout сторож падал UnicodeEncodeError на ПОСЛЕДНЕЙ строке, уже подтвердив, что
расхождений нет (замер 20.10.2026: rc=1 при полностью совпадающих правилах и коде). Ложный провал
хуже молчаливого пропуска: через несколько прогонов перестанешь верить ответу сторожа вообще.
Поэтому вывод перекодируется здесь, а не перекладывается на оператора. Тот же приём, что в
validate_project.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass  # вывод уже заменён на не-текстовый поток — на решение влиять нечем

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from check_mcp_tool_wiring import DEFAULT_TARGETS, EXPECTED_TOOLS, _tool_functions  # noqa: E402

DOC_FILES = [
    ROOT / "SEARCH_RULES.md",
    ROOT / ".clinerules" / "1c-knowledge-base_Rule.md",
]

SERVER_FILES = [
    ROOT / "server.py",
    ROOT / "server_configurations_core.py",
    ROOT / "server_configurations_enrichment.py",
    ROOT / "server_configurations_export.py",
]

TOOL_TOKEN = re.compile(r"\b[a-z][a-z0-9_]*_tool\b")

# Обязательные маркеры: факт, который нельзя терять из текста правил. Проверка маркером,
# а не числом — по той же причине, что в _cmp_ddl.py и check_xml_format_layer.py: число живёт
# замер, а утверждение о механике обязано жить в тексте.
REQUIRED_MARKERS = {
    "alias_exact": ["точное совпадение"],
    "preview_only": ["200 символов"],
    "group_reader": ["get_doc_tool"],
    # узел P6 (20.10.2026): маркер требует читателя и правку сниппета, а не констатирует пробел.
    # Прежний маркер «snippet_reader_gap» («содержимое сниппета») пропускал текст, который
    # по-прежнему говорит «прочитать нечем», — то есть регрессия закрытого дефекта не считалась бы
    # расхождением. Теперь отсутствие инструмента в правилах = расхождение.
    "snippet_reader": ["get_snippet_tool"],
    "snippet_updater": ["update_snippet_tool"],
    "truncation_named": ["MAX_ANSWER_CHARS"],
    "counters_from_measurement": ["get_db_state_tool"],
    "rules_tool": ["get_search_rules_tool"],
}

# То, что вернулось бы как регрессия найденных 20.10.2026 дефектов.
FORBIDDEN = [
    "Извлекаем answer — пример кода",
    "198 643",
    "1 498",
    "актуально на 07.10.2026",
    "Категории документации | 4",
    # закрытый узлом P6 открытый дефект чтения сниппета: вернуть эту формулировку — значит
    # вернуть в правила утверждение, которого в коде больше нет.
    "не читается ни одним инструментом контракта",
    "содержимое сниппета по ID не читается ничем",
]

def registered_tool_names():
    """Имена инструментов, реально зарегистрированных во всех MCP-серверах (AST)."""
    import ast
    names = {}
    for path in SERVER_FILES:
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        names[path.name] = sorted(node.name for node in _tool_functions(tree))
    return names


def _rel(path):
    """Путь для текста проблемы. Файл правил вне корня не должен ронять сам отчёт.

    `relative_to` бросает ValueError вне корня: сообщение «в правилах упомянут инструмент,
    которого нет» превращалось бы в traceback без вердикта — тот же класс дефекта, что падение
    на кодировке строки итога (см. шапку модуля). Отчёт обязан дожить до вывода.
    """
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def main():
    problems = []

    # 1. Собственная предпосылка: server.py в круге проверки контракта.
    if not any(Path(p).name == "server.py" for p in DEFAULT_TARGETS):
        problems.append("server.py не входит в DEFAULT_TARGETS tools/check_mcp_tool_wiring.py — "
                        "контракт knowledge-base никем не сверяется")
    if "server.py" not in EXPECTED_TOOLS:
        problems.append("server.py нет в EXPECTED_TOOLS tools/check_mcp_tool_wiring.py — "
                        "лишний или пропавший инструмент knowledge-base не считается регрессией")

    servers = registered_tool_names()
    known = set()
    for names in servers.values():
        known.update(names)
    kb_count = len(servers.get("server.py", []))

    # 2. Упомянутые в правилах инструменты обязаны существовать.
    doc_texts = {}
    for doc in DOC_FILES:
        if not doc.is_file():
            problems.append(f"файл правил не найден: {_rel(doc)}")
            continue
        text = doc.read_text(encoding="utf-8")
        doc_texts[doc] = text
        for name in sorted(set(TOOL_TOKEN.findall(text))):
            if name not in known:
                problems.append(f"{_rel(doc)}: упомянут инструмент {name}(), "
                                f"которого нет ни в одном MCP-сервере")

    # 3. Обязательные маркеры механики поиска и 4. возврат устаревших утверждений.
    for doc, text in doc_texts.items():
        low = text.lower()
        for key, markers in REQUIRED_MARKERS.items():
            if not any(m.lower() in low for m in markers):
                problems.append(f"{_rel(doc)}: нет маркера механики поиска «{key}» "
                                f"(ожидается один из: {', '.join(markers)})")
        for stale in FORBIDDEN:
            if stale in text:
                problems.append(f"{_rel(doc)}: вернулось устаревшее утверждение "
                                f"«{stale}»")

    print("Сверка текста правил поиска с кодом MCP-серверов (статика, БД не открывается)")
    print("=" * 70)
    for name, names in servers.items():
        print(f"  {name}: инструментов {len(names)}")
    print(f"  файлов правил: {len(doc_texts)}, известных инструментов: {len(known)}")
    print("=" * 70)
    if problems:
        for problem in problems:
            print(f"❌ {problem}")
        print(f"\n❌ расхождений: {len(problems)}")
        return 1
    print(f"✅ текст правил поиска совпадает с кодом: инструментов knowledge-base {kb_count}, "
          f"маркеры механики поиска на месте, устаревших утверждений нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())

