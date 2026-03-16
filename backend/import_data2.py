import pymysql
from db import get_connection

raw_data = """x	DESCRIÇÃO PRODUTO	DESTINAÇÃO DE USO	REFERÊNCIA - GALVANOTECK	REFERÊNCIA - CONCORRENTE	ESTOQUE	BCS	FCL 1	SJN	FCL 2	MEP	FCL 3	ESTOQUE MINIMO	ESTOQUE MÁXIMO
360589	Arame encapado kg	EMBALAR PRODUTOS PADARIA			2	7						7	8
376315	Bandeja de Isopor Preta B1 C/ 400	CARNE SECA 	CRL-001 C/ 400		8	1						1	1
366951	Bandeja de Isopor Amarela Funda 52 C/ 400	CARNE MOÍDA			22	5						5	6
370978	Bandeja de Isopor Preta Funda B2 C/ 400	CARNE PICADA	CFL-002 C/ 400		12	2						2	2
366957	Bandeja de Isopor Preta Rasa B2 C/ 400	BACALHAU	TRL-02 C/ 400		0	1						1	1
366958	Bandeja de Isopor Preta Rasa B3 C/ 400	PÃO DE ALHO 	CRL-003 C/ 400		0	5						5	6
366959	Bandeja de Isopor Preta Rasa B4 C/ 400	CARNE BIFES			3	2						2	2
366956	Bandeja de Isopor Branca Rasa B1 C/ 400	PRODUTOS ATENDIMENTO PADARIA	CRL-001 C/ 400	BICAS	7	1						1	1
366952	Bandeja de Isopor Branca Rasa B2 C/ 400	PRODUTOS EMBALADOS PADARIA	CRL-002 C/ 400		7	1						1	1
366955	Bandeja de Isopor Branca Rasa B3 C/ 400	PRODUTOS EMBALADOS PADARIA	CRL-003 C/ 400		1	2						2	2
377532	Bandeja de Isopor Preta Funda B3 C/400	SAZONAL 										0	0
369438	Bandeja Retangular Laminada n.5 c/100	ENCOMENDA BOLO		ESTOQUE ALTO	2							0	0
360973	Bandeja Retangular Laminada n.7 c/20	ENCOMENDA BOLO		ESTOQUE ALTO	20							0	0
369473	Capa para Cesta Básica 50x80 C/100	CESTA BÁSICA			0	8						8	10
366964	Disco de Isopor nº 30 C/ 400	PIZZA DA CASA 			5	4						4	5
367001	Embalagem a Vácuo 15x20cm C/ 1000	Bacon e Paio e alho			10	3						3	4
368410	Embalagem a Vácuo 15x35cm C/ 1000	Calabresa			0	2						2	2
368411	Embalagem a Vácuo 20x25cm C/ 1000	Salsicha e verduras			3	3						3	4
370472	Embalagem a Vácuo 20x35cm C/ 1000	CONGELADOS			0	1						1	1
368413	Embalagem a Vácuo 22x30cm C/ 1000	Frios fatiados e legumes			10	2						2	2
376497	Embalagem Articulada DA-10 C/100 Salgados assados, Bolo fatia	PRODUTOS EMBALADOS PADARIA	G-10 C100 / DA-10 C/100	REUTILIZADA	0	5						5	6
366970	Embalagem Articulada para 2 Doces	DOCE	G-14 C/100		3	1						1	1
376499	Embalagem Quadrada para Pequenos Doces de 200ml	DOCE	G-650 C/300	D-650 C/300	5	2						2	2
369361	Embalagem Redonda para Bolo Cone de 750g ( Lisa Tampa Média)	Bolo Confeitado 1kg / Torta premium	G-32CT C/100 - ESTOQUE ALTO	ELIMINAR	4							0	0
376501	Embalagem Redonda para Bolo Cone de 750g (Milenium Tampa Média)	Bolo Cone 750g	G-32M C/100	D-32M C/100	0	20						20	24
369367	Embalagem para Bolo G-32MA c/100	Bolo	G-32MA C/100	ELIMINAR	19							0	0
368978	Embalagem Redonda para Bolo de 1.5Kg (Milenium Tampa Alta)	Bolo 1.5kg	G-50MA C/50	ELIMINAR	1							0	0
366975	Embalagem Redonda para Bolo de 1.5Kg (Milenium Tampa Média)	Bolo 1.5kg	G-50MM C/50 - G-50A C/50	ELIMINAR	3							0	0
366977	Embalagem Redonda para Bolo de 2.2Kg	Bolo 2.2kg	G-60MM C/50		2	1						1	1
376503	Embalagem Redonda para Caçarola (Tampa Alta)	Caçarola	G-35MA C/100	D-35A C100	0	1						1	1
366983	Embalagem Retangular para Bolo de 3Kg	Bolo 3kg	G-70MM C/20		0	1						1	1
376505	Embalagem Retangular para Rocambole Pequeno de 300g	Rocambole	G-62 C/150	D-62R C/150	2	3						3	4
369801	Embalagem Retangular para Tranças Salgadas	Roscas Salgadas 	G-63MA C/ 100	ELIMINAR	1							0	0
366973	Embalagem Transparente para Panetone Trufado de 500g	SAZONAL	G-33 C/100		4	3						3	4
376507	Embalagem Triangular para Pizzabrownie	Pizza Browner	G-630 C300	D-630 C300	6	1						1	1
373627	Embalagem Sanduíche Natural G-560 C/100	SANDUICHE NATURAL	G-560 C/100		5	3						5	6
366967	Filme Poliolefínico 360x0,15	Pizza da casa			0	1						1	1
367091	Fita p/ Seladora	Seladora			30	20	3	12	6	12	6	59	71
364997	Forma de bolo Kraft 18cm c/100	Rosca doce de chocolate			0	2						2	2
368133	Forma Descartável Alumínio para Empadão 240ml C/200	Empadão	T-90 c/200		5	2						2	2
366992	Garrafa Plástica branca 1l c/25	BANHA AÇOUGUE			11							0	0
375376	Garrafa Plástica branca 300ml c/70 (TAMPA PRETA)	SUCO NATURAL			1	10						10	12
366835	Papel Absorvente para Bandeja c/ 3000	Absorvente para Carne			2	1						1	1
366969	Papel Manteiga c/400	Desenformar Bolo			2	1						1	1
366995	Placa de Isopor Branca 003 C/ 400	Frios fatiados 10F	PN 003 C/ 400	ELIMINAR	21	0						0	0
366999	Plástico Filme PVC 38x800 Rolo	Selar Produtos Padaria e Frios	COMPRA NA REDE		34	25	1	6	1	6	1	40	48
366997	Plástico Stretch Rolo	Envolver Mercadorias 			6	8						8	10
376509	Pote Acoplado 350mL	Azeitonas	G-750M C/200	D-750R C/200	0	5						5	6
376511	Pote Acoplado 250mL	Pastinhas	G-742M C/200	D-742R C/200	1	2						2	2
376513	Pote Acoplado 500ml	Pasta alho / parmesão / Biscoito	G-771M C/200	D-771R C/200	0	3						3	4
368395	Sacos PP para Farinha de Rosca	 Farinha de Rosca	SACO PP 15x30 C/ 1000		1	3						3	4
368405	Sacos PP para Farinha de Rosca	Pizza	SACO PP 30x45 C/ 1000	SUPERMAIS	3	3						3	4
368398	Sacos PP para Farinha de Rosca	Pães embalados / Polvilho	SACO PP 20x45 C/ 1000	SUPERMAIS	2	3						3	4
368392	Sacos PP para Pão Rabanada	PÃO RABANADA	SACO PP 15x70 C/ 1000	SAZONAL 	4	2						2	2
368400	Sacos PP para Pão Sírio / Panettone e Pães da Casa	Sírio / Panenttone	SACO PP 25x35 C/ 1000	SUPERMAIS	2	3						3	4
368396	Sacos PP c/1000	Torradas 	SACO PP 17x35 C/ 1000	SUPERMAIS	10	3						3	4
373090	Forma de papel para Panettone 500g c/100 Marrom	Forma de Panettone			0	1						1	1
368221	Bobiba de Papel para embalar	Embalar encomendas			0	1						1	1
360781	MARMITEX DE ISOPOR C TAMPA 750 ML -  C 100	LANCHONETE			3	1						1	1
321616	Manga para confeitar descartável G c/50	Manga para Confeitar			4	3						3	4
372827	Embalagem forma Pudim 150ml c/120	PUDIM 	G-367 C/120		1	1						1	1
377233	Copo com Tampa Bolha 400ml G-840 C/50 GALVANOTEK	SALADA DE FRUTAS	G-840 C/50		6	5						5	6
375732	Embalagem para salada G-682 c/100	SALADA PROTEICAS 	G-682 c/100		3	4						4	5
366976	Embalagem para aperitivo G-540 C/100	TABUA DE FRIOS 	G-540 C/100		4	1						1	1
374852	Sanitizante de verduras e legumes 3,6kg	Sanitizar verduras e legumes	FORNECEDOR FSD		0	1						1	1
377171	Embalagem  para torta fatiada G- 658 GALVANOTECK	TORTINHAS	G-658		2	1						1	1
377127	Copo  cristal c/ tampa bolha 200ml c/320	DOCE POTE 200ML			5	1						1	1
377173	Embalagem Forma Pudim 1100ml PW53 c/32	PUDIM 1KG	PW53 C/32		7	1						1	1
334413	Forminha de papel c/ 100 n.0 branca	Cestinha  Aberto de Alho Poro			2	4						4	5
377015	Forminha de papel c/ 100 n.4 branca	BRIGADEIRO 			2	1						1	1
13	Saco PE para alho descascado 500ml	Alho descascado 500ml			0							0	0
371430	Embalagem Articulada GA-8 C/100 Bolo Fatia	BOLO FATIA	GA-8 C/100	D-08 C/100	0	2						2	2
377701	EMBALAGEM DELPAK PUDIM NATURAL TP FILME C 200				0							0	0
377703	EMBALAGEM DELPAK PUDIM MINI TP FILME C 500				1							0	0
377705	EMBALAGEM DELPAK POTE P26 NATURAL TP FILME C 750				0							0	0
377707	EMBALAGEM DELPAK K151 NATURAL TP FILME C 200				1							0	0
377709	EMBALAGEM DELPAK K121 NATURAL TP FILME C 120				2							0	0
377711	EMBALAGEM DELPAK K106 NATURAL TP FILME C 200				1							0	0"""

def get_float(val_str):
    if not val_str: return 0.0
    v = val_str.replace('.', '').replace(',', '.')
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
            # 1. Adicionar coluna de Consumo_Medio se não existir
            try:
                cursor.execute("ALTER TABLE Estoque_Loja ADD COLUMN Consumo_Medio DECIMAL(10,2) DEFAULT 0")
                print("Coluna Consumo_Medio adicionada com sucesso.")
            except Exception as e:
                # Ignorar erro se coluna já existe
                pass
                
            # 2. Buscar/Garantir a Seção "Embalagem"
            cursor.execute("SELECT ID FROM Secoes WHERE Nome = 'Embalagem'")
            secao_row = cursor.fetchone()
            if not secao_row:
                cursor.execute("INSERT INTO Secoes (Nome) VALUES ('Embalagem')")
                secao_id = cursor.lastrowid
            else:
                secao_id = secao_row[0]

            rows = raw_data.strip().split('\n')[1:] # remove header
            count = 0
            
            # Map index to Loja_ID (1 - BCS, 3 - SJN, 4 - MEP, 5 - FCL1, 6 - FCL2, 7 - FCL3)
            # BCS = 6
            # FCL 1 = 7
            # SJN = 8
            # FCL 2 = 9
            # MEP = 10
            # FCL 3 = 11
            
            loja_map = {
                6: 1,  # BCS
                7: 5,  # FCL 1
                8: 3,  # SJN
                9: 6,  # FCL 2
                10: 4, # MEP
                11: 7  # FCL 3
            }

            for line in rows:
                cols = line.split('\t')
                
                # Minimum bounds check
                if len(cols) < 6: continue
                
                codigo = cols[0].strip()
                descricao = cols[1].strip()
                destinacao = cols[2].strip() if len(cols) > 2 else ""
                ref = cols[3].strip() if len(cols) > 3 else ""
                
                # Estes produtos são da secao_id
                estoque_total = get_float(cols[5])
                est_min = get_float(cols[12]) if len(cols) > 12 else 0
                est_max = get_float(cols[13]) if len(cols) > 13 else 0

                if not codigo: continue

                # Upsert Product
                sql_prod = """
                    INSERT INTO Produtos (Codigo_ERP_Principal, Nome, Destinacao_de_Uso, Referencia, Secao_ID, Estoque_Atual, Custo)
                    VALUES (%s, %s, %s, %s, %s, %s, 0)
                    ON DUPLICATE KEY UPDATE 
                        Nome = VALUES(Nome),
                        Destinacao_de_Uso = VALUES(Destinacao_de_Uso),
                        Referencia = VALUES(Referencia),
                        Secao_ID = VALUES(Secao_ID),
                        Estoque_Atual = VALUES(Estoque_Atual)
                """
                cursor.execute(sql_prod, (codigo, descricao, destinacao, ref, secao_id, estoque_total))

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
            print(f"Sucesso! {count} itens da Familia Embalagens adaptados e importados com sucesso.")
    except Exception as e:
        print(f"Erro ao importar dados DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
