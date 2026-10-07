const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),{webcrypto}=require('crypto');
global.window=global;global.crypto=webcrypto;
for(const file of ['datasource.js','review-data.js','review.js','table-model.js','source-model.js','column-resize.js'])vm.runInThisContext(fs.readFileSync(__dirname+'/app/'+file,'utf8'));
let count=0;async function test(name,fn){await fn();count++;console.log('PASS '+name)}
const schema={fields:[{name:'contract_id',label:'編號',type:'string',required:true},{name:'title',label:'名稱',type:'string',required:true},{name:'status',label:'狀態',type:'enum',required:true},{name:'date',label:'日期',type:'date'},{name:'amount',label:'金額',type:'number'},{name:'days',label:'天數',type:'integer'},{name:'updated_at',label:'更新日',type:'date',required:true}],enums:{status:['有效','審閱中']}};
const db={config:{schema,stages:['收件','法務審閱','歸檔'],transitions:{'收件':['法務審閱'],'法務審閱':['歸檔']}},contracts:[],cases:[],progress:[],review_versions:[],review_comments:[]},writes=[];
let seq=0;const request=async(url,options)=>{const [name,id]=url.replace(/^\//,'').split('/'),method=options.method,body=options.body?JSON.parse(options.body):null;let result;
 if(method==='GET'){result=id?db[name].find(r=>r.id===id):db[name];if(!result)return{ok:false,status:404}}
 else{writes.push({name,method,body});if(method==='POST'){result={...body,id:body.id??++seq};db[name].push(result)}else if(method==='PATCH'){const r=db[name].find(r=>r.id===id);if(!r)return{ok:false,status:404};Object.assign(r,body);result=r}else throw Error('unexpected method')}
 return{ok:true,status:200,json:async()=>structuredClone(result)}};
const source=new ContractHttp.HttpDataSource('',request),valid={title:'範例合約',status:'有效'},body=()=>({fields:{...valid},user:'範例甲',comment:'收到需求'});
(async()=>{
await test('Configuration loads through HTTP',async()=>{assert.equal(source.writable,false);await source.init();assert.equal(source.writable,true)});
await test('Invalid mandatory values send no writes',async()=>{const n=writes.length;await assert.rejects(source.create('contracts',{...body(),fields:{status:'有效'}}),/名稱/);assert.equal(writes.length,n)});
await test('Date integer enum and nonfinite rejected',async()=>{for(const fields of [{date:'2026-02-30'},{days:'1.2'},{amount:'Infinity'},{status:'未知'}]){const n=writes.length;await assert.rejects(source.create('contracts',{...body(),fields:{...valid,...fields}}));assert.equal(writes.length,n)}});
let contract,record;
await test('v0 preserves a string UUID distinct from the human contract number',async()=>{contract=await source.create('contracts',body());assert.match(contract.id,/^[a-f0-9-]{36}$/);assert.match(contract.fields.contract_id,/^C-\d{4}-0001$/);assert.equal(contract.fields.contract_id_origin,'system')});
await test('Case creation gets a human case number and initial log',async()=>{record=await source.create('cases',body());assert.match(record.case_number,/^CASE-/);assert.equal(record.stage,'收件');assert.equal(record.progress.length,1);assert.equal(record.progress[0].case_id,record.id)});
await test('Progress persists actor comment attachment and stage',async()=>{record=await source.appendProgress('cases',record.id,{user:'範例乙',comment:'完成初審',attachment_version:'V2',stage:'法務審閱'});assert.equal(record.stage,'法務審閱');assert.equal(record.progress.length,2);assert.equal(record.progress[1].user,'範例乙');assert.equal(record.progress[1].attachment_version,'V2')});
await test('Invalid transition and missing actor do not write',async()=>{for(const b of [{user:'甲',comment:'跳關',stage:'收件'},{user:'',comment:'x',stage:'歸檔'}]){const n=writes.length;await assert.rejects(source.appendProgress('cases',record.id,b));assert.equal(writes.length,n)}});
await test('Editing keeps system contract number and source references',async()=>{db.contracts[0].fields.source_refs='page 1';const r=await source.update('contracts',contract.id,{...body(),fields:{...contract.fields,title:'更新',contract_id:'other'}});assert.equal(r.fields.contract_id,contract.fields.contract_id);assert.equal(r.fields.source_refs,'page 1')});
await test('Case edit appends same-state history',async()=>{const r=await source.update('cases',record.id,{...body(),fields:{...record.fields,title:'更新案件'}});assert.equal(r.progress.at(-1).action,'更新欄位');assert.equal(r.progress.at(-1).to_stage,'法務審閱')});
await test('Historical enum can be kept but new unknown enum rejected',async()=>{db.contracts[0].fields.status='舊資料';await source.update('contracts',contract.id,{...body(),fields:{...db.contracts[0].fields,title:'保留舊值'}});await assert.rejects(source.update('contracts',contract.id,{...body(),fields:{...db.contracts[0].fields,status:'另一個未知'}}),/選項/)});
await test('Partial updates retain missing mandatory and malformed legacy fields',async()=>{
 for(const kind of ['contracts','cases']){
  const legacy={id:'legacy-'+kind,stage:'收件',fields:{contract_id:'LEGACY-01',title:'',status:'',date:'原文未載明',amount:'未知',notes:'',source_refs:'page 1'}};
  db[kind].push(legacy);const old=structuredClone(legacy.fields);
  const updated=await source.update(kind,legacy.id,{user:'甲',comment:'補充',fields:{notes:'只改備註'}});
  assert.equal(updated.fields.notes,'只改備註');
  for(const [name,value] of Object.entries(old))if(name!=='notes')assert.equal(updated.fields[name],value);
  if(kind==='cases')assert.equal(updated.progress.at(-1).action,'更新欄位');
 }
});
await test('Changed fields still require valid values and cannot clear a known mandatory value',async()=>{
 const legacy=db.contracts.find(r=>r.id==='legacy-contracts');legacy.fields.title='既有名稱';
 for(const fields of [{title:''},{date:'2026-02-30'},{days:'1.5'},{amount:'Infinity'},{status:'新未知值'},{title:[]}]){
  const n=writes.length;await assert.rejects(source.update('contracts',legacy.id,{user:'甲',comment:'x',fields}));assert.equal(writes.length,n);
 }
});
await test('Editor sends only fields changed from its displayed initial values',()=>{
 const initial={contract_id:'LEGACY-01',title:'',status:'',date:'',amount:'0',updated_at:'2026-10-07'};
 assert.deepEqual(ContractHttp.changedFields({...initial,title:'補充名稱',_comment:'x'},initial,schema),{title:'補充名稱'});
 assert.deepEqual(ContractHttp.changedFields({...initial,amount:'1'},initial,schema),{amount:'1'});
 assert.equal(ContractHttp.requiredOnCreate(schema.fields.find(f=>f.name==='title')),true);
 assert.equal(ContractHttp.requiredOnCreate(schema.fields.find(f=>f.name==='contract_id')),false);
 for(const value of ['',null,undefined,'  '])assert.equal(ContractHttp.displayValue(value),'未載明');
 assert.equal(ContractHttp.displayValue(0),'0');
});
db.review_versions.push({id:'rv',case_id:record.id,version_id:'V1',clauses:[{id:'第1條',text:'付款期限三十日'}]});
let review;
await test('v0 preserves review comment ID and stable thread key',async()=>{review=await source.appendReview(record.id,{user:'甲',comment:'請確認',expectedVersion:'V1',version_id:'V1',clause_id:'第1條',selector:{type:'TextQuoteSelector',exact:'三十日',prefix:'付款期限',suffix:''}});assert.equal(review.comments.length,1);assert.equal(review.comments[0].id,review.comments[0].thread_id)});
await test('Review resolves via a new event and retains original',async()=>{const root=review.comments[0];review=await source.appendReview(record.id,{...root,action:'resolve',expectedVersion:'V1',user:'乙',comment:''});assert.equal(review.comments.length,2);assert.equal(review.comments[0].action,'comment');assert.equal(ContractReview.threads(review.comments)[0].status,'已解決')});
await test('Wrong review anchor or outdated version rejected without writes',async()=>{for(const b of [{expectedVersion:'old',selector:{type:'TextQuoteSelector',exact:'三十日'}},{expectedVersion:'V1',selector:{type:'TextQuoteSelector',exact:'不存在'}}]){const n=writes.length;await assert.rejects(source.appendReview(record.id,{user:'甲',comment:'x',version_id:'V1',clause_id:'第1條',...b}));assert.equal(writes.length,n)}});
await test('HTTP errors are surfaced',async()=>{await assert.rejects(source.read('cases','missing'),/404/)});
await test('Browser calendar reminders ignore status and snapshot date',()=>{for(const status of ['', '審閱中', '已終止', '已到期']){const r={fields:{status,end_date:'2026-12-19'}};assert.equal(ContractTable.matchView(r,'90 天內到期','contracts','2026-10-07'),true);assert.equal(ContractTable.matchView(r,'已逾期','contracts','2027-01-01'),true)}assert.equal(ContractTable.localToday(new Date(2026,9,7,0,5)),'2026-10-07')});
await test('Expiration boundaries and missing date bucket',()=>{for(const [end,expired,soon]of [['2026-10-06',true,false],['2026-10-07',false,true],['2027-01-05',false,true],['2027-01-06',false,false]]){const r=ContractTable.reminder({end_date:end},'2026-10-07');assert.equal(r.expired,expired);assert.equal(r.expiring,soon)}for(const end_date of ['', '未載明','2026-02-30']){const r=ContractTable.reminder({end_date,status:'已到期'},'2026-10-07');assert.equal(r.endUnknown,true);assert.equal(r.expired||r.expiring||r.noticeDue,false)}});
await test('Auto-renewal notice includes overdue deadline before expiry',()=>{const f={end_date:'2026-11-01',notice_days:'30',renewal_type:'自動續約',status:''};assert.equal(ContractTable.reminder(f,'2026-10-07').noticeDue,true);assert.equal(ContractTable.reminder({...f,notice_days:'invalid'},'2026-10-07').noticeDue,false);assert.equal(ContractTable.reminder(f,'2026-11-02').noticeDue,false);assert.equal(ContractTable.reminder({...f,end_date:'2027-11-01'},'2026-10-07').noticeDue,false)});
await test('Empty columns hidden by default and explicit choice preserved',()=>{const records=[{fields:{title:'合約',department:'',amount:'0'}}],available=['title','department','amount'];assert.deepEqual(ContractTable.visibleColumns(available,available,records),['title','amount']);assert.deepEqual(ContractTable.visibleColumns(available,available,records,{title:false,department:true}),['department','amount']);assert.deepEqual(ContractTable.visibleColumns(available,available,[{fields:{department:'法務'}}],{department:false}),[])});
await test('Column preferences persist and blocked storage does not throw',()=>{const stored={};const storage={getItem:k=>stored[k],setItem:(k,v)=>stored[k]=v},prefs={contracts:{department:true,title:false},cases:{stage:true}};assert.equal(ContractTable.saveColumns(storage,prefs),true);assert.deepEqual(ContractTable.readColumns(storage),prefs);assert.deepEqual(ContractTable.readColumns({getItem:()=>'{bad'}),{});const blocked={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}};assert.deepEqual(ContractTable.readColumns(blocked),{});assert.equal(ContractTable.saveColumns(blocked,prefs),false)});
await test('Field sources use labels, original quotes and printed versus PDF pages',()=>{const rows=ContractSources.sourceRows({fields:{source_refs:JSON.stringify({title:{quote:'原文',printed_pages:[12],pdf_pages:[16],source_url:'https://example.org/report.pdf#page=99'}})}},schema);assert.deepEqual(rows,[{key:'title',label:'名稱',quote:'原文',source:'年報第 12 頁',url:'https://example.org/report.pdf#page=16',status:'未驗證'}]);assert.deepEqual(ContractSources.sourceRows({fields:{source_refs:'{broken'}},schema),[]);assert.equal(ContractSources.sourceRows({fields:{source_refs:{title:{source_url:'javascript:alert(1)'}}}},schema)[0].url,'')});
await test('Only explicitly identified fictional fields receive demo markers',()=>{const r={demo:true,demo_fields:['department']};assert.equal(ContractSources.isDemoField(r,'department'),true);assert.equal(ContractSources.isDemoField(r,'title'),false);assert.equal(ContractSources.isDemoField({demo:true},'title'),false)});
await test('Column width bounds, keyboard steps and safe persistence',()=>{const c=ContractColumnResize;assert.equal(c.clamp(1),80);assert.equal(c.clamp(9000),1000);assert.equal(c.keyboardWidth(120,'ArrowRight'),136);assert.equal(c.keyboardWidth(120,'ArrowLeft',true),88);assert.equal(c.keyboardWidth(120,'Home'),80);assert.equal(c.keyboardWidth(120,'End'),1000);assert.equal(c.keyboardWidth(120,'Escape'),null);const value={contracts:{title:240}},db={};const storage={getItem:k=>db[k],setItem:(k,v)=>db[k]=v};assert.equal(c.save(storage,value),true);assert.deepEqual(c.read(storage),value);assert.deepEqual(c.read({getItem:()=>'{broken'}),{});const blocked={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}};assert.deepEqual(c.read(blocked),{});assert.equal(c.save(blocked,value),false)});
console.log(JSON.stringify({checks:count,failed:0}));})().catch(e=>{console.error(e);process.exitCode=1});
