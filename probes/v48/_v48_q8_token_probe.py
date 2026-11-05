"""
_v48_q8_token_probe.py — чем проверка слоя видит имя будущего инструмента «живым обещанием».

`validate_project.py` (через `tools/check_search_rules_sync.py`) сообщает, что карточка
`rules:core-rules:functional:add-object-block` называет `load_session_parameters_tool` «вне
контракта и не снятым», хотя кода узла ещё нет. Проверка считает абзац описанием прежнего
состояния, если в нём стоит маркер из `HISTORY_MARKERS`; где проходит граница абзаца и какой
абзац читается живым — по одному сообщению проверки не видно. Скрипт печатает сами абзацы
живого текста с именем и маркеры, которые в них найдены.

Запуск: `python _v48_q8_token_probe.py`
"""
import sys

sys.path.insert(0, "tools")
sys.path.insert(0, "src")

import check_search_rules_sync as cs  # noqa: E402

TOKEN = "load_session_parameters_tool"
ADDRESS = "rules:core-rules:functional:add-object-block"


def main():
    cards, errors, fatal = cs.layer_document("core-rules")
    if fatal:
        print("⚠️", fatal)
        return 1
    if errors:
        print("ошибки разбора:", errors[:3])
    card = next((c for c in cards if c.get("address") == ADDRESS), None)
    if card is None:
        print("⚠️ карточка не найдена")
        return 1
    live = cs.live_tool_text(card)
    print(f"карточка: ответ {len(card['answer'])} симв., живой текст {len(live)} симв.")
    print("маркеры истории:", " ".join(cs.HISTORY_MARKERS))
    print()
    n = 0
    for para in live.split("\n\n"):
        if TOKEN in para:
            n += 1
            found = [m for m in cs.HISTORY_MARKERS if m in para.lower()]
            print(f"--- абзац живого текста #{n} (маркеры истории: {found or 'нет'}) ---")
            print(para.strip()[:700])
            print()
    if not n:
        print("имени нет в живом тексте — расхождения быть не должно")
    tokens = set(cs.TOOL_TOKEN_RE.findall(live))
    reg = set(cs.registered_tool_names())
    hist = set(cs.historical_tool_names())
    print("регистр инструментов:", len(reg), "| снятых имён:", len(hist))
    print("неизвестные имена карточки:", sorted(tokens - reg - hist) or "нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
