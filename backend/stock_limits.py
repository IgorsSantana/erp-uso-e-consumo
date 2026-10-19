"""Independent stock thresholds for each product/store; balances remain untouched."""

WORKBOOK_STORES = ('BCS', 'SJN', 'MEP', 'FCL1', 'FCL2', 'FCL3', 'FCL4')


def migrate_limits(db):
    """Copy the old threshold to existing stores once, then remove any global fallback."""
    db.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    db.commit()
    with db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM schema_migrations WHERE name='stock_limits_by_store_v1'").fetchone():
            return
        db.execute('''INSERT OR IGNORE INTO estoque_limites(produto_id,loja_id,estoque_minimo,estoque_maximo)
          SELECT p.id,l.id,p.estoque_minimo,p.estoque_maximo FROM produtos p CROSS JOIN lojas l
          WHERE p.estoque_minimo>0 OR p.estoque_maximo>0''')
        db.execute("INSERT INTO schema_migrations(name) VALUES('stock_limits_by_store_v1')")


def save_limit(db,pid,sid,minimum,maximum):
    db.execute('''INSERT INTO estoque_limites(produto_id,loja_id,estoque_minimo,estoque_maximo) VALUES(?,?,?,?)
      ON CONFLICT(produto_id,loja_id) DO UPDATE SET estoque_minimo=excluded.estoque_minimo,
      estoque_maximo=excluded.estoque_maximo,atualizado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now')''',
      (pid,sid,minimum,maximum))
