#!/usr/bin/env python3
"""Ядро загрузчика: константы, dataclass, теги, категории."""


# === ТЕГИ как ОСНОВНОЙ механизм классификации ===
# Теги определяют тип контента и имеют вес для ранжирования
CONTENT_TAGS = {
    'code': ['пример', 'код', 'синтаксис', 'вызов', 'метод', 'функция'],
    'howto': ['как создать', 'как добавить', 'как удалить', 'как изменить', 'как настроить', 'как подключить', 'инструкция', 'руководство'],
    'syntax': ['синтаксис', 'параметр', 'аргумент', 'возвращает', 'описание'],
    'error': ['ошибка', 'исключение', 'проблема', 'не работает', 'исправлени', 'решение', 'устранить', 'баг'],
    'solution': ['решение', 'способ', 'вариант', 'подход', 'рекомендация', 'совет', 'лучшая практика'],
    'api': ['интерфейс', 'метод', 'свойство', 'класс', 'объект', 'тип данных'],
    'command': ['команда', 'панель', 'меню', 'действие', 'операция'],
}

# Веса тегов — влияют на ранжирование результатов поиска
TAG_WEIGHTS = {
    'code': 1.5,
    'error': 1.4,
    'solution': 1.3,
    'howto': 1.3,
    'api': 1.2,
    'syntax': 0.9,
    'command': 0.8,
}

# === Категории — ВТОРОСТЕПЕННЫЕ (для обратной совместимости) ===
CATEGORY_KEYWORDS = {
    'language': ['синтаксис', 'встроенный язык', 'типы данных', 'переменные', 'методы', 'процедуры', 'функции', 'объекты', 'структура', 'модуль', 'конфигурация', 'объект конфигурации', 'формы', 'командный язык', 'разработчика', 'синтакс-помощник', 'syntaxhelper', 'запрос', 'запросы', 'справочник', 'документ', 'регистр', 'план счетов'],
    'platform': ['ком', 'com-интерфейс', 'http-сервис', 'http-запрос', 'веб-сервер', 'файловые операции', 'клиент', 'сервер', 'сеанс', 'клиент-сервер', 'кластер серверов', 'администратор', 'установка', 'запуск', 'консоль', 'обновление', 'веб-клиент', 'http-подключение'],
    'its': ['итс', 'интеграция и технологии', 'документация 1с', 'руководство пользователя', 'пользователя', 'справка'],
    'methodology': ['бухгалтерский учёт', 'бухгалтерский учет', 'нд/нр', 'методические рекомендации', 'методология', 'учёт', 'проводки', 'счёт'],
}


def detect_category(text):
    """Определяет категорию документа (language/platform/its/methodology)."""
    text_lower = text.lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(len(kw) for kw in keywords if kw in text_lower)
        scores[category] = score
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'language'


def detect_tags(text):
    """Определяет теги контента по текстовому содержимому.
    
    Возвращает список тегов. Каждый тег определяется если хотя бы одно ключевое слово найдено.
    """
    text_lower = text.lower()
    detected = []
    for tag, keywords in CONTENT_TAGS.items():
        for keyword in keywords:
            if keyword in text_lower and tag not in detected:
                detected.append(tag)
                break
    return detected


def get_tag_weight(tags):
    """Вычисляет суммарный вес тегов документа для ранжирования."""
    if not tags:
        return 1.0
    return sum(TAG_WEIGHTS.get(t, 1.0) for t in tags)


def assess_usefulness(text, tags):
    """Оценивает полезность контента (is_useful, confidence)."""
    score = 0.0
    if tags and 'code' in tags:
        score += 0.4
    if tags and ('solution' in tags or 'error' in tags):
        score += 0.3
    if tags and 'howto' in tags:
        score += 0.2
    text_len = len(text.strip())
    if text_len > 500:
        score += 0.1
    elif text_len < 50:
        score -= 0.3
    code_blocks = text.count('```') + text.count(chr(9)) + text.count('    ')
    if code_blocks > 2:
        score += 0.15
    confidence = max(0.0, min(1.0, score))
    is_useful = confidence >= 0.3
    return is_useful, confidence
