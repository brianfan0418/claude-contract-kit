#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""讀取合約主檔 register.csv，產生單一 HTML 面板（無外部相依，離線可開）。

用法：
    python build_dashboard.py [--register ../schema/register.csv] [--out dashboard.html] [--today YYYY-MM-DD]

計算規則（與 contracts/README.md 一致）：
    有效        狀態為「有效」，且到期日未過或無到期日
    已到期      狀態為「已到期」，或狀態為「有效」但到期日早於基準日
    90 天內到期  有效，且 0 <= 到期日 - 基準日 <= 90
    自動續約須通知  有效、續約方式為「自動續約」、有通知期限與到期日，
                  且 基準日 <= 通知截止日 <= 基準日 + 90
    通知截止日   到期日 - 通知期限（天）
"""

import argparse
import csv
import datetime as dt
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REGISTER = HERE.parent / "schema" / "register.csv"
DEFAULT_OUT = HERE / "dashboard.html"
WINDOW_DAYS = 90
REQUIRED_COLUMNS = [
    "contract_id", "title", "contract_type", "department", "counterparty_name",
    "status", "end_date", "renewal_type", "notice_days", "toc", "key_clauses",
]
FILTERS = [
    ("department", "部門"),
    ("counterparty_category", "對象類別"),
    ("contract_type", "類型"),
    ("status", "狀態"),
]


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
        columns = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise ValueError("register.csv 缺少欄位：" + "、".join(missing))
        return [row for row in reader if (row.get("contract_id") or "").strip()]


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


def filter_options(rows):
    return {key: sorted({(r.get(key) or "").strip() for r in rows if (r.get(key) or "").strip()})
            for key, _ in FILTERS}


def build_payload(register_path, today):
    rows = [enrich(r, today) for r in read_register(register_path)]
    return {
        "today": today.isoformat(),
        "window": WINDOW_DAYS,
        "summary": summarize(rows),
        "filters": [{"key": k, "label": l, "options": o}
                    for (k, l), o in zip(FILTERS, filter_options(rows).values())],
        "rows": rows,
    }


def render(payload):
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", data).replace("__TODAY__", html.escape(payload["today"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="由 register.csv 產生合約面板 HTML")
    parser.add_argument("--register", default=str(DEFAULT_REGISTER))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--today", help="基準日 YYYY-MM-DD，預設為本機今天（測試用）")
    args = parser.parse_args(argv)
    today = parse_date(args.today) if args.today else dt.date.today()
    if today is None:
        print("錯誤：--today 格式須為 YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        payload = build_payload(args.register, today)
    except (OSError, ValueError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1
    Path(args.out).write_text(render(payload), encoding="utf-8")
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
:root{--bg:#f6f7f9;--panel:#fff;--ink:#1d2430;--mute:#5d6877;--line:#d9dee5;--accent:#1f5fae;--warn:#b45309;--bad:#b3261e;--ok:#1b7a43;--chip:#e8eef7;--chip-warn:#fdecc8;--chip-bad:#f8d7d3}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14181e;--panel:#1c222b;--ink:#e6e9ee;--mute:#9aa5b4;--line:#323b47;--accent:#6aa5ee;--warn:#e3a14a;--bad:#f08a82;--ok:#62c28b;--chip:#26354b;--chip-warn:#4a3a1c;--chip-bad:#4c2622}}
:root[data-theme="dark"]{--bg:#14181e;--panel:#1c222b;--ink:#e6e9ee;--mute:#9aa5b4;--line:#323b47;--accent:#6aa5ee;--warn:#e3a14a;--bad:#f08a82;--ok:#62c28b;--chip:#26354b;--chip-warn:#4a3a1c;--chip-bad:#4c2622}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Noto Sans TC","Microsoft JhengHei","PingFang TC",system-ui,sans-serif}
main{max-width:1440px;margin:0 auto;padding:16px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 16px;text-align:left;font:inherit;color:inherit;cursor:pointer}
.stat[aria-pressed="true"]{outline:2px solid var(--accent)}
.stat .n{font-size:28px;font-weight:700;line-height:1.2;font-variant-numeric:tabular-nums}
.stat .l{color:var(--mute)}
.stat.warn .n{color:var(--warn)}.stat.bad .n{color:var(--bad)}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 8px}
.bar label{display:flex;flex-direction:column;font-size:12px;color:var(--mute);gap:2px}
select,input[type=search]{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:5px 8px;min-width:130px}
input[type=search]{min-width:240px}
.count{align-self:flex-end;color:var(--mute);margin-left:auto}
.tablewrap{background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:auto}
table{border-collapse:collapse;width:100%}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{position:sticky;top:0;background:var(--panel);font-weight:600;cursor:pointer;user-select:none}
td.t{white-space:normal;min-width:180px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tbody tr.row{cursor:pointer}
tbody tr.row:hover{background:var(--chip)}
.warn-t{color:var(--warn);font-weight:600}.bad-t{color:var(--bad);font-weight:600}.mute{color:var(--mute)}
tr.detail td{white-space:normal;background:var(--bg);padding:12px 16px}
.dgrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.dgrid h3{margin:0 0 4px;font-size:12px;color:var(--mute);font-weight:600}
.dgrid ol,.dgrid ul{margin:0;padding-left:18px}
.dgrid dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:2px 10px}
.dgrid dt{color:var(--mute)}.dgrid dd{margin:0}
h2{font-size:14px;margin:20px 0 8px}
.tl{display:grid;grid-template-columns:repeat(13,minmax(84px,1fr));gap:6px;overflow-x:auto}
.tl .m{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:6px;min-height:70px}
.tl .m.cur{border-color:var(--accent)}
.tl .mh{font-size:12px;color:var(--mute);margin-bottom:4px;font-variant-numeric:tabular-nums}
.chip{display:block;background:var(--chip);border-radius:4px;padding:2px 6px;margin-bottom:3px;font-size:12px;line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
.chip.notice{background:var(--chip-warn)}.chip.over{background:var(--chip-bad)}
.legend{display:flex;gap:12px;font-size:12px;color:var(--mute);margin-bottom:6px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
@media (max-width:760px){.stats{grid-template-columns:repeat(2,1fr)}.dgrid{grid-template-columns:1fr}}
</style>
</head>
<body>
<main>
<div class="stats" id="stats"></div>
<div class="bar" id="bar"></div>
<div class="tablewrap"><table id="tbl"><thead></thead><tbody></tbody></table></div>
<h2>到期時間軸（基準日 __TODAY__）</h2>
<div class="legend"><span><i style="background:var(--chip)"></i>到期日</span><span><i style="background:var(--chip-warn)"></i>通知截止日</span><span><i style="background:var(--chip-bad)"></i>已逾期</span></div>
<div class="tl" id="tl"></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
var D=JSON.parse(document.getElementById('data').textContent);
var rows=D.rows,state={q:'',f:{},stat:null,sort:'end_date',asc:true,open:null};
var COLS=[['contract_id','編號'],['title','名稱'],['contract_type','類型'],['department','部門'],['counterparty_name','對象'],['status','狀態'],['end_date','到期日'],['days_to_end','剩餘天數',1],['notice_deadline','通知截止日'],['renewal_type','續約']];
var STATS=[['active','有效',''],['expiring',D.window+' 天內到期','warn'],['notice_due','自動續約須通知','warn'],['expired','已到期','bad']];
var FLAG={active:'is_active',expiring:'is_expiring',notice_due:'is_notice_due',expired:'is_expired'};
function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e}
function v(r,k){return (r[k]==null?'':String(r[k]))}
function renderStats(){var box=document.getElementById('stats');box.textContent='';STATS.forEach(function(s){
 var b=el('button','stat '+s[2]);b.type='button';b.setAttribute('aria-pressed',state.stat===s[0]);
 b.appendChild(el('div','n',D.summary[s[0]]));b.appendChild(el('div','l',s[1]));
 b.onclick=function(){state.stat=state.stat===s[0]?null:s[0];render()};box.appendChild(b)})}
function renderBar(){var bar=document.getElementById('bar');
 D.filters.forEach(function(f){var l=el('label',null,f.label),s=el('select');s.appendChild(new Option('全部',''));
  f.options.forEach(function(o){s.appendChild(new Option(o,o))});s.onchange=function(){state.f[f.key]=s.value;render()};l.appendChild(s);bar.appendChild(l)});
 var l=el('label',null,'搜尋'),i=el('input');i.type='search';i.oninput=function(){state.q=i.value.trim().toLowerCase();render()};l.appendChild(i);bar.appendChild(l);
 bar.appendChild(el('span','count','')).id='count'}
function visible(){return rows.filter(function(r){
 if(state.stat&&!r[FLAG[state.stat]])return false;
 for(var k in state.f){if(state.f[k]&&v(r,k)!==state.f[k])return false}
 if(state.q){var h=[r.contract_id,r.title,r.counterparty_name,r.owner,r.notes,r.key_clauses].join(' ').toLowerCase();if(h.indexOf(state.q)<0)return false}
 return true})}
function cmp(a,b){var k=state.sort,x=a[k],y=b[k];var nx=(x==null||x===''),ny=(y==null||y==='');if(nx&&ny)return 0;if(nx)return 1;if(ny)return -1;
 var r=(typeof x==='number'&&typeof y==='number')?x-y:String(x).localeCompare(String(y),'zh-Hant');return state.asc?r:-r}
function cell(r,c){var td=el('td',c[2]?'num':(c[0]==='title'?'t':''),'');var x=v(r,c[0]);
 if(c[0]==='days_to_end'&&x!==''){td.textContent=x;if(r.is_expired)td.className+=' bad-t';else if(r.is_expiring)td.className+=' warn-t'}
 else if(c[0]==='notice_deadline'&&x!==''){td.textContent=x;if(r.is_notice_due)td.className+=' warn-t';else if(r.renewal_type==='自動續約'&&r.is_active&&r.days_to_notice<0)td.className+=' bad-t'}
 else if(c[0]==='status'&&r.is_expired&&x==='有效'){td.textContent='有效（已逾期）';td.className+=' bad-t'}
 else td.textContent=x;return td}
function dl(r,pairs){var d=el('dl');pairs.forEach(function(p){var x=v(r,p[0]);if(!x)return;d.appendChild(el('dt',null,p[1]));d.appendChild(el('dd',null,x))});return d}
function list(tag,text){var u=el(tag);(text||'').split('|').forEach(function(s){s=s.trim();if(s)u.appendChild(el('li',null,s))});return u}
function detail(r){var tr=el('tr','detail'),td=el('td');td.colSpan=COLS.length;var g=el('div','dgrid');
 var a=el('div');a.appendChild(el('h3',null,'章節目錄'));a.appendChild(list('ol',r.toc));
 var b=el('div');b.appendChild(el('h3',null,'關鍵條款摘要'));b.appendChild(list('ul',r.key_clauses));
 var c=el('div');c.appendChild(el('h3',null,'主檔資料'));c.appendChild(dl(r,[['our_entity','本方'],['owner','承辦人'],['effective_date','生效日'],['notice_days','通知期限（天）'],['termination_for_convenience','無因終止'],['contract_value','金額'],['currency','幣別'],['payment_terms','付款'],['liability_cap','責任上限'],['governing_law','準據法'],['jurisdiction','管轄'],['prior_contract_id','上期合約'],['risk_level','初審風險'],['file_path','原檔'],['notes','備註']]));
 g.appendChild(a);g.appendChild(b);g.appendChild(c);td.appendChild(g);tr.appendChild(td);return tr}
function renderTable(list_){var th=document.querySelector('#tbl thead'),tb=document.querySelector('#tbl tbody');th.textContent='';tb.textContent='';
 var hr=el('tr');COLS.forEach(function(c){var h=el('th',c[2]?'num':'',c[1]+(state.sort===c[0]?(state.asc?' ▲':' ▼'):''));h.onclick=function(){if(state.sort===c[0])state.asc=!state.asc;else{state.sort=c[0];state.asc=true}render()};hr.appendChild(h)});th.appendChild(hr);
 list_.slice().sort(cmp).forEach(function(r){var tr=el('tr','row');tr.id='r-'+r.contract_id;COLS.forEach(function(c){tr.appendChild(cell(r,c))});
  tr.onclick=function(){state.open=state.open===r.contract_id?null:r.contract_id;render()};tb.appendChild(tr);
  if(state.open===r.contract_id)tb.appendChild(detail(r))});
 document.getElementById('count').textContent=list_.length+' / '+rows.length+' 筆'}
function addMonths(d,n){return new Date(d.getFullYear(),d.getMonth()+n,1)}
function renderTimeline(list_){var tl=document.getElementById('tl');tl.textContent='';var t=new Date(D.today+'T00:00:00'),base=addMonths(t,0),cols=[];
 for(var i=0;i<13;i++){var m=addMonths(base,i),box=el('div','m'+(i===0?' cur':''));box.appendChild(el('div','mh',m.getFullYear()+'-'+('0'+(m.getMonth()+1)).slice(-2)));cols.push({y:m.getFullYear(),m:m.getMonth(),box:box});tl.appendChild(box)}
 function put(date,text,cls,id){if(!date)return;var d=new Date(date+'T00:00:00');var idx=(d.getFullYear()-base.getFullYear())*12+d.getMonth()-base.getMonth();if(idx<0)idx=0;if(idx>12)return;
  var c=el('span','chip '+cls,date.slice(5)+' '+text);c.title=date+' '+text;c.onclick=function(){state.open=id;render();var e=document.getElementById('r-'+id);if(e)e.scrollIntoView({block:'center'})};cols[idx].box.appendChild(c)}
 list_.filter(function(r){return r.status==='有效'}).sort(function(a,b){return String(a.end_date).localeCompare(String(b.end_date))}).forEach(function(r){
  put(r.end_date,r.title,r.is_expired?'over':'',r.contract_id);
  if(r.renewal_type==='自動續約'&&r.notice_deadline&&r.days_to_notice>=0)put(r.notice_deadline,'通知 '+r.title,'notice',r.contract_id)})}
function render(){var l=visible();renderStats();renderTable(l);renderTimeline(l)}
renderBar();render();
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
