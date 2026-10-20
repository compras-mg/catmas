# Painel CATMAS por período

Página adicional em `painel/`, ligada à base pública `history.db.gz` e à publicação `atualizacao.json` da raiz. Não altera o buscador ou o histórico por item. Sem preenchimento manual, sem persistência de dados pessoais ou alterações na base.

## Dados e limites

- Eventos da tabela `events` ligados aos itens e aos rótulos de ação. A interface conta registros e itens distintos separadamente. Comunicações 16/17 são ocultas por padrão. Não se presume que um evento comprove conclusão do processo.
- Datas sem fuso da exportação são interpretadas no horário de Brasília. Atalhos contam dias corridos, incluindo hoje. Há acesso ao último dia com eventos.
- Cobertura indica datas mínima/máxima encontradas, não garantia de completude. Versão da publicação é lida a cada abertura.
- Descrição atual é rotulada explicitamente. Não é tomada como versão histórica.
- Síntese, motivo, demanda e ID da edição ficam vazios. Estados de solicitações não são atribuídos a eventos sem vínculo comprovado.
- O banco é baixado no navegador e consultado em um Worker para preservar a resposta da interface. Índice por data é criado apenas na cópia em memória.

## Associações v1

Candidatos: outros itens do mesmo tipo, eventos não técnicos em ±7 dias; material pai em comum, prefixo de grupo em comum, ou mesmo início de nome. Até 3.000 candidatos, priorizando o material pai e distância temporal; quando excede, a busca informa o limite. Até 8 itens, escolhendo o evento de maior pontuação por item.

Pontuação: pai 30 / classe 20 / grupo 8 (alternativas); similaridade textual Jaccard até 30; distância temporal linear até 25; mesmo tipo de evento 10; mesmo responsável identificado 5. Critério mínimo: 40 pontos e pai ou classe compartilhada, ou similaridade >= 0,3. Prefixos derivam dos códigos de material de 8 dígitos (2 grupo, 4 classe). Descrições atuais e características textuais são usadas, não o conteúdo da mudança. Vínculos com solicitações não integram o método v1. Não é probabilidade; coincidências em lotes podem gerar falsos positivos. Recalibrar com a equipe antes de interpretação quantitativa.

## Validação

`tests/panel.test.cjs` testa a pontuação (mesmo item, tipo diferente, distância temporal, normalização de acentos), consultas com a base real, exclusão de comunicações, contagens, intervalo vazio, entrada de pesquisa com caracteres SQL e relações retornadas. Usar CATMAS_TEST_DB para apontar outra base SQLite.

## Próximos passos

Identificar no Data Lake versões de conteúdo e vínculo entre evento, edição e solicitação. Introduzir comparação do conteúdo efetivamente alterado e referência da demanda sem confundir inferência com vínculo explícito. Preservar campos vazios até haver fonte válida. Nenhum dado da planilha manual é publicado nesta página.
