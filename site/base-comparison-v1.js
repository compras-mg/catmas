/* Observed differences between published copies, not audited edit events. */
(() => {
  const cache = new Map();
  let generation = 0;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const labels = {spec:"Especificação",material_nome:"Nome do material/serviço pai",situacao:"Situação",ok_registro_precos:"Registro de preços",material_codigo:"Código do material/serviço pai",especificacao_longa:"Indicador de especificação longa"};
  function display(value) { return value === null ? "Valor nulo na cópia" : value === "" ? "Texto vazio na cópia" : String(value); }
  function marked(a, b) {
    a = display(a); b = display(b);
    let start=0, end=0;
    while (start < Math.min(a.length,b.length) && a[start]===b[start]) start++;
    while (end < Math.min(a.length,b.length)-start && a[a.length-1-end]===b[b.length-1-end]) end++;
    const mark = s => esc(s.slice(0,start))+"<mark>"+esc(s.slice(start,end?s.length-end:undefined))+"</mark>"+(end?esc(s.slice(-end)):"");
    return [mark(a),mark(b)];
  }
  function date(s) {return new Date(s).toLocaleString("pt-BR",{timeZone:"America/Sao_Paulo",dateStyle:"short",timeStyle:"short"});}
  function html(data, id, code) {
    if(data.schema!==1 || !Array.isArray(data.sources) || !data.items) throw Error("Formato inválido.");
    const rows=data.items[id] || [];
    if(rows.some(r=>String(r[1]).replace(/^0+/,"")!==String(code).replace(/^0+/,""))) throw Error("Identidade divergente.");
    let out="<h2>Diferenças entre bases publicadas</h2><p class='notice'>Comparação de cópias de setembro e outubro de 2026. As datas abaixo são de publicação (horário de Brasília), não da edição. Autoria, motivo e vínculo com eventos não foram confirmados. Mudanças na extração também podem produzir diferenças.</p>";
    if(!rows.length) return out+"<p class='empty'>Nenhuma diferença encontrada para este item nas cópias comparadas. Isso não comprova ausência de edições entre as extrações.</p>";
    const groups=new Map();
    for(const row of rows) {if(!groups.has(row[6]))groups.set(row[6],[]);groups.get(row[6]).push(row);}
    for(const [sourceIndex, records] of groups) {
      const source=data.sources[sourceIndex];
      if(!source || !/^[a-f0-9]{40}$/.test(source.before) || !/^[a-f0-9]{40}$/.test(source.after)) throw Error("Fonte inválida.");
      out+="<h3>Base de "+esc(date(source.published_before))+" → "+esc(date(source.published_after))+"</h3>";
      out+="<p class='meta'>"+records.length+" campo(s) com diferença · <a target='_blank' rel='noopener' href='https://github.com/compras-mg/catmas/commit/"+source.before+"'>Fonte anterior</a> · <a target='_blank' rel='noopener' href='https://github.com/compras-mg/catmas/commit/"+source.after+"'>Fonte posterior</a></p>";
      out+="<div class='base-diff-scroll'><table class='base-diff-table'><thead><tr><th>Campo</th><th>Antes</th><th>Depois</th></tr></thead><tbody>";
      for(const row of records) {
        const values=marked(row[3],row[4]);
        const kind={somente_diacriticos:"Somente acentuação/diacríticos",representacao_unicode:"Representação Unicode",outra_diferenca:"Diferença de conteúdo"}[row[5]] || "Diferença";
        out+="<tr><th scope='row'>"+esc(labels[row[2]]||row[2])+"<div class='meta'>"+esc(kind)+"</div></th><td>"+values[0]+"</td><td>"+values[1]+"</td></tr>";
      }
      out+="</tbody></table></div>";
    }
    return out;
  }
  window.CatmasBaseDiff = {html, marked, async render(container, item, scope) {
    const token=++generation;
    if(scope!=="item") {container.hidden=true;return;}
    container.hidden=false;
    container.innerHTML="<h2>Diferenças entre bases publicadas</h2><p>Carregando comparação…</p>";
    const bucket=Number(item.item_id)%8;
    try {
      if(!cache.has(bucket)) cache.set(bucket,fetch("base-diffs-v1/"+bucket+".json").then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json();}).catch(e=>{cache.delete(bucket);throw e;}));
      const data=await cache.get(bucket);
      if(token===generation)container.innerHTML=html(data,item.item_id,item.code);
    } catch(error) {
      if(token===generation)container.innerHTML="<h2>Diferenças entre bases publicadas</h2><p class='notice'>Não foi possível carregar esta comparação. Recarregue a página para tentar novamente. Os registros por solicitação permanecem disponíveis.</p>";
    }
  }};
})();
