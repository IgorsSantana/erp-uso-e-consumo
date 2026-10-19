# Segunda revisão dos produtos a partir do Excel

Origem: **USO E CONSUMO (1).xlsx**, o mesmo arquivo enviado pelo usuário e identificado pelo hash registrado em `importacao_uso_consumo.json`.

A primeira importação adicionou os códigos ausentes e preservou os produtos anteriores. Nesta revisão, os dados desses cadastros antigos foram comparados aos campos válidos do Excel e corrigidos, mantendo os códigos ERP.

## Resultado no ambiente preparado

- 466 produtos válidos da planilha conferidos.
- 175 produtos ajustados; os demais já estavam alinhados.
- 410 campos corrigidos.
- 676 produtos continuam cadastrados; nenhum produto foi excluído ou duplicado.
- Saldos, limites de estoque por loja e movimentações preservados e comparados ao backup.

| Campo | Quantidade de ajustes |
| --- | ---: |
| Nome/descrição | 163 |
| Seção | 26 |
| Unidade de medida | 22 |
| Período de consumo | 24 |
| Destinação de uso | 86 |
| Marca | 24 |
| Referência | 56 |
| Custo | 9 |

Os campos vazios no Excel não apagam dados existentes. Os 207 códigos do catálogo anterior que não constam no arquivo foram conservados. Os três códigos conflitantes **360618, 341499 e 377707** permaneceram sem alterações; suas divergências estão em [importacao_uso_consumo.md](importacao_uso_consumo.md).

## Aplicação e proteção de dados

`backend/data/ajustes_catalogo_20261019.json` registra, por campo, o valor antigo e o valor confirmado na planilha. A aplicação corrige apenas o valor antigo conhecido; se o usuário já personalizou o campo, ele é preservado e registrado para revisão.

A atualização é transacional e executada uma única vez por versão, com registro em `catalog_adjustments`. Reinícios não repetem a correção nem sobrescrevem edições feitas depois dela. Produtos que tenham sido removidos não são recriados por esta revisão.

Mudanças de unidade são separadas para revisão se o produto já possuir saldo, histórico de movimentações ou limites operacionais diferentes de zero. Isso evita reinterpretar quantidades existentes sem um fator de conversão. No ambiente preparado, os 22 produtos com troca de unidade não tinham esses vínculos e puderam ser ajustados.

Mínimos e máximos continuam pertencendo a cada par produto/loja. Essa revisão não utiliza valores globais da planilha para modificar os limites das lojas.

O GitHub contém o código e os dados da revisão. Na hospedagem, a correção é aplicada quando a versão atualizada inicia; o envio ao GitHub não confirma a implantação do serviço externo.
