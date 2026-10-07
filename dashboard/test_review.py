import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_dashboard as build
import import_review as importer


def string(text): return {'t': 'Str', 'c': text}
def span(cls, text, attrs=()): return {'t': 'Span', 'c': [['', [cls], list(attrs)], [string(text)] if text else []]}
def fixture():
    return {'blocks': [{'t': 'Para', 'c': [string('第1條 付款')]}, {'t': 'Para', 'c': [string('應於'), span('deletion', '30', [('author', '範例甲'), ('date', '2026-10-07T00:00:00Z')]), span('insertion', '60', [('author', '範例甲'), ('date', '2026-10-07T00:00:00Z')]), span('comment-start', '請確認', [('id', '0'), ('author', '範例乙'), ('date', '2026-10-07T00:00:01Z')]), string('日內付款'), span('comment-end', '', [('id', '0')])]}]}

class ReviewTests(unittest.TestCase):
    def test_track_changes_and_anchored_comment(self):
        clauses, comments, changes = importer.convert(fixture())
        self.assertEqual(clauses[0]['before'], '第1條 付款\n應於30日內付款')
        self.assertEqual(clauses[0]['after'], '第1條 付款\n應於60日內付款')
        self.assertEqual(comments[0]['selector']['exact'], '日內付款')
        self.assertEqual(comments[0]['user'], '範例乙')
        self.assertEqual([c['type'] for c in changes], ['delete', 'insert'])

    def test_unclosed_word_comment_rejected(self):
        ast = fixture(); ast['blocks'][1]['c'].pop()
        with self.assertRaisesRegex(ValueError, '未結束'): importer.convert(ast)

    def test_import_rebuild_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / 'C1'; case.mkdir(); (case/'index.md').write_text(importer.markdown({'case_id': 'C1'}))
            with patch('import_review.subprocess.check_output', return_value=json.dumps(fixture())) as call:
                self.assertEqual(importer.import_document('source.docx', case), (1, 1))
                self.assertIn('--track-changes=all', call.call_args[0][0])
                original = (case/'review/versions/V1.md').read_bytes()
                with self.assertRaisesRegex(ValueError, '不覆寫'): importer.import_document('source.docx', case)
                self.assertEqual((case/'review/versions/V1.md').read_bytes(), original)
            data = build.read_review(case)
            self.assertEqual(len(data['comments']), 1)
            self.assertEqual(data['versions'][1]['clauses'][0]['text'], '第1條 付款\n應於60日內付款')

    def test_invalid_anchor_prevents_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            case=Path(temp); (case/'review/versions').mkdir(parents=True); (case/'review/comments').mkdir()
            (case/'review/versions/V1.md').write_text(importer.markdown({'version_id':'V1','clauses':[{'id':'1','text':'原文'}]}))
            (case/'review/comments/1.md').write_text(importer.markdown({'id':'a','thread_id':'a','version_id':'V1','clause_id':'1','user':'甲','time':'2026-10-07T00:00:00Z','action':'comment','selector':{'type':'TextQuoteSelector','exact':'不存在'}},'意見'))
            with self.assertRaisesRegex(ValueError,'錨點'): build.read_review(case)

    def test_empty_author_and_naive_time_fail(self):
        for user, time in [('', '2026-10-07T00:00:00Z'), ('甲','2026-10-07T00:00:00')]:
            with tempfile.TemporaryDirectory() as temp:
                case=Path(temp); (case/'review/comments').mkdir(parents=True)
                (case/'review/comments/1.md').write_text(importer.markdown({'user':user,'time':time}))
                with self.assertRaises(ValueError): build.read_review(case)
