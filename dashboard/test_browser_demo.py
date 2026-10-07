import json
import tempfile
import unittest
import io
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

try:
    from .build_demo import build
    from .build_dashboard import build_payload
    from . import build_dashboard as dashboard_builder
except ImportError:
    from build_demo import build
    from build_dashboard import build_payload
    import build_dashboard as dashboard_builder


class BrowserDemoPackagingTest(unittest.TestCase):
    def test_api_import_updates_provenance_alongside_fields(self):
        old = {'id': 'internal-1', 'fields': {'contract_id': 'C-1', 'title': '舊名稱', 'owner': '保留'}, 'original_clauses': []}
        collections = {name: [] for name in ('contracts', 'cases', 'progress', 'review_versions', 'review_comments')}
        collections['contracts'] = [old]
        clauses = [{'clause_id': '1', 'text': '新版本原文'}]
        seed = {**collections, 'config': {}}
        seed['contracts'] = [{'id': 'C-1', 'fields': {'title': '新名稱'}, 'original_clauses': clauses, 'original_status': 'available'}]
        writes = []

        def api(request, timeout):
            path = urlparse(request.full_url).path.strip('/')
            if request.get_method() == 'GET':
                value = collections[path]
            else:
                value = json.loads(request.data)
                writes.append((path, value))
            return io.BytesIO(json.dumps(value).encode())

        with patch.object(dashboard_builder.urllib.request, 'urlopen', side_effect=api):
            dashboard_builder.import_api(seed, 'http://127.0.0.1:3000')
        saved = next(value for path, value in writes if path == 'contracts/internal-1')
        self.assertEqual(saved['fields']['owner'], '保留')
        self.assertEqual(saved['original_clauses'], clauses)
        self.assertEqual(saved['original_status'], 'available')

    def test_markdown_import_retains_clause_anchors_outside_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'sample.md').write_text('---\ncontract_id: "DEMO-1"\ntitle: "範例"\noriginal_status: "available"\noriginal_clauses: [{"clause_id":"1","text":"原文"}]\ndemo: true\ndemo_fields: ["title"]\n---\n第 1 條 原文\n', encoding='utf-8')
            record = build_payload(None, date(2026, 10, 7), markdown_dir=root)['records']['contracts'][0]
            self.assertTrue(record['demo'])
            self.assertEqual(record['original_clauses'][0]['clause_id'], '1')
            self.assertNotIn('original_clauses', record['fields'])

    def test_packages_shared_application_and_external_script_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            seed = {"config": {"schema": {"fields": []}}}
            seed.update({name: [] for name in ("contracts", "cases", "progress", "review_versions", "review_comments")})
            database = root / "db.json"
            database.write_text(json.dumps(seed), encoding="utf-8")
            output = build(database, root / "demo")
            source = Path(__file__).parent / "app"
            for name in ("app.js", "app.css", "datasource.js"):
                self.assertEqual((output / name).read_bytes(), (source / name).read_bytes())
            html = (output / "index.html").read_text()
            self.assertLess(html.index('src="demo-data.js"'), html.index('src="browser-datasource.js"'))
            self.assertLess(html.index('src="browser-datasource.js"'), html.index('src="app.js"'))
            self.assertTrue((output / "demo-data.js").read_text().startswith("window.CONTRACT_DEMO_DATA="))

    def test_invalid_seed_rejected_before_output_is_created(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database = root / "db.json"
            database.write_text('{}')
            with self.assertRaisesRegex(ValueError, "schema"):
                build(database, root / "demo")
            self.assertFalse((root / "demo").exists())
