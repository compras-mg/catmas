# Complementacao da especificacao no buscador CATMAS

## O que muda

O conversor preserva o texto original de `complementacaoespecificacao` em
`items.complementacao_especificacao` e inclui o texto no indice FTS5. A busca
geral passa a consultar tambem esse campo. O indicador `especificacao_longa`
continua separado e segue a mesma regra anterior. Arquivos anexos de
especificacao longa nao sao baixados nem indexados por esta alteracao.

A pagina exibe uma coluna Complementacao da especificacao, disponivel no
seletor de colunas, e o mesmo texto nos resultados em celular. O texto pode
ser expandido e vem aberto quando ha uma busca. HTML armazenado na base e
exibido como texto, sem execucao. Cargas antigas continuam funcionando com
aviso de que ainda nao contem complementos; ausencia da coluna nao e
confundida com um campo vazio no cadastro.

## Estado e origem

Implementacao preparada; ainda nao ativada em producao. A pagina parte da
publicacao `94f8dfa111c1e171aa0d90d03fe955830e781989`, para preservar as mudancas
que ja estavam publicadas. O conversor parte de
`f8c392eac1944c690d42c17b9aec60812a78065d`. A branch usa como base a rotina
integrada de `feat/diferencas-incrementais`.

O banco SQLite publicado atualmente nao contem o texto do complemento.
Nao ha como preencher essa coluna com fidelidade a partir dele. E necessario
reconverter o CSV original na maquina Windows. Nao usar snapshots do historico
para preencher cadastros atuais.

## Ativacao

1. Baixar os arquivos desta branch mantendo as pastas `scripts` e `deployment`.
2. Na maquina que executa as cargas, usar Python 3.11 ou superior:

   `python deployment/windows/instalar_complemento.py --target "PASTA_DA_ROTINA_CATMAS" --revision SHA_COMPLETO_DESTA_VERSAO`

   O instalador verifica o conversor original e os trechos do publicador,
   adquire a mesma trava da rotina integrada, recusa lote pendente e faz backup.
   Atualiza apenas `conversor_original.py` e a identificacao/validacao do conversor
   em `publicar_catmas.py`. Nao altera consulta SQL, credenciais ou agendamentos.
3. Preparar um lote usando `rotina_integrada.py convert` quando houver extracoes
   recentes e correspondentes, ou `prepare` para fazer novas extracoes.
   Ambos preparam sem publicar. Conferir contagem, integridade, tamanho abaixo
   de 100 MB e correspondencia dos complementos com o CSV original.
4. Publicar o lote pela rotina integrada e publicar `site/index.html` como
   `index.html` em `gh-pages`, preservando outros arquivos e mudancas concorrentes.
   A pagina suporta a base antiga e a nova; a pagina antiga tambem pode consultar
   a nova base. Nao usar o banco antigo versionado em `site/data.db.gz` nesta branch.
5. Conferir na ferramenta um item cujo termo exista apenas no complemento e
   verificar a data da carga. As cargas seguintes passam pelo conversor novo.

Para reverter a instalacao local, com a rotina parada e sem publicacao pendente,
restaurar os dois arquivos do backup. A pagina continua compativel com o esquema
antigo. Nao modificar um lote que ja foi preparado ou esta pendente de envio.

## Validacao executada

`python -m unittest discover -s tests -p test_complement.py`

`node tests/complement.test.cjs`

Testes com material e servico, complemento nulo/vazio, preservacao literal,
busca por palavra exclusiva do complemento, acentos, busca anterior e indicador
de especificacao longa. Verificacao de escape HTML e estados de exibicao.
Validacao de layout em navegador e da primeira carga completa permanecem
pendentes; nenhum resultado sintetico foi publicado como dado real.
