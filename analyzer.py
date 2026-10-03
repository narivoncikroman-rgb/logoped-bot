# analyzer.py
# Анализ описания речевых трудностей

from difflib import SequenceMatcher
from knowledge_base import DISORDERS


def _normalize(text):
    """Приводит текст к удобному для анализа виду."""
    text = text.lower().strip()

    replacements = {
        "ё": "е",
        "–": "-",
        "—": "-",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return " ".join(text.split())


def _similarity(text, keyword):
    """Сравнивает текст с ключевой фразой."""

    text = _normalize(text)
    keyword = _normalize(keyword)

    # Сначала проверяем точное совпадение всей ключевой фразы
    if keyword in text:
        return 1.0

    # Для конструкций с конкретными парами звуков
    # используем только точное совпадение пары.
    prefixes = [
        "путает ",
        "не различает "
    ]

    for prefix in prefixes:
        if keyword.startswith(prefix):
            pair = keyword[len(prefix):].strip()

            if pair in text:
                return 1.0

            return 0.0

    # Для коротких ключевых фраз
    # приблизительное сравнение не используем.
    keyword_words = keyword.split()

    if len(keyword_words) <= 3:
        return 0.0

    text_words = text.split()

    if not text_words:
        return 0.0

    best = 0.0
    window_size = len(keyword_words)

    for i in range(len(text_words) - window_size + 1):
        fragment = " ".join(
            text_words[i:i + window_size]
        )

        similarity = SequenceMatcher(
            None,
            fragment,
            keyword
        ).ratio()

        best = max(best, similarity)

    if best >= 0.95:
        return best

    return 0.0

def analyze(text, age=None):
    """
    Анализирует описание речевых особенностей.

    Возвращает список наиболее подходящих направлений.
    Результат не является диагнозом.
    """

    text = _normalize(text)

    if not text:
        return []

    results = []

    for code, disorder in DISORDERS.items():

        score = 0
        matched_keywords = []

        # Сначала собираем все точные совпадения
        exact_matches = []

        for keyword in disorder.get("keywords", []):
            similarity = _similarity(text, keyword)

            if similarity >= 1.0:
                exact_matches.append(keyword)
        specific_pairs = []

        for keyword in exact_matches:
            if (
                    keyword.startswith("путает ")
                    or keyword.startswith("не различает ")
            ):
                parts = keyword.split()

                if len(parts) == 4 and parts[2] == "и":
                    specific_pairs.append(keyword)
        # Убираем общие совпадения одного и того же признака.

        general_keywords = {
            "путает звуки",
            "не различает звуки"
        }
        # Если найдено несколько общих формулировок
        # одного признака — оставляем только одну.
        general_matches = [
            keyword
            for keyword in exact_matches
            if keyword in general_keywords
        ]

        # Если есть конкретная пара звуков,
        # общие формулировки пропускаем.
        if specific_pairs:
            general_matches = []

        if general_matches:
            matched_keywords.append(general_matches[0])

        for keyword in exact_matches:

            if keyword in general_keywords:
                continue

            matched_keywords.append(keyword)
        # Баллы за реальные, отличающиеся признаки
        score += len(matched_keywords) * 25

        # Учитываем возраст только как небольшой дополнительный фактор
        age_range = disorder.get("age_range")

        if age is not None and age_range:
            min_age, max_age = age_range

            if min_age <= age <= max_age:
                score += 5
            else:
                score -= 3

        # Ограничиваем максимальный результат
        score = min(score, 100)

        # Результат добавляем только если найден
        # хотя бы один конкретный речевой признак
        if matched_keywords:
            results.append({
                "code": code,
                "name": disorder["name"],
                "description": disorder["description"],
                "score": round(score, 1),
                "matched_keywords": matched_keywords,
                "age_range": age_range
            })

    # Сначала результаты с большим количеством совпадений,
    # затем с более высоким баллом
    results.sort(
        key=lambda x: (
            len(x["matched_keywords"]),
            x["score"]
        ),
        reverse=True
    )

    return results[:3]