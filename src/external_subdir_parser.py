#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор подкаталогов выгрузки внешнего объекта: Forms/, Templates/, Ext/*.bsl.

Норматив: docs/config-scenarios/FLOWCHART_1c-configurations-core.md (узлы V13, V14, V15).
Точка входа: parse_external_subdirs(base_path, report_uuid, ...) - см. docstring функции.

Правила:
  * R3: пустой или некорректный uuid у Form/Template из файла регистрации - ошибка
    разбора, загрузка прекращается (полный откат транзакции);
  * бинарная форма (Forms/<Имя>/Ext/Form.bin вместо Form.xml) и отсутствие каталогов
    Forms/, Templates/, Ext/ - НЕ ошибка: свойства формы не разбираются, возвращается
    только предупреждение;
  * V14: у бинарной ordinary-формы модуль берётся из 0/module внутри Form.bin и пишется
    в form_ext.ext (правило R9: в bsl_modules модуль формы не дублируется). Если v8unpack
    недоступен или контейнер не распаковывается - ext остаётся пустым, это предупреждение,
    а не ошибка; ext_bin сохраняется всегда;
  * V15: состав ordinary-формы берётся из 0/form того же контейнера и пишется в ТЕ ЖЕ колонки
    form_ext (items/attributes/events/commands/auto_command_bar), что и разбор Form.xml для
    управляемой формы: новых колонок в DDL нет, витрины v_form_elements/v_form_events общие.
    Полный elem.json v8unpack не сохраняется - источник истины ext_bin. Отказ разбора
    (нет v8unpack, неподдерживаемая версия разметки, пустая разметка) - предупреждение,
    колонки остаются пустыми, загрузка продолжается. Контейнер распакуется ОДИН раз на форму;
  * CustomSettingsFolder вида "3:02023637-..." uuid НЕ является и по R3 не проверяется;
  * имена форм/макетов из корневого XML (refs) служат только сверкой: расхождение -
    предупреждение, а не откат; uuid формы/макета берётся ИСКЛЮЧИТЕЛЬНО из файла
    Forms/<Имя>.xml / Templates/<Имя>.xml;
  * текст модуля формы и содержимое макета сохраняются целиком; при превышении порога
    MAX_TEXT_CHARS содержимое обрезается, ставится признак truncated и предупреждение.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

from external_meta_parser import (
    _bool,
    _check_uuid,
    _child,
    _children,
    _local,
    _multi_text,
    _read_properties,
    _text,
    _type_info,
)
from external_form_decoder import decode_layout

# Порог сохранения текстового содержимого (модуль формы, содержимое макета, код BSL).
MAX_TEXT_CHARS = 1_000_000

# Свойства регистрации формы: имя XML-свойства -> (колонка БД, вид значения).
FORM_REGISTRATION_FIELDS = {
    "Name": ("name", "text"),
    "Comment": ("comment", "text"),
    "FormType": ("form_type", "text"),
    "IncludeHelpInContents": ("include_help_in_contents", "bool"),
}

# Свойства регистрации макета.
TEMPLATE_REGISTRATION_FIELDS = {
    "Name": ("name", "text"),
    "Comment": ("comment", "text"),
    "TemplateType": ("template_type", "text"),
}

# Скалярные свойства содержимого формы (Ext/Form.xml). Вид значения — «text», как и в
# FORM_REGISTRATION_FIELDS / TEMPLATE_REGISTRATION_FIELDS: _read_properties разбирает
# значение как пару (колонка, вид); строка вместо пары даёт ValueError (дефект п. 18 правил).
FORM_CONTENT_FIELDS = {
    "CommandBarLocation": ("command_bar_location", "text"),
    "ReportResult": ("report_result", "text"),
    "DetailsData": ("details_data", "text"),
    "ReportFormType": ("report_form_type", "text"),
    "AutoShowState": ("auto_show_state", "text"),
    "CustomSettingsFolder": ("custom_settings_folder", "text"),
    "ReportResultViewMode": ("report_result_view_mode", "text"),
    "ViewModeApplicationOnSetReportResult": ("view_mode_application_on_set_report_result", "text"),
}

# Модули из Ext/ каталога объекта: имя файла (в нижнем регистре) -> тип модуля.
MODULE_FILE_KINDS = {
    "objectmodule.bsl": "ObjectModule",
    "managermodule.bsl": "ManagerModule",
}

# Псевдо-элементы формы (контекстные меню, расширенные подсказки): в items не попадают.
SKIPPED_ITEM_KINDS = {"contextmenu", "extendedtooltip", "autocommandbar", "childitems"}

FORMS_DIR_NAME = "Forms"
TEMPLATES_DIR_NAME = "Templates"
EXT_DIR_NAME = "Ext"
MODULE_DIR_NAME = "Form"

# V14/V15: у обычной формы (FormType=Ordinary) нет ни Ext/Form/Module.bsl, ни Form.xml -
# содержимое лежит внутри Form.bin (контейнер 1С с файлами 0/module и 0/form).
# 0/module -> form_ext.ext (узел V14), 0/form -> form_ext.items/attributes/events/commands/
# auto_command_bar (узел V15). Контейнер распакуется ОДИН раз на форму.
# v8unpack — ОПЦИОНАЛЬНАЯ зависимость (tools/requirements.txt): без неё поведение узла V13
# сохраняется (ext пустой, jsonb-колонки пустые, ext_bin полный), но предупреждения
# формулируются честно и загрузка не прерывается.
CONTAINER_MODULE_NAME = "module"
CONTAINER_LAYOUT_NAME = "form"


def _container_files(blob):
    """Байты контейнера Form.bin -> ({имя внутреннего файла: байты}, None).

    При неудаче возвращает (None, причина). Распаковка только с deflate=False:
    Form.bin из XML-выгрузки не сжат, CLI «python -m v8unpack -E» к нему неприменим.
    v8unpack импортируется внутри функции — при его отсутствии загрузка продолжается.
    """
    if not blob:
        return None, "содержимое form_ext.ext_bin пустое"
    try:
        from v8unpack.container_reader import extract as container_extract
    except ImportError:
        return None, ("v8unpack не установлен (pip install -r tools/requirements.txt), "
                      "модуль формы из Form.bin не извлечён")
    import io
    import os
    import sys
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as tmp:
            container = Path(tmp) / "Form.bin"
            container.write_bytes(blob)
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            # v8unpack печатает прогресс в stdout/stderr — глушим его на время распаковки.
            saved_out, saved_err = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = io.StringIO()
            try:
                container_extract(str(container), str(out_dir), False, True)
            finally:
                sys.stdout, sys.stderr = saved_out, saved_err
            found = {}
            for root, _dirs, names in os.walk(out_dir):
                for name in names:
                    found[name] = (Path(root) / name).read_bytes()
            return found, None
    except Exception as exc:
        return None, f"контейнер Form.bin не распаковывается: {exc}"


def _store_container_form_module(form_ext, name, warnings, container=None):
    """V14: текст модуля обычной формы берётся из 0/module внутри form_ext.ext_bin.

    Пишет form_ext.ext / ext_truncated; ext_size и ext_path не меняются — источником
    остаётся Forms/<Имя>/Ext/Form.bin (инвариант: ext_size = octet_length(ext_bin)).
    container — уже готовый (_container_files(...)) результат распаковки: он общий с узлом
    V15 (0/form), повторной распаковки контейнера на ту же форму нет.
    Возвращает True, если модуль сохранён. В bsl_modules модуль формы не дублируется (R9).
    """
    files, reason = _container_files(form_ext.get("ext_bin")) if container is None else container
    if files is None:
        warnings.append(f"Форма '{name}' выгружена в бинарном виде "
                        f"(Forms/{name}/Ext/Form.bin): модуль формы не извлечён — {reason}. "
                        "Колонка form_ext.ext остаётся пустой, содержимое формы сохранено "
                        "в form_ext.ext_bin целиком и восстанавливается из него.")
        return False
    module = files.get(CONTAINER_MODULE_NAME)
    if module is None:
        warnings.append(f"В контейнере формы '{name}' нет файла 0/module: у формы нет модуля, "
                        "колонка form_ext.ext остаётся пустой.")
        return False
    code = module.decode("utf-8-sig", errors="replace")
    truncated = len(code) > MAX_TEXT_CHARS
    if truncated:
        code = code[:MAX_TEXT_CHARS]
    form_ext["ext"] = code
    form_ext["ext_truncated"] = truncated
    if truncated:
        warnings.append(f"Модуль формы '{name}' длиннее порога {MAX_TEXT_CHARS} символов: "
                        "содержимое обрезано, ext_truncated = true.")
    return True


def _apply_container_form_layout(form_ext, name, form_uuid, container, warnings):
    """V15: состав ordinary-формы из 0/form внутри form_ext.ext_bin -> колонки form_ext.

    Заполняет ТЕ ЖЕ колонки (items / attributes / events / commands / auto_command_bar), что
    и разбор Form.xml для управляемой формы (V13): новых колонок в DDL нет, витрины
    v_form_elements / v_form_events и SQL-анализ остаются общими для обеих разновидностей.
    Полный elem.json v8unpack в БД не идёт — источник истины form_ext.ext_bin, из него
    0/form воспроизводится байт-в-байт (проверка — tools/decode_form_layout.py --round-trip).

    container — общий результат _container_files(...) для этой формы (V14 + V15).
    Возвращает ({items, attributes, events, commands, layout_version}, None) при успехе и
    (None, причина) при отказе: отказ НЕ прерывает загрузку (v8unpack опционален).
    """
    files, reason = container
    if files is None:
        return None, reason
    layout = files.get(CONTAINER_LAYOUT_NAME)
    if layout is None:
        return None, "в контейнере Form.bin нет файла 0/form — разметка элементов формы отсутствует"
    decoded = decode_layout(layout, name, form_uuid)
    if not decoded.get("success"):
        return None, decoded.get("reason") or "разметка 0/form не разобрана"
    columns = decoded["columns"]
    form_ext["items"] = columns["items"]
    form_ext["attributes"] = columns["attributes"]
    form_ext["events"] = columns["events"]
    form_ext["commands"] = columns["commands"]
    if columns["auto_command_bar"]:
        form_ext["auto_command_bar"] = columns["auto_command_bar"]
    for warning in decoded.get("warnings") or []:
        warnings.append(f"Разметка формы '{name}': {warning}.")
    counts = dict(decoded["counts"])
    counts["layout_version"] = decoded.get("layout_version")
    return counts, None



def _find_dir(parent, name):
    """Каталог по имени без учёта регистра (None, если его нет или parent отсутствует)."""
    if parent is None:
        return None
    try:
        for candidate in parent.iterdir():
            if candidate.is_dir() and candidate.name.lower() == name.lower():
                return candidate
    except OSError:
        return None
    return None


def _find_file(parent, name):
    """Файл по имени без учёта регистра (None, если его нет или parent отсутствует)."""
    if parent is None:
        return None
    try:
        for candidate in parent.iterdir():
            if candidate.is_file() and candidate.name.lower() == name.lower():
                return candidate
    except OSError:
        return None
    return None


def _registration_files(directory):
    """Файлы регистрации (Forms/*.xml, Templates/*.xml) в устойчивом порядке."""
    if directory is None:
        return []
    try:
        return sorted([p for p in directory.glob("*.xml") if p.is_file()],
                      key=lambda p: p.name.lower())
    except OSError:
        return []


def _meta_element(xml_path, tag_name):
    """Элемент <Form>/<Template> из файла регистрации.

    Корневой тег выгрузки - MetaDataObject, а нужный элемент - его потомок верхнего
    уровня; проверяется и сам корень, и дети верхнего уровня (так же, как в корневом XML).
    """
    try:
        root = ET.parse(str(xml_path)).getroot()
    except ET.ParseError as exc:
        return None, {"success": False,
                      "error": f"Файл {xml_path} не разобран как XML: {exc}",
                      "hint": "Загрузка прекращена: выгрузка повреждена или не является XML."}
    except OSError as exc:
        return None, {"success": False,
                      "error": f"Не удалось прочитать файл {xml_path}: {exc}",
                      "hint": "Загрузка прекращена: файл выгрузки недоступен для чтения."}
    if _local(root.tag) == tag_name:
        return root, {"success": True}
    for child in root:
        if _local(child.tag) == tag_name:
            return child, {"success": True}
    return None, {"success": False,
                  "error": f"В файле {xml_path} нет элемента {tag_name}",
                  "hint": "Файл подкаталога не соответствует ожидаемой регистрации "
                          f"{tag_name}; загрузка прекращена."}


def _read_use_purposes(element):
    """<UsePurposes> -> список строк из <v8:Value> (jsonb-массив use_purposes)."""
    if element is None:
        return []
    values = []
    for value_element in _children(element, "Value"):
        text = _text(value_element)
        if text:
            values.append(text)
    return values


def _read_text_file(path):
    """Текст файла (BOM снимается); возвращает (текст, признак обрезки, размер в байтах)."""
    try:
        size = path.stat().st_size
    except OSError:
        size = None
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            content = handle.read()
    except OSError:
        return None, False, size
    truncated = len(content) > MAX_TEXT_CHARS
    if truncated:
        content = content[:MAX_TEXT_CHARS]
    return content, truncated, size


def _read_bytes_file(path):
    """Содержимое файла как байты (для bytea-колонки ext_bin) либо None."""
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _rel_path(path, source_path):
    """Путь файла относительно корня выгрузки (как в bsl_modules.file_path)."""
    if source_path:
        try:
            return str(Path(path).relative_to(Path(source_path))).replace("\\", "/")
        except ValueError:
            pass
    return str(path)


def _root_tag_of(xml_path):
    """Локальное имя корневого тега XML содержимого ('' если файл не разбирается)."""
    try:
        root = ET.parse(str(xml_path)).getroot()
    except Exception:
        return ""
    return _local(root.tag)


def _read_form_items(container, depth=0):
    """Рекурсивная сводка <ChildItems>: вид элемента, имя, id, DataPath, заголовок и т.п."""
    items = []
    if container is None or depth > 64:
        return items
    for element in container:
        kind = _local(element.tag)
        if not kind or kind.lower() in SKIPPED_ITEM_KINDS:
            continue
        item = {"kind": kind, "name": element.get("name"), "id": element.get("id")}
        for tag, key in (("Type", "type"), ("DataPath", "datapath"),
                        ("CommandName", "command_name"), ("Representation", "representation"),
                        ("Group", "group"), ("Behavior", "behavior")):
            value = _text(_child(element, tag))
            if value:
                item[key] = value
        picture = _child(element, "Picture")
        if picture is not None:
            reference = _text(_child(picture, "Ref"))
            if reference:
                item["picture"] = reference
        title = _multi_text(_child(element, "Title"))
        if title:
            item["title"] = title
        tooltip = _multi_text(_child(element, "ToolTip"))
        if tooltip:
            item["tooltip"] = tooltip
        items.append(item)
        nested = _child(element, "ChildItems")
        if nested is not None:
            items.extend(_read_form_items(nested, depth + 1))
    return items


def _read_form_attributes(element):
    """<Attributes> содержимого формы: реквизиты формы (name, id, тип, заголовок)."""
    result = []
    if element is None:
        return result
    for attribute in _children(element, "Attribute"):
        item = {"name": attribute.get("name"), "id": attribute.get("id")}
        info = _type_info(_child(attribute, "Type"))
        if info:
            item["type"] = info
        main_attribute = _bool(_child(attribute, "MainAttribute"))
        if main_attribute is not None:
            item["main_attribute"] = main_attribute
        title = _multi_text(_child(attribute, "Title"))
        if title:
            item["title"] = title
        result.append(item)
    return result


def _read_form_commands(element):
    """<Commands> содержимого формы: команды (name, id, заголовок, подсказка, действие)."""
    result = []
    if element is None:
        return result
    for command in _children(element, "Command"):
        item = {"name": command.get("name"), "id": command.get("id")}
        for tag, key in (("Action", "action"), ("UseMode", "use_mode")):
            value = _text(_child(command, tag))
            if value:
                item[key] = value
        title = _multi_text(_child(command, "Title"))
        if title:
            item["title"] = title
        tooltip = _multi_text(_child(command, "ToolTip"))
        if tooltip:
            item["tooltip"] = tooltip
        result.append(item)
    return result


def _read_form_events(element):
    """<Events> содержимого формы: [{event, handler}] (<Event name="OnCreateAtServer">...).</Event>."""
    result = []
    if element is None:
        return result
    for event in _children(element, "Event"):
        result.append({"event": event.get("name"), "handler": _text(event)})
    return result


def _read_auto_command_bar(element):
    """<AutoCommandBar name id> с <Autofill> -> {name, id, autofill}."""
    if element is None:
        return None
    info = {"name": element.get("name"), "id": element.get("id")}
    autofill = _bool(_child(element, "Autofill"))
    if autofill is not None:
        info["autofill"] = autofill
    return info


def _content_dir(base_dir, candidate_names):
    """Каталог содержимого <каталог объекта>/<Имя>/Ext по списку возможных имён."""
    for candidate in candidate_names:
        if not candidate:
            continue
        ext_dir = _find_dir(_find_dir(base_dir, candidate), EXT_DIR_NAME)
        if ext_dir is not None:
            return ext_dir
    return None


def _read_form(xml_path, forms_dir, parent_uuid, parent_type, ref_names, warnings,
               source_path=None):
    """Одна форма: регистрация Forms/<Имя>.xml + содержимое Forms/<Имя>/Ext/.

    Возвращает {"success": True, "form": {...}, "form_ext": {...}} либо ошибку разбора.
    form_ext.form_id проставляет загрузчик (связь с forms.id после вставки формы).
    form_ext.ext_path - путь файла, из которого взято содержимое: модуля Module.bsl,
    если сохранён ext; Form.bin - для бинарной формы; Form.xml - если разобраны свойства.
    """
    element, status = _meta_element(xml_path, "Form")
    if not status.get("success"):
        return status
    checked = _check_uuid(element.get("uuid"), "Form", xml_path.stem)
    if not checked.get("success"):
        return checked
    uuid = checked["uuid"]

    properties = _child(element, "Properties")
    row = {"uuid": uuid, "parent_uuid": parent_uuid, "parent_type": parent_type}
    row.update(_read_properties(properties, FORM_REGISTRATION_FIELDS))
    row["synonym"] = _multi_text(_child(properties, "Synonym"))
    row["use_purposes"] = _read_use_purposes(_child(element, "UsePurposes"))
    if not row.get("name"):
        row["name"] = xml_path.stem
        warnings.append(f"У формы из файла {xml_path.name} пуст <Name>: использовано "
                        f"имя файла '{xml_path.stem}'.")
    name = row["name"]
    if ref_names and name not in ref_names:
        warnings.append(f"Форма '{name}' есть в каталоге Forms/, но в корневом XML она не "
                        "объявлена: форма сохранена, расхождение имён исправляется в конфигураторе.")

    form_ext = {"form_uuid": uuid, "parent_uuid": parent_uuid,
                "parent_type": parent_type, "name": name, "ext_truncated": False}
    ext_dir = _content_dir(forms_dir, (name, xml_path.stem))
    if ext_dir is None:
        form_ext["ext_format"] = "none"
        warnings.append(f"Для формы '{name}' нет каталога содержимого Forms/{name}/Ext: "
                        "сохранена только регистрация формы.")
        return {"success": True, "form": row, "form_ext": form_ext}

    form_xml = _find_file(ext_dir, "Form.xml")
    form_bin = _find_file(ext_dir, "Form.bin")
    # V15: распаковка Form.bin выполняется ОДИН раз на форму и переиспользуется для
    # 0/module (модуль, V14) и 0/form (состав элементов, V15).
    container = None
    if form_xml is not None:
        form_ext["ext_format"] = "xml"
        try:
            root = ET.parse(str(form_xml)).getroot()
        except ET.ParseError as exc:
            warnings.append(f"Содержимое формы '{name}' ({form_xml.name}) не разобрано как "
                            "XML: {0}. Разобраны только регистрация формы и её модуль.".format(exc))
        else:
            # Скалярные свойства содержимого формы в Form.xml лежат НЕ в <Properties>, а
            # непосредственно в корневом элементе <Form> (в отличие от XML метаданных).
            # До узла V14.1 их разбор молча не выполнялся: _child(root, "Properties")
            # давал None, и form_ext.command_bar_location / report_result / details_data /
            # report_form_type / auto_show_state / custom_settings_folder /
            # report_result_view_mode / view_mode_application_on_set_report_result
            # оставались NULL при явно заданных в выгрузке значениях (дефект п. 18 правил).
            # Фallback на <Properties> оставлен на случай иной раскладки.
            scalars = _read_properties(root, FORM_CONTENT_FIELDS)
            if not scalars:
                scalars = _read_properties(_child(root, "Properties"), FORM_CONTENT_FIELDS)
            form_ext.update(scalars)
            form_ext["attributes"] = _read_form_attributes(_child(root, "Attributes"))
            form_ext["commands"] = _read_form_commands(_child(root, "Commands"))
            form_ext["items"] = _read_form_items(_child(root, "ChildItems"))
            form_ext["events"] = _read_form_events(_child(root, "Events"))
            form_ext["auto_command_bar"] = _read_auto_command_bar(_child(root, "AutoCommandBar"))
    elif form_bin is not None:
        data = _read_bytes_file(form_bin)
        form_ext["ext_format"] = "bin"
        form_ext["ext_bin"] = data
        form_ext["ext_size"] = len(data) if data is not None else None
        container = _container_files(data)
        warnings.append(f"Форма '{name}' выгружена в бинарном виде "
                        f"(Forms/{name}/Ext/Form.bin): скалярные свойства формы "
                        "(command_bar_location, report_result, details_data, report_form_type, "
                        "auto_show_state, custom_settings_folder, report_result_view_mode, "
                        "view_mode_application_on_set_report_result) из Form.bin не разбираются; "
                        "двоичное содержимое формы сохранено в form_ext.ext_bin целиком "
                        "и воспроизводится из него байт-в-байт.")
        layout_counts, layout_reason = _apply_container_form_layout(
            form_ext, name, uuid, container, warnings)
        if layout_counts:
            warnings.append(
                f"Состав формы '{name}' разложен из 0/form контейнера Form.bin "
                f"(версия разметки {layout_counts['layout_version']}): items "
                f"{layout_counts['items']}, attributes {layout_counts['attributes']}, events "
                f"{layout_counts['events']}, commands {layout_counts['commands']} — колонки "
                "form_ext заполнены так же, как для управляемой формы "
                "(элементы формы доступны через витрину v_form_elements).")
        else:
            warnings.append(
                f"Состав формы '{name}' (form_ext.items/attributes/events/commands) не разложен: "
                f"{layout_reason}. Колонки остаются пустыми; содержимое Form.bin сохранено в "
                "form_ext.ext_bin и будет разложено, когда разбор станет доступен.")
    else:
        form_ext["ext_format"] = "none"
        warnings.append(f"В каталоге Forms/{name}/Ext нет ни Form.xml, ни Form.bin: "
                        "содержимое формы не сохранено.")

    module_path = _find_file(_find_dir(ext_dir, MODULE_DIR_NAME), "Module.bsl")
    if module_path is not None:
        code, truncated, size = _read_text_file(module_path)
        if code is None:
            warnings.append(f"Модуль формы '{name}' ({module_path.name}) не читается: "
                            "содержимое модуля не сохранено.")
        else:
            form_ext["ext"] = code
            form_ext["ext_size"] = size if size is not None else len(code.encode("utf-8"))
            form_ext["ext_truncated"] = bool(truncated)
            if truncated:
                warnings.append(f"Модуль формы '{name}' длиннее порога {MAX_TEXT_CHARS} "
                                "символов: содержимое обрезано, ext_truncated = true.")
    elif form_ext["ext_format"] == "bin":
        # V14: у обычной формы файла Ext/Form/Module.bsl в выгрузке нет — её модуль лежит
        # внутри Form.bin (0/module). Говорить «модуля нет» некорректно (дефект п. 15 правил).
        if _store_container_form_module(form_ext, name, warnings, container):
            # Отдельная строка о том, что модуль всё-таки сохранён: без неё предупреждение
            # о бинарной форме читается как «модуля в БД нет» (проверено на Test2_Otchet).
            warnings.append(f"Модуль формы '{name}' извлечён из 0/module контейнера Form.bin "
                            f"и сохранён в form_ext.ext (V14): {len(form_ext['ext'])} символов.")
    else:
        warnings.append(f"У формы '{name}' нет модуля Forms/{name}/Ext/Form/Module.bsl: "
                        "колонка form_ext.ext остаётся пустой.")
    # ext_path - файл-источник содержимого: Module.bsl, Form.bin или Form.xml.
    if form_ext.get("ext") and module_path is not None:
        form_ext["ext_path"] = _rel_path(module_path, source_path)
    elif form_ext.get("ext_bin") is not None:
        form_ext["ext_path"] = _rel_path(form_bin, source_path)
    elif form_ext["ext_format"] == "xml":
        form_ext["ext_path"] = _rel_path(form_xml, source_path)
    return {"success": True, "form": row, "form_ext": form_ext}


def _read_template(xml_path, templates_dir, parent_uuid, parent_type, ref_names, warnings,
                   source_path=None):
    """Один макет: регистрация Templates/<Имя>.xml + содержимое Templates/<Имя>/Ext/.

    Содержимое Template.xml сохраняется в templates.ext текстом как есть (без разбора),
    имя корневого тега - в templates.ext_root_tag; бинарный случай (Template.bin) идёт
    в templates.ext_bin.
    """
    element, status = _meta_element(xml_path, "Template")
    if not status.get("success"):
        return status
    checked = _check_uuid(element.get("uuid"), "Template", xml_path.stem)
    if not checked.get("success"):
        return checked
    uuid = checked["uuid"]

    properties = _child(element, "Properties")
    row = {"uuid": uuid, "parent_uuid": parent_uuid, "parent_type": parent_type}
    row.update(_read_properties(properties, TEMPLATE_REGISTRATION_FIELDS))
    row["synonym"] = _multi_text(_child(properties, "Synonym"))
    if not row.get("name"):
        row["name"] = xml_path.stem
        warnings.append(f"У макета из файла {xml_path.name} пуст <Name>: использовано "
                        f"имя файла '{xml_path.stem}'.")
    name = row["name"]
    if ref_names and name not in ref_names:
        warnings.append(f"Макет '{name}' есть в каталоге Templates/, но в корневом XML он не "
                        "объявлен: макет сохранён, расхождение имён исправляется в конфигураторе.")

    ext_dir = _content_dir(templates_dir, (name, xml_path.stem))
    if ext_dir is None:
        row["ext_format"] = "none"
        # ext_truncated — NOT NULL DEFAULT false, но писатель перечисляет колонки явно,
        # поэтому NULL в контракте пришёл бы в INSERT как NULL и overriding default уронил
        # бы вставку (найдено узлом V22 на бинарном макете Test2_ processing). Значение
        # известно точно: содержимого нет — обрезать нечего.
        row["ext_truncated"] = False
        warnings.append(f"Для макета '{name}' нет каталога содержимого Templates/{name}/Ext: "
                        "сохранена только регистрация макета.")
        return {"success": True, "template": row}

    template_xml = _find_file(ext_dir, "Template.xml")
    template_bin = _find_file(ext_dir, "Template.bin")
    if template_xml is not None:
        content, truncated, size = _read_text_file(template_xml)
        if content is None:
            row["ext_truncated"] = False
            warnings.append(f"Содержимое макета '{name}' ({template_xml.name}) не читается: "
                            "колонка templates.ext остаётся пустой.")
        else:
            row["ext"] = content
            row["ext_format"] = "xml"
            row["ext_path"] = _rel_path(template_xml, source_path)
            row["ext_root_tag"] = _root_tag_of(template_xml) or None
            row["ext_size"] = size if size is not None else len(content.encode("utf-8"))
            row["ext_truncated"] = truncated
            if truncated:
                warnings.append(f"Содержимое макета '{name}' длиннее порога {MAX_TEXT_CHARS} "
                                "символов: сохранена часть, ext_truncated = true.")
    elif template_bin is not None:
        data = _read_bytes_file(template_bin)
        row["ext_format"] = "bin"
        row["ext_path"] = _rel_path(template_bin, source_path)
        row["ext_bin"] = data
        row["ext_size"] = len(data) if data is not None else None
        # Дефект, найденный узлом V22 на выгрузке Test2_ processing (макет TSD_M_SEARCH,
        # Template.bin 37 053 байта): колонка ext_truncated NOT NULL DEFAULT FALSE, но
        # TemplateRowWriter перечисляет колонки в INSERT явно, и отсутствие значения в
        # контракте приходило как явный NULL — вставка падала с
        # «null value in column "ext_truncated" … violates not-null constraint», то есть
        # ЛЮБОЙ бинарный макет не загружался ни в отчёте, ни в обработке (у эталонных
        # выгрузок макеты XML, поэтому ветка не проверялась). Бинарь не обрезается —
        # об усечении сообщает именно false.
        row["ext_truncated"] = False
        warnings.append(f"Макет '{name}' выгружен в бинарном виде "
                        f"(Templates/{name}/Ext/Template.bin): содержимое сохранено как есть "
                        "в templates.ext_bin.")
    else:
        row["ext_format"] = "none"
        row["ext_truncated"] = False
        warnings.append(f"В каталоге Templates/{name}/Ext нет ни Template.xml, ни Template.bin: "
                        "содержимое макета не сохранено.")
    return {"success": True, "template": row}


def _read_bsl_modules(base_dir, source_path, parent_uuid, parent_type, object_name, warnings):
    """Модули объекта/менеджера из Ext/*.bsl. Модули ФОРМ здесь не пишутся (form_ext.ext)."""
    ext_dir = _find_dir(base_dir, EXT_DIR_NAME)
    if ext_dir is None:
        return []
    try:
        files = sorted([p for p in ext_dir.glob("*.bsl") if p.is_file()],
                       key=lambda p: p.name.lower())
    except OSError:
        return []
    rows = []
    for bsl_file in files:
        module_type = MODULE_FILE_KINDS.get(bsl_file.name.lower())
        if module_type is None:
            module_type = bsl_file.stem or "Module"
            warnings.append(
                f"Файл {bsl_file.name} в каталоге Ext/ не похож на известный модуль объекта "
                f"(ObjectModule.bsl / ManagerModule.bsl): сохранён как module_type='{module_type}'.")
        code, truncated, size = _read_text_file(bsl_file)
        if code is None:
            warnings.append(f"Модуль {bsl_file.name} не читается: он сохранён не будет.")
            continue
        rows.append({
            "module_name": module_type,
            "file_path": _rel_path(bsl_file, source_path),
            "code": code,
            "object_type": module_type,
            "object_name": object_name or None,
            "parent_uuid": parent_uuid,
            "parent_type": parent_type,
            "module_type": module_type,
            "code_size": len(code),
            "truncated": truncated,
        })
        if truncated:
            warnings.append(f"Модуль {bsl_file.name} длиннее порога {MAX_TEXT_CHARS} символов: "
                            "сохранена часть, truncated = true.")
    return rows


def parse_external_subdirs(base_path, report_uuid, parent_type="external_report",
                          object_name="", refs=None, source_path=None):
    """Разбор каталогов Forms/, Templates/, Ext/ внутри каталога объекта выгрузки.

    Аргументы:
      base_path   - каталог объекта (одноимённый корневому XML выгрузки);
      report_uuid - uuid корневого внешнего объекта; становится parent_uuid дочерних строк;
      parent_type - 'external_report' (для остальных вариантов - после их реализации);
      object_name - имя объекта выгрузки (для bsl_modules.object_name);
      refs        - child_refs корневого XML ({"forms": [...], "templates": [...]}) - только
                    сверка имён: расхождение даёт предупреждение, а не отказ;
      source_path - корень выгрузки для относительных путей file_path / ext_path.

    Возвращает dict с ключами forms / form_ext / templates / bsl_modules / warnings / counts
    либо ошибку вида {"success": False, "error": ..., "hint": ...} (нарушение R3, битый XML).
    Отсутствие каталогов Forms/, Templates/, Ext/ - не ошибка: соответствующие наборы пустые.
    """
    base_dir = Path(base_path)
    refs = refs or {}
    ref_forms = [name for name in (refs.get("forms") or []) if name]
    ref_templates = [name for name in (refs.get("templates") or []) if name]
    warnings = []

    if not base_dir.is_dir():
        # V13: каталога объекта нет - это НЕ ошибка (пустая выгрузка без Forms/,
        # Templates/, Ext/). Дочерних данных нет; если корневой XML что-то объявляет,
        # объяснение уходит в предупреждение, а не в отказ загрузки.
        if ref_forms or ref_templates:
            warnings.append(
                f"Каталог объекта '{base_dir.name}' не найден: формы ({len(ref_forms)}) и "
                f"макеты ({len(ref_templates)}), объявленные в корневом XML, сохранены не будут."
            )
        return {"success": True,
                "forms": [], "form_ext": [], "templates": [], "bsl_modules": [],
                "warnings": warnings,
                "counts": {"forms": 0, "form_ext": 0, "templates": 0, "bsl_modules": 0}}

    forms_dir = _find_dir(base_dir, FORMS_DIR_NAME)
    templates_dir = _find_dir(base_dir, TEMPLATES_DIR_NAME)

    # Сверка с корневым XML: объявленные имена без файла регистрации - предупреждение.
    for name in ref_forms:
        if _find_file(forms_dir, f"{name}.xml") is None:
            warnings.append(f"Форма '{name}' объявлена в корневом XML, но файл "
                            f"Forms/{name}.xml не найден: форма сохранена не будет.")
    for name in ref_templates:
        if _find_file(templates_dir, f"{name}.xml") is None:
            warnings.append(f"Макет '{name}' объявлен в корневом XML, но файл "
                            f"Templates/{name}.xml не найден: макет сохранён не будет.")

    forms, form_ext, templates = [], [], []
    for xml_path in _registration_files(forms_dir):
        parsed = _read_form(xml_path, forms_dir, report_uuid, parent_type, ref_forms,
                            warnings, source_path=source_path)
        if not parsed.get("success"):
            return parsed
        forms.append(parsed["form"])
        if parsed.get("form_ext") is not None:
            form_ext.append(parsed["form_ext"])
    for xml_path in _registration_files(templates_dir):
        parsed = _read_template(xml_path, templates_dir, report_uuid, parent_type,
                                ref_templates, warnings, source_path=source_path)
        if not parsed.get("success"):
            return parsed
        templates.append(parsed["template"])

    bsl_modules = _read_bsl_modules(base_dir, source_path, report_uuid, parent_type,
                                    object_name, warnings)
    result = {
        "success": True,
        "forms": forms,
        "form_ext": form_ext,
        "templates": templates,
        "bsl_modules": bsl_modules,
        "warnings": warnings,
    }
    result["counts"] = {key: len(result[key])
                        for key in ("forms", "form_ext", "templates", "bsl_modules")}
    return result


