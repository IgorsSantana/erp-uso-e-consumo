# Correção dos limites por loja do Excel

O carregamento anterior separou os limites por loja, mas o catálogo integrado adicionava os produtos depois da migração e descartava os limites agregados. Isso deixava as instalações novas sem configurações. Bases com o catálogo antigo também podiam conter cópias iguais do total da rede em todas as lojas.

A revisão `limites_excel_lojas_20261019_v1` aplica os limites depois do catálogo e dos ajustes de metadados. Usa o Excel enviado, com SHA-256 `8ee4eef4e6d5adcb64f9a0d86d8a07ef6249447e4c4182fa041fae6933274d97`, e contém **629 pares produto/loja para 403 produtos**. O arquivo Excel, seus contatos, anotações e históricos não são incluídos no Git.

## Regras confirmadas e interpretação das colunas

- Nas abas com somente máximo (Limpeza, Consumo Geral, Escritório, Bobinas e Etiquetas), a quantidade de cada loja é seu máximo. O mínimo fica em **0**, conforme confirmação explícita do usuário.
- Padaria e Consumo Interno Padaria usam os mínimos/máximos expressos nas linhas, exclusivamente na **BCS**, conforme confirmação explícita do usuário. As demais lojas não recebem esses limites.
- Embalagem: a quantidade da loja é o mínimo; o máximo segue a fórmula de margem de 20%, arredondando para cima por loja. Por exemplo, 7 torna-se mínimo 7/máximo 9. O arredondamento individual pode produzir uma soma diferente do máximo agregado da rede. Ajustes manuais dos totais são atribuídos quando há apenas uma loja com quantidade; com várias lojas, a linha fica pendente quando não é possível distribuir o ajuste.
- Açougue: a quantidade da loja é o mínimo e o máximo é o dobro. Todas as colunas, inclusive FCL4, são consideradas individualmente; não se copia a fórmula agregada que omite FCL4 em algumas somas.
- Sacola Supermais não tem quantidades preenchidas por loja no arquivo enviado; seus saldos físicos não são convertidos em limites.
- Em Limpeza, o primeiro grupo de nomes de lojas contém marcações `X`. Somente o grupo de colunas numéricas depois da descrição é utilizado.
- Divergências entre um máximo agregado manual e a soma das colunas das lojas são registradas no relatório JSON. Para as abas com somente máximo, prevalecem as quantidades individuais, sem ratear o total.
- Células vazias não atribuem limites a uma loja. Produtos sem informação continuam configuráveis na interface; campos desativados mostram **Não definido**.

| Loja | Configurações na revisão |
| --- | ---: |
| BCS | 394 |
| SJN | 57 |
| MEP | 44 |
| FCL1 | 30 |
| FCL2 | 33 |
| FCL3 | 38 |
| FCL4 | 33 |

Exemplos conferidos:

| Produto | Loja | Mínimo | Máximo |
| --- | --- | ---: | ---: |
| 369842 — AGLOMAX FRANGO | BCS | 20 | 40 |
| 369842 — AGLOMAX FRANGO | SJN | 10 | 20 |
| 367054 — Limpeza | BCS | 0 | 7 |
| 367054 — Limpeza | SJN | 0 | 2 |
| 337086 — Açafrão | BCS | 1 | 2 |
| 342612 — Açúcar refinado | BCS | 90 | 120 |

## Pendências preservadas

| Código | Aba / linha | Motivo |
| --- | --- | --- |
| 366959 | Embalagem / 11 | As quantidades de várias lojas somam 7,5, mas os limites agregados foram alterados manualmente para mínimo 7 e máximo 8. A linha não foi rateada. |
| 334512 | Etiquetas / 5 | O item está marcado como eliminado e tem máximo agregado 0, mas as colunas das lojas ainda somam 82. As quantidades contraditórias não foram importadas. |

Esses itens conservam eventuais configurações anteriores. Em instalações novas ficam sem limites importados. Os três códigos com descrições conflitantes da revisão do catálogo (341499, 360618 e 377707) continuam excluídos desta revisão.

## Proteção da base existente

A revisão identifica as lojas pela sigla cadastrada, sem depender de seus IDs. Não cria lojas e não atribui informações da planilha a uma sigla desconhecida ou ambígua. Unidades incompatíveis com o cadastro ficam para revisão.

Novos limites preenchem pares ausentes ou zerados sem ajuste manual registrado. Valores positivos personalizados são preservados. Edições manuais na API, inclusive zerar ou desativar limites, são protegidas pela auditoria. Como auditorias antigas de importação CSV identificam somente a loja, configurações já existentes nessas lojas são preservadas de forma conservadora.

Cópias automáticas da migração anterior só são substituídas ou removidas quando os valores correspondem exatamente aos campos globais antigos, o horário coincide com o registro da migração e não há edição manual registrada. Remover uma cópia de uma loja sem quantidade atribuída não modifica saldo nem histórico. Produtos fora do escopo da planilha são preservados.

Toda a aplicação ocorre em uma transação com auditoria e registro em `stock_limit_releases`. Falhas revertem todos os pares e o marcador da revisão. Reiniciar a aplicação não repete a carga, não restaura configurações excluídas e não afeta lojas cadastradas posteriormente.

No banco deste ambiente, após backup consistente e simulação em uma cópia, a revisão criou 352 pares e corrigiu 277, totalizando as 629 configurações da planilha. Foram removidas 1.473 cópias globais automáticas sem atribuição à loja. Os 676 produtos, 7 lojas e os dados de saldo, histórico, pedidos, compras, contagens e usuários permaneceram idênticos. A integridade SQLite e as chaves estrangeiras foram verificadas. A suíte de 84 testes e os testes de navegador, incluindo uma instalação nova com o catálogo real, passaram.

## Reprodução e implantação

```bash
/workspace/erp-venv/bin/python -m backend.workbook_limits "USO E CONSUMO (1).xlsx" \
  --output /tmp/limites_lojas.json --report /tmp/revisao_limites.json
```

O comando somente extrai e gera arquivos para conferência, sem abrir o banco nem executar fórmulas. O artefato revisado está em `backend/data/limites_lojas_20261019.json`; o relatório de exceções, em `docs/limites_lojas_20261019.json`.

A inicialização normal aplica o artefato automaticamente depois dos produtos. Bases de teste com `SEED_CATALOG=False` permanecem sem os dados reais. Na hospedagem, implante a versão atualizada e reinicie o serviço para aplicar os limites; não é necessário reimportar produtos ou recriar o banco. A validação no ambiente de desenvolvimento não confirma o estado de outra hospedagem.
