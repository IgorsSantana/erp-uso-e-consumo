"""Apply reviewed workbook limits once, after the products have been installed."""
import json
from pathlib import Path
import re

try:
    from .catalog_csv import decimal_cell, normalized
    from .stock_limits import save_limit, WORKBOOK_STORES as STORES
except ImportError:
    from catalog_csv import decimal_cell, normalized
    from stock_limits import save_limit, WORKBOOK_STORES as STORES

LIMITS = Path(__file__).with_name('data')/'limites_lojas_20261019.json'


def read_limits(path=LIMITS):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(data.get('version', ''))):
        raise ValueError('Revisão de limites inválida.')
    if not re.fullmatch(r'[a-f0-9]{64}', str(data.get('source_sha256', ''))):
        raise ValueError('Hash de origem inválido.')
    scope = data.get('scope')
    if not isinstance(scope, list) or len(scope) > 5000:
        raise ValueError('Produtos da revisão inválidos.')
    if any(not isinstance(pid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,20}', pid) for pid in scope):
        raise ValueError('Código de produto inválido.')
    if len(set(scope)) != len(scope):
        raise ValueError('Produto duplicado na revisão.')
    pairs = data.get('limits')
    if not isinstance(pairs, list) or len(pairs) > 35000:
        raise ValueError('Lista de limites inválida.')
    seen = set()
    for pair in pairs:
        if not isinstance(pair, dict) or pair.get('id') not in scope or pair.get('store') not in STORES:
            raise ValueError('Produto ou loja inválidos na revisão.')
        key = (pair['id'], pair['store'])
        if key in seen:
            raise ValueError('Limite duplicado na revisão.')
        seen.add(key)
        for field in ('estoque_minimo', 'estoque_maximo'):
            pair[field] = decimal_cell(str(pair.get(field)), field)
        if pair['estoque_maximo'] and pair['estoque_minimo'] > pair['estoque_maximo']:
            raise ValueError('Mínimo maior que máximo na revisão.')
        if not isinstance(pair.get('unidade'), str) or not 1 <= len(pair['unidade']) <= 12:
            raise ValueError('Unidade inválida na revisão.')
    return data


def manual_settings(db):
    """Protect explicit edits, including zero limits and deleted configurations."""
    pairs = set()
    stores = set()
    for row in db.execute("SELECT acao,entidade_id,detalhes FROM auditoria WHERE entidade='produtos' AND acao IN ('configurar_limites','importar')"):
        try:
            detail = json.loads(row['detalhes'])
            if row['acao'] == 'configurar_limites':
                for item in detail:
                    pairs.add((row['entidade_id'], int(item['loja_id'])))
            elif detail.get('loja_limites_id') is not None and detail.get('limites_atualizados', 0):
                # Older CSV audits identify the store but not individual SKUs;
                # conservatively preserve every existing choice in that store.
                stores.add(int(detail['loja_limites_id']))
        except (ValueError, TypeError, KeyError, AttributeError):
            # An unreadable historical audit must not authorize replacements.
            if row['acao'] == 'configurar_limites':
                pairs.update((row['entidade_id'], sid[0]) for sid in db.execute('SELECT id FROM lojas'))
            else:
                stores.update(sid[0] for sid in db.execute('SELECT id FROM lojas'))
    return pairs, stores


def apply_limits(db, path=LIMITS):
    patch = read_limits(path)
    if db.in_transaction:
        raise RuntimeError('A revisão de limites exige uma transação própria.')
    db.execute('''CREATE TABLE IF NOT EXISTS stock_limit_releases (
      version TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,resultado TEXT NOT NULL,
      aplicado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    with db:
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT resultado FROM stock_limit_releases WHERE version=?', (patch['version'],)).fetchone()
        if previous:
            return {**json.loads(previous['resultado']), 'aplicado': False}
        result = {'criados': 0, 'corrigidos': 0, 'copias_globais_removidas': 0,
                  'personalizacoes_preservadas': 0, 'produtos_ausentes': [],
                  'lojas_ausentes_ou_ambiguas': [], 'unidades_para_revisao': []}
        store_ids = {}
        stores = db.execute('SELECT id,sigla FROM lojas').fetchall()
        for code in STORES:
            matches = [store['id'] for store in stores if normalized(store['sigla']) == normalized(code)]
            if len(matches) == 1:
                store_ids[code] = matches[0]
            else:
                result['lojas_ausentes_ou_ambiguas'].append(code)
        targets = {(pair['id'], pair['store']): pair for pair in patch['limits']}
        protected_pairs, protected_stores = manual_settings(db)
        for pid in patch['scope']:
            product = db.execute('SELECT unidade FROM produtos WHERE id=?', (pid,)).fetchone()
            if product is None:
                result['produtos_ausentes'].append(pid)
                continue
            for code, sid in store_ids.items():
                pair = targets.get((pid, code))
                current = db.execute('SELECT * FROM estoque_limites WHERE produto_id=? AND loja_id=?', (pid, sid)).fetchone()
                if (sid in protected_stores and current is not None) or (pid, sid) in protected_pairs:
                    if current or pair:
                        result['personalizacoes_preservadas'] += 1
                    continue
                if pair and product['unidade'] != pair['unidade']:
                    if pid not in result['unidades_para_revisao']:
                        result['unidades_para_revisao'].append(pid)
                    continue
                # Identify only untouched copies from the previous automatic
                # migration: exact global values AND migration timestamp.
                legacy = current and db.execute('''SELECT 1 FROM produtos p JOIN schema_migrations m
                  ON m.name='stock_limits_by_store_v1' WHERE p.id=? AND p.estoque_minimo=? AND p.estoque_maximo=?
                  AND datetime(m.applied_at)=datetime(?)''',
                  (pid, current['estoque_minimo'], current['estoque_maximo'], current['atualizado_em'])).fetchone()
                if pair:
                    if current is None or legacy or (current['estoque_minimo'] == 0 and current['estoque_maximo'] == 0):
                        save_limit(db, pid, sid, pair['estoque_minimo'], pair['estoque_maximo'])
                        result['corrigidos' if current else 'criados'] += 1
                    else:
                        result['personalizacoes_preservadas'] += 1
                elif legacy:
                    db.execute('DELETE FROM estoque_limites WHERE produto_id=? AND loja_id=?', (pid, sid))
                    result['copias_globais_removidas'] += 1
        details = json.dumps(result, ensure_ascii=False)
        db.execute('INSERT INTO auditoria(acao,entidade,entidade_id,detalhes) VALUES(?,?,?,?)',
                   ('importar_limites_lojas', 'estoque_limites', patch['version'], details))
        db.execute('INSERT INTO stock_limit_releases(version,source_sha256,resultado) VALUES(?,?,?)',
                   (patch['version'], patch['source_sha256'], details))
    return {**result, 'aplicado': True}
