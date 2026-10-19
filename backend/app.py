"""ERP de Uso e Consumo: authenticated, transactional, self-contained API."""
import csv
import datetime as dt
import functools
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, g, jsonify, request, session, send_from_directory, Response
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
try:
    from .db import get_db, initialize, close_db
except ImportError:
    from db import get_db, initialize, close_db

ROOT = Path(__file__).resolve().parent.parent
MANAGERS = ('Admin','Gestor')

def today():
    return dt.datetime.now(ZoneInfo(os.environ.get('ERP_TIMEZONE','America/Sao_Paulo'))).date()

class APIError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def rows(sql, params=()):
    return [dict(r) for r in get_db().execute(sql, params).fetchall()]

def one(sql, params=(), message='Registro não encontrado.'):
    row = get_db().execute(sql, params).fetchone()
    if row is None:
        raise APIError(message,404)
    return dict(row)

def text(data, key, required=False, maximum=200):
    value = data.get(key,'')
    if value is None and not required:
        value = ''
    if not isinstance(value,str):
        raise APIError(f'{key}: informe um texto.')
    value = value.strip()
    if (required and not value) or len(value)>maximum:
        raise APIError(f'{key}: campo obrigatório ou tamanho inválido (máximo {maximum}).')
    return value

def number(value, field='quantidade', minimum=0, maximum=1000000000, places=3):
    try:
        if isinstance(value,bool):
            raise ValueError()
        n = Decimal(str(value))
        if not n.is_finite() or n<Decimal(str(minimum)) or n>Decimal(str(maximum)):
            raise ValueError()
        quantized = n.quantize(Decimal(10)**-places,rounding=ROUND_HALF_UP)
        if n != quantized:
            raise APIError(f'{field}: use no máximo {places} casas decimais.')
        return float(quantized)
    except (ValueError,InvalidOperation,TypeError):
        raise APIError(f'{field}: número inválido; intervalo {minimum} a {maximum}.')

def ident(value, field='id'):
    n = number(value,field,1,2147483647,0)
    return int(n)

def flag(value):
    if value not in (True,False,0,1):
        raise APIError('Valor booleano inválido.')
    return int(bool(value))

def body():
    data = request.get_json(silent=True)
    if not isinstance(data,dict):
        raise APIError('Envie um objeto JSON válido.')
    return data

def audit(action, entity, entity_id, details=''):
    user = getattr(g,'user',None)
    get_db().execute('INSERT INTO auditoria(usuario_id,acao,entidade,entidade_id,detalhes) VALUES(?,?,?,?,?)',
                     (user['id'] if user else None,action,entity,str(entity_id),details))

def require(*roles):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            if not g.user:
                raise APIError('Entre na sua conta para continuar.',401)
            if roles and g.user['nivel_acesso'] not in roles:
                raise APIError('Seu perfil não tem permissão para esta operação.',403)
            return fn(*args,**kwargs)
        return wrapped
    return decorator

def product(pid,active=True):
    p = one('SELECT * FROM produtos WHERE id=?',(str(pid),),'Produto não encontrado.')
    if active and not p['ativo']:
        raise APIError('Produto inativo.')
    return p

def store(sid):
    return one('SELECT * FROM lojas WHERE id=?',(ident(sid,'loja_id'),),'Loja não encontrada.')

def item_list(data):
    items = data.get('itens')
    if not isinstance(items,list) or not 1<=len(items)<=500:
        raise APIError('Informe de 1 a 500 itens.')
    seen,result = set(),[]
    for item in items:
        if not isinstance(item,dict):
            raise APIError('Item inválido.')
        pid = str(item.get('produto_id',''))
        if pid in seen:
            raise APIError('Produtos duplicados na lista.')
        p = product(pid)
        qty = number(item.get('quantidade'),minimum=0.001)
        result.append((p,qty))
        seen.add(pid)
    return result

def balance(pid,sid):
    row = get_db().execute('SELECT quantidade FROM estoque WHERE produto_id=? AND loja_id=?',(pid,sid)).fetchone()
    return float(row['quantidade']) if row else 0.0

def move(pid,sid,delta,kind,reason,pedido_id=None):
    before = balance(pid,sid)
    after = float((Decimal(str(before))+Decimal(str(delta))).quantize(Decimal('.001')))
    if after<0:
        raise APIError(f'Estoque insuficiente para {product(pid)["nome"]}. Disponível: {before:g}.',409)
    get_db().execute('INSERT INTO estoque(produto_id,loja_id,quantidade) VALUES(?,?,?) ON CONFLICT(produto_id,loja_id) DO UPDATE SET quantidade=excluded.quantidade',(pid,sid,after))
    get_db().execute('INSERT INTO movimentacoes(tipo,produto_id,loja_id,quantidade,saldo_anterior,saldo_atual,motivo,usuario_id,pedido_id,custo_unitario) VALUES(?,?,?,?,?,?,?,?,?,?)',
                     (kind,pid,sid,delta,before,after,reason,g.user['id'],pedido_id,product(pid)['custo']))

PRODUCT_SQL = '''SELECT p.*, s.nome AS secao FROM produtos p LEFT JOIN secoes s ON s.id=p.secao_id'''
STOCK_SQL = '''SELECT p.id AS produto_id,p.nome AS produto_nome,l.id AS loja_id,l.nome AS loja_nome,s.nome AS secao,
 p.unidade,COALESCE(e.quantidade,0) AS quantidade,p.estoque_minimo,p.estoque_maximo,p.custo
 FROM produtos p CROSS JOIN lojas l LEFT JOIN secoes s ON s.id=p.secao_id
 LEFT JOIN estoque e ON e.produto_id=p.id AND e.loja_id=l.id WHERE p.ativo=1'''
MOVES_SQL = '''SELECT m.*,p.nome AS produto_nome,l.nome AS loja_nome,u.nome AS usuario_nome
 FROM movimentacoes m JOIN produtos p ON p.id=m.produto_id JOIN lojas l ON l.id=m.loja_id LEFT JOIN usuarios u ON u.id=m.usuario_id'''

def create_app(config=None):
    app = Flask(__name__,static_folder=None)
    if os.environ.get('ERP_TRUST_PROXY')=='1':
        app.wsgi_app = ProxyFix(app.wsgi_app,x_for=0,x_proto=1,x_host=0,x_port=0,x_prefix=0)
    data_dir = Path(os.environ.get('ERP_DATA_DIR',str(ROOT.parent/'erp-data')))
    database = (config or {}).get('DATABASE') or os.environ.get('ERP_DATABASE',str(data_dir/'erp.sqlite3'))
    Path(database).parent.mkdir(parents=True,exist_ok=True)
    key = (config or {}).get('SECRET_KEY') or os.environ.get('ERP_SECRET_KEY')
    if not key:
        if os.environ.get('ERP_ENV')=='production':
            raise RuntimeError('Defina ERP_SECRET_KEY para produção.')
        keyfile = Path(database).parent/'.session-key'
        try:
            fd = os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as handle:
                handle.write(secrets.token_hex(48))
        except FileExistsError:
            pass
        key = keyfile.read_text().strip()
    app.config.update(DATABASE=database,SECRET_KEY=key,SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('ERP_COOKIE_SECURE')=='1',
        PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=8),MAX_CONTENT_LENGTH=2*1024*1024)
    if config:
        app.config.update(config)
    app.teardown_appcontext(close_db)
    initialize(app)

    @app.before_request
    def prepare():
        g.user = None
        uid = session.get('uid')
        if uid:
            user = get_db().execute('SELECT id,nome,username,nivel_acesso,ativo,auth_version FROM usuarios WHERE id=?',(uid,)).fetchone()
            sid_hash=hashlib.sha256(str(session.get('sid','')).encode()).hexdigest()
            active_session=get_db().execute('SELECT 1 FROM auth_sessions WHERE id_hash=? AND usuario_id=? AND expires_at>?',(sid_hash,uid,time.time())).fetchone()
            if user and user['ativo'] and active_session and user['auth_version']==session.get('auth_version'):
                g.user = dict(user)
            else:
                session.clear()
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        if request.path.startswith('/api/') and request.method in ('POST','PUT','PATCH','DELETE'):
            public = request.path in ('/api/login','/api/setup') or request.path.startswith('/api/portal-fornecedor/')
            if not public and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session['csrf']):
                raise APIError('Sessão de formulário expirada. Atualize a página.',403)
            origin = request.headers.get('Origin')
            if origin and origin.rstrip('/')!=request.host_url.rstrip('/'):
                raise APIError('Origem da requisição não permitida.',403)
            if request.path!='/api/produtos/ler-planilha':
                get_db().execute('BEGIN IMMEDIATE')

    @app.after_request
    def finish(response):
        db = g.get('db')
        if db and db.in_transaction:
            if response.status_code<400:
                db.commit()
            else:
                db.rollback()
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.path.startswith('/api/') or request.path.endswith('.html') or request.path=='/':
            response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        return jsonify(error=error.message),error.status

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(error):
        return jsonify(error='Registro duplicado ou vinculado a um histórico. Verifique os dados; prefira inativar cadastros em uso.'),409

    @app.errorhandler(Exception)
    def unexpected(error):
        if isinstance(error,HTTPException):
            return jsonify(error=error.description),error.code
        app.logger.exception('Falha na operação')
        return jsonify(error='Não foi possível concluir a operação. Consulte os registros do servidor.'),500

    @app.get('/api/health')
    def health():
        get_db().execute('SELECT 1').fetchone()
        return jsonify(status='ok',database='sqlite')

    def session_data():
        user = {k:g.user[k] for k in ('id','nome','username','nivel_acesso')} if g.user else None
        return jsonify(user=user,csrf_token=session['csrf'],setup_required=get_db().execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]==0)

    def authenticate(user):
        session.clear()
        sid=secrets.token_urlsafe(32)
        get_db().execute('DELETE FROM auth_sessions WHERE expires_at<=?',(time.time(),))
        get_db().execute('INSERT INTO auth_sessions(id_hash,usuario_id,expires_at) VALUES(?,?,?)',(hashlib.sha256(sid.encode()).hexdigest(),user['id'],time.time()+app.config['PERMANENT_SESSION_LIFETIME'].total_seconds()))
        session.update(uid=user['id'],auth_version=user['auth_version'],sid=sid,csrf=secrets.token_urlsafe(32))
        session.permanent=True
        g.user=dict(user)

    @app.get('/api/session')
    def current_session():
        return session_data()

    @app.post('/api/setup')
    def setup():
        if get_db().execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]:
            raise APIError('A configuração inicial já foi realizada.',409)
        d = body()
        name,username,password = text(d,'nome',True,100),text(d,'username',True,50),text(d,'password',True,256)
        validate_password(password)
        validate_username(username)
        uid = get_db().execute('INSERT INTO usuarios(nome,username,senha_hash,nivel_acesso) VALUES(?,?,?,?)',(name,username,generate_password_hash(password),'Admin')).lastrowid
        authenticate(one('SELECT * FROM usuarios WHERE id=?',(uid,)))
        audit('criar','usuarios',uid,'Configuração inicial')
        return session_data(),201

    @app.post('/api/login')
    def login():
        d=body()
        username,password=text(d,'username',True,50),text(d,'password',True,256)
        key=hashlib.sha256(f'{request.remote_addr}:{username.lower()}'.encode()).hexdigest()
        attempt=get_db().execute('SELECT * FROM login_attempts WHERE chave=?',(key,)).fetchone()
        if attempt and attempt['bloqueado_ate']>time.time():
            raise APIError('Muitas tentativas. Aguarde 5 minutos.',429)
        user=get_db().execute('SELECT * FROM usuarios WHERE username=?',(username,)).fetchone()
        if not user or not user['ativo'] or not check_password_hash(user['senha_hash'],password):
            failures=(attempt['falhas'] if attempt and attempt['bloqueado_ate']>time.time()-300 else 0)+1
            get_db().execute('INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(chave) DO UPDATE SET falhas=excluded.falhas,bloqueado_ate=excluded.bloqueado_ate',(key,failures,time.time()+300 if failures>=8 else time.time()))
            # Persist rate-limit counters even though the response is a denied login.
            get_db().commit()
            raise APIError('Usuário ou senha incorretos.',401)
        get_db().execute('DELETE FROM login_attempts WHERE chave=?',(key,))
        authenticate(user)
        audit('login','usuarios',user['id'])
        return session_data()

    @app.post('/api/logout')
    @require()
    def logout():
        sid_hash=hashlib.sha256(session['sid'].encode()).hexdigest()
        get_db().execute('DELETE FROM auth_sessions WHERE id_hash=?',(sid_hash,))
        audit('logout','usuarios',g.user['id'])
        session.clear()
        return jsonify(message='Sessão encerrada.')

    @app.post('/api/account/password')
    @require()
    def change_password():
        d=body()
        current=text(d,'current_password',True,256)
        new=text(d,'new_password',True,256)
        validate_password(new)
        user=one('SELECT * FROM usuarios WHERE id=?',(g.user['id'],))
        if not check_password_hash(user['senha_hash'],current):
            raise APIError('A senha atual está incorreta.',403)
        if current==new:
            raise APIError('A nova senha deve ser diferente da atual.')
        get_db().execute('UPDATE usuarios SET senha_hash=?,auth_version=auth_version+1 WHERE id=?',(generate_password_hash(new),user['id']))
        sid_hash=hashlib.sha256(session['sid'].encode()).hexdigest()
        get_db().execute('DELETE FROM auth_sessions WHERE usuario_id=? AND id_hash<>?',(user['id'],sid_hash))
        session['auth_version']=user['auth_version']+1
        audit('alterar_senha','usuarios',user['id'])
        return jsonify(message='Senha alterada. Outras sessões foram encerradas.')

    @app.get('/api/bootstrap')
    @require()
    def bootstrap():
        return jsonify(user={k:g.user[k] for k in ('id','nome','username','nivel_acesso')},
            lojas=rows('SELECT * FROM lojas ORDER BY id'),secoes=rows('SELECT * FROM secoes ORDER BY nome'),
            produtos=rows(PRODUCT_SQL+' ORDER BY p.nome'),fornecedores=rows('SELECT * FROM fornecedores ORDER BY nome_fantasia'))

    @app.route('/api/lojas',methods=['GET','POST'])
    @require()
    def lojas():
        if request.method=='GET':
            return jsonify(rows('SELECT * FROM lojas ORDER BY id'))
        manager()
        d=body()
        name,abbr=text(d,'nome',True,100),text(d,'sigla',True,12)
        if d.get('id') is not None:
            sid=ident(d['id'])
            get_db().execute('INSERT INTO lojas(id,nome,sigla) VALUES(?,?,?)',(sid,name,abbr))
        else:
            sid=get_db().execute('INSERT INTO lojas(nome,sigla) VALUES(?,?)',(name,abbr)).lastrowid
        audit('criar','lojas',sid)
        return jsonify(id=sid,message='Loja cadastrada.'),201

    @app.route('/api/lojas/<int:sid>',methods=['PUT','DELETE'])
    @require(*MANAGERS)
    def loja(sid):
        store(sid)
        if request.method=='DELETE':
            get_db().execute('DELETE FROM lojas WHERE id=?',(sid,))
        else:
            d=body()
            get_db().execute('UPDATE lojas SET nome=?,sigla=? WHERE id=?',(text(d,'nome',True,100),text(d,'sigla',True,12),sid))
        audit(request.method.lower(),'lojas',sid)
        return jsonify(message='Loja atualizada.')

    @app.route('/api/secoes',methods=['GET','POST'])
    @require()
    def secoes():
        if request.method=='GET':
            return jsonify(rows('SELECT * FROM secoes ORDER BY nome'))
        manager()
        sid=get_db().execute('INSERT INTO secoes(nome) VALUES(?)',(text(body(),'nome',True,100),)).lastrowid
        audit('criar','secoes',sid)
        return jsonify(id=sid,message='Seção cadastrada.'),201

    @app.route('/api/secoes/<int:sid>',methods=['PUT','DELETE'])
    @require(*MANAGERS)
    def secao(sid):
        one('SELECT * FROM secoes WHERE id=?',(sid,))
        if request.method=='DELETE':
            get_db().execute('DELETE FROM secoes WHERE id=?',(sid,))
        else:
            get_db().execute('UPDATE secoes SET nome=? WHERE id=?',(text(body(),'nome',True,100),sid))
        audit(request.method.lower(),'secoes',sid)
        return jsonify(message='Seção atualizada.')

    @app.route('/api/produtos',methods=['GET','POST'])
    @require()
    def produtos():
        if request.method=='GET':
            return jsonify(rows(PRODUCT_SQL+' ORDER BY p.nome'))
        manager()
        d=body()
        pid=text(d,'id',True,20)
        if not re.fullmatch(r'[A-Za-z0-9_-]+',pid):
            raise APIError('Código de produto inválido. Use letras, números, hífen ou sublinhado.')
        vals=product_values(d)
        get_db().execute('INSERT INTO produtos(id,nome,secao_id,unidade,custo,estoque_minimo,estoque_maximo,referencia,destinacao,marca,periodo_consumo,ativo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,*vals))
        audit('criar','produtos',pid)
        return jsonify(id=pid,message='Produto cadastrado.'),201

    @app.post('/api/produtos/ler-planilha')
    @require(*MANAGERS)
    def read_product_spreadsheet():
        try:
            from .catalog_csv import fetch_google_csv
        except ImportError:
            from catalog_csv import fetch_google_csv
        try:
            source=fetch_google_csv(body().get('url'))
        except ValueError as error:
            raise APIError(str(error),400)
        return jsonify(csv_text=source)

    @app.post('/api/produtos/importar')
    @require(*MANAGERS)
    def import_product_spreadsheet():
        try:
            from .catalog_csv import analyze_csv,import_rows
        except ImportError:
            from catalog_csv import analyze_csv,import_rows
        d=body()
        apply=flag(d.get('aplicar',False))
        update=flag(d.get('atualizar_existentes',False))
        try:
            analysis=analyze_csv(d.get('csv_text'),d.get('mapping'),d.get('header_row'))
        except ValueError as error:
            raise APIError(str(error))
        existing={r['id'] for r in get_db().execute('SELECT id FROM produtos')}
        analysis['novos']=sum(item['id'] not in existing for item in analysis['rows'])
        analysis['existentes']=sum(item['id'] in existing for item in analysis['rows'])
        if not apply:
            return jsonify(analysis)
        if analysis['errors']:
            raise APIError('A importação contém erros. Corrija as linhas indicadas antes de confirmar.')
        try:
            counts=import_rows(get_db(),analysis['rows'],bool(update),g.user['id'])
        except ValueError as error:
            raise APIError(str(error))
        return jsonify(**counts,message='Importação concluída. Saldos de estoque preservados.')

    @app.route('/api/produtos/<pid>',methods=['PUT','DELETE'])
    @require(*MANAGERS)
    def produto(pid):
        old=product(pid,False)
        if request.method=='DELETE':
            if get_db().execute('SELECT 1 FROM estoque WHERE produto_id=? AND quantidade>0',(pid,)).fetchone():
                raise APIError('Zere o estoque antes de inativar o produto.',409)
            get_db().execute('UPDATE produtos SET ativo=0 WHERE id=?',(pid,))
        else:
            d=body()
            if d.get('id',pid)!=pid:
                raise APIError('O código do produto não pode ser alterado.')
            merged={**old,**d}
            if not flag(merged.get('ativo',1)) and get_db().execute('SELECT 1 FROM estoque WHERE produto_id=? AND quantidade>0',(pid,)).fetchone():
                raise APIError('Zere o estoque antes de inativar o produto.',409)
            get_db().execute('UPDATE produtos SET nome=?,secao_id=?,unidade=?,custo=?,estoque_minimo=?,estoque_maximo=?,referencia=?,destinacao=?,marca=?,periodo_consumo=?,ativo=? WHERE id=?',(*product_values(merged),pid))
        audit(request.method.lower(),'produtos',pid)
        return jsonify(message='Produto atualizado.')

    @app.route('/api/fornecedores',methods=['GET','POST'])
    @require()
    def fornecedores():
        if request.method=='GET':
            return jsonify(rows('SELECT * FROM fornecedores ORDER BY nome_fantasia'))
        manager()
        fid=get_db().execute('INSERT INTO fornecedores(nome_fantasia,cnpj,contato_nome,email,telefone,ativo) VALUES(?,?,?,?,?,?)',supplier_values(body())).lastrowid
        audit('criar','fornecedores',fid)
        return jsonify(id=fid,message='Fornecedor cadastrado.'),201

    @app.route('/api/fornecedores/<int:fid>',methods=['PUT','DELETE'])
    @require(*MANAGERS)
    def fornecedor(fid):
        old=one('SELECT * FROM fornecedores WHERE id=?',(fid,))
        if request.method=='DELETE':
            get_db().execute('UPDATE fornecedores SET ativo=0 WHERE id=?',(fid,))
        else:
            get_db().execute('UPDATE fornecedores SET nome_fantasia=?,cnpj=?,contato_nome=?,email=?,telefone=?,ativo=? WHERE id=?',(*supplier_values({**old,**body()}),fid))
        audit(request.method.lower(),'fornecedores',fid)
        return jsonify(message='Fornecedor atualizado.')

    @app.get('/api/estoque')
    @app.get('/api/estoque/matriz')
    @require()
    def estoque():
        sql,params=STOCK_SQL,[]
        if request.args.get('loja_id'):
            sql+=' AND l.id=?'
            params.append(ident(request.args['loja_id']))
        return jsonify(rows(sql+' ORDER BY p.nome,l.id',params))

    @app.route('/api/movimentacoes',methods=['GET','POST'])
    @require()
    def movimentacoes():
        if request.method=='GET':
            return jsonify(movement_rows())
        manager()
        d=body()
        kind=text(d,'tipo',True,30)
        if kind not in ('Entrada','Saida','Transferencia'):
            raise APIError('Tipo de movimentação inválido.')
        p=product(d.get('produto_id',''))
        sid=store(d.get('loja_id'))['id']
        qty=number(d.get('quantidade'),minimum=.001)
        reason=text(d,'motivo',True,500)
        if kind=='Transferencia':
            dest=store(d.get('loja_destino_id'))['id']
            if dest==sid:
                raise APIError('Origem e destino devem ser diferentes.')
            move(p['id'],sid,-qty,'Transferencia',f'{reason} • destino {dest}')
            move(p['id'],dest,qty,'Transferencia',f'{reason} • origem {sid}')
        else:
            move(p['id'],sid,qty if kind=='Entrada' else -qty,kind,reason)
        audit('movimentar','estoque',p['id'],kind)
        return jsonify(message='Movimentação registrada.'),201

    @app.route('/api/contagens',methods=['GET','POST'])
    @require()
    def contagens():
        if request.method=='GET':
            history=rows('SELECT c.*,l.nome AS loja_nome,u.nome AS usuario_nome FROM contagens c JOIN lojas l ON l.id=c.loja_id JOIN usuarios u ON u.id=c.usuario_id ORDER BY c.id DESC')
            for c in history:
                c['itens']=rows('SELECT i.*,p.nome AS produto_nome FROM contagem_itens i JOIN produtos p ON p.id=i.produto_id WHERE contagem_id=?',(c['id'],))
            return jsonify(history)
        manager()
        d=body()
        sid=store(d.get('loja_id'))['id']
        reason=text(d,'motivo',True,500)
        items=d.get('itens')
        if not isinstance(items,list) or not 1<=len(items)<=500:
            raise APIError('Informe de 1 a 500 itens contados.')
        seen,validated=set(),[]
        for item in items:
            if not isinstance(item,dict):
                raise APIError('Item inválido.')
            pid=product(item.get('produto_id',''))['id']
            if pid in seen:
                raise APIError('Produtos duplicados na contagem.')
            seen.add(pid)
            validated.append((pid,number(item.get('quantidade'))))
        cid=get_db().execute('INSERT INTO contagens(loja_id,motivo,usuario_id) VALUES(?,?,?)',(sid,reason,g.user['id'])).lastrowid
        for pid,count in validated:
            old=balance(pid,sid)
            diff=round(count-old,3)
            get_db().execute('INSERT INTO contagem_itens VALUES(?,?,?,?,?)',(cid,pid,old,count,diff))
            if diff:
                move(pid,sid,diff,'Contagem',f'Contagem #{cid}: {reason}')
        audit('contar','contagens',cid)
        return jsonify(id=cid,message='Contagem conciliada com o estoque.'),201

    def order_detail(order):
        order['itens']=rows('SELECT i.*,p.nome AS produto_nome,p.unidade FROM pedido_itens i JOIN produtos p ON p.id=i.produto_id WHERE pedido_id=?',(order['id'],))
        return order

    order_sql='''SELECT p.*,l.nome AS loja_nome,o.nome AS origem_nome,u.nome AS usuario_nome FROM pedidos p JOIN lojas l ON l.id=p.loja_id JOIN lojas o ON o.id=p.loja_origem_id JOIN usuarios u ON u.id=p.usuario_id'''

    @app.route('/api/pedidos',methods=['GET','POST'])
    @require()
    def pedidos():
        if request.method=='GET':
            return jsonify([order_detail(o) for o in rows(order_sql+' ORDER BY p.id DESC')])
        d=body()
        dest,origin=store(d.get('loja_id'))['id'],store(d.get('loja_origem_id'))['id']
        if dest==origin:
            raise APIError('Origem e destino devem ser diferentes.')
        items=item_list(d)
        total=sum(Decimal(str(p['custo']))*Decimal(str(q)) for p,q in items).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        oid=get_db().execute('INSERT INTO pedidos(loja_id,loja_origem_id,total,observacoes,usuario_id) VALUES(?,?,?,?,?)',(dest,origin,float(total),text(d,'observacoes',maximum=2000),g.user['id'])).lastrowid
        get_db().executemany('INSERT INTO pedido_itens VALUES(?,?,?,?)',[(oid,p['id'],q,p['custo']) for p,q in items])
        audit('criar','pedidos',oid)
        return jsonify(id=oid,message='Requisição enviada para aprovação.'),201

    @app.get('/api/pedidos/<int:oid>')
    @require()
    def pedido(oid):
        return jsonify(order_detail(one(order_sql+' WHERE p.id=?',(oid,))))

    @app.post('/api/pedidos/<int:oid>/status')
    @require()
    def pedido_status(oid):
        order=one('SELECT * FROM pedidos WHERE id=?',(oid,))
        new=text(body(),'status',True,20)
        transitions={'Pendente':('Aprovado','Cancelado'),'Aprovado':('Atendido','Cancelado')}
        if new not in transitions.get(order['status'],()):
            raise APIError('Transição de status não permitida.',409)
        if new=='Cancelado' and g.user['id']==order['usuario_id'] and order['status']=='Pendente':
            pass
        else:
            manager()
        if new=='Atendido':
            for item in rows('SELECT * FROM pedido_itens WHERE pedido_id=?',(oid,)):
                product(item['produto_id'])
                move(item['produto_id'],order['loja_origem_id'],-item['quantidade'],'Requisicao',f'Atendimento do pedido #{oid}',oid)
                move(item['produto_id'],order['loja_id'],item['quantidade'],'Requisicao',f'Recebimento do pedido #{oid}',oid)
        get_db().execute('UPDATE pedidos SET status=? WHERE id=?',(new,oid))
        audit('status','pedidos',oid,new)
        return jsonify(message=f'Pedido {new.lower()}.')

    @app.route('/api/cotacoes',methods=['GET','POST'])
    @require()
    def cotacoes():
        if request.method=='GET':
            return jsonify(rows('''SELECT c.*,(SELECT COUNT(*) FROM cotacao_itens WHERE cotacao_id=c.id) AS qtd_itens,
             (SELECT COUNT(*) FROM cotacao_fornecedores WHERE cotacao_id=c.id) AS qtd_fornecedores,
             (SELECT COUNT(*) FROM cotacao_fornecedores WHERE cotacao_id=c.id AND preencheu=1) AS qtd_respostas
             FROM cotacoes c ORDER BY c.id DESC'''))
        manager()
        d=body()
        title=text(d,'titulo',True,150)
        deadline=text(d,'data_limite',maximum=10) or None
        if deadline:
            try:
                date=dt.date.fromisoformat(deadline)
                if date<today():
                    raise ValueError()
            except ValueError:
                raise APIError('Data limite deve ser uma data atual ou futura no formato AAAA-MM-DD.')
        items=item_list(d)
        suppliers=d.get('fornecedores')
        if not isinstance(suppliers,list) or not 1<=len(suppliers)<=100:
            raise APIError('Selecione de 1 a 100 fornecedores.')
        ids=[]
        for fid in suppliers:
            f=one('SELECT * FROM fornecedores WHERE id=?',(ident(fid),))
            if not f['ativo'] or f['id'] in ids:
                raise APIError('Fornecedor inativo ou duplicado.')
            ids.append(f['id'])
        cid=get_db().execute('INSERT INTO cotacoes(titulo,data_limite,observacoes,usuario_id) VALUES(?,?,?,?)',(title,deadline,text(d,'observacoes',maximum=2000),g.user['id'])).lastrowid
        get_db().executemany('INSERT INTO cotacao_itens VALUES(?,?,?)',[(cid,p['id'],q) for p,q in items])
        get_db().executemany('INSERT INTO cotacao_fornecedores(cotacao_id,fornecedor_id,token) VALUES(?,?,?)',[(cid,fid,secrets.token_urlsafe(32)) for fid in ids])
        audit('criar','cotacoes',cid)
        return jsonify(id=cid,message='Cotação criada. Compartilhe os convites com os fornecedores.'),201

    def quote_details(cid):
        q=one('SELECT * FROM cotacoes WHERE id=?',(cid,))
        q['itens']=rows('SELECT i.*,p.nome AS produto_nome,p.unidade FROM cotacao_itens i JOIN produtos p ON p.id=i.produto_id WHERE cotacao_id=?',(cid,))
        q['fornecedores']=rows('SELECT f.id,f.nome_fantasia,cf.token,cf.preencheu,cf.observacoes FROM cotacao_fornecedores cf JOIN fornecedores f ON f.id=cf.fornecedor_id WHERE cf.cotacao_id=?',(cid,))
        q['respostas']=rows('SELECT r.*,f.nome_fantasia AS fornecedor_nome FROM respostas r JOIN fornecedores f ON f.id=r.fornecedor_id WHERE cotacao_id=?',(cid,))
        return q

    @app.get('/api/cotacoes/<int:cid>')
    @require(*MANAGERS)
    def cotacao(cid):
        return jsonify(quote_details(cid))

    @app.post('/api/cotacoes/<int:cid>/encerrar')
    @require(*MANAGERS)
    def encerrar(cid):
        q=quote_details(cid)
        if q['status']!='Aberta':
            raise APIError('A cotação já está encerrada ou cancelada.',409)
        winners=[]
        for item in q['itens']:
            bids=[r for r in q['respostas'] if r['produto_id']==item['produto_id'] and not r['indisponivel'] and r['preco']>0]
            if not bids:
                raise APIError(f'Sem proposta válida para {item["produto_nome"]}. Não é possível encerrar.',409)
            winners.append(min(bids,key=lambda b:(b['preco'],b['prazo_entrega'],b['fornecedor_id'])))
        for bid in winners:
            get_db().execute('UPDATE respostas SET vencedor=1 WHERE cotacao_id=? AND fornecedor_id=? AND produto_id=?',(cid,bid['fornecedor_id'],bid['produto_id']))
        get_db().execute("UPDATE cotacoes SET status='Encerrada' WHERE id=?",(cid,))
        audit('encerrar','cotacoes',cid)
        return jsonify(message='Cotação encerrada. Menores preços selecionados por item.')

    @app.post('/api/cotacoes/<int:cid>/cancelar')
    @require(*MANAGERS)
    def cancelar(cid):
        q=one('SELECT * FROM cotacoes WHERE id=?',(cid,))
        if q['status']!='Aberta':
            raise APIError('A cotação já está encerrada ou cancelada.',409)
        get_db().execute("UPDATE cotacoes SET status='Cancelada' WHERE id=?",(cid,))
        audit('cancelar','cotacoes',cid)
        return jsonify(message='Cotação cancelada.')

    @app.route('/api/portal-fornecedor/<token>',methods=['GET','POST'])
    def supplier_portal(token):
        invite=one('SELECT cf.*,f.nome_fantasia FROM cotacao_fornecedores cf JOIN fornecedores f ON f.id=cf.fornecedor_id WHERE token=?',(token,),'Convite não encontrado.')
        cid,fid=invite['cotacao_id'],invite['fornecedor_id']
        q=one('SELECT * FROM cotacoes WHERE id=?',(cid,))
        items=rows('SELECT i.produto_id AS id,p.nome,i.quantidade AS qtd,p.unidade FROM cotacao_itens i JOIN produtos p ON p.id=i.produto_id WHERE cotacao_id=?',(cid,))
        if request.method=='GET':
            bids=rows('SELECT * FROM respostas WHERE cotacao_id=? AND fornecedor_id=?',(cid,fid))
            return jsonify(cotacao={'Titulo':q['titulo'],'Status':q['status'],'Observacoes':q['observacoes'],'Data_Limite':q['data_limite']},
                fornecedor_nome=invite['nome_fantasia'],preencheu=bool(invite['preencheu']),itens=items,
                respostas={b['produto_id']:b['preco'] for b in bids},respostas_detalhes={b['produto_id']:{'prazo_entrega':b['prazo_entrega'],'observacoes':b['observacoes'],'indisponivel':bool(b['indisponivel'])} for b in bids},observacoes=invite['observacoes'])
        if q['status']!='Aberta':
            raise APIError('A cotação está encerrada ou cancelada.',409)
        if q['data_limite'] and q['data_limite']<today().isoformat():
            raise APIError('O prazo desta cotação foi encerrado.',409)
        d=body()
        bids=d.get('respostas')
        if not isinstance(bids,list) or len(bids)!=len(items):
            raise APIError('Responda a todos os itens ou marque como indisponível.')
        wanted={i['id'] for i in items}
        seen,validated=set(),[]
        for b in bids:
            if not isinstance(b,dict):
                raise APIError('Resposta inválida.')
            pid=str(b.get('produto_id',''))
            if pid not in wanted or pid in seen:
                raise APIError('Item não pertence à cotação ou está duplicado.')
            seen.add(pid)
            unavailable=flag(b.get('indisponivel',False))
            price=number(b.get('preco',0),'preco',0 if unavailable else .0001,places=4)
            days=int(number(b.get('prazo_entrega') or 0,'prazo_entrega',0,3650,0))
            validated.append((cid,fid,pid,price,days,text(b,'observacoes',maximum=500),unavailable))
        notes=text(d,'observacoes',maximum=2000)
        get_db().execute('DELETE FROM respostas WHERE cotacao_id=? AND fornecedor_id=?',(cid,fid))
        get_db().executemany('INSERT INTO respostas(cotacao_id,fornecedor_id,produto_id,preco,prazo_entrega,observacoes,indisponivel) VALUES(?,?,?,?,?,?,?)',validated)
        get_db().execute('UPDATE cotacao_fornecedores SET preencheu=1,observacoes=? WHERE cotacao_id=? AND fornecedor_id=?',(notes,cid,fid))
        audit('responder','cotacoes',cid,f'Fornecedor #{fid}')
        return jsonify(message='Proposta registrada com sucesso.')

    purchase_sql = """SELECT c.*,f.nome_fantasia AS fornecedor_nome,l.nome AS loja_nome,u.nome AS usuario_nome
     FROM compras c JOIN fornecedores f ON f.id=c.fornecedor_id JOIN lojas l ON l.id=c.loja_id
     JOIN usuarios u ON u.id=c.usuario_id"""

    def purchase_detail(purchase):
        purchase['itens']=rows('SELECT i.*,p.nome AS produto_nome,p.unidade FROM compra_itens i JOIN produtos p ON p.id=i.produto_id WHERE compra_id=?',(purchase['id'],))
        return purchase

    def create_purchase(fid,sid,items,notes='',quote_id=None):
        total=sum((Decimal(str(q))*Decimal(str(c)) for _,q,c in items),Decimal('0')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        pid=get_db().execute('INSERT INTO compras(fornecedor_id,loja_id,cotacao_id,total,observacoes,usuario_id) VALUES(?,?,?,?,?,?)',(fid,sid,quote_id,float(total),notes,g.user['id'])).lastrowid
        get_db().executemany('INSERT INTO compra_itens VALUES(?,?,?,?)',[(pid,*item) for item in items])
        audit('criar','compras',pid)
        return pid

    @app.route('/api/compras',methods=['GET','POST'])
    @require(*MANAGERS)
    def compras():
        if request.method=='GET':
            return jsonify([purchase_detail(p) for p in rows(purchase_sql+' ORDER BY c.id DESC')])
        d=body()
        fid=ident(d.get('fornecedor_id'),'fornecedor_id')
        f=one('SELECT * FROM fornecedores WHERE id=?',(fid,))
        if not f['ativo']:
            raise APIError('Fornecedor inativo.')
        sid=store(d.get('loja_id'))['id']
        items=item_list(d)
        validated=[(p['id'],q,number(raw.get('custo_unitario'),'custo_unitario',places=4)) for (p,q),raw in zip(items,d['itens'])]
        pid=create_purchase(fid,sid,validated,text(d,'observacoes',maximum=2000))
        return jsonify(id=pid,message='Pedido de compra criado.'),201

    @app.post('/api/cotacoes/<int:cid>/compras')
    @require(*MANAGERS)
    def quotation_purchases(cid):
        q=quote_details(cid)
        if q['status']!='Encerrada':
            raise APIError('Encerre a cotação antes de gerar pedidos de compra.',409)
        if get_db().execute('SELECT 1 FROM compras WHERE cotacao_id=?',(cid,)).fetchone():
            raise APIError('Os pedidos de compra desta cotação já foram gerados.',409)
        sid=store(body().get('loja_id'))['id']
        winners=[bid for bid in q['respostas'] if bid['vencedor']]
        if len(winners)!=len(q['itens']):
            raise APIError('Cotação sem vencedores para todos os itens.',409)
        quantities={i['produto_id']:i['quantidade'] for i in q['itens']}
        groups={}
        for bid in winners:
            product(bid['produto_id'])
            f=one('SELECT * FROM fornecedores WHERE id=?',(bid['fornecedor_id'],))
            if not f['ativo']:
                raise APIError('Um fornecedor vencedor foi inativado. Reative-o antes de gerar a compra.',409)
            groups.setdefault(bid['fornecedor_id'],[]).append((bid['produto_id'],quantities[bid['produto_id']],bid['preco']))
        ids=[create_purchase(fid,sid,items,f'Originada da cotação #{cid}: {q["titulo"]}',cid) for fid,items in groups.items()]
        audit('gerar_compras','cotacoes',cid)
        return jsonify(ids=ids,message='Pedidos de compra gerados por fornecedor.'),201

    @app.post('/api/compras/<int:pid>/receber')
    @require(*MANAGERS)
    def receive_purchase(pid):
        purchase=purchase_detail(one(purchase_sql+' WHERE c.id=?',(pid,)))
        if purchase['status']!='Pendente':
            raise APIError('Esta compra já foi recebida ou cancelada.',409)
        for item in purchase['itens']:
            product(item['produto_id'])
            # Latest received unit price. Quotations alone never revalue stock.
            cost=float(Decimal(str(item['custo_unitario'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
            get_db().execute('UPDATE produtos SET custo=? WHERE id=?',(cost,item['produto_id']))
            move(item['produto_id'],purchase['loja_id'],item['quantidade'],'Compra',f'Recebimento da compra #{pid}')
        get_db().execute("UPDATE compras SET status='Recebida',recebido_em=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",(pid,))
        audit('receber','compras',pid)
        return jsonify(message='Compra recebida. Estoque e custo de cadastro atualizados.')

    @app.post('/api/compras/<int:pid>/cancelar')
    @require(*MANAGERS)
    def cancel_purchase(pid):
        purchase=one('SELECT * FROM compras WHERE id=?',(pid,))
        if purchase['status']!='Pendente':
            raise APIError('Esta compra já foi recebida ou cancelada.',409)
        get_db().execute("UPDATE compras SET status='Cancelada' WHERE id=?",(pid,))
        audit('cancelar','compras',pid)
        return jsonify(message='Compra cancelada.')

    @app.route('/api/usuarios',methods=['GET','POST'])
    @require('Admin')
    def usuarios():
        if request.method=='GET':
            return jsonify(rows('SELECT id,nome,username,nivel_acesso,ativo,criado_em FROM usuarios ORDER BY nome'))
        d=body()
        values=user_values(d)
        uid=get_db().execute('INSERT INTO usuarios(nome,username,senha_hash,nivel_acesso,ativo) VALUES(?,?,?,?,?)',values).lastrowid
        audit('criar','usuarios',uid)
        return jsonify(id=uid,message='Usuário cadastrado.'),201

    @app.route('/api/usuarios/<int:uid>',methods=['PUT','DELETE'])
    @require('Admin')
    def usuario(uid):
        old=one('SELECT * FROM usuarios WHERE id=?',(uid,))
        d={'ativo':False} if request.method=='DELETE' else body()
        merged={**old,**d}
        if uid==g.user['id'] and (not flag(merged['ativo']) or merged['nivel_acesso']!='Admin'):
            raise APIError('Você não pode desativar ou remover seu próprio perfil de administrador.',409)
        if old['nivel_acesso']=='Admin' and old['ativo'] and (not flag(merged['ativo']) or merged['nivel_acesso']!='Admin'):
            if get_db().execute("SELECT COUNT(*) FROM usuarios WHERE ativo=1 AND nivel_acesso='Admin'").fetchone()[0]<=1:
                raise APIError('Mantenha ao menos um administrador ativo.',409)
        values=user_values(merged,old['senha_hash'])
        get_db().execute('UPDATE usuarios SET nome=?,username=?,senha_hash=?,nivel_acesso=?,ativo=?,auth_version=auth_version+1 WHERE id=?',(*values,uid))
        if uid==g.user['id']:
            session['auth_version']=old['auth_version']+1
        audit(request.method.lower(),'usuarios',uid)
        return jsonify(message='Usuário atualizado.')

    @app.get('/api/auditoria')
    @require('Admin')
    def auditoria():
        return jsonify(rows('SELECT a.*,u.nome AS usuario_nome FROM auditoria a LEFT JOIN usuarios u ON u.id=a.usuario_id ORDER BY a.id DESC LIMIT 1000'))

    @app.get('/api/dashboard')
    @require()
    def dashboard():
        stock=rows(STOCK_SQL+' ORDER BY p.nome,l.id')
        alerts=[s for s in stock if s['quantidade']<s['estoque_minimo']]
        value=sum((Decimal(str(s['quantidade']))*Decimal(str(s['custo'])) for s in stock),Decimal('0'))
        consumption=rows('''SELECT COALESCE(s.nome,'Sem seção') AS secao,ROUND(SUM(-m.quantidade*m.custo_unitario),2) AS valor
          FROM movimentacoes m JOIN produtos p ON p.id=m.produto_id LEFT JOIN secoes s ON s.id=p.secao_id
          WHERE m.tipo='Saida' AND m.criado_em>=? GROUP BY s.nome ORDER BY valor DESC''',(dt.datetime.combine(today().replace(day=1),dt.time.min,ZoneInfo(os.environ.get('ERP_TIMEZONE','America/Sao_Paulo'))).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),))
        return jsonify(produtos=get_db().execute('SELECT COUNT(*) FROM produtos WHERE ativo=1').fetchone()[0],lojas=get_db().execute('SELECT COUNT(*) FROM lojas').fetchone()[0],
            pedidos_pendentes=get_db().execute("SELECT COUNT(*) FROM pedidos WHERE status IN ('Pendente','Aprovado')").fetchone()[0],
            cotacoes_abertas=get_db().execute("SELECT COUNT(*) FROM cotacoes WHERE status='Aberta'").fetchone()[0],
            valor_estoque=float(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),alertas=alerts,
            ultimas_movimentacoes=rows(MOVES_SQL+' ORDER BY m.id DESC LIMIT 10'),consumo_por_secao=consumption,
            pedidos_por_status=rows('SELECT status,COUNT(*) AS total FROM pedidos GROUP BY status'))

    @app.get('/api/relatorios/<report>.csv')
    @require()
    def reports(report):
        if report=='estoque':
            result=rows(STOCK_SQL+' ORDER BY p.nome,l.id')
            fields=['produto_id','produto_nome','loja_nome','secao','unidade','quantidade','estoque_minimo','estoque_maximo','custo']
        elif report=='movimentacoes':
            result=movement_rows(limit=100000)
            fields=['id','criado_em','tipo','produto_id','produto_nome','loja_nome','quantidade','saldo_anterior','saldo_atual','motivo','usuario_nome']
        elif report=='compras':
            manager()
            result=rows(purchase_sql+' ORDER BY c.id DESC')
            fields=['id','criado_em','fornecedor_nome','loja_nome','status','total','recebido_em','observacoes']
        elif report=='pedidos':
            result=rows(order_sql+' ORDER BY p.id DESC')
            fields=['id','criado_em','loja_nome','origem_nome','status','total','usuario_nome','observacoes']
        else:
            raise APIError('Relatório não encontrado.',404)
        out=io.StringIO()
        writer=csv.writer(out,delimiter=';',lineterminator='\r\n')
        writer.writerow(fields)
        for row in result:
            writer.writerow([csv_safe(row.get(f,'')) for f in fields])
        return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="{report}.csv"'})

    @app.post('/api/exportar-pedido-txt')
    @require()
    def export_txt():
        d=body()
        if d.get('pedido_id'):
            order=order_detail(one(order_sql+' WHERE p.id=?',(ident(d['pedido_id']),)))
            sid=order['loja_id']
            items=[{'codigo':i['produto_id'],'quantidade':i['quantidade'],'custo':i['custo_unitario']} for i in order['itens']]
        else:
            sid=store(d.get('loja_id'))['id']
            items=d.get('itens')
        if not isinstance(items,list) or not 1<=len(items)<=500:
            raise APIError('Informe de 1 a 500 itens.')
        lines=[]
        for item in items:
            if not isinstance(item,dict):
                raise APIError('Item inválido.')
            code=str(item.get('codigo',''))
            if not re.fullmatch(r'[0-9]{1,13}',code):
                raise APIError('O TXT posicional requer código numérico de até 13 dígitos.')
            qty=int(number(item.get('quantidade'),minimum=1,maximum=999999,places=0))
            cost=number(item.get('custo'),'custo',maximum=9999.99,places=2)
            cents=int(Decimal(str(cost))*100)
            lines.append(f'{code.zfill(13)}{qty:06d}{cents:06d}')
        return Response('\r\n'.join(lines),mimetype='text/plain',headers={'Content-Disposition':f'attachment; filename="PEDIDO_LOJA_{sid}.txt"'})

    @app.get('/')
    def index():
        return send_from_directory(ROOT,'index.html')

    @app.get('/<path:path>')
    def static_file(path):
        allowed=path in {'index.html','login.html','portal_fornecedor.html','aba_pedidos.html'} or (
            path.startswith(('css/','js/')) and Path(path).suffix in ('.css','.js') and '..' not in Path(path).parts and not any(p.startswith('.') for p in Path(path).parts))
        if not allowed:
            raise APIError('Arquivo não encontrado.',404)
        return send_from_directory(ROOT,path)

    return app


def manager():
    if g.user['nivel_acesso'] not in MANAGERS:
        raise APIError('Seu perfil não tem permissão para esta operação.',403)

def validate_password(password):
    if len(password)<10:
        raise APIError('A senha deve ter no mínimo 10 caracteres.')

def validate_username(username):
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{3,50}',username):
        raise APIError('Usuário deve ter de 3 a 50 caracteres: letras, números, ponto, @, hífen ou sublinhado.')

def product_values(d):
    name=text(d,'nome',True,150)
    sec=d.get('secao_id')
    if sec in ('',None):
        sec=None
    else:
        sec=ident(sec,'secao_id')
        one('SELECT * FROM secoes WHERE id=?',(sec,),'Seção não encontrada.')
    unit=text(d,'unidade',maximum=12) or 'UN'
    cost=number(d.get('custo',0),'custo',places=2)
    low=number(d.get('estoque_minimo',0),'estoque_minimo')
    high=number(d.get('estoque_maximo',0),'estoque_maximo')
    if high and low>high:
        raise APIError('Estoque máximo deve ser maior ou igual ao mínimo (ou zero, sem limite).')
    return (name,sec,unit,cost,low,high,text(d,'referencia',maximum=100),text(d,'destinacao',maximum=200),text(d,'marca',maximum=100),text(d,'periodo_consumo',maximum=30) or 'Mensal',flag(d.get('ativo',True)))

def supplier_values(d):
    email=text(d,'email',maximum=150)
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
        raise APIError('E-mail inválido.')
    return text(d,'nome_fantasia',True,150),text(d,'cnpj',maximum=20),text(d,'contato_nome',maximum=100),email,text(d,'telefone',maximum=30),flag(d.get('ativo',True))

def user_values(d,old_hash=None):
    name,username=text(d,'nome',True,100),text(d,'username',True,50)
    validate_username(username)
    role=text(d,'nivel_acesso',True,20)
    if role not in ('Admin','Gestor','Operacional'):
        raise APIError('Perfil inválido.')
    password=text(d,'password',maximum=256)
    if password or not old_hash:
        validate_password(password)
        hashed=generate_password_hash(password)
    else:
        hashed=old_hash
    return name,username,hashed,role,flag(d.get('ativo',True))

def movement_rows(limit=1000):
    sql,params=MOVES_SQL+' WHERE 1=1',[]
    for param,column in [('loja_id','m.loja_id'),('produto_id','m.produto_id'),('tipo','m.tipo')]:
        if request.args.get(param):
            sql+=f' AND {column}=?'
            params.append(request.args[param])
    for param,op in [('inicio','>='),('fim','<=')]:
        if request.args.get(param):
            try:
                date=dt.date.fromisoformat(request.args[param]).isoformat()
            except ValueError:
                raise APIError('Data de filtro inválida.')
            boundary=dt.datetime.combine(dt.date.fromisoformat(date),dt.time.min,ZoneInfo(os.environ.get('ERP_TIMEZONE','America/Sao_Paulo')))
            if param=='fim':
                boundary+=dt.timedelta(days=1)
            sql+=f' AND m.criado_em {"<" if param=="fim" else ">="} ?'
            params.append(boundary.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    return rows(sql+' ORDER BY m.id DESC LIMIT ?',(*params,limit))

def csv_safe(value):
    value='' if value is None else str(value)
    return "'"+value if value.startswith(('=','+','-','@','\t','\r','\n')) else value

app=create_app()

if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=False)
