#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_xml_format_layer.py — слой знаний формата XML доступен по якорям.

Что сторожит. Инструмент создания внешнего объекта читает профили не «по id», а по стабильным
якорям (id сниппетов меняются при пересоздании базы документации — на это уже натыкались
ссылки config_cross_references). Живого резолвера алиасов у `local_doc` нет: якорь
разрешается путём алиасов самого `search_docs` (точное совпадение, rank 3.0), поэтому для
каждого слоя проверяются четыре вещи одновременно:

  1. search_docs по якорю без категории отдаёт сниппет, и этот сниппет помечен тегом нужной
     категории (иначе якорь ведёт не туда);
  2. search_docs со своей категорией его отдаёт, а с чужими категориями — нет (иначе фильтр
     категории реализован, но слоем не пользуется никто);
  3. текст сниппета содержит маркеры профиля — то есть это именно профиль, а не любая строка
     той же категории;
  4. термины, которые FTS не находит (латинские идентификаторы, русские формулировки),
     находятся по алиасам — иначе слой фактически ненаходим.

Отдельно проверяется известное ограничение поиска: to_tsvector('russian', ...) не
индексирует латинские идентификаторы, поэтому имя свойства (DefaultForm) или имя
идентификатора (ClassId) находится только по алиасу. Это не дефект проверки, а причина, по
которой алиасы имени обязательны: случай фиксируется, чтобы ограничение не «исчезло» из правил.

Слои (LAYERS): профиль свойств ExternalDataProcessor, профиль свойств Configuration.xml
(55 свойств корня конфигурации: что маппится в configurations, что без колонки, а что не
заполняется осознанно — узлы V32/V33, замер MinCfg 19.10.2026), профиль идентификаторов
ClassId/ObjectId/TypeId/ValueId и три слоя структуры выгрузки конфигурации (состав каталогов
видов метаданных, индекс ConfigDumpInfo.xml, расположение uuid объекта конфигурации) — все
категории xml-format; профиль версий UUID — категории platform (его сниппет намеренно размечен
и xml-format, поэтому xml-format у него в «чужих» категориях не проверяется).

Профиль свойств Configuration.xml заведён отдельно от профиля ExternalDataProcessor, хотя
маркеры формата строк у них общие: у профиля конфигурации значимы счётчики `found=/mapped=`
и раздел ROOT_EXT_MODULES (модули предопределённых программ находятся только как файлы Ext/,
соответствующие им колонки конфигурации загрузчик не заполняет) — без этих маркеров профиль
смыкался бы с профилем внешнего объекта и перестал бы отвечать на вопрос «что теряется».

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_xml_format_layer.py
Код возврата 0 — слои доступны. Проверка только читает БД, ничего не пишет.
"""

import sys

sys.path.insert(0, r"C:\1C_LLM\ckb\src")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import database  # noqa: E402
from mcp_tools_api import search_docs  # noqa: E402
from search import list_categories  # noqa: E402

# Каждый слой: якорь (разрешается алиасами поиска), своя категория, маркеры текста профиля и
# термины, которые обязан дать алиас (FTS по-русски латиницу не индексирует).
FOREIGN_BASE = ["its", "language", "methodology"]
LAYERS = [
    {
        "name": "профиль свойств ExternalDataProcessor",
        "anchor": "property-profile-externaldataprocessor",
        "category": "xml-format",
        "markers": ("===PROPERTY_PROFILE", "path|kind|required|default|allowed|provenance"),
        "terms": ["DefaultForm", "AuxiliaryForm"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Профиль свойств корня конфигурации (замер MinCfg, 19.10.2026): 55 свойств,
        # 22 из них маппятся в configurations, 33 без колонки (6 непустых — слепые зоны),
        # 5 колонок не заполняются осознанно. Маркеры счётчиков и раздела модулей —
        # доказательство, что это профиль конфигурации, а не внешнего объекта.
        "name": "профиль свойств Configuration.xml (заголовок конфигурации)",
        "anchor": "property-profile-configuration",
        "category": "xml-format",
        "markers": ("===PROPERTY_PROFILE", "path|kind|required|default|allowed|provenance",
                    "===MAPPING_SUMMARY", "found=55 mapped=22", "===ROOT_EXT_MODULES"),
        "terms": ["ConfigurationExtensionCompatibilityMode", "MainClientApplicationWindowMode",
                  "ObjectAutonumerationMode", "DatabaseTablespacesUseMode"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Карточка ОДНОГО свойства корня (образец для остальных свойств и дочерних объектов):
        # «свойство XML → колонка БД → допустимые значения». Смысл узла V38 в том, чтобы ответ
        # выдавался по ключевому слову сразу, а не собирался из словаря маппинга, замеров
        # выгрузок и XSD в момент вопроса. Маркеры — заголовок карточки, колонка БД и ровно два
        # допустимых значения: подмена значений (например «Normal» вместо «OrdinaryApplication»)
        # роняет проверку, и это ровно тот дефект, который карточка и должна ловить.
        "name": "карточка свойства DefaultRunMode (Основной режим) -> main_mode",
        "anchor": "property-configuration-defaultrunmode",
        "category": "xml-format",
        "markers": ("===PROPERTY_CARD", "column=configurations.main_mode",
                    "ManagedApplication", "OrdinaryApplication"),
        "terms": ["DefaultRunMode", "main_mode", "основной режим"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        "name": "профиль идентификаторов ClassId/ObjectId/TypeId/ValueId",
        "anchor": "identifier-profile-classid-objectid-typeid-valueid",
        "category": "xml-format",
        # presence_boundary/refuted_docs/create_rule — границы, найденные 15.10.2026: у объектов
        # конфигурации ClassId в выгрузке отсутствует, значения из xsd-docs опровергнуты,
        # при создании объекта ContainedObject не пишут (зонд ibcmd). Без этих маркеров профиль
        # снова читался бы как «ClassId есть у любого объекта».
        "markers": ("===IDENTIFIER_PROFILE", "ver_rule:", "our_db:", "not_verified:",
                    "presence_boundary:", "refuted_docs:", "create_rule:"),
        "terms": ["ClassId", "TypeId", "ValueKey", "ContainedObject", "d69d52f4"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        "name": "профиль версий UUID (метаданные против данных)",
        "anchor": "uuid-versions-metadata-vs-data",
        "category": "platform",
        "markers": ("===UUID_VERSION_PROFILE", "not_verified:", "measured_by:"),
        "terms": ["uuid v4", "получитьссылку", "иом"],
        # xml-format у этого сниппета — второй слой намеренно (идентификаторы описаны в XML),
        # поэтому xml-format в «чужих» категориях не проверяется
        "foreign": FOREIGN_BASE,
    },
    # --- структура выгрузки КОНФИГУРАЦИИ (узел V32, замер 17.10.2026 по BGU2) -------------
    # Маркеры — замерные значения, а не условные теги: они и отличают профиль от любой другой
    # строки той же категории (числа дают сами замеры, см. раздел «Структура конфигурации…» в
    # docs/config-scenarios/01_configuration.md).
    {
        "name": "состав выгрузки конфигурации (каталоги видов метаданных)",
        "anchor": "configuration-dump-layout-catalogs",
        "category": "xml-format",
        "markers": ("158 925 XML", "CommonModules 2380", "ParentConfigurations.bin",
                    "Bots, WebSocketClients"),
        "terms": ["CommonModules", "ParentConfigurations.bin", "WebSocketClients",
                  "состав конфигурации"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        "name": "индекс ConfigDumpInfo.xml (перечень объектов и версий)",
        "anchor": "configdumpinfo-index-structure",
        "category": "xml-format",
        "markers": ("86 379", "ConfigVersions", "configVersion",
                    "876c6886-ab84-4942-8098-65d03e2e5119"),
        "terms": ["ConfigDumpInfo", "ConfigVersions", "configVersion", "версии метаданных"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        "name": "uuid объекта конфигурации и отличие от внешнего объекта",
        "anchor": "configuration-object-uuid-location",
        "category": "xml-format",
        "markers": ("<Catalog uuid=", "<CommonModule uuid=", "ContainedObject",
                    "876c6886-ab84-4942-8098-65d03e2e5119"),
        "terms": ["Catalog uuid", "uuid объекта конфигурации", "CommonModule uuid",
                  "GeneratedType"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
]

failures = []
total_checks = 0


def check(name, ok, detail=""):
    """Одна проверка; итоговое число печатает сам скрипт — на числа в правилах смотреть нельзя."""
    global total_checks
    total_checks += 1
    print(f"  [{'OK' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def snippet_ids(rows):
    return {int(r["id"]) for r in rows if r.get("type") == "snippet"}


def snippet_tags(snippet_id):
    """Теги категории сниппета и его текст — прямой SQL, это скрипт-сверка.

    get_cursor — штатный доступ к пулу (возврат соединения делает сам; conn.close()
    соединение из пула не возвращает, а закрывал бы).
    """
    with database.get_cursor() as cur:
        cur.execute("SELECT tags, answer FROM knowledge_snippets WHERE id = %s", (snippet_id,))
        row = cur.fetchone()
    if not row:
        return [], ""
    return (list(row["tags"]) if row["tags"] else []), (row["answer"] or "")


def check_layer(layer):
    """Четыре проверки для одного слоя: якорь, категория, маркеры, находимость терминов."""
    anchor, category, name = layer["anchor"], layer["category"], layer["name"]
    base = snippet_ids(search_docs(anchor, limit=20))
    check(f"[{name}] поиск по якорю без категории что-то отдаёт", bool(base),
          f"snippets: {sorted(base)}")

    tagged = set()
    for sid in sorted(base):
        tags, answer = snippet_tags(sid)
        if category in [t.lower() for t in tags]:
            tagged.add(sid)
            markers = [m for m in layer["markers"] if m in answer]
            check(f"[{name}] текст сниппета — профиль (маркеры на месте)",
                  len(markers) == len(layer["markers"]), f"snippets_id={sid}")
    check(f"[{name}] найденный по якорю сниппет помечен тегом {category}", bool(tagged),
          f"snippets: {sorted(tagged) or 'нет'}")
    if not tagged:
        return

    # фильтр категории слой не прячет и не подмешивает
    own = snippet_ids(search_docs(anchor, category=category, limit=20))
    check(f"[{name}] search_docs(category={category}) находит профиль по якорю",
          bool(tagged & own), f"найдено: {sorted(tagged & own)}")
    for other in layer["foreign"]:
        foreign = snippet_ids(search_docs(anchor, category=other, limit=20))
        check(f"[{name}] чужая категория {other} профиль НЕ отдаёт", not (tagged & foreign))

    # термины, которые FTS не берёт, обязан дать алиас
    for term in layer["terms"]:
        by_alias = snippet_ids(search_docs(term, category=category, limit=20))
        check(f"[{name}] термин «{term}» находится по алиасу (ограничение FTS закрыто алиасами)",
              bool(tagged & by_alias))


def main():
    for layer in LAYERS:
        check_layer(layer)

    # счётчик категории: для xml-format он и есть признак заполненного слоя (слоёв там два),
    # для platform счётчик не различающий — там и так сотни строк, поэтому для него
    # значимы проверки якоря и маркеров, а не число
    cats = {c["code"]: c for c in list_categories()}
    for category in sorted({l["category"] for l in LAYERS}):
        need = len([l for l in LAYERS if l["category"] == "xml-format"]) if category == "xml-format" else 1
        row = cats.get(category)
        check(f"категория {category} есть в справочнике", row is not None)
        if row:
            check(f"счётчик категории {category} учитывает сниппеты слоя (>= {need})",
                  int(row.get("fragment_count", 0)) >= need,
                  f"snippets={row.get('fragment_count')}, aliases={row.get('alias_count')}")

    print(f"\nВсего проверок: {total_checks}, провалено: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
