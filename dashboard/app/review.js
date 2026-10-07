/* Clause review: GitHub conversations + W3C TextQuoteSelector concepts. */
(() => {
  function diff(before, after) {
    const a=Array.from(before), b=Array.from(after), out=[];
    const push=(type,text)=>{if(!text)return;if(out.at(-1)?.type===type)out.at(-1).text+=text;else out.push({type,text})};
    if(a.length*b.length>1000000){let p=0,s=0;while(p<a.length&&p<b.length&&a[p]===b[p])p++;while(s<a.length-p&&s<b.length-p&&a.at(-1-s)===b.at(-1-s))s++;push('same',a.slice(0,p).join(''));push('delete',a.slice(p,a.length-s).join(''));push('insert',b.slice(p,b.length-s).join(''));push('same',a.slice(a.length-s).join(''));return out}
    const dp=Array.from({length:a.length+1},()=>new Uint32Array(b.length+1));
    for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)dp[i][j]=a[i]===b[j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
    let i=0,j=0;while(i<a.length||j<b.length){if(i<a.length&&j<b.length&&a[i]===b[j]){push('same',a[i++]);j++}else if(j<b.length&&(i===a.length||dp[i][j+1]>dp[i+1][j]))push('insert',b[j++]);else push('delete',a[i++])}return out;
  }
  function threads(events) {
    const result=new Map();for(const e of events){if(!result.has(e.thread_id))result.set(e.thread_id,{id:e.thread_id,clause_id:e.clause_id,version_id:e.version_id,selector:e.selector,status:'待處理',events:[]});const t=result.get(e.thread_id);t.events.push(e);if(e.action==='resolve')t.status='已解決';if(e.action==='reopen')t.status='待處理'}return [...result.values()];
  }
  const api={diff,threads};globalThis.ContractReview=api;
  if(typeof document==='undefined')return;
  const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
  api.mount=async(container,source,id,options)=>{
    let data=await source.readReview(id),unresolved=false,current=data.versions.at(-1)?.version_id,previous=data.versions.at(-2)?.version_id||'';
    const render=()=>{
      container.replaceChildren();const toolbar=el('div',undefined,'review-toolbar');
      for(const [title,value,set]of[['上一輪',previous,v=>previous=v],['本輪',current,v=>current=v]]){const label=el('label',title),select=el('select');select.append(el('option','無'));for(const v of data.versions){const o=el('option',v.version_id);o.value=v.version_id;select.append(o)}select.value=value||'';select.onchange=()=>{set(select.value);render()};label.append(select);toolbar.append(label)}
      const filter=el('label',undefined,'check-label'),check=el('input');check.type='checkbox';check.checked=unresolved;check.onchange=()=>{unresolved=check.checked;render()};filter.append(check,document.createTextNode('只看未解決'));toolbar.append(filter);container.append(toolbar);
      if(!data.versions.length){container.append(el('p','尚無條款版本；由 AI 將合約按條號建立審閱版本。'));return}
      const old=data.versions.find(v=>v.version_id===previous),now=data.versions.find(v=>v.version_id===current);if(!now){container.append(el('p','請選擇本輪版本。'));return}
      const discussions=threads(data.comments),ids=[...new Set([...(now.clauses||[]).map(c=>c.id),...(old?.clauses||[]).map(c=>c.id)])];let shown=0;
      const submit=async(body,button,error)=>{button.disabled=true;try{await source.appendReview(id,{...body,user:options.actor(),expectedVersion:now.version_id});data=await source.readReview(id);render()}catch(e){error.textContent=e.message}finally{button.disabled=false}};
      for(const clauseId of ids){const a=old?.clauses.find(c=>c.id===clauseId),b=now.clauses.find(c=>c.id===clauseId),list=discussions.filter(t=>t.clause_id===clauseId&&(!unresolved||t.status==='待處理'));if(unresolved&&!list.length)continue;shown++;
        const card=el('section',undefined,'review-clause');card.dataset.clauseId=clauseId;card.append(el('h3',`${clauseId} ${b?.title||a?.title||''}`));const changes=el('p',undefined,'clause-diff');changes.setAttribute('aria-label','刪除以刪除線、增加以底線表示');for(const part of diff(a?.text||'',b?.text||''))changes.append(el(part.type==='delete'?'del':part.type==='insert'?'ins':'span',part.text));card.append(changes);
        for(const t of list){const thread=el('section',undefined,'review-thread');thread.append(el('h4',`${t.status} · ${t.version_id}`));if(t.selector?.exact)thread.append(el('blockquote',t.selector.exact));if(!data.versions.find(v=>v.version_id===t.version_id)?.clauses.find(c=>c.id===t.clause_id)?.text.includes(t.selector?.exact||''))thread.append(el('p','原文錨點已失效，請回來源核對。','form-error'));
          for(const e of t.events){thread.append(el('p',`${e.user} · ${new Date(e.time).toLocaleString('zh-TW')} · ${e.action==='resolve'?'標記已解決':e.action==='reopen'?'重新開啟':'留言'}`,'meta'));if(e.comment)thread.append(el('p',e.comment))}
          if(source.writable){const reply=el('form',undefined,'review-reply'),label=el('label','回覆'),input=el('textarea');input.required=true;label.append(input);const button=el('button','送出回覆'),err=el('p',undefined,'form-error');err.setAttribute('role','alert');reply.append(label,button,err);reply.onsubmit=e=>{e.preventDefault();submit({thread_id:t.id,clause_id:clauseId,version_id:t.version_id,selector:t.selector,comment:input.value,action:'comment'},button,err)};thread.append(reply);const state=el('button',t.status==='已解決'?'重新開啟':'標記已解決');state.type='button';state.onclick=()=>submit({thread_id:t.id,clause_id:clauseId,version_id:t.version_id,selector:t.selector,action:t.status==='已解決'?'reopen':'resolve',comment:''},state,err);thread.append(state)}card.append(thread)}
        if(source.writable){const form=el('form',undefined,'review-new'),label=el('label','新增留言'),input=el('textarea');input.required=true;label.append(input);const button=el('button','送出留言','primary'),err=el('p',undefined,'form-error');err.setAttribute('role','alert');form.append(label,button,err);form.onsubmit=e=>{e.preventDefault();submit({clause_id:clauseId,version_id:b?.text?now.version_id:old.version_id,selector:{type:'TextQuoteSelector',exact:b?.text||a?.text||'',prefix:'',suffix:''},comment:input.value,action:'comment'},button,err)};card.append(form)}container.append(card)
      }if(!shown)container.append(el('p','沒有未解決的留言。'));if(!source.writable)container.append(el('p','連接資料夾後可留言、回覆與標記已解決。','muted'));
    };render();
  };
})();
