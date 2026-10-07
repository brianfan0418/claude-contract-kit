/* Fluent DataGrid resize handles and WAI-ARIA separator keyboard interaction. */
(() => {
 const MIN=80,MAX=1000,KEY='contract-column-widths-v1';
 const clamp=value=>Math.max(MIN,Math.min(MAX,Math.round(Number(value)||MIN)));
 function read(storage){try{const value=JSON.parse(storage.getItem(KEY)||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{}}catch{return {}}}
 function save(storage,value){try{storage.setItem(KEY,JSON.stringify(value));return true}catch{return false}}
 function keyboardWidth(width,key,shift=false){const step=shift?32:16;return key==='ArrowLeft'?clamp(width-step):key==='ArrowRight'?clamp(width+step):key==='Home'?MIN:key==='End'?MAX:null}
 function attach(table,keys,kind,storage){
  const preferences=read(storage),saved=preferences[kind]||{},cols=document.createElement('colgroup');
  const defaults={contract_id:112,case_number:160,title:210,department:160,owner:120,counterparty_name:260,contract_type:144,status:112,end_date:128,renewal_type:132,notice_days:120,contract_value:144,currency:100,contract_language:112,governing_law:148,dispute_resolution:200,stage:144};
  const measured=keys.map((key,i)=>saved[key]?clamp(saved[key]):clamp(defaults[key]||table.tHead.rows[0].cells[i].getBoundingClientRect().width));
  table.querySelector('colgroup')?.remove();
  for(const width of measured){const col=document.createElement('col');col.style.width=width+'px';cols.append(col)}table.prepend(cols);
  const layout=()=>{table.style.width=measured.reduce((a,b)=>a+b,0)+'px';table.classList.add('resizable-table')};layout();
  table.columnSizes={};
  for(const [i,key]of keys.entries()){
   const th=table.tHead.rows[0].cells[i],handle=document.createElement('span');handle.className='column-resizer';handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-label','調整'+th.textContent+'欄寬');handle.setAttribute('aria-orientation','vertical');handle.setAttribute('aria-valuemin',MIN);handle.setAttribute('aria-valuemax',MAX);handle.setAttribute('aria-controls',table.id);handle.setAttribute('aria-keyshortcuts','ArrowLeft ArrowRight Home End Enter');
   const apply=(value,persist=true)=>{measured[i]=clamp(value);cols.children[i].style.width=measured[i]+'px';handle.setAttribute('aria-valuenow',measured[i]);layout();if(persist){preferences[kind]={...(preferences[kind]||{}),[key]:measured[i]};save(storage,preferences)}};
   const fit=()=>{const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');ctx.font=getComputedStyle(table).font;let width=ctx.measureText(th.querySelector('button').textContent).width+42;for(const row of table.tBodies[0].rows){if(row.cells.length===keys.length)width=Math.max(width,ctx.measureText(row.cells[i].textContent).width+24)}apply(width)};
   table.columnSizes[key]={label:th.querySelector('button').textContent,get:()=>measured[i],apply,fit};
   apply(measured[i],false);handle.onclick=e=>e.stopPropagation();handle.ondblclick=e=>{e.preventDefault();e.stopPropagation();fit()};handle.onkeydown=e=>{const width=keyboardWidth(measured[i],e.key,e.shiftKey);if(width!==null||e.key==='Enter'){e.preventDefault();e.stopPropagation();if(e.key==='Enter')fit();else apply(width)}};
   handle.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();e.stopPropagation();const start=e.clientX,width=measured[i];handle.setPointerCapture(e.pointerId);handle.focus();document.body.classList.add('resizing');handle.onpointermove=event=>apply(width+event.clientX-start,false);const stop=()=>{handle.onpointermove=null;apply(measured[i]);document.body.classList.remove('resizing')};handle.onpointerup=stop;handle.onpointercancel=stop;handle.onlostpointercapture=stop};th.append(handle);
  }
 }
 function editor(table){
  // A single-pointer alternative to dragging (WCAG 2.2, 2.5.7).
  let dialog=document.getElementById('column-width-editor');if(dialog)dialog.remove();
  dialog=document.createElement('dialog');dialog.id='column-width-editor';dialog.setAttribute('aria-labelledby','column-width-title');
  const header=document.createElement('header');header.className='dialog-head';const title=document.createElement('h2');title.id='column-width-title';title.textContent='調整欄寬';header.append(title);dialog.append(header);
  const form=document.createElement('form'),fields=document.createElement('div');fields.className='form-fields';const select=document.createElement('select'),number=document.createElement('input');number.type='number';number.min=MIN;number.max=MAX;number.step=1;number.required=true;
  for(const [key,item]of Object.entries(table.columnSizes||{})){const option=document.createElement('option');option.value=key;option.textContent=item.label;select.append(option)}
  for(const [text,input]of [['欄位',select],['欄寬（px）',number]]){const label=document.createElement('label');label.className='field';label.append(document.createTextNode(text),input);fields.append(label)}
  const sync=()=>number.value=table.columnSizes[select.value].get();select.onchange=sync;sync();form.append(fields);const footer=document.createElement('footer');footer.className='dialog-foot';
  for(const text of ['自動適應','取消','套用']){const button=document.createElement('button');button.textContent=text;button.type=text==='套用'?'submit':'button';if(text==='套用')button.className='primary';if(text==='自動適應')button.onclick=()=>{table.columnSizes[select.value].fit();sync()};if(text==='取消')button.onclick=()=>dialog.close();footer.append(button)}form.append(footer);form.onsubmit=e=>{e.preventDefault();table.columnSizes[select.value].apply(number.value);dialog.close()};dialog.append(form);document.body.append(dialog);dialog.showModal();
 }
 window.ContractColumnResize={MIN,MAX,clamp,read,save,keyboardWidth,attach,editor};
})();
