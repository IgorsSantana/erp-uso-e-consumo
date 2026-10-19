# Importação de USO E CONSUMO (1).xlsx

Foram conferidas as 13 abas do Excel enviado pelo usuário. O arquivo original não foi incluído no Git; o repositório guarda somente o catálogo de produtos extraído e o relatório de revisão.

- 469 códigos distintos encontrados nas abas de cadastro e nas bases auxiliares.
- 466 códigos válidos reunidos em `backend/data/catalogo_uso_consumo.csv`.
- 3 códigos com descrições conflitantes separados para conferência.
- 15 linhas identificadas como datas de históricos desconsideradas como cadastro de produto.
- Aplicação no banco deste ambiente: 280 produtos novos e 186 cadastros existentes preservados. Total após a importação: 676 produtos, incluindo o catálogo anterior.
- Saldos físicos e movimentações existentes preservados. Um backup SQLite consistente foi verificado antes da importação.

As abas visíveis têm prioridade para descrição e detalhes do produto. As bases ocultas complementam códigos e campos ausentes, sem substituir o cadastro principal. Foram aproveitadas somente as colunas de produto suportadas pelo ERP; valores de custos e limites são incluídos quando informados e válidos. Fórmulas não foram executadas. Contatos, instruções em anotações e históricos não são importados como dados operacionais.

## Revisão posterior dos cadastros antigos

Após a separação dos limites por loja, os dados foram conferidos novamente com o Excel. Foram ajustados 175 produtos e 410 campos que ainda tinham valores do catálogo anterior, sem alterar saldos ou mínimos/máximos por loja. Consulte [ajuste_catalogo_20261019.md](ajuste_catalogo_20261019.md) para os resultados e as regras de proteção das edições do usuário.

## Códigos que precisam de revisão

| Código | Origem | Descrição no Excel |
| --- | --- | --- |
| 360618 | AÇOUGUE, linha 7 | CALDÃO DE GALINHA 1KG |
| 360618 | PADARIA, linha 19 | CALDO EM PÓ GALINHA MAGGI 1,01KG (KNNOR) |
| 341499 | AÇOUGUE, linha 5 | AJINOMOTO KG |
| 341499 | PADARIA, linha 188 | TEMPERO ANJINOMOTO 2KG |
| 377707 | EMBALAGEM, linha 38 | EMBALAGEM DELPAK K121 NATURAL TP FILME C 200 |
| 377707 | EMBALAGEM, linha 40 | EMBALAGEM DELPAK K151 NATURAL TP FILME C 200 |

Esses três códigos não receberam alterações provenientes do Excel. Os cadastros que já existiam continuam preservados. Confirme qual descrição e apresentação correspondem ao código ERP antes de editar ou importar esses itens.

## Reprodução e rastreabilidade

`importacao_uso_consumo.json` contém o hash SHA-256 do arquivo original, contagens por aba, divergências e regras aplicadas. O catálogo CSV passa pela mesma validação da importação do aplicativo. Cada revisão é registrada no banco por hash e adicionada apenas uma vez durante a inicialização; campos existentes e estoques não são sobrescritos.

O catálogo pode ser aplicado no ambiente publicado pelo próximo início da versão atualizada. O envio ao GitHub não comprova que a hospedagem já implantou essa versão ou reiniciou o serviço.
