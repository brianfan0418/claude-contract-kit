/* HTTP adapter for a local json-server. No direct database/file writes. */
(()=>{
 const uid=()=>crypto.randomUUID(),now=()=>new Date().toISOString();
 function validate(fields,schema,isCase=false,previous=null){
  const result={...fields};
  for(const f of schema.fields){
   if(previous!==null&&(!Object.hasOwn(fields,f.name)||fields[f.name]===(previous[f.name]??'')))continue;
   const raw=fields[f.name];
   if(raw!==undefined&&raw!==null&&(typeof raw==='boolean'||typeof raw==='object'||(!['number','integer'].includes(f.type)&&typeof raw!=='string')))throw new Error(`${f.label}格式不符`);
   const value=String(raw??'').trim();result[f.name]=value;
   if(f.required&&!value&&!(isCase&&f.name==='contract_id'))throw new Error(`${f.label}尚未填寫`);
   if(!value)continue;
   if(f.type==='date'&&(!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value))||new Date(value+'T00:00:00Z').toISOString().slice(0,10)!==value))throw new Error(`${f.label}日期不符`);
   if(['number','integer'].includes(f.type)&&(!Number.isFinite(Number(value))||(f.type==='integer'&&!Number.isInteger(Number(value)))))throw new Error(`${f.label}數值不符`);
   if(f.type==='enum'){const values=(schema.enums?.[f.enum||f.name]||[]).map(x=>typeof x==='string'?x:x.label);if(!values.includes(value))throw new Error(`${f.label}不在選項內`)}
   if(f.pattern&&!new RegExp(f.pattern).test(value))throw new Error(`${f.label}格式不符`);
  }
  return result;
 }
 function changedFields(values,initial,schema){return Object.fromEntries(schema.fields.filter(f=>Object.hasOwn(values,f.name)&&String(values[f.name]??'')!==String(initial[f.name]??'')).map(f=>[f.name,values[f.name]]))}
 function requiredOnCreate(f){return Boolean(f.required)&&!['contract_id','updated_at'].includes(f.name)}
 function displayValue(value){return value===undefined||value===null||String(value).trim()===''?'未載明':String(value)}

 class HttpDataSource {
  constructor(base='',request=globalThis.fetch.bind(globalThis)){this.base=base.replace(/\/$/,'');this.request=request;this.writable=false}
  async api(path,method='GET',body){const r=await this.request(this.base+'/'+path,{method,headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});if(!r.ok)throw new Error(`本機介面 ${method} ${path} 失敗（${r.status}）`);return r.status===204?null:r.json()}
  async init(){this.config=await this.api('config');if(!this.config?.schema?.fields)throw new Error('本機設定缺少欄位定義');this.writable=true;return this.config}
  async list(kind){if(!['contracts','cases'].includes(kind))throw new Error('未知集合');return this.api(kind)}
  async read(kind,id){const r=await this.api(kind+'/'+encodeURIComponent(id));return {...r,progress:kind==='cases'?(await this.api('progress')).filter(e=>e.case_id===id).sort((a,b)=>Date.parse(a.time)-Date.parse(b.time)):[]}}
  actor(body){if(!String(body.user||'').trim())throw new Error('處理人尚未填寫');if(!String(body.comment||'').trim())throw new Error('處理意見尚未填寫')}
  async create(kind,body){this.actor(body);const incoming={...body.fields};if(kind==='contracts'&&!incoming.contract_id){const reserved=new Set((await this.list(kind)).map(r=>r.fields.contract_id||r.id));let n=1;const prefix='C-'+new Date().getFullYear()+'-';while(reserved.has(prefix+String(n).padStart(4,'0')))n++;incoming.contract_id=prefix+String(n).padStart(4,'0');incoming.contract_id_origin='system'}incoming.updated_at=ContractTable.localToday();const fields=validate(incoming,this.config.schema,kind==='cases');if(incoming.contract_id_origin)fields.contract_id_origin=incoming.contract_id_origin;const id=kind==='cases'?'CASE-'+new Date().toISOString().slice(0,10).replaceAll('-','')+'-'+uid().slice(0,8):fields.contract_id;if((await this.list(kind)).some(r=>r.id===id||r.fields.contract_id===id))throw new Error('編號已存在');const record=await this.api(kind,'POST',{id:uid(),fields,updated_by:body.user,...(kind==='cases'?{stage:'收件',case_number:id}:{})});if(kind==='cases')await this.log(record.id,{time:now(),user:body.user,action:'新增案件',from_stage:'',to_stage:'收件',comment:body.comment,attachment_version:body.attachment_version||''});return this.read(kind,record.id)}
  async update(kind,id,body){this.actor(body);const current=await this.read(kind,id),changes={...body.fields,updated_at:ContractTable.localToday()};if(kind==='contracts')delete changes.contract_id;const fields={...current.fields,...validate(changes,this.config.schema,kind==='cases',current.fields)};await this.api(kind+'/'+encodeURIComponent(id),'PATCH',{fields,updated_by:body.user});if(kind==='cases')await this.log(id,{time:now(),user:body.user,action:'更新欄位',from_stage:current.stage,to_stage:current.stage,comment:body.comment,attachment_version:body.attachment_version||''});return this.read(kind,id)}
  log(id,event){return this.api('progress','POST',{...event,id:uid(),case_id:id})}
  async appendProgress(kind,id,body){if(kind!=='cases')throw new Error('進度只供案件使用');this.actor(body);const current=await this.read(kind,id),stage=body.stage||current.stage;if(stage!==current.stage&&!this.config.transitions[current.stage]?.includes(stage))throw new Error('不允許的狀態轉換');await this.log(id,{time:now(),user:body.user,action:stage===current.stage?'加入意見':'狀態變更',from_stage:current.stage,to_stage:stage,comment:body.comment,attachment_version:body.attachment_version||''});await this.api('cases/'+encodeURIComponent(id),'PATCH',{stage,updated_by:body.user});return this.read(kind,id)}
  async readReview(id){const [versions,comments]=await Promise.all([this.api('review_versions'),this.api('review_comments')]);return ContractReviewData.validateReview({versions:versions.filter(v=>v.case_id===id).sort((a,b)=>a.version_id.localeCompare(b.version_id,undefined,{numeric:true})),comments:comments.filter(c=>c.case_id===id).sort((a,b)=>Date.parse(a.time)-Date.parse(b.time))})}
  async appendReview(id,body){if(!String(body.user||'').trim())throw new Error('處理人尚未填寫');const data=await this.readReview(id);if(body.expectedVersion!==data.versions.at(-1)?.version_id)throw new Error('條款版本已更新，建議重新載入');const entry={id:uid(),case_id:id,thread_id:body.thread_id||'',clause_id:body.clause_id,version_id:body.version_id,selector:body.selector,user:body.user,time:now(),action:body.action||'comment',comment:body.comment||''};if(!entry.thread_id)entry.thread_id=entry.id;ContractReviewData.validateReview({versions:data.versions,comments:[...data.comments,entry]});await this.api('review_comments','POST',entry);return this.readReview(id)}
 }
 window.ContractHttp={HttpDataSource,validate,changedFields,requiredOnCreate,displayValue};window.createDataSource=()=>new HttpDataSource();
})();
