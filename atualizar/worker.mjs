import {prepareDatabase,hash} from './engine.mjs';
async function loadSqlite() {
  const base=new URL('./vendor/',import.meta.url);
  const response=await fetch(new URL('manifest.json',base));
  if(!response.ok)throw new Error('Não foi possível carregar os componentes de processamento.');
  const manifest=await response.json();
  async function unpack(name) {
    const asset=manifest[name],chunks=[];
    for(const part of asset.parts) {
      if(!/^[a-z0-9.-]+$/.test(part))throw new Error('Nome de componente inválido.');
      const result=await fetch(new URL(part,base));
      if(!result.ok)throw new Error('Um componente de processamento ainda não está disponível. Recarregue a página.');
      chunks.push(await result.arrayBuffer());
    }
    const bytes=new Uint8Array(await new Response(new Blob(chunks).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
    if(bytes.length!==asset.rawBytes||await hash(bytes)!==asset.sha256)throw new Error('Um componente de processamento não passou na verificação de integridade.');
    return bytes;
  }
  const [code,wasm]=await Promise.all([unpack('index.mjs'),unpack('sqlite3.wasm')]);
  const moduleUrl=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));
  try {
    const {default:sqlite3InitModule}=await import(moduleUrl);
    return await sqlite3InitModule({wasmBinary:wasm,locateFile:name=>new URL(name,base).href,print:()=>{},printErr:()=>{}});
  } finally {URL.revokeObjectURL(moduleUrl);}
}
self.onmessage=async ({data})=>{
  try {
    const bytes=new Uint8Array(data.buffer);
    let text;
    try {text=new TextDecoder(data.encoding,{fatal:true}).decode(bytes);}
    catch {throw new Error('O CSV não usa UTF-8 válido. Se ele foi exportado nessa codificação, selecione Windows / CP1252 e valide novamente.');}
    const sqlite3=await loadSqlite();
    const result=await prepareDatabase(sqlite3,text,bytes,progress=>self.postMessage({type:'progress',...progress}));
    self.postMessage({type:'result',...result},result.compressed?[result.compressed.buffer]:[]);
  } catch(error) {self.postMessage({type:'error',message:error.message||'Não foi possível processar o CSV.'});}
};
