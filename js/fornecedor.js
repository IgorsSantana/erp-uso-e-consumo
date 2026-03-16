const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');

let itensList = [];

// Funcao Auxiliar para Formatar Moeda
const formatCurrency = (val) => {
    return Number(val).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

async function init() {
    if (!token) {
        showError("Acesso restrito. Token não fornecido na URL.");
        return;
    }

    try {
        const res = await fetch(`/api/portal-fornecedor/${token}`);
        if (!res.ok) {
            const err = await res.json();
            showError(err.error || "Link inválido ou expirado.");
            return;
        }

        const data = await res.json();

        // Hide loading
        document.getElementById('loading').style.display = 'none';

        if (data.cotacao.Status !== 'Aberta') {
            showError(`Atenção: Esta cotação se encontra ENCERRADA. Não é possível enviar novos lances.`);
            return;
        }

        // Populate View
        document.getElementById('view-titulo').innerText = data.cotacao.Titulo;
        document.getElementById('view-fornecedor-nome').innerText = data.fornecedor_nome;

        if (data.preencheu) {
            document.getElementById('alert-preencheu-aviso').style.display = 'block';
        }

        itensList = data.itens;
        const container = document.getElementById('lista-itens');

        data.itens.forEach((item, index) => {
            const oldValue = data.respostas[item.id] || '';
            const html = `
                <div class="item-card">
                    <div class="item-info">
                        <h4>${item.nome}</h4>
                        <span>Código Ref: ${item.id}</span>
                    </div>
                    <div class="item-input">
                        <label style="font-size:12px; font-weight:600; color:var(--text-secondary); display:block; margin-bottom: 4px;">Seu Preço Unit. (R$)</label>
                        <input type="number" id="preco-${item.id}" step="0.01" min="0" placeholder="0,00" value="${oldValue}" oninput="atualizarContador()">
                    </div>
                </div>
            `;
            container.innerHTML += html;
        });

        document.getElementById('cotacao-content').style.display = 'block';
        atualizarContador();

    } catch (e) {
        console.error(e);
        showError("Não foi possível conectar ao servidor. Tente novamente mais tarde.");
    }
}

function atualizarContador() {
    let preenchidos = 0;
    itensList.forEach(item => {
        const p = parseFloat(document.getElementById(`preco-${item.id}`).value);
        if (!isNaN(p) && p > 0) preenchidos++;
    });
    document.getElementById('total-cotacao').innerText = `Itens preenchidos: ${preenchidos} / ${itensList.length}`;
}

async function enviarProposta() {
    const respostas = [];

    itensList.forEach(item => {
        const p = parseFloat(document.getElementById(`preco-${item.id}`).value);
        if (!isNaN(p) && p > 0) {
            respostas.push({ produto_id: item.id, preco: p });
        }
    });

    if (respostas.length === 0) {
        alert("Atenção: Você precisa informar o preço de ao menos um item para enviar a proposta.");
        return;
    }

    const btn = document.getElementById('btn-enviar');
    btn.innerText = "Enviando...";
    btn.disabled = true;

    try {
        const res = await fetch(`/api/portal-fornecedor/${token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ respostas })
        });

        if (res.ok) {
            document.getElementById('cotacao-content').style.display = 'none';
            document.getElementById('success-box').style.display = 'block';
        } else {
            const err = await res.json();
            alert(err.error || "Ocorreu um erro no envio. Tente novamente.");
            btn.innerText = "Tentar Novamente";
            btn.disabled = false;
        }
    } catch (e) {
        console.error(e);
        alert("Erro de conexão ao enviar a proposta.");
        btn.innerText = "Tentar Novamente";
        btn.disabled = false;
    }
}

function showError(msg) {
    document.getElementById('loading').style.display = 'none';
    const b = document.getElementById('error-box');
    b.innerText = msg;
    b.style.display = 'block';
}

// Auto-init
document.addEventListener('DOMContentLoaded', init);
