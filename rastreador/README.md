# Leia-me — Rastreador CATMAS

[Abrir o Rastreador](https://compras-mg.github.io/catmas/rastreador/) · [Consultar o histórico de um item](https://compras-mg.github.io/catmas/history.html?avaliacao=escopos-v1)

Este guia explica como ler as medidas e os resultados do Rastreador. Documentação atualizada em 21/10/2026.

## 1. O que o Rastreador mostra

O Rastreador consulta automaticamente os **registros de movimentação existentes na base histórica do CATMAS** e os relaciona aos itens do catálogo. Não há preenchimento manual, lista de tarefas ou status de acompanhamento da equipe.

Um registro pode indicar criação de item, mudança de situação, alteração de especificação, alteração de característica, de unidade ou de vínculo, entre outras ações. A presença de um registro não comprova, por si só, que todo o processo administrativo foi concluído, nem que houve uma mudança no texto da descrição.

A listagem atual tem **uma linha por evento**, não uma linha por item, material, solicitação ou edição de conteúdo. Vários eventos do mesmo item aparecem separadamente.

## 2. Como interpretar as três medidas

Todas as medidas se referem **aos mesmos filtros e ao mesmo período da consulta**, e abrangem o resultado inteiro, não apenas a página de 30 registros que está visível.

| Medida | O que conta | O que não significa |
| --- | --- | --- |
| **Registros de movimentação** | Cada evento encontrado nos filtros. Três eventos do mesmo item contam três vezes. | Não é quantidade de itens, materiais, edições de conteúdo ou trabalhos concluídos. |
| **Itens distintos** | Cada ID interno de item presente nos eventos filtrados, contado uma única vez. | Não significa que todos esses itens tiveram a descrição alterada. Uma mudança de situação também movimenta o item. |
| **Materiais/serviços com itens movimentados** | Os materiais ou serviços pais vinculados aos itens movimentados, sem repetir o mesmo pai dentro do mesmo tipo. | **Não é uma contagem de alterações no cadastro do próprio material/serviço.** |

**Exemplo — Bucha de redução, item `002066149`:** em 19/10/2026, aparecem uma criação às 14:57:15 e duas mudanças de situação às 14:57:55 e 14:58:40. Considerando somente esses eventos, o resultado é **3 registros, 1 item distinto e 1 material/serviço pai**. São três eventos diferentes; o item não é contado três vezes na medida de itens distintos.

Outro exemplo: cinco itens de um mesmo material com movimentações resultam em **5 itens distintos e 1 material/serviço pai**, independentemente da quantidade de eventos gerados por eles.

**Exceção de vínculo ausente:** na versão inicial, quando um item não possui ID de material/serviço pai, ele entra provisoriamente como uma chave própria na terceira contagem. Portanto, essa medida também pode incluir itens sem pai identificado; nesses casos, não deve ser lida como um total exato de pais conhecidos.

As contagens distintas não devem ser somadas entre dias para obter o total do período: o mesmo item ou material pode aparecer em vários dias, mas conta uma única vez na consulta do período inteiro.

Para medir **materiais efetivamente alterados**, será necessário identificar os eventos próprios do cadastro do material. A terceira medida atual não faz essa apuração.

## 3. Como consultar

1. Escolha **Último dia**, **Últimos 7 dias**, **Últimos 15 dias**, **Últimos 30 dias**, **Últimos 60 dias**, **Últimos 90 dias**, **Todos**, **Mês fechado** ou um intervalo personalizado.
2. Se desejar, filtre por material/serviço, tipo de movimentação e responsável registrado na origem.
3. Digite um código ou um trecho de texto e clique em **Consultar**.
4. Selecione uma movimentação para abrir os detalhes à direita e acessar o histórico do item.

### Períodos e datas

- **Todos** preenche as datas com o primeiro e o último evento encontrados na base carregada. Na versão consultada em 21/10/2026, isso corresponde a **12/06/2018 a 19/10/2026**. Os limites são calculados novamente a cada carregamento, não são datas fixas. Demais filtros continuam ativos. “Todos” significa todo o intervalo disponível de eventos, não garantia de histórico completo. A consulta separada de diferenças entre publicações usa essas mesmas datas de filtro: se a publicação posterior for mais recente que o último evento, amplie a data final para incluí-la.

- Os atalhos usam dias corridos e **incluem o dia atual**, no horário de Brasília. “Último dia” corresponde ao dia de hoje; não é uma janela móvel de 24 horas.
- **Mês fechado** permite escolher um mês já encerrado, do primeiro ao último dia, incluindo ambos. Por exemplo, em 21/10/2026, setembro de 2026 é um mês fechado; outubro ainda não. O mês anterior é sugerido inicialmente. Um mês fechado do calendário não implica que a base tenha dados completos desse mês.
- No intervalo personalizado, as duas datas são incluídas.
- O filtro usa a data do evento, não a data em que a base foi publicada nem a data de atualização da descrição atual.
- O botão **Usar último dia com registros** escolhe a maior data de evento encontrada na base inteira. Outros filtros continuam ativos; por isso, uma combinação específica ainda pode não retornar resultados nesse dia.
- O gráfico mostra os eventos por dia. Em consultas maiores que 45 dias, agrupa por mês.

### Busca

- Uma entrada composta só por números busca o código exato de item ou material/serviço, aceitando com ou sem zeros à esquerda. Um código pode existir nos dois tipos; use o filtro de material/serviço para distingui-los.
- Uma entrada textual busca um trecho no nome do material/serviço, na especificação atual ou na informação complementar do evento. A busca textual não tem a mesma normalização de acentos usada na regra de associações.

### Comunicações técnicas

Por padrão, os eventos de comunicação com pendência e comunicação com sistema externo — códigos 16 e 17 — ficam ocultos. Eles podem representar tentativas, respostas ou integrações, além das ações cadastrais.

Marcar **Incluir comunicações técnicas** e consultar novamente altera a lista, as contagens e o gráfico. Selecionar um tipo técnico sem marcar essa opção produz uma consulta sem resultados.

## 4. O detalhe de uma movimentação

O detalhe apresenta data/hora, tipo de ação, responsável informado no evento, material/serviço pai, indicador de operação automática e informação complementar da origem.

- **Responsável no evento** não é necessariamente o responsável por todo o trabalho, pela análise ou pela solicitação.
- **Operação automática na origem** é um atributo do registro, não um status de conclusão.
- **Identificador do evento** permite localizar o registro histórico. Não equivale necessariamente ao identificador de uma edição que reuniu várias ações.
- **Descrição atual do item** é o texto disponível na base atual. Ela não deve ser interpretada como o texto que existia na data da movimentação.

A seção **Conteúdo disponível para este item** reutiliza as comparações do histórico. Mostra uma síntese dos campos com diferenças entre cópias publicadas e as comparações Antes → Analisado de solicitações do item ou de seu material/serviço pai. Essas comparações não são atribuídas ao evento selecionado. Justificativas, referências e autoria de solicitação são apresentadas no contexto da respectiva solicitação; não são herdadas como motivo ou autoria da edição do item. Não há preenchimento manual.

A existência de estados Antes/Solicitado/Analisado em solicitações do mesmo item não comprova que esses estados pertencem à movimentação selecionada. O histórico do item pode mostrar essas solicitações separadamente.

### Diferenças de conteúdo entre bases publicadas

O Rastreador oferece uma consulta separada às diferenças entre cópias publicadas do catálogo. Abra **Diferenças de conteúdo entre bases publicadas** e clique em **Consultar diferenças publicadas no período**.

- Usa o período pela **data da publicação posterior**, o tipo material/serviço e a busca por código ou texto. Não aplica filtros de responsável ou tipo de evento, porque esses vínculos não foram confirmados.
- Cada resultado reúne um item e um par de publicações. As contagens de pares e de campos diferentes são independentes dos eventos e não alteram as três medidas principais.
- Mostra valores anteriores e posteriores, o tipo de diferença (inclusive acentuação) e links para as duas publicações de origem.
- Não é a data comprovada da edição. Uma diferença pode ter ocorrido entre as extrações ou decorrer de mudança no processo de extração.
- As cópias recuperadas de setembro/outubro de 2026 foram preservadas. A geração incremental está integrada à rotina existente desde o ciclo `1a2cdd3a063d40458555f1ad6e87c027`, confirmado em 21/10/2026 às 01:26:44 (Brasília). Recarregar a página consulta os resultados publicados; não executa extrações.
- As contagens incluem diferenças textuais nas listas. No primeiro intervalo automático, o item `000000035` (ID `105183`) apresenta os mesmos cinco elementos de despesa em outra ordem. Isso não comprova mudança dos vínculos. Ainda não há separação automática dessa categoria nas contagens.

As diferenças nas solicitações são obtidas do mesmo banco histórico. Só comparam valores presentes nos estados Antes e Analisado. Nulos não são tomados como vazios; inclusões e exclusões não são presumidas a partir da ausência de registros. Duplicidade por etapa ou por componente/etapa suspende a comparação. Aprovação com comunicação de sucesso é evidência administrativa separada, com horário bruto e fuso não confirmado; não é tratada como instante comprovado de gravação. Solicitações reprovadas ou parcialmente aprovadas são sinalizadas.

## 5. Alterações possivelmente relacionadas

Ao clicar em **Buscar associações**, o Rastreador procura movimentações de outros itens que possam ter relação com a selecionada. A busca é automática e apresenta os motivos de cada sugestão.

**A pontuação é uma medida de proximidade. Não é uma probabilidade, um vínculo comprovado nem evidência de que uma alteração causou a outra.**

### Onde a regra procura

- Outros itens do mesmo tipo: material com material ou serviço com serviço.
- Eventos não técnicos, com até 7 dias de distância antes ou depois do evento selecionado. Essa janela pode ultrapassar o período escolhido nos filtros do Rastreador.
- Candidatos com o mesmo material/serviço pai, o mesmo prefixo de grupo ou o mesmo início de nome.
- Até 3.000 eventos candidatos, priorizando o mesmo pai e a proximidade no tempo. Quando esse limite é atingido, o Rastreador avisa que a busca é parcial.

Não é uma busca exaustiva de todas as relações do catálogo. Uma possível relação fora desses critérios pode não ser examinada.

### Como a pontuação é calculada

| Critério | Pontos |
| --- | --- |
| Mesmo material/serviço pai | 30 |
| Ou mesmo prefixo de classe, quando não há pai em comum | 20 |
| Ou mesmo prefixo de grupo, quando não se aplicam os anteriores | 8 |
| Semelhança das descrições atuais | Até 30 |
| Proximidade no tempo: quanto menor o intervalo, maior a pontuação | Até 25 |
| Mesmo tipo de evento | 10 |
| Mesmo responsável identificado na origem | 5 |

Os três primeiros critérios são alternativos, não cumulativos. Os prefixos de grupo e classe são derivados, respectivamente, dos 2 e 4 primeiros dígitos dos códigos de material/serviço de 8 dígitos.

A similaridade textual compara conjuntos de palavras, desconsiderando acentos e termos genéricos. Usa o nome atual do material/serviço e até os primeiros 1.000 caracteres da especificação atual do item. **Ainda não compara os textos efetivamente alterados naquela edição. A disponibilização das comparações de conteúdo não muda essa regra: não há vínculo confirmado entre cada evento e a respectiva edição.**

Para aparecer, a sugestão precisa atingir pelo menos 40 pontos e também ter pai ou prefixo de classe em comum, ou similaridade textual de pelo menos 30%. O Rastreador mostra até 8 itens relacionados, com um evento por item: o de maior pontuação entre os candidatos avaliados. As pontuações são arredondadas na composição dos critérios.

### Limites da interpretação

- Mesma data, mesmo responsável ou mesmo grupo, isoladamente, não comprovam relação.
- Atualizações em massa podem produzir associações inadequadas por coincidência.
- As regras e os pesos são iniciais e ainda precisam ser calibrados com exemplos reconhecidos pela equipe.
- Uma lista vazia significa que nenhuma sugestão atingiu os critérios na busca realizada; não significa que não existe relação.

## 6. Atualização e cobertura dos dados

### Desde quando é possível rastrear?

**Não é possível afirmar “desde sempre”.** Na base publicada consultada em 21/10/2026, o evento mais antigo é de **12/06/2018** e o mais recente é de **19/10/2026**. Essas datas são limites observados nesta versão; o topo do Rastreador mostra os limites da base carregada e pode mudar com novas publicações. Não comprovam cobertura contínua, completude nem disponibilidade do texto anterior de todas as alterações.

Há três coberturas diferentes:

| Fonte | O que permite observar | Cobertura e data usada |
| --- | --- | --- |
| Eventos históricos | Que determinada movimentação foi registrada, com seu tipo e dados de origem | Eventos encontrados desde 12/06/2018 na base consultada. O filtro usa a data do evento. Nem todo evento preserva o conteúdo anterior/posterior. |
| Estados de solicitações | Diferenças entre valores armazenados em Antes e Analisado da mesma solicitação | Apenas solicitações/estados existentes na exportação. Não representam todas as edições diretas do catálogo e não são atribuídos aos eventos do item por aproximação de horário. |
| Comparação de cópias publicadas | Diferenças de conteúdo, incluindo acentuação, entre duas cópias do catálogo | Recuperação recente com publicações de 22/09/2026, 06/10/2026 e 20/10/2026 no horário de Brasília. Os pares históricos são 22/09 → 06/10 e 06/10 → 20/10, acrescidos dos intervalos processados pela rotina incremental a partir de 20/10 → 21/10. A consulta usa a data da publicação posterior, não a data exata da edição. |

A tarefa existente `CATMAS-Extracao-Python-1230` chama `rotina_integrada.py all --scheduled`, agora com comparação e preservação dos resultados antes da publicação. A primeira execução integrada foi disparada manualmente em 21/10/2026 e confirmada no Pages; a execução pelo próximo disparo do Agendador ainda não foi observada nesta validação. A extração isolada do histórico continua sem publicar comparações.

O primeiro intervalo automático registrou 16.861 campos diferentes em 16.014 itens, sem entradas, saídas, divergências de identidade ou alteração do esquema SQLite. Esses números incluem diferenças de representação, como a ordem das listas; não são quantidade comprovada de edições. O commit do conversor é o mesmo nas duas bases, mas os hashes dos arquivos de conversão e consulta só passaram a ser registrados neste ciclo, impedindo confirmar retrospectivamente a igualdade desses arquivos.

### Operação e retomada

Pasta da rotina: `C:\Users\m752409\Documents\CATMAS-Extracao-Python-v3`.

- Bases preservadas: `publicacao-integrada/diferencas/bases-anteriores/`.
- Diagnósticos: `publicacao-integrada/diferencas/intervalos/` e, na publicação, `base-diffs-v1/intervalos/`.
- Confirmação: `publicacao-integrada/diferencas/confirmado.json`, com `status: sucesso`, ciclo e último commit processado. Confirmações por ciclo em `publicacao-integrada/diferencas/execucoes/`.
- Logs: `logs/integrado-*.log`. O marcador só avança após a conferência dos arquivos servidos.
- Em falha, preservar o lote e executar na pasta da rotina: `uv run --offline --script rotina_integrada.py retry`. Isso retoma a publicação sem nova extração.
- Cópias compactadas não têm expurgo automático nesta versão. Monitorar o espaço em disco.

Validação real nas interfaces: o item `000000035` mostrou o intervalo 20/10 → 21/10 no Histórico e no Rastreador. A comparação anterior `CAPSULA → CÁPSULA` do item `000000248` permaneceu no Histórico, sem atribuição ao evento de uma analista.


O Rastreador usa a base histórica e os arquivos de comparação publicados junto à ferramenta. Ao abrir a página, consulta a versão da publicação e carrega a base correspondente. Não é uma conexão em tempo real com o sistema CATMAS ou com o Data Lake. Uma página já aberta não passa a usar automaticamente uma nova publicação; recarregue-a para consultar a atualização.

A data de publicação e o intervalo mínimo/máximo dos eventos aparecem no topo. Essas datas **não garantem cobertura contínua ou completa**. O aviso “O período inclui dias posteriores ao último registro disponível” significa que a consulta termina depois da data do evento mais recente na base carregada. Por exemplo, uma consulta até 21/10 com último evento em 19/10 inclui dois dias sem registros disponíveis. Isso não comprova que não ocorreram movimentações nesses dias. Um período vazio pode decorrer de ausência de movimentação, atraso de atualização ou lacuna de exportação.

O banco é consultado no navegador. A primeira abertura pode levar alguns instantes devido ao tamanho da base. Os filtros não alteram o cadastro ou a base de origem.

## 7. O que ainda depende do Data Lake

Precisamos localizar tabelas e campos que preservem valores anteriores e posteriores, datas e identificadores das edições e vínculos entre edição, evento e solicitação. Isso permitirá:

- Mostrar o conteúdo efetivamente alterado, inclusive correções textuais e de acentuação.
- Gerar uma síntese automática da edição baseada nas diferenças reais.
- Recuperar motivos e demandas quando registrados na origem.
- Distinguir alterações do material pai das movimentações dos seus itens.
- Melhorar as associações pela semelhança das próprias mudanças.

As cópias recuperadas e os estados de solicitação já permitem exibir conteúdo anterior/posterior em seus próprios contextos. Ainda falta validar vínculo com eventos, abrangência de edições diretas, autoria e instante de gravação. A ferramenta não reconstrói o texto anterior a partir da descrição atual nem atribui motivos por suposição.

