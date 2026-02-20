"""Экранирование для Telegram Markdown. Без parse_mode надёжнее для контента из БД/пользователя."""

def escape_md(text: str) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("`", "\\`")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
