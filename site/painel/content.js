/* Comparison of stored content, separate from item events. */
(function(root){
 'use strict';
 const labels={spec:'Especificação',material_nome:'Nome do material/serviço pai',situacao:'Situação',ok_registro_precos:'Registro de preços',material_codigo:'Código do material/serviço pai',especificacao_longa:'Indicador de especificação longa'};
 const kinds={somente_diacriticos:'Somente acentuação/diacríticos',representacao_unicode:'Representação Unicode',outra_diferenca:'Diferença de conteúdo'};
 const itemStatus=v=>v==null?null:({1:'Ativo',4:'Suspenso para compra'}[Number(v)]||'Situação não identificada (código '+v+')');
 const componentStatus=v=>v==null?null:({1:'Ativo',2:'Inativo'}[Number(v)]||'Situação '+v);
 const snapshotValue=(s,f)=>!s?null:f==='item_status'?itemStatus(s[f]):s[f]||null;
 function summarizeRequest(request,snapshots,components,events){
  const result={request,snapshots,changes:[],evidence:[],blocked:null};
  const stages=new Map();
  for(const s of snapshots){if(stages.has(Number(s.stage))){result.blocked='Há estados duplicados na mesma etapa. A comparação foi suspensa.';return result;}stages.set(Number(s.stage),s);}
  const componentsByKey=new Map(),stageById=new Map(snapshots.map(s=>[Number(s.snapshot_id),Number(s.stage)]));
  for(const c of components){const key=JSON.stringify([c.category,c.component_key]);if(!componentsByKey.has(key))componentsByKey.set(key,new Map());const group=componentsByKey.get(key),stage=stageById.get(Number(c.snapshot_id));if(group.has(stage)){result.blocked='Há componentes duplicados na mesma etapa. A comparação foi suspensa.';return result;}group.set(stage,c);}
  const before=stages.get(1),after=stages.get(3);
  if(before&&after){
   for(const [field,label] of [['specification','Especificação'],['specification_complement','Complementação'],['item_status','Situação do item']]){const a=snapshotValue(before,field),b=snapshotValue(after,field);if(a!=null&&b!=null&&a!==b)result.changes.push({label,before:a,after:b,source:'Estados '+before.snapshot_id+' → '+after.snapshot_id});}
   for(const group of componentsByKey.values()){const a=group.get(1),b=group.get(3);if(!a||!b)continue;for(const [field,suffix]of [['value',''],['situation',' — situação'],['sort_order',' — ordem']])if(a[field]!=null&&b[field]!=null&&a[field]!==b[field])result.changes.push({label:b.category+' · '+(b.label||a.label||b.component_key)+suffix,before:field==='situation'?componentStatus(a[field]):a[field],after:field==='situation'?componentStatus(b[field]):b[field],source:b.component_key+' · registros '+a.source_id+' → '+b.source_id});}
  }
  result.hasBefore=!!before;result.hasAfter=!!after;
  result.evidence=events.filter(e=>/^Aprovada\s+Status da última comunicação:\s*Sucesso(?:\s|$)/i.test(String(e.details||'').replace(/\s+/g,' ').trim()));
  return result;
 }
 function validateBucket(data){if(data?.schema!==1||!Array.isArray(data.sources)||!data.items||typeof data.items!=='object')throw Error('Formato da comparação entre bases não reconhecido.');for(const source of data.sources)if(!/^[a-f0-9]{40}$/.test(source.before)||!/^[a-f0-9]{40}$/.test(source.after)||!Number.isFinite(Date.parse(source.published_before))||!Number.isFinite(Date.parse(source.published_after)))throw Error('Fonte de comparação inválida.');for(const [id,rows]of Object.entries(data.items)){if(!/^\d+$/.test(id)||!Number.isSafeInteger(Number(id))||!Array.isArray(rows))throw Error('Identidade de comparação inválida.');for(const row of rows)if(!Array.isArray(row)||row.length!==7||!data.sources[row[6]]||typeof row[0]!=='string'||!/^\d+$/.test(String(row[1])))throw Error('Registro de comparação inválido.');}return data;}
 function identityRows(data,item){const rows=data.items[String(item.item_id)]||[];if(rows.some(r=>String(r[1]).replace(/^0+/,'')!==String(item.code).replace(/^0+/,'')))throw Error('O código da comparação não coincide com o item atual.');return rows;}
 function localDay(iso){return new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Sao_Paulo'}).format(new Date(iso));}
 function baseSummary(rows){return [...new Set(rows.map(r=>(labels[r[2]]||r[2])+' — '+(kinds[r[5]]||'Diferença observada')))].join('; ');}
 root.CatmasContent={labels,kinds,summarizeRequest,validateBucket,identityRows,localDay,baseSummary};
})(typeof self!=='undefined'?self:globalThis);
