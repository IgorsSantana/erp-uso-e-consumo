import pymysql
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from db import get_connection
except ImportError:
    from db import get_connection

raw_data = """CÓDIGO	DESCRIÇÃO PRODUTO	FORNECEDOR	DESTINAÇÃO DE USO	PERÍODO	ESTOQUE	CONSUMO	BCS	FCL 1	SJN	FCL 2	MEP	FCL 3	FCL 4	ESTOQUE MÍNIMO	ESTOQUE MÁXIMO	PEDIDO SEMESTRAL
367155	BORRACHA GRANDE CX C/20			SEIS MESES	0		20	10	20	20	20	20		110	220	110
367157	CALCULADORA UNIDADE			SEIS MESES	0		4	2	3	2	3	2		16	32	16
367061	CANETA AZUL C100			SEIS MESES	0		200	30	100	100	100	100		630	1260	630
367067	CANETA NOTA FALSA UNIDADE			SEIS MESES	0											
367069	CLIPS N.3 C/50			SEIS MESES	0		4	1	3	2	3	2		15	30	15
367071	CLIPS N.6 C/50			SEIS MESES	0		4	1	3	2	3	2		15	30	15
367073	CLIPS N.8 C/50			SEIS MESES	0		4	1	3	2	3	2		15	30	15
367075	COLA BASTÃO CX C/12			SEIS MESES	0		3	1	2	1	2	1		10	20	10
367081	DUREX 12MM x 50M CX C/20			SEIS MESES	0		60	20	60	40	60	40		280	560	280
367083	ELÁSTICO DINHEIRO PACOTE			SEIS MESES	0		2	1	1	1	1	1		7	14	7
367085	ENVELOPE PARDO CX C/100			SEIS MESES	0		2	0	0	0	0	0		2	4	2
367087	ENVELOPE PEQUENO CX C/100			SEIS MESES	0		2	0	0	0	0	0		2	4	2
367089	ESTILETE GRANDE UNIDADE			SEIS MESES	0		6	2	4	3	4	3		22	44	22
367109	GRAMPO  26/6 CX C/10X5000			SEIS MESES	0		4	1	3	2	3	2		15	30	15
367111	LACRE CAMINHÃO NUMERADO C/100			SEIS MESES	0		3	1	2	1	2	1		10	20	10
367119	MARCA TEXTO CX C/12			SEIS MESES	0		6	1	2	1	2	1		13	26	13
367129	PINCEL ATÔMICO  CX C/12			SEIS MESES	0		6	1	3	2	3	2		17	34	17
367137	RÉGUA GRANDE 30CM CX C/6			SEIS MESES	0		6	1	3	2	3	2		17	34	17
367143	SELADORA UNIDADE			SEIS MESES	0											
367145	TESOURA GRANDE UNIDADE			SEIS MESES	0		6	1	2	1	2	1		13	26	13
367147	GRAMPEADOR UNIDADE			SEIS MESES	0		6	1	3	2	3	2		17	34	17
367115	LÁPIS PRETO CX C/144			SEIS MESES	0		30	10	30	20	30	20		140	280	140
367099	FOLHA A4  BRANCO C 500			UM MÊS	0		25	5	20	15	20	15		100	200	100
367095	FOLHA A4 AMARELA C 100			UM MÊS	0		10	3	8	6	8	6		41	82	41
367097	FOLHA A4 AZUL C 100			UM MÊS	0		10	3	8	6	8	6		41	82	41
367101	FOLHA A4 ROSA C 100			UM MÊS	0		5	2	4	3	4	3		21	42	21
367105	FOLHA A4 VERDE C 100			UM MÊS	0		5	2	4	3	4	3		21	42	21
321375	PILHA PALITO C 4	EVEREADY GOLD		SEIS MESES	0		2	1	2	1	2	1		9	18	9
321376	PILHA PEQUENA C 4	EVEREADY GOLD		SEIS MESES	0		2	1	2	1	2	1		9	18	9"""

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
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = 'Escritório'")
            secao_row = cursor.fetchone()
            if not secao_row:
                cursor.execute("INSERT INTO Secoes (Nome) VALUES ('Escritório')")
                secao_id = cursor.lastrowid
            else:
                secao_id = secao_row[0]

            rows = raw_data.strip().split('\n')[1:] # remove header
            count = 0
            
            # Mapeamento do cabeçalho
            # 7: BCS
            # 8: FCL 1
            # 9: SJN
            # 10: FCL 2
            # 11: MEP
            # 12: FCL 3
            # 13: FCL 4
            
            loja_map = {
                7: 1,  # BCS
                8: 5,  # FCL 1
                9: 3,  # SJN
                10: 6, # FCL 2
                11: 4, # MEP
                12: 7, # FCL 3
                13: 8  # FCL 4
            }

            for line in rows:
                cols = line.split('\t')
                
                # Check empty rows
                if len(cols) < 2 or not cols[0].strip(): continue
                
                codigo = cols[0].strip()
                descricao = cols[1].strip()
                fornecedor = cols[2].strip() if len(cols) > 2 else ""
                destinacao = cols[3].strip() if len(cols) > 3 else ""
                
                periodo_str = cols[4].strip() if len(cols) > 4 else ""
                periodo_consumo = "Mensal" if "MÊS" in periodo_str.upper() else "Semestral"
                
                estoque_total = get_float(cols[5] if len(cols) > 5 else "0")
                
                est_min = get_float(cols[14]) if len(cols) > 14 else 0
                est_max = get_float(cols[15]) if len(cols) > 15 else 0

                # Upsert Product
                sql_prod = """
                    INSERT INTO Produtos (Codigo_ERP_Principal, Nome, Referencia, Destinacao_de_Uso, Secao_ID, Estoque_Atual, Periodo_Consumo, Custo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                    ON DUPLICATE KEY UPDATE 
                        Nome = VALUES(Nome),
                        Referencia = VALUES(Referencia),
                        Destinacao_de_Uso = VALUES(Destinacao_de_Uso),
                        Secao_ID = VALUES(Secao_ID),
                        Estoque_Atual = VALUES(Estoque_Atual),
                        Periodo_Consumo = VALUES(Periodo_Consumo)
                """
                cursor.execute(sql_prod, (codigo, descricao, fornecedor, destinacao, secao_id, estoque_total, periodo_consumo))

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
            print(f"Sucesso! {count} itens da Familia ESCRITORIO importados com sucesso.")
    except Exception as e:
        print(f"Erro ao importar dados DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
