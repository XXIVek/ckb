"""Разовый замер: почему дамп правил отдаёт 78 карточки, а адресов дерева 217.

Вопрос не в карантине (`--marked` добавляет только 5 строк), а в фильтре
`source_url LIKE 'rules-layer://' || '%'`, который стоит в by_marker/by_alias.
Зонд печатает по каждому слою: сколько адресов есть, сколько проходят по схеме,
сколько носят тег слоя, сколько помечено к удалению. После замера файл удаляется.
"""
from src.database import get_connection

SQL = """
SELECT split_part(question, ':', 2) AS seg,
       count(*)                                              AS total,
       count(*) FILTER (WHERE source_url LIKE 'rules-layer://%') AS scheme_ok,
       count(*) FILTER (WHERE 'rules-layer' = ANY(tags))      AS tag_ok,
       count(*) FILTER (WHERE 'mark-for-deletion' = ANY(tags)) AS marked
FROM knowledge_snippets
WHERE question LIKE 'rules:%' OR question = 'rules:'
GROUP BY 1
ORDER BY total DESC
"""


def main():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SQL)
    rows = cur.fetchall()
    print(f"{'слой':<16}{'адресов':>9}{'по схеме':>10}{'по тегу':>9}{'карантин':>10}")
    for seg, total, scheme_ok, tag_ok, marked in rows:
        print(f"{(seg or '(корень)'):<16}{total:>9}{scheme_ok:>10}{tag_ok:>9}{marked:>10}")
    print("ИТОГО", sum(r[1] for r in rows), sum(r[2] for r in rows),
          sum(r[3] for r in rows), sum(r[4] for r in rows))


if __name__ == "__main__":
    main()
