#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V50: круг `CommonAttributes` по эталонным выгрузкам (файлы, БД не трогает).

Зачем. Позиция 2.5 нормативного списка — общие реквизиты — это вид, у которого нет своей
раскладки содержимого (в четырёх выгрузках каталога подкаталогов нет вообще: только
`<Имя>.xml`), но свойства вида несут две вещи разного рода:

1. тип значения — тот же блок `<Type>`, что у параметров сеанса (узел V48), с квалификаторами
   и возможной кратностью (составной тип);
2. `<Content>` — перечень объектов, к которым применяется реквизит (`xr:Metadata` + `xr:Use` +
   `xr:ConditionalSeparation`). Именно этот перечень и есть содержательный вопрос вида
   («какие объекты получают общий реквизит», «почему у объекта нет этого реквизита»), и он же
   делает файлы большими: 121 КБ у `ОбластьДанныхОсновныеДанные` в BGU2 против 3 КБ у
   реквизита, применённого к двум объектам.

Прежде чем выбирать модель хранения (Q1), нужны числа:

1. раскладка — есть ли подкаталоги, формы, макеты, модули (по замеру модели вида нет, но
   проверка обязана быть своей);
2. словарь свойств вида — закрыт ли он по корпусу и сколько свойств в файле (XSD вида нет,
   замер модели: 19 каталогов без XSD, `CommonAttributes` среди них);
3. форма `<Type>` — одиночные и составные типы, квалификаторы, кратность (решение оператора Q4
   узла V48: одна запись — одиночный тип, несколько записей — составной);
4. масштаб и словарь `<Content>` — число `xr:Item`, словарь видов целей, состояния `xr:Use` и
   `xr:ConditionalSeparation`;
5. состояния перечислимых свойств (AutoUse, DataSeparation, Indexing, FullTextSearch, ...) —
   закрытый словарь или свободный текст;
6. вес условий разделения (`DataSeparationValue`, `DataSeparationUse`, `ConditionalSeparation`) —
   от этого зависит, нужна ли под них отдельная таблица;
7. предопределённость — совпадают ли имена и uuid между BGU2 и BP3 (у предопределённых
   реквизитов платформы uuid свой, и это надо измерить, а не выдумывать признак).

Ничего в БД зонд не пишет: он только читает файлы и печатает измеренное.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_scratch" / "v50_p0_probe.txt"

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "CommonAttributes"

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))

RE_ROOT = re.compile(r'<CommonAttribute\s+uuid="([0-9a-fA-F-]{36})"')
RE_PROPS = re.compile(r"<Properties>(.*?)</Properties>", re.S)
RE_TOKEN = re.compile(
    r"<(/?)([A-Za-z][A-Za-z0-9]*(?::[A-Za-z][A-Za-z0-9]*)?)(\s[^>]*?)?(/?)>"
)
RE_NAME = re.compile(r"<Name>(.*?)</Name>", re.S)

# --- блок <Type> -----------------------------------------------------------
RE_TYPE_BLOCK = re.compile(r"<Type>(.*?)</Type>", re.S)
RE_V8_TYPE = re.compile(r"<v8:Type>(.*?)</v8:Type>", re.S)
RE_QUALIFIER = re.compile(r"<v8:([A-Za-z]*[Qq]ualifier[s]?)\b")
RE_TYPE_COMPOSITE = re.compile(r"<v8:CompositeDataType|<v8:TypeByValueType")

# --- содержимое применения <Content> ---------------------------------------
RE_CONTENT = re.compile(r"<Content>(.*?)</Content>", re.S)
RE_XR_ITEM = re.compile(r"<xr:Item>(.*?)</xr:Item>", re.S)
RE_XR_METADATA = re.compile(r"<xr:Metadata>(.*?)</xr:Metadata>", re.S)
RE_XR_USE = re.compile(r"<xr:Use>(.*?)</xr:Use>", re.S)
RE_XR_COND_SEP = re.compile(r"<xr:ConditionalSeparation(/>|>(.*?)</xr:ConditionalSeparation>)", re.S)

# --- блоки условий разделения ---------------------------------------------
RE_BLOCK = lambda tag: re.compile(rf"<{tag}>(.*?)</{tag}>", re.S)  # noqa: E731
RE_XR_ITEM_ANY = re.compile(r"<xr:Item>(.*?)</xr:Item>", re.S)
RE_XR_VALUE = re.compile(r"<xr:Value>(.*?)</xr:Value>", re.S)

# --- перечислимые свойства: значения обязан называть замер, а не память ----
ENUM_PROPS = (
    "FillChecking", "ChoiceFoldersAndItems", "QuickChoice", "CreateOnInput",
    "ChoiceHistoryOnInput", "AutoUse", "DataSeparation", "SeparatedDataUse",
    "DataSeparationUse", "UsersSeparation", "AuthenticationSeparation",
    "ConfigurationExtensionsSeparation", "Indexing", "FullTextSearch", "DataHistory",
)
BOOL_PROPS = (
    "PasswordMode", "MarkNegatives", "MultiLine", "ExtendedEdit", "FillFromFillingValue",
)
# Блоки условий разделения: их внутренняя форма в прошлом замере не читалась (считались
# только xr:Item, которых там нет) — форма обязана быть измерена, иначе нельзя решить,
# нужна ли под них своя таблица.
SEP_TAGS = ("DataSeparationValue", "DataSeparationUse", "ConditionalSeparation")


def direct_children(props_block: str) -> list[tuple[str, str]]:
    """Прямые дети <Properties>: (имя тега, текст значения) без вложенных блоков.

    Глубина считается так: самозакрывающийся тег на глубине 0 — пустое значение; парный тег
    на глубине 0 закрывается токеном `</tag>` при глубине 1, и значением служит текст между
    ними. Ошибка прошлого замера (парные теги не попадали в словарь) закрыта именно этим:
    признак — `свойств на файл` обязан равняться числу тегов верхнего уровня файла.
    """
    out: list[tuple[str, str]] = []
    depth = 0
    name = ""
    start = 0
    for m in RE_TOKEN.finditer(props_block):
        closing, tag, _attrs, self_closed = m.group(1), m.group(2), m.group(3), m.group(4)
        if self_closed:
            if depth == 0:
                out.append((tag, ""))
            continue
        if closing:
            if depth == 1 and name:
                out.append((name, props_block[start:m.start()]))
                name = ""
            depth -= 1
            continue
        if depth == 0:
            name = tag
            start = m.end()
        depth += 1
    return out


def inner_tags(block_text: str) -> collections.Counter:
    """Теги верхнего уровня внутри блока — форма содержимого, а не допущение."""
    counter: collections.Counter = collections.Counter()
    depth = 0
    for m in RE_TOKEN.finditer(block_text):
        closing, tag, _attrs, self_closed = m.group(1), m.group(2), m.group(3), m.group(4)
        if self_closed:
            if depth == 0:
                counter[tag] += 1
            continue
        if closing:
            depth -= 1
            continue
        if depth == 0:
            counter[tag] += 1
        depth += 1
    return counter


def single_value(children: list[tuple[str, str]], tag: str) -> str | None:
    for name, text in children:
        if name == tag:
            return text.strip()
    return None


def main() -> int:
    lines: list[str] = []

    def emit(text: str = "") -> None:
        lines.append(text)

    corpus_props: collections.Counter = collections.Counter()
    corpus_enum: dict[str, collections.Counter] = {p: collections.Counter() for p in ENUM_PROPS}
    corpus_type_values: collections.Counter = collections.Counter()
    corpus_qualifiers: collections.Counter = collections.Counter()
    corpus_use: collections.Counter = collections.Counter()
    corpus_cond_sep: collections.Counter = collections.Counter()
    corpus_target_kinds: collections.Counter = collections.Counter()
    names_by_dump: dict[str, set[str]] = {}
    uuid_by_name: dict[str, dict[str, str]] = {}

    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        emit(f"=== {dump}")
        if not directory.is_dir():
            emit("  каталога CommonAttributes нет — позиции вида в этой конфигурации нет")
            emit()
            names_by_dump[dump] = set()
            continue

        files = sorted(directory.glob("*.xml"))
        subdirs = [p for p in directory.iterdir() if p.is_dir()]
        bsl = sorted(directory.rglob("*.bsl"))
        forms = [p for p in directory.rglob("*") if "Forms" in p.parts]
        templates = [p for p in directory.rglob("*") if "Templates" in p.parts]
        emit(f"  файлов метаданных: {len(files)}, байт: {sum(p.stat().st_size for p in files)}")
        emit(f"  подкаталогов: {len(subdirs)}, .bsl: {len(bsl)}, Forms: {len(forms)}, "
             f"Templates: {len(templates)}")

        props_counter: collections.Counter = collections.Counter()
        props_per_file: list[int] = []
        type_shapes: collections.Counter = collections.Counter()
        type_values: collections.Counter = collections.Counter()
        qualifiers: collections.Counter = collections.Counter()
        composite_files = 0
        content_items = 0
        content_files = 0
        per_file_content: list[int] = []
        use_states: collections.Counter = collections.Counter()
        cond_sep: collections.Counter = collections.Counter()
        target_kinds: collections.Counter = collections.Counter()
        sep_blocks: collections.Counter = collections.Counter()
        sep_shapes: dict[str, collections.Counter] = {t: collections.Counter() for t in SEP_TAGS}
        sep_samples: dict[str, list[str]] = {t: [] for t in SEP_TAGS}
        sep_values = 0
        enum_values: dict[str, collections.Counter] = {p: collections.Counter() for p in ENUM_PROPS}
        bool_values: dict[str, collections.Counter] = {p: collections.Counter() for p in BOOL_PROPS}
        present: collections.Counter = collections.Counter()
        nil_forms: collections.Counter = collections.Counter()
        languages: collections.Counter = collections.Counter()
        names: dict[str, str] = {}
        biggest: list[tuple[int, str]] = []

        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            uuid = RE_ROOT.search(text)
            props = RE_PROPS.search(text)
            if not props:
                emit(f"  ⚠️ {path.name}: блока <Properties> нет")
                continue
            children = direct_children(props.group(1))
            name_in_file = single_value(children, "Name") or path.stem
            names[name_in_file] = uuid.group(1) if uuid else ""
            biggest.append((path.stat().st_size, path.name))
            props_per_file.append(len(children))
            for tag, _text in children:
                props_counter[tag] += 1

            for tag, value in children:
                if tag in enum_values:
                    enum_values[tag][value or "<пусто>"] += 1
                elif tag in bool_values:
                    bool_values[tag][value or "<пусто>"] += 1
                elif tag in ("MinValue", "MaxValue", "FillValue"):
                    nil_forms[f"{tag}:{'nil' if 'xsi:nil' in value or not value.strip() else 'значение'}"] += 1
                elif value.strip():
                    present[tag] += 1
                if tag in ("Synonym", "ToolTip"):
                    languages[f"{tag}:{len(re.findall('<v8:lang>', value))}"] += 1

            type_block = RE_TYPE_BLOCK.search(text)
            if not type_block:
                type_shapes["<Type> отсутствует"] += 1
            else:
                block = type_block.group(1)
                values = [v.strip() for v in RE_V8_TYPE.findall(block)]
                for v in values:
                    type_values[v] += 1
                quals = list(RE_QUALIFIER.findall(block))
                for q in quals:
                    qualifiers[q] += 1
                if RE_TYPE_COMPOSITE.search(block):
                    type_shapes["есть признак составного типа (вложенные блоки)"] += 1
                if len(values) > 1:
                    composite_files += 1
                    type_shapes[f"несколько <v8:Type> ({len(values)})"] += 1
                elif not values:
                    type_shapes["<Type> без <v8:Type> (форма вне словаря)"] += 1
                else:
                    shape = f"один <v8:Type> + {sorted(set(quals))[0]}" if quals else "один <v8:Type> без квалификаторов"
                    type_shapes[shape] += 1

            content_block = RE_CONTENT.search(text)
            if content_block:
                items = RE_XR_ITEM.findall(content_block.group(1))
                content_items += len(items)
                content_files += 1
                per_file_content.append(len(items))
                for item in items:
                    meta = RE_XR_METADATA.search(item)
                    if meta:
                        target_kinds[meta.group(1).strip().split(".", 1)[0]] += 1
                    use = RE_XR_USE.search(item)
                    use_states[use.group(1).strip() if use else "<xr:Use нет>"] += 1
                    cond = RE_XR_COND_SEP.search(item)
                    if cond is None:
                        cond_sep["<xr:ConditionalSeparation> нет"] += 1
                    elif cond.group(1) == "/>":
                        cond_sep["пустой <xr:ConditionalSeparation/>"] += 1
                    else:
                        cond_sep[f"значение: {(cond.group(2) or '').strip() or '<пустое>'}"] += 1
            else:
                per_file_content.append(0)

            for tag in SEP_TAGS:
                block = RE_BLOCK(tag).search(text)
                if block:
                    inner = block.group(1)
                    sep_blocks[f"{tag}:непустой"] += 1
                    shapes = inner_tags(inner)
                    for name_tag, count in shapes.items():
                        sep_shapes[tag][f"{name_tag}×{count}"] += 1
                    sep_values += sum(shapes.values())
                    if len(sep_samples[tag]) < 2:
                        sep_samples[tag].append(
                            f"{path.name}: " + re.sub(r"\s+", " ", inner).strip()[:300]
                        )
                elif f"<{tag}/>" in text:
                    sep_blocks[f"{tag}:пустой"] += 1
                else:
                    sep_blocks[f"{tag}:тега нет"] += 1

        emit(f"  объектов вида: {len(names)}; свойств на файл: мин {min(props_per_file)}, "
             f"макс {max(props_per_file)}")
        emit(f"  словарь свойств (тег → число файлов): "
             f"{dict(sorted(props_counter.items(), key=lambda kv: (-kv[1], kv[0])))}")
        emit(f"  форма <Type>: {dict(sorted(type_shapes.items(), key=lambda kv: -kv[1]))}; "
             f"файлов с несколькими <v8:Type>: {composite_files}")
        emit(f"  значения <v8:Type>: {dict(sorted(type_values.items(), key=lambda kv: -kv[1]))}")
        emit(f"  квалификаторы: {dict(qualifiers)}")
        emit(f"  <Content>: файлов с перечнем {content_files}, строк xr:Item {content_items}; "
             f"на файл — мин {min(per_file_content)}, макс {max(per_file_content)}")
        emit(f"  состояния xr:Use: {dict(use_states)}")
        emit(f"  состояния xr:ConditionalSeparation: {dict(cond_sep)}")
        emit(f"  виды целей применения: {dict(sorted(target_kinds.items(), key=lambda kv: -kv[1]))}")
        emit(f"  блоки разделения: {dict(sorted(sep_blocks.items()))}; "
             f"тегов верхнего уровня в блоках разделения: {sep_values}")
        for tag in SEP_TAGS:
            if sep_shapes[tag]:
                emit(f"  ⚠️ форма блока {tag}: {dict(sep_shapes[tag])}")
                for sample in sep_samples[tag]:
                    emit(f"     образец {tag}: {sample}")
        for tag in ENUM_PROPS:
            if enum_values[tag]:
                emit(f"  {tag}: {dict(sorted(enum_values[tag].items(), key=lambda kv: -kv[1]))}")
        for tag in BOOL_PROPS:
            if bool_values[tag]:
                emit(f"  {tag}: {dict(bool_values[tag])}")
        emit(f"  непустых значений свойств: {dict(sorted(present.items(), key=lambda kv: -kv[1]))}")
        emit(f"  форма Min/Max/Fill: {dict(sorted(nil_forms.items()))}")
        emit(f"  языковые блоки: {dict(sorted(languages.items()))}")
        emit(f"  имена: {sorted(names)}")
        emit(f"  самые большие файлы: {sorted(biggest, reverse=True)[:5]}")

        corpus_props.update(props_counter)
        corpus_type_values.update(type_values)
        corpus_qualifiers.update(qualifiers)
        corpus_use.update(use_states)
        corpus_cond_sep.update(cond_sep)
        corpus_target_kinds.update(target_kinds)
        for tag in ENUM_PROPS:
            corpus_enum[tag].update(enum_values[tag])
        names_by_dump[dump] = set(names)
        for name, obj_uuid in names.items():
            uuid_by_name.setdefault(name, {})[dump] = obj_uuid
        emit()

    emit("=== объединение четырёх выгрузок")
    emit(f"  словарь свойств (всего встречаний): "
         f"{dict(sorted(corpus_props.items(), key=lambda kv: -kv[1]))}")
    emit(f"  значений <v8:Type> различных: {len(corpus_type_values)}: "
         f"{dict(sorted(corpus_type_values.items(), key=lambda kv: -kv[1]))}")
    emit(f"  квалификаторов различных: {len(corpus_qualifiers)}: {dict(corpus_qualifiers)}")
    emit(f"  словарь xr:Use: {dict(corpus_use)}")
    emit(f"  словарь xr:ConditionalSeparation: {dict(corpus_cond_sep)}")
    emit(f"  видов целей применения различных: {len(corpus_target_kinds)}")
    for tag in ENUM_PROPS:
        if corpus_enum[tag]:
            emit(f"  {tag}: различных {len(corpus_enum[tag])} — "
                 f"{dict(sorted(corpus_enum[tag].items(), key=lambda kv: -kv[1]))}")

    emit()
    emit("=== имена и uuid между выгрузками (признак предопределённости меряется, а не выдумывается)")
    all_names = set().union(*names_by_dump.values()) if names_by_dump else set()
    emit(f"  различных имён по корпусу: {len(all_names)}")
    for name in sorted(all_names):
        per = uuid_by_name.get(name, {})
        distinct_uuids = len({v for v in per.values() if v})
        emit(f"  {name}: выгрузок {len(per)}, uuid различных {distinct_uuids}: "
             f"{ {d: (v or '—')[:8] for d, v in sorted(per.items())} }")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"отчёт: {OUT}  строк: {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())



