'use strict';
importScripts('./content.js?v=20261021-1','./model.js?v=20261021-2','https://cdn.jsdelivr.net/npm/sql.js-fts5@1.4.0/dist/sql-wasm.js','https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js');
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

const baseBuckets=new Map();
async function baseBucket(bucket){
 if(!baseBuckets.has(bucket))baseBuckets.set(bucket,fetch('../base-diffs-v1/'+bucket+'.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Comparação entre bases indisponível ('+r.status+').');return r.json();}).then(CatmasContent.validateBucket).catch(e=>{baseBuckets.delete(bucket);throw e;}));
 return baseBuckets.get(bucket);
}
function requestContent(item){
 const requests=query(`SELECT DISTINCT r.*,rt.label AS type_label,rs.label AS status_label FROM requests r JOIN snapshots s ON s.request_id=r.request_id LEFT JOIN request_types rt ON rt.code=r.request_type LEFT JOIN request_statuses rs ON rs.code=r.status WHERE s.item_id=:item OR (s.item_id IS NULL AND :parent IS NOT NULL AND s.material_service_id=:parent) ORDER BY r.included_at DESC,r.request_id DESC LIMIT 101`,{':item':item.item_id,':parent':item.material_service_id});
 return {limited:requests.length>100,rows:requests.slice(0,100).map(r=>{
 const snapshots=query('SELECT * FROM snapshots WHERE request_id=:id ORDER BY stage,snapshot_id',{':id':r.request_id});
 const components=query('SELECT c.* FROM snapshot_components c JOIN snapshots s ON s.snapshot_id=c.snapshot_id WHERE s.request_id=:id ORDER BY c.category,c.sort_order,c.component_row_id',{':id':r.request_id});
 const events=query('SELECT * FROM request_events WHERE request_id=:id ORDER BY occurred_at,request_event_id',{':id':r.request_id});
 const scope=snapshots.some(s=>Number(s.item_id)===Number(item.item_id))?'Item':'Material/serviço pai';
 return {...CatmasContent.summarizeRequest(r,snapshots,components,events),scope};
 })};
}
async function content(id){
 const item=detail(id).row;
 const requests=requestContent(item);
 let base=null,baseError=null;
 try{const bucket=await baseBucket(Number(item.item_id)%8);const rows=CatmasContent.identityRows(bucket,item);base={schema:1,sources:bucket.sources,items:{[item.item_id]:rows}};}catch(e){baseError=e.message;}
 return {item,requests,base,baseError};
}
async function contentList(f){
 const buckets=await Promise.all(Array.from({length:8},(_,i)=>baseBucket(i)));
 const ids=[...new Set(buckets.flatMap(b=>Object.keys(b.items).map(Number)))];
 const itemMap=new Map();
 for(let i=0;i<ids.length;i+=400){const group=ids.slice(i,i+400);for(const row of query('SELECT item_id,code,item_type,material_service_id,material_service_code,material_service_name,current_specification FROM items WHERE item_id IN ('+group.map(()=>'?').join(',')+')',group))itemMap.set(Number(row.item_id),row);}
 const results=[];let unmatched=0;const search=CatmasModel.normalize(f.search||'');
 for(const bucket of buckets)for(const [id,all]of Object.entries(bucket.items)){
 const item=itemMap.get(Number(id));if(!item){unmatched++;continue;}
 let rows;try{rows=CatmasContent.identityRows(bucket,item);}catch(_e){unmatched++;continue;}
 if(f.type&&item.item_type!==f.type)continue;
 const groups=new Map();for(const row of rows){const source=bucket.sources[row[6]],day=CatmasContent.localDay(source.published_after);if(day<f.from||day>f.to)continue;if(!groups.has(row[6]))groups.set(row[6],[]);groups.get(row[6]).push(row);}
 for(const [index,changes]of groups){
 if(search){const numeric=/^\d+$/.test(search);if(numeric){if(Number(search)!==Number(item.code)&&Number(search)!==Number(item.material_service_code))continue;}else{const text=CatmasModel.normalize([item.material_service_name,item.current_specification,...changes.flatMap(c=>[c[2],c[3],c[4]])].join(' '));if(!text.includes(search))continue;}}
 results.push({item,changes,source:bucket.sources[index],summary:CatmasContent.baseSummary(changes)});
 }
 }
 results.sort((a,b)=>b.source.published_after.localeCompare(a.source.published_after)||String(a.item.code).localeCompare(String(b.item.code))||Number(a.item.item_id)-Number(b.item.item_id));
 return {count:results.length,fields:results.reduce((n,r)=>n+r.changes.length,0),unmatched,rows:results.slice(f.contentOffset||0,(f.contentOffset||0)+20),sources:buckets[0].sources};
}
self.onmessage=async event=>{const {id,method,args}=event.data;try{let result;if(method==='init')result=await init();else if(method==='list')result=list(args);else if(method==='detail')result=detail(args);else if(method==='related')result=related(args);else if(method==='content')result=await content(args);else if(method==='contentList')result=await contentList(args);else throw Error('Consulta inválida.');self.postMessage({id,result});}catch(error){self.postMessage({id,error:error.message||String(error)});}};
