"""Exercise the actual local server and portable documentation sitemap."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

DASHBOARD = Path(__file__).resolve().parent


class DocumentationServerTest(unittest.TestCase):
    def setUp(self):
        node = shutil.which('node')
        modules = DASHBOARD / 'node_modules'
        if not node or not (modules / 'json-server/package.json').exists():
            self.skipTest('Node and npm ci are required for real-server integration tests')
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        shutil.copyfile(DASHBOARD / 'start.mjs', root / 'start.mjs')
        (root / 'app').mkdir()
        (root / 'app/index.html').write_text('<h1>Contract application</h1>')
        (root / 'data').mkdir()
        (root / 'data/db.json').write_text(json.dumps({'contracts': [], 'cases': []}))
        site = root / 'docs-site/site'
        site.mkdir(parents=True)
        (site / 'index.html').write_text('<h1>Documentation</h1>')
        (site / 'sitemap.xml').write_text(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><loc>http://localhost/docs/index.html</loc></url>'
            '<url><loc>http://localhost/docs/contracts/review.html</loc></url></urlset>'
        )
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.base = f'http://127.0.0.1:{self.port}'
        self.server = subprocess.Popen(
            [node, str(root / 'start.mjs'), str(self.port)],
            cwd=root, env={**os.environ, 'CONTRACT_NODE_MODULES': str(modules),
                           'CONTRACT_ALLOWED_ORIGINS': 'https://demo.invalid:8444'},
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop_server)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                self.fail(self.server.stderr.read().decode())
            try:
                urllib.request.urlopen(self.base, timeout=1).close()
                break
            except urllib.error.URLError:
                time.sleep(.05)
        else:
            self.fail('Server failed to become ready')

    def stop_server(self):
        if self.server.poll() is None:
            self.server.terminate()
            self.server.wait(timeout=10)
        self.server.stderr.close()

    def test_docs_and_api_are_served_without_changing_database(self):
        with urllib.request.urlopen(self.base + '/docs/index.html') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'Documentation', response.read())
        with urllib.request.urlopen(self.base + '/contracts') as response:
            self.assertEqual(json.load(response), [])

    def test_sitemap_matches_actual_local_port_and_preserves_page_paths(self):
        with urllib.request.urlopen(self.base + '/docs/sitemap.xml') as response:
            self.assertIn('application/xml', response.headers['Content-Type'])
            root = ET.fromstring(response.read())
        urls = [node.text for node in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(urls, [self.base + '/docs/index.html', self.base + '/docs/contracts/review.html'])

    def test_explicit_proxy_origin_in_sitemap_does_not_allow_external_api_writes(self):
        request = urllib.request.Request(self.base + '/docs/sitemap.xml', headers={'Host': 'demo.invalid:8444'})
        with urllib.request.urlopen(request) as response:
            self.assertIn(b'https://demo.invalid:8444/docs/index.html', response.read())
        request = urllib.request.Request(self.base + '/cases', data=b'{"id":"blocked"}',
                                         headers={'Origin': 'https://demo.invalid:8444', 'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request)
        self.assertEqual(raised.exception.code, 403)
        with urllib.request.urlopen(self.base + '/cases') as response:
            self.assertEqual(json.load(response), [])
