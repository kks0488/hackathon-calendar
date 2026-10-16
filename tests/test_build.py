"""Offline fixtures for source normalization and the generated subscription."""

from datetime import date, datetime, timezone
import json
import unittest
from unittest.mock import patch

from scripts import build_calendar as build
from scripts import fetch_hackathons as fetch

TODAY = date(2026, 10, 16)
NOW = datetime(2026, 10, 16, 12, 30, tzinfo=timezone.utc)
DEVPOST = {
    "title": "Online AI Hackathon",
    "url": "https://example.devpost.com/",
    "submission_period_dates": "Oct 01 - Nov 15, 2026",
    "prize_amount": "$<span data-currency-value>10,000</span> &amp; credits",
    "themes": [{"name": "Machine Learning/AI"}, {"name": "Web"}],
    "open_state": "open",
    "organization_name": "Example &amp; Co.",
    "registrations_count": 42,
    "displayed_location": {"location": "Online"},
}
PROJECTS = """# Hackathon Tracker

> 마지막 갱신: 2026-02-27

## 보유 프로젝트 (출전 후보)

| 프로젝트 | 설명 | 적합 카테고리 |
|---------|------|-------------|
| dailywave | ADHD 친화적 플로우 플래너 (PWA) | Productivity, Health, AI |

---

## 참가 가능 해커톤 (old)

Old content.
"""


def event(**changes):
    return dict(fetch.parse_devpost_event(DEVPOST), **changes)


class DateTests(unittest.TestCase):
    def test_devpost_ranges(self):
        fixtures = [
            ("Oct 01 - Nov 15, 2026", "2026-10-01", "2026-11-15"),
            ("Oct 01 - 15, 2026", "2026-10-01", "2026-10-15"),
            ("October 1 – November 15, 2026", "2026-10-01", "2026-11-15"),
            ("Sept. 1 - Oct 5, 2026", "2026-09-01", "2026-10-05"),
            ("Dec 20 - Jan 05, 2027", "2026-12-20", "2027-01-05"),
            ("Dec 20, 2026 - Jan 05, 2027", "2026-12-20", "2027-01-05"),
            ("Dec 20, 2026 - Jan 05", "2026-12-20", "2027-01-05"),
            ("Nov 15, 2026", "2026-11-15", "2026-11-15"),
        ]
        for text, start, deadline in fixtures:
            with self.subTest(text=text):
                self.assertEqual(fetch.parse_devpost_dates(text), (start, deadline))

    def test_invalid_dates_are_not_guessed(self):
        for value in ("TBD", "Oct 01 - Nov 15", "Feb 30, 2026", "Nov 15, 2026 - Oct 01, 2026"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fetch.parse_devpost_dates(value)

    def test_timestamp_normalization(self):
        self.assertEqual(fetch.utc_value("2026-10-17T01:00:00+09:00"), "2026-10-16T16:00:00Z")
        with self.assertRaises(ValueError):
            fetch.utc_value("2026-10-16T12:00:00")


class SourceTests(unittest.TestCase):
    def test_devpost_html_and_fields(self):
        item = event()
        self.assertEqual(item["prize"], "$10,000 & credits")
        self.assertEqual(item["organizer"], "Example & Co.")
        self.assertEqual(item["themes"], ["Machine Learning/AI", "Web"])
        self.assertEqual(item["registrations_count"], 42)
        self.assertEqual(item["format"], "online")

    def test_devpost_excludes_closed_physical_and_invite_only(self):
        for changes in ({"open_state": "closed"}, {"invite_only": True},
                        {"displayed_location": {"location": "New York"}}):
            with self.subTest(changes=changes):
                self.assertIsNone(fetch.parse_devpost_event(dict(DEVPOST, **changes)))

    def test_dedupe_canonical_url_and_stable_id(self):
        result = fetch.dedupe_and_filter([
            event(), event(url="https://EXAMPLE.devpost.com/#about", source="MLH")
        ], TODAY)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], event()["id"])
        self.assertEqual(result[0]["url"], "https://example.devpost.com")

    def test_past_deadlines_filtered_today_and_future_kept(self):
        values = ["2026-10-15", "2026-10-15T23:59:59Z", "2026-10-16",
                  "2026-10-16T00:00:00Z", "2026-10-17"]
        items = [event(url=f"https://example.com/{i}", deadline=value)
                 for i, value in enumerate(values)]
        result = fetch.dedupe_and_filter(items, TODAY)
        self.assertEqual([item["deadline"] for item in result], values[2:])

    def test_filter_uses_utc_day(self):
        result = fetch.dedupe_and_filter([
            event(deadline="2026-10-16T01:00:00+09:00")
        ], TODAY)
        self.assertEqual(result, [])

    def test_paginates_until_empty(self):
        pages = [json.dumps({"hackathons": [DEVPOST]}),
                 json.dumps({"hackathons": [dict(DEVPOST, url="https://second.devpost.com")]}),
                 json.dumps({"hackathons": []})]
        with patch.object(fetch, "request_text", side_effect=pages) as request:
            self.assertEqual(len(fetch.fetch_devpost()), 2)
        self.assertEqual(request.call_count, 3)
        self.assertIn("page=3", request.call_args.args[0])

    def test_page_failure_keeps_previous_pages(self):
        with patch.object(fetch, "request_text", side_effect=[
            json.dumps({"hackathons": [DEVPOST]}), TimeoutError("fixture timeout")
        ]), self.assertLogs(fetch.LOG, level="WARNING"):
            self.assertEqual(len(fetch.fetch_devpost()), 1)

    def test_one_source_failure_does_not_stop_other_sources(self):
        with patch.object(fetch, "fetch_devpost", side_effect=TimeoutError("fixture timeout")), \
             patch.object(fetch, "request_text", return_value="fixture"), \
             patch.object(fetch, "parse_mlh", return_value=[event(source="MLH")]), \
             patch.object(fetch, "parse_lablab", side_effect=ValueError("no dates")), \
             self.assertLogs(fetch.LOG, level="WARNING"):
            result = fetch.collect_hackathons(TODAY)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "MLH")

    def test_request_has_timeout_and_user_agent(self):
        with patch.object(fetch, "urlopen") as opening:
            response = opening.return_value.__enter__.return_value
            response.read.return_value = b'{}'
            response.headers.get_content_charset.return_value = "utf-8"
            self.assertEqual(fetch.request_text("https://example.com"), "{}")
        self.assertEqual(opening.call_args.kwargs["timeout"], fetch.TIMEOUT)
        self.assertEqual(opening.call_args.args[0].get_header("User-agent"), fetch.USER_AGENT)

    def test_mlh_server_rendered_online_flag_and_utc_dates(self):
        items = [{"name": "Digital Week", "formatType": "digital",
                  "startsAt": "2026-10-18T14:00:00Z", "endsAt": "2026-10-24T17:00:00Z",
                  "websiteUrl": "https://example.com/digital", "url": "/events/digital/prizes"}]
        items.append(dict(items[0], name="Campus", formatType="physical"))
        raw = json.dumps({"props": {"upcomingEvents": items, "pastEvents": []}})
        result = fetch.parse_mlh(f'<script type="application/json" data-page="app">{raw}</script>')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Digital Week")
        self.assertEqual(result[0]["deadline"], "2026-10-24T17:00:00Z")
        with self.assertRaises(ValueError):
            fetch.parse_mlh("<html>Changed layout</html>")

    def test_optional_lablab_json_ld(self):
        raw = json.dumps({"@graph": [{"@type": "Event", "name": "AI Week",
            "url": "https://lablab.ai/example", "startDate": "2026-10-18",
            "endDate": "2026-10-25", "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode"}]})
        result = fetch.parse_lablab(f'<script type="application/ld+json">{raw}</script>')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "lablab.ai")
        with self.assertRaises(ValueError):
            fetch.parse_lablab('<script type="application/ld+json">{"@type":"ItemList"}</script>')


class CalendarTests(unittest.TestCase):
    def test_utf8_folding_and_crlf(self):
        for text in ("DESCRIPTION:" + "해커톤, AI; 개발자 🚀 " * 30,
                     "URL:" + "a" * 200, "X:" + " " * 72 + "🚀" * 10):
            with self.subTest(text=text):
                folded = build.fold_line(text)
                self.assertEqual(folded.replace("\r\n ", ""), text)
                self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in folded.split("\r\n")))
        data = build.render_calendar([event(title="한글 해커톤 🚀 " * 20)], NOW)
        self.assertTrue(data.endswith(b"\r\n"))
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertNotIn(b"\r", data.replace(b"\r\n", b""))
        for line in data.split(b"\r\n"):
            self.assertLessEqual(len(line), 75)
            line.decode("utf-8")  # A fold must never split a code point.

    def test_deadline_event_uid_stamp_and_two_alarms(self):
        item = event()
        text = build.render_calendar([item], NOW).decode().replace("\r\n ", "")
        self.assertIn(f"UID:{item['id']}@kks0488.github.io\r\n", text)
        self.assertIn("DTSTAMP:20261016T123000Z\r\n", text)
        self.assertIn("X-WR-CALNAME:Hackathon Tracker\r\n", text)
        self.assertIn("DTSTART;VALUE=DATE:20261115\r\n", text)
        self.assertIn("DTEND;VALUE=DATE:20261116\r\n", text)
        self.assertEqual(text.count("BEGIN:VALARM\r\n"), 2)
        self.assertIn("TRIGGER:-P3D\r\n", text)
        self.assertIn("TRIGGER:-P1D\r\n", text)
        self.assertIn("Prize: $10\\,000 & credits\\nOrganizer: Example & Co.", text)
        self.assertIn("Themes: Machine Learning/AI\\, Web\\n", text)
        self.assertIn("URL: https://example.devpost.com", text)

    def test_timed_event_is_utc_and_markdown_is_kst(self):
        item = event(deadline="2026-11-15T18:30:00Z")
        text = build.render_calendar([item], NOW).decode()
        self.assertIn("DTSTART:20261115T183000Z\r\n", text)
        self.assertNotIn("VALUE=DATE", text)
        self.assertEqual(build.deadline_kst(item["deadline"]), "2026-11-16 03:30 KST")

    def test_ics_escaping(self):
        self.assertEqual(build.escape_ics("one\\two;three,four\r\nfive"),
                         "one\\\\two\\;three\\,four\\nfive")

    def test_projects_preserved_markdown_sorted_and_repeat_build(self):
        before = build.project_section(PROJECTS)
        text = build.render_markdown([event(), event(title="Earlier", deadline="2026-10-20")], PROJECTS, NOW)
        self.assertEqual(build.project_section(text), before)
        self.assertLess(text.index("[Earlier]"), text.index("[Online AI Hackathon]"))
        self.assertIn("Last updated: 2026-10-16 12:30 UTC", text)
        self.assertIn("2026-11-15 (시각 미제공)", text)
        self.assertEqual(build.render_markdown([event()], PROJECTS, NOW),
                         build.render_markdown([event()], text, NOW))

    def test_remote_table_text_is_escaped(self):
        value = build.markdown_cell("[title] | <script>\nnext")
        self.assertNotIn("|", value)
        self.assertNotIn("<script>", value)
        self.assertNotIn("\n", value)
        self.assertNotIn("[", value)


if __name__ == "__main__":
    unittest.main()
