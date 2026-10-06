import base64
import csv
import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path

import build_dashboard as bd

SAMPLE = Path(__file__).resolve().parent / "sample_register.csv"
TODAY = dt.date(2026, 10, 7)


def row(**kw):
    base = {"status": "有效", "end_date": "", "notice_days": "", "renewal_type": "書面續約"}
    base.update(kw)
    return base


class EnrichTest(unittest.TestCase):
    def test_days_and_notice_deadline(self):
        r = bd.enrich(row(end_date="2026-11-30", notice_days="60", renewal_type="自動續約"), TODAY)
        self.assertEqual(r["days_to_end"], 54)
        self.assertEqual(r["notice_deadline"], "2026-10-01")
        self.assertEqual(r["days_to_notice"], -6)
        self.assertFalse(r["is_notice_due"])  # 通知截止日已過

    def test_notice_due_within_window(self):
        r = bd.enrich(row(end_date="2026-12-15", notice_days="30", renewal_type="自動續約"), TODAY)
        self.assertTrue(r["is_notice_due"])
        self.assertTrue(r["is_expiring"])

    def test_manual_renewal_is_not_notice_due(self):
        r = bd.enrich(row(end_date="2026-12-15", notice_days="30"), TODAY)
        self.assertFalse(r["is_notice_due"])

    def test_active_past_end_is_expired(self):
        r = bd.enrich(row(end_date="2026-09-30"), TODAY)
        self.assertTrue(r["is_expired"])
        self.assertFalse(r["is_active"])

    def test_boundaries(self):
        self.assertTrue(bd.enrich(row(end_date="2026-10-07"), TODAY)["is_expiring"])
        self.assertTrue(bd.enrich(row(end_date="2027-01-05"), TODAY)["is_expiring"])
        self.assertFalse(bd.enrich(row(end_date="2027-01-06"), TODAY)["is_expiring"])

    def test_no_end_date(self):
        r = bd.enrich(row(renewal_type="無固定期限"), TODAY)
        self.assertTrue(r["is_active"])
        self.assertIsNone(r["days_to_end"])
        self.assertFalse(r["is_expiring"])

    def test_non_active_status_not_counted(self):
        r = bd.enrich(row(status="審閱中", end_date="2026-10-31"), TODAY)
        self.assertFalse(r["is_active"] or r["is_expiring"] or r["is_expired"])


class SampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = bd.build_payload(SAMPLE, TODAY)
        cls.html = bd.render(cls.payload)

    def test_row_count(self):
        self.assertEqual(len(self.payload["rows"]), 13)

    def test_summary(self):
        self.assertEqual(self.payload["summary"],
                         {"active": 9, "expiring": 6, "notice_due": 1, "expired": 2})

    def test_filter_options(self):
        f = {x["key"]: x["options"] for x in self.payload["filters"]}
        self.assertIn("採購", f["department"])
        self.assertIn("房東", f["counterparty_category"])
        self.assertIn("不動產租賃", f["contract_type"])
        self.assertIn("已被續約取代", f["status"])
        self.assertEqual(f["status"], sorted(set(f["status"])))

    def test_html_is_self_contained(self):
        self.assertNotRegex(self.html, r'(src|href)="https?://')
        self.assertNotIn("__DATA__", self.html)
        data = re.search(r'<script id="data" type="application/json">(.*?)</script>', self.html, re.S).group(1)
        self.assertEqual(len(json.loads(data)["rows"]), 13)

    def test_script_close_tag_escaped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.csv"
            header = SAMPLE.read_text(encoding="utf-8-sig").splitlines()[0]
            p.write_text(header + "\nC-1,</script><b>x,,,,,,,,有效,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n", encoding="utf-8")
            html = bd.render(bd.build_payload(p, TODAY))
            self.assertEqual(html.count("</script>"), 2)


class CliTest(unittest.TestCase):
    def test_main_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.html"
            self.assertEqual(bd.main(["--register", str(SAMPLE), "--out", str(out), "--today", "2026-10-07"]), 0)
            self.assertTrue(out.read_text(encoding="utf-8").startswith("<!doctype html>"))

    def test_missing_columns_render_blank(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.csv"
            p.write_text("contract_id,title\nC-1,x\n", encoding="utf-8")
            self.assertEqual(bd.main(["--register", str(p), "--out", str(Path(d) / "o.html")]), 0)
            payload = bd.build_payload(p, TODAY)
            self.assertEqual(payload["rows"][0]["title"], "x")
            self.assertNotIn("status", payload["rows"][0])
            self.assertIsNone(payload["rows"][0]["days_to_end"])

    def test_bad_today(self):
        self.assertEqual(bd.main(["--register", str(SAMPLE), "--today", "abc"]), 2)


class SchemaAndLogoTest(unittest.TestCase):
    def test_schema_labels_and_added_fields(self):
        with tempfile.TemporaryDirectory() as d:
            schema = json.loads(bd.DEFAULT_FIELDS.read_text())
            next(f for f in schema["fields"] if f["name"] == "title")["label"] = "契約名稱"
            schema["fields"] = [f for f in schema["fields"]
                                if f["name"] not in {"contract_language", "dispute_resolution"}]
            schema["fields"].extend([
                {"name": "contract_language", "label": "合約語言", "type": "string"},
                {"name": "dispute_resolution", "label": "爭議解決", "type": "string"},
                {"name": "custom_field", "label": "新增欄位", "type": "string"},
            ])
            p = Path(d) / "fields.json"
            p.write_text(json.dumps(schema))
            payload = bd.build_payload(SAMPLE, TODAY, p)
            labels = {f["name"]: f["label"] for f in payload["columns"]}
            self.assertEqual(labels["title"], "契約名稱")
            self.assertEqual(labels["contract_language"], "合約語言")
            self.assertEqual(labels["dispute_resolution"], "爭議解決")
            self.assertIn("custom_field", {f["name"] for f in payload["fields"]})
            self.assertEqual(payload["rows"][0].get("contract_language", ""), "")

    def test_governing_law_filter_uses_schema_label(self):
        payload = bd.build_payload(SAMPLE, TODAY)
        f = next(f for f in payload["filters"] if f["key"] == "governing_law")
        self.assertEqual(f["label"], "準據法")
        self.assertIn("中華民國法", f["options"])

    def test_empty_register(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "empty.csv"
            p.write_text("contract_id,title\n")
            self.assertEqual(bd.build_payload(p, TODAY)["rows"], [])

    def test_short_row_and_missing_id(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "short.csv"
            p.write_text("title,status,end_date\nOnly title\n")
            payload = bd.build_payload(p, TODAY)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["end_date"], "")

    def test_source_refs_are_preserved_and_script_safe(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "refs.csv"
            refs = '{"title":{"page":2,"quote":"</script><img src=x>"}}'
            with p.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["contract_id", "source_refs"])
                writer.writeheader()
                writer.writerow({"contract_id": "C-1", "source_refs": refs})
            payload = bd.build_payload(p, TODAY)
            out = bd.render(payload)
            embedded = re.search(r'<script id="data" type="application/json">(.*?)</script>', out, re.S).group(1)
            self.assertEqual(json.loads(embedded)["rows"][0]["source_refs"], refs)
            self.assertEqual(out.count("</script>"), 2)

    def test_logo_is_embedded_only_when_requested(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "generic.png"
            data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1kAAAAASUVORK5CYII=")
            p.write_bytes(data)
            logo = bd.logo_data_uri(p)
            self.assertEqual(base64.b64decode(logo.split(",", 1)[1]), data)
            payload = bd.build_payload(SAMPLE, TODAY)
            self.assertNotIn('<img src=', bd.render(payload))
            self.assertIn('<img src="data:image/png;base64,', bd.render(payload, logo))
            out = Path(d) / "logo.html"
            self.assertEqual(bd.main(["--register", str(SAMPLE), "--out", str(out), "--logo", str(p)]), 0)
            self.assertIn(logo, out.read_text())

    def test_unsupported_logo_reports_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "text.png"
            p.write_text("not an image")
            out = Path(d) / "out.html"
            self.assertEqual(bd.main(["--register", str(SAMPLE), "--out", str(out), "--logo", str(p)]), 1)
            self.assertFalse(out.exists())

    def test_missing_logo_reports_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(bd.main(["--register", str(SAMPLE), "--out", str(Path(d)/"out.html"),
                                      "--logo", str(Path(d)/"missing.png")]), 1)


if __name__ == "__main__":
    unittest.main()
