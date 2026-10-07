// Local-only json-server host. beta.15's CLI parses --host but omits it from listen().
import {resolve,dirname,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {existsSync} from 'node:fs';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
const root=dirname(fileURLToPath(import.meta.url));process.chdir(root);
const port=Number(process.argv.find(a=>/^\d+$/.test(a))||3000);
if(!Number.isInteger(port)||port<1024||port>65535)throw Error('Port must be 1024–65535');
// CONTRACT_NODE_MODULES is a test-only dependency location; normal install uses ./node_modules.
const modules=process.env.CONTRACT_NODE_MODULES||join(root,'node_modules');
if(!existsSync(join(modules,'json-server/lib/app.js'))){console.error('Install Node.js >=22.12.0, then run: npm install');process.exit(1)}
const {createApp}=await import(pathToFileURL(join(modules,'json-server/lib/app.js')));
const {Low}=await import(pathToFileURL(join(modules,'lowdb/lib/index.js')));
const {JSONFile}=await import(pathToFileURL(join(modules,'lowdb/lib/node.js')));
const database=resolve('data/db.json');if(!existsSync(database))throw Error('data/db.json is missing; run build_dashboard.py first');
const db=new Low(new JSONFile(database),{});await db.read();
const staticDir=existsSync(resolve('app/index.html'))?'app':'面板';
const app=createApp(db,{logger:false,static:[resolve(staticDir)]});
// The listener is explicitly restricted to the loopback interface.
const server=createServer((req,res)=>{const origin=req.headers.origin;if(origin&&![`http://127.0.0.1:${port}`,`http://localhost:${port}`].includes(origin)){res.writeHead(403);res.end('Local origin required');return}app.attach(req,res)}).listen(port,'127.0.0.1',()=>{
 const url=`http://127.0.0.1:${port}/`;console.log(`Local contract system: ${url}\nData: ${database}\nStop: Ctrl+C`);
 if(process.argv.includes('--open')){const command=process.platform==='win32'?'cmd':process.platform==='darwin'?'open':'xdg-open',args=process.platform==='win32'?['/c','start','',url]:[url];const child=spawn(command,args,{stdio:'ignore',detached:true});child.on('error',()=>console.log('Open the URL in your browser.'));child.unref()}
});
server.on('error',error=>{console.error(error.message);process.exitCode=1});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>process.exit(0)));
