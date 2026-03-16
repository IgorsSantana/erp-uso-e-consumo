window.Fornecedores = {
    dados: [],

    async init() {
        await this.carregarDados();
    },

    async carregarDados() {
        try {
            const res = await fetch('/api/fornecedores');
            this.dados = await res.json();
            this.renderizarTabela(this.dados);
        } catch (e) {
            console.error("Erro Fornecedores:", e);
        }
    },

    renderizarTabela(lista) {
        const tbody = document.querySelector('#tabela-fornecedores tbody');
        tbody.innerHTML = '';

        if (lista.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding: 30px; color: var(--text-tertiary);">Nenhum fornecedor cadastrado.</td></tr>`;
            return;
        }

        lista.forEach(f => {
            const tr = document.createElement('tr');

            const btnStatus = f.Ativo
                ? `<span class="badge badge-normal"><i class="badge-dot"></i> Ativo</span>`
                : `<span class="badge badge-critico"><i class="badge-dot"></i> Inativo</span>`;

            tr.innerHTML = `
                <td style="font-weight: 500;">${f.Nome_Fantasia}</td>
                <td>${f.CNPJ || '-'}</td>
                <td>
                    ${f.Contato_Nome ? `<div>${f.Contato_Nome}</div>` : ''}
                    <div style="font-size: 12px; color: var(--text-tertiary);">${f.Email || '-'}</div>
                </td>
                <td>${f.Telefone || '-'}</td>
                <td class="text-center">${btnStatus}</td>
                <td class="text-center">
                    <button class="btn" style="padding: 6px 10px; background: var(--primary-light); color: var(--primary);" onclick='window.Fornecedores.abrirModalEdicao(${JSON.stringify(f)})'><i class="ph ph-pencil-simple"></i></button>
                    <button class="btn" style="padding: 6px 10px; background: var(--danger-light); color: var(--danger);" onclick="window.Fornecedores.excluir(${f.ID})"><i class="ph ph-trash"></i></button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    filtrarTabela() {
        const query = document.getElementById('search-fornecedor').value.toLowerCase();
        const filtrados = this.dados.filter(f => f.Nome_Fantasia.toLowerCase().includes(query));
        this.renderizarTabela(filtrados);
    },

    abrirModalEdicao(f = null) {
        document.getElementById('forn-form-id').value = f ? f.ID : '';
        document.getElementById('forn-form-nome').value = f ? f.Nome_Fantasia : '';
        document.getElementById('forn-form-cnpj').value = f ? (f.CNPJ || '') : '';
        document.getElementById('forn-form-contato').value = f ? (f.Contato_Nome || '') : '';
        document.getElementById('forn-form-telefone').value = f ? (f.Telefone || '') : '';
        document.getElementById('forn-form-email').value = f ? (f.Email || '') : '';

        document.getElementById('modal-fornecedor-titulo').innerText = f ? "Editar Fornecedor" : "Novo Fornecedor";
        document.getElementById('modal-fornecedor').style.display = 'flex';
    },

    fecharModal() {
        document.getElementById('modal-fornecedor').style.display = 'none';
        document.getElementById('form-fornecedor').reset();
    },

    async salvar() {
        const id = document.getElementById('forn-form-id').value;
        const payload = {
            nome: document.getElementById('forn-form-nome').value,
            cnpj: document.getElementById('forn-form-cnpj').value,
            contato: document.getElementById('forn-form-contato').value,
            telefone: document.getElementById('forn-form-telefone').value,
            email: document.getElementById('forn-form-email').value
        };

        if (!payload.nome) { alert('Nome é obrigatório'); return; }

        const url = id ? `/api/fornecedores/${id}` : `/api/fornecedores`;
        const method = id ? 'PUT' : 'POST';

        try {
            await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            this.fecharModal();
            this.carregarDados();
        } catch (e) {
            console.error(e);
            alert("Erro ao salvar fornecedor.");
        }
    },

    async excluir(id) {
        if (!confirm("Atenção: Excluir fornecedor pode afetar cotações passadas. Deseja continuar?")) return;
        try {
            await fetch(`/api/fornecedores/${id}`, { method: 'DELETE' });
            this.carregarDados();
        } catch (e) {
            console.error(e);
            alert("Erro ao excluir.");
        }
    }
};
