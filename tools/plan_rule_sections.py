"""План и заготовка исходника слоя правил (узел RULE-LAYER, 24.10.2026).

Зачем. Правила трёх MCP-серверов занимают ~300 КБ в `.clinerules/`, то есть попадают в контекст
каждого разговора, хотя нужны по одной карточке за раз. Переносить их в слой — не значит
переписать своими словами: формулировки решений (почему снят внешний ключ, что означает NULL,
чем проверяется узел) и есть ценность. Поэтому инструмент раскладывает существующие файлы по
адресам ДОСЛОВНО, а человек потом дописывает только то, чего в файлах не было: рабочий
порядок действий и индекс.

Что делает:

    python tools/plan_rule_sections.py --marker core-rules \
        --from .clinerules/1c-configurations-core_Rule.md --from LOAD_RULES_Config.md
        # план: карточка -> адрес, исходник, заголовок, размер; отчёт о дублях между файлами

    ... --emit docs/rules/core-rules.md
        # та же раскладка + индекс: адрес | исходник | заголовок раздела

Границы раскладки:

  * режет по `## ` (заголовок раздела верхнего уровня). Текст до первого `## ` — шапка файла:
    в ней у `.clinerules/1c-knowledge-base_Rule.md` стоит вся история дополнений, и она не
    теряется: блоки `> **Дополнение …**` / `> **Обновлено …**` становятся карточками
    `<marker>:journal:NN`. Отбросить их — значит молча выкинуть журнал;
  * раздел длиннее `MAX_ANSWER_CHARS` делится сначала по `### `, затем по абзацам — карточки
    `<marker>:ref:NN`, `<marker>:ref:NN:2` …. Жёсткий срез символами не применяется:
    разрезанная пополам таблица или SQL читаются хуже, чем две части;
  * дубли ищутся по нормализованным абзацам >= 200 символов: один и тот же текст в двух файлах
    (правила загрузки и файл правил сервера) после переноса дал бы две карточки одного знания,
    и поиск отдавал бы обе;
  * `--emit` не затыкает руками написанное: карточки существующего целевого файла, которых нет
    среди порождённых, сохраняются как есть, а рукописная часть индекса между маркерами
    `hand:start` / `hand:end` переносится в новый индекс.

Индекс генерируется по порождённым карточкам: правило «каждая карточка названа в индексе»
(`src/rules_layer.py::parse_document`) иначе падало бы на каждом переносе, а рукописный индекс
пришлось бы вести руками против списка, который и так знает только генератор.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import rules_layer as RL  # noqa: E402

H2_RE = re.compile(r"^##[ \t]+(?!#)(.+?)[ \t]*$", re.MULTILINE)
H3_RE = re.compile(r"^###[ \t]+(?!#)")
ADDITION_RE = re.compile(r"^>[ \t]*\*\*(?:Дополнение|Обновлено)[^\n]*", re.MULTILINE)
HAND_START = "<!-- hand:start -->"
HAND_END = "<!-- hand:end -->"
PARAGRAPH_CHARS = 6000  # запас до MAX_ANSWER_CHARS: к тексту части добавляется шапка карточки
MIN_PART_CHARS = 400    # часть короче — это не правило, а обрывок: он склеивается с соседом
DUPE_MIN_CHARS = 200    # абзац короче не показателен: совпадения вида «|---|---|» шумят
FENCE_LINE_RE = re.compile(r"(?m)^[ \t]*(?:```|~~~)")



def read_text(path):
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.read_text(encoding="utf-8")


def _fence_blocks(text):
    """Код-блоки как атомарные куски: [(start, end)] по строкам ``` / ~~~.

    Разрез внутри код-блока даёт две карточки с незакрытым и с не открытым блоком: markdown
    после этого ломается, а разбор файла слоя перестал бы видеть заголовки после незакрытого
    блока (в src/rules_layer.py незакрытый блок — отдельная ошибка именно поэтому)."""
    return RL.fence_spans(text)


def _chunks(text, min_part=PARAGRAPH_CHARS):
    """Текст -> куски не длиннее min_part по границам `###` и пустых строк, НЕ внутри
    код-блоков. Жёсткий срез символами не применяется: разрезанная пополам таблица или SQL
    читаются хуже, чем две части.

    Код-блок длиннее лимита — исключение: его приходится резать, но тогда каждая часть
    получает собственные границы блока и явную пометку, что это часть примера. Молча отдать
    половину SQL — значит выдать правило, которое читается как целый пример."""
    if len(text) <= RL.MAX_ANSWER_CHARS:
        return [text.strip()] if text.strip() else []
    spans = _fence_blocks(text)
    marks = {0,
             *[m.start() for m in H3_RE.finditer(text)],
             *[m.start() + 1 for m in re.finditer(r"\n[ \t]*\n", text)],
             *[start for start, _end in spans]}
    # границы внутри код-блоков не используются
    marks = sorted(p for p in marks
                   if not any(start < p < end for start, end in spans))
    blocks = []
    for i, start in enumerate(marks):
        end = marks[i + 1] if i + 1 < len(marks) else len(text)
        if end > start:
            blocks.append(text[start:end])
    parts, cur = [], ""
    for block in blocks:
        while len(block) > min_part:  # блок длиннее лимита — только код-блок
            if cur:
                parts.append(cur)
                cur = ""
            cut = block.rfind("\n", 0, min_part)
            cut = cut if cut > min_part // 4 else min_part
            parts.append(block[:cut])
            block = block[cut:]
        if cur and len(cur) + len(block) > min_part:
            parts.append(cur)
            cur = block.lstrip("\n")
        else:
            cur += block
    if cur.strip():
        parts.append(cur)
    return repair_fences(merge_tiny_parts([p.strip() for p in parts if p.strip()]))


def merge_tiny_parts(parts, min_chars=MIN_PART_CHARS, limit=RL.MAX_ANSWER_CHARS):
    """Обрывки короче `min_chars` склеиваются с предыдущим куском.

    Нужно затем, что деление по границам даёт и кусок в 32 символа (заголовок раздела плюс
    первая строка): как отдельная карточка он ничего не отвечает, но занимает адрес и попадает
    в индекс. Склейка возможна, только если объединённый кусок влезает в лимт answer — иначе
    правило пришлось бы резать снова.
    """
    merged = []
    for part in parts:
        if merged and (len(part) < min_chars
                       or len(merged[-1]) < min_chars) and len(merged[-1]) + len(part) + 2 <= limit:
            merged[-1] = f"{merged[-1]}\n\n{part}"
            continue
        merged.append(part)
    return merged


def repair_fences(parts):
    """Каждая часть остаётся корректным markdown: код-блок закрыт, продолжение открыто.

    Разрез внутри примера случается, когда пример длиннее лимита. Прежний порядок закрывал и
    тут же открывал блок в конце текущей части — и следующая часть начиналась с закрывающей
    границы, то есть её собственный заголовок `## <адрес>` оказывался внутри блокa: парсер
    переставал видеть следующую карточку, а её текст приклеивался к предыдущей (замер
    24.10.2026: core-rules:ref:06:2 — 6110 символов в файле против 8424 у разбора).
    Теперь граница ставится одна: закрывающая в конец оборванной части, открывающая — в начало
    следующей. Это чинит и разрезы по абзацам, если граница всё же попала внутрь блока.
    """
    fixed, carry_open = [], False
    for part in parts:
        if carry_open:
            part = ("```\n<!-- продолжение примера из предыдущей части того же правила -->\n"
                    + part)
            carry_open = False
        if len(FENCE_LINE_RE.findall(part)) % 2:
            part = (part.rstrip() + "\n```\n"
                    "<!-- граница части примера: продолжение в следующей карточке этого правила -->")
            carry_open = True
        fixed.append(part)
    return fixed



def build_cards(marker, inputs):
    """Список входных файлов -> карточки слоя: адрес, исходник, заголовок, тело.

    Заголовок раздела сохраняется первой строкой тела: `get_snippet_tool` отдаёт answer без
    вопроса, и карточка без заголовка не отвечает, к какому разделу она относится. В адрес
    заголовок не попадает намеренно: он кириллицей и с эмодзи, адрес обязан быть ASCII и
    коротким, иначе его нельзя повторить запросом (порог `MAX_TITLE_DISPLAY_CHARS`).
    """
    cards, errors = [], []
    # счётчики — на весь слой, а не на входной файл: у core-слоя два исходника (файл правил
    # сервера и LOAD_RULES_Config.md), и нумерация внутри каждого дала бы два ref:01 —
    # две карточки разных правил под одним адресом
    ref_count = journal_count = 0
    for src in inputs:
        text = read_text(src)
        additions, sections = split_sections(text)
        for title, block in additions:
            journal_count += 1
            base = f"{marker}:journal:{journal_count:02d}"
            parts = _chunks(block)
            if not parts:
                errors.append(f"{base}: пустой блок дополнения из {src}")
                continue
            for i, part in enumerate(parts, start=1):
                address = base if i == 1 else f"{base}:{i}"
                cards.append({"address": address, "heading": title, "source": str(src),
                              "body": part, "kind": "journal", "parts": len(parts)})
        for heading, body in sections:
            ref_count += 1
            base = f"{marker}:ref:{ref_count:02d}"
            # заголовок раздела — строкой `###`, а не `##`: разбор режет файл по `## `, и
            # односложный заголовок вида `## Предупреждения` стал бы фантомной карточкой
            # с невалидным адресом (замер 24.10.2026 на core-слое: 10 дублей и фантом
            # 'Предупреждения' при переносе двух исходников)
            full = f"### {heading}\n{body.strip()}"
            parts = _chunks(full)
            if not parts:
                errors.append(f"{base}: пустой раздел {heading!r} из {src} — переносить нечего")
                continue
            for i, part in enumerate(parts, start=1):
                address = base if i == 1 else f"{base}:{i}"
                if len(parts) > 1 and i > 1:
                    part = (f"### {heading} — часть {i} из {len(parts)}\n"
                            f"(раздел длинный, читать части по порядку)\n\n{part}")
                cards.append({"address": address, "heading": heading, "source": str(src),
                              "body": part, "kind": "ref", "parts": len(parts)})
    return cards, errors


def norm_paragraph(text):
    """Абзац -> нормализованная форма для сравнения: регистр, пустоту и разметку снимаем,
    потому что дубль в двух файлах различается ровно оформлением."""
    t = re.sub(r"[`*_>|#]+", " ", text.lower())
    return re.sub(r"\s+", " ", t).strip()


def find_duplicates(cards, min_chars=DUPE_MIN_CHARS):
    """Одинаковые абзацы в разных исходниках. Не провал, а предупреждение: решение о том,
    какой из двух текстов оставить, принимает человек — молча склеить их значит выбрать
    один из двух вариантов формулировки без ответа на вопрос, какой верный.

    Порог (`min_chars`) заварен в аргумент, а не в константу: на 200 символах находятся
    дословные копирования, на 100–120 — переформулировки одного и того же правила в двух
    файлах (правила загрузки и файл правил сервера), и их тоже нужно увидеть, чтобы решить."""
    by_hash = {}
    for card in cards:
        source = card["source"]
        for para in re.split(r"\n[ \t]*\n", card["body"]):
            key = norm_paragraph(para)
            if len(key) < min_chars:
                continue
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
            by_hash.setdefault(digest, []).append((source, card["address"], key[:90]))
    shared = {d: entries for d, entries in by_hash.items()
              if len({entry[0] for entry in entries}) > 1}
    return shared


def hand_region(path, marker):
    """Сохранённая рукописная часть индекса из существующего файла. Без неё перегенерация
    индекса стирала бы написанное человеком, и править индекс стало бы невозможно."""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    start, end = text.find(HAND_START), text.find(HAND_END)
    if start < 0 or end < 0 or end < start:
        return ""
    return text[start + len(HAND_START):end].strip()


def hand_cards(path, generated_addresses):
    """Карточки существующего файла, которых нет среди порождённых, — то есть написанные
    человеком. Терять их при перегенерации нельзя: рабочий порядок правил живёт именно так.

    Артефакты разбора сюда не попадают: общий парсер (src/rules_layer.py) отбрасывает строки
    с невалидным адресом, и фантом прошлого прогона не превращается в «ручную» карточку,
    которую следующий прогон вернёт в файл (замер 24.10.2026: так один раз уже случилось)."""
    if not path.exists():
        return []
    cards, _errors = RL.parse_document(path.read_text(encoding="utf-8"),
                                      RL.marker_for_path(path) or "")
    return [c for c in cards if c["address"] not in generated_addresses
            and c["address"] != RL.index_address(RL.marker_for_path(path) or "")]


def split_sections(text):
    """Файл -> (дополнения шапки, разделы). Разделы — по заголовкам `## `; текст до первого
    такого заголовка — шапка файла, и она не отбрасывается: у
    `.clinerules/1c-knowledge-base_Rule.md` в ней живёт вся история дополнений (десятки
    килобайт), отбросить её — значит молча выкинуть журнал."""
    matches = list(H2_RE.finditer(text or ""))
    preamble = text[: matches[0].start()] if matches else text
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1).strip(), text[m.end():end]))
    additions = []
    marks = list(ADDITION_RE.finditer(preamble))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(preamble)
        block = preamble[m.start():end].strip()
        title = block.splitlines()[0].lstrip("> ").strip()
        additions.append((title, block))
    return additions, sections


# ------------------------------------------------------------------ вывод

def emit_document(marker, generated, preserved, hand):
    """Текст исходника слоя. Индекс генерируется по карточкам: правило «каждая карточка
    названа в индексе» иначе роняет каждый перенос, а вести список адресов руками бессмысленно
    — его знает только генератор.

    Заголовок исходного раздела внутри карточки даётся строкой `###`, а не `##`: разбор режет
    файл по `## `, и перенесённый заголовок создал бы фантомную карточку с кириллическим
    адресом (адрес обязан быть ASCII и короче порога)."""
    category = RL.category_of(marker) or ""
    index = RL.index_address(marker)
    lines = [
        f"# Правила MCP `{category}` — исходник слоя `{marker}`",
        "",
        "<!-- Слой знаний local_doc (узел RULE-LAYER). "
        f"Категория: `{category}`. Метка адреса: `{marker}:`.",
        "     Файл НЕ загружается в контекст AI-ассистента: правила читаются из БД.",
        f"     План раскладки:  python tools/plan_rule_sections.py --marker {marker} --from <файл>",
        f"     Пересборка слоя: python tools/migrate_rules_to_layer.py "
        f"--file docs/rules/{marker}.md --apply",
        f"     Проверка:        python tools/check_rules_layer.py --layer {marker}",
        "     Карточки ниже порождены планом и перенесены из исходных файлов правил дословно;",
        "     текст изменений не меняет. Рукописная часть индекса между маркерами hand:start /",
        "     hand:end сохраняется при перегенерации; карточки, которых нет среди порождённых,",
        "     считаются написанными человеком и сохраняются как есть. -->",
        "",
        f"## {index}",
        "",
        f"Карточка-оглавление слоя `{marker}`. Первый шаг работы с этим MCP — прочитать её,",
        "дальше брать нужный адрес из таблиц ниже.",
        "",
        HAND_START,
        hand or "> Рабочий порядок (что делать по шагам) ещё не дописан: индекс порождён планом.",
        HAND_END,
        "",
        "### Карточки слоя: адрес | исходник | раздел",
        "",
        "| Адрес | Исходник | Раздел исходника |",
        "|---|---|---|",
    ]
    for card in generated:
        note = card["heading"]
        if card["parts"] > 1:
            note += f" — частей {card['parts']}"
        lines.append(f"| `{card['address']}` | `{card['source']}` | {note} |")
    if preserved:
        lines += ["", "### Карточки, написанные вручную (планом не порождаются)", "",
                  "| Адрес | Примечание |", "|---|---|"]
        for card in preserved:
            lines.append(f"| `{card['address']}` | сохранена как есть |")
    for card in generated:
        lines += ["", f"## {card['address']}", "", card["body"], ""]
    for card in preserved:
        lines += ["", f"## {card['address']}", "", card["answer"], ""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="План переноса файлов правил в слой карточек и заготовка исходника слоя")
    ap.add_argument("--marker", required=True,
                    help=f"метка слоя: {', '.join(RL.markers())}")
    ap.add_argument("--from", dest="inputs", action="append", default=[],
                    help="исходный файл правил (повторяется; можно несколько)")
    ap.add_argument("--emit", default="",
                    help="записать исходник слоя (обычно docs/rules/<метка>.md)")
    ap.add_argument("--plan-json", default="",
                    help="записать план JSON (адрес, исходник, заголовок, размер)")
    ap.add_argument("--dupe-min", type=int, default=DUPE_MIN_CHARS,
                    help=f"длина абзаца для поиска повторов (по умолчанию {DUPE_MIN_CHARS})")
    args = ap.parse_args(argv)

    marker = args.marker
    if marker not in RL.LAYERS:
        print(f"метка {marker!r} не из списка слоёв: {', '.join(RL.markers())}")
        return 1
    if not args.inputs:
        print("нужен хотя бы один --from <файл правил>")
        return 1

    generated, errors = build_cards(marker, args.inputs)
    print(f"метка: {marker}; категория: {RL.category_of(marker)}; "
          f"исходников: {len(args.inputs)}")
    for card in generated:
        print(f"  {card['address']:<34} {len(card['body']):>6}  "
              f"{card['source']} :: {card['heading'][:70]}")
    by_kind = {}
    for card in generated:
        by_kind[card["kind"]] = by_kind.get(card["kind"], 0) + 1
    print(f"карточек: {len(generated)} " +
          " ".join(f"({kind} {count})" for kind, count in sorted(by_kind.items())))
    longest = max((len(c["address"]) for c in generated), default=0)
    print(f"порог адреса: {RL.MAX_TITLE_DISPLAY_CHARS} (максимум {longest})")

    dupes = find_duplicates(generated, args.dupe_min)
    print(f"одинаковых абзацев (>= {args.dupe_min} симв.) в двух и более исходниках: "
          f"{len(dupes)}")
    for digest, entries in list(dupes.items())[:10]:
        print(f"  {digest}:")
        for source, address, snippet in entries:
            print(f"    {address} ({source}): {snippet}")

    if args.plan_json:
        payload = [{"address": c["address"], "source": c["source"], "heading": c["heading"],
                    "chars": len(c["body"]), "kind": c["kind"], "parts": c["parts"]}
                   for c in generated]
        plan_path = Path(args.plan_json)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"план: {plan_path}")

    if errors:
        print("ОШИБКИ РАСКЛАДКИ:")
        for e in errors:
            print(f"  - {e}")
        return 1

    if args.emit:
        out = Path(args.emit)
        if not out.is_absolute():
            out = PROJECT_ROOT / out
        preserved = hand_cards(out, {c["address"] for c in generated})
        text = emit_document(marker, generated, preserved, hand_region(out, marker))
        out.write_text(text, encoding="utf-8")
        print(f"исходник слоя: {out} ({len(text)} симв.), "
              f"порождено {len(generated)}, сохранено вручную {len(preserved)}")
        # разбор созданного файла — тем же парсером, что у мигратора: иначе инструмент
        # напечатал бы «записано», а мигратор на этом же файле споткнулся бы о фантомный адрес
        _cards, parse_errors = RL.parse_document(text, marker)
        if parse_errors:
            print("ОШИБКИ РАЗБОРА СОЗДАННОГО ФАЙЛА:")
            for e in parse_errors[:10]:
                print(f"  - {e}")
            return 1
        print("разбор созданного файла: ошибок нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


