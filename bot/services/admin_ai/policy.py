import re


def _clarification_policy_error(user_text: str, question: str) -> str | None:
    normalized_question = question.casefold()
    forbidden_rarities = (
        "эпическ",
        "легендарн",
        "необычн",
    )
    if any(value in normalized_question for value in forbidden_rarities):
        return "использована чужая шкала редкости; допустимы только H–SS"

    normalized_user = user_text.casefold()
    creative_request = any(
        marker in normalized_user
        for marker in (
            "придум",
            "сам реши",
            "сама реши",
            "пофиг",
            "на твой выбор",
            "что угодно",
        )
    )
    if creative_request:
        unnecessary_topics = (
            "редкост",
            "описан",
            "характеристик",
            "эффект",
            "лимит",
            "номер слот",
        )
        if any(topic in normalized_question for topic in unnecessary_topics):
            return "запрошены творческие параметры, которые пользователь поручил выбрать агенту"

    explicit_registry_type = bool(
        re.search(r"\b(заклинан\w*|контурн\w*|особ\w*\s+карт\w*)\b", normalized_user)
    )
    asks_registry_choice = "реестр" in normalized_question and "обычн" in normalized_question
    if explicit_registry_type and asks_registry_choice:
        return "тип карты уже означает реестровую карту; выбирать между реестром и Обычной не нужно"
    return None

