#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Живая проверка узла P6 (`get_snippet` / `update_snippet`) против базы `local_doc`.

Зачем отдельный прогон. `validate_project.py` и `tools/check_mcp_tool_wiring.py` проверяют
статику: живые имена функций, константу усечения, состав регистра инструментов. Живое поведение
без обращения к базе не проверить: выполняется ли собранный `UPDATE` (правка только алиасов не
меняет ни `question`, ни `answer`, ни `tags` — пустой `SET` падал бы до аудита), пишется ли
строка истории, остаются ли прежние алиасы, переживает ли тег карантина замену тегов.

Что проверяется:

  ПРОВЕРКА 1 (P6.1) — карточка сниппета отдаёт содержимое целиком, а не превью в 200 символов;
  ПРОВЕРКА 2 (P6.2) — длинный текст усекается до порога с явными `answer_chars` и
                      `answer_truncated` (усечённый ответ нельзя читать как полный);
  ПРОВЕРКА 3 (P6.3) — правка меняет существующую строку, а не создаёт вторую; прежний текст
                      целиком лежит в `snippet_audit_log` (`action=fix`);
  ПРОВЕРКА 4 (P6.4) — `tags` заменяются целиком, снятие тега категории называется прямо,
                      карантин правка не снимает и не ставит, пустой набор тегов отклоняется;
  ПРОВЕРКА 5 (P6.5) — алиасы аддитивны: прежние целы, существующий не удваивается, новый
                      добавляется ровно один раз;
  ПРОВЕРКА 6        — негативные ветки: пустая правка и правка без причины — отказ, строки
                      аудита при этом нет; несуществующий id — `success=False` с `found=False`;
  ПРОВЕРКА 7        — состояние таблицы аудита по живой схеме: строка хранит снимок
                      old/new, колонки актора (`changed_by`) в ней нет — поэтому правила не
                      обязаны утверждать, что инструмент подписывает строку своим именем.

Уборка за собой: прогон снимает свою строку, её алиасы и её строки аудита; чужие строки не
меняются, счётники возвращаются к началу прогона. `--keep` — оставить созданную строку (её id
печатается строкой `SNIPPET_ID=<id>`, чтобы убрать вручную).

Запуск:
    python tools/_p6_live_probe.py [--keep]
Код возврата 0 — провалов нет; 1 — есть.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

from mcp_tools_api import (  # noqa: E402
    MAX_ANSWER_CHARS, add_snippet, get_snippet, mark_snippet_for_deletion,
    unmark_snippet_for_deletion, update_snippet)
from mcp_tools_core import _get_pool  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []

QUESTION = "П6 probe: как прочитать содержимое сниппета по ID, а не по превью"
SHORT_ANSWER = "Процедура Пример():\n    Сообщить(\"полный текст, а не превью\");\nКонецПроцедуры;"
LONG_ANSWER = ("Сообщить(\"строка " + "x" * 60 + "\");\n") * 300
ALIAS_EXISTING = "p6-probe-alias"
ALIAS_NEW = "p6-probe-alias-new"
SOURCE_URL = "probe://p6-live"


def section(title):
    print(f"\n{title}")
    print("-" * 70)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'OK  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))


def _fetch(sql, params=None, one=False):
    pool = _get_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        if one:
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
        rows = cur.fetchall()
        conn.commit()
        return rows
    finally:
        pool.putconn(conn)


def sql_one(sql, params=None):
    return _fetch(sql, params, one=True)


def sql_rows(sql, params=None):
    return _fetch(sql, params)


def cleanup(snippet_id):
    """Снять всё, что создал прогон. Порядок: аудит → алиасы → строка сниппета."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM snippet_audit_log WHERE snippet_id = %s", (snippet_id,))
        cur.execute("DELETE FROM alias_targets WHERE snippets_id = %s", (snippet_id,))
        cur.execute("DELETE FROM knowledge_snippets WHERE id = %s", (snippet_id,))
        conn.commit()
    finally:
        pool.putconn(conn)


def main():
    keep = "--keep" in sys.argv[1:]
    baseline = {
        "snippets": sql_one("SELECT COUNT(*) FROM knowledge_snippets"),
        "audit": sql_one("SELECT COUNT(*) FROM snippet_audit_log"),
    }
    print("Живая проверка узла P6: чтение и правка сниппета по ID (local_doc)")
    print("=" * 70)
    print(f"  порог усечения MAX_ANSWER_CHARS = {MAX_ANSWER_CHARS}")
    print(f"  базовые счётники: snippets={baseline['snippets']}, audit={baseline['audit']}")

    made = add_snippet(QUESTION, SHORT_ANSWER, source_url=SOURCE_URL,
                       tags="xml-format,code,p6-probe", confidence=0.95,
                       aliases=[ALIAS_EXISTING])
    if not made.get("success"):
        print(f"❌ не удалось создать проверочную строку: {made.get('error')}")
        return 1
    sid = int(made["snippet_id"])
    print(f"  SNIPPET_ID={sid}")

    try:
        # ─────────── ПРОВЕРКА 1 (P6.1): содержимое целиком, а не превью ───────────
        section("ПРОВЕРКА 1 (P6.1): карточка сниппета — содержимое целиком, а не превью")
        card = get_snippet(sid)
        check("карточка получена", card.get("success") is True, str(card.get("error", "")))
        check("question отдан целиком", card.get("question") == QUESTION)
        check("answer отдан целиком (совпадает с записанным побайтово)",
              card.get("answer") == SHORT_ANSWER,
              f"получено {len(str(card.get('answer')))} симв. из {len(SHORT_ANSWER)}")
        check("признака усечения у полного текста нет",
              card.get("answer_truncated") is False
              and card.get("answer_chars") == len(SHORT_ANSWER))
        check("теги, уверенность и источник отдаются",
              "p6-probe" in (card.get("tags") or []) and card.get("confidence") == 0.95
              and card.get("source_url") == SOURCE_URL)
        check("алиасы перечислены с полным счётчиком",
              ALIAS_EXISTING in [a.get("alias_name") for a in (card.get("aliases") or [])]
              and (card.get("aliases_total") or 0) >= 1,
              f"aliases_total={card.get('aliases_total')}")

        # ─────────── ПРОВЕРКА 2 (P6.2): усечение длинного текста названо явно ───────────
        section("ПРОВЕРКА 2 (P6.2): длинный текст усекается с явным счётчиком и признаком")
        upd = update_snippet(sid, new_answer=LONG_ANSWER,
                             reason="П6 probe: проверка усечения длинного ответа")
        check("правка принята", upd.get("success") is True, str(upd.get("error", "")))
        check("изменённое поле названо", upd.get("changed") == ["answer"], str(upd.get("changed")))
        card2 = get_snippet(sid)
        check("answer_chars равен полной длине", card2.get("answer_chars") == len(LONG_ANSWER),
              f"{card2.get('answer_chars')} против {len(LONG_ANSWER)}")
        check("answer_truncated = True при тексте длиннее порога",
              len(LONG_ANSWER) > MAX_ANSWER_CHARS and card2.get("answer_truncated") is True)
        check("отдано ровно `MAX_ANSWER_CHARS` символов",
              len(str(card2.get("answer"))) == MAX_ANSWER_CHARS,
              f"получено {len(str(card2.get('answer')))}")

        # ─────────── ПРОВЕРКА 3 (P6.3): правка строки, а не вторая строка ───────────
        section("ПРОВЕРКА 3 (P6.3): изменена существующая строка, прежний текст — в истории")
        same = sql_one("SELECT COUNT(*) FROM knowledge_snippets WHERE question = %s", (QUESTION,))
        check("второй строки с тем же вопросом не появилось", same == 1, f"строк: {same}")
        audit = sql_rows("SELECT action, old_answer, new_answer, old_question, new_question "
                         "FROM snippet_audit_log WHERE snippet_id = %s ORDER BY id", (sid,))
        check("строка аудита ровно одна", len(audit) == 1, f"строк: {len(audit)}")
        if audit:
            action, old_answer, new_answer, old_question, new_question = audit[0]
            check("action = fix", action == "fix", str(action))
            check("прежний answer сохранён целиком", old_answer == SHORT_ANSWER)
            check("новый answer сохранён целиком", new_answer == LONG_ANSWER)
            check("неизменённое поле записано прежним значением, а не пустой строкой",
                  old_question == QUESTION and new_question == QUESTION)
        check("ответ инструмента ссылается на историю",
              str(upd.get("note", "")).find("snippet_audit_log") >= 0 and bool(upd.get("audit_id")))

        # ─────────── ПРОВЕРКА 4 (P6.4): теги, категории и карантин ───────────
        section("ПРОВЕРКА 4 (P6.4): снятие категории названо, карантин правка не трогает")
        empty_tags = update_snippet(sid, tags=[], reason="П6 probe: пустой набор тегов")
        check("пустой набор тегов отклонён",
              empty_tags.get("success") is False
              and "пустой набор тегов" in str(empty_tags.get("error", "")).lower())
        marked = mark_snippet_for_deletion(sid, reason="П6 probe: проверка сохранения карантина")
        check("строка помечена к удалению", marked.get("success") is True,
              str(marked.get("error", "")))
        upd_tags = update_snippet(sid, tags=["code", "p6-probe"],
                                  reason="П6 probe: замена тегов со снятием категории")
        check("правка тегов принята", upd_tags.get("success") is True,
              str(upd_tags.get("error", "")))
        check("снятая категория названа прямо",
              upd_tags.get("dropped_categories") == ["xml-format"],
              str(upd_tags.get("dropped_categories")))
        check("карантин правка сохранила (и метку, и причину)",
              upd_tags.get("marked") is True and bool(upd_tags.get("marked_reason")),
              f"marked={upd_tags.get('marked')}, reason={upd_tags.get('marked_reason')}")
        card3 = get_snippet(sid)
        check("карточка помеченной строки отдаёт признак и причину",
              card3.get("marked") is True and bool(card3.get("marked_reason")))
        unmarked = unmark_snippet_for_deletion(sid)
        check("пометка снята", unmarked.get("success") is True, str(unmarked.get("error", "")))

        # ─────────── ПРОВЕРКА 5 (P6.5): алиасы аддитивны ───────────
        section("ПРОВЕРКА 5 (P6.5): прежние алиасы целы, дубль не удваивается, новый — один раз")
        before = int(card3.get("aliases_total") or 0)
        alias_upd = update_snippet(sid, aliases=[ALIAS_EXISTING, ALIAS_NEW],
                                   reason="П6 probe: аддитивная правка алиасов")
        check("правка только алиасов выполняется (пустого `SET` нет)",
              alias_upd.get("success") is True, str(alias_upd.get("error", "")))
        check("существующий алиас не добавлен повторно",
              alias_upd.get("aliases_requested") == 2 and alias_upd.get("aliases_added") == 1,
              f"requested={alias_upd.get('aliases_requested')}, "
              f"added={alias_upd.get('aliases_added')}")
        card4 = get_snippet(sid)
        check("прежние алиасы остались", (card4.get("aliases_total") or 0) == before + 1,
              f"было {before}, стало {card4.get('aliases_total')}")
        names = [a.get("alias_name") for a in (card4.get("aliases") or [])]
        check("новый алиас появился, прежний на месте",
              ALIAS_NEW in names and ALIAS_EXISTING in names)
        update_snippet(sid, aliases=[ALIAS_NEW], reason="П6 probe: повтор того же алиаса")
        dup = sql_one("SELECT COUNT(*) FROM alias_targets WHERE snippets_id = %s "
                      "AND alias_name = %s", (sid, ALIAS_NEW))
        check("после повторного вызова дубля алиаса нет", dup == 1, f"строк: {dup}")

        # ─────────── ПРОВЕРКА 6: негативные ветки ───────────
        section("ПРОВЕРКА 6: пустая правка, правка без причины, несуществующий id")
        audit_before = sql_one("SELECT COUNT(*) FROM snippet_audit_log WHERE snippet_id = %s",
                               (sid,))
        no_change = update_snippet(sid, reason="П6 probe: пустая правка")
        check("пустая правка отклонена",
              no_change.get("success") is False
              and "ни одного изменения" in str(no_change.get("error", "")).lower())
        no_reason = update_snippet(sid, new_answer="П6 probe: правка без причины")
        check("правка без причины отклонена",
              no_reason.get("success") is False
              and "причин" in str(no_reason.get("error", "")).lower())
        audit_after = sql_one("SELECT COUNT(*) FROM snippet_audit_log WHERE snippet_id = %s",
                              (sid,))
        check("отклонённые правки не попали в аудит", audit_after == audit_before,
              f"было {audit_before}, стало {audit_after}")
        missing = get_snippet(999_999_999)
        check("несуществующий id — success=False с found=False",
              missing.get("success") is False and missing.get("found") is False)

        # ─────────── ПРОВЕРКА 7: состояние таблицы аудита по живой схеме ───────────
        section("ПРОВЕРКА 7: аудит хранит снимок old/new, колонки актора в нём нет")
        cols = {r[0] for r in sql_rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='snippet_audit_log'")}
        check("снимок QUESTION и ANSWER до/после правки в схеме аудита есть",
              {"old_question", "new_question", "old_answer", "new_answer"} <= cols,
              ", ".join(sorted(cols)))
        check("колонки актора (`changed_by`) нет — источник правки различается текстом `reason`",
              "changed_by" not in cols)
    finally:
        if keep:
            print(f"\n  строка оставлена в базе: SNIPPET_ID={sid}")
        else:
            cleanup(sid)
        left = sql_one("SELECT COUNT(*) FROM knowledge_snippets WHERE id = %s", (sid,))
        after = {
            "snippets": sql_one("SELECT COUNT(*) FROM knowledge_snippets"),
            "audit": sql_one("SELECT COUNT(*) FROM snippet_audit_log"),
        }
        section("УБОРКА ЗА СОБОЙ")
        if keep:
            check("проверочная строка оставлена по --keep", left == 1)
        else:
            check("проверочная строка снята", left == 0)
            check("счётники вернулись к началу прогона", after == baseline,
                  f"после: {after}, базовые: {baseline}")

    failed = [name for name, ok, _ in RESULTS if not ok]
    print("\n" + "=" * 70)
    print(f"ИТОГ: проверок {len(RESULTS)}, провалено {len(failed)}, пропущено 0")
    for name in failed:
        print(f"  ❌ {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())



