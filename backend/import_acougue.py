import pymysql
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from db import get_connection
except ImportError:
    from db import get_connection

raw_data = """CÓDIGO	DESCRIÇÃO PRODUTO	FORNECEDOR	DESTINAÇÃO DE USO	REFERÊNCIA	ESTOQUE	BCS	FCL 1	SJN	FCL 2	MEP	FCL 3	FCL 4	ESTOQUE MÍNIMO	ESTOQUE MÁXIMO	PEDIDO MENSAL
369842	AGLOMAX FRANGO (FARDO C/ 30)					0									
359071	AGLOMAX TOSCANA (FARDO C/ 30)	1354			2	2							2	4	2
341499	AJINOMOTO KG	1354			1	1							1	2	1
367175	BARBANTE ROLO	1354			3	2							2	4	1
360618	CALDÃO DE GALINHA 1KG	1354			2	1							1	2	ESTOQUE OK
367166	CEBOLINHA DESIDRATADA KG	1354			8	1					0,5		2	3	ESTOQUE OK
367205	CHAIRA 12 POLEGADAS	COTAÇÃO			2										
359074	CHIMICHURRI KG	1354			4	1							1	2	ESTOQUE OK
367207	CORANTE CARMIN 1L	1354			5	2							2	4	ESTOQUE OK
342604	EXACOR AÇOUGUE	1354			28	30							30	60	32
367197	FACA DESOSSA N.6	COTAÇÃO			0										
367314	FACA N.12 AMARELA	COTAÇÃO			1										
367312	FACA N.12 AZUL	COTAÇÃO			0										
367199	FACA N.12 BRANCA	COTAÇÃO			0										
370177	FUMARIN 1L	1354			28	1							1	2	ESTOQUE OK
367179	HARMONIX F 600 G	1354			34	30							30	60	26
367181	LIGATARI	1354			20	25		1					26	52	32
341927	NOZ MOSCADA KG	1354			1	1							1	2	1
367185	PEDRA PRA AMOLAR	1354			5	2							2	4	ESTOQUE OK
368117	PIMENTA MALAGUETA 1L	1354			2	1							1	2	ESTOQUE OK
344998	SAL DE CURA 1 KG	1354			11	10		1					11	22	11
338389	SERRA FITA MODELO 169 (não usa)	2093			9	2							2	4	ESTOQUE OK
375899	SERRA FITA MODELO (MEP 310) (SJ S310)9 DESCOBERTO)	2093			20	10							10	20	ESTOQUE OK
370508	SERRA FITA MODELO 255 (Maripá)				6	3							3	6	ESTOQUE OK
343244	SERRA FITA MODELO (BICAS   282)	2093			20	4							4	8	ESTOQUE OK
367209	TRIPA FINA 22	83284			3	2							2	4	1
367193	TRIPA SUÍNA GROSSA	83284			80	20							20	40	ESTOQUE OK
363124	URUCUM LÍQUIDO 1L	1354			7	2		1	1		1		5	10	3
352546	SERRA FITA 1,74 (SJ2)	2093			10	5							5	10	ESTOQUE OK"""

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
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = 'Açougue'")
            secao_row = cursor.fetchone()
            if not secao_row:
                cursor.execute("INSERT INTO Secoes (Nome) VALUES ('Açougue')")
                secao_id = cursor.lastrowid
            else:
                secao_id = secao_row[0]

            rows = raw_data.strip().split('\n')[1:] # remove header
            count = 0
            
            loja_map = {
                6: 1,  # BCS
                7: 5,  # FCL 1
                8: 3,  # SJN
                9: 6,  # FCL 2
                10: 4, # MEP
                11: 7, # FCL 3
                12: 8  # FCL 4
            }

            for line in rows:
                cols = line.split('\t')
                
                # Check empty rows
                if len(cols) < 2 or not cols[0].strip(): continue
                
                codigo = cols[0].strip()
                descricao = cols[1].strip()
                fornecedor = cols[2].strip() if len(cols) > 2 else ""
                destinacao = cols[3].strip() if len(cols) > 3 else ""
                ref_planilha = cols[4].strip() if len(cols) > 4 else ""
                
                # Juntar Fornecedor com Referência
                referencia_final = f"{fornecedor} / {ref_planilha}".strip(" /")
                
                estoque_total = get_float(cols[5] if len(cols) > 5 else "0")
                
                est_min = get_float(cols[13]) if len(cols) > 13 else 0
                est_max = get_float(cols[14]) if len(cols) > 14 else 0

                # Upsert Product
                sql_prod = """
                    INSERT INTO Produtos (Codigo_ERP_Principal, Nome, Referencia, Destinacao_de_Uso, Secao_ID, Estoque_Atual, Periodo_Consumo, Custo)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Mensal', 0)
                    ON DUPLICATE KEY UPDATE 
                        Nome = VALUES(Nome),
                        Referencia = VALUES(Referencia),
                        Destinacao_de_Uso = VALUES(Destinacao_de_Uso),
                        Secao_ID = VALUES(Secao_ID),
                        Estoque_Atual = VALUES(Estoque_Atual),
                        Periodo_Consumo = 'Mensal'
                """
                cursor.execute(sql_prod, (codigo, descricao, referencia_final, destinacao, secao_id, estoque_total))

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
            print(f"Sucesso! {count} itens da Familia AÇOUGUE importados com sucesso.")
    except Exception as e:
        print(f"Erro ao importar dados DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
