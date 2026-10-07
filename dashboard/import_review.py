#!/usr/bin/env python3
"""由 pandoc --track-changes=all 的 DOCX AST 建立不可覆寫的審閱版本。"""
import argparse
import datetime as dt
import json
import re
import subprocess
import uuid
from pathlib import Path


def markdown(meta, body=''):
    return '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in meta.items()) + '\n---\n\n' + body + '\n'


def convert(ast):
    clauses = []; comments = []; changes = []; current = None; active = {}

    def plain(nodes):
        text = ''
        for n in nodes:
            t, c = n['t'], n.get('c')
            if t in ('Str', 'Code'): text += c if t == 'Str' else c[1]
            elif t in ('Space', 'SoftBreak'): text += ' '
            elif t == 'LineBreak': text += '\n'
            elif t == 'Span': text += plain(c[1])
            elif t in ('Emph', 'Strong', 'Strikeout', 'SmallCaps', 'Superscript', 'Subscript'): text += plain(c)
            elif t == 'Link': text += plain(c[1])
            elif t == 'Image': raise ValueError('圖形內容須人工核對或 OCR，請另行轉換')
            elif t == 'Quoted': text += plain(c[1])
            elif t == 'Note': text += ''.join(plain(x['c']) for x in paragraphs(c))
            else: raise ValueError(f'未支援 inline {t}，請核對來源後轉換')
        return text

    def paragraphs(obj):
        if isinstance(obj, list):
            for x in obj: yield from paragraphs(x)
        elif isinstance(obj, dict):
            if obj.get('t') in ('Para', 'Plain'): yield obj
            elif obj.get('t') == 'Header': yield {'t': 'Para', 'c': obj['c'][2]}
            elif obj.get('t') in ('CodeBlock', 'RawBlock'): raise ValueError('未支援原始區塊，請核對來源')
            else: yield from paragraphs(obj.get('c', []))

    def render(nodes, mode, clause):
        text = ''
        for n in nodes:
            if n['t'] != 'Span': text += plain([n]); continue
            attr, children = n['c']; classes = attr[1]; props = dict(attr[2])
            if 'comment-start' in classes:
                if mode == 'after': active[props.get('id', '')] = {'user': props.get('author') or 'Word 未載處理人', 'time': props.get('date'), 'comment': plain(children), 'clause_id': clause['id'], 'start': len(clause['after']) + len(text)}
                continue
            if 'comment-end' in classes:
                if mode == 'after' and props.get('id', '') in active:
                    e = active.pop(props.get('id', ''))
                    if e['clause_id'] != clause['id']: raise ValueError('跨條號 Word 註解需人工核對')
                    e['end'] = len(clause['after']) + len(text); comments.append(e)
                continue
            deleted = any(x in classes for x in ('deletion', 'paragraph-deletion'))
            inserted = any(x in classes for x in ('insertion', 'paragraph-insertion'))
            if mode == 'after' and (deleted or inserted): changes.append({'clause_id': clause['id'], 'type': 'delete' if deleted else 'insert', 'text': plain(children), 'user': props.get('author', ''), 'time': props.get('date', '')})
            if (mode == 'before' and inserted) or (mode == 'after' and deleted): continue
            text += render(children, mode, clause)
        return text

    for p in paragraphs(ast['blocks']):
        visible = plain([n for n in p['c'] if not (n['t'] == 'Span' and 'comment-start' in n['c'][0][1])])
        heading = re.match(r'^(第\s*[^。\n]{1,12}?\s*條|\d+\s*[.、])\s*(.*)$', visible)
        if heading:
            current = {'id': re.sub(r'\s+', '', heading[1]), 'title': heading[2][:40], 'before': '', 'after': ''}; clauses.append(current)
        if current is None: current = {'id': '前言', 'title': '', 'before': '', 'after': ''}; clauses.append(current)
        for mode in ('before', 'after'):
            if current[mode]: current[mode] += '\n'
            value = render(p['c'], mode, current)
            marker = 'paragraph-insertion' if mode == 'before' else 'paragraph-deletion'
            if any(n['t'] == 'Span' and marker in n['c'][0][1] for n in p['c']): value = ''
            current[mode] += value
    if active: raise ValueError('Word 註解範圍未結束，請人工核對')
    if len({c['id'] for c in clauses}) != len(clauses): raise ValueError('條號重複，請先指定唯一條號')
    for e in comments:
        c = next(c for c in clauses if c['id'] == e['clause_id']); text = c['after']; exact = text[e.pop('start'):e.pop('end')]
        if not exact: raise ValueError('Word 註解沒有可錨定文字，請核對來源')
        at = text.find(exact); e['selector'] = {'type': 'TextQuoteSelector', 'exact': exact, 'prefix': text[max(0, at-24):at], 'suffix': text[at+len(exact):at+len(exact)+24]}
    return clauses, comments, changes


def import_document(source, case, previous='V1', current='V2'):
    if previous == current or not all(re.fullmatch(r'[A-Za-z0-9_-]+', v) for v in (previous, current)): raise ValueError('版本編號須不同，且使用英數字、底線或連字號')
    case = Path(case)
    if not (case / 'index.md').is_file(): raise ValueError('案件主檔不存在')
    ast = json.loads(subprocess.check_output(['pandoc', str(source), '--track-changes=all', '-t', 'json'], text=True))
    clauses, comments, changes = convert(ast); review = case / 'review'; versions = review / 'versions'; versions.mkdir(parents=True, exist_ok=True)
    targets = [versions / (v + '.md') for v in (previous, current)]
    if any(p.exists() for p in targets): raise ValueError('版本已存在；匯入不覆寫，請使用新版本編號')
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(); source_name = Path(source).name
    for e in comments:
        when = dt.datetime.fromisoformat((e.get('time') or stamp).replace('Z', '+00:00'))
        if when.tzinfo is None: raise ValueError('Word 註解時間缺少時區')
    for version, mode, path in zip((previous, current), ('before', 'after'), targets):
        meta = {'version_id': version, 'source': source_name, 'created': stamp, 'clauses': [{'id': c['id'], 'title': c['title'], 'text': c[mode]} for c in clauses], 'changes': changes}
        with path.open('x', encoding='utf-8') as f: f.write(markdown(meta))
    logs = review / 'comments'; logs.mkdir(exist_ok=True)
    for i, e in enumerate(comments):
        key = str(uuid.uuid4()); time = e.pop('time') or (dt.datetime.fromisoformat(stamp) + dt.timedelta(microseconds=i)).isoformat()
        when = dt.datetime.fromisoformat(time.replace('Z', '+00:00'))
        if when.tzinfo is None: raise ValueError('Word 註解時間缺少時區')
        body = e.pop('comment'); entry = {'id': key, 'thread_id': key, 'version_id': current, 'action': 'comment', **e, 'time': time}
        with (logs / (time.replace(':', '-') + '-' + key + '.md')).open('x', encoding='utf-8') as f: f.write(markdown(entry, body))
    return len(clauses), len(comments)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('docx'); p.add_argument('--case-dir', required=True); p.add_argument('--previous', default='V1'); p.add_argument('--current', default='V2'); a = p.parse_args()
    try: print('已匯入：%s 條、%s 則 Word 註解' % import_document(a.docx, a.case_dir, a.previous, a.current))
    except (OSError, ValueError, subprocess.CalledProcessError) as e: p.exit(1, f'錯誤：{e}\n')


if __name__ == '__main__': main()
