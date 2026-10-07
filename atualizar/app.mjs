import {githubClient,publish,verify,currentPublication,repository} from './github.mjs';
const $=id=>document.getElementById(id);
const show=(id,visible=true)=>$(id).hidden=!visible;
const number=value=>new Intl.NumberFormat('pt-BR').format(value);
let file=null,result=null,worker=null,api=null,busy=false,publication=null;
const warningLabels={datacriacao_vazia:'Registros sem data de criação',dataultimaatualizacao_vazia:'Registros sem data da última atualização',
  linhasfornecimentoformatadas_vazio:'Registros sem linha de fornecimento',elementositemdespesaformatados_vazio:'Registros sem elemento de despesa',
  descricaoitem_vazio:'Registros sem descrição',situacoes_agregadas_como_inativo:'Situações apresentadas como Inativo'};
const statuses={preparando:['Conferindo o destino','Verificando o buscador e preparando o envio.'],
  commit_preparado:['Preparando a atualização','O arquivo já foi recebido pelo GitHub. A versão ainda não foi aplicada.'],
  envio_em_andamento:['Aplicando a nova base','Atualizando a versão usada pelo buscador.'],
  enviado:['Base enviada','Aguardando o GitHub Pages publicar a atualização.'],
  aguardando_pages:['Aguardando a publicação','A confirmação inclui conferir o arquivo disponível no buscador. Isso pode levar alguns minutos.'],
  publicado:['Atualização publicada','O GitHub Pages publicou a versão correta e o arquivo do buscador confere com a base enviada.'],
  verificacao_pendente:['Envio realizado; confirmação pendente','A publicação ainda não foi confirmada. Clique em Verificar publicação para conferir novamente, sem repetir o envio.'],
  falha_pages:['Falha na publicação','A base foi enviada, mas o GitHub Pages informou uma falha. Baixe o registro para consultar o commit.'],
  substituida:['Outra atualização foi publicada','A branch recebeu uma atualização mais recente. Confira o buscador antes de enviar outra base.']};

function controls() {
  $('file').disabled=busy; $('encoding').disabled=busy;
  $('validate').disabled=busy||!file;
  $('publish').disabled=busy||!api||result?.report.status!=='preparado'||publication?.status==='publicado'||publication?.status==='envio_em_andamento'||publication?.status==='enviado'||publication?.status==='aguardando_pages'||publication?.status==='verificacao_pendente';
  $('disconnect').disabled=busy;$('connect-open').disabled=busy;$('connect-submit').disabled=busy;
  $('retry-verify').disabled=busy||!api||!publication?.commit;
  show('retry-verify',!!publication?.commit&&publication.status!=='publicado');
  show('download-publication',!!publication);
  $('publish-hint').textContent=busy?'Mantenha esta aba aberta.':result?.report.status!=='preparado'?'Selecione e valide um CSV para continuar.':!api?'Conecte o GitHub para publicar a base validada.':publication?.status==='publicado'?'Atualização concluída.':'A base está pronta para atualização.';
}
function step(current) {
  ['file','validation','publication'].forEach((name,i)=>{
    $('step-'+name).className=i<current?'done':i===current?'current':'';
  });
}
function download(object,name) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(object,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function updatePublication(state) {
  publication=state;show('publication-state');
  const [title,message]=statuses[state.status]||['Publicação não confirmada','Confira o registro antes de tentar novamente.'];
  $('publication-title').textContent=title;$('publication-message').textContent=message;
  $('publication-state').className='publication-state'+(state.status==='publicado'?' success':['falha_pages','substituida'].includes(state.status)?' failure':'');
  show('publication-spinner',['preparando','commit_preparado','envio_em_andamento','enviado','aguardando_pages'].includes(state.status)&&busy);
  if(state.commit){$('publication-link').href=`https://github.com/${repository}/commit/${state.commit}`;show('publication-link');}
  if(state.status==='publicado')step(3);
  controls();
}
function chooseFile(selected) {
  if(busy||!selected)return;
  if(!/\.csv$/i.test(selected.name)) {show('validation-error');$('validation-error').textContent='Selecione um arquivo com extensão .csv.';return;}
  if(selected.size>300*1024*1024){show('validation-error');$('validation-error').textContent='O arquivo excede 300 MB. Use uma extração menor para processar nesta aba.';return;}
  file=selected;result=null;publication=null;
  $('file-label').textContent=file.name;$('file-caption').textContent=(file.size/1024/1024).toLocaleString('pt-BR',{maximumFractionDigits:1})+' MB · clique para trocar';
  show('validation-error',false);show('result',false);show('processing',false);show('empty-result');show('publication-state',false);
  $('result-tag').textContent='Pronto para validar';$('result-tag').className='tag neutral';step(1);controls();
}
function renderResult(data) {
  result=data;
  const report=data.report,ready=report.status==='preparado';
  show('processing',false);show('result');show('empty-result',false);
  $('result-tag').textContent=ready?'Base validada':'Publicação bloqueada';$('result-tag').className='tag '+(ready?'success':'blocked');
  $('metric-items').textContent=number(report.published_items);$('metric-rows').textContent=number(report.rows);$('metric-excluded').textContent=number(report.excluded);
  $('validation-notice').className='notice'+(ready?'':' blocked');
  $('validation-notice').textContent=ready?'Banco e índice de busca conferidos. Data de criação e especificação longa preservadas.':`${number(report.errorCount)} problema(s) impedem a publicação. Confira o relatório e corrija a extração.`;
  $('issues').replaceChildren();
  const messages=ready?Object.entries(report.warnings).map(([key,value])=>`${warningLabels[key]||key}: ${number(value)}`):report.errors;
  for(const message of messages){const li=document.createElement('li');li.textContent=message;$('issues').append(li);}
  if(!messages.length){const li=document.createElement('li');li.textContent='Nenhum alerta de conteúdo encontrado.';$('issues').append(li);}
  if(ready)step(2);controls();
}
async function validateSelected() {
  if(!file||busy)throw new Error('Selecione um CSV antes de validar.');
  if(!window.Worker||!window.CompressionStream||!window.DecompressionStream||!crypto.subtle)throw new Error('Seu navegador não oferece os recursos necessários. Use uma versão atual de Chrome, Edge ou Firefox.');
  busy=true;result=null;publication=null;show('publication-state',false);controls();
  show('empty-result',false);show('result',false);show('validation-error',false);show('processing');show('validate',false);show('cancel-validation');
  $('processing-label').textContent='Lendo o CSV…';$('result-tag').textContent='Validando';$('result-tag').className='tag neutral';step(1);
  try {
    const buffer=await file.arrayBuffer();
    return await new Promise((resolve,reject)=>{
      worker=new Worker(new URL('./worker.mjs',import.meta.url),{type:'module'});
      worker.onerror=()=>{reject(new Error('O processamento foi interrompido. Recarregue a página ou tente uma extração menor.'));};
      worker.onmessage=({data})=>{
        if(data.type==='progress'){$('processing-label').textContent=({validando:'Validando registros',indexando:'Conferindo o índice de busca',compactando:'Compactando a base'}[data.phase]||'Processando')+` · ${number(data.rows)} registros`;}
        else if(data.type==='error')reject(new Error(data.message));
        else if(data.type==='result'){renderResult(data);resolve({status:data.report.status,rows:data.report.rows,items:data.report.published_items,errors:data.report.errorCount});}
      };
      worker.postMessage({buffer,encoding:$('encoding').value},[buffer]);
      worker.cancel=()=>reject(new Error('Validação cancelada. Nenhum arquivo foi enviado.'));
    });
  } catch(error) {
    show('processing',false);show('validation-error');$('validation-error').textContent=error.message;
    $('result-tag').textContent='Validação interrompida';$('result-tag').className='tag blocked';throw error;
  } finally {worker?.terminate();worker=null;busy=false;show('validate');show('cancel-validation',false);controls();}
}

async function verifyCurrent() {
  if(busy||!api||!publication?.commit)return;
  busy=true;controls();
  try {await verify(api,publication,{change:updatePublication});}
  catch(error){show('publication-state');$('publication-spinner').hidden=true;$('publication-message').textContent=error.message;$('publication-state').className='publication-state failure';}
  finally{busy=false;show('publication-spinner',false);controls();}
}
$('file').addEventListener('change',event=>chooseFile(event.target.files[0]));
$('drop-zone').addEventListener('dragover',event=>{event.preventDefault();if(!busy)$('drop-zone').classList.add('dragging');});
$('drop-zone').addEventListener('dragleave',()=>$('drop-zone').classList.remove('dragging'));
$('drop-zone').addEventListener('drop',event=>{event.preventDefault();$('drop-zone').classList.remove('dragging');chooseFile(event.dataTransfer.files[0]);});
$('encoding').addEventListener('change',()=>{if(file)chooseFile(file);});
$('validate').addEventListener('click',()=>validateSelected().catch(()=>{}));
$('cancel-validation').addEventListener('click',()=>worker?.cancel());
$('download-report').addEventListener('click',()=>result&&download(result.report,'catmas-validacao.json'));
$('download-publication').addEventListener('click',()=>publication&&download(publication,'catmas-publicacao.json'));
$('connect-open').addEventListener('click',()=>{show('auth-panel');$('token').focus();});
$('disconnect').addEventListener('click',()=>{api=null;$('token').value='';$('connection-status').textContent='GitHub desconectado';show('disconnect',false);show('connect-open');controls();});
$('auth-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;
  const access=$('token').value.trim();if(!access)return;
  busy=true;controls();$('auth-message').textContent='Conferindo acesso ao repositório…';$('auth-message').className='';
  try {
    const candidate=githubClient(access);const repo=await candidate('GET','');
    if(repo.full_name!==repository)throw new Error('O acesso retornou um repositório diferente.');
    if(repo.permissions && !repo.permissions.push)throw new Error('Seu acesso não permite atualizar este repositório.');
    api=candidate;$('token').value='';$('connection-status').textContent='GitHub conectado';show('connect-open',false);show('disconnect');show('auth-panel',false);$('auth-message').textContent='';
    if(!result&&!publication){try {const state=await currentPublication(api);if(state)updatePublication(state);}catch{/* A verificação completa acontecerá antes de publicar. */}}
  }catch(error){$('auth-message').textContent=error.message;$('auth-message').className='error';}
  finally{busy=false;controls();}
});
$('publish').addEventListener('click',async()=>{
  if(busy||!api||result?.report.status!=='preparado')return;
  busy=true;controls();step(2);
  try {
    const state=await publish(api,result.compressed,result.report,updatePublication);
    await verify(api,state,{change:updatePublication});
  }catch(error){show('publication-state');show('publication-spinner',false);$('publication-title').textContent=publication?.commit?'Publicação não confirmada':'Atualização interrompida';$('publication-message').textContent=error.message;$('publication-state').className='publication-state failure';}
  finally{busy=false;show('publication-spinner',false);controls();}
});
$('retry-verify').addEventListener('click',verifyCurrent);
window.addEventListener('beforeunload',event=>{if(busy){event.preventDefault();event.returnValue='';}});

if(document.modelContext?.registerTool) {
  const controller=new AbortController();
  for(const tool of [
    {name:'ler_estado_atualizacao_catmas',title:'Ler estado CATMAS',description:'Lê o estado visível da validação e publicação sem expor credenciais ou conteúdo do CSV.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true},execute(input){if(!input||Object.keys(input).length)throw new Error('Não há parâmetros nesta consulta.');return {fileSelected:!!file,connected:!!api,busy,validation:result?.report.status||null,publication:publication?.status||null};}},
    {name:'validar_csv_catmas_selecionado',title:'Validar CSV selecionado',description:'Valida o arquivo já selecionado nesta página e prepara o banco. Não publica no GitHub.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:false},execute(input){if(!input||Object.keys(input).length)throw new Error('Selecione o arquivo na página; esta ação não recebe parâmetros.');return validateSelected();}}
  ])Promise.resolve(document.modelContext.registerTool(tool,{signal:controller.signal})).catch(()=>{});
  window.addEventListener('pagehide',()=>controller.abort(),{once:true});
}
controls();
