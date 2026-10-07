#!/usr/bin/env python3
"""Read native DOCX review markup; add AI comments/revisions to a new Word version.

Uses lxml to preserve untouched OOXML package parts. CLI import writes via REST.
Usage: word_review.py inspect file.docx | suggest file.docx --suggestions ai.json --out new.docx
       word_review.py import file.docx --case CASE-ID --user NAME --api http://127.0.0.1:3000
"""
import argparse
import base64
from copy import deepcopy
import datetime as dt
import io
import json
from pathlib import Path
import re
import sys
import uuid
import zipfile
from lxml import etree as E

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'
W15 = 'http://schemas.microsoft.com/office/word/2012/wordml'
R = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
NS = {'w':W, 'w14':W14, 'w15':W15}
MAX_BYTES = 10 * 1024 * 1024

def q(name): return '{'+W+'}'+name

def xml(raw):
    return E.fromstring(raw, E.XMLParser(resolve_entities=False, no_network=True))

def package(raw):
    if len(raw)>MAX_BYTES: raise ValueError('Word 檔案須小於 10 MB')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist())>MAX_BYTES*5: raise ValueError('Word 解壓內容過大')
            parts={i.filename:z.read(i) for i in z.infolist()}
        if 'word/document.xml' not in parts: raise ValueError('不是可讀取的 Word 文件')
        return parts
    except zipfile.BadZipFile: raise ValueError('不是有效的 DOCX 檔案') from None

def text(node, include_deleted=True):
    return ''.join(n.text or '' for n in node.iter() if n.tag in (q('t'),q('delText')) and (include_deleted or not any(a.tag==q('del') for a in n.iterancestors())))

def clause_heading(value):
    m=re.match(r'^\s*第\s*([0-9一二三四五六七八九十百零〇]+)\s*條(?:\s|[：:、.．]|$)(.*)',value)
    return (m.group(1),m.group(2).strip()) if m else None

def inspect(raw):
    parts=package(raw);document=xml(parts['word/document.xml']);comments={};resolved={}
    if 'word/commentsExtended.xml' in parts:
        for n in xml(parts['word/commentsExtended.xml']).iter('{'+W15+'}commentEx'):
            resolved[n.get('{'+W15+'}paraId')]=n.get('{'+W15+'}done') in ('1','true')
    if 'word/comments.xml' in parts:
        for n in xml(parts['word/comments.xml']).iter(q('comment')):
            p=n.find('w:p',NS);pid=p.get('{'+W14+'}paraId') if p is not None else None
            comments[n.get(q('id'))]={'id':'comment-'+n.get(q('id')), 'type':'comment','author':n.get(q('author')) or '未載明','time':n.get(q('date')) or '', 'content':text(n),'resolved':resolved.get(pid,False),'quote':'','clause_id':'未載明'}
    items=[];clauses=[];current='未載明';active={};seen=set()
    for p in document.findall('.//w:body//w:p',NS):
        heading=clause_heading(text(p,False))
        if heading:
            current=heading[0]
            if current in seen: raise ValueError('條號重複，建議核對文件章節後匯入')
            seen.add(current);clauses.append({'id':current,'title':heading[1],'text':''})
        elif clauses:
            clauses[-1]['text']+=('\n' if clauses[-1]['text'] else '')+text(p,False)
        for n in p.iter():
            if n.tag==q('commentRangeStart'):
                key=n.get(q('id'));active[key]=[]
                if key in comments: comments[key]['clause_id']=current
            elif n.tag==q('commentRangeEnd'):
                key=n.get(q('id'))
                if key in active and key in comments: comments[key]['quote']=''.join(active.pop(key))
            elif n.tag in (q('t'),q('delText')):
                for value in active.values(): value.append(n.text or '')
            elif n.tag in (q('ins'),q('del')):
                items.append({'id':('insert-' if n.tag==q('ins') else 'delete-')+(n.get(q('id')) or str(len(items))), 'type':'insert' if n.tag==q('ins') else 'delete','clause_id':current,'author':n.get(q('author')) or '未載明','time':n.get(q('date')) or '','quote':text(n),'content':text(n),'resolved':False})
    for key,value in active.items():
        if key in comments: comments[key]['quote']=''.join(value)
    items.extend(comments.values())
    return {'clauses':clauses,'word_items':items,'unresolved':sum(not i['resolved'] for i in items)}

def dump_xml(node): return E.tostring(node,encoding='UTF-8',xml_declaration=True,standalone=True)

def run(value,props=None,deleted=False):
    r=E.Element(q('r'))
    if props is not None:r.append(deepcopy(props))
    t=E.SubElement(r,q('delText' if deleted else 't'));t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=value
    return r

def suggest(raw,suggestions,author='AI'):
    parts=package(raw);doc=xml(parts['word/document.xml']);comments=xml(parts['word/comments.xml']) if 'word/comments.xml' in parts else E.Element(q('comments'),nsmap={'w':W})
    if not isinstance(suggestions,list) or not suggestions:raise ValueError('建議須為非空陣列')
    numbers=[int(n.get(q('id'))) for n in doc.iter() if (n.get(q('id')) or '').isdigit()]
    next_id=max(numbers+[int(n.get(q('id'))) for n in comments if (n.get(q('id')) or '').isdigit()]+[-1])+1
    current='未載明';paragraphs=[]
    for p in doc.findall('.//w:body//w:p',NS):
        h=clause_heading(text(p,False))
        if h:current=h[0]
        else:paragraphs.append((current,p))
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    for s in suggestions:
        quote=s.get('quote');kind=s.get('type');clause=str(s.get('clause_id',''))
        if not isinstance(quote,str) or not quote or kind not in ('comment','replace'):raise ValueError('建議須有條號、唯一原文及 comment／replace 類型')
        matches=[]
        for cid,p in paragraphs:
            if cid!=clause:continue
            for r in p.findall('w:r',NS):
                # A simple text run only: preserve formatting, refuse destructive broad matches.
                ts=r.findall('w:t',NS)
                if len(ts)==1 and all(n.tag in (q('rPr'),q('t')) for n in r) and quote in (ts[0].text or ''):
                    value=ts[0].text or ''
                    if value.count(quote)!=1:raise ValueError('原文重複，建議縮小文字範圍')
                    matches.append((p,r,value))
        if len(matches)!=1:raise ValueError('找不到唯一的單一文字區段；跨格式或修訂範圍建議由 Word 處理')
        p,r,value=matches[0];position=p.index(r);props=r.find('w:rPr',NS);a,b=value.split(quote,1);nodes=[]
        if a:nodes.append(run(a,props))
        if kind=='comment':
            if not isinstance(s.get('content'),str) or not s['content'].strip():raise ValueError('註解內容不可空白')
            start=E.Element(q('commentRangeStart'));start.set(q('id'),str(next_id));nodes.append(start);nodes.append(run(quote,props));end=E.Element(q('commentRangeEnd'));end.set(q('id'),str(next_id));nodes.append(end)
            ref=E.Element(q('r'));n=E.SubElement(ref,q('commentReference'));n.set(q('id'),str(next_id));nodes.append(ref)
            c=E.SubElement(comments,q('comment'));c.set(q('id'),str(next_id));c.set(q('author'),author);c.set(q('date'),now);cp=E.SubElement(c,q('p'));cp.append(run(s['content']));next_id+=1
        else:
            if not isinstance(s.get('replacement'),str):raise ValueError('replacement 須為文字')
            for tag,content in [('del',quote),('ins',s['replacement'])]:
                if not content:continue
                n=E.Element(q(tag));n.set(q('id'),str(next_id));n.set(q('author'),author);n.set(q('date'),now);n.append(run(content,props,tag=='del'));nodes.append(n);next_id+=1
        if b:nodes.append(run(b,props))
        p.remove(r)
        for offset,node in enumerate(nodes):p.insert(position+offset,node)
    parts['word/document.xml']=dump_xml(doc)
    if len(comments):
        parts['word/comments.xml']=dump_xml(comments)
        relpath='word/_rels/document.xml.rels';rels=xml(parts[relpath]) if relpath in parts else E.Element('{'+R+'}Relationships')
        if not any(n.get('Type','').endswith('/comments') for n in rels):
            n=E.SubElement(rels,'{'+R+'}Relationship');n.set('Id','rIdComments'+uuid.uuid4().hex[:8]);n.set('Type','http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments');n.set('Target','comments.xml')
        parts[relpath]=dump_xml(rels);ct=xml(parts['[Content_Types].xml'])
        if not any(n.get('PartName')=='/word/comments.xml' for n in ct):
            n=E.SubElement(ct,'{'+CT+'}Override');n.set('PartName','/word/comments.xml');n.set('ContentType','application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml')
        parts['[Content_Types].xml']=dump_xml(ct)
    target=io.BytesIO()
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name,value in parts.items():z.writestr(name,value)
    return target.getvalue()

def record(raw,case_id,filename,author):
    summary=inspect(raw)
    result = {'id':uuid.uuid4().hex,'case_id':case_id,'version_id':'WORD-'+uuid.uuid4().hex[:8],'format':'docx','filename':Path(filename).name,'user':author,'time':dt.datetime.now(dt.timezone.utc).isoformat(),'document_base64':base64.b64encode(raw).decode(),**summary}
    if len(json.dumps(result,ensure_ascii=False).encode())>9*1024*1024:raise ValueError('Word 與總覽資料超過本機介面可保存大小，建議由 AI 拆分文件')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['inspect','suggest','import']);p.add_argument('document');p.add_argument('--suggestions');p.add_argument('--out');p.add_argument('--user',default='AI');p.add_argument('--case');p.add_argument('--api',default='http://127.0.0.1:3000');a=p.parse_args()
    try:
        raw=Path(a.document).read_bytes()
        if a.action=='inspect':result=inspect(raw)
        elif a.action=='suggest':
            if not a.out or not a.suggestions:raise ValueError('建議需 --suggestions 與 --out')
            result_raw=suggest(raw,json.loads(Path(a.suggestions).read_text(encoding='utf-8')),a.user)
            summary=inspect(result_raw)
            with Path(a.out).open('xb') as f:f.write(result_raw)
            result={'output':a.out,**summary}
        else:
            from contract_cli import Client
            if not a.case:raise ValueError('匯入需 --case')
            client=Client(a.api);case=client.read('cases',a.case);r=record(raw,case['id'],a.document,a.user);result=client.request('review_versions','POST',r);result.pop('document_base64',None)
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,OSError,E.XMLSyntaxError) as e:print(str(e),file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
