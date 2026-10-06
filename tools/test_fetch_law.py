import datetime as dt
import io
import json
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import fetch_law as law

NOW = dt.datetime(2026, 10, 7, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
PAGE = '''<table><tr><th>法規名稱：</th><td><a id="hlLawName" href="LawAll.aspx?pcode=B0000001">測試法</a><span>EN</span></td></tr>
<tr><th>修正日期：</th><td>民國 113 年 05 月 15 日</td></tr>{state}</table>
<div class="law-reg"><div class="row"><div class="col-no"><a>第 1 條</a></div>
<div class="col-data"><div class="law-article"><div>第一項內容。</div><div>第二項內容。</div></div></div></div>
<div class="row"><div class="col-no">第 2-1 條</div><div class="col-data">{text}</div></div></div>'''
STATE = '''<tr><th>生效狀態：</th><td>部分條文尚未生效<br>施行日期另定。
<a id="hyLawCon" href="/LawClass/LawOldVer.aspx?pcode=B0000001">連結舊法規內容</a></td></tr>'''


def page(state="", text="本條內容。"):
    return PAGE.format(state=state, text=text).encode()


def package(name="測試法", url=law.BASE + "/LawClass/LawAll.aspx?pcode=B0000001", abandoned="", kind="law"):
    data = {"UpdateDate": "2026/9/24", "Laws": [{"LawName": name, "LawURL": url, "LawAbandonNote": abandoned}]}
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("ChLaw.json" if kind == "law" else "ChOrder.json", json.dumps(data))
    return result.getvalue()


class FetchTest(unittest.TestCase):
    def test_cache_has_source_dates_article_and_paragraphs(self):
        with tempfile.TemporaryDirectory() as directory:
            target, pending = law.fetch_law("b0000001", directory, fetch=lambda _: page(), clock=NOW)
            text = target.read_text()
            self.assertEqual(target.name, "測試法.md")
            self.assertFalse(pending)
            self.assertIn('law_modified_date: "2024-05-15"', text)
            self.assertIn('fetched_date: "2026-10-07"', text)
            self.assertIn('source_url: "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B0000001"', text)
            self.assertIn("第一項內容。\n第二項內容。", text)
            self.assertIn("### 第 2-1 條", text)
            self.assertIn("以全國法規資料庫現行條文為準", text)
            self.assertNotIn("測試法EN", text)

    def test_pending_keeps_both_versions_without_claiming_effective(self):
        urls = []
        def fake(url):
            urls.append(url)
            return page(STATE, "新公布內容。") if "LawAll" in url else page(text="舊版本內容。")
        with tempfile.TemporaryDirectory() as directory:
            target, pending = law.fetch_law("B0000001", directory, fetch=fake, clock=NOW)
            text = target.read_text()
            self.assertTrue(pending)
            self.assertEqual(len(urls), 2)
            self.assertIn("current_text_verified: false", text)
            self.assertIn("新公布內容。", text)
            self.assertIn("舊版本內容。", text)
            self.assertIn("施行日期另定。", text)
            self.assertIn("previous_source_url:", text)

    def test_failure_preserves_existing_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "測試法.md"
            target.write_text("已有內容")
            def failure(url):
                if "LawOldVer" in url:
                    raise urllib.error.URLError("offline")
                return page(STATE)
            with self.assertRaises(urllib.error.URLError):
                law.fetch_law("B0000001", directory, fetch=failure, clock=NOW)
            self.assertEqual(target.read_text(), "已有內容")
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_missing_old_link_does_not_claim_current(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            law.fetch_law("B0000001", directory,
                          fetch=lambda _: page('<tr><th>生效狀態：</th><td>尚未生效</td></tr>'))

    def test_rejects_bad_code_before_fetch(self):
        with self.assertRaises(ValueError):
            law.fetch_law("../bad", fetch=lambda _: self.fail("不應下載"))

    def test_rejects_wrong_law_returned_by_official_page(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            law.fetch_law("I0020001", directory, fetch=lambda _: page(), clock=NOW)

    def test_rejects_error_page_duplicate_articles_and_missing_date(self):
        for raw in (b"<h1>Error</h1>", page().replace(b"2-1", b"1"),
                    page().replace("民國 113 年 05 月 15 日".encode(), b"")):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                law.parse_page(raw)

    def test_rejects_abandoned_page(self):
        raw = page().replace(b"</table>", '<tr><th>廢止日期：</th><td>民國 113 年 01 月 01 日</td></tr></table>'.encode())
        with self.assertRaises(ValueError):
            law.parse_page(raw)

    def test_name_lookup_uses_official_zip_exact_match(self):
        code, source, updated = law.resolve_name("測試法", fetch=lambda _: package())
        self.assertEqual(code, "B0000001")
        self.assertEqual(source, law.BASE + "/api/ch/law/json")
        self.assertEqual(updated, "2026/9/24")

    def test_name_lookup_falls_through_to_orders(self):
        seen = []
        def fake(url):
            seen.append(url)
            return package(name="另一法律") if "/law/" in url else package(kind="order")
        self.assertEqual(law.resolve_name("測試法", fetch=fake)[0], "B0000001")
        self.assertEqual(len(seen), 2)

    def test_name_lookup_rejects_not_found_abandoned_and_external_source(self):
        for data in (package(name="不符全名"), package(abandoned="廢止"), package(url="https://example.org/law")):
            with self.subTest(), self.assertRaises(ValueError):
                law.resolve_name("測試法", fetch=lambda _: data, category="law")

    def test_external_redirect_is_rejected(self):
        with self.assertRaises(ValueError):
            law.OfficialRedirect().redirect_request(None, None, 302, "", {}, "https://example.org/law")

    def test_cli_uses_mock_network_and_handles_network_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(law, "download", return_value=page()) as mock:
            # 將命令列路由的下載替身傳入執行函式，避免預設參數綁定真網路。
            original = law.fetch_law
            with patch.object(law, "fetch_law", side_effect=lambda code, folder, **kw:
                              original(code, folder, fetch=mock, clock=NOW, **kw)):
                self.assertEqual(law.main(["--code", "B0000001", "--cache-dir", directory]), 0)
                self.assertTrue((Path(directory) / "測試法.md").exists())
        with patch.object(law, "fetch_law", side_effect=urllib.error.URLError("offline")):
            self.assertEqual(law.main(["--code", "B0000001"]), 1)


if __name__ == "__main__":
    unittest.main()
