/* Review validation; W3C TextQuoteSelector anchors immutable versions. */
(()=>{
  function validateReview(data){
    const ids=new Set();for(const v of data.versions){if(!v.version_id||ids.has(v.version_id)||!Array.isArray(v.clauses))throw new Error('審閱版本格式或編號不符');ids.add(v.version_id);const clauses=new Set();for(const c of v.clauses){if(!c.id||clauses.has(c.id)||typeof c.text!=='string')throw new Error('條號須唯一，條款須為文字');clauses.add(c.id)}}
    const events=new Set(),roots=new Map();for(const e of data.comments){if(!e.id||events.has(e.id)||!e.thread_id||!e.user||!Number.isFinite(Date.parse(e.time))||!/(Z|[+-]\d{2}:\d{2})$/.test(e.time)||!['comment','resolve','reopen'].includes(e.action))throw new Error('審閱留言格式不符');events.add(e.id);const v=data.versions.find(v=>v.version_id===e.version_id),c=v?.clauses.find(c=>c.id===e.clause_id);if(!c||e.selector?.type!=='TextQuoteSelector'||!c.text.includes(e.selector.exact)||!e.selector.exact)throw new Error('審閱原文錨點不符');if(!roots.has(e.thread_id)){if(e.action!=='comment')throw new Error('留言串缺少首筆留言');roots.set(e.thread_id,e)}else{const root=roots.get(e.thread_id);if(root.clause_id!==e.clause_id||root.version_id!==e.version_id||JSON.stringify(root.selector)!==JSON.stringify(e.selector))throw new Error('留言串錨點不可改動')}if(e.action==='comment'&&!String(e.comment||'').trim())throw new Error('留言不可空白')}
    return data;
  }
window.ContractReviewData={validateReview};
})();
