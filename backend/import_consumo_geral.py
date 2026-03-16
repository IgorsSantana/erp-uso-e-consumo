import pymysql
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from db import get_connection
except ImportError:
    from db import get_connection

raw_data = """CÓDIGO	DESCRIÇÃO PRODUTO	MARCA	FORNECEDOR	REFERÊNCIA	ESTOQUE	BCS	FCL 1	SJN	FCL 2	MEP	FCL 3	FCL 4	ESTOQUE MÍNIMO	ESTOQUE MÁXIMO
367960	Disco de Fibra p/ máquina Flaire	FLAIRE	24011 - Flaire		17	3	0	2	1	2	1		9	18
367281	Bucha de Fibra Limpeza Leve c/10	FSD	71596 - FSD		0	1	0,5	2	0,5	2	0,5		7	13
367278	Bucha de Fibra Limpeza Pesada c/10	FSD	71596 - FSD		0	2	0,5	2	0,5	2	0,5		8	15
367891	Papel higiênico rolão un. (FD C/8)	SANPAPER	79471 - SanPaper		5	20	4	16	8	16	8		72	144
367022	Papel toalha interfolhado c/ 1000	SANPAPER	79471 - SanPaper		16	20	5	20	10	20	10		85	170
368292	Papel toalha rolão (fardo c/ 6)	SANPAPER	79471 - SanPaper		7	10	0	12	6	12	6		46	92
367020	Perfex rolão	BM3	87665 - BM3		44	10	1	5	3	5	3		27	54
367030	Touca sanfonada c/ 100	BM3	87665 - BM3		12000	3	1	3	2	3	2		14	28
367018	Luva descartável c/ 100	BM3	87665 - BM3		19	3	1	2	1	2	1		10	20
375040	Saco de lixo c/100 TRANSPARENTE 100L	LTA / EMBALA E LIMP	LTA / EMBALA E LIMP		4000	6	2	6	4	5	3		26	52
369905	Refil esfregão	SANPAPER	79471 - SanPaper		9	2	1	2	1	2	1		9	18
368128	Luva de borracha G c/ 2	BM3	87665 - BM3		60	2	1	5	2	4	2		16	32
373521	Guardanapo Caicai c 8000	SANPAPER	79471 - SanPaper		4	2							2	4
														
343580	Esponja multiuso c/4	VIP				3	2	5	3	5	3		21	42
376096	Palha de aço	QLUSTRO		BAIXA	2	3	1	4	2	3	2		15	30
15	Pulverizador	DEMANDA		BAIXA	15									
373276	COPO DESCARTAVEL 200ML  C 100	COPOFLEX		BAIXA	3	2	1	3	1	2	1		10	20
369968	GUARDANAPO	MAXIM C 50		BAIXA	15	4	1	4	2	3	1		15	30
358743	Vassoura sintética			BAIXA	0	7	0	3	0	3	0		13	26
310782	Vassoura piaçava			BAIXA	0	9	3	8	5	7	5		37	74
376515	Rodo alumínio 50cm	ZANINI	80446 - Zanini	BAIXA		13	1	10	4	9	3		40	80
330928	Pano alevjado azul	UNIÃO	1272 - D.V Distribuidora	BAIXA	7	10	2	8	4	6	4		34	68
324480	SODA CAUSTICA YARA 950G			BAIXA	0	1	1	3	1	1	1		8	16
337657	CURATIVO TRADICIONAL C 35			BAIXA		1	1	1	1	1	1		6	12
313065	ESCOVA DE MADEIRA			BAIXA		2	0	2	1	2	1		8	16
18	PAPEL HIGIÊNICO ESCRITÓRIO			BAIXA	0	60	12	48	24	36	24		204	408"""

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
            # Garantir a Seção "Consumo Geral"
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = 'Consumo Geral'")
            secao_row = cursor.fetchone()
            if not secao_row:
                cursor.execute("INSERT INTO Secoes (Nome) VALUES ('Consumo Geral')")
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
                marca = cols[2].strip() if len(cols) > 2 else ""
                fornecedor = cols[3].strip() if len(cols) > 3 else ""
                ref_planilha = cols[4].strip() if len(cols) > 4 else ""
                
                # Juntar Marca com Fornecedor/Ref
                referencia_final = f"{marca} / {ref_planilha}".strip(" /")
                
                estoque_total = get_float(cols[5] if len(cols) > 5 else "0")
                
                est_min = get_float(cols[13]) if len(cols) > 13 else 0
                est_max = get_float(cols[14]) if len(cols) > 14 else 0

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
            print(f"Sucesso! {count} itens da Familia CONSUMO GERAL importados com sucesso.")
    except Exception as e:
        print(f"Erro ao importar dados DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
