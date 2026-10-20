'use strict';
importScripts('./model.js?v=20261020-1','https://cdn.jsdelivr.net/npm/sql.js-fts5@1.4.0/dist/sql-wasm.js','https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js');
let db,publication={};
const query=(sql,bind={})=>{const r=db.exec(sql,bind)[0];return r?r.values.map(row=>Object.fromEntries(r.columns.map((c,i)=>[c,row[i]]))):[];};
const rowSelect=`e.*, a.label AS action_label, i.code, i.item_type, i.material_service_id, i.material_service_code, i.material_service_name, i.current_specification`;
const join=` FROM events e JOIN items i ON i.item_id=e.item_id LEFT JOIN action_labels a ON a.code=e.action_code `;
const progress=message=>self.postMessage({progress:message});
const escapeLike=s=>s.replace(/[\\%_]/g,'\\$&');
function where(f){const conditions=['e.occurred_at >= :from AND e.occurred_at < :end'];const p={':from':f.from,':end':f.to+'T99'};
if(!f.technical)conditions.push('e.action_code NOT IN (16,17)');
if(f.type){conditions.push('i.item_type=:type');p[':type']=f.type;}
if(f.action){conditions.push('e.action_code=:action');p[':action']=Number(f.action);}
if(f.actor){conditions.push("COALESCE(e.user_name,'')=:actor");p[':actor']=f.actor;}
if(f.search){const v=f.search.trim();if(/^\d+$/.test(v)){conditions.push('(CAST(i.code AS INTEGER)=:code OR CAST(i.material_service_code AS INTEGER)=:code)');p[':code']=Number(v);}else{conditions.push("(i.material_service_name LIKE :search ESCAPE '\\' OR i.current_specification LIKE :search ESCAPE '\\' OR e.details LIKE :search ESCAPE '\\')");p[':search']='%'+escapeLike(v)+'%';}}
return {sql:' WHERE '+conditions.join(' AND '),p};}
async function init(){
 try{const response=await fetch('../atualizacao.json',{cache:'no-store'});if(response.ok)publication=await response.json();}catch(_e){}
 progress('Baixando a base histórica…');
 const response=await fetch('../history.db.gz?v='+encodeURIComponent(publication.history_sha256||Date.now()),{cache:'no-store'});
 if(!response.ok)throw Error('Não foi possível carregar a base histórica ('+response.status+').');
 let compressed=new Uint8Array(await response.arrayBuffer());
 progress('Abrindo o histórico e preparando os filtros…');
 let bytes;
 if('DecompressionStream' in self){bytes=new Uint8Array(await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());}else bytes=pako.ungzip(compressed);
 compressed=null;
 const SQL=await initSqlJs({locateFile:f=>'https://cdn.jsdelivr.net/npm/sql.js-fts5@1.4.0/dist/'+f});db=new SQL.Database(bytes);bytes=null;
 progress('Preparando a consulta por período…');
 db.run('CREATE INDEX IF NOT EXISTS panel_events_date ON events(occurred_at)');
 const dates=query('SELECT MIN(occurred_at) AS first,MAX(occurred_at) AS last,COUNT(*) AS total FROM events')[0];
 const meta=Object.fromEntries(query('SELECT * FROM metadata').map(r=>[r.key,r.value]));
 const actors=query("SELECT DISTINCT user_name FROM events WHERE user_name IS NOT NULL AND user_name<>'' ORDER BY user_name");
 return {dates,meta,publication,actors,actions:query('SELECT * FROM action_labels ORDER BY label')};
}
function list(f){const w=where(f);const summary=query('SELECT COUNT(*) AS events,COUNT(DISTINCT e.item_id) AS items,COUNT(DISTINCT i.item_type||\':\'||COALESCE(CAST(i.material_service_id AS TEXT),\'item-\'||i.item_id)) AS parents'+join+w.sql,w.p)[0];
 const rows=query('SELECT '+rowSelect+join+w.sql+' ORDER BY e.occurred_at DESC,e.history_id DESC LIMIT 30 OFFSET :offset',{...w.p,':offset':f.offset||0});
 const days=query('SELECT substr(e.occurred_at,1,10) AS day,COUNT(*) AS count'+join+w.sql+' GROUP BY 1 ORDER BY 1',w.p);
 return {summary,rows,days};}
function detail(id){const row=query('SELECT '+rowSelect+join+' WHERE e.history_id=:id',{':id':id})[0];if(!row)throw Error('Movimentação não encontrada.');
 const stages=query('SELECT COUNT(*) AS count FROM snapshots WHERE item_id=:item',{':item':row.item_id})[0].count;
 return {row,stages};}
function related(id){const selected=detail(id).row;const when=CatmasModel.relation;const date=selected.occurred_at.slice(0,10);const from=CatmasModel.dateRange(date,8).from;const until=new Date(date+'T12:00:00Z');until.setUTCDate(until.getUTCDate()+8);const to=until.toISOString().slice(0,10);
 const seed=String(selected.material_service_name||'').split(/\s+/).find(x=>x.length>3)||'';
 const p={':from':from,':to':to,':item':selected.item_id,':type':selected.item_type,':parent':selected.material_service_id,':group':(CatmasModel.normalize(selected.material_service_code).match(/^\d{8}$/)||[])[0]?.slice(0,2)||'__',':seed':seed?escapeLike(seed)+'%':'__NO_MATCH__',':date':selected.occurred_at};
 const candidates=query('SELECT '+rowSelect+join+` WHERE e.occurred_at >= :from AND e.occurred_at < :to AND e.action_code NOT IN (16,17) AND e.item_id<>:item AND i.item_type=:type AND (i.material_service_id=:parent OR substr(i.material_service_code,1,2)=:group OR i.material_service_name LIKE :seed ESCAPE '\\') ORDER BY (i.material_service_id=:parent) DESC,ABS(julianday(e.occurred_at)-julianday(:date)),e.history_id DESC LIMIT 3001`,p);
 const limited=candidates.length>3000,byItem=new Map();
 for(const row of candidates.slice(0,3000)){const association=when(selected,row);if(!association)continue;const previous=byItem.get(row.item_id);if(!previous||association.score>previous.association.score)byItem.set(row.item_id,{row,association});}
 return {limited,candidates:Math.min(candidates.length,3000),matches:[...byItem.values()].sort((a,b)=>b.association.score-a.association.score||a.association.gap-b.association.gap).slice(0,8)};
}
self.onmessage=async event=>{const {id,method,args}=event.data;try{let result;if(method==='init')result=await init();else if(method==='list')result=list(args);else if(method==='detail')result=detail(args);else if(method==='related')result=related(args);else throw Error('Consulta inválida.');self.postMessage({id,result});}catch(error){self.postMessage({id,error:error.message||String(error)});}};
