import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import build_register as br

FIELDS = json.loads(br.DEFAULT_FIELDS.read_text(encoding="utf-8"))["fields"]
BODY = """<!-- page: 1 -->
本合約由本公司股份有限公司與甲供應商股份有限公司簽訂。
<!-- page: 2 -->
第5條 本合約有效期間至 2026 年 11 月 30 日止。
"""
SRC = b"original-bytes"


def meta(**over):
    m = {f["name"]: "" for f in FIELDS}
    m.update({
        "contract_id": "C-2026-0001", "title": "測試合約", "contract_type": "服務", "department": "資訊",
        "our_entity": "本公司股份有限公司", "counterparty_name": "甲供應商股份有限公司",
        "counterparty_category": "供應商", "status": "有效", "end_date": "2026-11-30",
        "renewal_type": "未載明", "updated_at": "2026-10-07",
        "source_path": "a.pdf", "source_sha256": hashlib.sha256(SRC).hexdigest(),
        "verification_status": "已驗證",
        "citations": [
            {"field": "our_entity", "page": 1, "clause": "前言", "quote": "本公司股份有限公司與甲供應商股份有限公司簽訂"},
            {"field": "counterparty_name", "page": 1, "clause": "前言", "quote": "甲供應商股份有限公司簽訂"},
            {"field": "end_date", "page": 2, "clause": "第5條", "quote": "有效期間至 2026 年 11 月 30 日止"},
            {"field": "title", "page": 1, "clause": "前言", "quote": "本合約"},
        ],
    })
    m.update(over)
    return m


def write(directory, name, m, body=BODY):
    (Path(directory) / name).write_text(br.dump_frontmatter(m) + body, encoding="utf-8")


class FrontmatterTest(unittest.TestCase):
    def test_roundtrip(self):
        m = meta(notes='含"引號"與換行\n第二行')
        parsed, body = br.split_document(br.dump_frontmatter(m) + BODY)
        self.assertEqual(parsed["notes"], m["notes"])
        self.assertEqual(parsed["citations"], m["citations"])
        self.assertIn("<!-- page: 2 -->", body)

    def test_no_frontmatter(self):
        self.assertEqual(br.split_document("# 標題\n")[0], None)

    def test_empty_converter_lists_keep_their_type(self):
        m = meta(ocr_pages=[], warnings=[])
        parsed, _ = br.split_document(br.dump_frontmatter(m) + BODY)
        self.assertEqual(parsed["ocr_pages"], [])
        self.assertEqual(parsed["warnings"], [])

    def test_bad_line(self):
        with self.assertRaises(ValueError):
            br.split_document("---\n壞掉的行\n---\n內文")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, **kw):
        return br.build(self.dir, **kw)

    def test_valid_contract_is_written(self):
        write(self.dir, "a.md", meta())
        rows, problems = self.run_build()
        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["counterparty_name"], "甲供應商股份有限公司")
        self.assertEqual(list(rows[0]), [f["name"] for f in FIELDS])

    def test_foreign_contract_fields_need_verbatim_citations(self):
        values = {
            "contract_language": "英文", "currency": "USD",
            "governing_law": "中華民國法", "dispute_resolution": "仲裁",
            "dispute_forum": "合約明載機構", "dispute_location": "臺北",
        }
        m = meta(contract_type="海外經銷", **values)
        body = BODY + "\n第6條 " + "；".join(values.values())
        write(self.dir, "a.md", m, body)
        rows, problems = self.run_build()
        self.assertEqual(rows, [])
        for name in values:
            self.assertTrue(any(name in error for error in problems[0][1]))
        m["citations"].extend({"field": name, "page": 2, "clause": "第6條", "quote": value}
                              for name, value in values.items())
        write(self.dir, "a.md", m, body)
        rows, problems = self.run_build()
        self.assertEqual(problems, [])
        for name, value in values.items():
            self.assertEqual(rows[0][name], value)

    def test_old_optional_fields_remain_readable_but_distribution_needs_confirmation(self):
        m = meta()
        for name in ("contract_language", "dispute_resolution", "dispute_forum", "dispute_location"):
            m.pop(name)
        write(self.dir, "a.md", m)
        rows, problems = self.run_build()
        self.assertEqual(problems, [])
        self.assertEqual(rows[0]["dispute_location"], "")
        write(self.dir, "a.md", {**m, "contract_type": "經銷代理"})
        rows, problems = self.run_build()
        self.assertEqual(rows, [])
        self.assertTrue(any("contract_type" in error for error in problems[0][1]))

    def test_quote_not_in_text_is_rejected(self):
        m = meta()
        m["citations"][2]["quote"] = "有效期間至 2027 年 11 月 30 日止"
        write(self.dir, "a.md", m)
        rows, problems = self.run_build()
        self.assertEqual(rows, [])
        self.assertIn("quote 不在第 2 頁原文中", problems[0][1][0])

    def test_quote_on_wrong_page_is_rejected(self):
        m = meta()
        m["citations"][2]["page"] = 1
        write(self.dir, "a.md", m)
        self.assertEqual(self.run_build()[0], [])

    def test_missing_citation_is_rejected(self):
        m = meta(governing_law="中華民國法")
        write(self.dir, "a.md", m)
        rows, problems = self.run_build()
        self.assertEqual(rows, [])
        self.assertTrue(any("governing_law：有值但沒有 citations" in e for e in problems[0][1]))

    def test_unstated_needs_no_citation(self):
        write(self.dir, "a.md", meta(governing_law="未載明"))
        self.assertEqual(len(self.run_build()[0]), 1)

    def test_unverified_blocked_unless_allowed(self):
        write(self.dir, "a.md", meta(verification_status="驗證不符"))
        self.assertEqual(self.run_build()[0], [])
        self.assertEqual(len(self.run_build(allow_unverified=True)[0]), 1)

    def test_invalid_enum_and_date(self):
        write(self.dir, "a.md", meta(status="進行中", effective_date="2026/01/01"))
        errors = self.run_build()[1][0][1]
        self.assertTrue(any("status" in e for e in errors))
        self.assertTrue(any("effective_date" in e for e in errors))

    def test_duplicate_contract_id(self):
        write(self.dir, "a.md", meta())
        write(self.dir, "b.md", meta())
        rows, problems = self.run_build()
        self.assertEqual(len(rows), 1)
        self.assertIn("重複", problems[0][1][-1])

    def test_history_is_excluded_at_any_depth(self):
        write(self.dir, "current.md", meta())
        for name in ("_history", "nested/_history"):
            history = self.dir / name
            history.mkdir(parents=True)
            write(history, "old.md", meta())
            (history / "broken.md").write_text("---\nbroken\n---", encoding="utf-8")
        rows, problems = self.run_build()
        self.assertEqual(len(rows), 1)
        self.assertEqual(problems, [])

    def test_needs_review_blocks_even_verified_and_draft(self):
        write(self.dir, "a.md", meta(needs_review=True))
        for allow in (False, True):
            rows, problems = self.run_build(allow_unverified=allow)
            self.assertEqual(rows, [])
            self.assertTrue(any("needs_review 為 true" in e for e in problems[0][1]))
        write(self.dir, "a.md", meta(needs_review=False))
        self.assertEqual(len(self.run_build()[0]), 1)

    def test_docx_clause_only_citations_pass(self):
        m = meta(source_path="a.docx")
        for c in m["citations"]:
            c["page"] = None
        body = br.PAGE_RE.sub("", BODY)
        write(self.dir, "a.docx.md", m, body)
        rows, problems = self.run_build()
        self.assertEqual(len(rows), 1)
        self.assertEqual(problems, [])

    def test_citation_without_page_or_clause_is_rejected(self):
        m = meta(source_path="a.docx")
        m["citations"][0].update(page=None, clause=" ")
        write(self.dir, "a.md", m)
        rows, problems = self.run_build()
        self.assertEqual(rows, [])
        self.assertTrue(any("須有頁碼或條號" in e for e in problems[0][1]))

    def test_page_requires_marker_even_with_clause(self):
        write(self.dir, "a.md", meta(), br.PAGE_RE.sub("", BODY))
        rows, problems = self.run_build()
        self.assertEqual(rows, [])
        self.assertTrue(any("頁標記" in e for e in problems[0][1]))

    def test_quote_is_verbatim_including_whitespace(self):
        m = meta()
        m["citations"][2]["quote"] = "有效期間至2026年11月30日止"
        write(self.dir, "a.md", m)
        self.assertEqual(self.run_build()[0], [])

    def test_source_hash_check(self):
        src = self.dir / "src"
        src.mkdir()
        (src / "a.pdf").write_bytes(SRC)
        md = self.dir / "md"
        md.mkdir()
        write(md, "a.md", meta())
        self.assertEqual(len(br.build(md, source_root=src)[0]), 1)
        (src / "a.pdf").write_bytes(b"changed")
        self.assertEqual(br.build(md, source_root=src)[0], [])

    def test_main_writes_csv_with_bom(self):
        write(self.dir, "a.md", meta())
        out = self.dir / "register.csv"
        self.assertEqual(br.main(["--md-dir", str(self.dir), "--out", str(out)]), 0)
        raw = out.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbfcontract_id,"))
        self.assertEqual(raw.decode("utf-8-sig").count("\r\n"), 2)


if __name__ == "__main__":
    unittest.main()
