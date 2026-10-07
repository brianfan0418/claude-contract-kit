/* Demonstration adapter: the same validation/workflow as REST, browser storage only. */
(() => {
 const clone=value=>JSON.parse(JSON.stringify(value));
 class BrowserDataSource extends ContractHttp.HttpDataSource {
  constructor(seed,storage=null,key='contract-browser-demo-v1'){
   super('',async()=>{throw Error('展示版不使用網路資料介面')});
   this.mode='demo';this.storage=storage;this.storageKey=key;this.persistent=Boolean(storage);this.db=clone(seed);
   try{const raw=storage?.getItem(key);if(raw){const saved=JSON.parse(raw);if(!saved.config?.schema?.fields||!['contracts','cases','progress','review_versions','review_comments'].every(k=>Array.isArray(saved[k])))throw Error('展示資料格式不符');this.db=saved}}catch{this.persistent=false}
  }
  async api(path,method='GET',body){
   const [name,encoded]=path.split('/'),id=encoded===undefined?undefined:decodeURIComponent(encoded);
   if(!Object.hasOwn(this.db,name))throw Error('找不到展示集合');
   const collection=this.db[name];let value;
   if(method==='GET'){value=id===undefined?collection:collection.find(r=>String(r.id)===id);if(value===undefined)throw Error('找不到展示紀錄');return clone(value)}
   if(!Array.isArray(collection))throw Error('展示設定為唯讀');
   if(method==='POST'){if(collection.some(r=>String(r.id)===String(body.id)))throw Error('編號已存在');value=clone(body);if(['contracts','cases'].includes(name)){value.demo=true;value.demo_fields=Object.keys(value.fields||{})}collection.push(value)}
   else if(method==='PATCH'){value=collection.find(r=>String(r.id)===id);if(!value)throw Error('找不到展示紀錄');Object.assign(value,clone(body))}
   else throw Error('展示版僅提供新增與更新');
   try{if(this.storage){this.storage.setItem(this.storageKey,JSON.stringify(this.db));this.persistent=true}else this.persistent=false}catch{this.persistent=false}
   return clone(value);
  }
  status(){return '展示版：資料只存在本瀏覽器'+(this.persistent?'':'；瀏覽器未允許保存，關閉後資料不保留。')}
 }
 window.ContractBrowser={BrowserDataSource};
 if(window.CONTRACT_DEMO_DATA)window.createDataSource=()=>{let storage=null;try{storage=localStorage}catch{}return new BrowserDataSource(window.CONTRACT_DEMO_DATA,storage,'contract-browser-demo-v14:'+location.pathname)};
})();
