> дамп правил · вариант 1 (только правила) — текст правил всех уровней; журналов, проверок и перечней ссылок нет · запрос `rules:enrich-rules:` · выбор: алиас rules:enrich-rules: · карточек: 1 · 26.10.2026 09:08
> правки делаются строками БД; файл показывает текущее состояние целиком, а не эталон
> не входят: перечни ссылок (`===LINKS`, `===INDEX`) — вариант 2; журнал (0) и проверки (0) — варианты 5 и 6

---

## rules:enrich-rules:

===SUMMARY
Первая карточка слоя правил MCP `1c-configurations-enrichment` — уровень 2 дерева правил. Она говорит, что это за сервер и
как устроены правила его слоя; сами правила лежат следующим уровнем.

Сегодня правила слоя записаны под прежним адресом `enrich-rules:<...>` — слой ещё не переразвёрнут в
дерево `rules:enrich-rules:<правило>`. Поэтому перечень `===LINKS` ниже ведёт именно туда, а
подсказка «когда нужен» взята из раздела `===WHEN` самой карточки. Когда слой переразвёрнут,
ссылки переставляются на адреса дерева в тот же момент, когда меняется строка БД.

Раздел `===MCP` — общие записи слоя, перенесённые из корневой карточки без правок текста. Их разбор
по отдельным правилам и частям `ref:NNN` — отдельный шаг.

===MCP
### 🔄 Шаг 3: Анализ и обогащение объектов выгрузки (MCP `1c-configurations-enrichment`)

**Когда использовать:** посмотреть, что представляет собой загруженный внешний отчёт и что делает его
код; найти объект по русскому синониму, имени реквизита, элемента формы, имени процедуры; создать
или снять алиас/сниппет/ссылку на документацию. Полные правила —
`.clinerules/1c-configurations-enrichment_Rule.md` (контракт — 21 инструмент).

| Сценарий | Инструмент | Описание |
|----------|-----------|----------|
| **Карточка объекта:** | | |
| Свойства, состав, что делает код | `config_enrichment_stats_tool(uuid?, limit=20, card=True)` | без `uuid` — сводка по всем объектам (в т. ч. раздел «ПРИВЯЗКИ К КОНФИГУРАЦИИ»: заголовки и число привязанных объектов, счётчики состояний); с `uuid` — карточка: свойства, синоним, реквизиты с типами, ТЧ, формы и их состав, макеты, модули, сниппеты, состояние привязки |
| **Привязка к конфигурации (узлы V20/V20.1):** | | |
| Заявить или снять привязку | `set_object_configuration_tool(uuid?, source_path?, configuration_id?)` | `configuration_id` — id строки заголовка `configurations.id` (НЕ uuid метаданных 1С); `None` — снять; несуществующий или нечисловой id отклоняется, привязка не меняется; возвращает «было/стало», имя и версию заголовка и число привязанных объектов |
| **Состав макета-СКД (узел B):** | | |
| Состав конкретного макета | `get_config_template_tool(uuid?, source_path?, name?, template_id?, include_query=True)` | наборы данных и их поля, связи, параметры, вычисляемые поля, итоги, варианты настроек и вывод — из сохранённого `templates.ext`; текст запроса набора отдаётся по умолчанию (`include_query=True`) и усекается до `MAX_ANSWER` = 8000 символов; карточка объекта (`card=True`) отдаёт тот же состав и счётчики `dcs_*` |

| **Генерация:** | | |
| Пересобрать алиасы и сниппеты | `generate_config_enrichment_tool(uuid?, source_path?)` | источник — сохранённое содержимое БД, конфигуратор не открывается |
| **Алиасы:** | | |
| Найти алиас по началу/середине | `search_config_aliases_tool(query, uuid?, target_type?, limit?)` | так работает поиск по алиасам |
| Разрешить алиас точно | `resolve_config_alias_tool(alias)` | отдаёт цели (объект, реквизит, форма, элемент, макет, модуль, сниппет) |
| Список алиасов объекта | `list_config_aliases_tool(uuid?, target_type?, origin?, limit?, include_inactive?)` | `origin`: `generated` / `manual` |
| Добавить ручной алиас | `add_config_aliases_tool(aliases, uuid?, source_path?, target_type?, target_name?, ...)` | там, где термина нет в выгрузке (русские формулировки, аббревиатуры) |
| Снять алиас | `delete_config_alias_tool(alias_id, hard=False)` | по умолчанию мягкое снятие (`active=false`) |
| **Сниппеты:** | | |
| Полный код + зависимости + алиасы | `get_config_snippet_tool(snippet_id)` | карточка сниппета |
| Список сниппетов (без кода целиком) | `list_config_snippets_tool(uuid?, source_kind?, limit?, only_verified?, include_marked=False)` | код бывает десятки КБ; помеченные к удалению скрыты по умолчанию |
| Полнотекстовый поиск по сниппетам | `search_config_snippets_tool(query, uuid?, limit?, include_marked=False)` | ищет и вопрос, и код; карантин скрыт по умолчанию, по `include_marked=True` отдаётся с явной пометкой и в конце выдачи |
| Что известно про конкретную цель | `get_config_snippets_for_object_tool(uuid?, source_path?, target_type, target_name, include_marked=False)` | перед тем, как писать новый сниппет |
| Добавить ручной сниппет | `add_config_snippet_tool(question, answer, uuid?, source_path?, dependencies?, ...)` | `is_verified=true`, обязан сослаться на сохранённую цель |
| Удалить сниппет | `delete_config_snippet_tool(snippet_id)` | снимает и его алиасы, зависимости, ссылки |
| **Карантин сниппетов (узел Q1, 16.10.2026)** | | |
| Пометить ошибочный сниппет на удаление | `mark_config_snippet_tool(snippet_id, reason?)` | строка остаётся в БД, выдача её не отдаёт; причина — второй тег `mark-for-deletion:reason=…` |
| Снять пометку | `unmark_config_snippet_tool(snippet_id)` | возвращает строку в поиск, списки и карточку объекта |
| Разобрать карантин перед чисткой | `list_marked_config_snippets_tool(uuid?, limit=50)` | id, объект, вопрос, источник, `is_verified`, причина; физически снимает только `tools/purge_marked_snippets.py` (`--dry-run` по умолчанию) |
| **Связи с документацией:** | | |
| Поставить указатель `local_doc` → цель | `add_config_cross_reference_tool(uuid?, local_doc_kind, local_doc_id, target_type?, ...)` | битый id не сохраняется |
| Прочитать связи | `get_config_cross_references_tool(uuid? \| local_doc_id, limit?)` | с проверкой указателя в `local_doc` |
| Снять связь | `delete_config_cross_reference_tool(reference_id)` | |

> ⚠️ Внешние объекты адресуются **`uuid` или `source_path` каталога выгрузки**, а не `config_id`
> (таблица `configurations` для enrichment не используется). Старые инструменты с `config_id`
> (`add_config_alias_tool`, `get_alias_target_tool`, `search_config_by_alias_tool`,
> `get_config_snippet_stats_tool`, `register_cross_reference_tool`, `add_snippet_dependency_tool`,
> `update_dependent_snippets_tool`, `generate_aliases_for_object_tool`,
> `get_snippets_for_object_tool`) удалены вместе с мёртвым кодом `src/config_aliases.py`,
> `src/config_snippets_manager.py`, `src/config_tools.py`.

---

### 3. Редактирование кода MCP `1c-configurations-enrichment` (server_configurations_enrichment.py)

**Перед началом редактирования файлов MCP `1c-configurations-enrichment`:**

✅ **ОБЯЗАТЕЛЬНО** ознакомьтесь с файлом правил:

```text
C:\1C_LLM\ckb\.clinerules\1c-configurations-enrichment_Rule.md
```

**Что нужно знать из файла правил:**

- Структура обогащения `ckb_1c_configurations`: `config_aliases`, `config_snippets`,
  `config_snippet_dependencies`, `config_cross_references`, витрины `v_config_alias_targets`,
  `v_config_enrichment`
- Словарь `target_type` (`ExternalReport`, `Attribute`, `TabularSection`, `TabularSectionColumn`,
  `Form`, `FormItem`, `Template`, `Module`, `ConfigSnippet`) и стабильные ключи `target_uuid`
- Генерация: один вызов на объект, одна транзакция, авто-строки (`origin='generated'`)
  отделяются от ручных (`origin='manual'`, `is_verified=true`)
- Карточка объекта (`config_enrichment_stats_tool(uuid=…, card=True)`) — только чтение
- Правила удаления: алиас — мягкое снятие, сниппет — hard с его алиасами/зависимостями/ссылками,
  enrichment чистится и при удалении самого объекта

**После ознакомления:**

1. Убедитесь, что понимаете механизм генерации алиасов (`src/enrichment_generator.py`)
2. Проверьте соответствие описанных таблиц реальному состоянию БД (`_cmp_ddl.py`, разделы 20–23
   `check_external_report_fill.sql`)
3. Только после этого приступайте к редактированию кода

---
