# Retomada CATMAS — 1 de outubro de 2026

## Estado conferido no GitHub

- main: 934d99a23873e43215c7a3cddb8233dbadb83a68
- dev: cb02993838d0b7497883fe73a331c5992d95bcd1
- feat/filtro-especificacao-longa: f8c392eac1944c690d42c17b9aec60812a78065d
- gh-pages: 9e0b2530ed7c44ad1708e0c9efcd9710b4150e4a

A main contém o pipeline básico; dev contém datas; a branch de especificação longa tem o conversor com datas e especificação longa. gh-pages tem index.html, data.db.gz e arquivos de histórico. O index.html publicado consulta data_criacao, data_ultima_atualizacao, versao e especificacao_longa, além das tabelas items, hierarchy e items_fts.

Conversor incluído sem alterações: scripts/transform.py da branch de especificação longa, blob Git 82940427c87528405c8837cc021d9933578b294c. Origem: https://github.com/compras-mg/catmas/blob/f8c392eac1944c690d42c17b9aec60812a78065d/scripts/transform.py

A memória em dev confirma o fluxo sem enriquecimento de bases anteriores e registra pendências de qualidade cadastral/situação. O justfile usa sqlite-utils com inferência de tipos; esta ferramenta troca apenas a carga intermediária por TEXT para evitar perdas, mantendo a transformação existente.

## Limitação concreta

O caminho solicitado /mnt/data/itens-catmas-comdatacriacao 4.csv não existe neste ambiente macOS. Não foram encontrados CSVs no workspace Documents/Codex. O conector de leitura read_thread não está disponível nesta sessão; foi usado o preview fornecido como contexto. Não foi possível recuperar o anexo da conversa antiga. Nenhuma afirmação de validação da fixture real deve ser feita.

## Entrega

Preparador local, iniciador Windows, documentação, testes de integração e testes originais do conversor. O banco gerado atende o schema das consultas inspecionadas no frontend; teste de navegador com a fixture real ainda pendente. Sem publicação, workflow automático, alterações no GitHub, instalação de dependências, agendamento ou histórico de produção.

## Próximo passo concreto

Executar o preparador com a fixture quando ela estiver acessível, revisar relatorio.json e testar data.db.gz no buscador. Após isso, integrar em uma branch de revisão alinhada com datas e especificação longa e preparar implantação manual. Não promover a main atual diretamente à produção.


## Avanço P04 — após autorização para seguir

O preparador agora integra publicar.py e Atualizar-GitHub-Pages.cmd: validação, commit direto em gh-pages, espera do build correspondente e comparação do hash público. A implantação usa o frontend publicado atual como base; não depende de promover main ou alinhar dev para este fluxo. A fonte deve ser gh-pages/raiz pelo modo de branch, verificada a cada execução.

O conector confirmou acesso de escrita ao repositório, mas recusou leitura de /pages por limitação dos endpoints suportados. Nenhuma credencial do conector foi extraída. A aplicação local usa autenticação própria (GitHub CLI ou token), como descrito no LEIA-ME.

A fixture segue ausente. A publicação real não foi executada. A etapa anteriormente pendente de implementação do envio foi concluída e testada com respostas simuladas; falta comprovação com a fixture e ambiente reais.
