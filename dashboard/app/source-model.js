/* Human-readable field provenance; source text never becomes HTML. */
(() => {
 function sourceRows(record,schema){
  let refs=record.fields?.source_refs;
  if(typeof refs==='string'){try{refs=JSON.parse(refs)}catch{return []}}
  if(!refs||typeof refs!=='object'||Array.isArray(refs))return [];
  return Object.entries(refs).map(([key,ref])=>{
   if(!ref||typeof ref!=='object')ref={quote:String(ref??'')};
   const printed=ref.printed_pages?.[0]??ref.page??ref.page_number;
   const physical=ref.pdf_pages?.[0]??printed;
   let url='';try{const candidate=new URL(ref.source_url||ref.url);if(['https:','http:'].includes(candidate.protocol)){if(physical)candidate.hash='page='+physical;url=candidate.href}}catch{}
   return {key,label:schema.fields.find(f=>f.name===key)?.label||key,
    quote:ref.quote||ref.original_quote||(ref.transformation?'未載明（'+ref.transformation+'）':'未載明'),
    source:printed?'年報第 '+printed+' 頁':(ref.source_name||'未載明'),url,
    status:ref.verification_status||record.fields.verification_status||'未驗證'};
  });
 }
 function isDemoField(record,key){return record.demo===true&&Array.isArray(record.demo_fields)&&record.demo_fields.includes(key)}
 window.ContractSources={sourceRows,isDemoField};
})();
