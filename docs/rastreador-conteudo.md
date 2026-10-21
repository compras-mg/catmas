# Rastreador — reutilização de conteúdo do histórico

Integração de 21/10/2026, sem alteração da extração, do banco histórico, dos arquivos de comparação ou da página de histórico por item.

## Fontes reaproveitadas

1. `history.db.gz`: `snapshots`, `snapshot_components`, `requests`, `request_events`. A síntese compara Antes → Analisado apenas quando ambos os valores foram recuperados; nulidade não equivale a vazio. Duplicidades por etapa ou componente/etapa suspendem a comparação. Evidência de aprovação com comunicação de sucesso é separada dos valores; status reprovado/parcial é sinalizado. As chaves de solicitação não são atribuídas a eventos do item por horário. Solicitações do pai são rotuladas separadamente.
2. `base-diffs-v1/{item_id % 8}.json`: mesmo contrato já usado em `base-comparison-v1.js`. O Rastreador reutiliza diretamente o renderizador `CatmasBaseDiff.html`, com os mesmos dados e validação de identidade (ID e código), rótulos e fontes. A síntese resume campos/tipos observados por par de publicações. Data de publicação não é data de edição; extração pode causar diferenças. O detalhe mostra essas comparações para o item, não para o evento.

## Consulta por período de conteúdo

Seção separada das contagens de eventos. Filtra data da publicação posterior (Brasília), tipo e código/texto. Não aplica responsável ou tipo de ação dos eventos, por ausência de vínculo confirmado. Cada resultado é um par item/publicações; campos diferentes são contados separadamente. Página de 20 pares. Os oito arquivos são carregados sob demanda e reutilizados na sessão. Falha na comparação não bloqueia consulta dos eventos ou estados de solicitação. Identidades divergentes são rejeitadas ou excluídas, com informação na consulta agregada.

## Cobertura

Eventos na publicação consultada: 12/06/2018 a 19/10/2026, sem garantia de completude. Estados de solicitação têm cobertura própria, não são todos os estados do item. Cópias recuperadas: publicações 22/09, 06/10 e 20/10/2026 em Brasília. Comparação incremental ainda não integrada à extração duas vezes ao dia; não prometer crescimento automático dessa fonte.

## Datas do Rastreador

Atalhos 1, 7, 15, 30, 60 e 90 dias corridos inclusive hoje, em Brasília. Mês fechado selecionável por mês/ano, rejeitando mês atual e futuro; sugerido o último mês encerrado. Intervalos personalizados continuam inclusivos. Gráfico agrupa por mês quando o intervalo supera 45 dias. URL `painel/` preservada; título visível alterado para Rastreador.

## Validação

`node tests/panel.test.cjs` verifica as medidas e associações com SQLite real, além de 30/60/90 dias, virada de ano, mês bissexto e rejeição de meses não encerrados.

`node tests/content.test.cjs` verifica com os arquivos de comparação e SQLite reais: item ID 15/código 248 CAPSULA → CÁPSULA; solicitação 26978 com capacidade 95 ML → 115 ML, e evidência 51056; exclusão de valores ausentes e comparações ambíguas; validação de identidade; data de publicação em Brasília; filtro de conteúdo independente de ação/responsável; consulta vazia.

Para os testes de dados reais: usar CATMAS_TEST_DB para o banco descompactado. Os arquivos de comparação devem estar em site/base-diffs-v1/ na árvore de fonte, ou em base-diffs-v1/ no pacote local de teste. Eles são os artefatos já publicados pelo histórico; não precisam ser gerados pelo Rastreador.

Regra de associações permanece v1: descrições atuais e contexto de eventos. Não incorpora automaticamente diferenças de conteúdo, pois ainda não há vínculo comprovado edição/evento.
