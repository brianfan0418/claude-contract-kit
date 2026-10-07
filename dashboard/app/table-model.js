/* Date-only reminders use the browser's current local calendar date. */
(() => {
 const DAY=86400000;
 function dateNumber(value){const s=String(value||'').trim();if(!/^\d{4}-\d{2}-\d{2}$/.test(s))return null;const time=Date.parse(s+'T00:00:00Z');return Number.isFinite(time)&&new Date(time).toISOString().slice(0,10)===s?time:null}
 function localToday(now=new Date()){return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`}
 function reminder(fields,today=localToday()){const end=dateNumber(fields.end_date),now=dateNumber(today),days=end===null||now===null?null:(end-now)/DAY;const n=String(fields.notice_days??'').trim(),notice=/^\d+$/.test(n)&&Number.isSafeInteger(Number(n))?Number(n):null;const noticeDays=days===null||notice===null?null:days-notice;return {days,noticeDays,expired:days!==null&&days<0,expiring:days!==null&&days>=0&&days<=90,noticeDue:days!==null&&days>=0&&fields.renewal_type==='自動續約'&&noticeDays!==null&&noticeDays<=90,endUnknown:end===null}}
 function matchView(record,view,kind='contracts',today=localToday()){const r=reminder(record.fields,today);if(view==='全部')return true;if(view==='已逾期')return r.expired;if(view==='90 天內到期')return r.expiring;if(view==='自動續約須通知')return r.noticeDue;if(view==='到期日未載明')return r.endUnknown;if(view==='審閱中')return kind==='cases'?!['歸檔','簽署'].includes(record.stage):record.fields.status==='審閱中';return false}
 function visibleColumns(defaults,available,records,overrides={}){return available.filter(key=>Object.hasOwn(overrides,key)?overrides[key]===true:defaults.includes(key)&&records.some(r=>String(key==='stage'?r.stage??'':r.fields[key]??'').trim()!==''))}
 function readColumns(storage){try{const raw=JSON.parse(storage.getItem('contract-columns-v1')||'{}');return raw&&typeof raw==='object'&&!Array.isArray(raw)?raw:{}}catch{return {}}}
 function saveColumns(storage,value){try{storage.setItem('contract-columns-v1',JSON.stringify(value));return true}catch{return false}}
 window.ContractTable={dateNumber,localToday,reminder,matchView,visibleColumns,readColumns,saveColumns};
})();
