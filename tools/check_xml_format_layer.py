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

Слои (LAYERS, 16): профиль свойств ExternalDataProcessor; профиль свойств Configuration.xml
(55 свойств корня конфигурации: что маппится в configurations, что без колонки, а что не
заполняется осознанно — узлы V32/V33, замер MinCfg 19.10.2026); карточки отдельных свойств
корня (DefaultRunMode и др.); общие свойства Name / Synonym / Comment; профиль идентификаторов
ClassId/ObjectId/TypeId/ValueId; три слоя структуры выгрузки конфигурации (состав каталогов
видов метаданных, индекс ConfigDumpInfo.xml, расположение uuid объекта конфигурации); и слой
представления (Представление) — четыре карточки: файлы Ext/ (HomePageWorkArea, CommandInterface,
Logo, Splash, Help…, точный состав каталога по 8 выгрузкам и формат картинок), свойства
представления в корне <Properties> (WindowMode, Style, Language, Info, Copyright, Addresses),
основные формы конфигурации (DefaultReportForm … DefaultCollaborationSystemUsersChoiceForm,
полный измеренный перечень свойств Default*) и отдельная карточка макета оформления отчётов
(configuration-report-appearance-template: предопределённые макеты платформы против общих
макетов конфигурации с TemplateType=DataCompositionAppearanceTemplate, содержимое
AppearanceTemplate со ссылками на стили вместо RGB) — замер 8 XML-выгрузок, 20.10.2026.
Всё это категории xml-format; профиль версий UUID — категории platform (его сниппет намеренно
размечен и xml-format, поэтому xml-format у него в «чужих» категориях не проверяется).

Профиль свойств Configuration.xml заведён отдельно от профиля ExternalDataProcessor, хотя
маркеры формата строк у них общие: у профиля конфигурации значимы счётчики `found=/mapped=`
и раздел ROOT_EXT_MODULES (модули предопределённых программ находятся только как файлы Ext/,
соответствующие им колонки конфигурации загрузчик не заполняет) — без этих маркеров профиль
смыкался бы с профилем внешнего объекта и перестал бы отвечать на вопрос «что теряется».
С узла V39 (21.10.2026) к маркерам профиля добавлены раздел достижимости `===REACHABILITY===`
и значение провенанса `dump8`: профиль обязан различать описание свойства в XML и то, доходит
ли значение до колонки (шесть многоязычных свойств корня с V39 пишутся jsonb-словарём, а не
теряются).

Карточки представления заведены тремя строками, а не одной, потому что у них разные источники
истины: «рабочая область», «интерфейс команд», «логотип», «заставка» в <Properties> не лежат
вовсе — это файлы Ext/; свойства представления корня маппятся в колонки configurations лишь
частично; основные формы — это ссылки на форму и макет метаданных. Различие `DefaultReportForm`
(значение по умолчанию на уровне конфигурации) и `DefaultForm` (своя форма конкретного отчёта)
названо в тексте прямо: без него ответ «какая форма у отчёта» собирался бы неверно.

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
        # Маркеры V39 (раздел достижимости, provenance dump8) в ЭТОЙ записи не ставят: якорь
        # профиля разрешается тремя строками (5917 профиль + объединённые карточки модулей
        # 5927 и хранилищ 5928), а проверка маркеров обязана пройти в каждой из них — у
        # карточек модулей и хранилищ раздела достижимости нет и быть не должно. Раздел
        # достижимости сторожит отдельная запись со своим уникальным якорем (см. ниже):
        # один алиас не может служить якорем двух слоёв.
        "name": "профиль свойств Configuration.xml (заголовок конфигурации)",
        "anchor": "property-profile-configuration",
        "category": "xml-format",
        "markers": ("===PROPERTY_PROFILE", "path|kind|required|default|allowed|provenance",
                    "===MAPPING_SUMMARY", "found=55 mapped=22", "===ROOT_EXT_MODULES"),
        "terms": ["ConfigurationExtensionCompatibilityMode", "MainClientApplicationWindowMode",
                  "ObjectAutonumerationMode", "DatabaseTablespacesUseMode",
                  "configurations.short_info", "configurations.vendor_url"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Раздел достижимости профиля (узел V39, 21.10.2026): профиль обязан различать
        # «свойство описано в XML» и «значение дошло до колонки». Шесть многоязычных свойств
        # корня (BriefInformation, DetailedInformation, Copyright, VendorInformationAddress,
        # ConfigurationInformationAddress, Synonym) с V39 пишутся jsonb-словарём и доходят до
        # колонок; до V39 пять из них терялись на разборе (вид "text" вместо составного
        # <v8:item><v8:content/>). Маркеры называют именно исправление: имя разбора
        # _multilang_value и имя миграции, — поэтому карточка не может снова застыть в
        # описании дефекта как в факте. Запись заведена ОТДЕЛЬНО от профиля: якорь профиля
        # разрешается и объединёнными карточками 5927/5928, у которых раздела достижимости
        # нет, а якорь обязан быть уникальным для слоя (правило «один алиас — один слой»).
        "name": "раздел достижимости профиля (что из XML доходит до колонок, узел V39)",
        "anchor": "configuration-reachability-section",
        "category": "xml-format",
        "markers": ("===REACHABILITY===", "dump8", "_multilang_value",
                    "migrate_v39_multilang_configuration_text.sql"),
        "terms": ["достижимость свойств конфигурации", "что доходит до колонки",
                  "configuration-reachability-section"],
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
    {
        # Карточка ОБЩИХ свойств: Name/Synonym/Comment есть в <Properties> и у конфигурации,
        # и у любого объекта метаданных — поэтому одна карточка на тройку (решение оператора
        # 20.10.2026). Маркеры берут ограничения и правила, а не общие слова: потеря
        # границы длины имени (80), правила "синоним не задан - используется имя" или
        # маршрута synonym в БД роняет проверку. С узла V39 (21.10.2026) маршрут у
        # Synonym один — JSONB и у конфигурации, и у внешнего объекта; маркер называет
        # именно это состояние, а карточка обязана хранить и историю (до V39 у
        # конфигурации был TEXT), и границу: config_extensions.synonym остаётся TEXT,
        # потому что загрузчика расширений нет (правило R7).
        "name": "карточка общих свойств Name/Synonym/Comment (конфигурация и любой объект)",
        "anchor": "property-common-name-synonym-comment",
        "category": "xml-format",
        "markers": ("===PROPERTY_CARD", "xml=Name,Synonym,Comment",
                    "НЕ БОЛЕЕ 80 СИМВОЛОВ", "ЕСЛИ СИНОНИМ НЕ ЗАДАН — ИСПОЛЬЗУЕТСЯ ИМЯ",
                    "configurations.synonym — колонка JSONB",
                    "config_extensions.synonym остаётся TEXT"),
        "terms": ["Name", "Synonym", "Comment", "синоним объекта", "80 символов",
                  "configurations.name", "configurations.synonym",
                  "представление объекта конфигурации"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    # --- группа «Представление» (замер 8 выгрузок, 20.10.2026) ------------------------------
    # Разделение на три слоя — не прихоть, а следствие замера: у настроек представления РАЗНЫЕ
    # способы хранения. Пункты «рабочая область», «командный интерфейс раздела», «картинка
    # раздела», «интерфейс клиентского приложения», логотип и заставка вообще не лежат в
    # <Properties> — это файлы каталога Ext/ у корня выгрузки, поэтому карточка свойства о них
    # соврала бы («свойства нет»), а карточка файлов называет ещё и границу «файла нет ≠
    # настройки нет». Маркеры — замерные имена файлов и корневые теги: они отличают слой от
    # любой другой строки категории xml-format.
    {
        "name": "файлы Ext/ представления конфигурации (рабочая область, командный интерфейс, картинки)",
        "anchor": "configuration-ext-presentation-files",
        "category": "xml-format",
        # Маркеры дополнены замером 20.10.2026 (20.10.2026, список каталога Ext/ по 8 выгрузкам):
        # точный состав каталога, правило «пяти файлов управляемого интерфейса нет у конфигурации
        # на обычных формах» (KomMag) и файлы Ext/, к представлению НЕ относящиеся
        # (MobileClientSignature.bin, StandaloneConfigurationContent.bin). Без них карточка
        # читалась бы как «в Ext/ лежат только настройки вида».
        "markers": ("===PRESENTATION_EXT_LAYER", "HomePageWorkArea.xml",
                    "MainSectionCommandInterface.xml", "ClientApplicationInterface.xml",
                    "ExtPicture", "TwoColumnsVariableWidth",
                    "точный состав файлов Ext/", "OrdinaryApplication",
                    "MobileClientSignature.bin", "StandaloneConfigurationContent.bin",
                    "Picture.jpg", "Picture.svg"),
        "terms": ["HomePageWorkArea", "MainSectionPicture", "ClientApplicationInterface",
                  "Splash.xml", "рабочая область начальной страницы",
                  "картинка основного раздела", "Logo.xml", "Picture.jpg",
                  "MobileClientSignature.bin", "StandaloneConfigurationContent.bin"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Свойства корня из той же группы: здесь хранение обычное (<Properties>), поэтому
        # карточка свойств уместна. Маркеры держат два опровергнутых значения — подмена
        # словаря значений (Maximized) или префикса ссылки (OtherConfiguration) роняет проверку.
        "name": "карточка свойств представления корня (режим окна, стиль, язык, адреса)",
        "anchor": "property-configuration-presentation-root",
        "category": "xml-format",
        "markers": ("===PROPERTY_CARD", "MainClientApplicationWindowMode", "FullscreenWorkplace",
                    "Kiosk", "configurations.short_info"),
        "terms": ["MainClientApplicationWindowMode", "DefaultStyle", "BriefInformation",
                  "VendorInformationAddress", "Киоск",
                  "режим основного окна клиентского приложения"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Подгруппа основных форм: значение — квалифицированное имя, а не uuid. Маркер
        # MainDataCompositionSchema обязателен: он доказывает, что карточка различает свойства
        # конфигурации и свойства самого отчёта (иначе «Основная форма отчета» читалась бы как
        # форма конкретного отчёта).
        "name": "карточка основных форм конфигурации и макета оформления отчёта",
        "anchor": "property-configuration-default-forms",
        "category": "xml-format",
        "markers": ("===PROPERTY_CARD", "DefaultReportForm", "CommonForm.ФормаНастроекОтчета",
                    "DefaultReportAppearanceTemplate", "MainDataCompositionSchema"),
        "terms": ["DefaultReportVariantForm", "DefaultDataHistoryVersionDifferencesForm",
                  "DefaultReportAppearanceTemplate", "основной макет оформления отчета",
                  "макет оформления отчета"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Пункт 23 («Основной макет оформления отчета») — отдельная карточка, а не строка
        # карточки основных форм. Причина: у макета оформления свой способ идентификации
        # (признак TemplateType в ФАЙЛЕ РЕГИСТРАЦИИ, а не корневой тег содержимого) и свой
        # источник перечня — предопределённые макеты ПЛАТФОРМЫ плюс общие макеты конфигурации
        # (методичка i8101592; в базе — строки 5939-5942). Прежняя формулировка «это список
        # макетов конкретной конфигурации» была ошибкой и её возврат обязан ронять проверку,
        # поэтому маркеры держат измеренное: тип AppearanceTemplateArea и ссылку на стиль
        # (style:FormTextColor) вместо литерального RGB — именно это объясняет «меняется
        # цветовая гамма», и перечень предопределённых макетов платформы.
        "name": "карточка макета оформления отчёта (пункт 23, AppearanceTemplate)",
        "anchor": "configuration-report-appearance-template",
        "category": "xml-format",
        "markers": ("===APPEARANCE_TEMPLATE_CARD", "DataCompositionAppearanceTemplate",
                    "AppearanceTemplateArea", "style:FormTextColor", "Арктика",
                    "БиблиотекаМакетовОформленияКомпоновкиДанных"),
        "terms": ["DataCompositionAppearanceTemplate", "Арктика",
                  "библиотека макетов оформления компоновки данных",
                  "макет оформления компоновки данных", "основной макет оформления отчета",
                  "item 23"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    # --- категории свойств конфигурации В (Разработка), Г (Справочная информация),
    # --- Д (Совместимость) — замер 8 XML-выгрузок, 20.10.2026 -------------------------
    # Маркеры держат измеренные значения и измеренные границы, а не общие слова: подмена
    # замера (возврат формы «downloads.v8.1c.furtmplts», утверждение «значение теряется» там,
    # где оно доходит, или наоборот) роняет проверку. Карточка В обязана называть и дефект V32
    # (BriefInformation/DetailedInformation/Copyright/адресы заполнены в XML, но не доходили
    # до колонок, потому что разбор ждал скалярный текст, а значение многоязычное), и его
    # снятие узлом V39 (21.10.2026): шесть свойств корня пишутся jsonb-словарём. Маркеры
    # называют именно механизм исправления — имя разбора `_multilang_value` и имя миграции
    # `migrate_v39_multilang_configuration_text.sql`: карточка не может снова застыть в
    # описании дефекта как в факте, и не может объявить исправление без ссылки на код,
    # который его делает. Граница (UpdateCatalogAddress остаётся TEXT) в тексте карточки есть,
    # но маркером не проверяется: её формулировка меняется вместе с формулировкой колонки.
    {
        "name": "карточка категории «Разработка» (Vendor, Version, UpdateCatalogAddress)",
        "anchor": "property-configuration-development",
        "category": "xml-format",
        "markers": ("===PROPERTY_CARD", "configurations.vendor_name",
                    "downloads.v8.1c.ru/tmplts/", "Показать информацию о программе",
                    "дефект загрузчика V32", "_multilang_value",
                    "migrate_v39_multilang_configuration_text.sql", "jsonb"),
        "terms": ["Vendor", "UpdateCatalogAddress", "Поставщик конфигурации",
                  "Адрес каталога обновлений", "каталог обновлений"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Отдельная карточка, а не строка карточки В: у пункта Г.2 XML-представления нет
        # вовсе (замер 55 имён свойств корня идентичен во всех восьми выгрузках), и это
        # утверждение обязано сохраняться — маркер «СВОЙСТВА С ТАКИМ ИМЕНЕМ … НЕТ».
        # Второй маркер — измеренное значение по умолчанию новой конфигурации 8.3.27.
        "name": "карточка категории «Справочная информация» (IncludeHelpInContents + Г.2)",
        "anchor": "property-configuration-help-contents",
        "category": "xml-format",
        "markers": ("===PROPERTY_CARD", "configurations.help_included",
                    "СВОЙСТВА С ТАКИМ ИМЕНЕМ В Configuration.xml НЕТ", "55 имён"),
        "terms": ["IncludeHelpInContents", "help_included", "Включать в содержание справки",
                  "справочная информация конфигурации"],
        "foreign": FOREIGN_BASE + ["platform"],
    },
    {
        # Категория «Совместимость»: карточка держит измеренные токены перечислений
        # (NotAutoFree, TaxiEnableVersion8_2, Version8_3_27), измеренные значения по умолчанию
        # новой конфигурации 8.3.27 и названную слепую зону ObjectAutonumerationMode (колонки
        # нет). Возврат выдуманных токенов (Version8_2 как измеренный) или молчание о слепой
        # зоне роняют проверку.
        "name": "карточка категории «Совместимость» (Д.1-Д.6, режимы и токены перечислений)",
        "anchor": "property-configuration-compatibility",
        "category": "xml-format",
        "markers": ("===PROPERTY_CARD", "configurations.lock_mode_default",
                    "ObjectAutonumerationMode", "КОЛОНКИ НЕТ", "EnableCheckModal"),
        "terms": ["DataLockControlMode", "ObjectAutonumerationMode",
                  "InterfaceCompatibilityMode", "NotAutoFree",
                  "режим совместимости интерфейса", "EnableCheckModal"],
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

    get_cursor — единственный канал доступа к пулу (соединение он возвращает в пул сам,
    src/database.py:65-92); conn.close() соединение из пула не возвращает, а закрывал бы.
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
