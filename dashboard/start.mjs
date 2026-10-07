// json-server 0.17 public module API; local access only.
import {resolve,dirname,join} from 'path';
import {fileURLToPath} from 'url';
import Module from 'module';
import {existsSync} from 'fs';
import {spawn} from 'child_process';
if(Number(process.versions.node.split('.')[0])<12){console.error('Install Node.js 12 or newer.');process.exit(1)}
const root=dirname(fileURLToPath(import.meta.url));process.chdir(root);
const port=Number(process.argv.find(a=>/^\d+$/.test(a))||3000);
if(!Number.isInteger(port)||port<1024||port>65535)throw Error('Port must be 1024–65535');
const modules=process.env.CONTRACT_NODE_MODULES||join(root,'node_modules');
if(!existsSync(join(modules,'json-server/package.json'))){console.error('Run npm ci in this folder first.');process.exit(1)}
// createRequireFromPath supports Node 12.0; createRequire is available from 12.2.
const require=(Module.createRequire||Module.createRequireFromPath)(fileURLToPath(import.meta.url));
const jsonServer=require(join(modules,'json-server'));
const database=resolve('data/db.json');if(!existsSync(database))throw Error('data/db.json is missing; run build_dashboard.py first');
const staticDir=existsSync(resolve('app/index.html'))?'app':'面板';
const app=jsonServer.create();
app.use((req,res,next)=>{const origin=req.headers.origin;if(origin&&![`http://127.0.0.1:${port}`,`http://localhost:${port}`].includes(origin)){res.sendStatus(403);return}next()});
app.use(jsonServer.defaults({logger:false,static:resolve(staticDir),noCors:true}));
// A complete MkDocs output can be shipped next to the application.
const docsDir=resolve(process.env.CONTRACT_DOCS_DIR||'docs-site/site');
if(existsSync(join(docsDir,'index.html')))app.use('/docs',jsonServer.defaults({logger:false,static:docsDir,noCors:true}));
const demoDir=resolve('展示版');
if(existsSync(join(demoDir,'index.html')))app.use('/demo',jsonServer.defaults({logger:false,static:demoDir,noCors:true}));
app.use(jsonServer.router(database));
const server=app.listen(port,'127.0.0.1',()=>{
 const url=`http://127.0.0.1:${port}/`;console.log(`Local contract system: ${url}\nData: ${database}\nStop: Ctrl+C`);
 if(process.argv.includes('--open')){const command=process.platform==='win32'?'cmd':process.platform==='darwin'?'open':'xdg-open',args=process.platform==='win32'?['/c','start','',url]:[url];const child=spawn(command,args,{stdio:'ignore',detached:true});child.on('error',()=>console.log('Open the URL in your browser.'));child.unref()}
});
server.on('error',error=>{console.error(error.message);process.exitCode=1});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>process.exit(0)));
