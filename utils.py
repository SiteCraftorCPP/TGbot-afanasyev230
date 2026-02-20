"""Экранирование для Telegram Markdown (parse_mode='Markdown'). Символы _ * ` [ ломают разбор."""

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
    )
