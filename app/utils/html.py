from html import escape


def escape_html(value: str | None) -> str:
    return escape(value or "", quote=False)
