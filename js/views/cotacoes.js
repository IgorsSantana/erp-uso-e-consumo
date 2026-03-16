window.Cotacoes = {
    dados: [],
    carrinho: [], // { produto_id, nome }

    async init() {
        await this.carregarListagem();
    },

    async carregarListagem() {
        try {
            const res = await fetch('/api/cotacoes');
            this.dados = await res.json();
            this.renderizarListagem(this.dados);
        } catch (e) {
            console.error("Erro Cotacoes:", e);
        }
    },

    renderizarListagem(lista) {
        const tbody = document.querySelector('#tabela-cotacoes tbody');
        tbody.innerHTML = '';

        if (lista.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding: 30px; color: var(--text-tertiary);">Nenhuma cotação encontrada.</td></tr>`;
            return;
        }

        lista.forEach(c => {
            const tr = document.createElement('tr');

            const btnStatus = c.Status === 'Aberta'
                ? `<span class="badge badge-normal"><i class="badge-dot"></i> Aberta</span>`
                : `<span class="badge badge-atencao"><i class="badge-dot" style="background:var(--warning)"></i> Encerrada</span>`;

            tr.innerHTML = `
                <td style="font-weight: 500;">${c.Titulo}</td>
                <td>
                    <div style="font-size: 12px; color: var(--text-tertiary);">Abertura: ${new Date(c.Data_Abertura).toLocaleDateString()}</div>
                    ${c.Data_Encerramento ? `<div style="font-size: 12px;">Encerramento: ${new Date(c.Data_Encerramento).toLocaleDateString()}</div>` : ''}
                </td>
                <td class="text-center">${c.qtd_fornecedores} Convidados</td>
                <td class="text-center">${c.qtd_itens} Produtos</td>
                <td class="text-center">${btnStatus}</td>
                <td class="text-center">
                    <button class="btn btn-primary shadow-sm" style="padding: 6px 12px; width: 100%;" onclick="window.Cotacoes.abrirResultados(${c.ID})">
                        Ver Ofertas
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    filtrarListagem() {
        const query = document.getElementById('search-cotacao').value.toLowerCase();
        const filtrados = this.dados.filter(c => c.Titulo.toLowerCase().includes(query));
        this.renderizarListagem(filtrados);
    },

    // ==========================================
    // NOVA COTAÇÃO WIZARD
    // ==========================================
    async abrirNovaCotacao() {
        this.carrinho = [];
        document.getElementById('cot-titulo').value = '';

        // Carrega Fornecedores
        const cbxContainer = document.getElementById('cot-fornecedores-cbx');
        cbxContainer.innerHTML = 'Carregando...';
        await window.Fornecedores.carregarDados();
        const f = window.Fornecedores.dados;
        if (f.length === 0) {
            cbxContainer.innerHTML = '<span style="color:var(--danger)">Você precisa cadastrar fornecedores primeiro no menu lateral.</span>';
        } else {
            cbxContainer.innerHTML = `
                <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap;">
                    <div class="search-input" style="flex: 1; min-width: 200px;">
                        <i class="ph ph-magnifying-glass"></i>
                        <input type="text" placeholder="Pesquisar fornecedor..." style="padding: 8px 16px 8px 40px; font-size: 13px;" onkeyup="
                            const q = this.value.toLowerCase();
                            document.querySelectorAll('.forn-cbx-item').forEach(el => {
                                el.style.display = el.innerText.toLowerCase().includes(q) ? 'flex' : 'none';
                            });
                        ">
                    </div>
                    <button type="button" class="btn" style="background:var(--bg-surface); border:1px solid var(--border); color:var(--text-secondary); padding: 8px 12px; font-size: 12px;" onclick="
                        const boxes = document.querySelectorAll('input[name=\\'forn_cotacao\\']');
                        // if any visible is unchecked, check all visible. else uncheck all visible
                        const visibleBoxes = Array.from(boxes).filter(b => b.closest('.forn-cbx-item').style.display !== 'none');
                        const allChecked = visibleBoxes.every(b => b.checked);
                        visibleBoxes.forEach(b => {
                            b.checked = !allChecked;
                            if(b.checked) b.closest('.forn-cbx-item').style.backgroundColor = 'var(--primary-light)';
                            else b.closest('.forn-cbx-item').style.backgroundColor = 'var(--bg-surface)';
                            if(b.checked) b.closest('.forn-cbx-item').style.borderColor = 'var(--primary)';
                            else b.closest('.forn-cbx-item').style.borderColor = 'var(--border)';
                        });
                    ">
                        <i class="ph ph-check-square"></i> Marcar/Desmarcar Visíveis
                    </button>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; max-height: 200px; overflow-y: auto; padding-right: 5px;">
                    ${f.map(forn => `
                        <label class="forn-cbx-item hover-lift" style="display:flex; align-items:center; gap:10px; background: var(--bg-surface); padding: 12px; border-radius: var(--radius-md); border: 1px solid var(--border); cursor: pointer; transition: 0.2s;">
                            <input type="checkbox" name="forn_cotacao" value="${forn.ID}" style="width:18px; height:18px; cursor:pointer; accent-color: var(--primary);" onchange="
                                this.parentElement.style.backgroundColor = this.checked ? 'var(--primary-light)' : 'var(--bg-surface)';
                                this.parentElement.style.borderColor = this.checked ? 'var(--primary)' : 'var(--border)';
                            ">
                            <span style="font-weight: 500; font-size: 13px; color: var(--text-primary);">${forn.Nome_Fantasia}</span>
                        </label>
                    `).join('')}
                </div>
            `;
        }

        // Carrega Opções de Seções (Dropdown)
        const selectSecao = document.getElementById('cot-secao-select');
        selectSecao.innerHTML = '<option value="">-- Adicionar Seção Inteira (Automático) --</option>';
        if (window.Store.secoes) {
            window.Store.secoes.forEach(s => {
                selectSecao.innerHTML += `<option value="${s.nome}">${s.nome}</option>`;
            });
        }

        this.renderizarCarrinho();
        document.getElementById('modal-nova-cotacao').style.display = 'flex';
    },

    fecharNovaCotacao() {
        document.getElementById('modal-nova-cotacao').style.display = 'none';
        this.carrinho = [];
    },

    adicionarSecaoAutomatica() {
        const selectSecao = document.getElementById('cot-secao-select');
        const secaoStr = selectSecao.options[selectSecao.selectedIndex].text;

        if (selectSecao.value === "") {
            alert('Por favor, selecione uma seção antes de carregar as necessidades.');
            return;
        }

        const estoqueGlobal = window.Store.getEstoqueGlobal();
        let adicionados = 0;

        // Verify if we have the global stock loaded
        if (!estoqueGlobal || estoqueGlobal.length === 0) {
            alert('Erro: Os dados de Estoque Global não estão carregados. Tente recarregar a página.');
            return;
        }

        estoqueGlobal.forEach(p => {
            // Check if section matches
            if (p.secao === secaoStr) {
                // Calculate shortage
                const needsToBuy = p.totalAtual < p.totalMin;
                if (needsToBuy) {
                    const qtdSugestao = p.totalMax > 0 ? (p.totalMax - p.totalAtual) : 1;

                    // Add if not already in cart
                    if (!this.carrinho.find(x => x.produto_id === p.id)) {
                        this.carrinho.push({
                            produto_id: p.id,
                            nome: p.nome
                        });
                        adicionados++;
                    }
                }
            }
        });

        if (adicionados > 0) {
            alert(`Foram adicionados ${adicionados} produtos da Seção "${secaoStr}" que estão abaixo do estoque mínimo!`);
            this.renderizarCarrinho();
        } else {
            alert(`Nenhum produto da Seção "${secaoStr}" necessita de compra urgente no momento (O estoque atual está acima do mínimo de segurança).`);
        }
        selectSecao.value = '';
    },

    abrirModalBuscaProduto() {
        document.getElementById('input-busca-produto-cotacao').value = '';
        this.filtrarBuscaProdutos('');
        document.getElementById('modal-busca-produto-cotacao').style.display = 'flex';
    },

    filtrarBuscaProdutos(termo) {
        const estoqueGlobal = window.Store.getEstoqueGlobal() || [];
        termo = termo.toLowerCase().trim();

        // Se vazio, lista os 50 primeiros para não travar a tela
        let filtrados = estoqueGlobal;
        if (termo) {
            filtrados = estoqueGlobal.filter(p =>
                p.nome.toLowerCase().includes(termo) ||
                p.id.toLowerCase().includes(termo)
            );
        }

        this.renderizarBuscaProdutos(filtrados.slice(0, 50));
    },

    renderizarBuscaProdutos(lista) {
        const tbody = document.querySelector('#tabela-busca-produtos-cotacao tbody');
        tbody.innerHTML = '';

        if (lista.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center" style="color:var(--text-tertiary); padding:20px;">Nenhum produto encontrado.</td></tr>';
            return;
        }

        lista.forEach(p => {
            const jaAdicionado = this.carrinho.find(x => x.produto_id === p.id);
            const btnHtml = jaAdicionado
                ? `<button class="btn btn-secondary" style="color: var(--success); width: 100%; border-color: var(--success);" disabled><i class="ph ph-check"></i> Na Cotação</button>`
                : `<button class="btn btn-primary" style="width: 100%; padding: 5px;" onclick="window.Cotacoes.adicionarItemManualBusca('${p.id}', '${p.nome.replace(/'/g, "\\'")}')">
                     <i class="ph ph-plus"></i> Add
                   </button>`;

            tbody.innerHTML += `
                <tr>
                    <td>
                        <div style="font-weight: 600; color: var(--text-main);">${p.id}</div>
                        <div style="font-size: 13px; color: var(--text-secondary);">${p.nome}</div>
                        <span class="badge badge-normal" style="font-size: 11px;">${p.secao || 'Sem Seção'}</span>
                    </td>
                    <td class="text-center" style="font-weight: 500; font-size: 16px;">
                        <span style="color: ${p.totalAtual < p.totalMin ? 'var(--danger)' : 'var(--success)'}">${p.totalAtual}</span>
                    </td>
                    <td class="text-center" style="font-size: 13px; color: var(--text-secondary);">
                        ${p.totalMin} / ${p.totalMax}
                    </td>
                    <td style="vertical-align: middle;">
                        ${btnHtml}
                    </td>
                </tr>
            `;
        });
    },

    adicionarItemManualBusca(id, nome) {
        if (this.carrinho.find(x => x.produto_id === id)) {
            alert("Este produto já está na cotação.");
            return;
        }

        this.carrinho.push({ produto_id: id, nome: nome });
        this.renderizarCarrinho();

        // Recarrega a linha especifica para atualizar o botao para "Ja adicionado"
        this.filtrarBuscaProdutos(document.getElementById('input-busca-produto-cotacao').value);
    },

    removerItemCarrinho(id) {
        this.carrinho = this.carrinho.filter(x => x.produto_id !== id);
        this.renderizarCarrinho();
    },

    renderizarCarrinho() {
        const tbody = document.querySelector('#tabela-cot-carrinho tbody');
        tbody.innerHTML = '';
        if (this.carrinho.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="text-center" style="color:var(--text-tertiary);">Nenhum item adicionado.</td></tr>';
            return;
        }
        this.carrinho.forEach(item => {
            tbody.innerHTML += `
                <tr>
                    <td>${item.nome} <div style="font-size:11px; color:var(--text-tertiary)">Cód: ${item.produto_id}</div></td>
                    <td class="text-center">
                        <button class="btn" style="padding: 4px 8px; color: var(--danger);" onclick="window.Cotacoes.removerItemCarrinho('${item.produto_id}')"><i class="ph ph-trash"></i></button>
                    </td>
                </tr>
            `;
        });
    },

    async salvarCotacao() {
        const titulo = document.getElementById('cot-titulo').value;
        const boxes = Array.from(document.querySelectorAll('input[name="forn_cotacao"]:checked'));
        const fornecedores_ids = boxes.map(b => parseInt(b.value));

        if (!titulo) { alert("Dê um título para a cotação."); return; }
        if (fornecedores_ids.length === 0) { alert("Selecione ao menos 1 fornecedor participante."); return; }
        if (this.carrinho.length === 0) { alert("Adicione ao menos 1 produto no pacote."); return; }

        const payload = { titulo, observacoes: '', itens: this.carrinho, fornecedores: fornecedores_ids };

        try {
            const res = await fetch('/api/cotacoes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            alert(`Cotação salva com sucesso. Um portal único foi criado para os fornecedores.`);
            this.fecharNovaCotacao();
            this.carregarListagem();
        } catch (e) {
            console.error(e);
            alert("Erro ao criar cotação.");
        }
    },

    // ==========================================
    // RESULTADOS DA COTAÇÃO
    // ==========================================
    cotacaoAbertaAtual: null,

    async abrirResultados(id) {
        try {
            const res = await fetch(`/api/cotacoes/${id}`);
            const data = await res.json();
            this.cotacaoAbertaAtual = data;

            document.getElementById('res-t-titulo').innerText = data.Titulo;

            const btnEncerrar = document.getElementById('btn-encerrar-cotacao');
            const statusSp = document.getElementById('res-t-status');
            if (data.Status === 'Encerrada') {
                statusSp.className = "badge badge-atencao";
                statusSp.innerHTML = "Encerrada (Vencedores Vistos Abaixo)";
                btnEncerrar.style.display = 'none';
            } else {
                statusSp.className = "badge badge-normal";
                statusSp.innerHTML = "Aberta para Lances";
                btnEncerrar.style.display = 'inline-flex';
            }

            // Gerar Links Base URL (localhost/portal_fornecedor.html)
            // Em producao trocar a URL base para o dominio real
            const baseUrl = window.location.origin + window.location.pathname.replace('index.html', '') + 'portal_fornecedor.html';
            const lc = document.getElementById('res-links-container');
            lc.innerHTML = data.fornecedores.map(f => {
                const url = `${baseUrl}?token=${f.Token_Acesso}`;
                const badge = f.Preencheu ? `<span style="color:var(--success); font-size:12px; font-weight:bold;">PREENCHEU 🟢</span>` : (f.Visualizou ? `<span style="color:var(--warning); font-size:12px;">VIU (Não Enviou) 🟡</span>` : `<span style="color:var(--text-tertiary); font-size:12px;">Não Visualizou ⚪</span>`);
                return `
                <div style="border: 1px dashed var(--border); padding: 12px; border-radius: 8px;">
                    <div style="font-weight: 600; margin-bottom: 5px;">${f.nome} - status: ${badge}</div>
                    <div style="display:flex; gap: 10px;">
                        <input type="text" value="${url}" readonly style="font-size: 11px; padding: 6px; background:#f8fafc; color:#94a3b8; border:none; border-radius:4px; margin:0;">
                        <button class="btn btn-primary" style="padding: 6px; font-size:14px;" onclick="navigator.clipboard.writeText('${url}'); alert('Copiado!')" title="Copiar Link Mágico"><i class="ph ph-copy"></i></button>
                    </div>
                </div>`;
            }).join('');

            // Tabela Comparativa (Matriz)
            const ht = document.getElementById('head-comparativa');
            const bt = document.getElementById('body-comparativa');

            let ths = `<tr>
                <th style="min-width: 250px;">Produto</th>
            `;
            data.fornecedores.forEach(f => {
                ths += `<th class="text-right" style="min-width:120px; border-left: 2px solid var(--border-light);">${f.nome} (R$)</th>`;
            });
            ths += `</tr>`;
            ht.innerHTML = ths;

            let trs = ``;
            data.itens.forEach(item => {
                trs += `<tr>
                    <td><div style="font-weight:600; font-size:13px; white-space:normal;">${item.nome}</div></td>`;

                data.fornecedores.forEach(f => {
                    const preco = item.precos[f.ID];
                    const isWinner = (item.vencedor_id == f.ID); // se encerrado, o backend carimba quem é vencedor_id

                    let bg = ""; let fw = "normal"; let label = "";
                    if (isWinner) {
                        bg = "background: var(--success-light);"; fw = "bold"; label = "🏆 ";
                    }

                    trs += `<td class="text-right" style="border-left: 2px solid var(--border-light); ${bg} font-weight: ${fw};">
                        ${preco ? (label + Number(preco).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })) : '-'}
                    </td>`;
                });
                trs += `</tr>`;
            });
            bt.innerHTML = trs;

            document.getElementById('modal-res-cotacao').style.display = 'flex';
        } catch (e) {
            console.error(e);
            alert("Erro ao abrir painel.");
        }
    },

    fecharModalRes() {
        document.getElementById('modal-res-cotacao').style.display = 'none';
        this.cotacaoAbertaAtual = null;
    },

    async encerrarCotacao() {
        if (!confirm("Atenção! Ao encerrar, o sistema recalculará os vencedores descartando lançamentos em andamento. Continuar?")) return;

        try {
            await fetch(`/api/cotacoes/${this.cotacaoAbertaAtual.ID}/encerrar`, { method: 'POST' });
            // re-abre e recarrega
            this.abrirResultados(this.cotacaoAbertaAtual.ID);
            this.carregarListagem();
        } catch (e) {
            console.error(e);
            alert("Erro ao encerrar cotação.");
        }
    }
};
