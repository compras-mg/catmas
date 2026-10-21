# Comparação do conteúdo das solicitações

A seção Comparar versões inclui uma síntese Antes → Analisado, os valores completos e os identificadores de origem, as justificativas e os eventos da mesma solicitação que registram aprovação com comunicação de sucesso. Usa o banco existente, sem nova extração ou migração.

## Fontes e limites

- `scripts/build_history.py` já mapeia conteudo 1/2/3 para Antes/Solicitado/Analisado. A investigação no Impala corroborou esse mapeamento nos exemplos, mas não obteve documentação formal dos enums.
- `07alteracao_caracteristica.csv` já alimenta snapshot_components. O vínculo é alteracao_id → snapshot_id; a comparação usa component_key, derivado da característica, nunca o ID da linha do componente entre etapas.
- Eventos de solicitação são ligados por request_id; não há vínculo atribuído aos eventos do item por horário.
- A síntese só compara campos com valores presentes em ambos os estados. Nulos não são tratados como valores anteriores vazios. Inclusões/exclusões não são inferidas de registros ausentes.
- Duplicidade de estados por etapa ou componentes por chave/etapa suspende a comparação, em vez de sobrescrever valores silenciosamente.
- Aprovação/comunicação é evidência administrativa separada da diferença de conteúdo. Não é a data exata comprovada da gravação; a seção conserva o horário bruto e informa fuso desconhecido. Aprovações parciais não recebem a classificação de aprovação integral por este detector.
- Rótulos das características vêm dos cadastros de referência; não são apresentados como nomes históricos comprovados. A síntese compara valores, situação e ordem, não diferenças de rótulo.
- A ausência do estado Analisado não é interpretada como prova de ausência de análise.

## Evidência da investigação

Solicitação 26978: característica 104169, capacidade 95 ML → 115 ML. Solicitação 27019: característica 38647, retirada de 43 ML. Solicitação 27039: características 124263 (20 KG → 25 KG), 124265 (retirada da exigência antiderrapante) e 124267 (EM PARADE → EM PAREDE). Estados 2 e 3 coincidem nesses componentes. Eventos 51056, 51258 e 51259 registram aprovação com comunicação de sucesso nas respectivas solicitações.

Item de código 000000248, ID 15, pai 9881: nenhum estado de solicitação foi encontrado. Master e staging retornaram apenas item versão 27, texto 1304 versão 1 e valores atuais das características. Retorno 134514 não oferece conteúdo anterior. A interface mostra conteúdo anterior não recuperado. Isso não prova inexistência de histórico na origem.

## Validação

Execute `node tests/history-content-comparison.test.cjs`. O teste usa as funções da página e verifica cinco diferenças reais, exclusão de nulos, identificação da evidência administrativa, escape de HTML, duplicidades e ausência de histórico. Não substitui validação visual com o banco completo. Nenhuma mudança no painel por período ou publicação em gh-pages é feita por esta alteração.
