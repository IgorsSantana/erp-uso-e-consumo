from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import pymysql
import uuid
import datetime
from db import get_connection
from werkzeug.security import check_password_hash, generate_password_hash

import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
app = Flask(__name__, static_folder=base_dir, static_url_path='')

CORS(app) # Allow cross-origin for local front-end

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join(base_dir, path)):
        return app.send_static_file(path)
    return jsonify({"error": "File not found"}), 404

@app.route('/favicon.ico')
def favicon():
    # Retorna NoContent para evitar erros no console do front-end
    return '', 204

# ==========================================
# AUTHENTICATION
# ==========================================
@app.route('/api/login', methods=['POST'])
def login():
    dados = request.json
    username = dados.get('username')
    password = dados.get('password')
    
    if not username or not password:
        return jsonify({"error": "Preencha usuário e senha"}), 400

    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM Usuarios WHERE Username = %s", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['SenhaHash'], password):
                return jsonify({
                    "message": "Login successful",
                    "user": {
                        "id": user['ID'],
                        "nome": user['Nome'],
                        "username": user['Username'],
                        "nivel_acesso": user['Nivel_Acesso']
                    }
                }), 200
            else:
                return jsonify({"error": "Usuário ou senha incorretos."}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==========================================
# GESTÃO DE USUÁRIOS (Admin)
# ==========================================
@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Não retorna a SenhaHash por segurança
            cursor.execute("SELECT ID, Nome, Username, Nivel_Acesso, Data_Criacao FROM Usuarios")
            usuarios = cursor.fetchall()
            return jsonify(usuarios), 200
    finally:
        conn.close()

@app.route('/api/usuarios', methods=['POST'])
def add_usuario():
    dados = request.json
    nome = dados.get('nome')
    username = dados.get('username')
    password = dados.get('password')
    nivel = dados.get('nivel_acesso', 'Operacional')

    if not nome or not username or not password:
        return jsonify({"error": "Nome, Usuário e Senha são obrigatórios"}), 400

    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        hash_senha = generate_password_hash(password)
        with conn.cursor() as cursor:
            # Verifica se já existe
            cursor.execute("SELECT ID FROM Usuarios WHERE Username = %s", (username,))
            if cursor.fetchone():
                return jsonify({"error": "Este nome de usuário já está em uso"}), 400

            cursor.execute(
                "INSERT INTO Usuarios (Nome, Username, SenhaHash, Nivel_Acesso) VALUES (%s, %s, %s, %s)",
                (nome, username, hash_senha, nivel)
            )
            conn.commit()
            novo_id = cursor.lastrowid
            return jsonify({"message": "Usuário criado com sucesso", "id": novo_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/usuarios/<int:id>', methods=['PUT'])
def update_usuario(id):
    dados = request.json
    nome = dados.get('nome')
    username = dados.get('username')
    password = dados.get('password') # Opcional
    nivel = dados.get('nivel_acesso')

    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor() as cursor:
            # Verifica se outro admin tenta mudar username prum existe
            if username:
                cursor.execute("SELECT ID FROM Usuarios WHERE Username = %s AND ID != %s", (username, id))
                if cursor.fetchone():
                    return jsonify({"error": "Username já em uso por outro usuário"}), 400
            
            # Monta query dinâmica
            campos = []
            valores = []
            if nome:
                campos.append("Nome = %s")
                valores.append(nome)
            if username:
                campos.append("Username = %s")
                valores.append(username)
            if nivel:
                campos.append("Nivel_Acesso = %s")
                valores.append(nivel)
            if password: # Se enviou senha nova, atualiza
                campos.append("SenhaHash = %s")
                valores.append(generate_password_hash(password))
            
            if campos:
                valores.append(id)
                query = f"UPDATE Usuarios SET {', '.join(campos)} WHERE ID = %s"
                cursor.execute(query, tuple(valores))
                conn.commit()

            return jsonify({"message": "Usuário atualizado com sucesso"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/usuarios/<int:id>', methods=['DELETE'])
def delete_usuario(id):
    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Impedir exclusão do id 1 ou do próprio admin root
            cursor.execute("SELECT Username FROM Usuarios WHERE ID = %s", (id,))
            usr = cursor.fetchone()
            if not usr:
                return jsonify({"error": "Usuário não encontrado"}), 404
            if usr['Username'] == 'admin':
                return jsonify({"error": "Não é permitido excluir o usuário Administrador principal"}), 403

            cursor.execute("DELETE FROM Usuarios WHERE ID = %s", (id,))
            conn.commit()
            return jsonify({"message": "Usuário removido com sucesso"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ==========================================
# LOJAS E SEÇÕES
# ==========================================
@app.route('/api/lojas', methods=['GET'])
def get_lojas():
    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT ID as id, Nome as nome FROM Lojas;")
            lojas = cursor.fetchall()
            for l in lojas:
                if l['id'] == 1: l['sigla'] = 'BCS'
                elif l['id'] == 3: l['sigla'] = 'SJN'
                elif l['id'] == 4: l['sigla'] = 'MEP'
                elif l['id'] == 5: l['sigla'] = 'FCL'
                elif l['id'] == 6: l['sigla'] = 'FC2'
                elif l['id'] == 7: l['sigla'] = 'FC3'
                elif l['id'] == 8: l['sigla'] = 'FC4'
                else: l['sigla'] = str(l['nome'])[:3].upper()
            return jsonify(lojas)
    finally:
        conn.close()

@app.route('/api/secoes', methods=['GET'])
def get_secoes():
    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT ID as id, Nome as nome FROM Secoes;")
            secoes = cursor.fetchall()
            return jsonify(secoes)
    finally:
        conn.close()

# ==========================================
# PRODUTOS
# ==========================================
@app.route('/api/produtos', methods=['GET'])
def get_produtos():
    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT p.Codigo_ERP_Principal as id, p.Nome as nome, 
                       p.Destinacao_de_Uso as destinacao, p.Referencia as referencia,
                       s.Nome as secao, p.Periodo_Consumo as periodo_consumo,
                       p.Custo as custo
                FROM Produtos p
                LEFT JOIN Secoes s ON p.Secao_ID = s.ID;
            """
            cursor.execute(sql)
            produtos = cursor.fetchall()
            # formatting numbers
            for p in produtos:
                p['custo'] = float(p['custo']) if p['custo'] else 0.0
            return jsonify(produtos)
    finally:
        conn.close()

@app.route('/api/produtos', methods=['POST'])
def criar_produto():
    dados = request.json
    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = %s", (dados.get('secao'),))
            secao_row = cursor.fetchone()
            secao_id = secao_row['ID'] if secao_row else None
            
            sql = """
                INSERT INTO Produtos (
                    Codigo_ERP_Principal, Nome, Destinacao_de_Uso, Referencia, 
                    Secao_ID, Periodo_Consumo, Custo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                dados.get('id'), dados.get('nome'), dados.get('destinacao', ''),
                dados.get('referencia', ''), secao_id, dados.get('periodo_consumo', 'Mensal'),
                dados.get('custo')
            ))
            conn.commit()
            return jsonify({"message": "Produto criado", "id": dados.get('id')}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/produtos/<id>', methods=['PUT'])
def editar_produto(id):
    dados = request.json
    conn = get_connection()
    if not conn: return jsonify({"error": "Database error"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = %s", (dados.get('secao'),))
            secao_row = cursor.fetchone()
            secao_id = secao_row['ID'] if secao_row else None
            
            sql = """
                UPDATE Produtos SET 
                    Nome = %s, Destinacao_de_Uso = %s, Referencia = %s, 
                    Secao_ID = %s, Periodo_Consumo = %s, Custo = %s
                WHERE Codigo_ERP_Principal = %s
            """
            cursor.execute(sql, (
                dados.get('nome'), dados.get('destinacao', ''), dados.get('referencia', ''), 
                secao_id, dados.get('periodo_consumo', 'Mensal'), dados.get('custo'), id
            ))
            conn.commit()
            return jsonify({"message": "Produto atualizado", "id": id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/produtos/<id>', methods=['DELETE'])
def deletar_produto(id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM Produtos WHERE Codigo_ERP_Principal = %s", (id,))
        conn.commit()
        return jsonify({"message": "Produto deletado"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

# ==========================================
# ESTOQUE GLOBAL
# ==========================================
@app.route('/api/estoque/matriz', methods=['GET'])
def get_estoque_matriz():
    # Isso simula a resposta do Mock do store.js que entrega o Estoque agrupado
    conn = get_connection()
    if not conn: return jsonify({"error": "DB err"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. Obter Produtos (Agora trazendo Estoque Global como baseline, mais Referencia e Uso)
            cursor.execute("""
                SELECT p.Codigo_ERP_Principal as id, p.Nome as nome, s.Nome as secao, 
                       p.Periodo_Consumo as periodo_consumo, p.Estoque_Atual as estoque_global,
                       p.Destinacao_de_Uso as destinacao, p.Referencia as referencia
                FROM Produtos p LEFT JOIN Secoes s ON p.Secao_ID = s.ID
            """)
            produtos = cursor.fetchall()
            
            # 2. Obter Lojas
            cursor.execute("SELECT ID as id, Nome as nome FROM Lojas;")
            lojas = cursor.fetchall()
            
            # 3. Obter dados das Lojas e Estoque Mínimo/Máximo e o Consumo Medio
            # O Estoque_Atual global será exibido apenas na Loja 1 (Matriz) para demonstração
            cursor.execute("SELECT Produto_ID, Loja_ID, Estoque_Minimo, Estoque_Maximo, Consumo_Medio FROM Estoque_Loja")
            estoques = cursor.fetchall()
            
            # Agrupar a resposta como o Frontend espera (mock model)
            for p in produtos:
                p['totalAtual'] = float(p['estoque_global'])
                p['totalMin'] = 0
                p['totalMax'] = 0
                p['matrizLojas'] = {}
                p['destinacao'] = p.get('destinacao', '')
                p['referencia'] = p.get('referencia', '')
                
                est_produto = [e for e in estoques if e['Produto_ID'] == p['id']]
                
                for l in lojas:
                    e_loja = next((e for e in est_produto if e['Loja_ID'] == l['id']), None)
                    if e_loja:
                        p['totalMin'] += float(e_loja['Estoque_Minimo'])
                        p['totalMax'] += float(e_loja['Estoque_Maximo'])
                        
                        p['matrizLojas'][l['id']] = {
                            "consumo": float(e_loja.get('Consumo_Medio', 0) or 0),
                            "min": float(e_loja.get('Estoque_Minimo', 0) or 0),
                            "max": float(e_loja.get('Estoque_Maximo', 0) or 0)
                        }
                    else:
                        # Cria default state to show in UI instead of null
                        p['matrizLojas'][l['id']] = {
                            "consumo": 0, "min": 0, "max": 0
                        }
                
                # Definir Status
                status = 'Normal'
                if p['totalMax'] == 0 and p['totalMin'] == 0:
                    status = 'Sem Registro'
                elif p['totalAtual'] < p['totalMin']:
                    status = 'Crítico'
                elif p['totalAtual'] <= (p['totalMin'] * 1.2):
                    status = 'Atenção'
                    
                p['status'] = status
                
            return jsonify(produtos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/estoque/ajuste', methods=['POST'])
def ajustar_estoque_global():
    dados = request.json # ex: [{ "produto_id": "123", "novo_estoque": 50 }, ...]
    conn = get_connection()
    if not conn: return jsonify({"error": "DB err"}), 500
    try:
        with conn.cursor() as cursor:
            for item in dados:
                prod_id = item.get('produto_id')
                novo_estoque = item.get('novo_estoque')
                if prod_id and novo_estoque is not None:
                    # Atualiza diretamente o estoque global (Estoque_Atual na tabela Produtos)
                    cursor.execute("UPDATE Produtos SET Estoque_Atual = %s WHERE Codigo_ERP_Principal = %s",
                                   (float(novo_estoque), prod_id))
            conn.commit()
            return jsonify({"message": "Estoque atualizado com sucesso!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

# ==========================================
# FORNECEDORES
# ==========================================
@app.route('/api/fornecedores', methods=['GET'])
def get_fornecedores():
    conn = get_connection()
    if not conn: return jsonify({"error": "DB err"}), 500
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM Fornecedores ORDER BY Nome_Fantasia")
            return jsonify(cursor.fetchall())
    finally:
        conn.close()

@app.route('/api/fornecedores', methods=['POST'])
def criar_fornecedor():
    dados = request.json
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO Fornecedores (Nome_Fantasia, CNPJ, Contato_Nome, Email, Telefone) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (dados.get('nome'), dados.get('cnpj'), dados.get('contato'), dados.get('email'), dados.get('telefone')))
            conn.commit()
            return jsonify({"message": "Fornecedor criado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/fornecedores/<int:id>', methods=['PUT', 'DELETE'])
def manage_fornecedor(id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if request.method == 'DELETE':
                cursor.execute("DELETE FROM Fornecedores WHERE ID = %s", (id,))
                conn.commit()
                return jsonify({"message": "Deletado"}), 200
            else:
                dados = request.json
                sql = "UPDATE Fornecedores SET Nome_Fantasia=%s, CNPJ=%s, Contato_Nome=%s, Email=%s, Telefone=%s, Ativo=%s WHERE ID=%s"
                cursor.execute(sql, (dados.get('nome'), dados.get('cnpj'), dados.get('contato'), dados.get('email'), dados.get('telefone'), dados.get('ativo', True), id))
                conn.commit()
                return jsonify({"message": "Atualizado"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

# ==========================================
# COTAÇÕES (ADMIN)
# ==========================================
@app.route('/api/cotacoes', methods=['GET'])
def get_cotacoes():
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM Cotacoes ORDER BY ID DESC")
            cotacoes = cursor.fetchall()
            for c in cotacoes:
                cursor.execute("SELECT COUNT(*) as qtd FROM Cotacao_Itens WHERE Cotacao_ID = %s", (c['ID'],))
                c['qtd_itens'] = cursor.fetchone()['qtd']
                cursor.execute("SELECT COUNT(*) as qtd FROM Cotacao_Fornecedores WHERE Cotacao_ID = %s", (c['ID'],))
                c['qtd_fornecedores'] = cursor.fetchone()['qtd']
            return jsonify(cotacoes)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/cotacoes', methods=['POST'])
def criar_cotacao():
    dados = request.json
    titulo = dados.get('titulo')
    observacoes = dados.get('observacoes', '')
    itens = dados.get('itens', []) # lista de objetos { produto_id, quantidade }
    fornecedores = dados.get('fornecedores', []) # lista de IDs

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Cria a Cotação
            cursor.execute("INSERT INTO Cotacoes (Titulo, Observacoes) VALUES (%s, %s)", (titulo, observacoes))
            cotacao_id = cursor.lastrowid
            
            # 2. Insere os Itens
            for item in itens:
                cursor.execute("INSERT INTO Cotacao_Itens (Cotacao_ID, Produto_ID, Quantidade_Solicitada) VALUES (%s, %s, %s)",
                               (cotacao_id, item['produto_id'], item['quantidade']))
            
            # 3. Insere os Fornecedores e gera Tokens
            links_gerados = []
            for f_id in fornecedores:
                token = str(uuid.uuid4())
                cursor.execute("INSERT INTO Cotacao_Fornecedores (Cotacao_ID, Fornecedor_ID, Token_Acesso) VALUES (%s, %s, %s)",
                               (cotacao_id, f_id, token))
                links_gerados.append({"fornecedor_id": f_id, "token": token})

            conn.commit()
            return jsonify({"message": "Cotação Criada", "cotacao_id": cotacao_id, "links": links_gerados}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/cotacoes/<int:id>', methods=['GET'])
def get_cotacao_detalhe(id):
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Info Cotacao
            cursor.execute("SELECT * FROM Cotacoes WHERE ID = %s", (id,))
            cotacao = cursor.fetchone()
            if not cotacao: return jsonify({"error": "Não encontrada"}), 404
            
            # Fornecedores
            cursor.execute('''
                SELECT cf.Fornecedor_ID as ID, f.Nome_Fantasia as nome, f.WhatsApp, cf.Token_Acesso, cf.Visualizou, cf.Preencheu 
                FROM Cotacao_Fornecedores cf
                JOIN Fornecedores f ON cf.Fornecedor_ID = f.ID
                WHERE cf.Cotacao_ID = %s
            ''', (id,))
            fornecedores = cursor.fetchall()
            
            # Itens
            sql_itens = """
                SELECT ci.Produto_ID, p.Nome, ci.Quantidade_Solicitada 
                FROM Cotacao_Itens ci
                JOIN Produtos p ON ci.Produto_ID = p.Codigo_ERP_Principal
                WHERE ci.Cotacao_ID = %s
            """
            cursor.execute(sql_itens, (id,))
            itens = cursor.fetchall()
            
            # Respostas
            cursor.execute("SELECT Fornecedor_ID, Produto_ID, Preco_Unitario, Eh_Vencedor FROM Respostas_Cotacao WHERE Cotacao_ID = %s", (id,))
            respostas_raw = cursor.fetchall()
            
            # Formatar a resposta no formato tabela pro frontend
            # { "produto_id": { "dados_produto": {}, "respostas": { "fornecedor_id": preco, "vencedor": id } } }
            matriz = []
            for item in itens:
                item_obj = {
                    "id": item["Produto_ID"],
                    "nome": item["Nome"],
                    "qtd": item["Quantidade_Solicitada"],
                    "precos": {},
                    "vencedor_id": None
                }
                for r in respostas_raw:
                    if str(r["Produto_ID"]) == str(item["Produto_ID"]):
                        item_obj["precos"][str(r["Fornecedor_ID"])] = float(r["Preco_Unitario"])
                        if r["Eh_Vencedor"]:
                            item_obj["vencedor_id"] = str(r["Fornecedor_ID"])
                matriz.append(item_obj)
                
            cotacao['fornecedores'] = fornecedores
            cotacao['itens'] = matriz
            return jsonify(cotacao)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/cotacoes/<int:id>/encerrar', methods=['POST'])
def encerrar_cotacao(id):
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Pega itens da cotação
            cursor.execute("SELECT Produto_ID FROM Cotacao_Itens WHERE Cotacao_ID = %s", (id,))
            itens = cursor.fetchall()
            
            for item in itens:
                prod_id = item['Produto_ID']
                # Busca menor preço
                sql_min = """
                    SELECT Fornecedor_ID, Preco_Unitario FROM Respostas_Cotacao
                    WHERE Cotacao_ID = %s AND Produto_ID = %s AND Preco_Unitario > 0
                    ORDER BY Preco_Unitario ASC LIMIT 1
                """
                cursor.execute(sql_min, (id, prod_id))
                menor = cursor.fetchone()
                
                if menor:
                    # Seta todos como false, depois o menor como true
                    cursor.execute("UPDATE Respostas_Cotacao SET Eh_Vencedor = FALSE WHERE Cotacao_ID = %s AND Produto_ID = %s", (id, prod_id))
                    cursor.execute("UPDATE Respostas_Cotacao SET Eh_Vencedor = TRUE WHERE Cotacao_ID = %s AND Produto_ID = %s AND Fornecedor_ID = %s", 
                                   (id, prod_id, menor['Fornecedor_ID']))
                                   
                    # Atualiza o custo base do produto no Cadastro Principal para refletir a economia ganha na cotação
                    cursor.execute("UPDATE Produtos SET Custo = %s WHERE Codigo_ERP_Principal = %s",
                                   (float(menor['Preco_Unitario']), prod_id))
            
            # Atualiza status
            cursor.execute("UPDATE Cotacoes SET Status = 'Encerrada', Data_Encerramento = CURRENT_TIMESTAMP WHERE ID = %s", (id,))
            conn.commit()
            return jsonify({"message": "Cotação Encerrada com sucesso!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

# ==========================================
# PORTAL DO FORNECEDOR (ACESSO EXTERNO)
# ==========================================
@app.route('/api/portal-fornecedor/<token>', methods=['GET'])
def get_portal_fornecedor(token):
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Valida Token
            sql_auth = "SELECT Cotacao_ID, Fornecedor_ID, Visualizou, Preencheu FROM Cotacao_Fornecedores WHERE Token_Acesso = %s"
            cursor.execute(sql_auth, (token,))
            auth = cursor.fetchone()
            if not auth: return jsonify({"error": "Link inválido ou expirado."}), 404
            
            cotacao_id = auth['Cotacao_ID']
            fornecedor_id = auth['Fornecedor_ID']
            
            # Marca visualizado se não estava
            if not auth['Visualizou']:
                cursor.execute("UPDATE Cotacao_Fornecedores SET Visualizou = TRUE, Data_Visualizacao = CURRENT_TIMESTAMP WHERE Token_Acesso = %s", (token,))
                conn.commit()
                
            # Detalhes Cotacao
            cursor.execute("SELECT Titulo, Status, Observacoes FROM Cotacoes WHERE ID = %s", (cotacao_id,))
            cotacao = cursor.fetchone()
            
            # Nome Fornecedor
            cursor.execute("SELECT Nome_Fantasia FROM Fornecedores WHERE ID = %s", (fornecedor_id,))
            nome_fornecedor = cursor.fetchone()['Nome_Fantasia']
            
            # Itens Solicitados
            sql_itens = """
                SELECT ci.Produto_ID as id, p.Nome as nome, ci.Quantidade_Solicitada as qtd 
                FROM Cotacao_Itens ci
                JOIN Produtos p ON ci.Produto_ID = p.Codigo_ERP_Principal
                WHERE ci.Cotacao_ID = %s
            """
            cursor.execute(sql_itens, (cotacao_id,))
            itens = cursor.fetchall()
            
            # Respostas Anteriores (se preencheu e está abrindo de novo)
            respostas_dict = {}
            if auth['Preencheu']:
                cursor.execute("SELECT Produto_ID, Preco_Unitario FROM Respostas_Cotacao WHERE Cotacao_ID = %s AND Fornecedor_ID = %s", (cotacao_id, fornecedor_id))
                for r in cursor.fetchall():
                    respostas_dict[r['Produto_ID']] = float(r['Preco_Unitario'])
            
            return jsonify({
                "cotacao": cotacao,
                "fornecedor_nome": nome_fornecedor,
                "preencheu": auth['Preencheu'],
                "itens": itens,
                "respostas": respostas_dict
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/portal-fornecedor/<token>', methods=['POST'])
def post_portal_fornecedor(token):
    dados = request.json # { "respostas": [ { "produto_id": "123", "preco": 10.50 } ] }
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Valida Token
            sql_auth = "SELECT Cotacao_ID, Fornecedor_ID FROM Cotacao_Fornecedores WHERE Token_Acesso = %s"
            cursor.execute(sql_auth, (token,))
            auth = cursor.fetchone()
            if not auth: return jsonify({"error": "Link inválido."}), 404
            
            cotacao_id = auth['Cotacao_ID']
            fornecedor_id = auth['Fornecedor_ID']
            
            # Validar se cotação ainda está aberta
            cursor.execute("SELECT Status FROM Cotacoes WHERE ID = %s", (cotacao_id,))
            if cursor.fetchone()['Status'] != 'Aberta':
                return jsonify({"error": "Esta cotação já foi encerrada."}), 400

            # Salvar respostas
            # Limpa antigas deste fornecedor nesta cotacao (se ele estiver reenviando)
            cursor.execute("DELETE FROM Respostas_Cotacao WHERE Cotacao_ID = %s AND Fornecedor_ID = %s", (cotacao_id, fornecedor_id))
            
            respostas = dados.get('respostas', [])
            for res in respostas:
                prod_id = res['produto_id']
                preco = float(res['preco'])
                if preco > 0:
                    cursor.execute("INSERT INTO Respostas_Cotacao (Cotacao_ID, Fornecedor_ID, Produto_ID, Preco_Unitario) VALUES (%s, %s, %s, %s)",
                                   (cotacao_id, fornecedor_id, prod_id, preco))
                                   
            # Marca como Preencheu
            cursor.execute("UPDATE Cotacao_Fornecedores SET Preencheu = TRUE, Data_Preenchimento = CURRENT_TIMESTAMP WHERE Token_Acesso = %s", (token,))
            conn.commit()
            return jsonify({"message": "Proposta enviada com sucesso!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==========================================
# EXPORTAÇÃO DE PEDIDOS TXT (CONSINCO/LEGADO)
# ==========================================
@app.route('/api/exportar-pedido-txt', methods=['POST'])
def exportar_pedido_txt():
    data = request.json
    loja_id = data.get('loja_id')
    itens = data.get('itens', [])
    
    if not loja_id or not itens:
        return jsonify({"error": "Loja solicitante e itens do pedido são obrigatórios."}), 400
        
    linhas_txt = []
    
    for item in itens:
        try:
            codigo = str(item['codigo']).zfill(13)
            quantidade = str(int(item['quantidade'])).zfill(6)
            
            # Custo em centavos garantindo 6 casas
            custo_centavos = int(round(float(item['custo']) * 100))
            custo = str(custo_centavos).zfill(6)
            
            linha = f"{codigo}{quantidade}{custo}"
            
            if len(linha) != 25:
                return jsonify({"error": f"Erro de formatação posicional no produto {item['codigo']}."}), 500
                
            linhas_txt.append(linha)
            
        except (KeyError, ValueError) as e:
            return jsonify({"error": f"Dados inválidos no item: {e}"}), 400
            
    # Cria a string completa separando por quebra de linha CR LF do Windows padrão
    conteudo_arquivo = "\r\n".join(linhas_txt)
    
    # Retorna o arquivo de texto para download direto via send_file (via StringIO/BytesIO)
    from io import BytesIO
    import datetime
    arquivo = BytesIO(conteudo_arquivo.encode('utf-8'))
    
    # Define o nome do arquivo dinâmico
    agora = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    nome_arquivo = f"PEDIDO_LOJA_{loja_id}_{agora}.txt"
    
    return send_file(
        arquivo,
        mimetype='text/plain',
        as_attachment=True,
        download_name=nome_arquivo
    )

if __name__ == '__main__':
    print("Iniciando API Python do Micro-ERP Uso e Consumo...")
    app.run(host='0.0.0.0', port=5000, debug=True)
