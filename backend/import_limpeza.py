import pymysql
import sys
import os

# Ensure backend module is available
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
try:
    from db import get_connection
except ImportError:
    # Fallback if running directly inside backend
    from db import get_connection

raw_data = """BCS	SJN	MEP	FCL1	FCL2	FCL3	CÓDIGO	DESCRIÇÃO PRODUTO	MARCA	FORNECEDOR	DILUIÇÃO POR LITRO	RENDIMENTO	DESTINAÇÃO DE USO	ESTOQUE	BCS SEMANAL LITRO	BCS FCL SEMANAL LITRO	SJN SEMANAL LITRO	SJN FCL SEMANAL LITRO	MEP SEMANAL LITRO	MARIPÁ SEMANAL LITRO	DESCOBERTO SEMANAL LITRO	ESTOQUE MÍNIMO EM LITRO	ESTOQUE MÁXIMO EM LITRO	ESTOQUE MÍNIMO EM GALÃO	ESTOQUE MÁXIMO EM GALÃO	PEDIDO QUINZENAL	PEDIDO QUINZENAL EM GALÃO
X	X	X	X	X	X	367054	Detergente Alcalino 5L	Ares DET 203	74253 - Mercominas	1/50L	250	Limpador Piso área de produção e manipulação inodor	3	9	1	10	2	5	2		29	58	6	12	55	11
X	X	X		X	X	367044	Detergente Alcalino Clorado 5L	Ares DET 239	74253 - Mercominas	1/20L	100	Limpador Multiuso para superficies	16	7	0	5	2	5	2		21	42	4	8	26	5
X	X	X	X	X	X	367040	Biguanida 5L	Ares 350	74253 - Mercominas	1/100L	500	Sanitizante alimentício inodor	4	2	0	1	0,5	1	0,5		5	10	1	2	6	1
X	X	X	X	X	X	367056	Quaternário 5L	Ares BAC 330	74253 - Mercominas	1/100L	500	Sanitizante área produção	2	3	0	1,5	0,5	1,5	0,5		7	14	1	3	12	2
X	X	X		X	X	367042	Decapante p/ gancho 5L	Ares 226	74253 - Mercominas	1/20L	100	Ganchos açougue (Diluição apenas em Bicas)	2	3	0	0	0	0	0		3	6	1	1	4	1
X	X	X	X	X	X	367038	Desinfetante concentrado floral 5L	Floralgel 301	74253 - Mercominas	1/20L	100	Limpeza de banheiros	6	5	1	5	3	5	2		21	42	4	8	36	7
X	X	X	X	X	X	367034	Sabonete Liq. p/ banheiro 5L	Lim+	71596 - FSD	X	5	Higienização das mãos em banheiros	29	3	2	5	2	5	2		19	38	4	8	9	2
X	X	X	X	X	X	367046	Detergente Neutro 5L ( usar CANDURA 5L )	Lim+	71596 - FSD	X	5	Lava louças	6	10	5	10	5	10	5		45	90	9	18	84	17
						367036	Álcool Gel 5L 	Lim+	71596 - FSD	X	5	Somente na área de produção ( banheiros )	11		0											
X	X	X		X	X	367995	Desinfetante concentrado máquina piso	Flaire Floormaq	24011 - Flaire	1/100L	500	Limpador piso máquina loja	15	2	0	2	1	1	1		7	14	1	3	ESTOQUE OK	
						374663	Detergente maquina de lavar louça 5L	71596 - FSD		1 galão 20L	1 POR MÊS		0	1							1	2	0	0	2	0
						374665	Secante maquina de lavar louça 5L	71596 - FSD		1 galão 20L	1 POR MÊS		2	1							1	2	0	0	ESTOQUE OK	"""

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
            # Garantir a Seção "Limpeza"
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = 'Limpeza'")
            secao_row = cursor.fetchone()
            if not secao_row:
                cursor.execute("INSERT INTO Secoes (Nome) VALUES ('Limpeza')")
                secao_id = cursor.lastrowid
            else:
                secao_id = secao_row[0]

            rows = raw_data.strip().split('\n')[1:] # remove header
            count = 0
            
            # Map index in the TSV array to Loja_ID
            # 14 = Consumo BCS -> Loja 1
            # 15 = Consumo BCS FCL (FCL1) -> Loja 5
            # 16 = Consumo SJN -> Loja 3
            # 17 = Consumo SJN FCL (FCL2) -> Loja 6
            # 18 = Consumo MEP -> Loja 4
            # 19 = Consumo MARIPÁ (FCL3) -> Loja 7
            
            loja_map = {
                14: 1,  # BCS
                15: 5,  # FCL 1
                16: 3,  # SJN
                17: 6,  # FCL 2
                18: 4,  # MEP
                19: 7   # FCL 3
            }

            for line in rows:
                cols = line.split('\t')
                
                # Check bounds
                if len(cols) < 8: continue
                
                codigo = cols[6].strip()
                descricao = cols[7].strip()
                marca = cols[8].strip() if len(cols) > 8 else ""
                destinacao = cols[12].strip() if len(cols) > 12 else ""
                estoque_total = get_float(cols[13] if len(cols) > 13 else "0")
                
                # Minimum and Maximum stock in Gallons (or Liters if fallbacks)
                # Col 23 = ESTOQUE MÍNIMO EM GALÃO
                # Col 24 = ESTOQUE MÁXIMO EM GALÃO
                est_min = get_float(cols[23]) if len(cols) > 23 else (get_float(cols[21]) if len(cols) > 21 else 0)
                est_max = get_float(cols[24]) if len(cols) > 24 else (get_float(cols[22]) if len(cols) > 22 else 0)

                if not codigo: continue

                # Upsert Product - Marca goes to Referencia, Fornecedor we ignore or append to Referencia 
                # Periodo_Consumo as "Semanal" for Limpeza where applicable
                sql_prod = """
                    INSERT INTO Produtos (Codigo_ERP_Principal, Nome, Destinacao_de_Uso, Referencia, Secao_ID, Estoque_Atual, Periodo_Consumo, Custo)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Semanal', 0)
                    ON DUPLICATE KEY UPDATE 
                        Nome = VALUES(Nome),
                        Destinacao_de_Uso = VALUES(Destinacao_de_Uso),
                        Referencia = VALUES(Referencia),
                        Secao_ID = VALUES(Secao_ID),
                        Estoque_Atual = VALUES(Estoque_Atual),
                        Periodo_Consumo = 'Semanal'
                """
                cursor.execute(sql_prod, (codigo, descricao, destinacao, marca, secao_id, estoque_total))

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
            print(f"Sucesso! {count} itens da Familia LIMPEZA importados com sucesso.")
    except Exception as e:
        print(f"Erro ao importar dados DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
