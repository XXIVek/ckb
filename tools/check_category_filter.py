#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_category_filter.py — проверка фильтра по категории в search_docs.

Дефект, который закрывает проверка (найдено 15.10.2026 при проектировании слоя
«профили свойств внешних объектов»): инструмент search_docs_tool принимал параметр
category и нигде его не использовал — поиск возвращал строки любых категорий, поэтому
отделить знания о формате XML-выгрузки от общей документации было нечем. Второй дефект
мешает проверять результат: list_categories считала строки жёстко по коду 'language'
и по несуществующей таблице documents, из-за чего у всех категорий показывались
одинаковые числа.

Категория в живой схеме local_doc — это значение в text[] tags (groups.tags /
knowledge_snippets.tags / alias_targets.tags) плюс строка-справочник в doc_categories.
Фильтр устроен по тегам ЦЕЛИ, а не по тегам алиаса: алиас может устареть, цель — нет.
Запросы используют пересечение массивов (&&) — оно обслуживается GIN-индексами
idx_groups_tags / idx_snippets_tags.

Что проверяется (живой прогон на local_doc, probe-строки удаляются за собой):
  1. категория xml-format есть в справочнике doc_categories (создаётся при отсутствии —
     тот же код, что в бутстрапе src/database.py);
  2. путь алиасов (шаги 1-2 поиска): без category probe находится; с category своей —
     находится; с category чужой — НЕ находится;
  3. строка без тега категории при category не отдаётся вовсе (иначе «категорийный»
     поиск молча подмешивает нейтральный контент);
  4. путь full-text (шаги 3-4): редкое слово только в answer — без category находит все
     probe-строки, с category — только свою; чужая и нейтральная не отдаются;
  5. category через запятую — пересечение по любому из кодов (обе находятся);
  6. пустая category ведёт себя как отсутствие фильтра;
  7. list_categories различает категории: наша в перечне, её счётчик >= 1, счётчики
     разных категорий не совпадают (прежний запрос давал одинаковые числа);
  8. категория наследуется от группы-родителя: сниппет без собственного тега категории
     находится по категории группы — так устроены BSL-строки (тег категории стоит на
     группе, а не на строке сниппета).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_category_filter.py
Код возврата 0 — все проверки пройдены.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import psycopg2  # noqa: E402

from database import get_db_config  # noqa: E402
from mcp_tools_api import add_snippet, search_docs  # noqa: E402
from search import list_categories  # noqa: E402

CATEGORY = "xml-format"
CATEGORY_NAME = "Формат XML-выгрузки метаданных"
CATEGORY_DESC = (
    "Состав XML-выгрузки объектов метаданных: ExternalReport/ExternalDataProcessor, "
    "формы, макеты СКД; профили свойств (значение по умолчанию, допустимые значения, "
    "происхождение) — то, чем пользуется инструмент создания внешнего объекта"
)
FTS_TOKEN = "категорипроба"  # вымышленное слово: не даёт попаданий по алиасам

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    line = f"  [{'OK' if ok else 'FAIL'}] {name}"
    if detail and not ok:
        line += f"  <- {detail}"
    print(line)


def found_ids(rows):
    return {int(r["id"]) for r in rows if r.get("type") == "snippet"}


def main():
    conn = psycopg2.connect(**get_db_config())
    cur = conn.cursor()

    # 1. Строка-справочник категории (идемпотентно; тот же код, что в бутстрапе).
    cur.execute("SELECT EXISTS(SELECT 1 FROM doc_categories WHERE code = %s)", (CATEGORY,))
    existed = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO doc_categories (code, name, description) VALUES (%s, %s, %s) "
        "ON CONFLICT (code) DO NOTHING",
        (CATEGORY, CATEGORY_NAME, CATEGORY_DESC),
    )
    conn.commit()
    note = "уже была в справочнике" if existed else "добавлена в справочник"
    print(f"Категория {CATEGORY}: {note}")
    print()

    # Probe-строки: A — наша категория, B — чужая (bsl), C — без категории вовсе.
    probes = []
    specs = [
        ("_catprobe_alpha_", "xml-format,probe", "профиль свойства DefaultForm"),
        ("_catprobe_beta_", "bsl,probe", "профиль свойства GeneratedType"),
        ("_catprobe_gamma_", "probe", "профиль свойства Comment"),
    ]
    for alias, tags, subject in specs:
        r = add_snippet(
            question=f"{alias} {subject}",
            answer=(
                f"probe для проверки фильтра по категории. Тело: {subject}. "
                f"{FTS_TOKEN} встречается только здесь, чтобы вызвать путь full-text."
            ),
            source_url="tools/check_category_filter.py#probe",
            tags=tags,
            confidence=1.0,
            aliases=[alias],
        )
        if not r.get("success"):
            print(f"Не создан probe-сниппет {alias}: {r.get('error')}")
            return 1
        probes.append((alias, int(r["snippet_id"])))
    ids = {alias: sid for alias, sid in probes}
    alpha, beta, gamma = ids["_catprobe_alpha_"], ids["_catprobe_beta_"], ids["_catprobe_gamma_"]

    # Probe-группа: категория стоит НА ГРУППЕ, а её сниппет собственного тега категории
    # не имеет — так устроены BSL-строки (language-категория у группы, сниппет нейтрален).
    # Без наследования поиск по категории отдавал бы группы и терял их сниппеты.
    cur.execute("DELETE FROM groups WHERE name = '_catprobe_group_'")  # остатки прошлого прогона
    cur.execute("INSERT INTO groups (name, tags, description) VALUES (%s, %s, %s) RETURNING id",
                ("_catprobe_group_", [CATEGORY, "probe"], "probe-группа: проверка наследования категории"))
    probe_group_id = int(cur.fetchone()[0])
    conn.commit()
    r = add_snippet(
        question="_catprobe_delta_ профиль свойства HelpDescription",
        answer=(
            "probe наследования категории: собственной категории у сниппета нет, "
            f"она только у группы-родителя. {FTS_TOKEN} встречается только здесь."
        ),
        source_url="tools/check_category_filter.py#probe-group",
        tags="probe",
        confidence=1.0,
        groups_id=probe_group_id,
    )
    if not r.get("success"):
        print(f"Не создан probe-сниппет группы: {r.get('error')}")
        cur.execute("DELETE FROM groups WHERE id = %s", (probe_group_id,))
        conn.commit()
        cur.close()
        conn.close()
        return 1
    delta = int(r["snippet_id"])
    print(f"Probe-сниппеты: {alpha} (xml-format), {beta} (bsl), {gamma} (без категории), "
          f"{delta} (через группу {probe_group_id})")
    print()

    try:
        # 2. Путь алиасов: точное совпадение имени (шаги 1-2 поиска).
        got = found_ids(search_docs("_catprobe_alpha_", limit=50))
        check("без category probe своей категории находится (путь алиасов)",
              alpha in got, str(sorted(got)))

        got = found_ids(search_docs("_catprobe_alpha_", category=CATEGORY, limit=50))
        check("category=своя находит probe своей категории", alpha in got, str(sorted(got)))

        got = found_ids(search_docs("_catprobe_alpha_", category="bsl", limit=50))
        check("category=чужая НЕ находит probe другой категории", alpha not in got, str(sorted(got)))

        # 3. Нейтральная строка (без тега категории) при category не отдаётся.
        got = found_ids(search_docs("_catprobe_gamma_", category=CATEGORY, limit=50))
        check("category исключает строку вообще без тега категории",
              gamma not in got, str(sorted(got)))
        got = found_ids(search_docs("_catprobe_gamma_", limit=50))
        check("без category нейтральная строка остаётся находимой",
              gamma in got, str(sorted(got)))

        # 4. Путь full-text (шаги 3-4): слова нет ни в одном алиасе.
        all_probes = {alpha, beta, gamma, delta}
        got = found_ids(search_docs(FTS_TOKEN, limit=50))
        check("full-text без category находит все probe-строки",
              all_probes <= got, str(sorted(got)))

        got = found_ids(search_docs(FTS_TOKEN, category=CATEGORY, limit=50))
        check("full-text с category находит свою категорию и не отдаёт чужую/нейтральную",
              alpha in got and delta in got and beta not in got and gamma not in got,
              str(sorted(got)))

        # 4b. Наследование категории от группы: у delta собственного тега категории нет,
        #     он находится только через группу-родителя (так устроены BSL-строки).
        check("сниппет без своего тега находится по категории родительской группы",
              delta in got, str(sorted(got)))

        # 5. Несколько категорий через запятую — пересечение по любому коду.
        got = found_ids(search_docs(FTS_TOKEN, category=f"{CATEGORY},bsl", limit=50))
        check("category через запятую находит обе запрошенные категории",
              alpha in got and beta in got and delta in got and gamma not in got,
              str(sorted(got)))

        # 6. Пустая category = отсутствие фильтра.
        got = found_ids(search_docs(FTS_TOKEN, category="", limit=50))
        check("пустая category ведёт себя как отсутствие фильтра",
              all_probes <= got, str(sorted(got)))

        # 7. list_categories различает категории (прежний запрос давал одинаковые числа).
        cats = {c["code"]: c for c in list_categories()}
        check("категория появилась в перечне list_categories", CATEGORY in cats)
        if CATEGORY in cats:
            check("счётчик категории учитывает её сниппеты",
                  int(cats[CATEGORY].get("fragment_count", 0)) >= 1,
                  f"fragment_count={cats[CATEGORY].get('fragment_count')}")
        counts = [int(c.get("fragment_count", 0)) for c in cats.values()]
        check("счётчики разных категорий различаются (дефект одинаковых чисел снят)",
              len(set(counts)) > 1, str(sorted(counts)))
    finally:
        # Уборка: алиасы снимаются каскадом (alias_targets.snippets_id ON DELETE CASCADE).
        probe_ids = [sid for _, sid in probes] + [delta]
        cur.execute("DELETE FROM knowledge_snippets WHERE id = ANY(%s)", (probe_ids,))
        cur.execute("DELETE FROM groups WHERE id = %s", (probe_group_id,))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM knowledge_snippets WHERE id = ANY(%s)", (probe_ids,))
        left = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM alias_targets WHERE alias_name = ANY(%s)",
                    ([spec[0] for spec in specs],))
        left_aliases = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM groups WHERE name = '_catprobe_group_'")
        left_group = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"\nУборка: probe-сниппетов осталось {left}, probe-алиасов осталось {left_aliases}, "
              f"probe-групп осталось {left_group}")
        check("после уборки probe-строк не осталось",
              left == 0 and left_aliases == 0 and left_group == 0)

    total = len(results)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\nПроверок: {total}, провалено: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

