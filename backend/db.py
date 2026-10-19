"""SQLite persistence. No credentials or external database required."""
import sqlite3
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
 senha_hash TEXT NOT NULL, nivel_acesso TEXT NOT NULL CHECK(nivel_acesso IN ('Admin','Gestor','Operacional')),
 ativo INTEGER NOT NULL DEFAULT 1, auth_version INTEGER NOT NULL DEFAULT 1,
 criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS auth_sessions (id_hash TEXT PRIMARY KEY,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id), expires_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_auth_user ON auth_sessions(usuario_id);
CREATE TABLE IF NOT EXISTS lojas (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE, sigla TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS secoes (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS fornecedores (id INTEGER PRIMARY KEY, nome_fantasia TEXT NOT NULL,
 cnpj TEXT NOT NULL DEFAULT '', contato_nome TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
 telefone TEXT NOT NULL DEFAULT '', ativo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS produtos (id TEXT PRIMARY KEY, nome TEXT NOT NULL,
 secao_id INTEGER REFERENCES secoes(id), unidade TEXT NOT NULL DEFAULT 'UN', custo REAL NOT NULL DEFAULT 0 CHECK(custo>=0),
 estoque_minimo REAL NOT NULL DEFAULT 0 CHECK(estoque_minimo>=0), estoque_maximo REAL NOT NULL DEFAULT 0 CHECK(estoque_maximo>=0),
 referencia TEXT NOT NULL DEFAULT '', destinacao TEXT NOT NULL DEFAULT '', marca TEXT NOT NULL DEFAULT '',
 periodo_consumo TEXT NOT NULL DEFAULT 'Mensal', ativo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS estoque (produto_id TEXT REFERENCES produtos(id), loja_id INTEGER REFERENCES lojas(id),
 quantidade REAL NOT NULL DEFAULT 0 CHECK(quantidade>=0), PRIMARY KEY(produto_id,loja_id));
CREATE TABLE IF NOT EXISTS estoque_limites (
 produto_id TEXT NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
 loja_id INTEGER NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
 estoque_minimo REAL NOT NULL DEFAULT 0 CHECK(estoque_minimo>=0),
 estoque_maximo REAL NOT NULL DEFAULT 0 CHECK(estoque_maximo>=0),
 atualizado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 PRIMARY KEY(produto_id,loja_id), CHECK(estoque_maximo=0 OR estoque_maximo>=estoque_minimo));
CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, loja_id INTEGER NOT NULL REFERENCES lojas(id),
 loja_origem_id INTEGER NOT NULL REFERENCES lojas(id), status TEXT NOT NULL DEFAULT 'Pendente', total REAL NOT NULL,
 observacoes TEXT NOT NULL DEFAULT '', usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS pedido_itens (pedido_id INTEGER REFERENCES pedidos(id), produto_id TEXT REFERENCES produtos(id),
 quantidade REAL NOT NULL CHECK(quantidade>0), custo_unitario REAL NOT NULL CHECK(custo_unitario>=0), PRIMARY KEY(pedido_id,produto_id));
CREATE TABLE IF NOT EXISTS movimentacoes (id INTEGER PRIMARY KEY, tipo TEXT NOT NULL, produto_id TEXT NOT NULL REFERENCES produtos(id),
 loja_id INTEGER NOT NULL REFERENCES lojas(id), quantidade REAL NOT NULL, saldo_anterior REAL NOT NULL, saldo_atual REAL NOT NULL,
 motivo TEXT NOT NULL, usuario_id INTEGER REFERENCES usuarios(id), pedido_id INTEGER REFERENCES pedidos(id), custo_unitario REAL NOT NULL DEFAULT 0,
 criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS contagens (id INTEGER PRIMARY KEY, loja_id INTEGER NOT NULL REFERENCES lojas(id), motivo TEXT NOT NULL,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id), criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS contagem_itens (contagem_id INTEGER REFERENCES contagens(id), produto_id TEXT REFERENCES produtos(id),
 anterior REAL NOT NULL, contado REAL NOT NULL, diferenca REAL NOT NULL, PRIMARY KEY(contagem_id,produto_id));
CREATE TABLE IF NOT EXISTS cotacoes (id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Aberta',
 data_limite TEXT, observacoes TEXT NOT NULL DEFAULT '', usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS cotacao_itens (cotacao_id INTEGER REFERENCES cotacoes(id), produto_id TEXT REFERENCES produtos(id),
 quantidade REAL NOT NULL CHECK(quantidade>0), PRIMARY KEY(cotacao_id,produto_id));
CREATE TABLE IF NOT EXISTS cotacao_fornecedores (cotacao_id INTEGER REFERENCES cotacoes(id), fornecedor_id INTEGER REFERENCES fornecedores(id),
 token TEXT NOT NULL UNIQUE, preencheu INTEGER NOT NULL DEFAULT 0, observacoes TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(cotacao_id,fornecedor_id));
CREATE TABLE IF NOT EXISTS respostas (cotacao_id INTEGER, fornecedor_id INTEGER, produto_id TEXT REFERENCES produtos(id),
 preco REAL NOT NULL CHECK(preco>=0), prazo_entrega INTEGER NOT NULL DEFAULT 0, observacoes TEXT NOT NULL DEFAULT '',
 indisponivel INTEGER NOT NULL DEFAULT 0, vencedor INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(cotacao_id,fornecedor_id,produto_id),
 FOREIGN KEY(cotacao_id,fornecedor_id) REFERENCES cotacao_fornecedores(cotacao_id,fornecedor_id),
 FOREIGN KEY(cotacao_id,produto_id) REFERENCES cotacao_itens(cotacao_id,produto_id));
CREATE TABLE IF NOT EXISTS compras (id INTEGER PRIMARY KEY, fornecedor_id INTEGER NOT NULL REFERENCES fornecedores(id),
 loja_id INTEGER NOT NULL REFERENCES lojas(id), cotacao_id INTEGER REFERENCES cotacoes(id), status TEXT NOT NULL DEFAULT 'Pendente',
 total REAL NOT NULL, observacoes TEXT NOT NULL DEFAULT '', usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
 criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), recebido_em TEXT,
 UNIQUE(cotacao_id,fornecedor_id));
CREATE TABLE IF NOT EXISTS compra_itens (compra_id INTEGER REFERENCES compras(id), produto_id TEXT REFERENCES produtos(id),
 quantidade REAL NOT NULL CHECK(quantidade>0), custo_unitario REAL NOT NULL CHECK(custo_unitario>=0),PRIMARY KEY(compra_id,produto_id));
CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY, usuario_id INTEGER REFERENCES usuarios(id), acao TEXT NOT NULL,
 entidade TEXT NOT NULL, entidade_id TEXT NOT NULL, detalhes TEXT NOT NULL DEFAULT '',
 criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS login_attempts (chave TEXT PRIMARY KEY, falhas INTEGER NOT NULL, bloqueado_ate REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_mov_loja_data ON movimentacoes(loja_id,criado_em);
CREATE INDEX IF NOT EXISTS idx_pedido_status ON pedidos(status);
"""

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=20)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=20000')
    return g.db


def initialize(app):
    with app.app_context():
        db = get_db()
        db.execute('PRAGMA journal_mode=WAL')
        fresh = db.execute('PRAGMA user_version').fetchone()[0] == 0
        db.executescript(SCHEMA)
        if 'custo_unitario' not in [row[1] for row in db.execute('PRAGMA table_info(movimentacoes)')]:
            db.execute('ALTER TABLE movimentacoes ADD COLUMN custo_unitario REAL NOT NULL DEFAULT 0')
            db.commit()
        if fresh:
            # Operational reference data only; imported product metadata never creates stock.
            for loja in [(1,'BCS','BCS'),(3,'SJN','SJN'),(4,'MEP','MEP'),(5,'FCL1','FCL1'),(6,'FCL2','FCL2'),(7,'FCL3','FCL3'),(8,'FCL4','FCL4')]:
                db.execute('INSERT OR IGNORE INTO lojas(id,nome,sigla) VALUES(?,?,?)',loja)
            for nome in ['Embalagem','Limpeza','Consumo Geral','Escritório','Açougue','Bobina PDV','Etiquetas','Bobina Estrela']:
                db.execute('INSERT OR IGNORE INTO secoes(nome) VALUES(?)',(nome,))
            db.execute('PRAGMA user_version=1')
            db.commit()
        try:
            from .stock_limits import migrate_limits
        except ImportError:
            from stock_limits import migrate_limits
        migrate_limits(db)
        if app.config.get('SEED_CATALOG',not app.testing):
            try:
                from .bundled_catalog import apply_catalog
            except ImportError:
                from bundled_catalog import apply_catalog
            apply_catalog(db)
            if app.config.get('APPLY_CATALOG_ADJUSTMENTS',True):
                try:
                    from .catalog_adjustments import apply_adjustments
                except ImportError:
                    from catalog_adjustments import apply_adjustments
                apply_adjustments(db)


def close_db(error=None):
    db = g.pop('db',None)
    if db is not None:
        db.close()
