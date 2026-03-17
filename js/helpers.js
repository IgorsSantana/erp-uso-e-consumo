/**
 * helpers.js - Funções utilitárias compartilhadas entre Views
 */

window.Helpers = {
    /**
     * Gera uma string HTML com os detalhes específicos da seção de um produto.
     * Retorna tags <div> com label:value para cada campo relevante.
     * @param {Object} prod - O objeto do produto com todos os campos.
     * @returns {string} HTML formatado com os detalhes da seção.
     */
    gerarDetalhesSecao(prod) {
        const secao = prod.secao || '';
        const parts = [];

        switch (secao) {
            case 'Embalagem':
                if (prod.destinacao) parts.push(`Uso: ${prod.destinacao}`);
                if (prod.ref_galvanoteck) parts.push(`Galvanoteck: ${prod.ref_galvanoteck}`);
                if (prod.ref_concorrente) parts.push(`Concorrente: ${prod.ref_concorrente}`);
                break;
            case 'Limpeza':
                if (prod.marca) parts.push(`Marca: ${prod.marca}`);
                if (prod.diluicao) parts.push(`Diluição: ${prod.diluicao}`);
                if (prod.rendimento) parts.push(`Rend.: ${prod.rendimento}`);
                if (prod.destinacao) parts.push(`Uso: ${prod.destinacao}`);
                break;
            case 'Escritório':
                if (prod.fornecedor) parts.push(`Forn.: ${prod.fornecedor}`);
                if (prod.destinacao) parts.push(`Uso: ${prod.destinacao}`);
                break;
            case 'Consumo Geral':
                if (prod.marca) parts.push(`Marca: ${prod.marca}`);
                if (prod.fornecedor) parts.push(`Forn.: ${prod.fornecedor}`);
                if (prod.referencia) parts.push(`Ref.: ${prod.referencia}`);
                break;
            case 'Açougue':
                if (prod.fornecedor) parts.push(`Forn.: ${prod.fornecedor}`);
                if (prod.destinacao) parts.push(`Uso: ${prod.destinacao}`);
                if (prod.referencia) parts.push(`Ref.: ${prod.referencia}`);
                break;
            default:
                if (prod.destinacao) parts.push(`Uso: ${prod.destinacao}`);
                if (prod.referencia) parts.push(`Ref.: ${prod.referencia}`);
                break;
        }

        if (parts.length === 0) return '<span style="color:var(--text-tertiary)">-</span>';

        return parts.map(p => `<span style="display:inline-block; font-size:11px; color:var(--text-secondary); background:var(--bg-main); padding:1px 6px; border-radius:4px; margin:1px 2px;">${p}</span>`).join('');
    }
};
