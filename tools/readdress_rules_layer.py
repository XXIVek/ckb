"""Переадресация карточек слоя в журнал (узел RULE-V2, 24.10.2026).

Зачем отдельный инструмент. Слой формата 1 — перенесённый файл правил: его карточки описывают
состояние проекта до перехода на иерархический индекс, но содержат замеры, причины решений и
проверки, которые нельзя выбрасывать. Удалять их — значит потерять историю; оставлять под
рабочими адресами — значит выдать снимок за действующее правило (например, «алиасный шаг ищет
по подстроке» из старой карточки против текущего «точное совпадение всего запроса»).

Поэтому прежние карточки переезжают в состояние `journal`:

    <метка>:ref:NN      -> <метка>:journal:NN
    <метка>:index       -> <метка>:journal:index   (прежний индекс слоя становится снимком)

Строка при этом не удаляется и не создаётся заново: правится та же запись `update_snippet`
(прежнее содержимое уходит в `snippet_audit_log`), а прежний адрес добавляется алиасом — иначе
ссылка из индекса или из прежнего разговора ведёт в никуда. Текст ответа не меняется: журнал
переписывать нельзя, он и есть запись о том, что было.

Теги пересчитываются по новому адресу: у правил слоя появляется своя категория (`*-rules`), и
строка журнала остаётся в той же категории, что и рабочие правила слоя, — различает их тег
состояния и префикс адреса, а не отдельная категория.

Запуск:

    python tools/readdress_rules_layer.py --layer kb-rules            # только разбор
    python tools/readdress_rules_layer.py --layer kb-rules --apply    # запись

Код возврата 1 — писать нечего или запись отклонена.
"""

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # сбой настройки потока не меняет итог операции
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import rules_layer as RL  # noqa: E402

REASON_DEFAULT = ("узел RULE-V2: карточки слоя формата 1 переведены в состояние journal — "
                  "снимок прежних правил остаётся в базе, рабочие правила пишутся новым форматом")


def journal_address(address, marker):
    """Новый адрес карточки журнала или None, если карточка не переезжает.

    Переезжают только карточки переноса и прежний индекс слоя: они описывали файл правил.
    Всё остальное (уже написанные правила новых состояний) остаётся на месте — молча увести
    рабочее правило в журнал значит снять его с применения.

    Семейства журнала различаются сегментом происхождения, и это не косметика: в слое уже
    лежат датированные дополнения шапки файла правил (`journal:01…`), и перенесённые разделы
    дали бы с ними одинаковые адреса (замер 24.10.2026: `ref:01` и `journal:01` — разные
    тексты на одном адресе). Поэтому:

        <метка>:ref:NN            -> <метка>:journal:ref:NN   (перенесённые разделы правил)
        <метка>:journal:NN        -> <метка>:journal:hdr:NN   (дополнения шапки файла)
        <метка>:index             -> <метка>:journal:index    (прежний индекс слоя)
    """
    if not address.startswith(marker + ":"):
        return None
    rest = address[len(marker) + 1:]
    if rest == RL.INDEX_LEAF:
        return f"{marker}:journal:{RL.INDEX_LEAF}"
    if rest.startswith("ref:"):
        return f"{marker}:journal:{rest}"
    if rest.startswith("journal:"):
        tail = rest[len("journal:"):]
        if tail and all(part.isdigit() for part in tail.split(":")):
            # точка в адресе запрещена грамматикой, часть карточки разделяется дефисом
            return f"{marker}:journal:hdr:{tail.replace(':', '-')}"
        return None
    return None


def plan_moves(rows, marker):
    """Список переходов и список ошибок. Коллизии проверяются до записи: две карточки на одном
    адресе — это ровно тот дефект, из-за которого поиск отдаёт два разных знания по одному
    запросу (замер 24.10.2026 на kb-rules:ref:01 и kb-rules:journal:01)."""
    moves, errors, taken = [], [], {}
    existing = {row["question"] for row in rows}
    for row in rows:
        old = row["question"]
        new = journal_address(old, marker)
        if new:
            errors += [f"{old} -> {new}: {e}" for e in RL.validate_address(new, marker)]
            if new in existing:
                errors.append(f"адрес {new} уже занят карточкой слоя — переезд создал бы "
                              f"две карточки на одном адресе")
                continue
            if new in taken:
                errors.append(f"коллизия адресов журнала: {taken[new]} и {old} -> {new}")
                continue
            taken[new] = old
            moves.append((row, new))
    return moves, errors




def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Перевод карточек слоя правил в состояние journal (узел RULE-V2)")
    ap.add_argument("--layer", required=True, help="метка слоя (например kb-rules)")
    ap.add_argument("--apply", action="store_true",
                    help="записать в local_doc (по умолчанию только разбор)")
    ap.add_argument("--reason", default=REASON_DEFAULT, help="причина правки для аудита")
    args = ap.parse_args(argv)

    marker = args.layer
    if marker not in RL.LAYERS:
        print(f"неизвестная метка слоя {marker!r} — известными считаются {list(RL.LAYERS)}")
        return 1

    from database import get_cursor, seed_categories
    from mcp_tools_api import update_snippet

    moved = retagged = kept = failed = 0
    with get_cursor() as cur:
        seed_categories(cur)
        cur.execute(
            "SELECT id, question, answer, tags, source_url FROM knowledge_snippets "
            "WHERE question LIKE %s AND source_url LIKE %s ORDER BY question",
            (marker + ":%", RL.SOURCE_SCHEME + "%"),
        )
        rows = [dict(row) for row in cur.fetchall()]
        moves, errors = plan_moves(rows, marker)
        for err in errors:
            failed += 1
            print(f"  ОТКАЗ: {err}")
        moving = {row["id"] for row, _ in moves}
        for row, new in moves:
            old = row["question"]
            if not args.apply:
                moved += 1
                print(f"  переедет: {old} -> {new} (прежний адрес станет алиасом)")
                continue
            res = update_snippet(
                row["id"], new_question=new, new_answer=None, tags=RL.tags_for(new, marker),
                aliases=old, reason=args.reason)
            if res.get("success"):
                # source_url обязан следовать за адресом: это ключ идемпотентности загрузки
                # слоя, и оставленный ключ прежнего адреса позволяет следующей загрузке слоя
                # найти карточку журнала по ключу рабочей карточки и перезаписать её (замер
                # 24.10.2026: 28 строк kb-rules остались с ключом прежнего адреса, проверка
                # слоя называет это «source_url перестаёт быть ключом идемпотентности»).
                cur.execute("UPDATE knowledge_snippets SET source_url = %s WHERE id = %s",
                            (RL.source_url(new), row["id"]))
                moved += 1
                print(f"  переехала: {old} -> {new}")
            else:
                failed += 1
                print(f"  ОТКАЗ записи {old}: {res.get('error') or 'строки нет'}")
        for row in rows:
            if row["id"] in moving:
                continue
            old = row["question"]
            tags = set(row["tags"] or [])
            primary = RL.category_of(marker)
            need_tag = bool(primary) and primary not in tags
            need_key = row["source_url"] != RL.source_url(old)
            # Карточка уже в журнале и уже переезжала: адрес менять нечего, но тег категории у
            # неё прежний — без перетегиования проверка слоя не нашла бы категорию на строке.
            # Эта же ветка чинит ключ source_url, оставшийся от прежнего адреса.
            if RL.state_of(old) == "journal" and (need_tag or need_key):
                if not args.apply:
                    retagged += 1
                    what = ("тег категории " + primary) if need_tag else ""
                    what += (" " if need_tag and need_key else "") + ("ключ source_url" if need_key else "")
                    print(f"  исправляется: {old} ({what})")
                    continue
                if need_tag:
                    res = update_snippet(row["id"], new_question=None, new_answer=None,
                                         tags=RL.tags_for(old, marker), reason=args.reason)
                    if not res.get("success"):
                        failed += 1
                        print(f"  ОТКАЗ перетегиования {old}: {res.get('error') or 'строки нет'}")
                        continue
                if need_key:
                    cur.execute("UPDATE knowledge_snippets SET source_url = %s WHERE id = %s",
                                (RL.source_url(old), row["id"]))
                retagged += 1
                print(f"  исправлена: {old}")
                continue
            kept += 1
            print(f"  без изменений: {old}")


    if not rows:
        print(f"в слое {marker!r} карточек нет — переводить нечего; пустой прогон ничего "
              f"не подтверждает")
        return 1
    print(f"\nстрок в слое: {len(rows)}, "
          f"{'переведено' if args.apply else 'к переводу'}: {moved}, "
          f"{'перетегиовано' if args.apply else 'к перетегиованию'}: {retagged}, "
          f"без изменений: {kept}, отказов: {failed}")
    if not args.apply:
        print("в БД не писали — нужен --apply")
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
