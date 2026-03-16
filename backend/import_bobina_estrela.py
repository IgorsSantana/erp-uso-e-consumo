import pymysql
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from db import get_connection
except ImportError:
    from db import get_connection

raw_data = """CÓDIGO	DESCRIÇÃO PRODUTO	FORNECEDOR	REFERÊNCIA	ESTOQUE	BCS	FCL 1	SJN	FCL 2	MEP	FCL 3	FCL 4	ESTOQUE MÍNIMO	ESTOQUE MÁXIMO	PEDIDO MENSAL
368422	Bobina Plástica Estrela G C/6			88	20	4	10	4	10	4		52	104	ESTOQUE OK
368424	Bobina Plástica Estrela M  C/6			98	20	4	10	4	10	4		52	104	ESTOQUE OK
368426	Bobina Plástica Estrela P C/6			135	12	2	8	2	8	2		34	68	ESTOQUE OK"""

def get_float(val_str):
    if not val_str: return 0.0
    v = val_str.strip().replace('.', '').replace(',', '.')
    if v == "ESTOQUE OK" or v == "": return 0.0
    try:
        return float(v)
    except:
        return 0.0

def run():
    conn = get_connection()
    if not conn:
        print("Erro de conexão DB")
        return

    try:
        with conn.cursor() as cursor:
            # Garantir a Seção
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = 'Bobina Estrela'")
            secao_row = cursor.fetchone()
            if not secao_row:
                cursor.execute("INSERT INTO Secoes (Nome) VALUES ('Bobina Estrela')")
                secao_id = cursor.lastrowid
            else:
                secao_id = secao_row[0]

            rows = raw_data.strip().split('\n')[1:] # remove header
            count = 0
            
            # Mapeamento do cabeçalho
            # 5: BCS
            # 6: FCL 1
            # 7: SJN
            # 8: FCL 2
            # 9: MEP
            # 10: FCL 3
            # 11: FCL 4
            
            loja_map = {
                5: 1,  # BCS
                6: 5,  # FCL 1
                7: 3,  # SJN
                8: 6,  # FCL 2
                9: 4,  # MEP
                10: 7, # FCL 3
                11: 8  # FCL 4
            }

            for line in rows:
                cols = line.split('\t')
                
                # Check empty rows
                if len(cols) < 2 or not cols[0].strip(): continue
                
                codigo = cols[0].strip()
                descricao = cols[1].strip()
                fornecedor = cols[2].strip() if len(cols) > 2 else ""
                ref_planilha = cols[3].strip() if len(cols) > 3 else ""
                
                referencia_final = f"{fornecedor} / {ref_planilha}".strip(" /")
                estoque_total = get_float(cols[4] if len(cols) > 4 else "0")
                
                est_min = get_float(cols[12]) if len(cols) > 12 else 0
                est_max = get_float(cols[13]) if len(cols) > 13 else 0

                # Upsert Product
                sql_prod = """
                    INSERT INTO Produtos (Codigo_ERP_Principal, Nome, Referencia, Secao_ID, Estoque_Atual, Periodo_Consumo, Custo)
                    VALUES (%s, %s, %s, %s, %s, 'Mensal', 0)
                    ON DUPLICATE KEY UPDATE 
                        Nome = VALUES(Nome),
                        Referencia = VALUES(Referencia),
                        Secao_ID = VALUES(Secao_ID),
                        Estoque_Atual = VALUES(Estoque_Atual),
                        Periodo_Consumo = 'Mensal'
                """
                cursor.execute(sql_prod, (codigo, descricao, referencia_final, secao_id, estoque_total))

                # Upsert Estoque Mín/Máximo Global no Loja 1 (Matriz)
                sql_est_matriz = """
                    INSERT INTO Estoque_Loja (Produto_ID, Loja_ID, Estoque_Minimo, Estoque_Maximo)
                    VALUES (%s, 1, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        Estoque_Minimo = VALUES(Estoque_Minimo),
                        Estoque_Maximo = VALUES(Estoque_Maximo)
                """
                cursor.execute(sql_est_matriz, (codigo, est_min, est_max))
                
                # Upsert Consumos
                for col_idx, lj_id in loja_map.items():
                    if len(cols) > col_idx:
                        consumo = get_float(cols[col_idx])
                        if consumo > 0:
                            sql_cons = """
                                INSERT INTO Estoque_Loja (Produto_ID, Loja_ID, Consumo_Medio)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE 
                                    Consumo_Medio = VALUES(Consumo_Medio)
                            """
                            cursor.execute(sql_cons, (codigo, lj_id, consumo))
                            
                count += 1

            conn.commit()
            print(f"Sucesso! {count} itens da Familia BOBINA ESTRELA importados com sucesso.")
    except Exception as e:
        print(f"Erro ao importar dados DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
