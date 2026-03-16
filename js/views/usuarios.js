/**
 * usuarios.js - Gestão de Usuários (Admin)
 */

window.Usuarios = {
    listaCache: [],

    init() {
        console.log("Módulo Usuarios Inicializado.");
    },

    async carregarTabela() {
        try {
            const res = await fetch('/api/usuarios');
            if (res.ok) {
                const data = await res.json();
                this.listaCache = data;
                this.renderTabela(data);
            }
        } catch (err) {
            console.error("Erro ao carregar usuários:", err);
            alert("Falha de conexão com o servidor ao carregar usuários.");
        }
    },

    renderTabela(usuarios) {
        const tbody = document.querySelector('#tabela-usuarios tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (usuarios.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="padding: 20px; color: var(--text-secondary);">Nenhum usuário encontrado.</td></tr>`;
            return;
        }

        usuarios.forEach(u => {
            const dataCriacao = new Date(u.Data_Criacao).toLocaleDateString('pt-BR');
            let badgeHtml = '';
            if (u.Nivel_Acesso === 'Admin') badgeHtml = '<span class="badge badge-danger">Admin</span>';
            else badgeHtml = '<span class="badge badge-normal">Operacional</span>';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${u.Nome}</strong></td>
                <td style="color: var(--text-secondary);">${u.Username}</td>
                <td class="text-center">${badgeHtml}</td>
                <td class="text-center">${dataCriacao}</td>
                <td class="text-center">
                    <div style="display:flex; gap: 8px; justify-content:center;">
                        <button class="action-btn" title="Editar Usuário" onclick="window.Usuarios.editarUsuario(${u.ID})">
                            <i class="ph ph-pencil-simple" style="color:var(--primary)"></i>
                        </button>
                        <button class="action-btn" title="Excluir" onclick="window.Usuarios.excluirUsuario(${u.ID}, '${u.Username}')">
                            <i class="ph ph-trash" style="color:var(--danger)"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    filtrarTabela() {
        const termo = document.getElementById('search-usuario').value.toLowerCase();
        const filtrada = this.listaCache.filter(u =>
            u.Nome.toLowerCase().includes(termo) ||
            u.Username.toLowerCase().includes(termo)
        );
        this.renderTabela(filtrada);
    },

    abrirModalNovo() {
        document.getElementById('modal-usuario-titulo').innerText = 'Novo Usuário';
        document.getElementById('form-usuario').reset();
        document.getElementById('usr-id').value = '';
        document.getElementById('usr-senha-asterisk').style.display = 'inline';
        document.getElementById('usr-senha-hint').style.display = 'none';

        // Senha obrigatória na criação
        document.getElementById('usr-senha').required = true;

        document.getElementById('modal-usuario').style.display = 'flex';
    },

    editarUsuario(id) {
        const usr = this.listaCache.find(u => u.ID === id);
        if (!usr) return;

        document.getElementById('modal-usuario-titulo').innerText = 'Editar Usuário';
        document.getElementById('usr-id').value = usr.ID;
        document.getElementById('usr-nome').value = usr.Nome;
        document.getElementById('usr-username').value = usr.Username;
        document.getElementById('usr-nivel').value = usr.Nivel_Acesso;
        document.getElementById('usr-senha').value = '';

        // Senha opcional na edição
        document.getElementById('usr-senha').required = false;
        document.getElementById('usr-senha-asterisk').style.display = 'none';
        document.getElementById('usr-senha-hint').style.display = 'block';

        document.getElementById('modal-usuario').style.display = 'flex';
    },

    fecharModal() {
        document.getElementById('modal-usuario').style.display = 'none';
    },

    async salvar() {
        const id = document.getElementById('usr-id').value;
        const nome = document.getElementById('usr-nome').value;
        const username = document.getElementById('usr-username').value;
        const nivel_acesso = document.getElementById('usr-nivel').value;
        const password = document.getElementById('usr-senha').value;

        const payload = { nome, username, nivel_acesso };
        if (password) payload.password = password;

        try {
            let url = '/api/usuarios';
            let method = 'POST';

            if (id) {
                // Modo Edição
                url = `/api/usuarios/${id}`;
                method = 'PUT';
            }

            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (!res.ok) {
                alert(data.error || 'Erro ao processar requisição.');
                return;
            }

            this.fecharModal();
            this.carregarTabela(); // Recarrega lista

        } catch (err) {
            console.error(err);
            alert("Falha de conexão com o servidor.");
        }
    },

    async excluirUsuario(id, username) {
        if (username === 'admin') {
            alert("Ação Bloqueada: Não é permitido excluir o usuário Administrador principal.");
            return;
        }

        const sessionUser = JSON.parse(localStorage.getItem('erp_user'));
        if (sessionUser && sessionUser.username === username) {
            alert("Ação Bloqueada: Você não pode excluir a sua própria conta logada.");
            return;
        }

        const conf = confirm(`ATENÇÃO: Deseja realmente excluir permanentemente o usuário '${username}'?`);
        if (!conf) return;

        try {
            const res = await fetch(`/api/usuarios/${id}`, { method: 'DELETE' });
            const data = await res.json();

            if (!res.ok) {
                alert(data.error || 'Erro ao excluir usuário.');
                return;
            }

            this.carregarTabela();

        } catch (err) {
            console.error(err);
            alert("Falha de conexão com o servidor.");
        }
    }
};
