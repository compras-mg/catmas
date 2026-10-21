# Integração incremental — instalação e execução real pendentes

Esta entrega prepara a integração na tarefa existente `CATMAS-Extracao-Python-1230`, cuja ação é `uv run --offline --script C:\Users\m752409\Documents\CATMAS-Extracao-Python-v3\rotina_integrada.py all --scheduled`. Não cria uma segunda tarefa nem modifica extrações/conversor. Ainda não há ciclo real confirmado com esta versão.

## Instalação

Baixar os quatro arquivos Python desta pasta em uma subpasta `pacote-diferencas` da pasta instalada e executar `uv run --offline --script pacote-diferencas\instalar_diferencas.py`. O instalador confere XML da tarefa, pasta, argumentos, assinatura do script recebido para análise e importação dos módulos. Preserva backups em `backups-diferencas/<data>/`. A instalação usa a mesma trava da rotina. Se já houver uma execução, aguardar seu término antes de instalar.

Depois, na pasta da tarefa, executar `uv run --offline --script rotina_integrada.py all --scheduled`. Só declarar a integração ativa após retornar SUCESSO e conferir os dados nas duas ferramentas. O código publicado nesta branch é um pacote de implantação, não evidência de instalação no Windows.

## Publicação e recuperação

`rotina_integrada.finish` chama o comparador, verifica bases e arquivos servidos, e só então grava o sucesso. Antes de nova extração, `all` retoma lote pendente não confirmado. Um lote ultrapassado por outro publicador não substitui o mais recente: fica preservado localmente, com `requested_cycle_superseded=true`, e a cobertura remota é reconciliada.

Git prepara dois commits locais: o primeiro contém as bases e serve como identificador imutável da cópia; o segundo acrescenta comparações e manifesto. Um único push sem force aponta a branch diretamente ao segundo. O primeiro nunca é enviado como estado intermediário da branch. Suas datas de commit são referências de publicação; não são horário comprovado de edição nem horário em que o Pages terminou de servir o conteúdo.

Em conflito ou resposta perdida no envio, reler a branch e reconstruir as diferenças a partir dos arquivos remotos. Intervalos pendentes são recuperados na ordem dos commits do primeiro ramo de ancestralidade. O marco inicial é a publicação de 20/10/2026 `3d4423269651d452527f4a878cb489412792899a`. Os intervalos históricos amplos até esse marco permanecem intactos. Não são recalculados intervalos internos sobrepostos.

Os índices existentes de sources e registros são preservados. Todo ciclo novo ganha fonte e relatório, mesmo sem diferenças. Novos campos `servico_id`, `linhas_fornecimento` e `elementos_codigos` passam a ser comparados apenas nos novos intervalos. Valores nulos e vazios são diferentes; coluna ausente é reportada no diagnóstico do esquema e não vira um valor inventado. Código/tipo divergentes suspendem a comparação daquele item e são registrados no relatório. Entradas/saídas da extração são listadas separadamente, sem afirmar criação/exclusão na origem.

O catálogo novo nunca recebe valores da cópia anterior. A comparação opera sobre as cópias do catálogo publicado; perdas de informação já ocorridas na exportação/conversão não são reversíveis por este mecanismo.

## Onde consultar

Na pasta `publicacao-integrada/diferencas`:

- `bases-anteriores/<SHA256>.db.gz`: cópias compactadas usadas; SQLite temporário é removido depois de comparar. Não há expurgo automático das cópias compactadas nesta versão.
- `git/`: objetos Git e histórico para recuperação, sem credenciais copiadas.
- `intervalos/<commit-anterior>-<commit-posterior>.json`: diagnóstico e contagem de cada comparação, inclusive tentativas não publicadas.
- `confirmado.json`: último resultado realmente conferido no Pages.
- `execucoes/<ciclo-solicitado>.json`: confirmação por ciclo; inclui indicador de lote ultrapassado.

O lote preparado mantém `diferencas-recibo.json`, inclusive em falha. Os logs continuam em `logs/integrado-*.log`. `publicacao-integrada/pendente.json` identifica o lote a retomar. Para retomada sem nova extração: `uv run --offline --script rotina_integrada.py retry`.

No GitHub: `base-diffs-v1/0.json` até `7.json`; `base-diffs-v1/intervalos/`; `base-diffs-v1/processamento.json`. O checkpoint remoto representa os intervalos incluídos no commit; a confirmação de entrega fica no marcador local. `atualizacao.json.content_differences` contém a âncora e os hashes dos oito arquivos, checkpoint, relatórios novos e consumidores. Os consumidores rejeitam arquivos de outro ciclo. Falha de comparação não impede consulta administrativa.

## Testes realizados, ainda sem execução real

`python -m unittest discover -s tests -p test_incremental.py -v`: sete testes, incluindo Git local real com push, conflito e resposta perdida. Cobrem acentos, situação, vínculo do pai, identidade, nulo/vazio, ausência de coluna, ciclo vazio, preservação de registros/índices, repetição, falha antes/depois do push, marcadores após conferência, recuperação de pendentes e lote ultrapassado. Patches dos consumidores conferidos como idempotentes; renderização e síntese conferidas com acento, pai e nulo/vazio.

Ainda necessário: execução pela instalação Windows, evidência de sucesso no Pages, exemplo real nas duas ferramentas. Os avisos públicos e READMEs existentes permanecem inalterados até essa confirmação.
