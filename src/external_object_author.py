#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Узел V29, этап 1: сборка XML внешнего объекта С НУЛЯ (чистая сборка по спецификации).

Отличие от остального кода подсистемы: здесь нет ни SQL, ни `ibcmd`, ни чтения чужой
выгрузки. Модуль только собирает текст XML по спецификации — то, что нельзя подсмотреть
в базе, потому что объекта ещё нет (правило 10 .clinerules/1C_Rule.md допускает
исключение именно для создания: строк БД ещё нет, а наружу объект отдаётся файлом,
собранным платформой из этого же XML — round-trip и закрывает исключение).

Норматив формата — не xsd-schemas/ (они противоречат и живой выгрузке, и ответам
платформы), а профиль свойств `ExternalDataProcessor` (категория `xml-format` в local_doc,
якорь `property-profile-externaldataprocessor`) и пробы импорта
`tools/probe_external_processing_properties.py` (отчёт `_ibcmd_work/v29_probe/report.json`).
Каждая строка сборки опирается на пробу, а не на догадку:

  * корень `MetaDataObject` с `xmlns="http://v8.1c.ru/8.3/MDClasses"` и `version="2.20"`
    — provenance declared (эталонная выгрузка);
  * ровно один потомок корня `<ExternalDataProcessor uuid=...>`; порядок дочерних узлов
    значим: InternalInfo -> Properties -> ChildObjects. Доказательство —
    rejected(v5_no_properties), rejected(v8_no_childobjects): платформа отвечает
    «читаемое свойство не соответствует ожидаемому. Текущее …, ожидаемое …»;
  * `@uuid` обязателен — rejected(v9_no_uuid);
  * `InternalInfo` обязателен как элемент — rejected(v6_no_internalinfo);
  * `<xr:ContainedObject>` НЕ пишется вовсе — accepted(v15_no_containedobject): файл принят
    без него, блок доставляет платформа. Поэтому в модуле нет ни одной ветки, которая
    умела бы его напечатать: написать нельзя то, чего нет в коде;
  * если ClassId всё же пишут — только константа класса вида (CLASS_IDS): пустой и чужой
    значения отклонены импортом (rejected(v14_empty_classid), rejected(v10_foreign_classid));
  * `Properties` и `ChildObjects` обязательны как элементы и принимаются пустыми —
    accepted(v11_empty_properties) вместе с rejected(v5/v8);
  * `Name` заполняется валидным идентификатором: пустой и «1Отчет-Х» импорт принимает
    (accepted(v12_empty_name), accepted(v13_bad_name)), но наш загрузчик при пустом Name
    берёт имя файла — поэтому генератор пустое имя не выдаёт;
  * состав `Properties` — замер реального объекта с пустым содержимым
    (`C:\1C_LLM\LoadDoc\Test0_ processing_Null\ВнешняяОбработка1.xml` и принятый зондом
    `v15_no_containedobject.xml`): Name, Synonym, Comment, DefaultForm, AuxiliaryForm —
    тег AuxiliaryForm в ЕДИНСТВЕННОМ числе. Профиль свойств даёт тот же набор (Name
    обязателен, остальные не обязательны и пусты по умолчанию). Широкие наборы свойств
    (Presentation, UsePurposes, AutoUseParentForm, UseCodePage, StoreContent,
    CompatibilityMode и др.) в принятых зондах не участвовали — генератор их не пишет;
  * атрибут `category` у `xr:GeneratedType` внешнего объекта = `Object`, а не имя вида,
    `name` = `ExternalDataProcessorObject.<Имя>` / `ExternalReportObject.<Имя>` (замер
    обоих эталонов). Вид строки БД (`object_kind`, словарь узла V22) к XML отношения не имеет;
  * `@uuid`, `xr:TypeId`, `xr:ValueId` — свои, свежие UUID v4: переносить их с другого
    объекта нельзя (якорь `identifier-profile-classid-objectid-typeid-valueid`: ClassId —
    идентификатор КЛАССА метаданных, ObjectId/TypeId/ValueId принадлежат объекту и
    генерируемому типу).

Форм вывода (байты): UTF-8 с BOM, CRLF, табуляция — так же пишет
`tools/probe_external_processing_properties.py`, и именно этот формат импорт принимает.
Детерминированность: при заданных `uuid`/`type_id`/`value_id` вывод совпадает
байт-в-байт, поэтому прогон валидатора идемпотентен, а diff двух прогонов показывает
только сделанную правку.
"""
import re
import uuid as uuid_module
from pathlib import Path

FORMAT_VERSION = "2.20"
MDCLASSES_NS = "http://v8.1c.ru/8.3/MDClasses"

# Список префиксов корня — константа из эталонной выгрузки (provenance declared,
# строка профиля MetaDataObject/@xmlns). Порядок фиксирован: он же в выгрузке 1С и в
# принятом зондом файле (_ibcmd_work/v29_probe/v15_no_containedobject.xml). Минимальный
# набор префиксов импортом НЕ проверялся, поэтому неиспользуемые (app, cfg, cmi, ent, lf,
# style, sys, v8ui, web, win, xen, xpr, xs) сохраняются как в доказанном образце.
XMLNS_PREFIXES = (
    ("", MDCLASSES_NS),
    ("app", "http://v8.1c.ru/8.2/managed-application/core"),
    ("cfg", "http://v8.1c.ru/8.1/data/enterprise/current-config"),
    ("cmi", "http://v8.1c.ru/8.2/managed-application/cmi"),
    ("ent", "http://v8.1c.ru/8.1/data/enterprise"),
    ("lf", "http://v8.1c.ru/8.2/managed-application/logform"),
    ("style", "http://v8.1c.ru/8.1/data/ui/style"),
    ("sys", "http://v8.1c.ru/8.1/data/ui/fonts/system"),
    ("v8", "http://v8.1c.ru/8.1/data/core"),
    ("v8ui", "http://v8.1c.ru/8.1/data/ui"),
    ("web", "http://v8.1c.ru/8.1/data/ui/colors/web"),
    ("win", "http://v8.1c.ru/8.1/data/ui/colors/windows"),
    ("xen", "http://v8.1c.ru/8.3/xcf/enums"),
    ("xpr", "http://v8.1c.ru/8.3/xcf/predef"),
    ("xr", "http://v8.1c.ru/8.3/xcf/readable"),
    ("xs", "http://www.w3.org/2001/XMLSchema"),
    ("xsi", "http://www.w3.org/2001/XMLSchema-instance"),
)
NS_BY_PREFIX = dict(XMLNS_PREFIXES)
XR_NS = NS_BY_PREFIX["xr"]
V8_NS = NS_BY_PREFIX["v8"]

# Константы КЛАССОВ метаданных (замер 915 + 158 925 XML, слой `xml-format`): ровно одно
# значение на вид метаданных, оно переходит из поставки в поставку. Это НЕ идентификатор
# объекта, и у объектов конфигурации элемента ClassId нет вовсе — поэтому он не требуется.
CLASS_IDS = {
    "external_report": "e41aff26-25cf-4bb6-b6c1-3f478a75f374",
    "external_processing": "c3831ec8-d8d5-4f93-8a22-f9bfae07327f",
}
# Корневой тег вида метаданных (замер обоих эталонов) и вид строки БД (словарь V22) —
# разные вещи: вид строки задаёт писатель заголовка, тег читает импорт.
ROOT_TAGS = {"external_report": "ExternalReport", "external_processing": "ExternalDataProcessor"}
# Генерируемый тип: ExternalDataProcessorObject.<Имя> — элемент с АТРИБУТАМИ name/category,
# а не набор дочерних элементов (замер; опровергает заметки xsd-schemas/).
GENERATED_TYPE_PREFIX = {
    "external_report": "ExternalReportObject",
    "external_processing": "ExternalDataProcessorObject",
}
# category у xr:GeneratedType внешнего объекта — "Object", а не имя вида
# (замер: Test0_ processing_Null, Test1_Otchet). Ошибочное значение здесь импорт не
# отклоняет (не проверялось), поэтому значение берётся из замера, а не из словаря видов.
GENERATED_TYPE_CATEGORY = "Object"

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'

# Байты вывода: табуляция как отступ, CRLF как перевод строки, BOM в начале файла —
# так же пишут и реальная выгрузка, и принятый зондом файл (замер: BOM True, CRLF-only).
TAB = "\t"
CRLF = "\r\n"
BOM = "\ufeff"

# Имя объекта: начинается с буквы или подчёркивания, далее буквы/цифры/подчёркивание.
# Это ПРАВИЛО ГЕНЕРАТОРА, а не проверенное правило конфигуратора: импорт принимает и
# пустое имя, и «1Отчет-Х» (accepted v12_empty_name, v13_bad_name), а правила именования
# на уровне конфигуратора не проверялись (строка профиля — unknown, закрывается пробой P6).
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-z0-9А-Яа-яЁё_]*$")
# Канонический UUID v4: версия — 13-й шестнадцатеричный разряд (15-й символ строки с
# дефисами), вариант — 8/9/a/b (компоновка RFC 4122). Требование версии 4 задаёт ГЕНЕРАТОР:
# создаваемый объект получает свои свежие v4 (слой `identifier-profile-classid-objectid-
# typeid-valueid`). Валидирует ли версию сама платформа — отдельная проба P3 (uuid формы v1
# или v5), поэтому правило здесь наше, а не измеренное поведение импорта.
UUID_V4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}"
                        r"-[0-9a-f]{12}$")

VERSION_RE = re.compile(r"^\d+\.\d+$")


class AuthorError(ValueError):
    """Спецификация не годится для сборки: причина называется прямо, а не молча."""


def new_ids():
    """Свежие UUID v4 для одного нового объекта: uuid, type_id, value_id — РАЗНЫЕ значения.

    Один uuid под @uuid и xr:ObjectId ставить нельзя: в обеих эталонных выгрузках это
    разные значения (замечание 2 профиля свойств).
    """
    return {"uuid": str(uuid_module.uuid4()), "type_id": str(uuid_module.uuid4()),
            "value_id": str(uuid_module.uuid4())}


def is_valid_identifier(name):
    """Проходит ли имя правилу генератора (см. комментарий у NAME_RE)."""
    return bool(NAME_RE.match(str(name or "")))


def _check_uuid(value, field):
    """Проверить идентификатор: канонический UUID v4 (правило генератора, см. UUID_V4_RE).

    Причина формулируется двумя разными отказами: «это не UUID» и «это UUID другой версии» —
    по одному сообщению нельзя понять, что именно не так с идентификатором.
    """
    text = str(value or "").strip().lower()
    if UUID_V4_RE.match(text):
        return text
    canonical = re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                         text)
    if canonical:
        raise AuthorError(
            f"{field} — канонический UUID, но не версии 4 (версия: {text[14]!r}). "
            "Генератор создаёт объект из своих свежих v4; переносить идентификатор другого "
            "объекта или иную версию нельзя. Проверяет ли версия импорта — проба P3, "
            "ответа о платформе здесь нет."
        )
    raise AuthorError(
        f"{field} не является каноническим UUID v4: {value!r}. Нужен свежий v4 самого "
        "объекта: идентификаторы другого объекта переносить нельзя."
    )



def normalize_spec(spec):
    """Проверить спецификацию и подставить значения по умолчанию.

    Обязательное: name (валидный идентификатор). По умолчанию: uuid/type_id/value_id —
    свежие v4; comment/synonym/default_form/auxiliary_form — пустые; format_version — 2.20
    (иных версий формат не проверялся: строка профиля MetaDataObject/@version = unknown).
    """
    if not isinstance(spec, dict):
        raise AuthorError("Спецификация должна быть словарём")
    name = str(spec.get("name") or "").strip()
    if not name:
        raise AuthorError(
            "Не задано имя объекта (Properties/Name). Пустой Name импорт принимает "
            "(accepted v12_empty_name), но наш загрузчик при пустом Name берёт имя файла, "
            "поэтому генератор пустое имя не выдаёт."
        )
    if not is_valid_identifier(name):
        raise AuthorError(
            f"Имя объекта {name!r} не проходит правилу генератора (начинается с буквы или "
            "_, далее буквы/цифры/_). Правила именования конфигуратором не проверялись, "
            "поэтому границу держит генератор."
        )
    ids = new_ids()
    out = {
        "name": name,
        "object_kind": str(spec.get("object_kind") or "external_processing"),
        "uuid": _check_uuid(spec.get("uuid") or ids["uuid"], "uuid"),
        "type_id": _check_uuid(spec.get("type_id") or ids["type_id"], "type_id"),
        "value_id": _check_uuid(spec.get("value_id") or ids["value_id"], "value_id"),
        "comment": str(spec.get("comment") or ""),
        "synonym": dict(spec.get("synonym") or {}),
        "default_form": str(spec.get("default_form") or ""),
        "auxiliary_form": str(spec.get("auxiliary_form") or ""),
        "format_version": str(spec.get("format_version") or FORMAT_VERSION),
    }
    if out["object_kind"] not in CLASS_IDS:
        raise AuthorError(
            "Неизвестный вид объекта: %r. Этап 1 — только внешняя обработка "
            "(внешний отчёт — следующий этап)." % out["object_kind"]
        )
    if not VERSION_RE.match(out["format_version"]):
        raise AuthorError(f"Некорректная версия формата: {out['format_version']!r}")
    return out


# ---------------------------------------------------------------------------
# Сборка XML
# ---------------------------------------------------------------------------


def escape_text(value):
    """Экранирование XML-текста. Порядок важен: & первым, иначе экранирование удвоится.

    Табуляция и переводы строк внутри значения остаются как есть: в эталонных файлах их
    нет, а round-trip (шаг 7 плана) проверяется на пустых значениях.
    """
    text = "" if value is None else str(value)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text.replace('"', "&quot;")


def _pad(depth):
    """Отступ строки: табуляция × depth. CRLF добавляет write_text."""
    return TAB * depth


def _empty_or_value(depth, tag, value):
    """Строка свойства: пустое значение — самозакрывающийся тег, иначе значение внутри.

    Пустое значение пишется именно как `<Тег/>`, а не как отсутствующая строка: так
    записаны эталонная выгрузка пустой обработки (Test0_ processing_Null) и принятый
    зондом файл. Отсутствие Properties целиком импорт принимает (accepted
    v11_empty_properties), но пустой объект без Properties читается двусмысленно.
    """
    text = "" if value is None else str(value)
    if not text:
        return [_pad(depth) + f"<{tag}/>"]
    return [_pad(depth) + f"<{tag}>{escape_text(text)}</{tag}>"]


def _synonym_lines(synonym, depth):
    """Синоним: пустой — `<Synonym/>` (замер эталона пустой обработки).

    Непустой — каноническая раскладка реальной выгрузки с заполненным синонимом
    (замер `Test1_Otchet\\СравнениеУСНИ90_2.xml`, файл принят платформой): внутри
    каждого `<v8:item>` — сначала `<v8:lang>{ключ словаря}</v8:lang>`, затем
    `<v8:content>текст</v8:content>`. Порядок и наличие lang — не косметика:
    XDTO-тип свойства — `{http://v8.1c.ru/8.1/data/core}LocalStringType`, и item
    без lang импорт отклоняет (замер B3 валидатора V29: «Ошибка преобразования
    данных XDTO … НачалоСвойства: Synonym … LocalStringType»). Тот же формат
    читает и наш загрузчик: `_multi_text` (src/external_meta_parser.py) строит
    jsonb только по паре lang+content, без lang синоним в БД не попадает.
    Ключ словаря спецификации (`ru`) пишется значением `<v8:lang>` как есть —
    так же, как в эталонной выгрузке.
    """
    if not synonym:
        return [_pad(depth) + "<Synonym/>"]
    lines = [_pad(depth) + "<Synonym>"]
    for lang, content in synonym.items():
        lines.append(_pad(depth + 1) + "<v8:item>")
        lines.append(_pad(depth + 2) + f"<v8:lang>{escape_text(lang)}</v8:lang>")
        lines.append(_pad(depth + 2) + f"<v8:content>{escape_text(content)}</v8:content>")
        lines.append(_pad(depth + 1) + "</v8:item>")
    lines.append(_pad(depth) + "</Synonym>")
    return lines


def _properties_lines(spec, depth):
    """Properties в составе и порядке, замеренном на объекте с пустым содержимым.

    Состав и порядок (замер: Test0_ processing_Null и принятый зондом
    v15_no_containedobject.xml): Name, Synonym, Comment, DefaultForm, AuxiliaryForm —
    заметьте AuxiliaryForm (единственное число), а не AuxiliaryForms. Профиль свойств
    (якорь `property-profile-externaldataprocessor`) даёт тот же набор: Name обязателен,
    остальные пять не обязательны и по умолчанию пусты.

    Более широкие наборы свойств (Presentation, ExtensionPresentation, Picture,
    UsePurposes, AdditionalProperties, AutoUseParentForm, UseCodePage, StoreContent,
    CompatibilityMode) в принятых зондах не участвовали: у отчёта они есть в эталоне
    Test1_Otchet, для обработки не проверялись. Поэтому Этап 1 их не пишет: строка
    профиля по каждому из них = unknown, закрывается пробами P1–P6.
    """
    lines = [
        _pad(depth) + "<Properties>",
        _pad(depth + 1) + f"<Name>{escape_text(spec['name'])}</Name>",
    ]
    lines += _synonym_lines(spec["synonym"], depth + 1)
    lines += _empty_or_value(depth + 1, "Comment", spec["comment"])
    lines += _empty_or_value(depth + 1, "DefaultForm", spec["default_form"])
    lines += _empty_or_value(depth + 1, "AuxiliaryForm", spec["auxiliary_form"])
    lines.append(_pad(depth) + "</Properties>")
    return lines


def _root_open_line(spec):
    """Строка корня: MetaDataObject со списком префиксов в фиксированном порядке.

    Порядок и состав префиксов — замер принятых файлов (см. XMLNS_PREFIXES); атрибут
    version идёт последним, как в выгрузке. Версия 2.20 — в ней выполнены все принятые
    зонды; иных версий формат не проверялся.
    """
    attrs = " ".join(
        ('xmlns' if not prefix else f'xmlns:{prefix}') + f'="{uri}"'
        for prefix, uri in XMLNS_PREFIXES
    )
    return f'<MetaDataObject {attrs} version="{spec["format_version"]}">'


def build_external_object_xml(spec):
    """Собрать текст XML внешнего объекта по спецификации (общая сборка для обоих видов).

    Порядок дочерних элементов значим: InternalInfo -> Properties -> ChildObjects.
    Доказательство — отклонённые зонды v5_no_properties («читаемое свойство не
    соответствует ожидаемому. Текущее Properties, ожидаемое ChildObjects») и
    v8_no_childobjects; пустыми они принимаются (v11_empty_properties).

    Блок xr:ContainedObject НЕ пишется вовсе: файл без него принят (v15_no_containedobject),
    а пустой ClassId и ClassId чужого вида отклонены (v14_empty_classid,
    v10_foreign_classid). В модуле нет ни одной ветки, способной напечатать ContainedObject:
    написать нельзя то, чего нет в коде.

    Атрибут category элемента xr:GeneratedType = "Object" (замер эталонов), name =
    `< префикс вида >Object.<Имя>`. @uuid/TypeId/ValueId — свежие UUID v4 самого объекта.

    Возвращает текст БЕЗ BOM и с переводом строки \\n: байты (UTF-8 BOM + CRLF) даёт
    write_text. При одних и тех же идентификаторах вывод побайтово совпадает от вызова
    к вызову — на этом держится идемпотентность валидатора и читаемый diff правок.
    """
    spec = normalize_spec(spec)
    kind = spec["object_kind"]
    root_tag = ROOT_TAGS[kind]
    type_name = f"{GENERATED_TYPE_PREFIX[kind]}.{spec['name']}"
    lines = [
        XML_DECLARATION,
        _root_open_line(spec),
        _pad(1) + f'<{root_tag} uuid="{spec["uuid"]}">',
        _pad(2) + "<InternalInfo>",
        _pad(3) + f'<xr:GeneratedType name="{escape_text(type_name)}" '
        f'category="{GENERATED_TYPE_CATEGORY}">',
        _pad(4) + f"<xr:TypeId>{spec['type_id']}</xr:TypeId>",
        _pad(4) + f"<xr:ValueId>{spec['value_id']}</xr:ValueId>",
        _pad(3) + "</xr:GeneratedType>",
        _pad(2) + "</InternalInfo>",
    ]
    lines += _properties_lines(spec, 2)
    lines.append(_pad(2) + "<ChildObjects/>")
    lines.append(_pad(1) + f"</{root_tag}>")
    lines.append("</MetaDataObject>")
    return "\n".join(lines)


def build_external_processing_xml(spec):
    """Собрать XML внешней обработки (точка входа Этапа 1).

    Вид фиксируется в спецификации: явный object_kind="external_report" отклоняется,
    потому что отчёт — следующий этап, а не потому что сборка не умеет.
    """
    spec = dict(spec)
    spec.setdefault("object_kind", "external_processing")
    if spec["object_kind"] != "external_processing":
        raise AuthorError(
            "Этап 1 собирает только внешнюю обработку (object_kind='external_processing'); "
            f"передан вид {spec['object_kind']!r}."
        )
    return build_external_object_xml(spec)


# ---------------------------------------------------------------------------
# Запись каталога разбора
# ---------------------------------------------------------------------------


def write_text(path, text):
    """Записать текст в UTF-8 с BOM и CRLF (байты принятого форматом образца).

    BOM и CRLF относятся к формату выгрузки: и эталонная выгрузка, и принятый зондом
    файл имеют BOM и только CRLF (замер: BOM True, LF-only 0). Поведение импорта при
    UTF-8 без BOM или с LF не проверялось — эксперимент не проводится, чтобы не смешивать
    проверку создания объекта с проверкой кодировки.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = BOM + text.replace("\r\n", "\n").replace("\n", CRLF)
    target.write_bytes(data.encode("utf-8"))
    return str(target)


def write_layout(spec, layout_dir):
    """Записать каталог разбора той же раскладки, что даёт `ibcmd config export`.

    Раскладка и кодировки зафиксированы в docs/EXTERNAL_OBJECT_EDIT_PLAN.md (раздел 0):
    `<ИмяОбъекта>.xml` в корне каталога И подкаталоги `Ext/`, `Forms/`, `Templates/` —
    ВНУТРИ каталога `<ИмяОбъекта>/` с тем же базовым именем. Это не произвольный выбор:
    ровно такую пару (`<база>.xml` + `<база>/Ext/…`) даёт `ibcmd config export` (замер:
    `_ibcmd_work/epf_real.xml` + `_ibcmd_work/epf_real/Ext`), и ровно так же загрузчик
    ищет каталог содержимого — `Path(ext_xml).parent / Path(ext_xml).stem`
    (src/external_report_loader.py, V10). Плоская раскладка (`Ext/` рядом с XML) для
    объекта с содержимым означала бы «форм и макетов не найдено».
    Каталог разбора — транспорт между БД и конфигуратором, а не место правок (правило 10).
    Пустые подкаталоги создаются намеренно: их отсутствие для объекта с пустым
    содержимым импортом не проверялось, а раскладка export их даёт.

    Возвращает dict с путями: layout_dir, root_xml, content_dir, ext_dir, forms_dir,
    templates_dir.
    """
    spec = normalize_spec(spec)
    root = Path(layout_dir)
    root.mkdir(parents=True, exist_ok=True)
    content = root / spec["name"]
    for sub in ("Ext", "Forms", "Templates"):
        (content / sub).mkdir(parents=True, exist_ok=True)
    root_xml = write_text(root / f"{spec['name']}.xml", build_external_object_xml(spec))
    return {
        "layout_dir": str(root),
        "root_xml": root_xml,
        "content_dir": str(content),
        "ext_dir": str(content / "Ext"),
        "forms_dir": str(content / "Forms"),
        "templates_dir": str(content / "Templates"),
    }
