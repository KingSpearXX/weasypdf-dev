from datetime import datetime

def format_iso_date(value: str | None, fmt: str = "%m/%d/%Y") -> str:
    if not value:
        return ""
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00") if text.endswith("Z") else text
        )
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return text
    return parsed.strftime(fmt)
