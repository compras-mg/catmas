export const required = `ehmaterialouservico_id materialouservico_classe_codigogrupoformatado materialouservico_classe_codigonomeformatado codigo especificacaocompleta descricaoitem situacao_id materialouservico_naturezadespesa_nome linhasfornecimentoformatadas elementositemdespesaformatados materialouservico_codigoformatado materialouservico_nome ehagriculturafamiliar sustentavel espokregprecos complementacaoespecificacao versao datacriacao dataultimaatualizacao id materialouservico_id`.split(' ');
export const converter = 'f8c392eac1944c690d42c17b9aec60812a78065d';
export const columns = `tipo grupo classe codigo spec situacao natureza linhas_fornecimento elementos_codigos material_codigo material_nome agricultura_familiar sustentavel ok_registro_precos especificacao_longa versao data_criacao data_ultima_atualizacao item_id servico_id`.split(' ');
const integerColumns = new Set(['versao','item_id','servico_id']);

export async function hash(bytes, algorithm='SHA-256') {
  return [...new Uint8Array(await crypto.subtle.digest(algorithm, bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
}
export async function blobSha(bytes) {
  const prefix = new TextEncoder().encode(`blob ${bytes.length}\0`);
  const data = new Uint8Array(prefix.length + bytes.length);
  data.set(prefix); data.set(bytes,prefix.length);
  return hash(data,'SHA-1');
}

export function delimiterFor(text) {
  const scores = new Map([',',';','\t','|'].map(x=>[x,0]));
  let quoted=false;
  for(let i=0;i<Math.min(text.length,65536);i++) {
    const c=text[i];
    if(c==='"') { if(quoted && text[i+1]==='"'){i++;continue;} quoted=!quoted; }
    if(!quoted && (c==='\r'||c==='\n')) break;
    if(!quoted && scores.has(c)) scores.set(c,scores.get(c)+1);
  }
  const sorted=[...scores].sort((a,b)=>b[1]-a[1]);
  if(!sorted[0][1]) throw new Error('Não foi possível identificar o separador do CSV.');
  return sorted[0][0];
}

export function* csvRows(text, delimiter) {
  if(text.charCodeAt(0)===0xfeff) text=text.slice(1);
  let field='', fields=[], quoted=false, closed=false, line=1, start=1;
  for(let i=0;i<text.length;i++) {
    const c=text[i];
    if(quoted) {
      if(c==='"') { if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;closed=true;} }
      else {field+=c;if(c==='\n')line++;}
    } else if(c===delimiter) {fields.push(field);field='';closed=false;}
    else if(c==='\n'||c==='\r') {
      if(c==='\r' && text[i+1]==='\n')i++;
      fields.push(field);
      if(fields.length>1 || fields[0]!=='')yield {values:fields,line:start};
      field='';fields=[];closed=false;line++;start=line;
    } else if(c==='"') {
      if(field || closed)throw new Error(`Linha ${line}: aspas fora de posição.`);
      quoted=true;
    } else {
      if(closed)throw new Error(`Linha ${line}: conteúdo após o fechamento das aspas.`);
      field+=c;
    }
    if(field.length>16*1024*1024)throw new Error(`Linha ${line}: campo acima de 16 MB.`);
  }
  if(quoted)throw new Error('CSV termina com aspas sem fechamento.');
  if(field || fields.length || closed) {fields.push(field);yield {values:fields,line:start};}
}

export function hasLong(value) {
  const text=(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toUpperCase();
  return /\b(?:ESPECIFICAC(?:AO|A|O|OES)|ESPECIFICAO|ESPEIFICACAO|ESEPCIFICACAO)\s+LONGAS?\b/.test(text)
    || /\b(?:ARQUIVO\s+DE\s+)?LONGA\s+ANEXAD[AO]\b/.test(text) ? 'true':'false';
}
export function validDate(value) {
  const m=/^(\d{4})-(\d{2})-(\d{2})(?:$|[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?$)/.exec(value);
  if(!m || !Number.isFinite(Date.parse(value)))return false;
  const [year,month,day]=m.slice(1,4).map(Number);
  if(year<1 || month<1 || month>12 || day<1)return false;
  const clock=/[T ](\d{2}):(\d{2})(?::(\d{2}))?/.exec(value);
  if(clock&&(Number(clock[1])>23||Number(clock[2])>59||Number(clock[3]||0)>59))return false;
  const days=[31,(year%4===0 && (year%100!==0||year%400===0))?29:28,31,30,31,30,31,31,30,31,30,31];
  return day<=days[month-1];
}
const prefix=value=>value.includes(' - ')?value.split(' - ',1)[0].trim():value;
const situation=value=>value.toUpperCase()==='ATIVO'?'Ativo':(['SUSPENSO_PARA_COMPRA','SUSPENSO PARA COMPRA'].includes(value.toUpperCase())?'Suspenso para compra':'Inativo');

export async function prepareDatabase(sqlite3, text, sourceBytes, progress=()=>{}) {
  const delimiter=delimiterFor(text);
  const iterator=csvRows(text,delimiter);
  const first=iterator.next();
  if(first.done)throw new Error('O CSV está vazio.');
  const headers=first.value.values.map(s=>s.trim().toLowerCase());
  if(new Set(headers).size!==headers.length)throw new Error('Há colunas duplicadas no CSV.');
  const missing=required.filter(x=>!headers.includes(x));
  if(missing.length)throw new Error('Colunas obrigatórias ausentes: '+missing.join(', '));
  const report={status:'validando',rows:0,published_items:0,excluded:0,errors:[],errorCount:0,warnings:{},
    source_sha256:await hash(sourceBytes),delimiter,columns:headers,converter_commit:converter};
  const warn=k=>report.warnings[k]=(report.warnings[k]||0)+1;
  const error=(line,message)=>{report.errorCount++;if(report.errors.length<100)report.errors.push(`Linha ${line}: ${message}`);};
  const db=new sqlite3.oo1.DB(':memory:','c');
  let insert,fts;
  const ids=new Set(), codes=new Set(),hierarchy=new Set();
  try {
    db.exec(`CREATE TABLE items (${columns.map(c=>`"${c}" ${integerColumns.has(c)?('INTEGER'+(c==='item_id'?' NOT NULL':'')):'TEXT NOT NULL'}`).join(',')})`);
    db.exec('CREATE TABLE hierarchy (tipo TEXT NOT NULL, grupo TEXT NOT NULL, classe TEXT NOT NULL)');
    db.exec("CREATE VIRTUAL TABLE items_fts USING fts5(codigo,spec,material_nome,grupo_label,classe_label,tokenize='unicode61 remove_diacritics 2')");
    insert=db.prepare('INSERT INTO items VALUES ('+columns.map(()=>'?').join(',')+')');
    fts=db.prepare('INSERT INTO items_fts(codigo,spec,material_nome,grupo_label,classe_label) VALUES(?,?,?,?,?)');
    db.exec('BEGIN');
    for(const {values,line} of iterator) {
      report.rows++;
      if(values.length!==headers.length) {error(line,'número de campos diferente do cabeçalho');continue;}
      const row=Object.fromEntries(headers.map((h,i)=>[h,values[i].trim()]));
      const initialErrors=report.errorCount;
      for(const [key,width] of [['codigo',9],['materialouservico_codigoformatado',8]]) {
        if(row[key] && !new RegExp(`^[0-9]{1,${width}}$`).test(row[key]))error(line,`${key} inválido`);
      }
      for(const key of ['id','materialouservico_id','versao']) {
        if((key==='id'&&!row[key]) || (row[key]&&(!/^[0-9]+$/.test(row[key])||!Number.isSafeInteger(Number(row[key])))))error(line,`${key} inválido`);
      }
      for(const key of ['datacriacao','dataultimaatualizacao']) {
        if(row[key]&&!validDate(row[key]))error(line,`${key} deve ser uma data ISO válida`);
        if(!row[key])warn(key+'_vazia');
      }
      for(const key of ['ehagriculturafamiliar','sustentavel','espokregprecos']) {
        if(row[key]&&!['true','false'].includes(row[key].toLowerCase()))error(line,`${key} deve ser true ou false`);
      }
      for(const key of ['linhasfornecimentoformatadas','elementositemdespesaformatados','descricaoitem'])if(!row[key])warn(key+'_vazio');
      if(!['ATIVO','INATIVO','SUSPENSO_PARA_COMPRA','SUSPENSO PARA COMPRA'].includes(row.situacao_id.toUpperCase()))warn('situacoes_agregadas_como_inativo');
      if(!row.codigo){report.excluded++;continue;}
      for(const key of ['ehmaterialouservico_id','materialouservico_classe_codigogrupoformatado','materialouservico_classe_codigonomeformatado'])if(!row[key])error(line,`${key} vazio`);
      const code=row.codigo.padStart(9,'0'),id=Number(row.id);
      if(codes.has(code))error(line,'código duplicado');
      if(ids.has(id))error(line,'identificador duplicado');
      codes.add(code);ids.add(id);
      if(report.errorCount!==initialErrors)continue;
      const spec=row.especificacaocompleta||row.descricaoitem;
      const grupo=row.materialouservico_classe_codigogrupoformatado;
      const classe=row.materialouservico_classe_codigonomeformatado;
      const item=[row.ehmaterialouservico_id,prefix(grupo),prefix(classe),code,spec,situation(row.situacao_id),
        row.materialouservico_naturezadespesa_nome,row.linhasfornecimentoformatadas,row.elementositemdespesaformatados,
        row.materialouservico_codigoformatado?row.materialouservico_codigoformatado.padStart(8,'0'):'',row.materialouservico_nome,
        row.ehagriculturafamiliar||'false',row.sustentavel||'false',row.espokregprecos.toLowerCase(),hasLong(row.complementacaoespecificacao),
        row.versao?Number(row.versao):null,row.datacriacao,row.dataultimaatualizacao||row.datacriacao,id,
        row.materialouservico_id?Number(row.materialouservico_id):null];
      insert.bind(item).step();insert.reset(true);
      fts.bind([code,spec,row.materialouservico_nome,grupo,classe]).step();fts.reset(true);
      hierarchy.add(JSON.stringify([row.ehmaterialouservico_id,grupo,classe]));
      report.published_items++;
      if(report.rows%2000===0)progress({phase:'validando',rows:report.rows});
    }
    insert.finalize();insert=null;fts.finalize();fts=null;
    if(!report.published_items)error(0,'nenhum item disponível para publicação');
    if(report.errorCount) {report.status='bloqueado';db.exec('ROLLBACK');return {report};}
    for(const tuple of [...hierarchy].sort())db.exec({sql:'INSERT INTO hierarchy VALUES(?,?,?)',bind:JSON.parse(tuple)});
    db.exec('COMMIT');
    progress({phase:'indexando',rows:report.rows});
    for(const [name,cols] of [['tipo','tipo'],['grupo','grupo'],['classe','classe'],['codigo','codigo'],
      ['especificacao_longa','especificacao_longa'],['composite','tipo,grupo,classe']])db.exec(`CREATE INDEX idx_${name} ON items(${cols})`);
    db.exec('VACUUM');
    if(db.selectValue('PRAGMA integrity_check')!=='ok')throw new Error('O banco não passou na verificação de integridade.');
    db.exec("INSERT INTO items_fts(items_fts) VALUES('integrity-check')");
    if(db.selectValue('SELECT COUNT(*) FROM items')!==report.published_items || db.selectValue('SELECT COUNT(*) FROM items_fts')!==report.published_items)throw new Error('Contagens do banco e índice inconsistentes.');
    const bytes=sqlite3.capi.sqlite3_js_db_export(db.pointer);
    progress({phase:'compactando',rows:report.rows});
    const raw=bytes.slice();
    const compressed=new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
    const decompressed=new Uint8Array(await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
    if(await hash(raw)!==await hash(decompressed))throw new Error('O arquivo compactado não corresponde ao banco gerado.');
    if(compressed.length>=100*1024*1024)throw new Error('A base compactada excede o limite de envio ao GitHub (100 MB).');
    report.status='preparado';report.data_sha256=await hash(compressed);report.database_sha256=await hash(raw);
    report.gzip_bytes=compressed.length;report.hierarchy_rows=hierarchy.size;
    return {report,compressed};
  } finally {insert?.finalize();fts?.finalize();db.close();}
}
