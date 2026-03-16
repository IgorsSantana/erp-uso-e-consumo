/**
 * store.js - Camada de Dados conectada na API Python
 */

const API_BASE = '/api';

window.Store = {
    lojas: [],
    produtos: [],
    estoqueGlobal: [],
    secoes: [],

    // ==========================================
    // DATA FETCHERS
    // ==========================================

    async fetchInitialData() {
        try {
            const [resLojas, resSecoes] = await Promise.all([
                fetch(`${API_BASE}/lojas`),
                fetch(`${API_BASE}/secoes`)
            ]);
            this.lojas = await resLojas.json();
            this.secoes = await resSecoes.json();
        } catch (e) {
            console.error("Erro ao carregar dados iniciais (Lojas/Seções)", e);
        }
    },

    async fetchProdutos() {
        try {
            const res = await fetch(`${API_BASE}/produtos`);
            this.produtos = await res.json();
        } catch (e) {
            console.error("Erro ao buscar produtos", e);
        }
    },

    async fetchEstoqueGlobal() {
        try {
            const res = await fetch(`${API_BASE}/estoque/matriz`);
            this.estoqueGlobal = await res.json();
        } catch (e) {
            console.error("Erro ao carregar matriz de estoque", e);
        }
    },

    // ==========================================
    // GETTERS (Sync after fetch)
    // ==========================================

    getLojas() { return this.lojas; },
    getSecoes() { return this.secoes; },
    getProdutos() { return this.produtos; },
    getEstoqueGlobal() { return this.estoqueGlobal; },

    // ==========================================
    // MÉTODOS CRUD ASSÍNCRONOS
    // ==========================================

    async salvarProduto(dados, isEdicao) {
        try {
            const url = isEdicao ? `${API_BASE}/produtos/${dados.id}` : `${API_BASE}/produtos`;
            const method = isEdicao ? 'PUT' : 'POST';

            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dados)
            });

            if (!res.ok) {
                const erro = await res.json();
                throw new Error(erro.error || "Erro desconhecido");
            }

            return true;
        } catch (e) {
            console.error("Erro ao salvar produto:", e);
            alert("Erro ao salvar: " + e.message);
            return false;
        }
    },

    async excluirProduto(idProduto) {
        try {
            const res = await fetch(`${API_BASE}/produtos/${idProduto}`, {
                method: 'DELETE'
            });

            if (!res.ok) throw new Error("Falha ao excluir");
            return true;
        } catch (e) {
            console.error("Erro ao excluir produto:", e);
            alert("Erro ao excluir: " + e.message);
            return false;
        }
    },

    // Apenas simula o ajuste local antes do envio no Bulk (já estávamos fazendo isso no pedidos.js mockado)
    ajustarEstoque(lojaId, produtoId, qtdeAjuste) {
        // Implementação para ajuste assincrono se precisar
        // Deixando mock para funcionar localmente enquanto não criamos o endpoint de Pedidos no Python
        console.log(`[Mock] Estoque ajustado: Loja ${lojaId}, Prod ${produtoId}, Ajuste ${qtdeAjuste}`);
    }
};
