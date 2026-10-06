#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""讀取合約主檔 register.csv，產生單一 HTML 面板（無外部相依，離線可開）。

用法：
    python build_dashboard.py [--register ../schema/register.csv] [--out dashboard.html] [--today YYYY-MM-DD] [--logo 圖檔] [--fields ../schema/fields.json]

計算規則：
    有效        狀態為「有效」，且到期日未過或無到期日
    已到期      狀態為「已到期」，或狀態為「有效」但到期日早於基準日
    90 天內到期  有效，且 0 <= 到期日 - 基準日 <= 90
    自動續約須通知  有效、續約方式為「自動續約」、有通知期限與到期日，
                  且 基準日 <= 通知截止日 <= 基準日 + 90
    通知截止日   到期日 - 通知期限（天）
"""

import argparse
import base64
import csv
import datetime as dt
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REGISTER = HERE.parent / "schema" / "register.csv"
DEFAULT_OUT = HERE / "dashboard.html"
DEFAULT_FIELDS = HERE.parent / "schema" / "fields.json"
WINDOW_DAYS = 90
FILTER_KEYS = ["department", "counterparty_category", "contract_type", "status", "governing_law"]
TABLE_KEYS = ["contract_id", "title", "contract_type", "department", "counterparty_name",
              "status", "end_date", "days_to_end", "notice_deadline", "renewal_type",
              "contract_language", "language", "currency", "governing_law", "dispute_resolution"]
DERIVED_FIELDS = [{"name": "days_to_end", "label": "剩餘天數", "type": "integer"},
                  {"name": "notice_deadline", "label": "通知截止日", "type": "date"}]


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def read_register(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        # CSV 可以是舊版或部分欄位；缺值交由呈現層留白。
        return [{k: (v or "") for k, v in row.items() if k is not None}
                for row in reader if any(v for k, v in row.items() if k is not None)]


def enrich(row, today):
    """加上由日期推算的欄位，不修改原列。"""
    out = dict(row)
    end = parse_date(row.get("end_date"))
    notice_days = parse_int(row.get("notice_days"))
    status = (row.get("status") or "").strip()
    days_to_end = (end - today).days if end else None
    notice_deadline = end - dt.timedelta(days=notice_days) if end and notice_days is not None else None
    days_to_notice = (notice_deadline - today).days if notice_deadline else None

    expired = status == "已到期" or (status == "有效" and days_to_end is not None and days_to_end < 0)
    active = status == "有效" and not expired
    expiring = active and days_to_end is not None and 0 <= days_to_end <= WINDOW_DAYS
    notice_due = (
        active
        and (row.get("renewal_type") or "").strip() == "自動續約"
        and days_to_notice is not None
        and 0 <= days_to_notice <= WINDOW_DAYS
    )
    out.update({
        "days_to_end": days_to_end,
        "notice_deadline": notice_deadline.isoformat() if notice_deadline else "",
        "days_to_notice": days_to_notice,
        "is_active": active,
        "is_expired": expired,
        "is_expiring": expiring,
        "is_notice_due": notice_due,
    })
    return out


def summarize(rows):
    return {
        "active": sum(1 for r in rows if r["is_active"]),
        "expiring": sum(1 for r in rows if r["is_expiring"]),
        "notice_due": sum(1 for r in rows if r["is_notice_due"]),
        "expired": sum(1 for r in rows if r["is_expired"]),
    }


def read_fields(path=DEFAULT_FIELDS):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["fields"]


def build_payload(register_path, today, fields_path=DEFAULT_FIELDS):
    fields = read_fields(fields_path)
    definitions = {f["name"]: f for f in fields}
    definitions.update({f["name"]: f for f in DERIVED_FIELDS})
    rows = [enrich(r, today) for r in read_register(register_path)]
    filters = []
    for key in FILTER_KEYS:
        if key not in definitions:
            continue
        options = sorted({r.get(key, "").strip() for r in rows if r.get(key, "").strip()})
        filters.append({"key": key, "label": definitions[key]["label"], "options": options})
    return {
        "today": today.isoformat(), "window": WINDOW_DAYS,
        "summary": summarize(rows), "filters": filters,
        "fields": fields,
        "columns": [definitions[k] for k in TABLE_KEYS if k in definitions],
        "rows": rows,
    }


def logo_data_uri(path):
    data = Path(path).read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        mime = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError("--logo 須為 PNG、JPEG、GIF 或 WebP 圖檔")
    return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")


def render(payload, logo=None):
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    branding = ('<div class="brand"><img src="' + html.escape(logo, quote=True)
                + '" alt="Logo"></div>') if logo else ""
    return TEMPLATE.replace("__DATA__", data).replace("__TODAY__", html.escape(payload["today"])).replace("__LOGO__", branding)


def main(argv=None):
    parser = argparse.ArgumentParser(description="由 register.csv 產生合約面板 HTML")
    parser.add_argument("--register", default=str(DEFAULT_REGISTER))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--today", help="基準日 YYYY-MM-DD，預設為本機今天（測試用）")
    parser.add_argument("--fields", default=str(DEFAULT_FIELDS), help="欄位定義 fields.json")
    parser.add_argument("--logo", help="內嵌 PNG、JPEG、GIF 或 WebP logo；未給則不顯示")
    args = parser.parse_args(argv)
    today = parse_date(args.today) if args.today else dt.date.today()
    if today is None:
        print("錯誤：--today 格式須為 YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        payload = build_payload(args.register, today, args.fields)
        logo = logo_data_uri(args.logo) if args.logo else None
    except (OSError, ValueError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1
    try:
        Path(args.out).write_text(render(payload, logo), encoding="utf-8")
    except OSError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1
    s = payload["summary"]
    print(f"已產生 {args.out}：{len(payload['rows'])} 筆；有效 {s['active']}、"
          f"{WINDOW_DAYS} 天內到期 {s['expiring']}、自動續約須通知 {s['notice_due']}、已到期 {s['expired']}")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>合約面板</title>
<style>
:root{color-scheme:light;--bg:#ecefee;--panel:#f8faf9;--side:#f1f4f3;--ink:#35413e;--muted:#687670;--line:#dce3df;--accent:#466e64;--selected:#e2ece7;--stripe:#f0f4f2;--warn:#88683c;--bad:#985956;--shadow:#283d3520}
:root[data-theme=dark]{color-scheme:dark;--bg:#252d2b;--panel:#2c3532;--side:#29312e;--ink:#d1dad5;--muted:#a2b0a8;--line:#414d46;--accent:#a3c1b4;--selected:#3c5147;--stripe:#303b35;--warn:#cfb68c;--bad:#d7a39d;--shadow:#0004}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.5 "Segoe UI","Microsoft JhengHei","Noto Sans CJK TC",system-ui,sans-serif}
button,input{font:inherit;color:inherit}button{cursor:pointer;background:transparent;border:0}button:focus-visible,a:focus-visible,input:focus-visible,summary:focus-visible,tr:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}button:hover{background:var(--selected)}
.app{display:grid;grid-template-columns:238px minmax(0,1fr);height:100vh;height:100dvh}.sidebar{background:var(--side);border-right:1px solid var(--line);overflow:auto;padding:12px}.brand{height:64px;display:flex;align-items:center;padding:2px 8px 12px}.brand img{max-width:150px;max-height:48px;object-fit:contain;background:#f8faf9;border-radius:3px;padding:4px}
.sidebar h2{font-size:12px;color:var(--muted);font-weight:500;margin:14px 8px 6px}.nav-button{width:100%;display:flex;align-items:center;justify-content:space-between;text-align:left;padding:7px 9px;border-radius:4px;gap:6px}.nav-button[aria-pressed=true]{background:var(--selected);color:var(--accent);font-weight:600}.badge{font-variant-numeric:tabular-nums;color:var(--muted);min-width:23px;text-align:right;font-size:12px}.filter-group{border-top:1px solid var(--line);margin-top:8px;padding-top:8px}.filter-group summary{cursor:pointer;padding:3px 8px;color:var(--muted);font-size:12px}.filter-group .nav-button{padding:4px 9px;font-size:13px}.reset{margin:12px 8px 4px;color:var(--accent);text-decoration:underline;text-underline-offset:3px}
.workspace{display:flex;flex-direction:column;min-width:0;min-height:0}.topbar{height:52px;flex-shrink:0;display:flex;align-items:center;gap:18px;padding:0 20px;background:var(--panel);border-bottom:1px solid var(--line)}h1{font-size:15px;font-weight:600;margin:0;white-space:nowrap}.search{width:min(440px,42vw);margin-left:auto;background:var(--side);border:1px solid var(--line);border-radius:4px;padding:6px 10px}.theme{border:1px solid var(--line);border-radius:4px;padding:5px 11px;white-space:nowrap}
.content{padding:14px 18px;overflow:auto;min-height:0;flex:1}.tablebar{display:flex;align-items:center;gap:16px;min-height:32px;margin-bottom:6px}.tablebar h2{font-size:14px;margin:0;font-weight:600}.count{color:var(--muted);font-variant-numeric:tabular-nums}.date{margin-left:auto;color:var(--muted);font-size:12px}.tablewrap{overflow:auto;max-height:calc(100vh - 180px);background:var(--panel);border:1px solid var(--line);border-radius:5px}table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}th,td{height:32px;padding:5px 9px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}th{position:sticky;top:0;background:var(--side);z-index:1;font-weight:500;color:var(--muted)}th button{width:100%;text-align:inherit;padding:0;font-weight:inherit}tbody tr:nth-child(even){background:var(--stripe)}tbody tr:hover,tbody tr[aria-selected=true]{background:var(--selected)}tbody tr{cursor:pointer}tbody tr:last-child td{border-bottom:0}.title{min-width:160px}.num{text-align:right;font-variant-numeric:tabular-nums}.warn{color:var(--warn)}.bad{color:var(--bad)}.status{padding:2px 5px;background:var(--stripe);border:1px solid var(--line);border-radius:3px;font-size:12px}.empty{text-align:center;color:var(--muted);height:64px;cursor:default}
.timeline{margin-top:16px}.timeline h2{font-size:13px;font-weight:500;margin:0 0 8px}.months{display:grid;grid-template-columns:repeat(13,minmax(95px,1fr));gap:5px;overflow:auto}.month{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:6px;min-height:80px}.month-title{color:var(--muted);font-size:12px;margin-bottom:5px}.event{display:block;text-align:left;width:100%;font-size:12px;padding:3px 4px;border-radius:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;background:var(--stripe);margin-bottom:4px}.event.notice{color:var(--warn)}.event.expired{color:var(--bad)}
.drawer{position:fixed;inset:52px 0 0 auto;width:min(580px,calc(100vw - 32px));background:var(--panel);border-left:1px solid var(--line);box-shadow:-10px 0 35px var(--shadow);z-index:5;display:flex;flex-direction:column}.drawer[hidden]{display:none}.drawer-head{display:flex;align-items:start;gap:12px;border-bottom:1px solid var(--line);padding:16px 20px}.drawer-head h2{font-size:15px;margin:2px 0}.drawer-head p{color:var(--muted);margin:0;font-size:12px}.close{margin-left:auto;border:1px solid var(--line);border-radius:4px;padding:4px 8px;flex-shrink:0}.drawer-body{padding:0 20px 20px;overflow:auto}.drawer section{margin-top:18px}.drawer h3{font-size:13px;font-weight:600;margin:0 0 8px}.drawer dl{display:grid;grid-template-columns:145px minmax(0,1fr);margin:0}.drawer dt,.drawer dd{padding:5px 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.drawer dt{color:var(--muted);padding-right:10px}.drawer dd{margin:0;white-space:pre-wrap}.drawer ol,.drawer ul{padding-left:20px;margin:0}.drawer li{margin:6px 0;white-space:pre-wrap;overflow-wrap:anywhere}.drawer pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--side);padding:10px;font:inherit;margin:0}.drawer a{color:var(--accent)}
@media(max-width:900px){.app{grid-template-columns:190px minmax(0,1fr)}.topbar{padding:0 12px;gap:10px}.content{padding:12px}.date{display:none}}@media(max-width:600px){.app{grid-template-columns:150px minmax(0,1fr)}.sidebar{padding:7px}.topbar{height:auto;min-height:52px;flex-wrap:wrap;padding:8px}.search{order:3;width:100%;margin:0}.theme{margin-left:auto}.drawer{inset:0 0 0 auto}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar" aria-label="檢視與篩選">__LOGO__<h2>預設檢視</h2><nav id="views" aria-label="預設檢視"></nav><h2>篩選</h2><div id="filters"></div><button type="button" class="reset" id="reset">清除篩選</button></aside>
<div class="workspace"><header class="topbar"><h1>合約面板</h1><input id="search" class="search" type="search" placeholder="搜尋合約" aria-label="搜尋合約"><button id="theme" class="theme" type="button">暗色</button></header>
<main class="content"><div class="tablebar"><h2 id="view-title">全部</h2><span id="count" class="count" aria-live="polite"></span><span class="date">基準日 __TODAY__</span></div><div class="tablewrap"><table id="tbl" aria-label="合約主檔"><thead></thead><tbody></tbody></table></div><section class="timeline"><h2>到期時間軸</h2><div class="months" id="timeline"></div></section></main></div>
</div>
<aside class="drawer" id="drawer" aria-label="合約明細" hidden><header class="drawer-head"><div><p id="detail-id"></p><h2 id="detail-title"></h2></div><button class="close" id="close" type="button">關閉</button></header><div class="drawer-body" id="detail-body"></div></aside>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
'use strict';
const D=JSON.parse(document.getElementById('data').textContent),rows=D.rows;
const state={view:'all',q:'',filters:{},sort:'end_date',asc:true,open:null};
const views=[['all','全部'],['expiring','90 天內到期'],['notice_due','自動續約須通知'],['expired','已逾期'],['review','審閱中']];
const flags={expiring:'is_expiring',notice_due:'is_notice_due',expired:'is_expired'};
const byId=id=>document.getElementById(id),value=(r,k)=>r[k]==null?'':String(r[k]);
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
const media=window.matchMedia('(prefers-color-scheme: dark)');let choice=null;
try{choice=localStorage.getItem('contract-dashboard-theme')}catch(e){}
if(!['light','dark'].includes(choice))choice=null;
function applyTheme(){const dark=choice?choice==='dark':media.matches;document.documentElement.dataset.theme=dark?'dark':'light';byId('theme').textContent=dark?'亮色':'暗色';byId('theme').setAttribute('aria-label',dark?'切換亮色':'切換暗色')}
byId('theme').onclick=()=>{choice=document.documentElement.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem('contract-dashboard-theme',choice)}catch(e){}applyTheme()};media.addEventListener('change',()=>{if(!choice)applyTheme()});applyTheme();
function inView(r,key){return key==='all'||(key==='review'?r.status==='審閱中':Boolean(r[flags[key]]))}
function matches(r,omit){if(state.q&&!Object.values(r).join(' ').toLocaleLowerCase().includes(state.q))return false;return Object.entries(state.filters).every(([k,v])=>k===omit||!v||value(r,k).trim()===v)}
function navButton(text,count,pressed,action){const b=el('button','nav-button');b.type='button';b.setAttribute('aria-pressed',String(pressed));b.append(el('span',null,text),el('span','badge',count));b.onclick=action;return b}
function renderSidebar(){const nav=byId('views');nav.replaceChildren();views.forEach(([key,label])=>nav.append(navButton(label,rows.filter(r=>inView(r,key)&&matches(r)).length,state.view===key,()=>{state.view=key;closeDrawer();render()})));
 D.filters.forEach(f=>{const box=byId('filter-'+f.key);box.replaceChildren();const pool=rows.filter(r=>inView(r,state.view)&&matches(r,f.key));box.append(navButton('全部',pool.length,!state.filters[f.key],()=>{delete state.filters[f.key];closeDrawer();render()}));f.options.forEach(o=>box.append(navButton(o,pool.filter(r=>value(r,f.key).trim()===o).length,state.filters[f.key]===o,()=>{state.filters[f.key]=state.filters[f.key]===o?'':o;closeDrawer();render()})))})}
D.filters.forEach(f=>{const group=el('details','filter-group');group.open=true;group.append(el('summary',null,f.label));const box=el('div');box.id='filter-'+f.key;group.append(box);byId('filters').append(group)});
function compare(a,b){const f=D.columns.find(c=>c.name===state.sort),x=a[state.sort],y=b[state.sort];if(x==null||x==='')return y==null||y===''?0:1;if(y==null||y==='')return -1;let n;if(f&&['integer','number'].includes(f.type)&&Number.isFinite(Number(x))&&Number.isFinite(Number(y)))n=Number(x)-Number(y);else n=String(x).localeCompare(String(y),'zh-Hant',{numeric:true});return state.asc?n:-n}
function renderTable(list){const head=byId('tbl').tHead,body=byId('tbl').tBodies[0];head.replaceChildren();body.replaceChildren();const hr=el('tr');D.columns.forEach(c=>{const numeric=['number','integer'].includes(c.type),th=el('th',numeric?'num':'');th.scope='col';th.setAttribute('aria-sort',state.sort===c.name?(state.asc?'ascending':'descending'):'none');const b=el('button',null,c.label+(state.sort===c.name?(state.asc?' ↑':' ↓'):''));b.type='button';b.onclick=()=>{state.asc=state.sort===c.name?!state.asc:true;state.sort=c.name;render()};th.append(b);hr.append(th)});head.append(hr);
list.slice().sort(compare).forEach(r=>{const tr=el('tr');tr.tabIndex=0;tr.dataset.index=rows.indexOf(r);tr.setAttribute('aria-selected',String(state.open===rows.indexOf(r)));D.columns.forEach(c=>{let text=value(r,c.name),cls=['number','integer'].includes(c.type)?'num':c.name==='title'?'title':'';if(c.name==='days_to_end')cls+=' '+(r.is_expired?'bad':r.is_expiring?'warn':'');if(c.name==='notice_deadline')cls+=' '+(r.is_notice_due?'warn':r.is_active&&r.renewal_type==='自動續約'&&r.days_to_notice<0?'bad':'');const td=el('td',cls);if(c.name==='status'){if(r.is_expired&&text==='有效')text='有效（已逾期）';td.append(el('span','status'+(r.is_expired?' bad':''),text))}else td.textContent=text;tr.append(td)});tr.onclick=()=>openDrawer(rows.indexOf(r));tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openDrawer(rows.indexOf(r))}};body.append(tr)});
if(!list.length){const tr=el('tr'),td=el('td','empty','無符合的合約');td.colSpan=D.columns.length;tr.append(td);body.append(tr)}byId('count').textContent=list.length+' / '+rows.length+' 筆';byId('view-title').textContent=views.find(v=>v[0]===state.view)[1]}
function section(title){const s=el('section');s.append(el('h3',null,title));byId('detail-body').append(s);return s}
function listSection(title,text,tag){const s=section(title),l=el(tag);String(text||'').split('|').filter(x=>x.trim()).forEach(x=>l.append(el('li',null,x.trim())));s.append(l)}
function sourceSection(r){const s=section('原文出處');let refs=r.source_refs;if(refs){let parsed;try{parsed=JSON.parse(refs)}catch(e){}if(parsed&&typeof parsed==='object')refs=JSON.stringify(parsed,null,2);s.append(el('pre',null,refs))}else s.append(el('pre',null,''));if(r.file_path){const dl=el('dl');const def=D.fields.find(f=>f.name==='file_path');dl.append(el('dt',null,def?def.label:'原檔位置'),el('dd',null,r.file_path));s.append(dl)}}
function openDrawer(index){state.open=index;const r=rows[index];byId('detail-id').textContent=value(r,'contract_id');byId('detail-title').textContent=value(r,'title');byId('detail-body').replaceChildren();listSection((D.fields.find(f=>f.name==='toc')||{}).label||'章節目錄',r.toc,'ol');listSection((D.fields.find(f=>f.name==='key_clauses')||{}).label||'關鍵條款摘要',r.key_clauses,'ul');sourceSection(r);const s=section('主檔欄位'),dl=el('dl');D.fields.filter(f=>!['toc','key_clauses','source_refs','file_path'].includes(f.name)).forEach(f=>dl.append(el('dt',null,f.label),el('dd',null,value(r,f.name))));s.append(dl);byId('drawer').hidden=false;byId('detail-body').scrollTop=0;renderTable(visible());byId('close').focus()}
function closeDrawer(){const previous=state.open;state.open=null;byId('drawer').hidden=true;document.querySelectorAll('#tbl tbody tr[aria-selected]').forEach(tr=>tr.setAttribute('aria-selected','false'));const row=document.querySelector('#tbl tbody tr[data-index="'+previous+'"]');if(row)row.focus()}
byId('close').onclick=closeDrawer;document.addEventListener('keydown',e=>{if(e.key==='Escape'&&state.open!==null)closeDrawer()});
function renderTimeline(list){const box=byId('timeline');box.replaceChildren();const base=new Date(D.today+'T00:00:00'),months=[];for(let i=0;i<13;i++){const date=new Date(base.getFullYear(),base.getMonth()+i,1),m=el('div','month');m.append(el('div','month-title',date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')));months.push(m);box.append(m)}
 function add(date,r,notice){if(!date)return;const d=new Date(date+'T00:00:00');let i=(d.getFullYear()-base.getFullYear())*12+d.getMonth()-base.getMonth();if(i<0||i>12)return;const b=el('button','event '+(notice?'notice':r.is_expired?'expired':''),(notice?'通知 ':'')+date.slice(5)+' '+r.title);b.type='button';b.title=date+' '+r.title;b.onclick=()=>openDrawer(rows.indexOf(r));months[i].append(b)}
 list.filter(r=>r.status==='有效').sort((a,b)=>value(a,'end_date').localeCompare(value(b,'end_date'))).forEach(r=>{add(r.end_date,r,false);if(r.renewal_type==='自動續約'&&r.days_to_notice>=0)add(r.notice_deadline,r,true)})}
function visible(){return rows.filter(r=>inView(r,state.view)&&matches(r))}function render(){const list=visible();renderSidebar();renderTable(list);renderTimeline(list)}
byId('search').oninput=e=>{state.q=e.target.value.trim().toLocaleLowerCase();closeDrawer();render()};byId('reset').onclick=()=>{state.view='all';state.filters={};state.q='';byId('search').value='';closeDrawer();render()};render();
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
