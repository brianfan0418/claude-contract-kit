#!/usr/bin/env python3
"""將合約 CSV／Markdown 與案件日誌轉為 file:// 可載入的 data.js。

用法：python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv
      --out dashboard/app/data/data.js --logo logo.png --today YYYY-MM-DD
"""
import argparse
import base64
import csv
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_FIELDS = HERE.parent / 'schema' / 'fields.json'
DEFAULT_REGISTER = HERE.parent / 'schema' / 'register.csv'
DEFAULT_OUT = HERE / 'app' / 'data'
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
    expired = row.get('status') == '已到期' or (row.get('status') == '有效' and days is not None and days < 0)
    active = row.get('status') == '有效' and not expired
    out.update(days_to_end=days, notice_deadline=deadline.isoformat() if deadline else '',
               days_to_notice=ndays, is_active=active, is_expired=expired,
               is_expiring=active and days is not None and 0 <= days <= 90,
               is_notice_due=active and row.get('renewal_type') == '自動續約' and ndays is not None and 0 <= ndays <= 90)
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
    else: raise ValueError('--logo 須為 PNG、JPEG、GIF 或 WebP')
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

def build_payload(register_path, today, fields_path=DEFAULT_FIELDS, logo=None, markdown_dir=None, cases_dir=None):
    schema = json.loads(Path(fields_path).read_text(encoding='utf-8'))
    rows = read_register(register_path) if register_path else []
    if markdown_dir:
        for path in sorted(Path(markdown_dir).glob('*.md')):
            values, _ = read_markdown(path)
            rows.append({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v) for k, v in values.items()})
    contracts = []; seen = set()
    for index, row in enumerate(rows, 1):
        key = row.get('contract_id') or f'IMPORT-{index:04d}'
        if key in seen: raise ValueError(f'重複合約編號：{key}')
        seen.add(key); contracts.append({'id': key, 'fields': row})
    cases = []; progress = {}
    if cases_dir:
        paths = sorted(Path(cases_dir).glob('*.md')) + sorted(p.parent for p in Path(cases_dir).glob('*/index.md'))
        for path in paths:
            record, entries = read_case_directory(path) if path.is_dir() else read_case(path)
            if any(r['id'] == record['id'] for r in cases): raise ValueError('重複案件編號')
            cases.append(record); progress[f'cases:{record["id"]}'] = entries
    return {'config': {'schema': schema, 'today': today.isoformat(), 'logo': logo or '',
                       'stages': STAGES, 'transitions': TRANSITIONS},
            'records': {'contracts': contracts, 'cases': cases, 'progress': progress}}

def main(argv=None):
    parser = argparse.ArgumentParser(description='合約 CSV／Markdown 與案件日誌轉 data.js')
    parser.add_argument('--register', help='合約 CSV；未指定且未給 --md-dir 時使用預設 register')
    parser.add_argument('--md-dir', help='合約 Markdown 資料夾，與 register 同時給時合併並檢查重複編號')
    parser.add_argument('--cases-dir', help='每案一檔的 Markdown＋JSONL 進度日誌')
    parser.add_argument('--fields', default=str(DEFAULT_FIELDS))
    parser.add_argument('--out', default=str(HERE / 'app' / 'data' / 'data.js'))
    parser.add_argument('--logo'); parser.add_argument('--today')
    args = parser.parse_args(argv)
    today = parse_date(args.today) if args.today else dt.date.today()
    if today is None:
        print('錯誤：--today 格式須為 YYYY-MM-DD', file=sys.stderr); return 2
    try:
        payload = build_payload(args.register or (None if args.md_dir else DEFAULT_REGISTER), today, args.fields,
                                logo_data_uri(args.logo) if args.logo else None, args.md_dir, args.cases_dir)
        out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        temporary = out.with_name(out.name + '.tmp')
        temporary.write_text('/* Generated snapshot; source documents remain authoritative. */\nwindow.CONTRACT_DATA = ' + raw + ';\n', encoding='utf-8')
        temporary.replace(out)
    except (OSError, ValueError) as exc:
        print(f'錯誤：{exc}', file=sys.stderr); return 1
    print(f'已產生 {out}：{len(payload["records"]["contracts"])} 筆合約、{len(payload["records"]["cases"])} 件案件')
    return 0

if __name__ == '__main__': raise SystemExit(main())
