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

            // Highlight card visually
            const inputEl = document.getElementById(`contagem-input-${produtoId}`);
            if (inputEl) {
                const card = inputEl.closest('.contagem-card');
                if (card) {
                    if (prod.novoEstoque !== '') {
                        card.classList.add('selected');
                    } else {
                        card.classList.remove('selected');
                    }
                }
            }
        }
    },

    ajustarQtdeRapido(produtoId, delta) {
        const prod = this.produtosRenderizados.find(p => p.id === produtoId);
        if (!prod) return;

        let atual = parseFloat(prod.novoEstoque);
        if (isNaN(atual)) {
            // Se está vazio, o usuário está fazendo o primeiro toque, assumimos o saldo atual como base
            atual = parseFloat(prod.totalAtual) || 0;
        }

        let novo = atual + delta;
        if (novo < 0) novo = 0;

        this.alterarQuantidade(produtoId, novo);

        // Atualiza o DOM para refletir a nova qtde sem re-renderizar a lista toda e perder o foco scroll
        const inputEl = document.getElementById(`contagem-input-${produtoId}`);
        if (inputEl) {
            inputEl.value = novo;
        }
    },

    renderizarGradeItens(lista) {
        const container = document.getElementById('lista-contagem');
        if (!container) return;

        container.innerHTML = '';

        if (lista.length === 0) {
            container.innerHTML = `<div class="empty-state text-center" style="padding: 20px;">Nenhum produto atende aos filtros.</div>`;
            return;
        }

        // Limitando renderização para não travar tela se houver milhares de produtos
        const renderList = lista.slice(0, 150);

        renderList.forEach(prod => {
            const isSelected = prod.novoEstoque !== '';
            const statusColor = prod.totalAtual < prod.totalMin ? 'var(--danger)' : 'var(--success)';

            const card = document.createElement('div');
            card.className = `contagem-card ${isSelected ? 'selected' : ''}`;

            card.innerHTML = `
                <div class="contagem-card-header">
                    <span style="color:var(--text-tertiary);">Cód: <strong style="color:var(--text-primary);">${prod.id}</strong></span>
                    <span style="color:var(--text-tertiary);"><i class="ph ph-tag"></i> ${prod.secao || 'Sem Seção'}</span>
                </div>
                <div class="produto-nome-card">${prod.nome}</div>
                
                <div class="contagem-card-body">
                    <div class="estoque-atual-box">
                        <small>Sistema Atual</small>
                        <strong style="color: ${statusColor};">${prod.totalAtual}</strong>
                    </div>
                    
                    <div class="estoque-fisico-input">
                        <button type="button" class="btn-circular" onclick="window.Contagem.ajustarQtdeRapido('${prod.id}', -1)" title="Subtrair 1">
                            <i class="ph ph-minus"></i>
                        </button>
                        
                        <input type="number" min="0" value="${prod.novoEstoque}" 
                            placeholder="Real"
                            id="contagem-input-${prod.id}"
                            onchange="window.Contagem.alterarQuantidade('${prod.id}', this.value)"
                            onkeyup="window.Contagem.alterarQuantidade('${prod.id}', this.value)"
                        >
                        
                        <button type="button" class="btn-circular" onclick="window.Contagem.ajustarQtdeRapido('${prod.id}', 1)" title="Somar 1">
                            <i class="ph ph-plus"></i>
                        </button>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

        if (lista.length > 150) {
            container.innerHTML += `<div class="text-center" style="color: var(--text-tertiary); padding: 10px;"><small>+ ${lista.length - 150} produtos ocultos. Use a barra de pesquisa para filtrar.</small></div>`;
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

        const btn = document.querySelector('.mobile-sticky-footer .btn-primary') || document.querySelector('#view-contagem .btn-primary');
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
