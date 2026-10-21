# Comparação entre bases publicadas

A interface mostra diferenças observadas entre cópias do catálogo, sem equipará-las a eventos de edição. As datas são de publicação em Brasília; autoria, motivo e vínculo com eventos não são inferidos. Os registros administrativos existentes permanecem disponíveis.

Dados: site/base-diffs-v1/{item_id % 8}.json; cada arquivo contém schema=1, sources e items. Cada registro é [id_diferenca, codigo, campo, antes, depois, tipo, indice_fonte]. As fontes guardam commits e datas UTC de publicação. IDs e códigos são conferidos antes da renderização. O módulo trata falhas sem bloquear o histórico administrativo e evita resultados de consultas anteriores ao trocar de item.

Verificação: renderização dos 7.207 itens e 7.353 diferenças; teste do item 15/código 248, escape HTML, identidade divergente e sintaxe JavaScript. Comparações por solicitação continuam separadas.

Publicação pendente: revisão automática interrompeu o envio dos dados para gh-pages. Apenas partes 0–5 foram enviadas. Partes 6–7 e ativação em history.html aguardam autorização explícita para publicação pública. A página de produção ainda não carrega o novo módulo.

Esta recuperação cobre as cópias de setembro/outubro de 2026. A atualização automática incremental ainda não está integrada à rotina de extração.
