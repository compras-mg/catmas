const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const base=path.resolve(__dirname,'../site/painel');
const ctx={self:{postMessage(){}},importScripts(){},Intl,Date,fetch:async url=>{const name=String(url).replace(/^\.\.\//,'');return {ok:true,json:async()=>JSON.parse(fs.readFileSync(path.resolve(base,'..',name),'utf8'))};}};
vm.createContext(ctx);
for(const file of ['model.js','content.js'])vm.runInContext(fs.readFileSync(base+'/'+file,'utf8'),ctx);
ctx.CatmasModel=ctx.self.CatmasModel;ctx.CatmasContent=ctx.self.CatmasContent;
vm.runInContext(fs.readFileSync(base+'/worker.js','utf8'),ctx);
ctx.querySql=(sql,bind)=>JSON.parse(execFileSync('python3',['-c',`import sqlite3,json,sys
c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row
p=json.loads(sys.argv[3]);p={k.lstrip(':'):v for k,v in p.items()} if isinstance(p,dict) else p
print(json.dumps([dict(r) for r in c.execute(sys.argv[2],p)]))`,process.env.CATMAS_TEST_DB||'/private/tmp/catmas-history-status.db',sql,JSON.stringify(bind)],{maxBuffer:32*1024*1024}).toString());
vm.runInContext('db={exec(sql,bind={}){const rows=querySql(sql,bind);return rows.length?[{columns:Object.keys(rows[0]),values:rows.map(r=>Object.values(r))}]:[]}}',ctx);
(async()=>{
 const c=ctx.CatmasContent;
 const lamp=await vm.runInContext('content(955532)',ctx);
 assert.equal(lamp.item.item_id,15);const diffs=lamp.base.items['15'];assert.equal(diffs.length,1);assert(diffs[0][3].includes('CAPSULA'));assert(diffs[0][4].includes('CÁPSULA'));assert.equal(diffs[0][5],'somente_diacriticos');assert.equal(lamp.requests.rows.length,0);
 assert.equal(c.localDay(lamp.base.sources[0].published_after),'2026-10-06');
 assert.throws(()=>c.identityRows(lamp.base,{item_id:15,code:'999'}));
 ctx.item={item_id:292141,material_service_id:null};const requests=vm.runInContext('requestContent(item)',ctx);const r=requests.rows.find(r=>r.request.request_id===26978);assert(r);assert(r.changes.some(x=>x.before.includes('CAPACIDADE 95 ML')&&x.after.includes('CAPACIDADE 115 ML')));assert.equal(r.evidence.length,1);
 const snapshots=[{snapshot_id:1,stage:1,specification:null},{snapshot_id:2,stage:3,specification:'texto'}];assert.equal(c.summarizeRequest({},snapshots,[],[]).changes.length,0);
 assert(c.summarizeRequest({},[...snapshots,{snapshot_id:3,stage:1}],[],[]).blocked);
 const comps=[{snapshot_id:1,category:'x',component_key:'k',value:'a'},{snapshot_id:1,category:'x',component_key:'k',value:'b'}];assert(c.summarizeRequest({},snapshots,comps,[]).blocked);
 ctx.f={from:'2026-10-01',to:'2026-10-21',type:'MATERIAL',search:'248',actor:'não deve filtrar cópias',action:25};const list=await vm.runInContext('contentList(f)',ctx);assert.equal(list.count,1);assert.equal(list.rows[0].item.item_id,15);assert.equal(list.rows[0].changes.length,1);
 ctx.f={from:'2099-01-01',to:'2099-01-02'};assert.equal((await vm.runInContext('contentList(f)',ctx)).count,0);
 console.log(JSON.stringify({result:'ok',lampDifferences:diffs.length,request26978:r.changes,evidence:r.evidence.map(e=>e.request_event_id),filteredPublications:list.count}));
})().catch(e=>{console.error(e);process.exitCode=1;});
