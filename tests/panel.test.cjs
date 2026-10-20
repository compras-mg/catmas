const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),path=require('node:path');
const base=path.resolve(__dirname,'../site/painel');
const context={self:{postMessage(){}},globalThis:{},importScripts(){}};vm.createContext(context);
vm.runInContext(fs.readFileSync(base+'/model.js','utf8'),context);context.CatmasModel=context.self.CatmasModel;
const model=context.CatmasModel;
const event={item_id:1,item_type:'MATERIAL',material_service_id:22,material_service_code:'65150012',material_service_name:'LAMINA PARA MICROSCOPIO',current_specification:'VIDRO INCOLOR',occurred_at:'2026-10-19T12:00:00',action_code:25,user_masp:'x'};
assert.equal(model.relation(event,event),null);
assert.equal(model.relation(event,{...event,item_id:2,occurred_at:'2026-10-01T12:00:00'}),null);
assert.equal(model.relation(event,{...event,item_id:2,item_type:'SERVICO'}),null);
assert.equal(model.relation(event,{...event,item_id:2}).score,100);
assert.equal(model.relation(event,{...event,item_id:2,material_service_id:80,material_service_code:'11110022',material_service_name:'TRATOR AGRICOLA',current_specification:'MOTOR DIESEL'}),null);
assert.equal(model.similarity('Lâmina de vidro','LAMINA VIDRO'),1);
assert.equal(model.dateRange('2026-03-02',7).from,'2026-02-24');
vm.runInContext(fs.readFileSync(base+'/worker.js','utf8'),context);
context.querySql=(sql,bind)=>JSON.parse(execFileSync('python3',['-c',`import sqlite3,json,sys
c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row
p=json.loads(sys.argv[3]);p={k.lstrip(':'):v for k,v in p.items()}
print(json.dumps([dict(r) for r in c.execute(sys.argv[2],p)]))`,process.env.CATMAS_TEST_DB||'/private/tmp/catmas-history-status.db',sql,JSON.stringify(bind)],{maxBuffer:16*1024*1024}).toString());
vm.runInContext('db={exec(sql,bind){const rows=querySql(sql,bind);return rows.length?[{columns:Object.keys(rows[0]),values:rows.map(r=>Object.values(r))}]:[]}}',context);
const f={from:'2026-10-14',to:'2026-10-20',technical:false,offset:0};
context.f=f;
const a=vm.runInContext('list(f)',context);
assert(a.summary.events>0);assert(a.rows.length<=30);assert(a.rows.every(r=>![16,17].includes(r.action_code)));
assert.equal(a.days.reduce((n,d)=>n+d.count,0),a.summary.events);
context.f={...f,technical:true};const all=vm.runInContext('list(f)',context);assert(all.summary.events>=a.summary.events);
context.f={...f,from:'2099-01-01',to:'2099-01-02'};assert.equal(vm.runInContext('list(f)',context).summary.events,0);
context.f={...f,search:"' OR 1=1 --"};assert.equal(vm.runInContext('list(f)',context).summary.events,0);
context.id=a.rows[0].history_id;
const d=vm.runInContext('detail(id)',context);assert.equal(d.row.history_id,context.id);
const related=vm.runInContext('related(id)',context);assert(related.matches.length<=8);for(const m of related.matches){assert.notEqual(m.row.item_id,d.row.item_id);assert(m.association.score>=40&&m.association.score<=100);assert(m.association.gap<=7);}
console.log(JSON.stringify({result:'ok',events:a.summary.events,items:a.summary.items,withTechnical:all.summary.events,example:context.id,related:related.matches.length,candidates:related.candidates}));
