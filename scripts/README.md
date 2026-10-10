# 📁 Скрипты для индексации конфигураций 1С

## index_config.py — Универсальный скрипт загрузки конфигураций

### Назначение
Автоматизация регистрации и индексации выгруженных конфигураций 1С (БГУ2, УТ, ERP и др.) в базу `configurations`.

### Использование

#### Базовый синтаксис
```powershell
cd C:\1C_LLM\ckb
python scripts\index_config.py <путь_к_конфигурации> [опции]
```

#### Примеры

**1. Полная индексация всех типов объектов:**
```powershell
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2"
```

**2. Только регистрация (без индексации):**
```powershell
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" --register-only
# или
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" -r
```

**3. Индексация только определённых типов:**
```powershell
# Только справочники и документы
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" --types catalog,document
# или с коротким флагом
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" -t catalog,document
```

**4. Индексация всех типов кроме указанных:**
```powershell
# Без перечислений (быстрее)
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" --skip enum
# или
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" -s enum

# Без перечислений и констант
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" --skip enum,constant
```

**5. Быстрая проверка структуры (только справочники):**
```powershell
python scripts\index_config.py "C:\1C_LLM\LoadDoc\BGU2" -t catalog
```

### Поддерживаемые типы объектов

| Тип | Описание | Примерное кол-во (БГУ2) |
|-----|----------|-------------------------|
| `catalog` | Справочники | ~540 |
| `document` | Документы | ~473 |
| `register_info` | Регистры сведений | ~948 |
| `register_accumulation` | Регистры накопления | ~54 |
| `enum` | Перечисления | ~807 |
| `constant` | Константы | ~552 |
| `plan_accounts` | Планы счетов | 1 |

### Вывод скрипта

Скрипт отображает:
1. ✅ Результат регистрации конфигурации (ID, название, версия)
2. 📊 Прогресс индексации по каждому типу
3. 📋 Итоговый отчёт с таблицей результатов
4. 💡 Рекомендации по проверке статуса

### Проверка результата

После завершения скрипта проверьте статус конфигурации:

**Через MCP:**
```python
list_configurations_tool(status='indexed')
```

**Через psql:**
```powershell
$env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -U postgres -d configurations -c "SELECT id, name, version, status, created_at FROM configuration ORDER BY created_at DESC LIMIT 5;"
```

### Получение помощи

```powershell
python scripts\index_config.py --help
```
