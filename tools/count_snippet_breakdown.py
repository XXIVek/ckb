# -*- coding: utf-8 -*-
"""Разбивка knowledge_snippets для честных счётчиков в .clinerules/1c-knowledge-base_Rule.md.

Прежняя строка правил («2 876 = 1 226 PDF + 1 496 BSL + 154 без группы») перестала сходиться
с живым числом. Скрипт печатает разбивку по тому же признаку, что описан в правилах:
groups_id IS NOT NULL — привязан к группе; тег 'pdf' — загруженные PDF; остальное — ручные и
прочие без группы. Сумма обязана равняться общему числу, иначе разбивку в правила писать нельзя.
"""
import sys

sys.path.insert(0, r"C:\1C_LLM\ckb\src")
import database  # noqa: E402

SQL = """
SELECT count(*) AS total,
       count(*) FILTER (WHERE groups_id IS NOT NULL)                    AS with_group,
       count(*) FILTER (WHERE 'pdf' = ANY(tags))                       AS pdf_tag,
       count(*) FILTER (WHERE 'xml-format' = ANY(tags))                AS xml_format,
       count(*) FILTER (WHERE groups_id IS NULL
                          AND NOT ('pdf' = ANY(tags)))                 AS no_group_other,
       (SELECT count(*) FROM alias_targets)                            AS aliases_total,
       (SELECT count(*) FROM alias_targets a WHERE a.target_type='snippet'
          AND a.snippets_id IN (SELECT id FROM knowledge_snippets
                                 WHERE 'xml-format' = ANY(tags)))      AS aliases_xml_format,
       (SELECT count(*) FROM alias_targets a WHERE a.target_type='snippet'
          AND a.snippets_id IN (SELECT id FROM knowledge_snippets
                                 WHERE 'pdf' = ANY(tags)))             AS aliases_pdf
FROM knowledge_snippets
"""

with database.get_cursor() as cur:
    cur.execute(SQL)
    row = cur.fetchone()

total = int(row["total"])
# Грань разбивки та же, что описана в правилах: привязанные к группе, PDF-сниппеты (всегда без
# группы) и прочие без группы. xml-format — подмножество третьей части, в сумму не входит.
parts = int(row["with_group"]) + int(row["pdf_tag"]) + int(row["no_group_other"])
print(f"snippets всего: {total}")
print(f"  с groups_id:         {row['with_group']}")
print(f"  тег pdf:             {row['pdf_tag']}")
print(f"  без группы и не pdf: {row['no_group_other']}  (из них тег xml-format: {row['xml_format']})")
print(f"сумма разбивки (with_group + pdf + no_group_other): {parts} -> "
      f"{'сходится' if parts == total else 'НЕ сходится'}")
print(f"aliases всего: {row['aliases_total']}, к xml-format: {row['aliases_xml_format']}, "
      f"к pdf: {row['aliases_pdf']}")
