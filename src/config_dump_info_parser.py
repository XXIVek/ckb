"""Разбор `ConfigDumpInfo.xml` — индекса состава конфигурации (узел V33).

Зачем отдельный модуль. Каталог выгрузки конфигурации — 158 925 XML (замер BGU2,
17.10.2026): перечислять объекты обходом каталогов долго, а ответ на вопрос
«что вообще есть в конфигурации» нужен сразу после загрузки заголовка. `ConfigDumpInfo.xml`
(16.8 МБ) даёт готовый перечень: 122 164 записи `<Metadata name id>`, из них 67 887
с атрибутом `configVersion`.

Что утверждает замер и что учитывает код (полные замеры — якорь
`configdumpinfo-index-structure` слоя `xml-format` в MCP `1c-knowledge-base`):

* D1. `<Metadata>` лежит на ДВУХ уровнях (замер дерева BGU2, 17.10.2026): у корня ровно
  один элемент — контейнер `<ConfigVersions>` (без атрибутов); его прямые дети — 67 887
  записей `<Metadata>` (среди них 11 703 с двухсегментным именем `Вид.Имя` — верхние
  объекты, остальные глубже); дети этих `<Metadata>` — ещё 54 277 записей (имена из 4 или
  6 сегментов). Обходить только прямых детей контейнера — значит потерять 54 277 записей
  из 122 164 (44 %).
* D2. Атрибут `id` принимает ЧЕТЫРЕ формы: канонический uuid v4 (86 379), составной
  `<uuid>.<число>` (35 713 — нумерованные дочерние: `Catalog.Х.Форма.УстановкиОборотов.Список.1`),
  suffixed `<uuid>.1c` (69 — `…Ссылка.1c`, `Predefined`) и suffixed `<uuid>.<буква>`
  (`.a`/`.b`/`.c` — по одной записи уровня конфигурации: CommandInterface,
  ClientApplicationInterface, MainSectionPicture). Форма связана с уровнем в XML: вложенные
  записи (54 277) — ВСЕГДА канонический uuid; у прямых детей `<ConfigVersions>` — смесь
  (32 102 uuid + 35 785 составных/с суффиксом). Колонка `object_id` — TEXT:
  uuid-колонка три последние формы не хранит, а `uuid` заполняется только у канонических.
  Формы (`id_forms`) и окончания (`id_suffixes`) считаются отдельными счётчиками: список
  окончаний открыт, поэтому дописывать его по одной букве нельзя — «не uuid» считается по
  остатку после канонического значения.
* D3. Иерархия (`parent_name`) берётся из ИМЕНИ по правилу сегментов, а не из вложенности
  XML: вложенность в индексе покрывает не все записи (у прямых детей контейнера дочерние
  элементы лежат и в контейнере, и внутри записи), а имя даёт родителя для 110 461 из 110 461
  некорневых записей (`parent_unresolved` = 0, проверка — `_v33_probe.py`).
  Правило: объект метаданных занимает два сегмента (`Вид.Имя`), каждый следующий уровень —
  ещё два (`Форма.Имя`, `Реквизит.Имя`, …); при нечётном числе сегментов последний сегмент
  сам является именем дочернего элемента (`…Ссылка`). Глубина по имени:
  depth_hist = {0: 11 703, 1: 68 070, 2: 42 307, 3: 78, 4: 6}, `max_depth` = 4.
* D4. Атрибут `configVersion` есть не у всех записей (54 277 без него) — ожидаемое состояние
  индекса, а не дефект разбора: предупреждение отдаётся одно, с агрегатным числом. Значение —
  версия метаданных из 40 шестнадцатеричных символов (замер BGU2: у всех 67 887 заполненных),
  а НЕ идентификатор объекта: для него в таблице отдельная колонка `config_version`, в `uuid`
  оно не кладётся ни при какой форме.
* D5. Имена и идентификаторы в индексе уникальны (замер — 0 дублей). Дубль в присланном
  файле = повреждённый индекс: загрузка отказывает, а не пишет половину.
* D6. Атрибута-отметки `byParent` в индексе НЕТ (0 вхождений на 122 164 записи; счётчик
  неизвестных атрибутов пуст) — прежняя формулировка правила была ошибочной. Признаком
  раскладки служит сам `configVersion`: он стоит ровно на прямых детях `<ConfigVersions>`
  (67 887) и отсутствует у вложенных (54 277). В БД раскладка не пишется (колонки под неё
  нет), но считается счётчиком `by_xml_parent` — он и показывает, где лежали записи, потому
  что на этом держится разбор (D1).

Модуль ничего не знает о PostgreSQL: он отдаёт dict-контракт
`{success, error?, hint?, objects[], counts{}, warnings[], source_file}`. Запись строк —
`src/configuration_loader.py` и `ConfigurationObjectRowWriter` из `src/external_table_writer.py`.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

CONFIG_DUMP_INFO = "ConfigDumpInfo.xml"
ROOT_TAG = "ConfigDumpInfo"
CONFIG_VERSIONS_TAG = "ConfigVersions"
METADATA_TAG = "Metadata"


CATALOG_TO_KIND = {
    # Словарь «каталог выгрузки (множественный) ↔ вид метаданных (сингулярный)».
    # Наивное «снял хвостовой s» не работает: AccountRoles -> AccountSetting,
    # ArrivalPackages -> ArrivalPackageOrdering, RecalculationOfAmounts ->
    # FinancialResultsAndVATRecordingVariants… Словарь построен мажоритарным голосованием
    # по всем именам индекса BGU2 (замер 17.10.2026, tools/_v33_probe_configdumpinfo.py)
    # и сверен с перечнем каталогов выгрузки (якорь configuration-dump-layout-catalogs).
    # Парсер вид метаданных НЕ переименовывает: object_type берётся из имени как есть,
    # иначе строки таблицы разошлись бы с тем, что написано в файле выгрузки.
    "AccountSettings": "AccountSetting",
    "Accounts": "ChartOfAccounts",
    "AccountAnalyses": "AccountType",
    "AccountRoles": "AccountSetting",
    "ArrivalPackages": "ArrivalPackageOrdering",
    "Authorizations": "Authorization",
    "BehaviorTemplates": "BehaviorTemplate",
    "CalculationAdditions": "CalculationAddition",
    "CalculationAdditionsPurposes": "CalculationPurpose",
    "CalculationAdvantages": "CalculationAdvantage",
    "CalculationAdvantagesPurposes": "CalculationPurpose",
    "CalculationBasisActionDirections": "CalculationBasisActionDirection",
    "CalculationBasisActionDirectionsPriority": "CalculationBasisActionDirectionsPriority",
    "CalculationBasisActions": "CalculationBasisAction",
    "CalculationBasisActionSelfDirections": "CalculationBasisActionSelfDirection",
    "CalculationBasisIndicators": "CalculationBasisIndicator",
    "CalculationBasisIndicatorGroups": "CalculationBasisIndicatorGroup",
    "CalculationDirections": "CalculationDirection",
    "CalculationDirectionsPriorities": "CalculationDirectionPriority",
    "CalculationIndicators": "CalculationIndicator",
    "CalculationIndicatorGroups": "CalculationIndicatorGroup",
    "CalculationManager": "CalculationManager",
    "Calculations": "Calculation",
    "CalculationPurposes": "CalculationPurpose",
    "CalculationTechniques": "CalculationTechnique",
    "CalculationVariants": "CalculationVariant",
    "ChartOfCalculationTypes": "ChartOfCalculationTypes",
    "ChartOfComponents": "ChartOfCharacteristicTypes",
    "ChartOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "ChartOfCharacteristicTypesAdditionalAttributePurposes": "AdditionalAttributeReason",
    "ChartOfCharacteristicTypesMainPurposes": "MainFilterPurpose",
    "ChartOfCharacteristicTypesPurposes": "Purpose",
    "ChartOfOrders": "ChartOfOrders",
    "ChartsOfCalculationTypes": "ChartOfCalculationTypes",
    "ChartOfSystems": "ChartOfCalculationTypes",
    "ChartOfUnitCodes": "Unit",
    "ChartOfUnits": "Unit",
    "Committees": "Committee",
    "CommonAttributes": "CommonAttribute",
    "CommonForms": "CommonForm",
    "CommonModules": "CommonModule",
    "CommonModulesOptions": "CommonModuleOption",
    "CommonOwnedRoles": "Role",
    "CommonPictures": "Picture",
    "CommonTemplates": "Template",
    "ConditionalApplication": "ConditionalApplication",
    "ConditionalUserForms": "ConditionalUserForm",
    "ConfigurationDataConsumptionLog": "ConfigurationLogInfo",
    "ConfigurationFolder": "Configuration",
    "ConfigurationFunctions": "ConfigurationFunction",
    "ConfigurationLogs": "ConfigurationLog",
    "ConfigurationReport": "ConfigurationReport",
    "Conjugate": "Conjugate",
    "ConjugateByRecord": "Conjugate",
    "CurrencyConversions": "CurrencyConversion",
    "Currencies": "Currency",
    "CustomDataStores": "CustomDataSource",
    "CustomShortcutGroups": "CustomShortcutGroup",
    "DistranslationCases": "DistranslationCase",
    "DistranslationCasesCases": "DistranslationCase",
    "DistranslationCasesTypes": "DistranslationCaseType",
    "DocumentNumerators": "DocumentNumberRef",
    "DocumentRegistrations": "DocumentRegistration",
    "DocumentTables": "Document",
    "Documents": "Document",
    "Engines": "CalculationProvision",
    "Enums": "Enum",
    "ExchangePlans": "ExchangePlan",
    "ExternalDataProcessors": "ExternalDataProcessor",
    "ExternalReports": "ExternalReport",
    "FilterCriteria": "FilterCriterion",
    "ForeignPlans": "ExternalDataSource",
    "Functions": "Function",
    "Glossary": "Glossary",
    "GlossarySubjects": "GlossarySubject",
    "InformationRecordRegistration": "InformationRecordRegistration",
    "InformationRegisters": "InformationRegister",
    "InternalConjugate": "Conjugate",
    "KeyVLScenarios": "KeyVLScenarios",
    "KMPVariants": "CalculationVariant",
    "KSSets": "KSComposition",
    "LegalNamesKinds": "Contract",
    "ManagedForms": "Form",
    "Mappings": "Mapping",
    "MDO": "CalculationBasisIndicator",
    "MobileFunctions": "MobileApplication",
    "MobileInterfaces": "MobileInterface",
    "MobileSubsystemRoles": "Role",
    "Namespaces": "Namespaces",
    "ObjectServers": "ObjectServer",
    "OtherOptions": "InterfaceContent",
    "PackageForm": "PackageForm",
    "Plotter": "Plotter",
    "PricePurposes": "PricePurpose",
    "PriceTypes": "PriceType",
    "PriorityUse": "PriorityUse",
    "PrivilegedGetters": "PrivilegedGetter",
    "ProgrammersUseOnly": "Namespaces",
    "RecalculationOfAmounts": "FinancialResultsAndVATRecordingVariants",
    "RecalculationOfAmountsPurposes": "CalculationPurpose",
    "Recalculations": "Calculation",
    "RecordRegistration": "InformationRecordRegistration",
    "Registers": "InformationRegister",
    "ReportTables": "Report",
    "Reports": "Report",
    "RestorationDirections": "CalculationDirection",
    "RestorationDirectionsPurposes": "CalculationPurpose",
    "Roles": "Role",
    "RowIDs": "RowIDRef",
    "SeriesOfCalculationTypes": "CalculationType",
    "SettingsStorages": "SettingsStorage",
    "SubsystemFilterCriterion": "FilterCriterion",
    "SubsystemFilterCriteria": "FilterCriterion",
    "Subsystems": "Subsystem",
    "Tables": "Catalog",
    "TaskServicers": "ServiceBehaviorDescription",
    "Template": "Template",
    "ToBeDeleted": "FunctionalOptionsParameter",
    "TransformationOfSets": "CompositionOf",
    "TurnoverDirections": "ChartOfAccounts",
    "UnitByBaseUnits": "Unit",
    "UnitByUnits": "Unit",
    "UnitAdditionalCoefficients": "Unit",
    "UnitParameters": "Unit",
    "UnitTypes": "Unit",
    "Users": "StandardServer",
    "VATRecordPurposes": "CalculationPurpose",
    "VATRecordVariant": "CalculationVariant",
    "VATRecordVariants": "CalculationVariant",
    "VersionsOfDataStorage": "VersionsOfDataStorage",
    "WebServices": "WebService",
    "WebServiceOperationClients": "WebServiceOperationClient",
    "WebServiceOperationServers": "WebServiceOperationServer",
    "XMLPrefixes": "XMLPrefix",
}
"""Справочный словарь видов метаданных (см. комментарий в его теле): он нужен следующему
узлу для сопоставления строк индекса с каталогами выгрузки, а не для переименования имён."""



KNOWN_METADATA_ATTRS = {"name", "id", "version", "configVersion"}
"""Атрибуты `<Metadata>`, которые разбирает парсер. Прочие — сигнал о неизвестной версии
формата: молча отбросить их нельзя, потому что следующий шаг (сверка изменений по
`configVersion`) опирается ровно на них."""

KNOWN_ROOT_CHILDREN = {CONFIG_VERSIONS_TAG, METADATA_TAG}
"""Элементы корня, назначение которых известно по замеру. Неизвестный элемент обязан быть
назван: «в индексе больше ничего нет» без проверки — это утверждение о файле, которого нет."""

MAX_EXAMPLES = 5
"""Сколько примеров печатать в тексте ошибки или предупреждения (полный перечень — в БД)."""

CONFIG_VERSION_HEX_LEN = 40
"""Длина `configVersion` в hex-символах (замер BGU2: 40 у всех 67 887 значений)."""

CONFIG_VERSION_RE = re.compile(r"^[0-9a-fA-F]{40}$")
"""Форма `configVersion`: 40 hex-символов, то есть НЕ uuid с дефисами.

Замер BGU2 (17.10.2026): длина ровно 40 у всех 67 887 заполненных значений; хвост из 8
символов — `00000000`; первые 32 символа не совпадают с `id` объекта ни в одном из
32 102 сравнимых случаев. Поэтому `configVersion` в колонку `uuid` не кладётся никогда:
это отдельный идентификатор состояния объекта, а не его uuid.
"""


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                      r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
COMPOSITE_ID_RE = re.compile(r"^(?:[0-9a-fA-F-]{36})\.\d+$")
SUFFIXED_ID_RE = re.compile(r"^(?:[0-9a-fA-F-]{36})\.(?!\d+$).+$")
_SUFFIX_AFTER_UUID_RE = re.compile(r"^(?:[0-9a-fA-F-]{36})\.(?P<suffix>[^.]*)$")



def id_form(object_id):
    """Вернуть форму идентификатора: `uuid` | `composite` | `suffixed` | `other`.

    Формы — факт индекса (правило D2), а не случайные данные: от формы зависит, заполнять
    ли колонку `uuid`. Проверка каноничности строгая: неляпота в uuid-колонке прилетела бы
    ошибкой вставки на 122 тысячах строк.
    """
    text = str(object_id or "").strip()
    if _UUID_RE.match(text):
        return "uuid"
    if COMPOSITE_ID_RE.match(text):
        return "composite"
    if SUFFIXED_ID_RE.match(text):
        return "suffixed"
    return "other"


def id_suffix(object_id):
    """Служебная часть составного идентификатора: `N` для чисел, иначе сам суффикс.

    Нужна только для честного ответа «какие суффиксы встречаются»: в BGU2 это числа
    (35 713), `1c` (69) и одиночные буквы `a`/`b`/`c` (3 записи уровня конфигурации —
    ClientApplicationInterface, CommandInterface, MainSectionPicture). Числа сворачиваются
    в `N`, иначе перечень суффиксов вырастет до десятков тысяч строк.
    """
    text = str(object_id or "").strip()
    match = _SUFFIX_AFTER_UUID_RE.match(text)
    if not match:
        return None
    suffix = match.group("suffix")
    return "N" if suffix.isdigit() else suffix



def split_name(name):
    """Разобрать имя записи индекса на (вид, имя объекта, вид дочернего, родитель, глубина).

    Возвращает None, если сегментов меньше двух: имя без вида метаданных нельзя разложить,
    не придумав значение, поэтому вызывающий обязан отказать, а не догадываться.
    Правило D3 проверено на всех 122 164 записях BGU2: родитель существует в том же
    индексе для 110 461 из 110 461 некорневых записей (пропуск — 0).
    """
    parts = str(name).split(".")
    if len(parts) < 2:
        return None
    object_type, object_name = parts[0], parts[1]
    if len(parts) == 2:
        return {"object_type": object_type, "object_name": object_name,
                "child_type": None, "parent_name": None, "depth": 0}
    if len(parts) % 2 == 0:
        return {"object_type": object_type, "object_name": object_name,
                "child_type": parts[-2], "parent_name": ".".join(parts[:-2]),
                "depth": len(parts) // 2 - 1}
    return {"object_type": object_type, "object_name": object_name,
            "child_type": parts[-1], "parent_name": ".".join(parts[:-1]),
            "depth": (len(parts) - 1) // 2}



def _local_name(element) -> str:
    """Локальное имя элемента без префикса пространства имён."""
    return str(element.tag).rsplit("}", 1)[-1]


def _fail(error, hint=None):
    result = {"success": False, "error": error, "objects": [], "counts": {}, "warnings": []}
    if hint:
        result["hint"] = hint
    return result


def find_config_dump_info(source_dir):
    """Найти `ConfigDumpInfo.xml` в КОРНЕ каталога выгрузки конфигурации.

    Тот же контракт R1, что и при выборе варианта загрузки: смотрим только корневой
    каталог, без рекурсии в подкаталоги. Возвращает Path или None.
    """
    candidate = Path(source_dir) / CONFIG_DUMP_INFO
    return candidate if candidate.is_file() else None


def _examples(values, limit=MAX_EXAMPLES):
    """Сжатый перечень примеров для текста ошибки или предупреждения."""
    values = list(values)
    shown = ", ".join(str(value) for value in values[:limit])
    if len(values) > limit:
        shown += f", … (ещё {len(values) - limit})"
    return shown



def parse_config_dump_info(path):
    """Разобрать `ConfigDumpInfo.xml` в контракт строк `configuration_objects`.

    Контракт: {success, error?, objects[], counts{}, warnings[], source_file}.
    Отказ (success=False) — только когда индекс нельзя прочитать без выдумки: нет файла,
    битый XML, чужой корневой элемент, пустой индекс, пустой name/id, имя без вида
    метаданных, дубль name или id. Всё остальное (нет `configVersion`, неканонический id,
    неизвестный атрибут, несуществующий родитель) — предупреждение с агрегатным числом:
    это состояние файла, а не ошибка разбора.

    Порядок строк — документный (он же иерархический), `id` выдаёт bigserial.
    Родитель (`parent_name`) считается по имени (правило D3); если родителя в индексе нет,
    поле остаётся NULL, а случай попадает в `counts.parent_unresolved` и в предупреждение:
    висячий `parent_name` сломал бы инвариант «несиротских родителей = 0».
    """
    xml_path = Path(path)
    if not xml_path.is_file():
        return _fail(f"Файл индекса состава не найден: {xml_path}",
                     hint=f"Ожидается {CONFIG_DUMP_INFO} в корне каталога выгрузки конфигурации.")
    try:
        tree = ET.parse(str(xml_path))
    except ET.ParseError as exc:
        return _fail(f"{xml_path.name} не разбирается как XML: {exc}")

    root = tree.getroot()
    if _local_name(root) != ROOT_TAG:
        return _fail(
            f"Корневой элемент {xml_path.name} — <{_local_name(root)}>, ожидался <{ROOT_TAG}>: "
            "это не индекс состава конфигурации."
        )

    counts = {
        "entries_total": 0, "metadata_direct": 0, "metadata_nested": 0,
        "root_entries": 0, "child_entries": 0, "max_depth": 0, "depth_hist": {},
        "types": {}, "id_forms": {}, "id_suffixes": {}, "by_xml_parent": {},
        "config_versions": 0, "config_versions_missing": 0,
        "config_versions_bad_form": 0, "parent_unresolved": 0,
        "unknown_attributes": {}, "unknown_elements": {},
    }
    warnings = []
    errors = []
    entries = []
    seen_names, seen_ids = {}, {}
    duplicate_names, duplicate_ids = [], []

    def consume(element, parent_tag):
        # parent_tag — локальное имя родителя в XML. Это НЕ иерархия объектов (её даёт имя,
        # правило D3): счётчик нужен, чтобы видеть раскладку самого индекса — в BGU2 у корня
        # ровно один контейнер <ConfigVersions>, и `<Metadata>` лежат в двух местах: прямые
        # дети контейнера (все с configVersion) и дети <Metadata> (все без configVersion).
        nested = parent_tag == METADATA_TAG
        counts["metadata_nested" if nested else "metadata_direct"] += 1

        attrs = element.attrib
        for attr in attrs:
            if attr not in KNOWN_METADATA_ATTRS:
                counts["unknown_attributes"][attr] = counts["unknown_attributes"].get(attr, 0) + 1

        name = str(attrs.get("name") or "").strip()
        object_id = str(attrs.get("id") or "").strip()
        config_version = str(attrs.get("configVersion") or "").strip() or None
        if not name:
            errors.append(f"запись индекса с пустым name (id={object_id or 'тоже пуст'})")
            return
        if not object_id:
            errors.append(f"запись `{name}` с пустым id")
            return
        if name in seen_names:
            duplicate_names.append(name)
        else:
            seen_names[name] = object_id
        if object_id in seen_ids:
            duplicate_ids.append(f"{name} / {object_id}")
        else:
            seen_ids[object_id] = name

        parts = split_name(name)
        if parts is None:
            errors.append(f"имя `{name}` без вида метаданных (нет второй части)")
            return

        counts["entries_total"] += 1
        counts["root_entries" if parts["depth"] == 0 else "child_entries"] += 1
        counts["max_depth"] = max(counts["max_depth"], parts["depth"])
        counts["depth_hist"][parts["depth"]] = counts["depth_hist"].get(parts["depth"], 0) + 1
        counts["types"][parts["object_type"]] = counts["types"].get(parts["object_type"], 0) + 1

        form = id_form(object_id)
        counts["id_forms"][form] = counts["id_forms"].get(form, 0) + 1
        suffix = id_suffix(object_id)
        if suffix is not None:
            counts["id_suffixes"][suffix] = counts["id_suffixes"].get(suffix, 0) + 1

        xml_parent = parent_tag or "(root)"
        by_xml_parent = counts["by_xml_parent"].setdefault(
            xml_parent, {"total": 0, "with_config_version": 0, "without_config_version": 0})
        by_xml_parent["total"] += 1

        if config_version is None:
            counts["config_versions_missing"] += 1
            by_xml_parent["without_config_version"] += 1
        else:
            counts["config_versions"] += 1
            by_xml_parent["with_config_version"] += 1
            if not CONFIG_VERSION_RE.match(config_version):
                counts["config_versions_bad_form"] += 1

        entries.append({**parts, "name": name, "object_id": object_id,
                        "uuid": object_id if form == "uuid" else None,
                        "config_version": config_version})

    def walk(element, parent_tag):
        # Плоский обход всего дерева: `<Metadata>` в BGU2 лежат и внутри контейнера
        # <ConfigVersions>, и внутри <Metadata> (правило D1). Игнорировать второй уровень —
        # значит потерять 54 277 записей из 122 164.
        for child in element:
            tag = _local_name(child)
            if parent_tag is None and tag not in KNOWN_ROOT_CHILDREN:
                counts["unknown_elements"][tag] = counts["unknown_elements"].get(tag, 0) + 1
            if tag == METADATA_TAG:
                consume(child, parent_tag)
            walk(child, tag)

    walk(root, None)

    if errors:
        return _fail(
            f"{xml_path.name}: неразрешимых записей {len(errors)}: {_examples(errors)}. "
            "Индекс загружается целиком либо не загружается вовсе.",
            hint="Проверьте файл: это не тот индекс, который отдаёт выгрузка конфигурации.",
        )
    if not entries:
        return _fail(f"{xml_path.name}: ни одной записи <{METADATA_TAG}> — индекс пуст, "
                     "записывать в configuration_objects нечего.")
    if duplicate_names:
        return _fail(
            f"{xml_path.name}: дублирующиеся имена ({len(duplicate_names)}): "
            f"{_examples(duplicate_names)}. Имя записи уникально в пределах конфигурации "
            "(configuration_objects_name_unique), поэтому индекс принят не будет.",
            hint="Дубль имени — повреждённый или правленный вручную индекс состава.",
        )
    if duplicate_ids:
        return _fail(
            f"{xml_path.name}: дублирующиеся идентификаторы ({len(duplicate_ids)}): "
            f"{_examples(duplicate_ids)}.",
            hint="Один и тот же id у двух имён — индекс состава не загружается.",
        )


    names = set(seen_names)
    for entry in entries:
        parent = entry["parent_name"]
        if parent is not None and parent not in names:
            counts["parent_unresolved"] += 1
            entry["parent_name"] = None
            if counts["parent_unresolved"] <= MAX_EXAMPLES:
                warnings.append(
                    f"родитель `{parent}` записи `{entry['name']}` отсутствует в индексе — "
                    "parent_name оставлен NULL"
                )

    if counts["config_versions_missing"]:
        warnings.append(
            f"`configVersion` отсутствует у {counts['config_versions_missing']} из "
            f"{counts['entries_total']} записей — ожидаемое состояние индекса; сверку изменений "
            "можно строить только по заполненной части"
        )
    if counts["config_versions_bad_form"]:
        warnings.append(
            f"`configVersion` не шестнадцатеричной формы (ожидаемая — {CONFIG_VERSION_LEN} "
            f"символов) у {counts['config_versions_bad_form']} записей. Значение версии метаданных "
            "не является идентификатором объекта и в `uuid` не кладётся ни при какой форме"
        )
    non_uuid = counts["entries_total"] - counts["id_forms"].get("uuid", 0)
    if non_uuid:
        suffixes = ", ".join(
            f"`{suffix}` — {count}" for suffix, count in sorted(counts["id_suffixes"].items())
        )
        warnings.append(
            f"идентификаторы неканонические у {non_uuid} записей (формы: {counts['id_forms']}; "
            f"окончания идентификаторов: {suffixes}) — `object_id` хранит их текстом, `uuid` "
            "заполнен только у канонических UUID v4"
        )
    if counts["by_xml_parent"]:
        # Раскладка файла описывается реальными тегами-родителями, а не выдуманным
        # атрибутом: замер BGU2 (17.10.2026) — атрибута `byParent` в индексе нет вовсе
        # (0 вхождений на 122 164 записи), признак изменения — сам `configVersion`.
        layout = ", ".join(
            f"дети <{tag}> — {info['total']} (с `configVersion`: {info['with_config_version']}, "
            f"без: {info['without_config_version']})"
            for tag, info in sorted(counts["by_xml_parent"].items())
        )
        warnings.append(
            f"раскладка индекса: {layout}. `<{METADATA_TAG}>` лежит на двух уровнях (правило D1), "
            f"вложенных — {counts['metadata_nested']} из {counts['entries_total']}; вложенность "
            "состава не даёт (признаком изменения служит `configVersion`), поэтому `parent_name` "
            "восстановлен из имени записи (правило D3), а не из вложенности XML"
        )
    if counts["unknown_attributes"]:
        warnings.append(
            "неизвестные атрибуты <Metadata>: "
            + ", ".join(f"{name} ({count})" for name, count in counts["unknown_attributes"].items())
            + " — формат индекса новее разбираемого, значения отброшены"
        )
    if counts["unknown_elements"]:
        warnings.append(
            "неизвестные элементы корня: "
            + ", ".join(f"<{name}> ({count})" for name, count in counts["unknown_elements"].items())
        )
    if counts["metadata_nested"]:
        warnings.append(
            f"вложенных <{METADATA_TAG}> {counts['metadata_nested']} из {counts['entries_total']}: "
            "иерархия взята из имени записи, а не из вложенности XML (правило D3)"
        )

    return {
        "success": True,
        "source_file": str(xml_path),
        "objects": entries,
        "counts": counts,
        "warnings": warnings,
    }
