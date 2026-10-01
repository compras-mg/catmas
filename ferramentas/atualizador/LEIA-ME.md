# CATMAS — atualização do GitHub Pages (P04)

## Acionar a atualização

No Windows, extraia o ZIP e abra **Atualizar-GitHub-Pages.cmd**. Informe o caminho do CSV extraído pelo KNIME. A ferramenta valida o CSV, gera a base, envia ao repositório compras-mg/catmas e aguarda a publicação no GitHub Pages. Não é necessário copiar arquivos nem criar commits manualmente.

Requisitos: Python 3.9 ou superior com SQLite FTS5, acesso à internet e autenticação GitHub com acesso ao repositório. Nenhum pacote Python externo é necessário. Python, credenciais e permissões não são instalados/criados automaticamente.

A autenticação reutiliza o GitHub CLI, se instalado e conectado (`gh auth login`), ou lê CATMAS_GITHUB_TOKEN/GH_TOKEN. Caso contrário, pede um token com entrada oculta, sem salvá-lo. Não cole credenciais no chat. Para token de acesso com permissões específicas, selecione apenas compras-mg/catmas, **Contents: leitura e escrita** e **Pages: leitura**. Autorizações da organização também podem ser necessárias. A conexão GitHub desta conversa não fornece automaticamente credenciais ao programa executado no seu computador.

A fonte do GitHub Pages precisa estar configurada como **Deploy from a branch → gh-pages → /(root)**. A ferramenta confere isso antes de escrever e interrompe se a configuração for diferente; não muda as configurações do repositório. Essa configuração ainda não foi confirmada nesta sessão porque o conector disponível não permite ler o endpoint Pages.

Também pode executar:

```text
python publicar.py "itens-catmas-comdatacriacao 4.csv"
```

A pasta de resultados é criada automaticamente, com nome único. Para escolher a pasta, use `--saida "resultados/minha-atualizacao"`; precisa ser uma pasta nova. UTF-8 com ou sem BOM é o padrão; `--encoding cp1252` e `--delimiter ";"` estão disponíveis para exportações que usem outro formato.

## O que acontece ao acionar

1. Copia o CSV exatamente para data-raw/main.csv em uma pasta isolada e verifica que ele não mudou durante a cópia.
2. Valida as colunas, códigos, IDs, booleanos, datas e estrutura das linhas.
3. Gera data-raw/data.db, site/data.db e site/data.db.gz usando o conversor do projeto com datas e especificação longa.
4. Confere SQLite, FTS5, contagens e igualdade do gzip com o banco validado.
5. Confere a fonte do Pages e o frontend atual de gh-pages.
6. Cria um commit em gh-pages com data.db.gz e atualizacao.json. Usa a árvore atual como base, preservando index.html, histórico e demais arquivos. Não modifica main ou dev nem envia o CSV bruto ao site público.
7. Aguarda o build do commit correto e compara o hash do banco servido pelo site com o banco enviado. Só informa **publicado** quando ambos conferem.

O fluxo continua sendo CSV do KNIME → data-raw/main.csv → SQLite → site/data.db.gz → GitHub Pages. Na branch gh-pages o arquivo fica na raiz, como o site atual espera. O CSV e o SQLite intermediário ficam na pasta local para auditoria/reprodução; somente o banco compactado e metadados sem caminhos locais são publicados.

O commit preserva data de criação e especificação longa. A atualização nunca preenche dados a partir de extrações antigas. Códigos de item têm nove dígitos; códigos de material têm oito. A carga intermediária usa TEXT para evitar inferência destrutiva de códigos.

O envio não usa force. Se outra atualização avançar a branch durante a execução, a ferramenta interrompe em vez de sobrescrevê-la. Se o banco já for igual, não cria outro commit e verifica a versão existente.

## Relatórios e resultado

Cada execução conserva CSV, bancos e relatorio.json. O arquivo publicacao.json registra commit anterior, novo commit, hashes, URL e etapa alcançada. O token nunca vai para esses arquivos.

Código de saída 0: publicação confirmada. Código 2: erro ou bloqueio. Código 3: envio realizado, mas confirmação pendente após o limite de espera (dez minutos por padrão).

Se houver timeout, falha de rede ou interrupção depois do envio, **não suponha que nada foi publicado**. Consulte publicacao.json e retome só a verificação:

```text
python publicar.py --verificar "resultados/pasta-da-execucao"
```

Essa opção não cria commits nem repete o envio. `--timeout 1200` aumenta o limite para vinte minutos. Em caso de falha de build, o registro mantém o commit enviado; a ferramenta não reverte automaticamente. O commit anterior registrado permite recuperação por um novo commit revisado, sem apagar o histórico Git.

Validar-e-preparar.cmd e atualizar.py continuam disponíveis para testar sem publicação.

## Contrato e alertas

Colunas obrigatórias estão em REQUIRED, no arquivo atualizar.py. Nomes são normalizados para minúsculas; dataCriacao/dataUltimaAtualizacao são aceitos. Colunas ausentes não são inventadas.

Bloqueios incluem: schema ausente/duplicado, campos desalinhados, códigos inválidos ou acima da largura, IDs/versões inválidos, códigos/IDs publicados duplicados, datas preenchidas inválidas, booleanos fora de true/false, tipo/grupo/classe vazios e base sem itens publicáveis.

Datas preenchidas precisam estar em ISO, por exemplo 2024-04-05T12:00:00Z. Datas vazias, vínculos/descrições vazios, exclusões de itens sem código e situações agregadas como Inativo aparecem como alertas. O conversor existente usa data de criação como fallback da atualização vazia. A ferramenta não presume fuso horário de datas sem fuso; o site exibe horários em America/Sao_Paulo.

A agregação EM REVISÃO/DELETADO como Inativo segue a transformação existente; a decisão sobre distinguir essas situações continua pendente. Histórico não integra esta atualização.

## Validação desta entrega

Testes automatizados locais usam dados sintéticos e respostas simuladas do GitHub. Cobrem geração/busca, datas, códigos, publicação, concorrência, falha de Pages, arquivo alterado, cache desatualizado, ausência de mudanças e retomada da verificação. Execute:

```text
python -m unittest discover -s tests -v
```

A fixture /mnt/data/itens-catmas-comdatacriacao 4.csv permanece inacessível nesta sessão. Não houve publicação de uma base real nem teste de implantação ao vivo. O iniciador .cmd não foi executado em Windows. Esses limites não devem ser confundidos com publicação concluída.

Referências técnicas: [API Pages](https://docs.github.com/en/rest/pages/pages), [referências Git](https://docs.github.com/en/rest/git/refs), [blobs Git](https://docs.github.com/en/rest/git/blobs).
