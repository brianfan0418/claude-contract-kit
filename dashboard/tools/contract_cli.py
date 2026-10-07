#!/usr/bin/env python3
"""AI 透過本機 REST 管理合約；禁止直接改 db.json。"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_SCHEMA = Path(__file__).resolve().parents[2] / 'schema' / 'fields.json'


def validate_fields(fields, schema, is_case=False, previous=None):
    result = dict(fields)
    for f in schema['fields']:
        if previous is not None and (f['name'] not in fields or fields[f['name']] == previous.get(f['name'], '')):
            continue
        raw = fields.get(f['name'], '')
        if isinstance(raw, (dict, list, bool)) or (raw is not None and f['type'] not in ('number', 'integer') and not isinstance(raw, str)):
            raise ValueError(f"{f['label']}須為文字或數值，結構資料請提供 JSON 字串")
        value = '' if raw is None else str(raw).strip()
        result[f['name']] = value
        if f.get('required') and not value and not (is_case and f['name'] == 'contract_id'):
            raise ValueError(f"請填{f['label']}")
        if not value:
            continue
        try:
            if f['type'] == 'date' and dt.date.fromisoformat(value).isoformat() != value:
                raise ValueError()
            if f['type'] in ('number', 'integer'):
                from decimal import Decimal
                number = Decimal(value)
                if not number.is_finite() or (f['type'] == 'integer' and number != number.to_integral_value()):
                    raise ValueError()
        except (ValueError, ArithmeticError):
            raise ValueError(f"{f['label']}格式不符") from None
        if f['type'] == 'enum':
            values = [v if isinstance(v, str) else v['label'] for v in schema.get('enums', {}).get(f.get('enum', f['name']), [])]
            if value not in values:
                raise ValueError(f"{f['label']}不在選項內")
        if f.get('pattern') and not re.fullmatch(f['pattern'], value):
            raise ValueError(f"{f['label']}格式不符")
    return result


class Client:
    def __init__(self, base='http://127.0.0.1:3000', schema=None):
        parsed = urllib.parse.urlparse(base)
        if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('第一階段只可呼叫本機 HTTP 位址')
        self.base = base.rstrip('/')
        self.schema_override = schema

    def request(self, path, method='GET', body=None):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(self.base+'/'+path, method=method, data=data, headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise ValueError(f'本機介面 {method} {path} 失敗（{e.code}）：{e.read().decode(errors="replace")}') from None
        except urllib.error.URLError as e:
            raise ValueError(f'本機程式未啟動或無法連線：{e.reason}') from None

    def config(self):
        config = self.request('config')
        schema_path = Path(self.schema_override) if self.schema_override else DEFAULT_SCHEMA
        if self.schema_override or schema_path.exists():
            config['schema'] = json.loads(schema_path.read_text(encoding='utf-8'))
        if config.get('organization', {}).get('units'):
            f = next((f for f in config['schema']['fields'] if f['name'] == 'department'), None)
            if f:
                config['schema']['enums'][f.get('enum', 'department')] = [u.get('path') or u['name'] for u in config['organization']['units']]
        return config

    def read(self, kind, key):
        for r in self.request(kind):
            if key in (r['id'], r.get('case_number') if kind == 'cases' else r.get('fields', {}).get('contract_id')):
                return r
        raise ValueError('找不到紀錄')

    @staticmethod
    def actor(body):
        if not isinstance(body, dict):
            raise ValueError('請提供 JSON 物件')
        if not isinstance(body.get('user'), str) or not isinstance(body.get('comment'), str) or not body['user'].strip() or not body['comment'].strip():
            raise ValueError('請填處理人與意見')

    def create(self, kind, body):
        self.actor(body)
        if not isinstance(body.get('fields'), dict): raise ValueError('fields 須為欄位物件')
        config = self.config()
        fields = dict(body['fields'])
        fields['updated_at'] = dt.date.today().isoformat()
        if kind == 'contracts' and not fields.get('contract_id'):
            reserved = {r['fields'].get('contract_id', r['id']) for r in self.request(kind)}
            prefix = f'C-{dt.date.today().year}-'; number = 1
            while f'{prefix}{number:04d}' in reserved: number += 1
            fields.update(contract_id=f'{prefix}{number:04d}', contract_id_origin='system')
        fields = validate_fields(fields, config['schema'], kind == 'cases')
        if kind == 'contracts' and any(r['fields'].get('contract_id') == fields['contract_id'] for r in self.request(kind)):
            raise ValueError('合約編號已存在')
        record = {'fields':fields, 'updated_by':body['user']}
        if kind == 'cases':
            record.update(stage='收件', case_number=f'CASE-{dt.date.today():%Y%m%d}-{uuid.uuid4().hex[:8]}')
        result = self.request(kind, 'POST', record)
        if kind == 'cases': self.log(result['id'], body, '', '收件', '新增案件')
        return result

    def log(self, key, body, before, after, action):
        return self.request('progress', 'POST', {'case_id':key, 'time':dt.datetime.now(dt.timezone.utc).isoformat(), 'user':body['user'], 'action':action, 'from_stage':before, 'to_stage':after, 'comment':body['comment'], 'attachment_version':body.get('attachment_version', '')})

    def update(self, kind, key, body):
        self.actor(body)
        if not isinstance(body.get('fields'), dict): raise ValueError('fields 須為欄位物件')
        config = self.config(); current = self.read(kind, key)
        changes = {**body['fields'], 'updated_at':dt.date.today().isoformat()}
        if kind == 'contracts': changes.pop('contract_id', None)
        fields = {**current['fields'], **validate_fields(changes, config['schema'], kind == 'cases', current['fields'])}
        result = self.request(kind+'/'+urllib.parse.quote(current['id']), 'PATCH', {'fields':fields, 'updated_by':body['user']})
        if kind == 'cases': self.log(current['id'], body, current['stage'], current['stage'], '更新欄位')
        return result

    def progress(self, key, body):
        self.actor(body); config = self.config(); current = self.read('cases', key)
        stage = body.get('stage') or current['stage']
        if stage != current['stage'] and stage not in config['transitions'].get(current['stage'], []):
            raise ValueError('不允許的狀態轉換')
        event = self.log(current['id'], body, current['stage'], stage, '加入意見' if stage == current['stage'] else '狀態變更')
        self.request('cases/'+urllib.parse.quote(current['id']), 'PATCH', {'stage':stage, 'updated_by':body['user']})
        return event

    def review_import(self, key, directory):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        try:
            import build_dashboard
        except ModuleNotFoundError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import build_dashboard
        data = build_dashboard.read_review(directory)
        case = self.read('cases', key)
        count = 0
        threads = {}
        for collection, name in (('review_versions', 'versions'), ('review_comments', 'comments')):
            existing = [r for r in self.request(collection) if r['case_id'] == case['id']]
            for event in data[name]:
                source_id = event.get('id') or event['version_id']
                import_key = case['id']+':'+source_id
                found = next((r for r in existing if r.get('import_key') == import_key or (name == 'versions' and r['version_id'] == source_id) or (name == 'comments' and r['id'] == case['id']+'-'+source_id)), None)
                if found:
                    if name == 'versions' and found['clauses'] != event['clauses']:
                        raise ValueError('既有條款版本不同，不覆寫')
                    if name == 'comments': threads[event['thread_id']] = found['thread_id']
                    continue
                record = dict(event, case_id=case['id'], import_key=import_key)
                record.pop('id', None)
                if name == 'comments':
                    record['thread_id'] = threads.setdefault(event['thread_id'], case['id']+':'+event['thread_id'])
                self.request(collection, 'POST', record); count += 1
        return {'imported':count,'case_id':case['id']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default='http://127.0.0.1:3000')
    parser.add_argument('--fields', help='欄位定義；預設使用由 schema/fields.json 產生的本機 config')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('list','read','create','update'):
        sub = commands.add_parser(name); sub.add_argument('kind', choices=('contracts','cases'))
        if name in ('read','update'): sub.add_argument('id')
        if name in ('create','update'): sub.add_argument('--input', required=True, help='UTF-8 JSON，含 fields/user/comment')
    sub = commands.add_parser('review-import'); sub.add_argument('id'); sub.add_argument('--case-dir', required=True)
    sub = commands.add_parser('progress'); sub.add_argument('id'); sub.add_argument('--input', required=True)
    args = parser.parse_args(argv)
    try:
        client = Client(args.api, args.fields)
        body = json.loads(Path(args.input).read_text(encoding='utf-8')) if hasattr(args,'input') else None
        if args.command == 'review-import': result = client.review_import(args.id, args.case_dir)
        elif args.command == 'list': result = client.request(args.kind)
        elif args.command == 'read': result = client.read(args.kind, args.id)
        elif args.command == 'create': result = client.create(args.kind, body)
        elif args.command == 'update': result = client.update(args.kind, args.id, body)
        else: result = client.progress(args.id, body)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'拒絕：{exc}', file=sys.stderr); return 1

if __name__ == '__main__': raise SystemExit(main())
