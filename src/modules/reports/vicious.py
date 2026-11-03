"""Vic Hop counters shared by the live table and report attachments."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

FONT_PATH = Path(__file__).resolve().parents[2] / "hourly_report/Inter/static/Inter_18pt-Medium.ttf"

METRICS = (
    ("vic_servers", "Servers joined"),
    ("vic_nights", "Nights detected"),
    ("vic_sightings", "Vicious Bee sightings"),
    ("vic_defeats", "Confirmed defeats"),
    ("vic_stingers", "Stingers earned"),
    ("vic_deaths", "Deaths during combat"),
    ("vic_returns", "Successful returns after death"),
)


def rows(hour, session):
    return [(label, hour.get(key, 0), session.get(key, 0)) for key, label in METRICS]


def send_report(logger, report, session=False):
    hour = report.hourlyReportStats
    total = report.sessionReportStats
    if not total.get("vic_servers", 0):
        return
    if session:
        report.vicLastSession = {key: total.get(key, 0) for key, _ in METRICS}
        report.saveHourlyReportData()
    title = "Vic Hop Session Report" if session else "Vic Hop Hourly Report"
    data = rows(hour, total)
    canvas = Image.new("RGB", (700, 100 + len(data) * 42), "#191923")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(FONT_PATH), 18)
    draw.text((24, 20), title, fill="white", font=font)
    draw.text((455, 60), "This hour", fill="white", font=font)
    draw.text((580, 60), "Session", fill="white", font=font)
    fields = []
    for i, (label, current, cumulative) in enumerate(data):
        y = 90 + i * 42
        draw.text((24, y), label, fill="white", font=font)
        draw.text((455, y), str(current), fill="white", font=font)
        draw.text((580, y), str(cumulative), fill="white", font=font)
        fields.append({"name": label, "value": str(cumulative if session else current), "inline": True})
    path = "vicSessionReport.png" if session else "vicHourlyReport.png"
    canvas.save(path)
    logger.itemReport(title, "Stinger totals include only rewards successfully read by OCR.", "purple", fields=fields, imagePath=path)


def saved_stats():
    """Return current, last session and lifetime counters from the atomic snapshot."""
    import pickle
    from modules.misc import settingsManager
    path = Path(settingsManager.getUserDataPath("hourly_report_stats.pkl"))
    if not path.exists():
        return {}, {}, {}
    try:
        with path.open("rb") as source:
            data = pickle.load(source)
    except (OSError, EOFError, pickle.UnpicklingError):
        return {}, {}, {}
    current = data.get("sessionReportStats", {})
    completed = data.get("vicCompletedTotals", {})
    total = {key: completed.get(key, 0) + current.get(key, 0) for key, _ in METRICS}
    return current, data.get("vicLastSession", {}), total
