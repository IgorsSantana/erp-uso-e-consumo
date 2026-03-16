/**
 * estoque.js - Matriz Global de Estoque com Visão Resumida
 */

window.Estoque = {
    dadosGlobais: [],

    init() {
        this.renderizarMatrizCompleta();
        this.carregarComboLoja();
    },

    carregarComboLoja() {
        const lojas = window.Store.getLojas();
        const selectLoja = document.getElementById('matriz-loja-pedido');
        if (selectLoja) {
            lojas.forEach(l => {
                selectLoja.innerHTML += `<option value="${l.id}">${l.nome}</option>`;
            });
        }
    },

    carregarDados() {
        this.dadosGlobais = window.Store.getEstoqueGlobal();
    },

    renderizarMatrizCompleta() {
        this.carregarDados();
        this.renderCabecalho();
        this.renderLinhas(this.dadosGlobais);
    },

    filtrarMatriz() {
        const termo = document.getElementById('search-estoque').value.toLowerCase();
        const secao = document.getElementById('filtro-secao-estoque').value;

        let filtrados = this.dadosGlobais;

        if (secao) {
            filtrados = filtrados.filter(item => item.secao === secao);
        }

        if (termo) {
            filtrados = filtrados.filter(item =>
                item.nome.toLowerCase().includes(termo) ||
                item.id.includes(termo)
            );
        }

        this.renderLinhas(filtrados);
    },

    renderCabecalho() {
        const trHeader = document.getElementById('matriz-header-row');
        trHeader.innerHTML = `
            <th class="col-produto sticky-col">Produto (Cód / Desc)</th>
            <th class="col-ref" style="min-width: 140px;">Referência / Uso</th>
            <th class="text-center col-total" title="Estoque Físico Total (Matriz)">Estoque Total</th>
        `;

        const lojas = window.Store.getLojas();
        lojas.forEach(l => {
            trHeader.innerHTML += `<th class="text-center col-loja">${l.sigla}</th>`;
        });

        // Add final column for Orders
        trHeader.innerHTML += `<th class="text-center" style="min-width: 100px; position: sticky; right: 0; background: var(--bg); z-index: 10; border-left: 1px solid var(--border);">Fazer Pedido</th>`;
    },

    renderLinhas(itens) {
        const tbody = document.querySelector('#tabela-matriz tbody');
        tbody.innerHTML = '';

        if (itens.length === 0) {
            const numLojas = window.Store.getLojas().length;
            tbody.innerHTML = `<tr>
                <td colspan="${numLojas + 4}" class="empty-state">
                    <p>Nenhum produto atende a esse filtro.</p>
                </td>
            </tr>`;
            return;
        }

        const lojas = window.Store.getLojas();

        itens.forEach(item => {
            let badgeClass = 'badge-normal';
            if (item.status === 'Crítico') badgeClass = 'badge-critico';
            else if (item.status === 'Atenção') badgeClass = 'badge-atencao';

            const badgeHtml = item.status === 'Sem Registro'
                ? '<span style="color:var(--text-tertiary); font-size:11px;">Sem Config</span>'
                : `<span class="badge ${badgeClass}"><div class="badge-dot"></div></span>`;

            const dest = item.destinacao || '-';
            const ref = item.referencia || '-';

            // Html da coluna Fixa do Produto
            let linhaHtml = `
                <td class="col-produto sticky-col">
                    <div style="font-weight: 600;">${item.id}</div>
                    <div style="color: var(--text-secondary); font-size: 13px;">${item.nome}</div>
                </td>
                <td class="col-ref" style="font-size: 12px;">
                    <div style="color: var(--text-primary); margin-bottom: 2px;">${ref}</div>
                    <div style="color: var(--text-tertiary); font-size: 11px;">Uso: ${dest}</div>
                </td>
                <td class="text-center col-total" style="vertical-align: middle;">
                    <div style="font-size: 16px; font-weight: 700; color:var(--primary);">${item.totalAtual}</div>
                    <div style="font-size: 11px; color: var(--text-tertiary);">Mín: ${item.totalMin} / Máx: ${item.totalMax}</div>
                    <div style="margin-top:4px;">${badgeHtml}</div>
                </td>
            `;

            // Histograma / Dados de cada Loja
            lojas.forEach(l => {
                const celula = item.matrizLojas[l.id];
                if (!celula) {
                    linhaHtml += `<td class="text-center col-loja" style="background:#f8fafc; color:#cbd5e1">-</td>`;
                } else {
                    linhaHtml += `
                        <td class="text-center col-loja">
                            <div class="matriz-cell-val" style="color: var(--text-tertiary); font-size: 11px;">Consumo</div>
                            <div class="matriz-cell-cons" style="font-size: 14px; color: var(--text-primary); margin-top: 2px;" title="Consumo Médio ${item.periodo_consumo} Cadastrado">${celula.consumo} <span style="font-size:10px;">/${item.periodo_consumo === 'Semanal' ? 'sem.' : 'mês'}</span></div>
                        </td>
                     `;
                }
            });

            // Input Final column for Pedido
            linhaHtml += `
                <td class="text-center" style="position: sticky; right: 0; background: var(--bg); z-index: 10; border-left: 1px solid var(--border); vertical-align: middle;">
                     <input type="number" min="0" placeholder="0" 
                        class="input-qty-matriz" style="width: 60px; text-align: center; margin: 0 auto; display: block; padding: 4px;"
                        data-id="${item.id}"
                        data-nome="${item.nome}"
                        data-custo="${item.custo}"
                        onchange="window.Estoque.calcularTotalPedido()"
                        onkeyup="window.Estoque.calcularTotalPedido()"
                     >
                </td>
            `;

            const tr = document.createElement('tr');
            tr.innerHTML = linhaHtml;
            tbody.appendChild(tr);
        });

        this.calcularTotalPedido();
    },

    sugerirQuantidades() {
        const secao = document.getElementById('filtro-secao-estoque').value;

        const btnSugerir = document.getElementById('btn-sugerir-matriz');
        if (btnSugerir) {
            btnSugerir.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Processando...';
            btnSugerir.disabled = true;
        }

        let suggestionsCount = 0;

        // Iterate over rendered inputs
        const inputs = document.querySelectorAll('.input-qty-matriz');
        inputs.forEach(inp => {
            const prodId = inp.getAttribute('data-id');
            const item = this.dadosGlobais.find(p => p.id === prodId);

            if (!item) return;

            // Global stock thresholds
            const atual = item.totalAtual || 0;
            const min = item.totalMin || 0;
            const max = item.totalMax || 0;

            let suggestedQty = 0;
            if (atual <= min && max > atual) {
                suggestedQty = (max - atual);
            } else if (atual < max && min === 0 && max > 0) {
                // Se o min for 0 mas tem um limite max, repôr a partir do momento de quebra
                suggestedQty = (max - atual);
            }

            if (suggestedQty > 0) {
                inp.value = suggestedQty;
                suggestionsCount++;
            }
        });

        this.calcularTotalPedido();

        if (btnSugerir) {
            btnSugerir.innerHTML = '<i class="ph ph-magic-wand"></i> Auto-Sugerir';
            btnSugerir.disabled = false;
        }

        if (suggestionsCount === 0) {
            alert('Atenção: Nenhuma sugestão identificada. O estoque dos itens selecionados já está adequado ou não possui limites Max/Min definidos.');
        } else {
            console.log(`Auto-suggest finalizado: ${suggestionsCount} itens preenchidos.`);
        }
    },

    calcularTotalPedido() {
        let total = 0;
        const inputs = document.querySelectorAll('.input-qty-matriz');
        inputs.forEach(inp => {
            const val = parseInt(inp.value) || 0;
            const custo = parseFloat(inp.getAttribute('data-custo')) || 0;
            total += (val * custo);

            const tr = inp.closest('tr');
            if (val > 0) {
                tr.style.backgroundColor = 'var(--primary-light)';
            } else {
                tr.style.backgroundColor = '';
            }
        });

        const spanTotal = document.getElementById('matriz-total-pedido');
        if (spanTotal) {
            spanTotal.innerText = `R$ ${total.toFixed(2).replace('.', ',')}`;
        }
    },

    exportarPedidoTxt() {
        const lojaId = document.getElementById('matriz-loja-pedido').value;
        if (!lojaId) {
            alert('Por favor, selecione a Loja Solicitante no topo antes de exportar o pedido.');
            return;
        }

        const inputs = document.querySelectorAll('.input-qty-matriz');
        const itensPedir = [];

        inputs.forEach(inp => {
            const val = parseInt(inp.value) || 0;
            if (val > 0) {
                itensPedir.push({
                    codigo: inp.getAttribute('data-id'),
                    nome: inp.getAttribute('data-nome'),
                    custo: parseFloat(inp.getAttribute('data-custo')) || 0,
                    quantidade: val
                });
            }
        });

        if (itensPedir.length === 0) {
            alert('Você não informou a quantidade de nenhum produto.');
            return;
        }

        const payloadPedido = {
            loja_id: lojaId,
            itens: itensPedir.map(p => ({
                codigo: p.codigo,
                nome: p.nome,
                custo: p.custo,
                quantidade: p.quantidade,
                subtotal: p.custo * p.quantidade
            }))
        };

        console.log("== ENVIANDO PEDIDO LOTE PARA O BACK-END ==", JSON.stringify(payloadPedido, null, 2));

        // Generate TXT Content based on Python logic
        // Codigo (13) + Qtd (6) + Custo (6 cents)
        let txtContent = "";
        itensPedir.forEach(p => {
            const cod = String(p.codigo).padStart(13, '0');
            const qtd = String(p.quantidade).padStart(6, '0');
            const custoCents = String(Math.round(p.custo * 100)).padStart(6, '0');
            txtContent += `${cod}${qtd}${custoCents}\n`;
        });

        // Deduzir globalmente no estoque local (Visual Update only, would need backend route for permanent storage)
        payloadPedido.itens.forEach(i => {
            window.Store.ajustarEstoque(lojaId, i.codigo, -i.quantidade);
        });

        // Trigger file download
        const blob = new Blob([txtContent], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Pedido_Loja_${lojaId}_${new Date().getTime()}.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        alert('Pedido efetuado com Sucesso! TXT Posicional Gerado para Download.\nA Matriz de Estoque Global local foi atualizada.');

        // Limpar inputs de pedido
        inputs.forEach(inp => inp.value = '');
        this.calcularTotalPedido();
    }
};
