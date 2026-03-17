/**
 * app.js - Arquivo de Inicialização e Roteamento SPA
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Carrega a preferência de Sidebar Colapsável
    const isSidebarCollapsed = localStorage.getItem('sidebar_collapsed') === 'true';
    if (isSidebarCollapsed) {
        document.body.classList.add('sidebar-collapsed');
    }

    const toggleBtn = document.getElementById('btn-toggle-sidebar');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            document.body.classList.toggle('sidebar-collapsed');
            localStorage.setItem('sidebar_collapsed', document.body.classList.contains('sidebar-collapsed'));
        });
    }

    // Carrega dados do usuário logado
    const sessionUser = JSON.parse(localStorage.getItem('erp_user'));
    if (sessionUser) {
        document.getElementById('auth-user-name').innerText = sessionUser.nome;
        document.getElementById('auth-user-role').innerText = sessionUser.nivel_acesso;

        // Show Admin Tab if applicable
        if (sessionUser.nivel_acesso === 'Admin') {
            const btnUsers = document.getElementById('nav-btn-usuarios');
            if (btnUsers) btnUsers.style.display = 'flex';
        }
    }

    // Exporta Auth Globais
    window.Auth = {
        logout: () => {
            localStorage.removeItem('erp_user');
            window.location.href = 'login.html';
        }
    };

    // Atualiza Data no Topbar
    const currentDateEl = document.getElementById('current-date');
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    currentDateEl.innerHTML = new Date().toLocaleDateString('pt-BR', options);

    // Carrega todos os repositórios da nuvem (TiDB via API Flask)
    await window.Store.fetchInitialData();
    await window.Store.fetchProdutos();
    await window.Store.fetchEstoqueGlobal();

    // Inicializa Views Individuais
    window.Pedidos.init();
    window.Estoque.init();
    window.Produtos.init();
    if (window.Fornecedores) window.Fornecedores.init();
    if (window.Cotacoes) window.Cotacoes.init();
    if (window.Contagem) window.Contagem.init();
    if (window.Usuarios) window.Usuarios.init();

    // Configuração do "Router" (Troca de abas)
    const navItems = document.querySelectorAll('.nav-item');
    const pageTitle = document.getElementById('page-title');

    navItems.forEach(item => {
        item.addEventListener('click', async () => {
            // 1. Remove active
            navItems.forEach(nav => nav.classList.remove('active'));
            document.querySelectorAll('.view').forEach(view => view.classList.remove('active'));

            // 2. Add active no botao
            item.classList.add('active');

            // 3. Mostra view e atualiza título
            const viewName = item.getAttribute('data-view');
            document.getElementById(`view-${viewName}`).classList.add('active');

            if (viewName === 'pedidos') {
                pageTitle.innerText = "Fazer Pedido em Lote";
                await window.Store.fetchProdutos(); // refresh the items before loading
                window.Pedidos.verificarPainel();
            } else if (viewName === 'estoque') {
                pageTitle.innerText = "Matriz Geral de Estoque";
                await window.Store.fetchEstoqueGlobal();
                window.Estoque.carregarDados();
                window.Estoque.renderizarMatrizCompleta();
            } else if (viewName === 'produtos') {
                pageTitle.innerText = "Cadastro de Produtos";
                await window.Store.fetchProdutos();
                window.Produtos.carregarTabela();
            } else if (viewName === 'fornecedores') {
                pageTitle.innerText = "Base de Fornecedores";
                window.Fornecedores.carregarDados();
            } else if (viewName === 'cotacoes') {
                pageTitle.innerText = "Portal de Cotações / Resultados";
                window.Cotacoes.carregarListagem();
            } else if (viewName === 'contagem') {
                pageTitle.innerText = "Contagem de Estoque Global";
                await window.Store.fetchEstoqueGlobal();
                window.Contagem.verificarPainel();
            } else if (viewName === 'usuarios') {
                pageTitle.innerText = "Gestão de Usuários (Acesso Administrativo)";
                window.Usuarios.carregarTabela();
            }
        });
    });

    // Auto-Routing Baseado em Dispositivo
    if (window.innerWidth <= 768) {
        document.querySelector('.nav-item[data-view="contagem"]')?.click();
    } else {
        document.querySelector('.nav-item[data-view="estoque"]')?.click();
    }

    console.log("== Micro-ERP Inicializado ==");
});
