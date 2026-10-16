#!/usr/bin/env python3
"""Build the subscribed calendar and Korean tracker from normalized public data."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re

try:
    from .fetch_hackathons import DATA_PATH, ROOT, dedupe_and_filter
except ImportError:
    from fetch_hackathons import DATA_PATH, ROOT, dedupe_and_filter

KST = timezone(timedelta(hours=9))
CALENDAR_NAME = "Hackathon Tracker"


def escape_ics(value):
    return (str(value).replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n")
            .replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,"))


def fold_line(line):
    """Fold at 75 UTF-8 octets, counting the continuation space."""
    lines, current, octets = [], "", 0
    for char in line:
        size = len(char.encode("utf-8"))
        if octets + size > 75:
            # Move trailing spaces to the continuation without losing content.
            trimmed = current.rstrip(" \t")
            carry = current[len(trimmed):] if trimmed else ""
            if not trimmed or len(carry.encode("utf-8")) + 1 + size > 75:
                trimmed, carry = current, ""
            lines.append(trimmed)
            current = " " + carry
            octets = len(current.encode("utf-8"))
        current += char
        octets += size
    lines.append(current)
    return "\r\n".join(lines)


def render_calendar(events, now=None, calendar_name=CALENDAR_NAME):
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Hackathon Tracker//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics(calendar_name)}", "X-WR-TIMEZONE:Asia/Seoul",
    ]
    for event in events:
        deadline = event["deadline"]
        lines += ["BEGIN:VEVENT", f"UID:{event['id']}@kks0488.github.io", f"DTSTAMP:{stamp}"]
        if len(deadline) == 10:
            day = date.fromisoformat(deadline)
            lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
                      f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}"]
        else:
            cutoff = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            lines.append(f"DTSTART:{cutoff.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}")
        description = "\n".join([
            f"Prize: {event['prize'] or 'Not listed'}",
            f"Organizer: {event['organizer'] or 'Not listed'}",
            f"Themes: {', '.join(event['themes']) or 'Not listed'}",
            "Format: online", f"Source: {event['source']}", f"URL: {event['url']}",
        ])
        lines += [f"SUMMARY:{escape_ics(event['title'])} — 마감",
                  f"DESCRIPTION:{escape_ics(description)}", f"URL:{event['url']}",
                  "STATUS:CONFIRMED", "CATEGORIES:HACKATHON"]
        for days in (3, 1):
            lines += ["BEGIN:VALARM", f"TRIGGER:-P{days}D", "ACTION:DISPLAY",
                      f"DESCRIPTION:{escape_ics(event['title'])} — {days}일 전", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode("utf-8")


def project_section(existing):
    """Keep the existing candidate project section byte-for-byte as text."""
    match = re.search(r"^## 보유 프로젝트 \(출전 후보\)[^\n]*\n", existing, re.M)
    if not match:
        raise ValueError("HACKATHONS.md is missing the candidate project section")
    end = re.search(r"^(?:---\s*$|## )", existing[match.end():], re.M)
    return existing[match.start():match.end() + end.start() if end else len(existing)]


def markdown_cell(value):
    value = str(value).replace("\r", " ").replace("\n", " ")
    # Escape remote text so titles/themes cannot break the generated table or HTML.
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                     ("|", "&#124;"), ("\\", "&#92;"), ("[", "&#91;"), ("]", "&#93;")):
        value = value.replace(old, new)
    return value


def deadline_kst(value):
    if len(value) == 10:
        return f"{value} (시각 미제공)"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


def render_markdown(events, existing, now=None):
    now = now or datetime.now(timezone.utc)
    prefix = "# Hackathon Tracker\n\n" + project_section(existing)
    lines = ["---", "", "## 참가 가능 해커톤", "",
             f"> Last updated: {now.astimezone(timezone.utc):%Y-%m-%d %H:%M UTC}", "",
             "온라인 참여가 가능한 행사입니다. 시각이 없는 마감은 출처의 날짜를 그대로 표시합니다.",
             "MLH는 행사 종료 시각을 마감으로 사용합니다. 참가 자격과 정확한 제출 시각은 행사 링크에서 확인하세요.", "",
             "| 해커톤 | 주최 | 마감 (KST) | 상금 | 테마 | 출처 |",
             "|---|---|---|---|---|---|"]
    for event in sorted(events, key=lambda e: (e["deadline"], e["url"])):
        # Angle brackets keep parentheses in URLs from closing the Markdown link.
        url = event["url"].replace("<", "%3C").replace(">", "%3E").replace("|", "%7C")
        cells = [f"[{markdown_cell(event['title'])}](<{url}>)",
                 markdown_cell(event["organizer"] or "미공개"), deadline_kst(event["deadline"]),
                 markdown_cell(event["prize"] or "미공개"),
                 markdown_cell(", ".join(event["themes"]) or "미공개"), markdown_cell(event["source"])]
        lines.append("| " + " | ".join(cells) + " |")
    if not events:
        lines += ["", "현재 수집된 참가 가능 행사가 없습니다. 수집 경고는 실행 로그에서 확인하세요."]
    return prefix + "\n".join(lines) + "\n"


def main():
    now = datetime.now(timezone.utc)
    events = dedupe_and_filter(json.loads(DATA_PATH.read_text(encoding="utf-8")), now.date())
    tracker = ROOT / "HACKATHONS.md"
    calendar = ROOT / "hackathon-calendar.ics"
    existing_calendar = calendar.read_text(encoding="utf-8")
    unfolded = re.sub(r"\n[ \t]", "", existing_calendar)
    name = re.search(r"^X-WR-CALNAME:(.*)$", unfolded, re.M)
    calendar_name = name[1] if name else CALENDAR_NAME
    markdown = render_markdown(events, tracker.read_text(encoding="utf-8"), now)
    calendar.write_bytes(render_calendar(events, now, calendar_name))
    tracker.write_text(markdown, encoding="utf-8")
    DATA_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built calendar, tracker and JSON: {len(events)} events")


if __name__ == "__main__":
    main()
