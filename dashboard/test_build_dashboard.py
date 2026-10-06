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

    def test_missing_columns(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.csv"
            p.write_text("contract_id,title\nC-1,x\n", encoding="utf-8")
            self.assertEqual(bd.main(["--register", str(p), "--out", str(Path(d) / "o.html")]), 1)

    def test_bad_today(self):
        self.assertEqual(bd.main(["--register", str(SAMPLE), "--today", "abc"]), 2)


if __name__ == "__main__":
    unittest.main()
