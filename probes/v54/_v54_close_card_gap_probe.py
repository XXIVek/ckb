# -*- coding: utf-8 -*-
"""Разбор лаксуны в карточках слоя core-rules: перечень снимков журнала (узел V54, закрытие).

Повод: карточка `rules:core-rules:functional:goal-and-stages` в разделе `===SOURCE===`
перечисляет разрешимые адреса снимков слоя до `…journal:node:v52`, хотя в базе есть записи
узлов V53 и V54 (`rules:core-rules:journal:node:v53`, `…node:v54`), а индекс ветки `journal`
их отдаёт. Значит, правило-перечень ссылается на неполный состав: читатель карточки, который
по адресам перечня идёт смотреть историю стадий, не увидит двух последних узлов.

Зонд отвечает на три вопроса, на которые отвечает и патч:

1. точный текст перечня (сырые переносы — правка делается границами `replace_span`, а не
   пересказом абзаца);
2. в каких ещё карточках слоя встречается тот же перечень (чтобы правка не осталась точечной
   там, где расхождение в нескольких местах);
3. сходятся ли числа карточек ветки `journal`, которые называют карточка слоя и индекс ветки,
   с базой (число из той же группы расхождений: текст правила расходится с составом строк).

Прогон только читает: записей не меняет.
"""

import sys

sys.path.insert(0, "src")

from database import get_cursor  # noqa: E402

GOAL = "rules:core-rules:functional:goal-and-stages"
LAYER = "rules:core-rules:"
J_INDEX = "rules:core-rules:journal:index"
CHECKS = "rules:core-rules:checks:index"
NEEDLE = "journal:node:v52"


def main():
    with get_cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (GOAL,))
        text = cur.fetchone()["answer"]
        begin = text.find("===SOURCE===")
        print("=== сырой текст раздела SOURCE ===")
        print(repr(text[begin:begin + 2400]))

        print("\n=== карточки слоя, где встречается тот же перечень ===")
        cur.execute(
            "SELECT question FROM knowledge_snippets "
            "WHERE question LIKE 'rules:core-rules:%%' AND answer LIKE %s "
            "ORDER BY question",
            ("%" + NEEDLE + "%",),
        )
        for row in cur.fetchall():
            print(" ", row["question"])

        print("\n=== число карточек ветки journal ===")
        for like, label in (
            ("rules:core-rules:journal:%", "ветка journal целиком"),
            ("rules:core-rules:journal:node:%", "снимки узлов"),
            ("rules:core-rules:journal:pos:%", "снимки позиций"),
            ("rules:core-rules:journal:ref:%", "снимки прежних текстов"),
        ):
            cur.execute(
                "SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s", (like,)
            )
            print(f"  {label}: {cur.fetchone()['n']}")

        print("\n=== строки карточек, где называется число карточек или ветки ===")
        for address in (LAYER, J_INDEX, CHECKS, GOAL):
            cur.execute(
                "SELECT answer FROM knowledge_snippets WHERE question=%s", (address,)
            )
            row = cur.fetchone()
            if not row:
                continue
            for line in (row["answer"] or "").splitlines():
                low = line.lower()
                if "карточ" in low or "ветк" in low or "журнал" in low:
                    print(f"  {address}: {line.strip()[:190]}")

        print("\n=== карточки слоя с перечнем снимков узлов: чего в перечне нет ===")
        cur.execute(
            "SELECT question, answer FROM knowledge_snippets "
            "WHERE question LIKE 'rules:%%' AND answer LIKE %s ORDER BY question",
            ("%journal:node:v51%",),
        )
        for row in cur.fetchall():
            answer = row["answer"] or ""
            missing = [
                node
                for node in ("v52", "v53", "v54")
                if f"journal:node:{node}" not in answer
            ]
            print(
                f"  {row['question']}: есть v51, "
                f"{'НЕТ ' + ','.join(missing) if missing else 'v52/v53/v54 на месте'}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
