#!/usr/bin/env python3
"""將合約 CSV／Markdown 與案件日誌匯入本機 json-server db.json。

用法：python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv
      --out dashboard/data/db.json --logo logo.png --today YYYY-MM-DD
"""
import argparse
import base64
import csv
import datetime as dt
import json
import sys
import hashlib
import uuid
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_FIELDS = HERE.parent / 'schema' / 'fields.json'
DEFAULT_REGISTER = HERE.parent / 'schema' / 'register.csv'
DEFAULT_OUT = HERE / 'data' / 'db.json'
WINDOW_DAYS = 90
STAGES = ['收件', '法務審閱', '退回需求部門', '與對方協商', '核准', '簽署', '歸檔']
TRANSITIONS = {
    '收件': ['法務審閱'],
    '法務審閱': ['退回需求部門', '與對方協商', '核准'],
    '退回需求部門': ['法務審閱'],
    '與對方協商': ['法務審閱', '退回需求部門'],
    '核准': ['法務審閱', '簽署'],
    '簽署': ['法務審閱', '歸檔'],
    '歸檔': [],
}

def parse_date(value):
    try:
        return dt.date.fromisoformat(str(value).strip()) if value else None
    except (ValueError, TypeError):
        return None

def parse_int(value):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None

def enrich(row, today):
    out = dict(row)
    end = parse_date(row.get('end_date'))
    days = (end - today).days if end else None
    notice = parse_int(row.get('notice_days'))
    deadline = None
    if end and notice is not None and notice >= 0:
        try:
            deadline = end - dt.timedelta(days=notice)
        except OverflowError:
            pass
    ndays = (deadline - today).days if deadline else None
    expired = days is not None and days < 0
    active = days is not None and days >= 0
    out.update(days_to_end=days, notice_deadline=deadline.isoformat() if deadline else '',
               days_to_notice=ndays, is_active=active, is_expired=expired,
               is_expiring=active and days is not None and 0 <= days <= 90,
               is_notice_due=active and row.get('renewal_type') == '自動續約' and ndays is not None and ndays <= 90, is_end_unknown=end is None)
    return out

def read_register(path):
    with open(path, encoding='utf-8-sig', newline='') as handle:
        return [{k: v or '' for k, v in r.items() if k is not None}
                for r in csv.DictReader(handle) if any(v for k, v in r.items() if k is not None)]

def logo_data_uri(path):
    data = Path(path).read_bytes()
    if data.startswith(b'\x89PNG\r\n\x1a\n'): mime = 'image/png'
    elif data.startswith(b'\xff\xd8\xff'): mime = 'image/jpeg'
    elif data[:6] in (b'GIF87a', b'GIF89a'): mime = 'image/gif'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP': mime = 'image/webp'
    elif data.lstrip().startswith((b'<svg', b'<?xml')):
        try: root = ET.fromstring(data)
        except ET.ParseError as error: raise ValueError('--logo SVG 格式錯誤') from error
        if root.tag.split('}')[-1] != 'svg': raise ValueError('--logo 須為 SVG 圖片')
        for node in root.iter():
            if node.tag.split('}')[-1] in ('script', 'foreignObject'): raise ValueError('--logo SVG 不得含程式')
            for key, value in node.attrib.items():
                embedded_image = node.tag.split('}')[-1] == 'image' and re.fullmatch(
                    r'data:image/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]+', value)
                if key.split('}')[-1].lower().startswith('on') or (key.split('}')[-1] == 'href' and not value.startswith('#') and not embedded_image):
                    raise ValueError('--logo SVG 不得含程式或外部資源')
        mime = 'image/svg+xml'
    else: raise ValueError('--logo 須為 SVG、PNG、JPEG、GIF 或 WebP')
    return 'data:' + mime + ';base64,' + base64.b64encode(data).decode()

def read_markdown(path):
    """解析可攜子集：頂層 YAML scalar、JSON inline 值、literal/folded block。"""
    text = Path(path).read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---': raise ValueError(f'{path}: 缺少 YAML frontmatter')
    try: end = next(i for i in range(1, len(lines)) if lines[i].strip() == '---')
    except StopIteration: raise ValueError(f'{path}: frontmatter 未結束')
    values = {}; index = 1
    while index < end:
        line = lines[index]; index += 1
        if not line.strip() or line.lstrip().startswith('#'): continue
        if line[0].isspace() or ':' not in line: raise ValueError(f'{path}: 只支援頂層欄位；巢狀值請使用單行 JSON')
        key, value = line.split(':', 1); value = value.strip()
        if key in values: raise ValueError(f'{path}: 重複欄位 {key}')
        if value in ('|', '|-', '|+', '>', '>-', '>+'):
            block = []
            while index < end and (not lines[index].strip() or lines[index].startswith('  ')):
                block.append(lines[index][2:] if lines[index].startswith('  ') else ''); index += 1
            value = (' ' if value.startswith('>') else '\n').join(block)
        elif value.startswith(('"', '[', '{')):
            try: value = json.loads(value)
            except ValueError: raise ValueError(f'{path}: {key} 請使用有效 JSON 引號或 inline JSON')
        elif value.startswith("'") and value.endswith("'"): value = value[1:-1].replace("''", "'")
        elif value.lower() in ('null', '~'): value = ''
        values[key.strip()] = value
    return values, '\n'.join(lines[end + 1:])

def read_case(path):
    meta, body = read_markdown(path)
    entries = []; inside = False
    for line in body.splitlines():
        if line.strip() == '```jsonl': inside = True; continue
        if inside and line.strip() == '```': inside = False; continue
        if inside and line.strip():
            entry = json.loads(line)
            if not isinstance(entry, dict): raise ValueError(f'{path}: 進度須為 JSON 物件')
            for name in ('time', 'user', 'action', 'comment', 'attachment_version', 'to_stage'):
                if name not in entry: raise ValueError(f'{path}: 進度缺少 {name}')
            if not isinstance(entry['user'], str) or not entry['user'].strip(): raise ValueError(f'{path}: 處理人不可空白')
            if not isinstance(entry['time'], str): raise ValueError(f'{path}: 時間須為字串')
            when = dt.datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
            if when.tzinfo is None: raise ValueError(f'{path}: 時間须包含時區')
            previous = entries[-1]['to_stage'] if entries else ''
            if entry['to_stage'] not in STAGES: raise ValueError(f'{path}: 未知案件狀態')
            if entries and entry['to_stage'] != previous and entry['to_stage'] not in TRANSITIONS[previous]:
                raise ValueError(f'{path}: 不允許狀態 {previous} → {entry["to_stage"]}')
            if not entries and entry['to_stage'] != '收件': raise ValueError(f'{path}: 首筆狀態須為收件')
            entry['from_stage'] = previous
            if entries and when < dt.datetime.fromisoformat(entries[-1]['time'].replace('Z', '+00:00')): raise ValueError(f'{path}: 進度時間須依序追加')
            entries.append(entry)
    if inside: raise ValueError(f'{path}: jsonl 區塊未結束')
    if not entries: raise ValueError(f'{path}: 案件須有進度紀錄')
    key = str(meta.pop('case_id', Path(path).stem))
    example = str(meta.pop('example', '')).lower() == 'true'
    return {'id': key, 'fields': meta, 'stage': entries[-1]['to_stage'], 'example': example}, entries

def read_case_directory(path):
    path = Path(path); meta, _ = read_markdown(path / 'index.md')
    entries = []
    for log in sorted((path / 'log').glob('*.md')):
        fields, comment = read_markdown(log)
        entry = dict(fields); entry['comment'] = comment.strip(); entry['file'] = log.name
        for name in ('time', 'user', 'action', 'attachment_version', 'to_stage'):
            if name not in entry: raise ValueError(f'{log}: 缺少 {name}')
        if not isinstance(entry['time'], str): raise ValueError(f'{log}: 時間須為字串')
        when = dt.datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
        if when.tzinfo is None: raise ValueError(f'{log}: 時間須有時區')
        entries.append(entry)
    entries.sort(key=lambda e: (dt.datetime.fromisoformat(e['time'].replace('Z', '+00:00')), e['file']))
    stage = ''
    for entry in entries:
        if not str(entry['user']).strip(): raise ValueError(f'{path}: 處理人不可空白')
        if entry['to_stage'] not in STAGES: raise ValueError(f'{path}: 狀態不符')
        if not stage and entry['to_stage'] != '收件': raise ValueError(f'{path}: 首筆須為收件')
        if stage and entry['to_stage'] != stage and entry['to_stage'] not in TRANSITIONS[stage]: raise ValueError(f'{path}: 狀態轉換衝突')
        if 'from_stage' in entry and entry['from_stage'] != stage: raise ValueError(f'{path}: 同時更新的進度衝突')
        entry['from_stage'] = stage; stage = entry['to_stage']
    if not entries: raise ValueError(f'{path}: 案件須有收件紀錄')
    key = str(meta.pop('case_id', path.name))
    if key != path.name: raise ValueError(f'{path}: 案號與資料夾不符')
    example = str(meta.pop('example', '')).lower() == 'true'
    return {'id': key, 'fields': meta, 'stage': stage, 'example': example}, entries

def read_review(path):
    root = Path(path) / 'review'; data = {'versions': [], 'comments': []}
    for name in data:
        for file in sorted((root / name).glob('*.md')):
            meta, body = read_markdown(file)
            if name == 'comments': meta['comment'] = body.strip()
            data[name].append(meta)
    data['versions'].sort(key=lambda v: [int(x) if x.isdigit() else x for x in __import__('re').split(r'(\d+)', str(v.get('version_id', '')))])
    versions = {}; threads = {}; event_ids = set()
    for version in data['versions']:
        key = version.get('version_id')
        if not key or key in versions or not isinstance(version.get('clauses'), list): raise ValueError(f'{path}: 審閱版本不符')
        clauses = version['clauses']
        if any(not c.get('id') or not isinstance(c.get('text'), str) for c in clauses) or len({c['id'] for c in clauses}) != len(clauses): raise ValueError(f'{path}: 條號或文字不符')
        versions[key] = version
    for event in data['comments']:
        when = dt.datetime.fromisoformat(str(event.get('time', '')).replace('Z', '+00:00'))
        if when.tzinfo is None or not event.get('user'): raise ValueError(f'{path}: 留言須有處理人及含時區時間')
    data['comments'].sort(key=lambda e: dt.datetime.fromisoformat(e['time'].replace('Z', '+00:00')))
    for e in data['comments']:
        key = e.get('id'); thread = e.get('thread_id'); selector = e.get('selector', {})
        clause = next((c for c in versions.get(e.get('version_id'), {}).get('clauses', []) if c['id'] == e.get('clause_id')), None)
        if not key or key in event_ids or not thread or e.get('action') not in ('comment', 'resolve', 'reopen'): raise ValueError(f'{path}: 留言事件不符')
        if not clause or selector.get('type') != 'TextQuoteSelector' or not selector.get('exact') or selector['exact'] not in clause['text']: raise ValueError(f'{path}: 原文錨點不符')
        if e['action'] == 'comment' and not e['comment'].strip(): raise ValueError(f'{path}: 留言不可空白')
        if thread not in threads:
            if e['action'] != 'comment' or key != thread: raise ValueError(f'{path}: 缺少首筆留言')
            threads[thread] = e
        elif any(e.get(k) != threads[thread].get(k) for k in ('clause_id', 'version_id', 'selector')): raise ValueError(f'{path}: 留言串錨點變更')
        event_ids.add(key)
    return data

def build_payload(register_path, today, fields_path=DEFAULT_FIELDS, logo=None, markdown_dir=None, cases_dir=None):
    schema = json.loads(Path(fields_path).read_text(encoding='utf-8'))
    rows = read_register(register_path) if register_path else []
    if markdown_dir:
        for path in sorted(Path(markdown_dir).glob('*.md')):
            values, _ = read_markdown(path)
            rows.append({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v) for k, v in values.items()})
    contracts = []; seen = set(); reserved = {str(r.get('contract_id') or '').strip() for r in rows}; next_id = 1
    for index, row in enumerate(rows, 1):
        key = str(row.get('contract_id') or '').strip()
        if not key:
            while f'C-{today.year}-{next_id:04d}' in reserved: next_id += 1
            key = f'C-{today.year}-{next_id:04d}'; next_id += 1; reserved.add(key)
            row['contract_id_origin'] = 'system'
        row['contract_id'] = key
        if key in seen: raise ValueError(f'重複合約編號：{key}')
        seen.add(key); contracts.append({'id': key, 'fields': row})
    cases = []; progress = {}; review = {}
    if cases_dir:
        paths = sorted(Path(cases_dir).glob('*.md')) + sorted(p.parent for p in Path(cases_dir).glob('*/index.md'))
        for path in paths:
            record, entries = read_case_directory(path) if path.is_dir() else read_case(path)
            if any(r['id'] == record['id'] for r in cases): raise ValueError('重複案件編號')
            cases.append(record); progress[f'cases:{record["id"]}'] = entries
            if path.is_dir(): review[record['id']] = read_review(path)
    return {'config': {'schema': schema, 'today': today.isoformat(), 'logo': logo or '',
                       'stages': STAGES, 'transitions': TRANSITIONS},
            'records': {'contracts': contracts, 'cases': cases, 'progress': progress, 'review': review}}

def database_from_payload(payload):
    records = payload['records']
    database = {name: [] for name in ('contracts', 'cases', 'progress', 'review_versions', 'review_comments')}
    database.update(config=payload['config'], contracts=records['contracts'], cases=records['cases'])
    for key, entries in records['progress'].items():
        case_id = key.split(':', 1)[1]
        for index, entry in enumerate(entries):
            digest = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
            database['progress'].append(dict(entry, id=f'{case_id}-{index:04d}-{digest}', case_id=case_id))
    for case_id, review in records['review'].items():
        for version in review['versions']:
            database['review_versions'].append(dict(version, id=case_id+'-'+version['version_id'], case_id=case_id))
        for event in review['comments']:
            database['review_comments'].append(dict(event, id=case_id+'-'+event['id'], thread_id=case_id+'-'+event['thread_id'], case_id=case_id))
    return database

def import_api(database, base):
    from urllib.parse import quote, urlparse
    parsed = urlparse(base)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('第一階段只可匯入本機 HTTP 位址')
    def request(path, method='GET', body=None):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(base.rstrip('/')+'/'+path, data=data, method=method, headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=15) as response: return json.load(response)
    case_ids = {}
    for name in ('contracts', 'cases', 'progress', 'review_versions', 'review_comments'):
        rows = request(name)
        existing = {r.get('import_key', r['id']): r for r in rows}
        if name == 'contracts': existing.update({r.get('fields', {}).get('contract_id', r['id']): r for r in rows})
        if name == 'cases': existing.update({r.get('case_number', r['id']): r for r in rows})
        for original in database[name]:
            record = dict(original)
            import_key = record['id']
            if 'case_id' in record: record['case_id'] = case_ids.get(record['case_id'], record['case_id'])
            if import_key in existing:
                current = existing[import_key]
                if name in ('contracts', 'cases'):
                    merged = dict(fields={**current.get('fields', {}), **record['fields']})
                    request(name+'/'+quote(str(current['id']), safe=''), 'PATCH', merged)
                else:
                    comparable = {k: v for k, v in current.items() if k not in ('id', 'import_key')}
                    expected = {k: v for k, v in record.items() if k != 'id'}
                    if comparable != expected: raise ValueError(f'{name}/{import_key}: 既有事件不同，不覆寫')
                result = current
            else:
                record['id'] = uuid.uuid4().hex
                record['import_key'] = import_key
                if name == 'cases': record['case_number'] = import_key
                result = request(name, 'POST', record)
            if name == 'cases': case_ids[import_key] = result['id']
    request('config', 'PATCH', database['config'])

def main(argv=None):
    parser = argparse.ArgumentParser(description='合約 CSV／Markdown 匯入本機 json-server')
    parser.add_argument('--register', help='合約 CSV；未指定且未給 --md-dir 時使用預設 register')
    parser.add_argument('--md-dir', help='合約 Markdown 資料夾，與 register 同時給時合併並檢查重複編號')
    parser.add_argument('--cases-dir', help='每案一檔的 Markdown＋JSONL 進度日誌')
    parser.add_argument('--fields', default=str(DEFAULT_FIELDS))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--api', help='執行中的本機 REST 位址；既有資料只經 API 更新')
    parser.add_argument('--logo'); parser.add_argument('--today')
    parser.add_argument('--settings', help='私人組織與核決 JSON；只加入 organization／approvalAuthority，不改公開 schema')
    args = parser.parse_args(argv)
    today = parse_date(args.today) if args.today else dt.date.today()
    if today is None:
        print('錯誤：--today 格式須為 YYYY-MM-DD', file=sys.stderr); return 2
    try:
        payload = build_payload(args.register or (None if args.md_dir else DEFAULT_REGISTER), today, args.fields,
                                logo_data_uri(args.logo) if args.logo else None, args.md_dir, args.cases_dir)
        if args.settings:
            settings = json.loads(Path(args.settings).read_text(encoding='utf-8'))
            for key in ('organization', 'approvalAuthority'):
                if key in settings: payload['config'][key] = settings[key]
        if args.api and not args.logo: payload['config'].pop('logo', None)
        database = database_from_payload(payload)
        if args.api:
            import_api(database, args.api); out = args.api
        else:
            out = Path(args.out)
            if out.exists(): raise ValueError('db.json 已存在；請啟動本機程式並改用 --api，禁止直接覆寫')
            out.parent.mkdir(parents=True, exist_ok=True)
            temporary = out.with_name(out.name + '.tmp')
            temporary.write_text(json.dumps(database, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            temporary.replace(out)
    except (OSError, ValueError) as exc:
        print(f'錯誤：{exc}', file=sys.stderr); return 1
    print(f'已產生 {out}：{len(payload["records"]["contracts"])} 筆合約、{len(payload["records"]["cases"])} 件案件')
    return 0

if __name__ == '__main__': raise SystemExit(main())
