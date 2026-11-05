#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Карточка `rules:checks:root-hygiene` + строка перечня + снятие устаревшего номера шага.

Зачем: узел ROOT-FILES (05.11.2026) разложил файлы корня по классам и завёл постоянную
проверку `tools/check_root_hygiene.py`. Правило о размещении без карточки остаётся рассказом:
проверка есть, а требования, которые она сторожит, нигде не записаны. Вторая правка — карточка
`rules:checks:project-integration` называла шаг `check_rules_layer` числом «шагом 10»; после
встраивания новой проверки шаг стал одиннадцатым, и число в правиле стало отставать от прогона
(тот же класс расхождения, что «правило называет 5 инструментов, а регистр даёт 4»).

Идемпотентность — по `source_url` (уникального ограничения на него в схеме нет, приём взят у
`probes/misc/_add_core_journal_nodes.py`); теги новой карточки берутся у соседней строки того
же состояния, чтобы новая карточка выглядела строкой ряда.

Запуск:
    python probes/misc/_add_root_hygiene_rule.py            # что будет сделано
    python probes/misc/_add_root_hygiene_rule.py --write    # записать
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

CARD = "rules:checks:root-hygiene"
TAGS_FROM = "rules:checks:project-integration"
INDEX = "rules:checks:index"

TEXT = """===WHEN
Корень репозитория — место точек входа, а не место складывания: разбор 05.11.2026 нашёл в
корне 332 файла рядом с 13 точками входа — 34 файла поставки схемы, 39 измерителей чужих узлов,
3 документа-одиночки, 238 файлов вывода замеров (`.txt`, `.log`, `.err`, снятые `.json`),
3 черновых запроса и дамп базы на 108 МБ. Накопление шло месяцами потому, что описание
разложения было в `.gitignore` и `probes/README.md`, а факта никто не сверял.

Читать правило нужно, когда в корень появляется файл, когда меняется положение класса файлов
(поставка схемы, измеритель узла, вывод замера, документ) или когда после переноса правится
путь в коде, — и перед тем, как сказать «каталог разобран».

===MUST
1. В корне лежат только точки входа: серверы MCP (`server*.py`), валидаторы проекта
   (`validate_*.py`), генератор алиасов и `.gitignore`. Перечень держит список
   `ALLOWED_ROOT_FILES` проверки `tools/check_root_hygiene.py`; новый файл в корне возможен
   только внесённым в этот список сознательно.
2. У каждого класса файлов одно место. Поставка схемы — `sql/`: DDL-загрузка
   `create_1c_configurations_db.sql`, аддитивные миграции `migrate_vNN_*.sql`, SQL-сверки
   `check_external_report_*.sql`; её читают `tools/check_v32_zero_configuration.py`,
   `tools/check_v42_configuration_header.py`, `tools/check_v31_provenance.py` и зонды узлов.
   Измеритель узла — `probes/<узел>/` рядом с зондом, который его читает. Вывод замера —
   `_scratch/`. Документ — `docs/`, промпт-задание узла — `docs/prompts/`, прежний текст —
   `docs/legacy/`.
3. Писать вывод замера разрешено только в `_scratch/` (приём `probes/v50/_v50_p2_offline_probe.py`,
   `probes/v56/_v56_p3_offline_probe.py`). Рядом с зондом писать нельзя: выход измерения
   засоряет круг доказательств и перестаёт отличаться от измерителя. Путь вывода строится от
   `_scratch/` явно — `ROOT / "_scratch" / "<имя>.txt"` (приём `probes/v43/_v43_gen_sql.py`,
   исправлен 05.11.2026): путь `ROOT / "<имя>.txt"` означает возврат в корень при запуске из
   корня, и заметен он только после прогона. Фикстура, которую читает
   зонд, остаётся в каталоге узла и трекается — без неё замер не воспроизвести
   (`probes/v46/_v46_props_bp3.json`, `probes/misc/_v40_slots_table.json`,
   `probes/v54/_v54_p5_card_min.cfg`).
4. Исторические строки правил и планов новым путём не переписываются: строка карточки — запись
   того, как выглядел замер на дату. Тексты правил называют артефакты голыми именами, и вопрос
   «существует ли названный файл» разрешает поиск по каталогам (`rules_layer.artifact_exists`
   читает `probes/*/` и `sql/`), а не подмена имени в снимке.
5. Путь, собранный в коде от корня репозитория к файлу поставки, измерителя или фикстуры,
   обязан существовать: перенос класса файлов без правки пути — это ссылка кода в никуда.
   Путь вывода замера проверяется другим способом: он обязан строиться от `_scratch/` и
   существовать между прогонами не обязан. Разбираются только конструкции с явным
   основанием-переменной корня; путь от каталога выгрузки, каталога ИБ или текущего каталога
   остаётся вне разбора — это названная граница проверки.

6. Дамп базы в репозиторий не кладётся ни в какой каталог: копия живой базы — не вывод замера и
   не поставка схемы. Точку восстановления создаёт штатная процедура `tools/backup_databases.py`
   (узел ARCHIVE-BD) в каталоге вне репозитория — `C:\\1C_LLM\\Arhiv_BD`, где держатся точки
   отката, описания `RESTORE_<база>.md` и манифест с sha256 и результатом контрольного
   восстановления. Ручная копия рядом с замером заводит вторую, не связанную с процедурой
   россыпь: замер 05.11.2026 нашёл в `_scratch/` четыре файла на 1292.3 МБ при актуальной
   точке архива от 03.11.2026, тогда как весь круг доказательств весит 15.3 МБ. Сжатия в этой
   сборке нет: `pg_dump` 17.2 на `-Z 6` отвечает `invalid compression specification`, zstd тоже
   не поддержан (замер 05.11.2026), поэтому размер копии — 44–52 % от размера базы при `-Z0`,
   и экономия возможна только внешней упаковкой (замер: дамп одной таблицы 324.7 МБ → 30.3 МБ).

===FORBID
- класть в корень замер, дамп прогона, снимок карточки, документ-одиночку или фикстуру чужого узла;
- класть дамп базы в репозиторий (`*.dump`, `*.bak`, `_backup*`) вместо штатной точки, создаваемой
  `tools/backup_databases.py` вне репозитория;
- переписывать историческое упоминание новым путём вместо разрешения имени;
- называть местом правки правила `_scratch/`, `logs/`, `layers/`, `Arhiv_Rules/` — это снимки
  и вывод, правилом они не являются;
- считать перенос завершённым без проверки состава корня: «разложил» без сторожа означает, что
  через месяц в корне снова триста файлов.

===TOOLS
MCP-инструментов не требует.

===CHECK
python tools/check_root_hygiene.py, python validate_project.py

===SOURCE
Узел ROOT-FILES (05.11.2026), продолжение узла ROOT-RESTRUCTURE (тот же признак разделения:
класс определяется по использованию файла, а не по имени). Числа разбора и перечень перенесённого —
снимок rules:journal:node:root-files."""


# Строка перечня проверок. Колонка «чем проверяется» читается проверкой слоя как ссылка на
# инструмент: названное имя обязано разрешаться файлом.
INDEX_ROW = ("| rules:checks:root-hygiene | что лежит в корне репозитория и куда переносить "
             "классы файлов; пути кода к поставке схемы и измерителям разрешаются | "
             "check_root_hygiene.py, validate_project.py |")

# Карточка интеграции проверок называла шаг числом; после встраивания новой проверки число
# отстаёт. Число убирается, смысл («замыкает прогон перед слоями правил») остаётся.
PI_OLD = "шагом 10 (`check_rules_layer`)"
PI_NEW = "шагом, замыкающим прогон перед слоями правил (`check_rules_layer`)"


MD_FILE = ROOT / "docs" / "rules" / "rules.md"
# Карточка вставляется перед первой карточкой журнала — порядок секций исходника повторяет
# порядок дерева, а не порядок записи.
MD_ANCHOR = "## rules:journal:"


def sync_md() -> str:
    """Парная правка исходника слоя правил.

    Проверка слоя сверяет текст строки БД с текстом `docs/rules/rules.md`: «правило есть»
    перестаёт быть правдой, если БД и место правки расходятся (замер 05.11.2026: прогон
    проекта назвал расхождения именно так — правка ушла в БД без исходника).
    """
    text = MD_FILE.read_text(encoding="utf-8")
    done = []
    head = f"## {CARD}\n"
    if head in text:
        start = text.index(head)
        nxt = text.find("\n## ", start + len(head))
        body_end = nxt if nxt != -1 else len(text)
        text = text[:start] + head + "\n" + TEXT + "\n" + text[body_end:]
        done.append("карточка заменена")
    else:
        pos = text.index(MD_ANCHOR)
        text = text[:pos] + head + "\n" + TEXT + "\n\n" + text[pos:]
        done.append("карточка вставлена перед разделом журнала")
    if INDEX_ROW not in text:
        lines = text.splitlines()
        last = max(i for i, line in enumerate(lines) if line.lstrip().startswith("| rules:checks:"))
        lines.insert(last + 1, INDEX_ROW)
        text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        done.append("строка перечня добавлена")
    if PI_OLD in text:
        text = text.replace(PI_OLD, PI_NEW)
        done.append("номер шага снят")
    MD_FILE.write_text(text, encoding="utf-8")
    return ", ".join(done) if done else "исходник уже содержит правки"


def main(argv=None):
    write = "--write" in (argv or sys.argv[1:])
    with get_cursor() as cur:
        cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s", (TAGS_FROM,))
        row = cur.fetchone()
        if not row:
            raise SystemExit("нет строки-образца тегов: карточка проверок не найдена")
        tags = list(row["tags"] or [])

        key = f"{RL.SOURCE_SCHEME}{CARD}"
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE source_url=%s", (key,))
        known = cur.fetchone()
        print(f"карточка: {'обновляется' if known else 'создаётся'}  {CARD}  {len(TEXT)} симв., теги {tags}")
        if write:
            if known:
                cur.execute("UPDATE knowledge_snippets SET answer=%s, tags=%s WHERE id=%s",
                            (TEXT, tags, known["id"]))
            else:
                cur.execute(
                    "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url,"
                    " tags, confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, 1.0, TRUE)",
                    (CARD, TEXT, key, tags))

        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (INDEX,))
        card = cur.fetchone()
        if not card:
            raise SystemExit("перечень проверок не найден")
        text = card["answer"] or ""
        if CARD in text:
            print("перечень: строка уже есть")
            if text != text.rstrip("\n"):
                if write:
                    cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                                (text.rstrip("\n"), card["id"]))
                print("перечень: концевые переводы строки сняты (форма загрузчика)")
        else:
            lines = text.splitlines()
            last = max((i for i, line in enumerate(lines) if line.lstrip().startswith("| rules:checks:")),
                       default=None)
            if last is None:
                raise SystemExit("в перечне нет таблицы — строка не добавлена")
            lines.insert(last + 1, INDEX_ROW)
            if write:
                # Форма строки — та, что даёт загрузчик исходника: карточка из файла
                # читается без концевых переводов строки, и концевой "\n" в БД — это
                # расхождение текста с исходником (замер 05.11.2026: проверка назвала его
                # «текст БД совпадает с исходником» при равных 1672 символах).
                cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                            ("\n".join(lines), card["id"]))
            print("перечень: строка добавлена после:", lines[last][:60])

        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (TAGS_FROM,))
        pi = cur.fetchone()
        if pi and PI_OLD in (pi["answer"] or ""):
            if write:
                cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                            (pi["answer"].replace(PI_OLD, PI_NEW), pi["id"]))
            print("карточка project-integration: номер шага снят")
        else:
            print("карточка project-integration: устаревшего номера шага нет (править нечего)")
    if write:
        print("исходник docs/rules/rules.md:", sync_md())
    else:
        print("исходник docs/rules/rules.md: не тронут (нет --write)")
    print("готово" if write else "черновик: запуск без --write ничего не записал")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

