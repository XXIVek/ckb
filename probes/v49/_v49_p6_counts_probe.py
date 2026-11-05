# -*- coding: utf-8 -*-
"""_v49_p6_counts_probe.py — фактические числа круга V49 в живой базе.

Зачем. Постоянная проверка `tools/check_v49_roles.py` обязана сравнивать круг с числами
плана (`docs/CONFIGURATION_ROLES_PLAN.md`, раздел 2 и раздел 7 «критерии готовности»), а не
с тем, что получилось в момент написания скрипта. Прежде чем записывать ожидания в скрипт,
числа снимаются этим зондом — по живой базе, по каждой строке заголовка отдельно.

Зонд только читает. Он называет и то, чего касались уже в модели A–H: число строк шаблонов
ограничений отличается от числа различных текстов и различных имён (позиция O6), и все три
величины обязаны быть названы раздельно — «строк 18 при 9 текстах» и «1+7+8» несовместимы,
поэтому какое из них_FACT_, решает только запрос.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from external_db import transaction  # noqa: E402

# Круг мерится по параметру конфигурации: %(u)s — uuid строки заголовка, %(i)s — её id.
AGGREGATES = [
    ("roles (CURRENT)", """
        SELECT count(*) FROM v_current_roles r
         WHERE r.configuration_uuid = %(u)s::uuid"""),
    ("role_sources (CURRENT)", """
        SELECT count(*) FROM v_current_role_sources s
         WHERE s.configuration_uuid = %(u)s::uuid"""),
    ("role_rights (через v_current_roles)", """
        SELECT count(*) FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid"""),
    ("role_restriction_templates (CURRENT, строк)", """
        SELECT count(*) FROM v_current_role_restriction_templates t
         WHERE t.configuration_uuid = %(u)s::uuid"""),
    ("шаблоны: различных digest", """
        SELECT count(DISTINCT t.digest) FROM v_current_role_restriction_templates t
         WHERE t.configuration_uuid = %(u)s::uuid"""),
    ("шаблоны: различных name", """
        SELECT count(DISTINCT t.name) FROM v_current_role_restriction_templates t
         WHERE t.configuration_uuid = %(u)s::uuid"""),
    ("индекс состава: Role.* верхнего уровня", """
        SELECT count(*) FROM configuration_objects o
         WHERE o.configuration_id = %(i)s AND o.object_type = 'Role'
           AND (o.child_type IS NULL OR o.child_type = '')"""),
    ("индекс состава: Role.*.Rights", """
        SELECT count(*) FROM configuration_objects o
         WHERE o.configuration_id = %(i)s AND o.object_type = 'Role'
           AND o.child_type = 'Rights'"""),
    ("configurations.roles[] (длина)", """
        SELECT coalesce(array_length(roles, 1), 0) FROM configurations
         WHERE uuid = %(u)s::uuid"""),
    ("roles: empty_content", """
        SELECT count(*) FROM v_current_roles r
         WHERE r.configuration_uuid = %(u)s::uuid AND r.content_state = 'empty_content'"""),
    ("roles: with_rights", """
        SELECT count(*) FROM v_current_roles r
         WHERE r.configuration_uuid = %(u)s::uuid AND r.content_state = 'with_rights'"""),
    ("role_rights: exact / prefix_only / unresolved", """
        SELECT count(*) FILTER (WHERE rr.target_resolve_state = 'exact'),
               count(*) FILTER (WHERE rr.target_resolve_state = 'prefix_only'),
               count(*) FILTER (WHERE rr.target_resolve_state = 'unresolved')
          FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid"""),
]

# Продолжение круга — состояния, согласованность счётчиков и носители шаблонов. Эти меры не
# выводятся из CHECK: CHECK отклоняет противоречие внутри одной строки, а равенство «счётчик
# строки роли = число строк прав» и «множество носителей ⊆ имён ролей» выражаются только
# проверкой.
AGGREGATES += [
    ("role_rights: unknown_name / unknown_form", """
        SELECT count(*) FILTER (WHERE rr.right_name_state = 'unknown_name'),
               count(*) FILTER (WHERE rr.right_value_state = 'unknown_form')
          FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid"""),
    ("role_rights: granted / denied", """
        SELECT count(*) FILTER (WHERE rr.right_value_state = 'granted'),
               count(*) FILTER (WHERE rr.right_value_state = 'denied')
          FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid"""),
    ("role_rights: with_call / no_call / no_condition", """
        SELECT count(*) FILTER (WHERE rr.condition_state = 'with_call'),
               count(*) FILTER (WHERE rr.condition_state = 'no_call'),
               count(*) FILTER (WHERE rr.condition_state = 'no_condition')
          FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid"""),
    ("role_rights: с полем <field>", """
        SELECT count(*) FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid
           AND rr.restriction_field_name IS NOT NULL"""),
    ("role_rights: различных имён права", """
        SELECT count(DISTINCT rr.right_name) FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid"""),
    ("role_rights: различных целей", """
        SELECT count(DISTINCT rr.target_full_name) FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid"""),
    ("role_sources: состояния", """
        SELECT string_agg(s.declaration_state || '=' || s.c, ', ')
          FROM (SELECT declaration_state, count(*) AS c FROM v_current_role_sources s
                 WHERE s.configuration_uuid = %(u)s::uuid
                 GROUP BY declaration_state) s"""),
]

# Инварианты круга — то, что не выражается ни CHECK, ни витриной (колонки этих связей в
# схеме нет осознанно: прецедент V20.1).
AGGREGATES += [
    ("роли ↔ индекс состава: расхождений имён", """
        SELECT (SELECT count(*) FROM (
                  SELECT object_name FROM v_current_roles
                   WHERE configuration_uuid = %(u)s::uuid
                  EXCEPT
                  SELECT replace(o.object_name, 'Role.', '') FROM configuration_objects o
                   WHERE o.configuration_id = %(i)s AND o.object_type = 'Role'
                     AND (o.child_type IS NULL OR o.child_type = '')
                ) a)
             + (SELECT count(*) FROM (
                  SELECT replace(o.object_name, 'Role.', '') FROM configuration_objects o
                   WHERE o.configuration_id = %(i)s AND o.object_type = 'Role'
                     AND (o.child_type IS NULL OR o.child_type = '')
                  EXCEPT
                  SELECT object_name FROM v_current_roles
                   WHERE configuration_uuid = %(u)s::uuid
                ) b)"""),
    ("роли ↔ перечень заголовка: расхождений", """
        SELECT (SELECT count(*) FROM (
                  SELECT object_name FROM v_current_roles
                   WHERE configuration_uuid = %(u)s::uuid
                  EXCEPT
                  SELECT unnest(roles) FROM configurations WHERE uuid = %(u)s::uuid
                ) a)
             + (SELECT count(*) FROM (
                  SELECT unnest(roles) FROM configurations WHERE uuid = %(u)s::uuid
                  EXCEPT
                  SELECT object_name FROM v_current_roles
                   WHERE configuration_uuid = %(u)s::uuid
                ) b)"""),
    ("прав, висящих не на CURRENT-роли", """
        SELECT count(*) FROM role_rights rr
          LEFT JOIN v_current_roles r ON r.id = rr.role_id
         WHERE rr.configuration_uuid = %(u)s::uuid AND r.id IS NULL"""),
    ("ролей со счётчиком прав без строк прав", """
        SELECT count(*) FROM v_current_roles r
         WHERE r.configuration_uuid = %(u)s::uuid AND r.rights_count > 0
           AND NOT EXISTS (SELECT 1 FROM v_current_role_rights rr
                            WHERE rr.role_id = r.id)"""),
    ("шаблонов с носителями вне перечня ролей", """
        SELECT count(*) FROM v_current_role_restriction_templates t
          JOIN configurations c ON c.uuid = t.configuration_uuid
         WHERE t.configuration_uuid = %(u)s::uuid
           AND EXISTS (SELECT 1 FROM unnest(t.holder_role_names) h
                        WHERE NOT (h = ANY (c.roles)))"""),
    ("шаблонов, где длина не равна тексту", """
        SELECT count(*) FROM v_current_role_restriction_templates t
         WHERE t.configuration_uuid = %(u)s::uuid
           AND t.condition_length <> char_length(t.condition_text)"""),
    ("прав с именем шаблона вне строк шаблонов", """
        SELECT count(*) FROM v_current_role_rights rr
         WHERE rr.configuration_uuid = %(u)s::uuid
           AND rr.restriction_template_names IS NOT NULL
           AND EXISTS (SELECT 1 FROM unnest(rr.restriction_template_names) n
                        WHERE NOT EXISTS (SELECT 1 FROM v_current_role_restriction_templates t
                                           WHERE t.configuration_uuid = rr.configuration_uuid
                                             AND t.name = n))"""),
]


def main():
    with transaction() as cur:
        cur.execute("SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
        headers = [dict(zip(("id", "uuid", "name"), row)) for row in cur.fetchall()]
        print("строк заголовков:", len(headers))
        for header in headers:
            print(f"\n### {header['name']} (id={header['id']})")
            for label, sql in AGGREGATES:
                try:
                    cur.execute(sql, {"u": header["uuid"], "i": header["id"]})
                    row = cur.fetchone()
                except Exception as exc:  # мера не выразима — называется, а не замалчивается
                    print(f"    {label:<52} ОТКАЗ: {type(exc).__name__}: {exc}")
                    cur.connection.rollback()
                    continue
                value = row[0] if row else None
                extra = ""
                if row and len(row) > 1:
                    extra = " | " + " | ".join(str(item) for item in row[1:])
                print(f"    {label:<52} {value}{extra}")


if __name__ == "__main__":
    main()
