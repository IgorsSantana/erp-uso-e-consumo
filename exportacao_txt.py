def gerar_linha_txt(codigo_produto: str, custo: float, quantidade: int) -> str:
    """
    Gera uma linha posicional para exportação TXT com exatamente 25 caracteres.
    
    Regras:
    - Código (13 posições): zeros à esquerda.
    - Quantidade (6 posições): zeros à esquerda.
    - Custo (6 posições): em centavos (sem vírgula), zeros à esquerda.
    """
    # 1. Código: 13 posições com zeros à esquerda
    codigo_str = str(codigo_produto).zfill(13)
    
    # 2. Quantidade: 6 posições com zeros à esquerda
    quantidade_str = str(int(quantidade)).zfill(6)
    
    # 3. Custo: 6 posições (em centavos), zeros à esquerda
    # Multiplica por 100 para converter reais em centavos e arredonda para evitar problemas de float (ex: 1.39 * 100 = 139.0)
    custo_centavos = int(round(custo * 100))
    custo_str = str(custo_centavos).zfill(6)
    
    # 4. Concatena tudo
    linha = f"{codigo_str}{quantidade_str}{custo_str}"
    
    # Validação de segurança (garantir que sempre terá 25 posições)
    if len(linha) != 25:
        raise ValueError(f"A linha gerada tem {len(linha)} caracteres, mas deve ter exatamente 25. Dados: {linha}")
        
    return linha

# --- Teste com o exemplo fornecido ---
if __name__ == "__main__":
    codigo = "376520"
    custo = 1.39
    quantidade = 20
    
    resultado = gerar_linha_txt(codigo, custo, quantidade)
    
    print(f"Entrada: Produto {codigo} | R$ {custo} | Qtd {quantidade}")
    print(f"Saída Esperada : 0000000376520000020000139")
    print(f"Saída Executada: {resultado}")
    print(f"Número de caracteres: {len(resultado)}")
    
    assert resultado == "0000000376520000020000139", "Erro: A string gerada não corresponde à esperada!"
    print("Teste passou com sucesso!")
