import {hash,blobSha,converter} from './engine.mjs';
export const repository='compras-mg/catmas';
const root='https://api.github.com/repos/'+repository;
export function encode64(bytes) {
  let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
  return btoa(binary);
}
export function decode64(content) {
  return new Uint8Array([...atob(content.replace(/\s/g,''))].map(c=>c.charCodeAt(0)));
}
export function githubClient(token, request=fetch) {
  return async (method,path,payload)=>{
    let response;
    try {response=await request(root+path,{method,headers:{'Authorization':'Bearer '+token,
      'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28',
      ...(payload?{'Content-Type':'application/json'}:{})},body:payload?JSON.stringify(payload):undefined,
      cache:'no-store',redirect:'error',signal:AbortSignal.timeout(90000)});}
    catch {throw new Error('A conexão com o GitHub foi interrompida. Se o envio já começou, verifique o resultado antes de tentar novamente.');}
    if(!response.ok) {
      const messages={401:'A autenticação não foi aceita. Reconecte o GitHub.',403:'O GitHub recusou o acesso. Confira as permissões do token para este repositório.',
        404:'O recurso não foi encontrado. Confira o acesso e a configuração do GitHub Pages.',409:'A branch mudou durante a atualização.',
        422:'O GitHub recusou a alteração. A branch pode ter recebido outra atualização.'};
      throw new Error(messages[response.status]||`O GitHub retornou um erro (${response.status}).`);
    }
    return response.status===204?{}:response.json();
  };
}
export async function preflight(api) {
  const pages=await api('GET','/pages');
  if(pages.build_type && pages.build_type!=='legacy' || pages.source?.branch!=='gh-pages' || pages.source?.path!=='/')
    throw new Error('A publicação do repositório precisa usar a raiz de gh-pages, no modo “Deploy from a branch”. Nenhuma configuração foi alterada.');
  if(!pages.html_url?.startsWith('https://'))throw new Error('O GitHub não informou uma URL segura para o buscador.');
  const head=(await api('GET','/git/ref/heads/gh-pages')).object.sha;
  const commit=await api('GET','/git/commits/'+head);
  const tree=await api('GET','/git/trees/'+commit.tree.sha);
  if(tree.truncated)throw new Error('Não foi possível conferir todos os arquivos publicados.');
  const files=Object.fromEntries(tree.tree.map(file=>[file.path,file]));
  if(!files['index.html'])throw new Error('O buscador não foi encontrado na branch publicada.');
  const blob=await api('GET','/git/blobs/'+files['index.html'].sha);
  if(blob.encoding!=='base64')throw new Error('Não foi possível conferir o formato do buscador.');
  const html=new TextDecoder().decode(decode64(blob.content));
  if(!['data_criacao','especificacao_longa','data.db.gz'].every(s=>html.includes(s)))
    throw new Error('A página publicada não contém os campos esperados de data de criação e especificação longa.');
  return {pages,head,tree:commit.tree.sha,files};
}
export async function publish(api,compressed,report,change=()=>{}) {
  if(report.status!=='preparado'||report.errorCount || await hash(compressed)!==report.data_sha256)
    throw new Error('A base precisa ser validada novamente antes da publicação.');
  const current=await preflight(api);
  const state={status:'preparando',repository,branch:'gh-pages',previous_commit:current.head,
    source_sha256:report.source_sha256,data_sha256:report.data_sha256,page_url:current.pages.html_url};
  change({...state});
  const expected=await blobSha(compressed);
  if(current.files['data.db.gz']?.sha===expected){state.commit=current.head;state.status='enviado';change({...state});return state;}
  const blob=await api('POST','/git/blobs',{encoding:'base64',content:encode64(compressed)});
  if(blob.sha!==expected)throw new Error('O arquivo recebido pelo GitHub difere da base validada.');
  const metadata=JSON.stringify({source_sha256:report.source_sha256,data_sha256:report.data_sha256,
    items:report.published_items,converter_commit:converter,updated_at:new Date().toISOString()},null,2);
  const tree=await api('POST','/git/trees',{base_tree:current.tree,tree:[
    {path:'data.db.gz',mode:'100644',type:'blob',sha:expected},
    {path:'atualizacao.json',mode:'100644',type:'blob',content:metadata}]});
  const commit=await api('POST','/git/commits',{message:`Atualiza base CATMAS (${report.published_items} itens; CSV ${report.source_sha256.slice(0,12)})`,
    tree:tree.sha,parents:[current.head]});
  state.commit=commit.sha;state.status='commit_preparado';change({...state});
  if((await api('GET','/git/ref/heads/gh-pages')).object.sha!==current.head)throw new Error('Outra atualização avançou gh-pages. Nenhuma atualização desta execução foi publicada.');
  state.status='envio_em_andamento';change({...state});
  await api('PATCH','/git/refs/heads/gh-pages',{sha:commit.sha,force:false});
  state.status='enviado';change({...state});
  return state;
}
export async function liveHash(url) {
  const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(60000)});
  if(!response.ok)throw new Error('O arquivo do buscador ainda não está disponível.');
  const bytes=new Uint8Array(await response.arrayBuffer());
  if(bytes.length>100*1024*1024)throw new Error('O arquivo servido excede o limite de verificação.');
  return hash(bytes);
}
export async function verify(api,state,{timeout=600000,interval=10000,readHash=liveHash,change=()=>{},
  sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),now=()=>Date.now()}={}) {
  const until=now()+timeout;
  state={...state,status:'aguardando_pages'};change({...state});
  do {
    const head=(await api('GET','/git/ref/heads/gh-pages')).object.sha;
    if(head!==state.commit){state.status='substituida';change({...state});throw new Error('Outra atualização substituiu esta versão. Confira o estado atual do buscador.');}
    const build=await api('GET','/pages/builds/latest');
    if(build.commit===state.commit && build.status==='errored'){state.status='falha_pages';change({...state});throw new Error('O arquivo foi enviado, mas o GitHub Pages falhou ao publicar. O commit está no relatório.');}
    if(build.commit===state.commit && build.status==='built') {
      let currentHash;
      try {currentHash=await readHash(state.page_url.replace(/\/$/,'')+'/data.db.gz?catmas='+state.commit);} catch{}
      if(currentHash===state.data_sha256) {
        if((await api('GET','/git/ref/heads/gh-pages')).object.sha!==state.commit)throw new Error('Outra atualização avançou durante a conferência.');
        state.status='publicado';state.verified_at=new Date().toISOString();change({...state});return state;
      }
    }
    if(now()>=until)break;
    await sleep(interval);
  } while(now()<=until);
  state.status='verificacao_pendente';change({...state});return state;
}
export async function currentPublication(api) {
  const info=await preflight(api);
  if(!info.files['atualizacao.json'])return null;
  const blob=await api('GET','/git/blobs/'+info.files['atualizacao.json'].sha);
  const data=JSON.parse(new TextDecoder().decode(decode64(blob.content)));
  if(!/^[a-f0-9]{64}$/.test(data.data_sha256))return null;
  return {status:'verificacao_pendente',repository,branch:'gh-pages',commit:info.head,
    data_sha256:data.data_sha256,source_sha256:data.source_sha256,page_url:info.pages.html_url};
}
