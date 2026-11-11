# Correção das variáveis Impala — 11/11/2026

A execução agendada de 30/10/2026 às 12h30 interrompeu o ciclo porque
`extrair_catmas.py` procurava `impala-user` nas variáveis persistentes do Windows.
Os nomes usados na instalação são `impala_user` e `impala_user_senha`.

## Correção

`corrigir_variaveis_impala.ps1` aplica nos dois extratores instalados:

| Nome antigo | Nome correto |
| --- | --- |
| impala-user | impala_user |
| impala-password | impala_user_senha |

Execute no PowerShell, com a rotina parada:

```powershell
.\corrigir_variaveis_impala.ps1
```

Os caminhos padrão são as pastas CATMAS-Extracao-Python-v3 e
CATMAS-Historico-Python-v1 dentro de Documents do usuário.
Os parâmetros `-Catalogo` e `-Historico` permitem indicar os arquivos completos.

O script verifica a presença das variáveis persistentes sem imprimir valores,
prepara ambos os arquivos antes de escrever, cria backups, verifica a gravação
e restaura os backups em caso de falha na escrita. Não altera variáveis,
credenciais, consultas, agendamentos ou dados publicados.
A substituição também atualiza os nomes nas mensagens de diagnóstico.

Esta branch contém o pacote de implantação, mas não os arquivos completos
`extrair_catmas.py` e `historico_catmas.py` da instalação. Por isso a correção
é entregue como patch aplicável aos arquivos existentes, sem reconstruir seus
conteúdos. Ela deve ser preservada ao reinstalar os extratores.

## Validação real informada pelo operador

A mesma substituição, com backups e conferência, foi aplicada aos dois
extratores no Windows. Em 11/11/2026, a execução direta de
`uv run --offline --script rotina_integrada.py all --scheduled` retornou:

```text
SUCESSO: ciclo servido d83966b88fae4f2686e965e3f89d18a3; comparacoes conferidas ate 1712b5c3a4f2e521cd5c5f892fbd5614d62f994c; ciclo solicitado d83966b88fae4f2686e965e3f89d18a3.
```

Log: `integrado-20261111-160622-09387e.log`.
O ciclo abrange Buscador, Histórico e comparações usadas pelo Rastreador.
O script versionado encapsula o bloco aplicado, acrescentando parâmetros de
caminho e omitindo a consulta final ao Agendador; não foi executado novamente
no Windows a partir do repositório.

O disparo automático seguinte ainda precisa ser observado.
A tarefa separada do Termômetro também apresentou erro e permanece pendente
de diagnóstico; esta correção não declara seu problema resolvido.
