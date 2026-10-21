"""Minimal, guarded compatibility patches. No claims of activation in UI text."""


def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Consumidor mudou; revisar integracao antes de publicar.')
    return text.replace(old, new)


def patch(files):
    files = dict(files)
    js = files['base-comparison-v1.js']
    if 'CATMAS_DIFF_HASH_V1' not in js:
        js = once(js, 'async render(container, item, scope)', 'async render(container, item, scope, publication)')
        old = '''      if(!cache.has(bucket)) cache.set(bucket,fetch("base-diffs-v1/"+bucket+".json").then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json();}).catch(e=>{cache.delete(bucket);throw e;}));
      const data=await cache.get(bucket);'''
        new = '''      // CATMAS_DIFF_HASH_V1: freeze comparisons to the same publication as history.
      const path="base-diffs-v1/"+bucket+".json";
      const expected=publication?.content_differences?.sha256?.[path];
      if(publication?.content_differences && !/^[a-f0-9]{64}$/.test(expected||"")) throw Error("Manifesto incompleto.");
      const key=path+":"+(expected||"legacy");
      if(!cache.has(key)) cache.set(key,fetch(path+(expected?"?v="+expected:""),{cache:"no-store"}).then(async r=>{
        if(!r.ok)throw Error("HTTP "+r.status);
        const bytes=await r.arrayBuffer();
        if(expected){const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),x=>x.toString(16).padStart(2,"0")).join("");if(hash!==expected)throw Error("Comparações de outro ciclo. Recarregue em instantes.");}
        return JSON.parse(new TextDecoder().decode(bytes));
      }).catch(e=>{cache.delete(key);throw e;}));
      const data=await cache.get(key);'''
        js = once(js, old, new)
        js = once(js, 'const labels = {spec:', 'const labels = {servico_id:"ID do material/serviço pai",linhas_fornecimento:"Linhas de fornecimento",elementos_codigos:"Elementos de despesa",spec:')
    files['base-comparison-v1.js'] = js
    html = files['history.html']
    old = 'window.CatmasBaseDiff.render($("#base-comparison"), item, activeScope);'
    new = 'window.CatmasBaseDiff.render($("#base-comparison"), item, activeScope, publication);'
    if new not in html:
        html = once(html, old, new)
    files['history.html'] = html
    worker = files['rastreador/worker.js']
    if 'CATMAS_DIFF_HASH_V1' not in worker:
        old = "if(!baseBuckets.has(bucket))baseBuckets.set(bucket,fetch('../base-diffs-v1/'+bucket+'.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Comparação entre bases indisponível ('+r.status+').');return r.json();}).then(CatmasContent.validateBucket).catch(e=>{baseBuckets.delete(bucket);throw e;}));"
        new = '''// CATMAS_DIFF_HASH_V1: all eight buckets must match the loaded publication.
 const path='base-diffs-v1/'+bucket+'.json',expected=publication.content_differences?.sha256?.[path];
 if(publication.content_differences&&!/^[a-f0-9]{64}$/.test(expected||''))throw Error('Manifesto de comparações incompleto.');
 if(!baseBuckets.has(bucket))baseBuckets.set(bucket,fetch('../'+path+(expected?'?v='+expected:''),{cache:'no-store'}).then(async r=>{
 if(!r.ok)throw Error('Comparação entre bases indisponível ('+r.status+').');
 const bytes=await r.arrayBuffer();
 if(expected){const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');if(hash!==expected)throw Error('Comparações de outro ciclo. Recarregue em instantes.');}
 return JSON.parse(new TextDecoder().decode(bytes));}).then(CatmasContent.validateBucket).catch(e=>{baseBuckets.delete(bucket);throw e;}));'''
        worker = once(worker, old, new)
        # The tracker must also reject a history database from a different cycle.
        worker = once(worker, ' let compressed=new Uint8Array(await response.arrayBuffer());', ''' let compressed=new Uint8Array(await response.arrayBuffer());
 if(!/^[a-f0-9]{64}$/.test(publication.history_sha256||''))throw Error('Metadados do histórico indisponíveis.');
 const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',compressed)),x=>x.toString(16).padStart(2,'0')).join('');
 if(actual!==publication.history_sha256)throw Error('Histórico de outro ciclo. Recarregue em instantes.');''')
    files['rastreador/worker.js'] = worker
    content = files['rastreador/content.js']
    if "servico_id:'ID do material/serviço pai'" not in content:
        content = once(content, "const labels={spec:", "const labels={servico_id:'ID do material/serviço pai',linhas_fornecimento:'Linhas de fornecimento',elementos_codigos:'Elementos de despesa',spec:")
    files['rastreador/content.js'] = content
    return files
