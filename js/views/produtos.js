/**
 * produtos.js - Lógica Geral para a Tela de Cadastro de Produtos
 */

window.Produtos = {
    produtosRenderizados: [],
    produtoEmEdicaoId: null,

    init() {
        this.carregarSelectSecoes();
    },

    carregarSelectSecoes() {
        // Mock sections array based on DB Schema
        const secoes = [
            'Embalagem', 'Limpeza', 'Consumo Geral', 'Escritório',
            'Açougue', 'Bobina PDV', 'Etiquetas', 'Bobina Estrela'
        ];

        const select = document.getElementById('prod-form-secao');
        if (!select) return;

        select.innerHTML = '<option value="">-- Selecione a Seção --</option>';
        secoes.forEach(s => {
            select.innerHTML += `<option value="${s}">${s}</option>`;
        });
    },

    carregarTabela() {
        this.produtosRenderizados = window.Store.getProdutos();
        this.renderizarGradeItens(this.produtosRenderizados);
    },

    filtrarTabela() {
        const termo = document.getElementById('search-produtos').value.toLowerCase();
        let filtrados = this.produtosRenderizados;

        if (termo) {
            filtrados = this.produtosRenderizados.filter(item =>
                item.nome.toLowerCase().includes(termo) ||
                item.id.includes(termo)
            );
        }

        this.renderizarGradeItens(filtrados);
    },

    formatarMoeda(v) { return `R$ ${v.toFixed(2).replace('.', ',')}`; },

    renderizarGradeItens(lista) {
        const tbody = document.querySelector('#tabela-crud-produtos tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (lista.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Nenhum produto cadastrado.</td></tr>`;
            return;
        }

        lista.forEach(prod => {
            const tr = document.createElement('tr');

            const dest = prod.destinacao || '-';
            const ref = prod.referencia || '-';

            tr.innerHTML = `
                <td>
                    <div style="font-weight: 600; color:var(--text-primary);">${prod.id}</div>
                </td>
                <td>
                    <div style="font-weight: 500;">${prod.nome}</div>
                    <small style="color:var(--text-tertiary)">${prod.secao}</small>
                </td>
                <td>
                    <div style="font-size: 13px;">${dest}</div>
                    <small style="color:var(--text-tertiary)">Ref: ${ref}</small>
                </td>
                <td class="text-center">
                    <span class="badge ${prod.periodo_consumo === 'Semanal' ? 'badge-atencao' : 'badge-normal'}">${prod.periodo_consumo}</span>
                </td>
                <td class="text-right" style="vertical-align: middle;">${this.formatarMoeda(prod.custo)}</td>
                <td class="text-center">
                    <button class="btn btn-sm" style="color: var(--primary);" onclick="window.Produtos.abrirModalEdicao('${prod.id}')" title="Editar">
                        <i class="ph ph-pencil-simple"></i>
                    </button>
                    <button class="btn btn-sm" style="color: var(--danger);" onclick="window.Produtos.excluirProduto('${prod.id}')" title="Excluir">
                        <i class="ph ph-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    abrirModalEdicao(id = null) {
        this.produtoEmEdicaoId = id;
        const titulo = document.getElementById('modal-produto-titulo');
        const inputId = document.getElementById('prod-form-id');

        if (id) {
            // Edit Mode
            titulo.innerText = "Editar Produto";
            inputId.readOnly = true;
            inputId.style.backgroundColor = 'var(--bg)';

            const prod = window.Store.getProdutos().find(p => p.id === id);
            if (prod) {
                inputId.value = prod.id;
                document.getElementById('prod-form-nome').value = prod.nome;
                document.getElementById('prod-form-secao').value = prod.secao;
                document.getElementById('prod-form-custo').value = prod.custo;
                document.getElementById('prod-form-periodo').value = prod.periodo_consumo || 'Mensal';
                document.getElementById('prod-form-destinacao').value = prod.destinacao || '';
                document.getElementById('prod-form-ref').value = prod.referencia || '';
                document.getElementById('prod-form-minimo').value = prod.estoque_minimo || 0;
                document.getElementById('prod-form-maximo').value = prod.estoque_maximo || 0;
            }
        } else {
            // Create Mode
            titulo.innerText = "Novo Produto";
            inputId.readOnly = false;
            inputId.style.backgroundColor = '#fff';
            document.getElementById('form-produto').reset();
        }

        // --- Renderização Dinâmica das Lojas ---
        const configContainer = document.getElementById('prod-lojas-config-container');
        configContainer.innerHTML = '';
        const lojas = window.Store.getLojas() || [];

        let existingConfig = {};
        if (id) {
            const prod = window.Store.getProdutos().find(p => p.id === id);
            existingConfig = (prod && prod.matrizLojas) ? prod.matrizLojas : {};
        }

        lojas.forEach(loja => {
            const lc = existingConfig[loja.id] || { consumo: 0 };
            const div = document.createElement('div');
            div.style.cssText = 'display:flex; gap:10px; align-items:flex-end; padding-bottom:10px; border-bottom:1px solid var(--border-light);';
            div.innerHTML = `
                <div style="width: 80px; font-weight:600; color:var(--text-primary); padding-bottom:10px;">
                    ${loja.sigla || loja.nome}
                </div>
                <div class="form-group flex-1" style="margin-bottom:0;">
                    <label style="font-size:11px; color:var(--warning);">Consumo Médio</label>
                    <input type="number" step="0.01" id="cfg-consumo-${loja.id}" value="${lc.consumo}">
                </div>
            `;
            configContainer.appendChild(div);
        });
        // ----------------------------------------

        document.getElementById('modal-produto').style.display = 'flex';
    },

    fecharModal() {
        document.getElementById('modal-produto').style.display = 'none';
        this.produtoEmEdicaoId = null;
    },

    async salvarProduto() {
        const pId = document.getElementById('prod-form-id').value.trim();
        const pNome = document.getElementById('prod-form-nome').value.trim();
        const pSecao = document.getElementById('prod-form-secao').value;
        const pCusto = parseFloat(document.getElementById('prod-form-custo').value);
        const pPeriodo = document.getElementById('prod-form-periodo').value;
        const pDest = document.getElementById('prod-form-destinacao').value.trim();
        const pRef = document.getElementById('prod-form-ref').value.trim();
        const pMinimo = parseFloat(document.getElementById('prod-form-minimo').value) || 0;
        const pMaximo = parseFloat(document.getElementById('prod-form-maximo').value) || 0;

        const lojas_config = [];
        const lojas = window.Store.getLojas() || [];
        lojas.forEach(loja => {
            const consumo = parseFloat(document.getElementById(`cfg-consumo-${loja.id}`).value) || 0;

            lojas_config.push({
                loja_id: loja.id,
                consumo: consumo
            });
        });

        if (!pId || !pNome || !pSecao || isNaN(pCusto)) {
            alert("Por favor, preencha todos os campos obrigatórios (*).");
            return;
        }

        const payload = {
            id: pId,
            nome: pNome,
            secao: pSecao,
            custo: pCusto,
            periodo_consumo: pPeriodo,
            destinacao: pDest,
            referencia: pRef,
            estoque_minimo: pMinimo,
            estoque_maximo: pMaximo,
            lojas_config: lojas_config
        };

        const success = await window.Store.salvarProduto(payload, !!this.produtoEmEdicaoId);

        if (success) {
            await window.Store.fetchProdutos(); // refresh store with true DB state
            this.fecharModal();
            this.carregarTabela(); // refresh current table array
            // Notification or visual feedback could be added here
        } else {
            alert("Erro: Não foi possível salvar (Verifique se o Código do Produto já existe).");
        }
    },

    async excluirProduto(id) {
        if (confirm(`Tem certeza que deseja excluir o produto ${id}? Essa ação apagará o histórico de estoque associado a ele.`)) {
            const success = await window.Store.excluirProduto(id);
            if (success) {
                await window.Store.fetchProdutos();
                this.carregarTabela();
            }
        }
    }
};
