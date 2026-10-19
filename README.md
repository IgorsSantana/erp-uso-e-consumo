# ERP de Uso e Consumo

Aplicação web em português para controlar materiais de uso e consumo em várias lojas: cadastro de produtos, estoque por unidade, movimentações, pedidos internos, fornecedores, cotações e compras. O backend usa Flask e SQLite, e serve a interface no mesmo endereço. Não depende do antigo servidor TiDB para iniciar.

## Executar localmente

Requisitos: Python 3.12 ou superior, `venv`, espaço gravável para o banco e acesso ao PyPI para instalar as dependências. Execute os comandos na raiz do repositório existente. Cada tarefa na nuvem já tem um ambiente isolado; não é necessário criar outro checkout ou Git worktree.

```bash
python3 -m venv /workspace/erp-venv
/workspace/erp-venv/bin/python -m pip install -r backend/requirements.txt
export ERP_DATA_DIR=/workspace/erp-data
/workspace/erp-venv/bin/python -m backend.init_db
/workspace/erp-venv/bin/gunicorn backend.app:app --bind 127.0.0.1:8000 --workers 1 --threads 4 --timeout 60 --no-control-socket
```

Abra `http://127.0.0.1:8000`. No onboarding na nuvem, a validação ocorre por requisições locais; a interface de onboarding não oferece preview web. O banco e suas tabelas são criados automaticamente. O catálogo revisado do Excel enviado acompanha a aplicação e adiciona os produtos ausentes na primeira inicialização dessa versão. Lojas e seções iniciais são referências; confira os cadastros e registre os saldos reais da empresa.

Na primeira abertura, cadastre seu nome, usuário e uma senha de pelo menos 10 caracteres. Não há conta ou senha padrão. Proteja o acesso ao endereço até concluir esse cadastro. Administradores adicionais são gerenciados na área de usuários. O botão **Minha senha** permite que cada pessoa altere sua própria senha, encerrando as outras sessões. Sair da conta invalida a sessão no servidor.

Também é possível criar somente o primeiro administrador pelo terminal, com a senha solicitada sem exibição:

```bash
/workspace/erp-venv/bin/python -m backend.create_admin --nome "Seu nome" --username seu.usuario
```

Essa ferramenta utiliza a mesma validação da configuração inicial e não substitui nem redefine usuários existentes.

## Fluxo de trabalho

1. Cadastre ou revise lojas, seções, produtos e fornecedores com os dados reais da operação.
2. Registre entradas reais por loja e configure os limites de reposição dos produtos. O cadastro de um produto não cria saldo disponível.
3. Acompanhe saldos, itens abaixo do mínimo e histórico de movimentos. Registre consumo e transferências pelas operações correspondentes.
4. Crie pedidos internos com quantidades e loja de destino; acompanhe o atendimento pelo fluxo de status do sistema.
5. Abra cotações, selecione produtos e fornecedores e compartilhe os links de resposta. Compare as propostas, encerre a cotação e gere compras com a loja de recebimento.
6. Acompanhe as compras por fornecedor e registre o recebimento real para adicionar os materiais ao estoque. Compras diretas também podem ser cadastradas sem cotação.
7. Consulte relatórios, exportações e auditoria para conferir a operação.

Os links de fornecedor dão acesso à cotação específica. Compartilhe-os apenas com o fornecedor correspondente. O sistema não envia e-mails automaticamente.

### Perfis e regras de operação

| Perfil | Acesso |
| --- | --- |
| Operacional | Consulta painéis, catálogos, estoque e relatórios; cria pedidos internos e pode cancelar seus próprios pedidos pendentes. |
| Gestor | Também gerencia cadastros, movimentos, contagens de inventário, aprovação e atendimento de pedidos, cotações e compras. |
| Admin | Todas as operações anteriores, além de usuários, perfis e consulta à auditoria. |

Os perfis não restringem o usuário a uma única loja. Atribua contas apenas a pessoas autorizadas a consultar a operação das unidades.

Pedidos seguem `Pendente → Aprovado → Atendido`, com cancelamento permitido antes do atendimento. Ao atender, o sistema baixa a quantidade na origem e credita o destino na mesma transação. Falta de saldo cancela a operação inteira; o status impede atender o mesmo pedido duas vezes. O atendimento representa a transferência interna completa, sem uma etapa separada de confirmação de entrega.

Entradas, saídas e transferências exigem motivo. Transferências usam lojas distintas e não permitem saldo negativo. Contagens registram a quantidade física por produto, preservam o histórico e geram o ajuste correspondente. Quantidades aceitam até três casas decimais; custo de cadastro, até duas; propostas de fornecedor, até quatro. Os limites mínimo e máximo pertencem ao par produto/loja. Cada loja pode ter valores diferentes para o mesmo produto, sem afetar as outras unidades. Configure em **Produtos → Limites por loja** ou **Estoque e movimentos → Limites**. Máximo zero significa sem teto; desmarcar **Usar limites** remove somente a configuração daquela loja. Lojas novas começam sem limites configurados. Alertas e relatórios usam os valores da loja correspondente. Na migração, os limites antigos são copiados uma única vez para as lojas existentes como ponto de partida independente, preservando os saldos e o histórico.

Cotações abertas aceitam a atualização da proposta pelo mesmo link até seu prazo. O fornecedor responde a todos os itens ou informa indisponibilidade. O encerramento exige uma proposta válida para cada item e seleciona o menor preço unitário, desempatando por prazo de entrega e depois identificador do fornecedor. Após o encerramento, gere as compras a partir dos vencedores, informando a loja de recebimento; os itens são agrupados por fornecedor. A geração da compra não altera o estoque. Confirme o recebimento quando os materiais chegarem para registrar as entradas, sem repetir o recebimento da mesma compra. Também é possível cadastrar uma compra diretamente.

Responder ou encerrar uma cotação não altera o custo do catálogo. O recebimento de compra atualiza o custo unitário do produto pelo preço da última entrada de compra, arredondado para duas casas decimais; a avaliação do estoque utiliza esse custo atual. Não há cálculo de custo médio ponderado ou escrituração financeira.

Relatórios CSV de estoque, movimentações, pedidos e compras usam separador `;`. O indicador de consumo usa o custo registrado no momento de cada saída, preservando os valores históricos quando o custo do cadastro muda. O TXT de pedido usa linhas posicionais com 13 dígitos de código, 6 de quantidade inteira e 6 de custo em centavos. Esse formato exige código numérico de até 13 dígitos e não aceita quantidade fracionada; a exportação sinaliza itens incompatíveis.

## Importar produtos de uma planilha

Em **Produtos → Importar planilha**, cole o link da aba do Google Sheets ou selecione diretamente um arquivo Excel `.xlsx` ou o CSV exportado em **Arquivo → Fazer download → Valores separados por vírgulas (.csv)**. A leitura pelo link exige que a hospedagem possa acessar `docs.google.com` e que o documento permita a leitura. Se a rede ou o compartilhamento impedir o acesso, use o arquivo CSV; a aplicação não solicita nem armazena credenciais do Google.

O Excel é lido sem executar fórmulas nem carregar links externos. Todas as abas com código e descrição são verificadas; as abas visíveis têm prioridade sobre as bases ocultas. Datas, históricos sem código e anotações não são tratados como produtos. Se um código tiver descrições diferentes nas abas prioritárias, ele é separado para revisão e exibido na prévia, preservando seu cadastro atual.

A etapa de conferência reconhece colunas em português e permite associá-las manualmente. Código e descrição são obrigatórios; seção, unidade, custo, referência, marca e destinação são opcionais. Se houver mínimos/máximos, escolha a loja de destino dos limites ou marque para não importá-los; eles nunca são distribuídos automaticamente para todas as lojas. São aceitos CSV com vírgula, ponto e vírgula ou tabulação, até 1,5 MB e 5.000 produtos. Valores como `R$ 1.234,56` são reconhecidos e os zeros à esquerda nos códigos são mantidos.

A prévia informa novos e existentes, erros, colunas ignoradas e repetições. Duplicidades com informações conflitantes impedem a importação inteira até sua correção. Por padrão, os produtos existentes são preservados; marque **Atualizar os produtos existentes** somente quando quiser atualizar as colunas preenchidas. Campos vazios não apagam dados anteriores. A confirmação é transacional e registrada na auditoria.

**Colunas de saldo físico não são importadas por esse fluxo.** A planilha pode fornecer níveis mínimo e máximo para uma loja escolhida na conferência. Configurações existentes dessa loja são preservadas, salvo quando a atualização de existentes for autorizada. As outras lojas não são alteradas. Os saldos disponíveis continuam sendo mantidos por entradas, compras e inventários. A importação não cria movimentações fictícias.

## Catálogo revisado do Excel enviado

O arquivo **USO E CONSUMO (1).xlsx** foi conferido em 13 abas. O catálogo em `backend/data/catalogo_uso_consumo.csv` reúne 466 códigos válidos, sem saldos físicos ou dados de contato. Os mínimos e máximos desse arquivo são referências para importação com loja escolhida; o catálogo integrado não cria novos limites globais nem copia esses valores automaticamente para lojas novas. O relatório [docs/importacao_uso_consumo.md](docs/importacao_uso_consumo.md) registra as regras e os 3 códigos conflitantes que precisam de revisão.

Na inicialização, a aplicação aplica cada revisão do catálogo uma única vez, identificada pelo SHA-256 do CSV. Ela adiciona produtos ausentes, preserva os cadastros existentes e não altera saldos, custos cadastrados ou movimentações anteriores. Reinícios não repetem a importação nem restauram produtos excluídos após a aplicação da revisão. Novas instalações recebem os 466 produtos revisados; instalações com catálogos anteriores conservam também seus produtos existentes.

Para conferir novamente um Excel e gerar outro catálogo, sem alterar o banco:

```bash
/workspace/erp-venv/bin/python -m backend.import_workbook arquivo.xlsx --output /tmp/catalogo.csv --report /tmp/revisao.json
```

A geração não aplica dados ao app. Para outro arquivo, prefira **Produtos → Importar planilha** e confira a prévia antes de confirmar. `SEED_CATALOG=False` nas configurações da fábrica de aplicação desativa o catálogo integrado em testes; a suíte padrão usa bancos temporários sem carregar dados reais.

## Catálogo antigo, sem saldos históricos

O repositório contém uma lista de produtos no literal `raw_data` de `backend/import_data.py`. O importador novo lê somente esse texto pela árvore sintática; não executa o arquivo legado, seus imports ou suas conexões.

```bash
/workspace/erp-venv/bin/python -m backend.import_catalog --dry-run
/workspace/erp-venv/bin/python -m backend.import_catalog
```

A simulação não abre o banco. A importação adiciona somente produtos e seções ausentes, preserva cadastros existentes e ignora códigos repetidos com informações conflitantes. Não importa estoque, custo, pedidos, contas ou credenciais. A origem padrão possui 396 produtos sem ambiguidade e 8 códigos conflitantes descartados; revise os descartes na origem antes de cadastrar esses itens manualmente. A opção `--source caminho/arquivo.py` permite indicar outro arquivo com o mesmo formato.

Os antigos `backend/import_*.py`, exceto `import_catalog.py`, os arquivos `database_schema.sql` e `schema_cotacoes.sql` e o exportador Python legado pertencem à implementação MySQL/TiDB anterior. Não os execute no ambiente novo. Dados do TiDB não foram migrados: a recuperação de histórico exige exportação autorizada, conferência e uma migração separada. Rotacione as credenciais do banco antigo que tenham sido expostas no histórico do repositório.

## Configuração

Configure as variáveis no ambiente do processo; o serviço não carrega arquivos `.env` automaticamente. Nunca salve segredos no Git.

| Variável | Uso |
| --- | --- |
| `ERP_DATA_DIR` | Diretório persistente e gravável do banco. Na nuvem, use `/workspace/erp-data`; no Render, `/var/data`. |
| `ERP_DATABASE` | Caminho explícito do arquivo SQLite, quando for preciso substituir o caminho calculado por `ERP_DATA_DIR`. |
| `ERP_ENV` | Use `production` em produção. |
| `ERP_SECRET_KEY` | Segredo estável e aleatório para assinar sessões; obrigatório em produção. Alterá-lo encerra sessões existentes. |
| `ERP_COOKIE_SECURE` | Use `1` quando o endereço público utiliza HTTPS. Para desenvolvimento local em HTTP, deixe desativado. |
| `ERP_TIMEZONE` | Fuso para prazos e períodos de operação; padrão `America/Sao_Paulo`. Use um identificador IANA válido. |
| `ERP_TRUST_PROXY` | Use `1` somente atrás de um proxy confiável que defina `X-Forwarded-Proto`, como o Render. Permite reconhecer o HTTPS original sem confiar no host encaminhado. |

Defina um segredo forte nas configurações seguras da hospedagem. O `render.yaml` solicita sua geração automática. Conserve o mesmo segredo entre reinícios e mantenha o banco fora de pastas temporárias e do checkout versionado.

## Publicar no Render

O Blueprint `render.yaml` define um serviço Python no plano Starter, com disco persistente montado em `/var/data`, HTTPS na borda, reconhecimento do proxy confiável, fuso `America/Sao_Paulo`, chave de sessão gerada e verificação de saúde em `/api/health`. O plano e o disco têm custos conforme o provedor. Revise os recursos antes de aplicar o Blueprint.

O processo usa `gunicorn backend.app:app`, escuta em `$PORT` e tem um worker com quatro threads. O banco SQLite usa WAL e atende este serviço em um único host com armazenamento persistente. Não escale para múltiplas instâncias com bancos independentes nem coloque o arquivo em um compartilhamento de rede. Para alta disponibilidade ou maior concorrência de gravação, planeje a migração para um banco servidor.

A preparação do código não publica o serviço nem transfere dados do banco antigo.

## Backup e restauração

Use a API de backup do SQLite, que produz uma cópia consistente mesmo com o aplicativo aberto. Não copie apenas o arquivo `.sqlite3` em uso: transações recentes podem estar no WAL. Execute com o mesmo `ERP_DATA_DIR` ou `ERP_DATABASE` utilizado pelo serviço:

```bash
export ERP_BACKUP_DIR=/workspace/backups
/workspace/erp-venv/bin/python - <<'PY'
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

source_path = Path(os.environ.get("ERP_DATABASE", str(Path(os.environ.get("ERP_DATA_DIR", "/workspace/erp-data")) / "erp.sqlite3")))
if not source_path.is_file():
    raise SystemExit(f"Banco não encontrado: {source_path}")
backup_dir = Path(os.environ.get("ERP_BACKUP_DIR", "/workspace/backups"))
backup_dir.mkdir(parents=True, exist_ok=True)
backup_path = backup_dir / ("erp-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".sqlite3")
with sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True) as source:
    with sqlite3.connect(backup_path) as target:
        source.backup(target)
        if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SystemExit("Backup criado, mas a verificação de integridade falhou.")
print(f"Backup verificado: {backup_path}")
PY
```

No Render, ajuste `ERP_BACKUP_DIR` para um diretório gravável, como `/var/data/backups`. Essa variável é usada somente pelo exemplo de backup. Guarde cópias protegidas fora do host e teste a restauração periodicamente. Para restaurar, pare o serviço, preserve o banco atual, valide o backup com `PRAGMA quick_check`, restaure-o para um caminho novo e configure `ERP_DATABASE` para esse arquivo. Reinicie e confira os dados antes de descartar qualquer cópia. Esse procedimento evita misturar arquivos WAL de bancos diferentes.

## Verificações e diagnóstico

A suíte de testes usa bancos SQLite temporários e não precisa de serviços externos:

```bash
/workspace/erp-venv/bin/python -m unittest discover -s tests -v
```

Há também um teste opcional de navegador em `tests/browser_smoke.py`, que exige o pacote de desenvolvimento `playwright` e um Chromium instalado. Execute `python tests/browser_smoke.py` no ambiente que os fornece; use `CHROMIUM_EXECUTABLE` se o executável estiver fora de `/usr/bin/chromium`. O teste abre um serviço temporário e não cadastra dados de demonstração no banco da aplicação.

A validação básica inclui integridade SQLite, autenticação, permissões, regras de estoque e transações dos fluxos de pedido e cotação. O endpoint de saúde é útil para verificar se o serviço está ativo:

```bash
curl --fail http://127.0.0.1:8000/api/health
/workspace/erp-venv/bin/python -m backend.init_db
```

Se o processo não iniciar, confira o diretório gravável e, em produção, `ERP_SECRET_KEY`. Se o login funciona em HTTP local, mas a sessão não persiste, confira se `ERP_COOKIE_SECURE=1` foi ativado indevidamente. Se aparecer banco vazio, confirme que serviço e ferramentas usam o mesmo caminho persistente.

Este sistema cobre gestão interna de materiais. Não emite documentos fiscais, não substitui escrituração contábil e não integra automaticamente fornecedores, bancos ou o ERP corporativo. Antes do uso real, valide os cadastros, os responsáveis, os limites e o processo de backup da empresa.
