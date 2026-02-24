"""Экранирование для Telegram Markdown. Без parse_mode надёжнее для контента из БД/пользователя."""

import re


def text_to_telegram_html(text: str) -> str:
    """
    Конвертирует разметку в HTML для Telegram (по всему проекту).
    Поддерживает: *жирный*, _курсив_, __подчёркнутый__, ~зачёркнутый~.
    Отправлять с parse_mode="HTML".
    """
    if not text or not text.strip():
        return ""
    s = str(text)
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    s = re.sub(r"__(.+?)__", r"<u>\1</u>", s, flags=re.DOTALL)
    s = re.sub(r"\*(.+?)\*", r"<b>\1</b>", s, flags=re.DOTALL)
    s = re.sub(r"_(.+?)_", r"<i>\1</i>", s, flags=re.DOTALL)
    s = re.sub(r"~(.+?)~", r"<s>\1</s>", s, flags=re.DOTALL)
    return s


# для обратной совместимости в рассылке
broadcast_text_to_html = text_to_telegram_html


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
