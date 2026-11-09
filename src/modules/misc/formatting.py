import math
from datetime import datetime


def millify(n, style="short"):
    """Abbreviate a number. "short" -> 1.5M (embeds), "report" -> 1.50 M (report images), "compact" -> 1.50M (report text)"""
    if style == "short":
        for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if n >= limit:
                return f"{n/limit:.1f}{suffix}"
        return str(int(n))
    if not n: return "0"
    names = ['', 'K', 'M', 'B', 'T', 'Qd']
    n = float(n)
    idx = max(0, min(len(names) - 1, int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))
    return '{:.2f}{}{}'.format(n / 10**(3 * idx), " " if style == "report" else "", names[idx])


def formatHMS(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def timestampedEmbedText(title, desc, time_value, time_format=24):
    """Prefix the log time ("HH:MM:SS", shown as 12-hour when time_format is 12) to the title, or to the description when there is no title. Returns (title, desc)."""
    if time_format == 12:
        try:
            time_value = datetime.strptime(time_value, "%H:%M:%S").strftime("%I:%M:%S %p")
        except Exception:
            pass
    if title:
        return f"[{time_value}] {title}", desc
    return "", f"[{time_value}] {desc}"
