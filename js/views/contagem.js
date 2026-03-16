/**
 * contagem.js - Módulo de Ajuste Físico de Estoque
 */

window.Contagem = {
    produtosRenderizados: [],

    init() {
        this.carregarComboSecao();
        this.verificarPainel();
    },

    carregarComboSecao() {
        const secoes = window.Store.getSecoes();
        const selectSecao = document.getElementById('filtro-secao-contagem');
        if (selectSecao && secoes) {
            selectSecao.innerHTML = '<option value="">Todas as Seções</option>';
            secoes.forEach(s => {
                selectSecao.innerHTML += `<option value="${s.nome}">${s.nome}</option>`;
            });
        }
    },

    verificarPainel() {
        const estoqueGlobal = window.Store.getEstoqueGlobal() || [];
        // Preparar lista adicionando state para o input numérico
        this.produtosRenderizados = estoqueGlobal.map(p => ({ ...p, novoEstoque: '' }));

        document.getElementById('search-contagem').value = '';
        document.getElementById('filtro-secao-contagem').value = '';

        this.renderizarGradeItens(this.produtosRenderizados);
    },

    filtrarProdutos() {
        const termo = document.getElementById('search-contagem').value.toLowerCase();
        const secao = document.getElementById('filtro-secao-contagem').value;
        let filtrados = this.produtosRenderizados;

        if (secao) {
            filtrados = filtrados.filter(item => item.secao === secao);
        }

        if (termo) {
            filtrados = filtrados.filter(item =>
                item.nome.toLowerCase().includes(termo) ||
                item.id.toLowerCase().includes(termo)
            );
        }

        this.renderizarGradeItens(filtrados);
    },

    alterarQuantidade(produtoId, qtdeStr) {
        let q = parseFloat(qtdeStr);
        const prod = this.produtosRenderizados.find(p => p.id === produtoId);

        if (prod) {
            if (isNaN(q) || qtdeStr === "") {
                prod.novoEstoque = '';
            } else {
                prod.novoEstoque = q;
            }

            // Highlight row visually
            const inputEl = document.getElementById(`contagem-input-${produtoId}`);
            if (inputEl) {
                const tr = inputEl.closest('tr');
                if (prod.novoEstoque !== '') {
                    tr.classList.add('row-selected');
                } else {
                    tr.classList.remove('row-selected');
                }
            }
        }
    },

    renderizarGradeItens(lista) {
        const tbody = document.querySelector('#tabela-contagem tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (lista.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-state text-center" style="padding: 20px;">Nenhum produto encontrado.</td></tr>`;
            return;
        }

        // Limitando renderização para não travar tela se houver milhares de produtos (Renderiza lote inicial)
        const renderList = lista.slice(0, 150);

        renderList.forEach(prod => {
            const tr = document.createElement('tr');
            if (prod.novoEstoque !== '') tr.classList.add('row-selected');

            tr.innerHTML = `
                <td style="font-weight: 600; color:var(--text-primary);">${prod.id}</td>
                <td>
                    <div style="color:var(--text-secondary);">${prod.nome}</div>
                </td>
                <td><small style="color:var(--text-tertiary)">${prod.secao || 'Sem Seção'}</small></td>
                <td class="text-center" style="vertical-align: middle; font-size: 16px;">
                    <span style="color: ${prod.totalAtual < prod.totalMin ? 'var(--danger)' : 'var(--success)'}; font-weight: 500;">
                        ${prod.totalAtual}
                    </span>
                </td>
                <td class="text-center" style="vertical-align: middle;">
                    <div style="display:inline-block; max-width:120px;">
                        <input type="number" min="0" value="${prod.novoEstoque}" 
                            placeholder="Ajuste..."
                            class="input-qty"
                            id="contagem-input-${prod.id}"
                            onchange="window.Contagem.alterarQuantidade('${prod.id}', this.value)"
                            onkeyup="window.Contagem.alterarQuantidade('${prod.id}', this.value)"
                            style="border: 1px solid var(--primary); background-color: #f8fafc;"
                        >
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });

        if (lista.length > 150) {
            tbody.innerHTML += `<tr><td colspan="5" class="text-center" style="color: var(--text-tertiary); padding: 10px;"><small>+ ${lista.length - 150} produtos ocultos. Use a pesquisa para filtrar.</small></td></tr>`;
        }
    },

    async salvarContagem() {
        // Pega apenas o que teve o input preenchido
        const itensAlterados = this.produtosRenderizados.filter(p => p.novoEstoque !== '');

        if (itensAlterados.length === 0) {
            alert('Não há nenhuma alteração de estoque para ser salva. Preencha a nova quantidade em algum produto.');
            return;
        }

        const confirmacao = confirm(`Você está prestes a substituir o Estoque Atual de ${itensAlterados.length} produto(s) no sistema. Confirma esta operação de inventário?`);
        if (!confirmacao) return;

        const payload = itensAlterados.map(p => ({
            produto_id: p.id,
            novo_estoque: p.novoEstoque
        }));

        const btn = document.querySelector('#view-contagem .btn-primary');
        const textOrig = btn.innerHTML;
        btn.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Salvando...';
        btn.disabled = true;

        try {
            const res = await fetch('/api/estoque/ajuste', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Falha ao gravar Inventário.');
            }

            alert('✅ Estoque ajustado com Sucesso!');

            // Recarrega os dados globais da store pra atualizar as outras abas instantaneamente
            await window.Store.fetchEstoqueGlobal();
            this.verificarPainel();

        } catch (error) {
            console.error("Erro no Inventário:", error);
            alert("Erro ao salvar contagem: " + error.message);
        } finally {
            btn.innerHTML = textOrig;
            btn.disabled = false;
        }
    }
};
