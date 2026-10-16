#!/usr/bin/env python3
"""Fetch public online hackathons using only the Python 3.11+ standard library."""

import hashlib
import html
from html.parser import HTMLParser
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "hackathons.json"
USER_AGENT = "hackathon-calendar/1.0 (+https://github.com/kks0488/hackathon-calendar)"
TIMEOUT = 30
SOURCES = ("Devpost", "MLH", "lablab.ai")
LOG = logging.getLogger(__name__)
MONTHS = {
    name: number
    for number, names in enumerate(
        ("jan january", "feb february", "mar march", "apr april", "may",
         "jun june", "jul july", "aug august", "sep sept september",
         "oct october", "nov november", "dec december"), 1
    )
    for name in names.split()
}


def clean_text(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).split())


def parse_devpost_dates(value):
    """Return ISO dates; date-only listings never imply a precise cutoff time."""
    parts = re.split(r"\s*[-–—]\s*", clean_text(value).replace(".", ""))
    if not 1 <= len(parts) <= 2:
        raise ValueError(f"Unrecognized date range: {value!r}")

    def parse_part(part):
        match = re.fullmatch(r"(?:(?P<month>[A-Za-z]+)\s+)?(?P<day>\d{1,2})"
                             r"(?:,?\s+(?P<year>\d{4}))?", part)
        if not match:
            raise ValueError(f"Unrecognized date: {part!r}")
        month = match["month"]
        return (MONTHS[month.lower()] if month else None, int(match["day"]),
                int(match["year"]) if match["year"] else None)

    sm, sd, sy = parse_part(parts[0])
    em, ed, ey = parse_part(parts[-1])
    if sm is None or not (sy or ey):
        raise ValueError(f"Missing month/year: {value!r}")
    em = em or sm
    if sy is None:
        sy = ey - (em < sm)
    if ey is None:
        ey = sy + (em < sm)
    start, deadline = date(sy, sm, sd), date(ey, em, ed)
    if deadline < start:
        raise ValueError(f"Reversed date range: {value!r}")
    return start.isoformat(), deadline.isoformat()


def utc_value(value):
    """Normalize ISO timestamps to UTC, preserving date-only precision."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value).isoformat()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp has no timezone: {value!r}")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_url(value):
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid event URL: {value!r}")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(),
                       parsed.path.rstrip("/"), parsed.query, ""))


def normalize_event(*, title, organizer, url, start, deadline, prize="", themes=(), source):
    url = canonical_url(url)
    title = clean_text(title)
    if not title:
        raise ValueError("Missing event title")
    return {
        "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:24],
        "title": title,
        "organizer": clean_text(organizer),
        "url": url,
        "start": utc_value(start),
        "deadline": utc_value(deadline),
        "prize": clean_text(prize),
        "themes": [clean_text(theme) for theme in themes if clean_text(theme)],
        "format": "online",
        "source": source,
    }


def dedupe_and_filter(events, today=None):
    """Keep deadlines on/after today's UTC date, including earlier times today."""
    today = today or datetime.now(timezone.utc).date()
    unique = {}
    for event in events:
        if event["format"] != "online":
            continue
        if date.fromisoformat(utc_value(event["deadline"])[:10]) < today:
            continue
        url = canonical_url(event["url"])
        if url not in unique:
            unique[url] = dict(event, url=url,
                               id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:24])
    return sorted(unique.values(), key=lambda e: (e["deadline"], e["url"]))


def request_text(url, *, accept="text/html"):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8")


def parse_devpost_event(item):
    if item.get("open_state") not in ("open", "upcoming") or item.get("invite_only"):
        return None
    # The endpoint is online-only; also reject explicitly physical listings.
    location = item.get("displayed_location") or {}
    if location.get("location") and not re.search(r"\bonline\b", location["location"], re.I):
        return None
    start, deadline = parse_devpost_dates(item["submission_period_dates"])
    event = normalize_event(
        title=item["title"], organizer=item.get("organization_name", ""),
        url=item["url"], start=start, deadline=deadline,
        prize=item.get("prize_amount", ""),
        themes=[theme["name"] for theme in item.get("themes", [])], source="Devpost",
    )
    event["open_state"] = item["open_state"]
    event["registrations_count"] = item.get("registrations_count", 0)
    return event


def fetch_devpost():
    events, seen_pages, page = [], set(), 1
    while True:
        url = ("https://devpost.com/api/hackathons?status[]=open&status[]=upcoming"
               f"&challenge_type[]=online&page={page}")
        try:
            payload = json.loads(request_text(url, accept="application/json"))
            items = payload["hackathons"]
            if not isinstance(items, list):
                raise ValueError("hackathons is not a list")
            if not items:
                break
            signature = tuple(item["url"] for item in items)
            if signature in seen_pages:
                raise ValueError("Pagination repeated a page")
            seen_pages.add(signature)
            for item in items:
                try:
                    event = parse_devpost_event(item)
                    if event:
                        events.append(event)
                except (KeyError, TypeError, ValueError) as exc:
                    LOG.warning("Devpost: skipping %r: %s", item.get("title"), exc)
            page += 1
        except Exception as exc:
            LOG.warning("Devpost page %s failed; keeping earlier pages: %s", page, exc)
            break
    return events


class JSONScripts(HTMLParser):
    """Read server-rendered JSON script elements without executing JavaScript."""

    def __init__(self, body):
        super().__init__()
        self.scripts = []
        self.attributes = None
        self.chunks = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") in ("application/json", "application/ld+json"):
            self.attributes, self.chunks = attrs, []

    def handle_data(self, data):
        if self.attributes is not None:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.attributes is not None:
            self.scripts.append((self.attributes, "".join(self.chunks)))
            self.attributes = None


def parse_mlh(body):
    for attrs, raw in JSONScripts(body).scripts:
        if attrs.get("data-page") != "app":
            continue
        props = json.loads(raw)["props"]
        if not all(isinstance(props.get(key), list) for key in ("upcomingEvents", "pastEvents")):
            raise ValueError("Unrecognized MLH event lists")
        events = []
        for item in props["upcomingEvents"] + props["pastEvents"]:
            if item.get("formatType", "").lower() not in ("digital", "online", "hybrid"):
                continue
            try:
                events.append(normalize_event(
                    title=item["name"], organizer="Major League Hacking",
                    url=urljoin("https://www.mlh.com", item.get("websiteUrl") or item["url"]),
                    start=item["startsAt"], deadline=item["endsAt"], source="MLH",
                ))
            except (KeyError, TypeError, ValueError) as exc:
                LOG.warning("MLH: skipping %r: %s", item.get("name"), exc)
        return events
    raise ValueError("No parseable server-rendered MLH event data")


def parse_lablab(body):
    def objects(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from objects(child)
        elif isinstance(value, list):
            for child in value:
                yield from objects(child)

    events, found_event = [], False
    for attrs, raw in JSONScripts(body).scripts:
        if attrs.get("type") != "application/ld+json":
            continue
        for item in objects(json.loads(raw)):
            kinds = item.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if "Event" not in kinds:
                continue
            found_event = True
            if not re.search(r"OnlineEventAttendanceMode|MixedEventAttendanceMode",
                             str(item.get("eventAttendanceMode", ""))):
                continue
            if str(item.get("eventStatus", "")).endswith(("EventCancelled", "EventPostponed")):
                continue
            try:
                organizer = item.get("organizer") or {}
                events.append(normalize_event(
                    title=item["name"], organizer=organizer.get("name", "lablab.ai"),
                    url=item["url"], start=item["startDate"], deadline=item["endDate"],
                    source="lablab.ai",
                ))
            except (KeyError, TypeError, ValueError) as exc:
                LOG.warning("lablab.ai: skipping %r: %s", item.get("name"), exc)
    if not found_event:
        raise ValueError("Listing has no dated Event JSON-LD; skipping optional source")
    return events


def collect_hackathons(today=None):
    events = []
    collectors = [
        ("Devpost", fetch_devpost),
        ("MLH 2027", lambda: parse_mlh(request_text("https://mlh.io/seasons/2027/events"))),
        ("MLH 2026", lambda: parse_mlh(request_text("https://mlh.io/seasons/2026/events"))),
        ("lablab.ai", lambda: parse_lablab(request_text("https://lablab.ai/event"))),
    ]
    for name, collect in collectors:
        try:
            events.extend(collect())
        except Exception as exc:
            LOG.warning("%s failed: %s", name, exc)
    return dedupe_and_filter(events, today)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    events = collect_hackathons()
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for source in SOURCES:
        print(f"{source}: {sum(event['source'] == source for event in events)} events")
    print(f"Total: {len(events)} events → {DATA_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
