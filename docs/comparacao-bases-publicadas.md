# Comparação entre bases publicadas

A interface mostra diferenças observadas entre cópias do catálogo, sem equipará-las a eventos de edição. As datas são de publicação em Brasília; autoria, motivo e vínculo com eventos não são inferidos. Os registros administrativos existentes permanecem disponíveis.

Dados: site/base-diffs-v1/{item_id % 8}.json; cada arquivo contém schema=1, sources e items. Cada registro é [id_diferenca, codigo, campo, antes, depois, tipo, indice_fonte]. As fontes guardam commits e datas UTC de publicação. IDs e códigos são conferidos antes da renderização. O módulo trata falhas sem bloquear o histórico administrativo e evita resultados de consultas anteriores ao trocar de item.

Verificação: renderização dos 7.207 itens e 7.353 diferenças; teste do item 15/código 248, escape HTML, identidade divergente e sintaxe JavaScript. Comparações por solicitação continuam separadas.

Publicação autorizada explicitamente pelo usuário para a ferramenta de histórico. Dados completos e interface publicados em gh-pages; ativação no commit 6f8d8f4a776b21aa34a2d865bc547b080b4e8da3. O buscador não foi alterado.

Esta recuperação cobre as cópias de setembro/outubro de 2026. A atualização automática incremental ainda não está integrada à rotina de extração.
