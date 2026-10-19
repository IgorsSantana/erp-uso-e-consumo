"""Apply the reviewed Excel correction once, without replacing later user edits.

Each field includes the previous catalog value and the confirmed spreadsheet
value. Only matching previous values are corrected; operational data and
store-specific thresholds are outside this revision.
"""
import json
from pathlib import Path
import re
from decimal import Decimal,InvalidOperation

try:
    from .catalog_csv import import_rows,normalized,LIMITS
except ImportError:
    from catalog_csv import import_rows,normalized,LIMITS

PATCH = Path(__file__).with_name('data')/'ajustes_catalogo_20261019.json'
FIELDS = {'nome','secao','unidade','custo','periodo_consumo','destinacao','marca','referencia'}


def read_adjustments(path=PATCH):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(data.get('version',''))):
        raise ValueError('Identificador de revisão inválido.')
    if not re.fullmatch(r'[a-f0-9]{64}',str(data.get('source_sha256',''))):
        raise ValueError('Hash da origem inválido.')
    changes=data.get('changes')
    if not isinstance(changes,list) or not 1<=len(changes)<=5000:
        raise ValueError('Lista de ajustes inválida.')
    seen=set()
    for change in changes:
        if not isinstance(change,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,20}',str(change.get('id',''))):
            raise ValueError('Código de produto inválido.')
        if change['id'] in seen:raise ValueError('Produto duplicado na revisão.')
        seen.add(change['id'])
        fields=change.get('campos')
        if not isinstance(fields,dict) or not fields or not set(fields).issubset(FIELDS):
            raise ValueError('A revisão contém campos não permitidos.')
        for field,pair in fields.items():
            if not isinstance(pair,dict) or set(pair)!= {'antes','depois'}:
                raise ValueError('Valores de ajuste inválidos.')
            if field=='custo':
                try:
                    value=Decimal(str(pair['depois']))
                    if not value.is_finite() or value<0 or value>1_000_000_000 or value!=value.quantize(Decimal('.01')):
                        raise ValueError('Custo inválido.')
                except InvalidOperation as error:
                    raise ValueError('Custo inválido.') from error
            else:
                value=pair['depois']
                if not isinstance(value,str) or len(value)>LIMITS[field] or (field in ('nome','secao','unidade','periodo_consumo') and not value.strip()):
                    raise ValueError('Texto do ajuste inválido.')
    return data


def equal(field,first,second):
    return normalized(first or '')==normalized(second or '') if field=='secao' else first==second


def apply_adjustments(connection,path=PATCH):
    patch=read_adjustments(path)
    if connection.in_transaction:
        raise RuntimeError('A revisão precisa iniciar fora de outra transação.')
    connection.execute('''CREATE TABLE IF NOT EXISTS catalog_adjustments (
      version TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,resultado TEXT NOT NULL,
      aplicado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        previous=connection.execute('SELECT resultado FROM catalog_adjustments WHERE version=?',(patch['version'],)).fetchone()
        if previous:
            return {**json.loads(previous['resultado']),'aplicado':False}
        pending=[];field_count=0;preserved=[];unit_review=[];missing=[];aligned=0
        for change in patch['changes']:
            pid=change['id']
            current=connection.execute('SELECT p.*,s.nome AS secao FROM produtos p LEFT JOIN secoes s ON s.id=p.secao_id WHERE p.id=?',(pid,)).fetchone()
            if current is None:
                missing.append(pid)
                continue
            updates={'id':pid}
            for field,pair in change['campos'].items():
                if equal(field,current[field],pair['depois']):
                    continue
                if not equal(field,current[field],pair['antes']):
                    preserved.append({'id':pid,'campo':field})
                    continue
                if field=='unidade' and (connection.execute('SELECT 1 FROM estoque WHERE produto_id=? AND quantidade>0',(pid,)).fetchone()
                                        or connection.execute('SELECT 1 FROM movimentacoes WHERE produto_id=?',(pid,)).fetchone()
                                        or connection.execute('SELECT 1 FROM estoque_limites WHERE produto_id=? AND (estoque_minimo>0 OR estoque_maximo>0)',(pid,)).fetchone()):
                    unit_review.append(pid)
                    continue
                updates[field]=pair['depois']
                field_count+=1
            if len(updates)>1:pending.append(updates)
            else:aligned+=1
        counts={'criados':0,'atualizados':0,'preservados':0,'secoes_criadas':0}
        if pending:
            counts=import_rows(connection,pending,update_existing=True,origin=patch['version'])
        result={**counts,'campos_atualizados':field_count,'ja_alinhados_ou_preservados':aligned,
                'personalizacoes_preservadas':preserved,'unidades_para_revisao':unit_review,'produtos_ausentes':missing}
        if preserved or unit_review or missing:
            connection.execute('INSERT INTO auditoria(acao,entidade,entidade_id,detalhes) VALUES(?,?,?,?)',
                               ('revisar_catalogo','produtos',patch['version'],json.dumps(result,ensure_ascii=False)))
        connection.execute('INSERT INTO catalog_adjustments(version,source_sha256,resultado) VALUES(?,?,?)',
                           (patch['version'],patch['source_sha256'],json.dumps(result,ensure_ascii=False)))
    return {**result,'aplicado':True}
