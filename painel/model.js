(function (root) {
  'use strict';
  const TECHNICAL = [16,17];
  const normalize = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const stop = new Set('a o as os de da do das dos e em para por com sem um uma tipo material servico uso modelo'.split(' '));
  function tokens(s) { return new Set(normalize(s).match(/[a-z0-9]+/g)?.filter(t=>t.length>2&&!stop.has(t))||[]); }
  function similarity(a,b) { const x=tokens(a),y=tokens(b);if(!x.size||!y.size)return 0;let both=0;for(const v of x)if(y.has(v))both++;return both/(x.size+y.size-both); }
  function stamp(value) { const d=String(value||'');return Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(d)?d:d+'-03:00'); }
  function prefix(v,n) {const s=String(v||'').replace(/\D/g,'');return s.length===8?s.slice(0,n):null;}
  function relation(a,b) {
    if(Number(a.item_id)===Number(b.item_id)||a.item_type!==b.item_type)return null;
    const gap=Math.abs(stamp(a.occurred_at)-stamp(b.occurred_at))/86400000;
    if(!Number.isFinite(gap)||gap>7)return null;
    const parent=a.material_service_id!=null&&b.material_service_id!=null&&Number(a.material_service_id)===Number(b.material_service_id);
    const sameClass=!!prefix(a.material_service_code,4)&&prefix(a.material_service_code,4)===prefix(b.material_service_code,4);
    const sameGroup=!!prefix(a.material_service_code,2)&&prefix(a.material_service_code,2)===prefix(b.material_service_code,2);
    const sim=similarity((a.material_service_name||'')+' '+(a.current_specification||'').slice(0,1000),(b.material_service_name||'')+' '+(b.current_specification||'').slice(0,1000));
    if(!parent&&!sameClass&&sim<0.3)return null;
    const reasons=[];
    let score=0;
    if(parent){score+=30;reasons.push('Mesmo material/serviço pai');}
    else if(sameClass){score+=20;reasons.push('Mesmo prefixo de classe (4 dígitos)');}
    else if(sameGroup){score+=8;reasons.push('Mesmo prefixo de grupo (2 dígitos)');}
    score+=Math.round(sim*30);
    if(sim>=0.15)reasons.push('Semelhança das descrições atuais: '+Math.round(sim*100)+'%');
    score+=Math.round(25*(1-gap/7));
    reasons.push(gap<1?'Intervalo menor que 24 horas':'Intervalo de '+gap.toFixed(1).replace('.',',')+' dias');
    if(Number(a.action_code)===Number(b.action_code)){score+=10;reasons.push('Mesmo tipo de evento');}
    if(a.user_masp&&b.user_masp&&a.user_masp===b.user_masp){score+=5;reasons.push('Mesmo responsável no registro de origem');}
    if(score<40)return null;
    return {score,similarity:sim,gap,reasons};
  }
  function dateRange(end,days){const d=new Date(end+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-days+1);return {from:d.toISOString().slice(0,10),to:end};}
  root.CatmasModel={TECHNICAL,normalize,tokens,similarity,relation,dateRange};
})(typeof self!=='undefined'?self:globalThis);
