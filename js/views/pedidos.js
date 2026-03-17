/**
 * pedidos.js - Roteirização de Pedidos em Lote "Fácil Fazer"
 */

window.Pedidos = {
    produtosRenderizados: [],

    init() {
        this.carregarComboLoja();
    },

    carregarComboLoja() {
        const lojas = window.Store.getLojas();
        const selectLoja = document.getElementById('loja-pedido');
        lojas.forEach(l => {
            selectLoja.innerHTML += `<option value="${l.id}">${l.nome}</option>`;
        });
    },

    verificarPainel() {
        const lojaId = document.getElementById('loja-pedido').value;
        const painel = document.getElementById('painel-pedidos');
        const vazio = document.getElementById('painel-vazio-pedidos');
        const searchInput = document.getElementById('search-pedidos');

        const secaoSelect = document.getElementById('filtro-secao-pedido');
        const btnSugerir = document.getElementById('btn-sugerir-pedidos');

        if (lojaId) {
            painel.style.display = 'block';
            vazio.style.display = 'none';
            searchInput.disabled = false;
            secaoSelect.disabled = false;
            if (btnSugerir) btnSugerir.disabled = false;

            // Recarrega todos os produtos e limpa buscas
            this.produtosRenderizados = window.Store.getProdutos().map(p => ({ ...p, qtdeInput: 0 }));
            searchInput.value = '';
            secaoSelect.value = '';

            this.renderizarGradeItens(this.produtosRenderizados);
            this.calcularTotalGlobal();
        } else {
            painel.style.display = 'none';
            vazio.style.display = 'block';
            searchInput.disabled = true;
            secaoSelect.disabled = true;
            if (btnSugerir) btnSugerir.disabled = true;
            secaoSelect.value = '';
        }
    },

    filtrarProdutos() {
        const termo = document.getElementById('search-pedidos').value.toLowerCase();
        const secao = document.getElementById('filtro-secao-pedido').value;
        let filtrados = this.produtosRenderizados;

        if (secao) {
            filtrados = filtrados.filter(item => item.secao === secao);
        }

        if (termo) {
            filtrados = filtrados.filter(item =>
                item.nome.toLowerCase().includes(termo) ||
                item.id.includes(termo)
            );
        }

        this.renderizarGradeItens(filtrados);
    },

    async sugerirQuantidades() {
        const lojaId = document.getElementById('loja-pedido').value;
        const secao = document.getElementById('filtro-secao-pedido').value;

        if (!lojaId) return;

        const btnSugerir = document.getElementById('btn-sugerir-pedidos');
        const oldHtml = btnSugerir.innerHTML;
        btnSugerir.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Processando...';
        btnSugerir.disabled = true;

        // Garantir que a matriz de estoque está carregada e atualizada
        await window.Store.fetchEstoqueGlobal();
        const estoqueMatriz = window.Store.getEstoqueGlobal();

        let suggestionsCount = 0;

        this.produtosRenderizados.forEach(prod => {
            // Respeitar o filtro de seção se houver algum selecionado
            if (secao && prod.secao !== secao) return;

            // Buscar os limites e níveis de estoque do produto
            const matItem = estoqueMatriz.find(e => e.id === prod.id);
            if (matItem && matItem.matrizLojas && matItem.matrizLojas[lojaId]) {
                const limit = matItem.matrizLojas[lojaId];
                // Em um sistema real, totalAtual poderia vazar per-store, mas no MVP usa estoque_global
                const atual = matItem.totalAtual || 0;
                const min = limit.min || 0;
                const max = limit.max || 0;

                // Regra de Reposição
                if (atual <= min && max > atual) {
                    prod.qtdeInput = (max - atual);
                    suggestionsCount++;
                } else if (atual < max && min === 0 && max > 0) {
                    // Quando não possui mínimo mapeado (trata como <= 0), sugere tapar o buraco do max 
                    prod.qtdeInput = (max - atual);
                    suggestionsCount++;
                }
            }
        });

        // Re-renderiza a grade de itens com as novas quantidades mantendo o filtro ativo
        this.filtrarProdutos();
        this.calcularTotalGlobal(); // Ensure footer total is updated

        btnSugerir.innerHTML = oldHtml;
        btnSugerir.disabled = false;

        if (suggestionsCount === 0) {
            alert('Atenção: Nenhuma sugestão identificada. O estoque dos itens selecionados já está adequado (acima do mínimo) ou não possui limites Max/Min definidos.');
        }
    },

    formatarMoeda(v) { return `R$ ${v.toFixed(2).replace('.', ',')}`; },

    alterarQuantidade(produtoId, qtdeStr) {
        let q = parseInt(qtdeStr);
        if (isNaN(q) || q < 0) q = 0;

        const prod = this.produtosRenderizados.find(p => p.id === produtoId);
        if (prod) {
            prod.qtdeInput = q;
        }

        // Atualiza subtotal na tela apenas para essa row pra performance
        const spanSub = document.getElementById(`subtotal-${produtoId}`);
        if (spanSub) {
            const sub = q * prod.custo;
            spanSub.innerText = this.formatarMoeda(sub);

            // Highlight na row se for > 0
            const tr = spanSub.closest('tr');
            if (q > 0) tr.classList.add('row-selected');
            else tr.classList.remove('row-selected');
        }

        this.calcularTotalGlobal();
    },

    renderizarGradeItens(lista) {
        const tbody = document.querySelector('#tabela-pedidos tbody');
        tbody.innerHTML = '';

        if (lista.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="empty-state">Nenhum produto encontrado.</td></tr>`;
            return;
        }

        lista.forEach(prod => {
            const tr = document.createElement('tr');
            if (prod.qtdeInput > 0) tr.classList.add('row-selected');

            const detalhes = window.Helpers.gerarDetalhesSecao(prod);
            const sub = prod.qtdeInput * prod.custo;

            tr.innerHTML = `
                <td>
                    <div style="font-weight: 600; color:var(--text-primary);">${prod.id}</div>
                    <div style="color:var(--text-secondary);">${prod.nome}</div>
                    <small style="color:var(--text-tertiary)">${prod.secao}</small>
                    <div style="margin-top:4px; line-height:1.8;">${detalhes}</div>
                </td>
                <td class="text-right" style="vertical-align: middle;">${this.formatarMoeda(prod.custo)}</td>
                <td class="text-center" style="vertical-align: middle;">
                    <div style="display:inline-block; max-width:120px;">
                        <input type="number" min="0" value="${prod.qtdeInput || ''}" 
                            placeholder="0"
                            class="input-qty"
                            onchange="window.Pedidos.alterarQuantidade('${prod.id}', this.value)"
                            onkeyup="window.Pedidos.alterarQuantidade('${prod.id}', this.value)"
                        >
                    </div>
                </td>
                <td class="text-right" style="vertical-align: middle; font-weight:600; color:var(--primary);">
                    <span id="subtotal-${prod.id}">${this.formatarMoeda(sub)}</span>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    calcularTotalGlobal() {
        let total = 0;
        this.produtosRenderizados.forEach(p => {
            total += (p.qtdeInput * p.custo);
        });
        document.getElementById('total-pedido').innerText = this.formatarMoeda(total);
    },

    async finalizarExportarPedido() {
        const lojaId = document.getElementById('loja-pedido').value;
        const itensPedir = this.produtosRenderizados.filter(p => p.qtdeInput > 0);

        if (itensPedir.length === 0) {
            alert('Você não informou a quantidade de nenhum produto.');
            return;
        }

        const payloadPedido = {
            loja_id: lojaId,
            itens: itensPedir.map(p => ({
                codigo: p.id,
                nome: p.nome,
                custo: p.custo,
                quantidade: p.qtdeInput,
                subtotal: p.custo * p.qtdeInput
            }))
        };

        try {
            // 1. Enviar para a API Python para gerar o TXT posicional
            const res = await fetch('/api/exportar-pedido-txt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payloadPedido)
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Falha ao exportar pedido.');
            }

            // 2. Processar o download do Blob (Arquivo TXT Genérico)
            const blob = await res.blob();

            // Pega o nome do arquivo enviado pelo Content-Disposition Header (fallback manual)
            const contentDisposition = res.headers.get('Content-Disposition');
            let filename = `PEDIDO_LOJA_${lojaId}.txt`;
            if (contentDisposition && contentDisposition.includes('filename=')) {
                filename = contentDisposition.split('filename=')[1].split(';')[0].replace(/"/g, '');
            }

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            // 3. Atualiza Estoque Local UI (Opcional, se o back tivesse integração real de db já descontava lá)
            payloadPedido.itens.forEach(i => {
                window.Store.ajustarEstoque(lojaId, i.codigo, -i.quantidade);
            });

            alert(`Pedido finalizado com sucesso!\\nO arquivo ${filename} foi baixado.`);

            // Reset View
            document.getElementById('loja-pedido').value = '';
            this.verificarPainel();

        } catch (error) {
            console.error("Erro na exportação:", error);
            alert("Erro ao gerar o pedido: " + error.message);
        }
    }
};
