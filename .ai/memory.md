# Memoria de Analise da Base CATMAS

## 2026-07-16 - Suficiencia informacional da base nova

Contexto: a ferramenta CATMAS foi atualizada com a base `catmas_itens_2 1.csv`.
A preocupacao central e evitar enriquecimento da base nova com dados da base antiga,
porque linhas de fornecimento, elementos de despesa e demais vinculos podem variar de
forma real entre extracoes.

Conclusao operacional:
- O pipeline usado nesta atualizacao nao enriquece a base nova com a base antiga.
- O fluxo copia a base nova para `data-raw/main.csv`, recria `data-raw/data.db` a partir
  desse CSV e gera `site/data.db.gz` a partir desse banco.
- `scripts/transform.py` nao le `main.enriched.csv`, banco antigo ou qualquer artefato
  de versao anterior.
- Portanto, campos como `linhasfornecimentoformatadas` e
  `elementositemdespesaformatados`, quando aparecem na ferramenta, vieram da base nova.

Deficiencias informacionais observadas na base nova:
- Registros totais na base nova: 208.663.
- Registros publicados na ferramenta: 208.510.
- Registros excluidos por falta de `codigo`: 153.
- Itens publicados sem `linhasfornecimentoformatadas`: 565
  - Materiais: 210.
  - Servicos: 355.
- Itens publicados sem `elementositemdespesaformatados`: 16
  - Materiais: 9.
  - Servicos: 7.
- Itens publicados sem `descricaoitem`: 4.
- Itens publicados com `especificacaocompleta` vazia: 123.380.

Perda informacional na transformacao atual da ferramenta:
- A base nova traz situacoes distintas:
  - `SUSPENSO_PARA_COMPRA`: 115.871.
  - `ATIVO`: 90.526.
  - `EM REVISÃO`: 1.386.
  - `INATIVO`: 629.
  - `DELETADO`: 98.
- Hoje a ferramenta transforma tudo que nao e `ATIVO` ou `SUSPENSO_PARA_COMPRA` em
  `Inativo`, misturando `EM REVISÃO`, `INATIVO` e `DELETADO`.

Pendencia da Samira:
- Verificar na base original do sistema se as ausencias de `linhasfornecimentoformatadas`
  e `elementositemdespesaformatados` sao consistentes com o cadastro real ou se indicam
  falha na producao/exportacao da nova base.
- Confirmar tambem se `EM REVISÃO`, `INATIVO` e `DELETADO` devem ser preservados como
  situacoes distintas na ferramenta, em vez de agregados como `Inativo`.
- A diretriz e que a nova base seja suficiente para nutrir todas as necessidades da
  ferramenta, sem herdar informacoes da base anterior.

## 2026-07-20 - Pendencias para a proxima atualizacao

Conclusoes adicionais:
- A ausencia de linha de fornecimento em itens antigos parece ser consistente com a
  origem, nao necessariamente falha de vinculacao da nova base.
- A perda de zeros a esquerda em `materialouservico_codigoformatado` era problema da
  transformacao da ferramenta, causado pela carga SQLite com deteccao automatica de
  tipos. O script `scripts/transform.py` foi ajustado para publicar esse codigo com 8
  digitos.

Pendencias:
- Melhorar a qualidade das descricoes na proxima atualizacao, especialmente casos com
  `descricaoitem` vazio, descricoes muito curtas e descricoes terminadas em hifen.
- Reavaliar se a ferramenta deve usar `especificacaocompleta` como exibicao principal
  quando `descricaoitem` estiver vazio ou muito generico.
